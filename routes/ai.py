
import os
import json

from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    flash
)
from flask_babel import gettext as _

from flask_login import login_required, current_user

from services.ai_service import (
    parse_expense_text,
    analyze_finances_with_ai,
    simulate_savings,
    ask_financial_ai
)

from services.financial_analyzer import (
    summarize_user_finances,
    detect_insights
)

from extensions import db

from models import (
    Expense,
    FinancialInsight
)

from datetime import datetime


# ============================================================
# BLUEPRINT
# ============================================================

ai_bp = Blueprint(
    "ai",
    __name__,
    template_folder="../templates"
)


# ============================================================
# CHATBOT
# ============================================================

@ai_bp.route(
    "/chat",
    methods=["GET"]
)
@login_required
def chat_page():

    return render_template(
        "chatbot.html"
    )


@ai_bp.route(
    "/chat-message",
    methods=["POST"]
)
@login_required
def chat_message():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    question = (
        data.get("message")
        or ""
    ).strip()

    if not question:

        return jsonify({
            "reply":
                "Escribe una pregunta para NexoAI."
        }), 400

    try:

        # ====================================================
        # HISTORIAL
        # ====================================================

        conversation_history = (
            data.get("history")
            or data.get(
                "conversation_history"
            )
            or []
        )

        if not isinstance(
            conversation_history,
            list
        ):

            conversation_history = []

        # ====================================================
        # IA
        # ====================================================

        result = ask_financial_ai(

            user_id=current_user.id,

            question=question,

            conversation_history=(
                conversation_history
            )

        )

        if not result:

            return jsonify({
                "reply":
                    (
                        "No pude procesar tu pregunta "
                        "en este momento."
                    )
            }), 500

        answer = result.get(
            "answer"
        )

        if not answer:

            answer = (
                "No pude generar una respuesta "
                "en este momento."
            )

        return jsonify({

            "reply":
                answer

        })

    except Exception as exc:

        print("=" * 60)
        print("CHAT AI ERROR")
        print(
            "Tipo:",
            type(exc).__name__
        )
        print(
            "Error:",
            str(exc)
        )
        print("=" * 60)

        return jsonify({

            "reply":
                (
                    "Ocurrió un problema al procesar "
                    "tu pregunta. Intenta nuevamente."
                )

        }), 500


# ============================================================
# PARSEAR TEXTO
# ============================================================

@ai_bp.route(
    "/parse-text",
    methods=["POST"]
)
@login_required
def parse_text_endpoint():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    text = (
        data.get("text")
        or ""
    ).strip()

    if not text:

        return jsonify({
            "error":
                "No text provided"
        }), 400

    result = parse_expense_text(
        text
    )

    return jsonify({

        "proposal":
            result

    })


# ============================================================
# REVISAR PROPUESTA
# ============================================================

@ai_bp.route(
    "/parse-text/review",
    methods=["POST"]
)
@login_required
def parse_text_review():

    text = None

    if request.form:

        text = request.form.get(
            "text"
        )

    if not text:

        json_data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        text = json_data.get(
            "text"
        )

    if not text:

        flash(
            _("Texto no proporcionado"),
            "danger"
        )

        return redirect(
            url_for(
                "dashboard.index"
            )
        )

    proposal = parse_expense_text(
        text
    )

    return render_template(

        "ai_review.html",

        proposal=proposal

    )


# ============================================================
# CONFIRMAR EXPENSE
# ============================================================

@ai_bp.route(
    "/confirm-expense",
    methods=["POST"]
)
@login_required
def confirm_expense():

    if request.form:

        data = request.form

    else:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

    # ========================================================
    # MONTO
    # ========================================================

    try:

        raw_amount = data.get(
            "amount"
        )

        if raw_amount in (
            None,
            "",
            "null"
        ):

            amount = None

        else:

            amount = float(
                raw_amount
            )

    except (
        ValueError,
        TypeError
    ):

        flash(
            _("Monto inválido"),
            "danger"
        )

        return redirect(
            url_for(
                "dashboard.index"
            )
        )

    # ========================================================
    # DATOS
    # ========================================================

    currency = (
        data.get("currency")
        or "GTQ"
    )

    merchant = data.get(
        "merchant"
    )

    description = data.get(
        "description"
    )

    category = data.get(
        "category"
    )

    payment_method = data.get(
        "payment_method"
    )

    # ========================================================
    # CONFIANZA IA
    # ========================================================

    ai_confidence = None

    try:

        raw_confidence = data.get(
            "ai_confidence"
        )

        if raw_confidence not in (
            None,
            ""
        ):

            ai_confidence = float(
                raw_confidence
            )

    except (
        ValueError,
        TypeError
    ):

        ai_confidence = None

    # ========================================================
    # FECHA
    # ========================================================

    expense_date = None

    date_str = data.get(
        "expense_date"
    )

    if date_str:

        try:

            expense_date = (
                datetime
                .fromisoformat(
                    str(date_str)
                )
                .date()
            )

        except (
            ValueError,
            TypeError
        ):

            try:

                expense_date = (
                    datetime
                    .strptime(
                        str(date_str),
                        "%Y-%m-%d"
                    )
                    .date()
                )

            except (
                ValueError,
                TypeError
            ):

                expense_date = None

    # ========================================================
    # VALIDAR MONTO
    # ========================================================

    if amount is None:

        flash(
            _("Monto requerido para guardar"),
            "danger"
        )

        return redirect(
            url_for(
                "dashboard.index"
            )
        )

    if amount <= 0:

        flash(
            _("El monto debe ser mayor que cero"),
            "danger"
        )

        return redirect(
            url_for(
                "dashboard.index"
            )
        )

    # ========================================================
    # TIPO
    # ========================================================

    transaction_type = (
        data.get(
            "transaction_type"
        )
        or "expense"
    )

    if transaction_type not in (
        "expense",
        "income"
    ):

        transaction_type = "expense"

    # ========================================================
    # CREAR TRANSACCIÓN
    # ========================================================

    exp = Expense(

        user_id=current_user.id,

        amount=amount,

        currency=currency,

        description=description,

        merchant=merchant,

        category=category,

        payment_method=payment_method,

        expense_date=expense_date,

        ai_generated=True,

        ai_confidence=ai_confidence,

        transaction_type=transaction_type

    )

    try:

        db.session.add(
            exp
        )

        db.session.commit()

    except Exception as exc:

        db.session.rollback()

        print(
            "Error saving AI transaction:",
            type(exc).__name__,
            str(exc)
        )

        flash(
            _("No se pudo guardar la transacción"),
            "danger"
        )

        return redirect(
            url_for(
                "dashboard.index"
            )
        )

    # ========================================================
    # MENSAJE
    # ========================================================

    if transaction_type == "income":

        flash(
            _("Ingreso guardado desde propuesta de IA"),
            "success"
        )

    else:

        flash(
            _("Gasto guardado desde propuesta de IA"),
            "success"
        )

    return redirect(
        url_for(
            "expenses.list_expenses"
        )
    )


# ============================================================
# ANÁLISIS FINANCIERO
# ============================================================

@ai_bp.route(
    "/analyze-finances",
    methods=["POST"]
)
@login_required
def analyze_finances():

    try:

        # ====================================================
        # 1. RESUMEN FINANCIERO
        # ====================================================

        summary = summarize_user_finances(
            current_user.id
        )

        # ====================================================
        # 2. INSIGHTS BASADOS EN REGLAS
        # ====================================================

        try:

            rule_insights = detect_insights(
                current_user.id
            )

        except Exception as exc:

            print(
                "Rule insights error:",
                exc
            )

            rule_insights = []

        # ====================================================
        # 3. GUARDAR INSIGHTS
        # ====================================================

        for ins in rule_insights:

            try:

                if not isinstance(
                    ins,
                    dict
                ):
                    continue

                fi = FinancialInsight(

                    user_id=current_user.id,

                    insight_type=ins.get(
                        "type"
                    ),

                    title=ins.get(
                        "title"
                    ),

                    description=ins.get(
                        "description"
                    ),

                    severity=ins.get(
                        "severity",
                        "low"
                    )

                )

                db.session.add(
                    fi
                )

            except Exception as exc:

                print(
                    "Error creating financial insight:",
                    exc
                )

        try:

            db.session.commit()

        except Exception as exc:

            print(
                "Error committing insights:",
                exc
            )

            db.session.rollback()

        # ====================================================
        # 4. ANÁLISIS CON IA
        # ====================================================

        ai_result = analyze_finances_with_ai(

            current_user.id

        )

        if not isinstance(
            ai_result,
            dict
        ):

            ai_result = {
                "insights": []
            }

        ai_insights = ai_result.get(
            "insights",
            []
        )

        if not isinstance(
            ai_insights,
            list
        ):

            ai_insights = []

        # ====================================================
        # 5. UNIFICAR INSIGHTS
        # ====================================================

        insights = []

        # ----------------------------------------------------
        # INSIGHTS DE IA
        # ----------------------------------------------------

        for insight in ai_insights:

            if not isinstance(
                insight,
                dict
            ):

                continue

            insights.append({

                "type":
                    insight.get(
                        "type",
                        "info"
                    ),

                "title":
                    insight.get(
                        "title",
                        "Recomendación financiera"
                    ),

                "description":
                    insight.get(
                        "description",
                        ""
                    ),

                "recommendation":
                    insight.get(
                        "recommendation",
                        ""
                    ),

                "priority":
                    insight.get(
                        "priority",
                        999
                    )

            })

        # ----------------------------------------------------
        # INSIGHTS DE REGLAS
        # ----------------------------------------------------

        for insight in rule_insights:

            if not isinstance(
                insight,
                dict
            ):

                continue

            insights.append({

                "type":
                    insight.get(
                        "severity",
                        "info"
                    ),

                "title":
                    insight.get(
                        "title",
                        "Insight financiero"
                    ),

                "description":
                    insight.get(
                        "description",
                        ""
                    ),

                "recommendation":
                    insight.get(
                        "recommendation",
                        ""
                    ),

                "priority":
                    1000

            })

        # ====================================================
        # 6. ORDENAR
        # ====================================================

        try:

            insights.sort(
                key=lambda x: float(
                    x.get(
                        "priority",
                        999
                    )
                )
            )

        except (
            ValueError,
            TypeError
        ):

            pass

        # ====================================================
        # 7. RESPUESTA JSON
        # ====================================================

        return jsonify({

            "success":
                True,

            "summary":
                summary,

            "insights":
                insights,

            "rule_insights":
                rule_insights,

            "ai_insights":
                ai_insights

        }), 200

    except Exception as exc:

        # ====================================================
        # ERROR
        # ====================================================

        print("=" * 60)

        print(
            "ANALYZE FINANCES ERROR"
        )

        print(
            "Tipo:",
            type(exc).__name__
        )

        print(
            "Error:",
            str(exc)
        )

        print("=" * 60)

        return jsonify({

            "success":
                False,

            "error":
                (
                    f"{type(exc).__name__}: "
                    f"{str(exc)}"
                ),

            "insights":
                []

        }), 500


# ============================================================
# SIMULACIÓN
# ============================================================

@ai_bp.route(
    "/simulation",
    methods=["POST"]
)
@login_required
def simulation():

    data = (
        request.get_json(
            silent=True
        )
        or {}
    )

    amount = data.get(
        "amount"
    )

    months = data.get(
        "months",
        [1, 6, 12, 24]
    )

    if amount is None:

        return jsonify({
            "error":
                "amount required"
        }), 400

    try:

        amount = float(
            amount
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify({
            "error":
                "amount must be a number"
        }), 400

    if amount < 0:

        return jsonify({
            "error":
                "amount cannot be negative"
        }), 400

    try:

        sim = simulate_savings(
            amount,
            months
        )

        return jsonify(
            sim
        )

    except Exception as exc:

        print(
            "Simulation error:",
            type(exc).__name__,
            str(exc)
        )

        return jsonify({

            "error":
                (
                    "No se pudo realizar "
                    "la simulación."
                )

        }), 500

