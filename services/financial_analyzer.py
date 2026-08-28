from extensions import db
from models import Expense, Budget
from datetime import date, timedelta
from collections import defaultdict


def summarize_user_finances(user_id: int) -> dict:
    """
    Obtiene y resume los datos financieros del usuario desde la DB.

    Esta función NO decide si algo es bueno, malo o preocupante.
    Solamente recopila información para que la IA la analice.
    """

    today = date.today()

    # ============================================================
    # FECHAS
    # ============================================================

    first_day_month = date(today.year, today.month, 1)

    prev_end = first_day_month - timedelta(days=1)
    prev_start = prev_end.replace(day=1)

    since_90_days = today - timedelta(days=90)

    # ============================================================
    # TRANSACCIONES DEL MES ACTUAL
    # ============================================================

    expenses_month = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= first_day_month,
        Expense.expense_date <= today,
        Expense.transaction_type == 'expense'
    ).all()

    incomes_month = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= first_day_month,
        Expense.expense_date <= today,
        Expense.transaction_type == 'income'
    ).all()

    # ============================================================
    # TRANSACCIONES DEL MES ANTERIOR
    # ============================================================

    expenses_prev = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= prev_start,
        Expense.expense_date <= prev_end,
        Expense.transaction_type == 'expense'
    ).all()

    incomes_prev = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= prev_start,
        Expense.expense_date <= prev_end,
        Expense.transaction_type == 'income'
    ).all()

    # ============================================================
    # TOTALES
    # ============================================================

    total_month = sum(
        float(e.amount or 0)
        for e in expenses_month
    )

    total_incomes_month = sum(
        float(e.amount or 0)
        for e in incomes_month
    )

    total_prev = sum(
        float(e.amount or 0)
        for e in expenses_prev
    )

    total_incomes_prev = sum(
        float(e.amount or 0)
        for e in incomes_prev
    )

    balance = total_incomes_month - total_month

    # ============================================================
    # GASTOS POR CATEGORÍA
    # ============================================================

    expense_by_category = defaultdict(float)

    for expense in expenses_month:
        category = expense.category or "Otros"
        expense_by_category[category] += float(
            expense.amount or 0
        )

    # ============================================================
    # CATEGORÍAS DEL MES ANTERIOR
    # ============================================================

    previous_expense_by_category = defaultdict(float)

    for expense in expenses_prev:
        category = expense.category or "Otros"
        previous_expense_by_category[category] += float(
            expense.amount or 0
        )

    # ============================================================
    # PRESUPUESTOS
    # ============================================================

    budgets = Budget.query.filter_by(
        user_id=user_id,
        month=today.month,
        year=today.year
    ).all()

    budget_usage = {}

    for budget in budgets:

        category = budget.category
        limit = float(budget.amount or 0)

        spent = float(
            expense_by_category.get(category, 0)
        )

        budget_usage[category] = {
            "limit": round(limit, 2),
            "spent": round(spent, 2)
        }

    # ============================================================
    # CRECIMIENTO DE GASTOS
    # ============================================================

    expense_growth_pct = None

    if total_prev > 0:
        expense_growth_pct = round(
            ((total_month - total_prev) / total_prev) * 100,
            2
        )

    # ============================================================
    # CRECIMIENTO DE INGRESOS
    # ============================================================

    income_growth_pct = None

    if total_incomes_prev > 0:
        income_growth_pct = round(
            (
                (total_incomes_month - total_incomes_prev)
                / total_incomes_prev
            ) * 100,
            2
        )

    # ============================================================
    # GASTOS RECIENTES
    # ============================================================

    recent_transactions = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= since_90_days
    ).order_by(
        Expense.expense_date.desc()
    ).all()

    recent_expenses = []

    for transaction in recent_transactions:

        recent_expenses.append({
            "date": (
                transaction.expense_date.isoformat()
                if transaction.expense_date
                else None
            ),
            "amount": round(
                float(transaction.amount or 0),
                2
            ),
            "category": transaction.category or "Otros",
            "merchant": transaction.merchant or None,
            "transaction_type": transaction.transaction_type
        })

    # ============================================================
    # COMERCIOS FRECUENTES
    # ============================================================

    merchant_counts = defaultdict(int)

    for transaction in recent_transactions:

        if (
            transaction.transaction_type == "expense"
            and transaction.merchant
        ):
            merchant_counts[
                transaction.merchant
            ] += 1

    recurring_merchants = [
        {
            "merchant": merchant,
            "transactions": count
        }
        for merchant, count in merchant_counts.items()
        if count >= 3
    ]

    # ============================================================
    # RESUMEN FINAL
    # ============================================================

    summary = {

        "period": {
            "current_month": first_day_month.strftime("%Y-%m"),
            "previous_month": prev_start.strftime("%Y-%m"),
            "analyzed_last_days": 90
        },

        "current_month": {
            "expenses": round(total_month, 2),
            "income": round(total_incomes_month, 2),
            "balance": round(balance, 2)
        },

        "previous_month": {
            "expenses": round(total_prev, 2),
            "income": round(total_incomes_prev, 2),
            "balance": round(
                total_incomes_prev - total_prev,
                2
            )
        },

        "changes": {
            "expense_percentage": expense_growth_pct,
            "income_percentage": income_growth_pct
        },

        "expense_by_category": {
            category: round(amount, 2)
            for category, amount
            in expense_by_category.items()
        },

        "previous_expense_by_category": {
            category: round(amount, 2)
            for category, amount
            in previous_expense_by_category.items()
        },

        "budgets": budget_usage,

        "recurring_merchants": recurring_merchants,

        "recent_transactions": recent_expenses,

        "as_of": today.isoformat()
    }

    return summary
