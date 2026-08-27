from extensions import db
from models import Expense, Budget
from datetime import date, datetime, timedelta
from collections import defaultdict


def summarize_user_finances(user_id: int) -> dict:
    """
    Query DB and compute a numeric summary for the user.
    Returns a dict with totals and breakdowns that can be sent to the AI for interpretation.
    """
    today = date.today()
    first_day_month = date(today.year, today.month, 1)
    last_month = (first_day_month - timedelta(days=1)).replace(day=1)

    # Total expenses this month (transaction_type == 'expense')
    expenses_month = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= first_day_month,
        Expense.transaction_type == 'expense'
    ).all()
    total_month = sum(e.amount or 0.0 for e in expenses_month)

    # Total incomes this month (transaction_type == 'income')
    incomes_month = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= first_day_month,
        Expense.transaction_type == 'income'
    ).all()
    total_incomes_month = sum(i.amount or 0.0 for i in incomes_month)

    # Total expenses previous month
    prev_start = (first_day_month - timedelta(days=1)).replace(day=1)
    prev_end = first_day_month - timedelta(days=1)
    expenses_prev = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= prev_start,
        Expense.expense_date <= prev_end,
        Expense.transaction_type == 'expense'
    ).all()
    total_prev = sum(e.amount or 0.0 for e in expenses_prev)

    # Total incomes previous month
    incomes_prev = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= prev_start,
        Expense.expense_date <= prev_end,
        Expense.transaction_type == 'income'
    ).all()
    total_incomes_prev = sum(i.amount or 0.0 for i in incomes_prev)

    expense_by_category = defaultdict(float)
    for e in expenses_month:
        expense_by_category[e.category or 'Otros'] += (e.amount or 0.0)

    # Budgets
    budgets = Budget.query.filter_by(user_id=user_id, month=today.month, year=today.year).all()
    budget_map = {b.category: b.amount for b in budgets}

    # Calculate percentage used per budget
    budget_usage = {}
    for cat, limit in budget_map.items():
        spent = expense_by_category.get(cat, 0.0)
        budget_usage[cat] = {'limit': limit, 'spent': spent, 'percent': round((spent/limit)*100,2) if limit>0 else None}

    expense_growth_pct = None
    if total_prev and total_prev > 0:
        expense_growth_pct = round(((total_month - total_prev) / total_prev) * 100, 2)

    # income growth pct
    income_growth_pct = None
    if total_incomes_prev and total_incomes_prev > 0:
        income_growth_pct = round(((total_incomes_month - total_incomes_prev) / total_incomes_prev) * 100, 2)

    # Detect recurring merchants (simple heuristic: merchant appears 3+ times in last 90 days)
    since = today - timedelta(days=90)
    recent = Expense.query.filter(Expense.user_id==user_id, Expense.expense_date >= since).all()
    merchant_counts = defaultdict(int)
    for e in recent:
        if e.merchant:
            merchant_counts[e.merchant] += 1
    recurring = [m for m, c in merchant_counts.items() if c >= 3]

    balance = round((total_incomes_month or 0.0) - (total_month or 0.0), 2)

    summary = {
        'monthly_expenses': round(total_month, 2),
        'previous_month_expenses': round(total_prev, 2),
        'monthly_incomes': round(total_incomes_month, 2),
        'previous_month_incomes': round(total_incomes_prev, 2),
        'expense_growth_percentage': expense_growth_pct,
        'income_growth_percentage': income_growth_pct,
        'expense_by_category': dict(expense_by_category),
        'budget_usage': budget_usage,
        'recurring_merchants': recurring,
        'balance': balance,
        'as_of': today.isoformat()
    }
    return summary


def detect_insights(user_id: int) -> list:
    """
    Apply rule-based detections (increase >20%, budget exceeded, recurring, trends).
    Returns a list of insight dicts.
    """
    insights = []
    summary = summarize_user_finances(user_id)
    # Increase of category: compare top categories month vs previous month (simplified)
    if summary.get('expense_growth_percentage') and summary['expense_growth_percentage'] > 20:
        insights.append({
            'type': 'warning',
            'title': 'Tus gastos aumentaron',
            'description': f"Tus gastos aumentaron {summary['expense_growth_percentage']}% respecto al mes anterior.",
            'severity': 'high'
        })
    # Low or negative balance
    if 'balance' in summary and summary['balance'] < 0:
        insights.append({
            'type': 'alert',
            'title': 'Balance negativo',
            'description': f"Tus ingresos (Q{summary.get('monthly_incomes',0)}) son menores que tus gastos (Q{summary.get('monthly_expenses',0)}). Resultado: Q{summary['balance']}.",
            'severity': 'high',
            'recommendation': 'Revisa gastos o aumenta ingresos para equilibrar tus finanzas.'
        })
    # Budget exceeded
    for cat, usage in summary.get('budget_usage', {}).items():
        if usage.get('percent') and usage['percent'] > 100:
            insights.append({
                'type': 'alert',
                'title': f'Presupuesto excedido: {cat}',
                'description': f"Has gastado Q{usage['spent']} de Q{usage['limit']} asignados para {cat}.",
                'severity': 'medium'
            })
    # Recurring
    if summary.get('recurring_merchants'):
        insights.append({
            'type': 'info',
            'title': 'Gastos recurrentes detectados',
            'description': f"Se detectaron pagos repetidos en: {', '.join(summary['recurring_merchants'])}.",
            'severity': 'low'
        })
    return insights
