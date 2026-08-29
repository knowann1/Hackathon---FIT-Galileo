import os
import json
import re
from datetime import datetime, timedelta

from openai import OpenAI

from extensions import db
from models import Expense

from legal_docs_search import (
    build_legal_context_block
)


# ============================================================
# CONFIGURACIÓN OPENAI
# ============================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

client = (
    OpenAI(
        api_key=OPENAI_API_KEY
    )
    if OPENAI_API_KEY
    else None
)


# ============================================================
# UTILIDADES
# ============================================================

def _extract_json(text: str):

    if not text:

        return None

    text = text.strip()

    # ========================================================
    # JSON DIRECTO
    # ========================================================

    try:

        return json.loads(
            text
        )

    except Exception:

        pass

    # ========================================================
    # JSON DENTRO DE TEXTO
    # ========================================================

    start = text.find(
        "{"
    )

    end = text.rfind(
        "}"
    )

    if (
        start != -1
        and end != -1
        and end > start
    ):

        try:

            return json.loads(
                text[
                    start:end + 1
                ]
            )

        except Exception:

            pass

    return None


def _safe_float(value):

    try:

        return float(
            value or 0
        )

    except (
        ValueError,
        TypeError
    ):

        return 0.0


# ============================================================
# PARSEAR TEXTO DE GASTO
# ============================================================

def parse_expense_text(
    text: str
) -> dict:

    if not text:

        return {}

    if client:

        try:

            prompt = f"""
Eres un asistente especializado
en registrar transacciones financieras.

Analiza este texto:

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

- amount: monto.
- currency: moneda.
- merchant: comercio.
- description: descripción breve.
- category: categoría.
- payment_method: método de pago.
- expense_date: YYYY-MM-DD.
- transaction_type: expense o income.
- No inventes datos.
- Si no aparece un dato utiliza null.
"""

            response = client.chat.completions.create(

                model=OPENAI_MODEL,

                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]

            )

            output_text = (
                response.choices[0].message.content
                or ""
            ).strip()

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

        except Exception as exc:

            print(
                "OpenAI parse expense error:",
                type(exc).__name__,
                str(exc)
            )

    return _expense_fallback(
        text
    )


# ============================================================
# FALLBACK
# ============================================================

def _expense_fallback(
    text: str
) -> dict:

    amount = None

    match = re.search(
        r"(\d+(?:[.,]\d+)?)",
        text
    )

    if match:

        try:

            amount = float(
                match.group(
                    1
                ).replace(
                    ",",
                    "."
                )
            )

        except Exception:

            amount = None

    lower_text = (
        text.lower()
    )

    category = None
    payment_method = None
    transaction_type = "expense"

    # ========================================================
    # INGRESO
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
    # PAGO
    # ========================================================

    if "tarjeta" in lower_text:

        payment_method = "Tarjeta"

    elif "efectivo" in lower_text:

        payment_method = "Efectivo"

    elif "transferencia" in lower_text:

        payment_method = "Transferencia"

    return {

        "amount":
            amount,

        "currency":
            "GTQ",

        "merchant":
            None,

        "description":
            text,

        "category":
            category,

        "payment_method":
            payment_method,

        "expense_date":
            None,

        "transaction_type":
            transaction_type,

        "proposal_source":
            "fallback"
    }


# ============================================================
# CONTEXTO FINANCIERO
# ============================================================

def get_user_financial_context(
    user_id
):

    expenses = (
        Expense.query
        .filter_by(
            user_id=user_id
        )
        .order_by(
            Expense.expense_date.desc(),
            Expense.id.desc()
        )
        .all()
    )

    if not expenses:

        return {

            "total_transactions":
                0,

            "total_income":
                0,

            "total_expenses":
                0,

            "balance":
                0,

            "message":
                (
                    "El usuario todavía no tiene "
                    "transacciones registradas."
                )
        }

    today = datetime.utcnow().date()

    current_month = (
        today.month
    )

    current_year = (
        today.year
    )

    previous_month_date = (
        today.replace(
            day=1
        )
        - timedelta(
            days=1
        )
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
    # TRANSACCIONES
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
        # GASTOS
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
        # RECIENTES
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
    # RATIOS
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

    average_expense = (

        sum(
            expense_transactions
        )
        / len(
            expense_transactions
        )

        if expense_transactions
        else 0
    )

    average_income = (

        sum(
            income_transactions
        )
        / len(
            income_transactions
        )

        if income_transactions
        else 0
    )

    largest_expense = (

        max(
            expense_transactions
        )

        if expense_transactions
        else 0
    )

    # ========================================================
    # CATEGORÍAS
    # ========================================================

    top_categories = sorted(
        expenses_by_category.items(),
        key=lambda item: item[1],
        reverse=True
    )[:10]

    top_category = None

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

    category_percentages = {}

    for category, amount in top_categories:

        percentage = (

            (
                amount
                / total_expenses
            ) * 100

            if total_expenses > 0
            else 0
        )

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
    # COMERCIOS
    # ========================================================

    top_merchants = sorted(
        expenses_by_merchant.items(),
        key=lambda item: item[1],
        reverse=True
    )[:10]

    # ========================================================
    # MÉTODOS DE PAGO
    # ========================================================

    payment_methods = sorted(
        expenses_by_payment_method.items(),
        key=lambda item: item[1],
        reverse=True
    )

    # ========================================================
    # CAMBIOS
    # ========================================================

    expense_change_percentage = None

    if previous_month_expenses > 0:

        expense_change_percentage = (

            (
                current_month_expenses
                - previous_month_expenses
            )
            / previous_month_expenses

        ) * 100

    income_change_percentage = None

    if previous_month_income > 0:

        income_change_percentage = (

            (
                current_month_income
                - previous_month_income
            )
            / previous_month_income

        ) * 100

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
                ),

            "balance":
                round(
                    previous_month_income
                    - previous_month_expenses,
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

def analyze_finances_with_ai(
    user_id
):

    # ========================================================
    # OBTENER CONTEXTO
    # ========================================================

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

        financial_json = json.dumps(
            context,
            ensure_ascii=False,
            indent=2,
            default=str
        )

        prompt = f"""
Eres NexoAI, un asistente profesional
de finanzas personales.

Analiza ÚNICAMENTE los datos financieros
reales proporcionados a continuación.

DATOS FINANCIEROS:

{financial_json}

============================================================
OBJETIVO
============================================================

Genera un análisis financiero personalizado.

Analiza, cuando existan datos suficientes:

1. Ingresos frente a gastos.

2. Balance.

3. Capacidad de ahorro.

4. Categorías principales.

5. Porcentaje de cada categoría.

6. Gasto promedio.

7. Gastos grandes.

8. Comercios frecuentes.

9. Métodos de pago.

10. Evolución respecto al mes anterior.

11. Presupuestos.

12. Oportunidades concretas de ahorro.

13. Alertas financieras justificadas por los datos.

14. Educación financiera cuando sea útil.

============================================================
POCAS TRANSACCIONES
============================================================

Si hay menos de 10 transacciones:

- reconoce que el análisis tiene información limitada;
- no inventes patrones;
- no inventes hábitos;
- puedes dar recomendaciones basadas en los datos existentes.

============================================================
REGLAS
============================================================

- No inventes datos.
- No inventes transacciones.
- No inventes cantidades.
- No inventes fechas.
- No inventes hábitos.
- No juzgues al usuario.
- Puedes hacer cálculos.
- Utiliza quetzales (Q) cuando corresponda.
- Los consejos deben estar relacionados con los datos.
- No presentes recomendaciones como órdenes.
- No afirmes que una categoría es mala solamente porque tiene el mayor gasto.
- Una categoría alta puede ser completamente normal dependiendo del contexto.
- Si no existe suficiente información, dilo.
- Sé concreto.
- Sé profesional.
- Responde en español.

============================================================
TIPOS PERMITIDOS
============================================================

Utiliza solamente:

success
info
warning
alert
saving

============================================================
FORMATO
============================================================

Devuelve ÚNICAMENTE JSON válido.

Formato:

{{
    "insights": [
        {{
            "type": "warning",
            "title": "Título corto",
            "description": "Explicación basada en los datos.",
            "recommendation": "Consejo práctico basado en los datos.",
            "priority": 1
        }}
    ]
}}

Genera entre 4 y 8 insights cuando exista
suficiente información.

Si hay poca información, genera los insights
que realmente puedan justificarse.

Ordena por importancia.

No incluyas texto fuera del JSON.
"""

        response = client.chat.completions.create(

            model=OPENAI_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]

        )

        output_text = (
            response.choices[0].message.content
            or ""
        ).strip()

        result = _extract_json(
            output_text
        )

        if not result:

            return {

                "insights": [],

                "financial_context":
                    context,

                "error":
                    "La IA no devolvió un JSON válido."
            }

        insights = result.get(
            "insights",
            []
        )

        if not isinstance(
            insights,
            list
        ):

            insights = []

        # ====================================================
        # LIMPIAR INSIGHTS
        # ====================================================

        valid_types = {
            "success",
            "info",
            "warning",
            "alert",
            "saving"
        }

        cleaned_insights = []

        for insight in insights:

            if not isinstance(
                insight,
                dict
            ):
                continue

            insight_type = (
                insight.get("type")
                or "info"
            )

            if insight_type not in valid_types:

                insight_type = "info"

            cleaned_insights.append({

                "type":
                    insight_type,

                "title":
                    str(
                        insight.get(
                            "title"
                        )
                        or "Análisis financiero"
                    ),

                "description":
                    str(
                        insight.get(
                            "description"
                        )
                        or ""
                    ),

                "recommendation":
                    str(
                        insight.get(
                            "recommendation"
                        )
                        or ""
                    ),

                "priority":
                    _safe_float(
                        insight.get(
                            "priority",
                            999
                        )
                    )
            })

        cleaned_insights.sort(
            key=lambda item: item[
                "priority"
            ]
        )

        return {

            "insights":
                cleaned_insights,

            "financial_context":
                context
        }

    except Exception as exc:

        print("=" * 60)
        print("FINANCIAL AI ERROR")
        print("Tipo:", type(exc).__name__)
        print("Error:", str(exc))
        print("=" * 60)

        return {

            "insights": [],

            "financial_context":
                context,

            "error":
                str(exc)
        }


# ============================================================
# CHAT FINANCIERO
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
                (
                    "El servicio de inteligencia "
                    "financiera no está configurado."
                )
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

        if not isinstance(
            history,
            list
        ):

            history = []

        history = history[-10:]

        conversation_text = ""

        for message in history:

            if not isinstance(
                message,
                dict
            ):
                continue

            role = (
                message.get(
                    "role"
                )
                or "user"
            )

            content = (
                message.get(
                    "content"
                )
                or message.get(
                    "message"
                )
                or ""
            )

            if not content:
                continue

            conversation_text += (
                f"{role}: {content}\n"
            )

        # ====================================================
        # DOCUMENTOS LEGALES
        # ====================================================

        legal_context = ""

        try:

            legal_result = (
                build_legal_context_block(
                    question
                )
            )

            if legal_result:

                legal_context = f"""

============================================================
DOCUMENTOS LEGALES DE REFERENCIA
============================================================

{legal_result}

Utiliza estos documentos únicamente
si son relevantes para la pregunta.

Si utilizas información de ellos,
menciona su documento de origen.

No los presentes como asesoría legal
personalizada ni vinculante.

"""

        except Exception as exc:

            print(
                "Legal context error:",
                type(exc).__name__,
                str(exc)
            )

        # ====================================================
        # PROMPT
        # ====================================================

        prompt = f"""
Eres NexoAI, el administrador financiero
personal del usuario.

Utiliza los datos financieros reales
proporcionados por la aplicación.

============================================================
DATOS FINANCIEROS
============================================================

{json.dumps(
    financial_context,
    ensure_ascii=False,
    indent=2,
    default=str
)}

{legal_context}

============================================================
HISTORIAL DEL CHAT
============================================================

{conversation_text}

============================================================
PREGUNTA ACTUAL
============================================================

{question}

============================================================
INSTRUCCIONES
============================================================

- Responde en español.
- Sé claro.
- Sé natural.
- Personaliza la respuesta.
- Utiliza los datos financieros disponibles.
- No inventes información.
- No inventes transacciones.
- No inventes cantidades.
- No inventes fechas.
- Puedes hacer cálculos.
- Explica cálculos importantes.
- Da consejos prácticos.
- Si existen pocos registros, dilo.
- Si no existe suficiente información, indícalo.
- No juzgues al usuario.
- No tomes decisiones por el usuario.
- Presenta recomendaciones.
- Mantén el contexto de la conversación.
- Si el usuario pregunta por una transacción,
  utiliza únicamente las transacciones disponibles.
- Si los documentos legales son relevantes,
  utilízalos correctamente.
- Si no son relevantes, ignóralos.
- Nunca reveles información de otros usuarios.

FORMATO:

Haz la respuesta visualmente agradable
sin generar ruido visual.

Puedes utilizar:

- **negrita**
- *cursiva*
- viñetas
- emojis moderados
- títulos cortos

Mantén siempre un tono profesional.

Tu nombre es **NexoAI**.
"""

        response = client.chat.completions.create(

            model=OPENAI_MODEL,

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]

        )

        answer = (
            response.choices[0].message.content
            or ""
        ).strip()

        if not answer:

            answer = (
                "No pude generar una respuesta "
                "en este momento."
            )

        return {

            "answer":
                answer,

            "financial_context":
                financial_context
        }

    except Exception as exc:

        print("=" * 60)
        print("FINANCIAL CHAT ERROR")
        print("Tipo:", type(exc).__name__)
        print("Error:", str(exc))
        print("=" * 60)

        return {

            "answer":
                (
                    "Ocurrió un problema al procesar "
                    "tu pregunta. Intenta nuevamente."
                ),

            "error":
                str(exc)
        }


# ============================================================
# SIMULACIÓN DE AHORRO
# ============================================================

def simulate_savings(
    amount: float,
    months=None
):

    try:

        amount = float(
            amount
        )

    except (
        ValueError,
        TypeError
    ):

        amount = 0

    if months is None:

        months = [
            1,
            6,
            12,
            24
        ]

    valid_months = []

    for month in months:

        try:

            month = int(
                month
            )

            if month > 0:

                valid_months.append(
                    month
                )

        except (
            ValueError,
            TypeError
        ):

            continue

    valid_months = sorted(
        set(
            valid_months
        )
    )

    projections = {}

    for month in valid_months:

        projections[
            str(month)
        ] = round(
            amount * month,
            2
        )

    return {

        "monthly_amount":
            round(
                amount,
                2
            ),

        "projections":
            projections
    }
