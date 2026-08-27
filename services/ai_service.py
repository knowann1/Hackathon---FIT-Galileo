
import os
import json
import re
from datetime import datetime, timedelta

from openai import OpenAI

from extensions import db
from models import Expense


# ============================================================
# CONFIGURACIÓN OPENAI
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============================================================
# PARSEAR TEXTO DE GASTO
# ============================================================

def parse_expense_text(text: str) -> dict:

    if not text:
        return {}

    if client:

        try:

            prompt = f"""
Eres un asistente especializado en registrar transacciones
financieras personales.

Analiza el siguiente texto y extrae la información financiera.

TEXTO:
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
- Si no conoces un dato utiliza null.
"""

            response = client.responses.create(
                model=OPENAI_MODEL,
                input=prompt
            )

            output_text = response.output_text.strip()

            start = output_text.find("{")
            end = output_text.rfind("}")

            if start != -1 and end != -1:

                return json.loads(
                    output_text[start:end + 1]
                )

        except Exception as e:

            print(
                "OpenAI parse expense error:",
                type(e).__name__,
                str(e)
            )

    return _expense_fallback(text)


# ============================================================
# FALLBACK
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
                match.group(1).replace(",", ".")
            )

        except Exception:

            amount = None

    lower_text = text.lower()

    category = None
    payment_method = None

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
            "cafe"
        ]
    ):

        category = "Alimentación"

    if "tarjeta" in lower_text:

        payment_method = "Tarjeta"

    elif "efectivo" in lower_text:

        payment_method = "Efectivo"

    return {

        "amount": amount,

        "currency": "GTQ",

        "merchant": None,

        "description": text,

        "category": category,

        "payment_method": payment_method,

        "expense_date": None,

        "transaction_type": "expense",

        "proposal_source": "fallback"

    }


# ============================================================
# OBTENER INFORMACIÓN FINANCIERA DEL USUARIO
# ============================================================

def get_user_financial_context(user_id):

    expenses = (
        Expense.query
        .filter_by(user_id=user_id)
        .order_by(Expense.expense_date.desc())
        .all()
    )

    if not expenses:

        return {
            "total_transactions": 0,
            "message": "El usuario todavía no tiene transacciones registradas."
        }

    today = datetime.utcnow().date()

    current_month = today.month
    current_year = today.year

    previous_month_date = (
        today.replace(day=1)
        - timedelta(days=1)
    )

    previous_month = previous_month_date.month
    previous_year = previous_month_date.year

    total_income = 0
    total_expenses = 0

    current_month_income = 0
    current_month_expenses = 0

    previous_month_income = 0
    previous_month_expenses = 0

    expenses_by_category = {}
    recent_transactions = []

    for expense in expenses:

        amount = float(
            expense.amount or 0
        )

        transaction_type = (
            expense.transaction_type
            or "expense"
        )

        expense_date = expense.expense_date

        # --------------------------------------------
        # INGRESOS
        # --------------------------------------------

        if transaction_type == "income":

            total_income += amount

            if expense_date:

                if (
                    expense_date.month == current_month
                    and expense_date.year == current_year
                ):

                    current_month_income += amount

                elif (
                    expense_date.month == previous_month
                    and expense_date.year == previous_year
                ):

                    previous_month_income += amount

        # --------------------------------------------
        # GASTOS
        # --------------------------------------------

        else:

            total_expenses += amount

            category = (
                expense.category
                or "Sin categoría"
            )

            expenses_by_category[category] = (
                expenses_by_category.get(
                    category,
                    0
                ) + amount
            )

            if expense_date:

                if (
                    expense_date.month == current_month
                    and expense_date.year == current_year
                ):

                    current_month_expenses += amount

                elif (
                    expense_date.month == previous_month
                    and expense_date.year == previous_year
                ):

                    previous_month_expenses += amount

        # --------------------------------------------
        # TRANSACCIONES RECIENTES
        # --------------------------------------------

        if len(recent_transactions) < 20:

            recent_transactions.append({

                "date": (
                    expense_date.isoformat()
                    if expense_date
                    else None
                ),

                "type": transaction_type,

                "amount": amount,

                "currency": expense.currency,

                "merchant": expense.merchant,

                "category": expense.category,

                "description": expense.description,

                "payment_method": expense.payment_method

            })

    # --------------------------------------------
    # BALANCES
    # --------------------------------------------

    balance = (
        total_income
        - total_expenses
    )

    current_balance = (
        current_month_income
        - current_month_expenses
    )

    # --------------------------------------------
    # CATEGORÍAS PRINCIPALES
    # --------------------------------------------

    top_categories = sorted(
        expenses_by_category.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    return {

        "total_transactions": len(expenses),

        "total_income": round(
            total_income,
            2
        ),

        "total_expenses": round(
            total_expenses,
            2
        ),

        "balance": round(
            balance,
            2
        ),

        "current_month": {

            "income": round(
                current_month_income,
                2
            ),

            "expenses": round(
                current_month_expenses,
                2
            ),

            "balance": round(
                current_balance,
                2
            )

        },

        "previous_month": {

            "income": round(
                previous_month_income,
                2
            ),

            "expenses": round(
                previous_month_expenses,
                2
            )

        },

        "expenses_by_category": {

            category: round(
                amount,
                2
            )

            for category, amount
            in top_categories

        },

        "recent_transactions":
            recent_transactions

    }


# ============================================================
# RECOMENDACIONES FINANCIERAS
# ============================================================

def analyze_finances_with_ai(user_id):

    context = get_user_financial_context(
        user_id
    )

    if not client:

        return {

            "insights": [],

            "financial_context": context,

            "error":
                "OPENAI_API_KEY no está configurada."

        }

    try:

        prompt = f"""
Actúa como un administrador financiero personal.

Analiza exclusivamente los datos financieros reales
proporcionados del usuario.

DATOS FINANCIEROS:

{json.dumps(
    context,
    ensure_ascii=False,
    indent=2
)}

Genera recomendaciones financieras PERSONALIZADAS.

Analiza:

1. Nivel de gastos.
2. Categorías donde más dinero gasta.
3. Cambios respecto al mes anterior.
4. Balance entre ingresos y gastos.
5. Posibles oportunidades de ahorro.
6. Comportamientos que debería vigilar.
7. Consejos prácticos para mejorar sus finanzas.

NO inventes datos.

NO asumas información que no aparece.

Si no existe suficiente información para realizar
una recomendación, indícalo claramente.

Devuelve ÚNICAMENTE JSON:

{{
    "insights": [
        {{
            "type": "info",
            "title": "Título",
            "description": "Análisis personalizado",
            "recommendation": "Consejo práctico"
        }}
    ]
}}

Puedes generar entre 3 y 7 recomendaciones.
"""

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt
        )

        output_text = response.output_text.strip()

        start = output_text.find("{")
        end = output_text.rfind("}")

        if start != -1 and end != -1:

            result = json.loads(
                output_text[start:end + 1]
            )

            result["financial_context"] = context

            return result

        return {

            "insights": [],

            "financial_context": context,

            "raw": output_text

        }

    except Exception as e:

        print(
            "Financial AI error:",
            type(e).__name__,
            str(e)
        )

        return {

            "insights": [],

            "financial_context": context,

            "error": str(e)

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
                "El servicio de inteligencia financiera no está configurado."
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

        # --------------------------------------------
        # Limitar historial
        # --------------------------------------------

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

        # --------------------------------------------
        # PROMPT
        # --------------------------------------------

        prompt = f"""
Eres el administrador financiero personal del usuario.

Tu función es ayudar al usuario a comprender y mejorar
sus finanzas utilizando sus datos financieros reales.

DATOS DEL USUARIO:

{json.dumps(
    financial_context,
    ensure_ascii=False,
    indent=2
)}

HISTORIAL RECIENTE DEL CHAT:

{conversation_text}

NUEVA PREGUNTA:

{question}

INSTRUCCIONES:

- Responde en español.
- Sé claro, natural y útil.
- Personaliza la respuesta utilizando los datos financieros.
- Utiliza los datos de PostgreSQL proporcionados.
- No inventes ingresos, gastos, fechas, categorías ni cantidades.
- Si el usuario pregunta sobre una transacción concreta,
  utiliza únicamente las transacciones proporcionadas.
- Si no tienes suficiente información, dilo.
- Puedes calcular porcentajes, diferencias, promedios
  y balances utilizando los datos disponibles.
- Explica los cálculos importantes de manera sencilla.
- Da consejos financieros prácticos y relacionados
  directamente con la situación del usuario.
- Recuerda el contexto de los mensajes anteriores.
- Si el usuario hace una pregunta relacionada con algo
  mencionado anteriormente, utiliza ese contexto.
- Mantén el papel de administrador financiero personal.
- No tomes decisiones por el usuario.
- Presenta recomendaciones, no órdenes.

La respuesta debe ser conversacional y fácil de entender.
"""

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt
        )

        answer = (
            response.output_text.strip()
        )

        return {

            "answer": answer,

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
                "Ocurrió un problema al procesar tu pregunta. "
                "Intenta nuevamente más tarde.",

            "error": str(e)

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

        projections[str(month)] = round(
            amount * month,
            2
        )

    return {

        "monthly_amount":
            float(amount),

        "projections":
            projections

    }


