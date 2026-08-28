import os
import json
import re
from datetime import datetime, timedelta

from openai import OpenAI

from extensions import db
from models import Expense
from legal_docs_search import build_legal_context_block


# ============================================================
# CONFIGURACIÓN OPENAI
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

client = (
    OpenAI(api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY
    else None
)


# ============================================================
# UTILIDADES
# ============================================================

def _extract_json(text: str):

    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:

        try:
            return json.loads(
                text[start:end + 1]
            )
        except Exception:
            pass

    return None


def _safe_float(value):

    try:
        return float(value or 0)
    except (
        ValueError,
        TypeError
    ):
        return 0.0


# ============================================================
# PARSEAR TEXTO DE GASTO
# ============================================================

def parse_expense_text(text: str) -> dict:

    if not text:
        return {}

    if client:

        try:

            prompt = f"""
Eres un asistente especializado en registrar
transacciones financieras personales.

Analiza el siguiente texto:

{text}

Devuelve ÚNICAMENTE JSON válido:

{{
    "amount": null,
    "currency": "GTQ",
    "merchant": null,
    "description": null,
    "category": null,
    "payment_method": null,
    "expense_date": null,
    "transaction_type": "expense"
}}

REGLAS:

- amount: monto de la transacción.
- currency: moneda.
- merchant: comercio o establecimiento.
- description: descripción breve.
- category: categoría financiera.
- payment_method: método de pago.
- expense_date: formato YYYY-MM-DD.
- transaction_type: "expense" o "income".
- No inventes información.
- Si un dato no aparece utiliza null.
"""

            response = client.responses.create(
                model=OPENAI_MODEL,
                input=prompt
            )

            output_text = (
                response.output_text.strip()
            )

            result = _extract_json(
                output_text
            )

            if result:

                result.setdefault(
                    "transaction_type",
                    "expense"
                )

                result[
                    "proposal_source"
                ] = "openai"

                return result

        except Exception as e:

            print(
                "OpenAI parse expense error:",
                type(e).__name__,
                str(e)
            )

    return _expense_fallback(text)


# ============================================================
# FALLBACK PARA TEXTO
# ============================================================

def _expense_fallback(text: str) -> dict:

    amount = None

    match = re.search(
        r"(\d+(?:[.,]\d+)?)",
        text
    )

    if match:

        try:

            amount = float(
                match.group(1).replace(
                    ",",
                    "."
                )
            )

        except Exception:

            amount = None

    lower_text = text.lower()

    category = None
    payment_method = None
    transaction_type = "expense"

    # ========================================================
    # TIPO
    # ========================================================

    if any(
        word in lower_text
        for word in [
            "recibí",
            "recibi",
            "ingreso",
            "me pagaron",
            "salario",
            "gané",
            "gane"
        ]
    ):

        transaction_type = "income"

    # ========================================================
    # CATEGORÍA
    # ========================================================

    if any(
        word in lower_text
        for word in [
            "walmart",
            "supermercado",
            "super",
            "despensa"
        ]
    ):

        category = "Supermercado"

    elif any(
        word in lower_text
        for word in [
            "gasolina",
            "uber",
            "taxi",
            "bus",
            "transporte"
        ]
    ):

        category = "Transporte"

    elif any(
        word in lower_text
        for word in [
            "restaurante",
            "pizza",
            "comida",
            "cafe",
            "café"
        ]
    ):

        category = "Alimentación"

    # ========================================================
    # MÉTODO DE PAGO
    # ========================================================

    if "tarjeta" in lower_text:

        payment_method = "Tarjeta"

    elif "efectivo" in lower_text:

        payment_method = "Efectivo"

    elif "transferencia" in lower_text:

        payment_method = "Transferencia"

    return {

        "amount": amount,

        "currency": "GTQ",

        "merchant": None,

        "description": text,

        "category": category,

        "payment_method": payment_method,

        "expense_date": None,

        "transaction_type":
            transaction_type,

        "proposal_source":
            "fallback"

    }


# ============================================================
# CONTEXTO FINANCIERO DEL USUARIO
# ============================================================

def get_user_financial_context(user_id):

    expenses = (
        Expense.query
        .filter_by(
            user_id=user_id
        )
        .order_by(
            Expense.expense_date.desc()
        )
        .all()
    )

    # ========================================================
    # SIN TRANSACCIONES
    # ========================================================

    if not expenses:

        return {

            "total_transactions": 0,

            "total_income": 0,

            "total_expenses": 0,

            "balance": 0,

            "message":
                "El usuario todavía no tiene "
                "transacciones registradas."

        }

    # ========================================================
    # FECHAS
    # ========================================================

    today = datetime.utcnow().date()

    current_month = today.month
    current_year = today.year

    previous_month_date = (
        today.replace(day=1)
        - timedelta(days=1)
    )

    previous_month = (
        previous_month_date.month
    )

    previous_year = (
        previous_month_date.year
    )

    # ========================================================
    # TOTALES
    # ========================================================

    total_income = 0
    total_expenses = 0

    current_month_income = 0
    current_month_expenses = 0

    previous_month_income = 0
    previous_month_expenses = 0

    # ========================================================
    # AGRUPACIONES
    # ========================================================

    expenses_by_category = {}
    income_by_category = {}

    expenses_by_payment_method = {}
    expenses_by_merchant = {}

    expense_transactions = []
    income_transactions = []

    recent_transactions = []

    # ========================================================
    # PROCESAR TRANSACCIONES
    # ========================================================

    for expense in expenses:

        amount = _safe_float(
            expense.amount
        )

        transaction_type = (
            expense.transaction_type
            or "expense"
        )

        expense_date = (
            expense.expense_date
        )

        # ====================================================
        # INGRESOS
        # ====================================================

        if transaction_type == "income":

            total_income += amount

            income_transactions.append(
                amount
            )

            category = (
                expense.category
                or "Sin categoría"
            )

            income_by_category[
                category
            ] = (
                income_by_category.get(
                    category,
                    0
                )
                + amount
            )

            if expense_date:

                if (
                    expense_date.month
                    == current_month
                    and
                    expense_date.year
                    == current_year
                ):

                    current_month_income += (
                        amount
                    )

                elif (
                    expense_date.month
                    == previous_month
                    and
                    expense_date.year
                    == previous_year
                ):

                    previous_month_income += (
                        amount
                    )

        # ====================================================
        # EGRESOS
        # ====================================================

        else:

            total_expenses += amount

            expense_transactions.append(
                amount
            )

            category = (
                expense.category
                or "Sin categoría"
            )

            expenses_by_category[
                category
            ] = (
                expenses_by_category.get(
                    category,
                    0
                )
                + amount
            )

            payment_method = (
                expense.payment_method
                or "No especificado"
            )

            expenses_by_payment_method[
                payment_method
            ] = (
                expenses_by_payment_method.get(
                    payment_method,
                    0
                )
                + amount
            )

            merchant = (
                expense.merchant
                or "Comercio no especificado"
            )

            expenses_by_merchant[
                merchant
            ] = (
                expenses_by_merchant.get(
                    merchant,
                    0
                )
                + amount
            )

            if expense_date:

                if (
                    expense_date.month
                    == current_month
                    and
                    expense_date.year
                    == current_year
                ):

                    current_month_expenses += (
                        amount
                    )

                elif (
                    expense_date.month
                    == previous_month
                    and
                    expense_date.year
                    == previous_year
                ):

                    previous_month_expenses += (
                        amount
                    )

        # ====================================================
        # TRANSACCIONES RECIENTES
        # ====================================================

        if len(
            recent_transactions
        ) < 20:

            recent_transactions.append({

                "date":
                    (
                        expense_date.isoformat()
                        if expense_date
                        else None
                    ),

                "type":
                    transaction_type,

                "amount":
                    round(
                        amount,
                        2
                    ),

                "currency":
                    (
                        expense.currency
                        or "GTQ"
                    ),

                "merchant":
                    expense.merchant,

                "category":
                    expense.category,

                "description":
                    expense.description,

                "payment_method":
                    expense.payment_method

            })

    # ========================================================
    # BALANCE
    # ========================================================

    balance = (
        total_income
        - total_expenses
    )

    current_balance = (
        current_month_income
        - current_month_expenses
    )

    # ========================================================
    # PORCENTAJES
    # ========================================================

    if total_income > 0:

        spending_ratio = (
            total_expenses
            / total_income
        ) * 100

        savings_ratio = (
            balance
            / total_income
        ) * 100

    else:

        spending_ratio = None
        savings_ratio = None

    # ========================================================
    # PROMEDIOS
    # ========================================================

    if expense_transactions:

        average_expense = (
            sum(
                expense_transactions
            )
            / len(
                expense_transactions
            )
        )

    else:

        average_expense = 0

    if income_transactions:

        average_income = (
            sum(
                income_transactions
            )
            / len(
                income_transactions
            )
        )

    else:

        average_income = 0

    # ========================================================
    # GASTO MÁS GRANDE
    # ========================================================

    largest_expense = (
        max(expense_transactions)
        if expense_transactions
        else 0
    )

    # ========================================================
    # CATEGORÍAS
    # ========================================================

    top_categories = sorted(
        expenses_by_category.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    # ========================================================
    # COMERCIOS
    # ========================================================

    top_merchants = sorted(
        expenses_by_merchant.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    # ========================================================
    # MÉTODOS DE PAGO
    # ========================================================

    payment_methods = sorted(
        expenses_by_payment_method.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # ========================================================
    # CAMBIO DE GASTOS
    # ========================================================

    if previous_month_expenses > 0:

        expense_change_percentage = (
            (
                current_month_expenses
                - previous_month_expenses
            )
            / previous_month_expenses
        ) * 100

    else:

        expense_change_percentage = None

    # ========================================================
    # CAMBIO DE INGRESOS
    # ========================================================

    if previous_month_income > 0:

        income_change_percentage = (
            (
                current_month_income
                - previous_month_income
            )
            / previous_month_income
        ) * 100

    else:

        income_change_percentage = None

    # ========================================================
    # CATEGORÍA PRINCIPAL
    # ========================================================

    if top_categories:

        top_category = {

            "name":
                top_categories[0][0],

            "amount":
                round(
                    top_categories[0][1],
                    2
                )

        }

    else:

        top_category = None

    # ========================================================
    # PORCENTAJE POR CATEGORÍA
    # ========================================================

    category_percentages = {}

    for category, amount in top_categories:

        if total_expenses > 0:

            percentage = (
                amount
                / total_expenses
            ) * 100

        else:

            percentage = 0

        category_percentages[
            category
        ] = {

            "amount":
                round(
                    amount,
                    2
                ),

            "percentage":
                round(
                    percentage,
                    2
                )

        }

    # ========================================================
    # RESULTADO
    # ========================================================

    return {

        "total_transactions":
            len(expenses),

        "total_income":
            round(
                total_income,
                2
            ),

        "total_expenses":
            round(
                total_expenses,
                2
            ),

        "balance":
            round(
                balance,
                2
            ),

        "spending_ratio":
            (
                round(
                    spending_ratio,
                    2
                )
                if spending_ratio is not None
                else None
            ),

        "savings_ratio":
            (
                round(
                    savings_ratio,
                    2
                )
                if savings_ratio is not None
                else None
            ),

        "average_expense":
            round(
                average_expense,
                2
            ),

        "average_income":
            round(
                average_income,
                2
            ),

        "largest_expense":
            round(
                largest_expense,
                2
            ),

        "top_category":
            top_category,

        "category_percentages":
            category_percentages,

        "expenses_by_category": {

            category:
                round(
                    amount,
                    2
                )

            for category, amount
            in top_categories

        },

        "income_by_category": {

            category:
                round(
                    amount,
                    2
                )

            for category, amount
            in income_by_category.items()

        },

        "top_merchants": {

            merchant:
                round(
                    amount,
                    2
                )

            for merchant, amount
            in top_merchants

        },

        "payment_methods": {

            method:
                round(
                    amount,
                    2
                )

            for method, amount
            in payment_methods

        },

        "current_month": {

            "income":
                round(
                    current_month_income,
                    2
                ),

            "expenses":
                round(
                    current_month_expenses,
                    2
                ),

            "balance":
                round(
                    current_balance,
                    2
                )

        },

        "previous_month": {

            "income":
                round(
                    previous_month_income,
                    2
                ),

            "expenses":
                round(
                    previous_month_expenses,
                    2
                )

        },

        "expense_change_percentage":
            (
                round(
                    expense_change_percentage,
                    2
                )
                if expense_change_percentage
                is not None
                else None
            ),

        "income_change_percentage":
            (
                round(
                    income_change_percentage,
                    2
                )
                if income_change_percentage
                is not None
                else None
            ),

        "recent_transactions":
            recent_transactions

    }


# ============================================================
# ANÁLISIS FINANCIERO CON IA
# ============================================================

def analyze_finances_with_ai(user_id):

    context = (
        get_user_financial_context(
            user_id
        )
    )

    if not client:

        return {

            "insights": [],

            "financial_context":
                context,

            "error":
                "OPENAI_API_KEY no está configurada."

        }

    try:

        prompt = f"""
Eres un asistente de finanzas personales.

Analiza los datos financieros REALES
del usuario.

DATOS:

{json.dumps(
    context,
    ensure_ascii=False,
    indent=2
)}

Tu objetivo NO es simplemente decir
cuál es la categoría donde más gasta.

Debes proporcionar un análisis financiero
personalizado.

============================================================
ANALIZA
============================================================

1. INGRESOS VS GASTOS

Determina si el usuario gasta:

- menos que sus ingresos
- aproximadamente lo mismo
- más que sus ingresos

Explica qué significa.

------------------------------------------------------------

2. BALANCE

Analiza el balance general y el balance
del mes actual.

------------------------------------------------------------

3. CAPACIDAD DE AHORRO

Utiliza:

- savings_ratio
- balance
- ingresos
- gastos

Si existe capacidad de ahorro,
propón una estrategia razonable.

------------------------------------------------------------

4. CATEGORÍAS

Identifica las categorías principales.

Analiza qué porcentaje representan
del total de gastos.

No asumas que gastar más en una categoría
significa necesariamente que sea un problema.

------------------------------------------------------------

5. GASTO PROMEDIO

Analiza el gasto promedio.

Compáralo con el gasto más grande.

------------------------------------------------------------

6. GASTOS GRANDES

Si existe un gasto considerablemente
superior al promedio, indícalo.

------------------------------------------------------------

7. COMERCIOS

Analiza si existe concentración de gastos
en determinados comercios.

------------------------------------------------------------

8. MÉTODOS DE PAGO

Analiza los métodos de pago cuando
existan suficientes datos.

No asumas que utilizar tarjeta es malo.

------------------------------------------------------------

9. EVOLUCIÓN

Compara:

- ingresos actuales
- ingresos anteriores
- gastos actuales
- gastos anteriores

Calcula e interpreta los cambios.

------------------------------------------------------------

10. ALERTAS

Genera alertas solamente cuando
los datos las justifiquen.

Ejemplos:

- gastos superiores a ingresos
- balance negativo
- crecimiento importante de gastos
- concentración importante de gastos

------------------------------------------------------------

11. AHORRO

Busca oportunidades concretas
para ahorrar.

Evita consejos genéricos.

------------------------------------------------------------

12. EDUCACIÓN FINANCIERA

Cuando sea útil, explica conceptos
de forma sencilla.

------------------------------------------------------------

13. CONSEJOS PERSONALIZADOS

Los consejos deben relacionarse
directamente con los datos.

------------------------------------------------------------

14. POCAS TRANSACCIONES

Si existen menos de 10 transacciones,
reconoce que el análisis es limitado.

No inventes patrones.

Puedes recomendar registrar más
transacciones para obtener mejores
predicciones.

============================================================
TIPOS
============================================================

Utiliza únicamente:

success
info
warning
alert
saving

============================================================
FORMATO
============================================================

Devuelve únicamente JSON:

{{
    "insights": [
        {{
            "type": "warning",
            "title": "Título corto",
            "description": "Explicación basada en datos.",
            "recommendation": "Consejo práctico.",
            "priority": 1
        }}
    ]
}}

Genera bastantes insights para que el usuario tenga feedback general y profundo de sus gastos e ingresos
No importa que haya poca informacion en la db del usuario, coloca datos relevantes.
Coloca consejos financieros especigicops y generales relacionados al usuario




Ordena los insights por importancia.

============================================================
REGLAS
============================================================

- No inventes información.
- No inventes transacciones.
- No inventes ingresos.
- No inventes gastos.
- No inventes fechas.
- No inventes hábitos.
- Utiliza solamente los datos proporcionados.
- Puedes realizar cálculos matemáticos.
- Sé claro.
- Sé profesional.
- Responde en español.
- No juzgues al usuario.
- No presentes consejos como órdenes.
- Explica por qué cada recomendación es relevante.
"""

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt
        )

        output_text = (
            response.output_text.strip()
        )

        result = _extract_json(
            output_text
        )

        if result:

            insights = result.get(
                "insights",
                []
            )

            insights.sort(
                key=lambda x: x.get(
                    "priority",
                    999
                )
            )

            result["insights"] = (
                insights
            )

            result[
                "financial_context"
            ] = context

            return result

        return {

            "insights": [],

            "financial_context":
                context,

            "raw":
                output_text

        }

    except Exception as e:

        print(
            "Financial AI error:",
            type(e).__name__,
            str(e)
        )

        return {

            "insights": [],

            "financial_context":
                context,

            "error":
                str(e)

        }


# ============================================================
# CHAT FINANCIERO PERSONAL
# ============================================================

def ask_financial_ai(
    user_id,
    question,
    conversation_history=None
):

    if not question:

        return {

            "answer":
                "Escribe una pregunta financiera."

        }

    if not client:

        return {

            "answer":
                "El servicio de inteligencia financiera "
                "no está configurado."

        }

    try:

        financial_context = (
            get_user_financial_context(
                user_id
            )
        )

        history = (
            conversation_history
            or []
        )

        history = history[-10:]

        conversation_text = ""

        for message in history:

            role = message.get(
                "role",
                "user"
            )

            content = message.get(
                "content",
                ""
            )

            conversation_text += (
                f"{role}: {content}\n"
            )

        # ====================================================
        # BÚSQUEDA ESPONTÁNEA EN DOCUMENTOS LEGALES
        # ====================================================
        # No hay un prompt fijo tipo "si pregunta X responde Y".
        # search_legal_docs (dentro de build_legal_context_block)
        # puntúa la pregunta del usuario contra los PDFs
        # indexados (fundamentos legales para emprendedores y
        # guía de formalización laboral) usando coincidencia de
        # palabras clave. Si la pregunta no tiene relación legal
        # ("¿cuánto gasté en comida?"), esto devuelve string
        # vacío y no se agrega nada al prompt — la IA ni se
        # entera de que existen esos PDFs para esa pregunta.

        legal_context = build_legal_context_block(question)

        legal_context_section = ""

        if legal_context:

            legal_context_section = f"""
============================================================
DOCUMENTOS LEGALES DE REFERENCIA
============================================================

Se encontraron fragmentos potencialmente relevantes en los
documentos de referencia legal/laboral disponibles. Úsalos
ÚNICAMENTE si de verdad ayudan a responder la pregunta del
usuario. Si no aplican a lo que pregunta, ignóralos por
completo y no los menciones.

Cuando SÍ los uses, indica de qué documento sale la
información (por ejemplo: "según la Guía para la
Formalización Laboral...").

No trates estos fragmentos como asesoría legal vinculante:
son material de referencia general, no un sustituto de un
abogado o contador.

{legal_context}

"""

        prompt = f"""
Eres el administrador financiero
personal del usuario.

Utiliza los datos financieros reales
proporcionados por PostgreSQL.

============================================================
DATOS FINANCIEROS
============================================================

{json.dumps(
    financial_context,
    ensure_ascii=False,
    indent=2
)}
{legal_context_section}
============================================================
HISTORIAL DEL CHAT
============================================================

{conversation_text}

============================================================
PREGUNTA DEL USUARIO
============================================================

{question}

============================================================
INSTRUCCIONES
============================================================

- Responde en español.
- Sé claro.
- Sé natural.
- Personaliza la respuesta.
- Utiliza los datos de PostgreSQL.
- No inventes información.
- No inventes transacciones.
- No inventes cantidades.
- No inventes fechas.
- Puedes hacer cálculos.
- Explica cálculos importantes.
- Da consejos prácticos.
- Si existen pocos registros, dilo.
- Si no existe suficiente información,
  indícalo claramente.
- No juzgues al usuario.
- No tomes decisiones por el usuario.
- Presenta recomendaciones.
- Mantén el contexto de la conversación.
- Si el usuario pregunta por una transacción,
  utiliza únicamente las transacciones disponibles.
- Si se te proporcionaron fragmentos de documentos legales
  de referencia y son relevantes a la pregunta, apóyate en
  ellos y cita el documento de origen. Si no aplican, no los
  menciones.

Tu objetivo es ayudar al usuario a comprender
sus finanzas y tomar mejores decisiones.
Dale un toque visualmente estetico, utiliza viñetas, cursiva, negrita, signos, emogis, sin perder la formalidad, no dejando de lado el profesionalismo
Quiero que el texto sea visualmente agradable, que no genere ruido visual
Ademas, te llamas NexoAI, tengo en cuenta por si se refieren a ti de esa forma, tambien podrian llegar a decirte chat u otra forma, pero tu nombre dado ppor tu creador es NexoAI
"""

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt
        )

        answer = (
            response.output_text.strip()
        )

        return {

            "answer":
                answer,

            "financial_context":
                financial_context

        }

    except Exception as e:

        print(
            "Financial chat error:",
            type(e).__name__,
            str(e)
        )

        return {

            "answer":
                "Ocurrió un problema al procesar "
                "tu pregunta. Intenta nuevamente.",

            "error":
                str(e)

        }


# ============================================================
# SIMULACIÓN DE AHORRO
# ============================================================

def simulate_savings(
    amount: float,
    months=None
):

    if months is None:

        months = [
            1,
            6,
            12,
            24
        ]

    months = sorted(
        set(
            int(m)
            for m in months
        )
    )

    projections = {}

    for month in months:

        projections[
            str(month)
        ] = round(
            amount * month,
            2
        )

    return {

        "monthly_amount":
            float(amount),

        "projections":
            projections

    }
