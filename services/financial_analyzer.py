from extensions import db
from models import Expense, Budget
from datetime import date, timedelta
from collections import defaultdict


# ============================================================
# CONVERSIÓN SEGURA
# ============================================================

def _safe_float(value):

    try:
        return float(value or 0)

    except (
        ValueError,
        TypeError
    ):

        return 0.0


# ============================================================
# RESUMEN FINANCIERO
# ============================================================

def summarize_user_finances(
    user_id: int
) -> dict:

    today = date.today()

    # ========================================================
    # FECHAS
    # ========================================================

    first_day_month = date(
        today.year,
        today.month,
        1
    )

    previous_month_end = (
        first_day_month
        - timedelta(days=1)
    )

    previous_month_start = (
        previous_month_end.replace(
            day=1
        )
    )

    since_90_days = (
        today
        - timedelta(days=90)
    )

    # ========================================================
    # TRANSACCIONES MES ACTUAL
    # ========================================================

    expenses_month = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= first_day_month,
        Expense.expense_date <= today,
        Expense.transaction_type == "expense"
    ).all()

    incomes_month = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= first_day_month,
        Expense.expense_date <= today,
        Expense.transaction_type == "income"
    ).all()

    # ========================================================
    # MES ANTERIOR
    # ========================================================

    expenses_previous = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= previous_month_start,
        Expense.expense_date <= previous_month_end,
        Expense.transaction_type == "expense"
    ).all()

    incomes_previous = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= previous_month_start,
        Expense.expense_date <= previous_month_end,
        Expense.transaction_type == "income"
    ).all()

    # ========================================================
    # TOTALES
    # ========================================================

    total_month_expenses = sum(
        _safe_float(e.amount)
        for e in expenses_month
    )

    total_month_income = sum(
        _safe_float(e.amount)
        for e in incomes_month
    )

    total_previous_expenses = sum(
        _safe_float(e.amount)
        for e in expenses_previous
    )

    total_previous_income = sum(
        _safe_float(e.amount)
        for e in incomes_previous
    )

    # ========================================================
    # BALANCES
    # ========================================================

    current_balance = (
        total_month_income
        - total_month_expenses
    )

    previous_balance = (
        total_previous_income
        - total_previous_expenses
    )

    # ========================================================
    # CATEGORÍAS
    # ========================================================

    expense_by_category = defaultdict(float)

    for expense in expenses_month:

        category = (
            expense.category
            or "Otros"
        )

        expense_by_category[
            category
        ] += _safe_float(
            expense.amount
        )

    previous_expense_by_category = defaultdict(float)

    for expense in expenses_previous:

        category = (
            expense.category
            or "Otros"
        )

        previous_expense_by_category[
            category
        ] += _safe_float(
            expense.amount
        )

    # ========================================================
    # PRESUPUESTOS
    # ========================================================

    budgets = Budget.query.filter_by(
        user_id=user_id,
        month=today.month,
        year=today.year
    ).all()

    budget_usage = {}

    for budget in budgets:

        category = (
            budget.category
            or "Otros"
        )

        limit = _safe_float(
            budget.amount
        )

        spent = _safe_float(
            expense_by_category.get(
                category,
                0
            )
        )

        remaining = (
            limit - spent
        )

        percentage = (
            (spent / limit) * 100
            if limit > 0
            else None
        )

        budget_usage[
            category
        ] = {

            "limit":
                round(
                    limit,
                    2
                ),

            "spent":
                round(
                    spent,
                    2
                ),

            "remaining":
                round(
                    remaining,
                    2
                ),

            "percentage_used":
                (
                    round(
                        percentage,
                        2
                    )
                    if percentage is not None
                    else None
                )
        }

    # ========================================================
    # CAMBIOS
    # ========================================================

    expense_change_percentage = None

    if total_previous_expenses > 0:

        expense_change_percentage = (
            (
                total_month_expenses
                - total_previous_expenses
            )
            / total_previous_expenses
        ) * 100

    income_change_percentage = None

    if total_previous_income > 0:

        income_change_percentage = (
            (
                total_month_income
                - total_previous_income
            )
            / total_previous_income
        ) * 100

    # ========================================================
    # ÚLTIMOS 90 DÍAS
    # ========================================================

    recent_transactions = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.expense_date >= since_90_days
    ).order_by(
        Expense.expense_date.desc(),
        Expense.id.desc()
    ).all()

    recent_data = []

    for transaction in recent_transactions[:50]:

        recent_data.append({

            "date": (
                transaction.expense_date.isoformat()
                if transaction.expense_date
                else None
            ),

            "amount": round(
                _safe_float(
                    transaction.amount
                ),
                2
            ),

            "currency": (
                transaction.currency
                or "GTQ"
            ),

            "transaction_type": (
                transaction.transaction_type
                or "expense"
            ),

            "category": (
                transaction.category
                or "Otros"
            ),

            "merchant": (
                transaction.merchant
                or None
            ),

            "description": (
                transaction.description
                or None
            ),

            "payment_method": (
                transaction.payment_method
                or None
            )
        })

    # ========================================================
    # COMERCIOS
    # ========================================================

    merchant_totals = defaultdict(float)
    merchant_counts = defaultdict(int)

    for transaction in recent_transactions:

        if (
            transaction.transaction_type
            == "expense"
            and transaction.merchant
        ):

            merchant = (
                transaction.merchant
            )

            merchant_totals[
                merchant
            ] += _safe_float(
                transaction.amount
            )

            merchant_counts[
                merchant
            ] += 1

    recurring_merchants = []

    for merchant in merchant_totals:

        if merchant_counts[
            merchant
        ] >= 2:

            recurring_merchants.append({

                "merchant":
                    merchant,

                "transactions":
                    merchant_counts[
                        merchant
                    ],

                "total":
                    round(
                        merchant_totals[
                            merchant
                        ],
                        2
                    )
            })

    recurring_merchants.sort(
        key=lambda item: item["total"],
        reverse=True
    )

    # ========================================================
    # PORCENTAJES DE CATEGORÍA
    # ========================================================

    category_percentages = {}

    for category, amount in sorted(
        expense_by_category.items(),
        key=lambda item: item[1],
        reverse=True
    ):

        percentage = (
            amount
            / total_month_expenses
            * 100
            if total_month_expenses > 0
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
    # CATEGORÍA PRINCIPAL
    # ========================================================

    top_category = None

    if category_percentages:

        category_name = next(
            iter(
                category_percentages
            )
        )

        top_category = {

            "name":
                category_name,

            "amount":
                category_percentages[
                    category_name
                ]["amount"],

            "percentage":
                category_percentages[
                    category_name
                ]["percentage"]
        }

    # ========================================================
    # TODAS LAS TRANSACCIONES PARA ESTADÍSTICAS
    # ========================================================

    all_transactions = Expense.query.filter_by(
        user_id=user_id
    ).all()

    total_income = 0
    total_expenses = 0

    income_transactions = []
    expense_transactions = []

    income_by_category = defaultdict(float)
    all_expenses_by_category = defaultdict(float)
    all_merchants = defaultdict(float)
    payment_methods = defaultdict(float)

    for transaction in all_transactions:

        amount = _safe_float(
            transaction.amount
        )

        transaction_type = (
            transaction.transaction_type
            or "expense"
        )

        if transaction_type == "income":

            total_income += amount

            income_transactions.append(
                amount
            )

            category = (
                transaction.category
                or "Sin categoría"
            )

            income_by_category[
                category
            ] += amount

        else:

            total_expenses += amount

            expense_transactions.append(
                amount
            )

            category = (
                transaction.category
                or "Otros"
            )

            all_expenses_by_category[
                category
            ] += amount

            payment_method = (
                transaction.payment_method
                or "No especificado"
            )

            payment_methods[
                payment_method
            ] += amount

            if transaction.merchant:

                all_merchants[
                    transaction.merchant
                ] += amount

    # ========================================================
    # BALANCE GENERAL
    # ========================================================

    total_balance = (
        total_income
        - total_expenses
    )

    # ========================================================
    # RATIO DE GASTO Y AHORRO
    # ========================================================

    spending_ratio = None
    savings_ratio = None

    if total_income > 0:

        spending_ratio = (
            total_expenses
            / total_income
        ) * 100

        savings_ratio = (
            total_balance
            / total_income
        ) * 100

    # ========================================================
    # PROMEDIOS
    # ========================================================

    average_expense = (
        sum(expense_transactions)
        / len(expense_transactions)
        if expense_transactions
        else 0
    )

    average_income = (
        sum(income_transactions)
        / len(income_transactions)
        if income_transactions
        else 0
    )

    # ========================================================
    # MAYOR GASTO
    # ========================================================

    largest_expense = (
        max(expense_transactions)
        if expense_transactions
        else 0
    )

    # ========================================================
    # TOP COMERCIOS
    # ========================================================

    top_merchants = sorted(
        all_merchants.items(),
        key=lambda item: item[1],
        reverse=True
    )[:10]

    # ========================================================
    # RESULTADO
    # ========================================================

    summary = {

        "period": {

            "current_month":
                first_day_month.strftime(
                    "%Y-%m"
                ),

            "previous_month":
                previous_month_start.strftime(
                    "%Y-%m"
                ),

            "as_of":
                today.isoformat(),

            "analyzed_last_days":
                90
        },

        "total_transactions":
            len(all_transactions),

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
                total_balance,
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

        "current_month": {

            "income":
                round(
                    total_month_income,
                    2
                ),

            "expenses":
                round(
                    total_month_expenses,
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
                    total_previous_income,
                    2
                ),

            "expenses":
                round(
                    total_previous_expenses,
                    2
                ),

            "balance":
                round(
                    previous_balance,
                    2
                )
        },

        "changes": {

            "expense_percentage":
                (
                    round(
                        expense_change_percentage,
                        2
                    )
                    if expense_change_percentage
                    is not None
                    else None
                ),

            "income_percentage":
                (
                    round(
                        income_change_percentage,
                        2
                    )
                    if income_change_percentage
                    is not None
                    else None
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

        "expense_by_category": {
            category: round(
                amount,
                2
            )
            for category, amount
            in sorted(
                expense_by_category.items(),
                key=lambda item: item[1],
                reverse=True
            )
        },

        "previous_expense_by_category": {
            category: round(
                amount,
                2
            )
            for category, amount
            in previous_expense_by_category.items()
        },

        "category_percentages":
            category_percentages,

        "income_by_category": {
            category: round(
                amount,
                2
            )
            for category, amount
            in income_by_category.items()
        },

        "top_merchants": {
            merchant: round(
                amount,
                2
            )
            for merchant, amount
            in top_merchants
        },

        "recurring_merchants":
            recurring_merchants,

        "payment_methods": {
            method: round(
                amount,
                2
            )
            for method, amount
            in sorted(
                payment_methods.items(),
                key=lambda item: item[1],
                reverse=True
            )
        },

        "budgets":
            budget_usage,

        "recent_transactions":
            recent_data
    }

    return summary


# ============================================================
# INSIGHTS BASADOS EN REGLAS
# ============================================================

def detect_insights(
    user_id: int
) -> list:

    summary = summarize_user_finances(
        user_id
    )

    insights = []

    current = summary[
        "current_month"
    ]

    income = current[
        "income"
    ]

    expenses = current[
        "expenses"
    ]

    balance = current[
        "balance"
    ]

    # ========================================================
    # BALANCE NEGATIVO
    # ========================================================

    if income > 0 and balance < 0:

        insights.append({

            "type":
                "alert",

            "title":
                "Tus gastos superan tus ingresos",

            "description":
                (
                    f"Este mes tienes Q{expenses:.2f} "
                    f"en gastos frente a Q{income:.2f} "
                    "en ingresos."
                ),

            "severity":
                "high"
        })

    # ========================================================
    # SIN INGRESOS
    # ========================================================

    elif income == 0 and expenses > 0:

        insights.append({

            "type":
                "warning",

            "title":
                "No hay ingresos registrados este mes",

            "description":
                (
                    f"Hay Q{expenses:.2f} "
                    "en gastos registrados, pero "
                    "no aparecen ingresos para "
                    "el mismo período."
                ),

            "severity":
                "medium"
        })

    # ========================================================
    # AHORRO POSITIVO
    # ========================================================

    elif balance > 0:

        savings_ratio = summary.get(
            "savings_ratio"
        )

        if savings_ratio is not None:

            insights.append({

                "type":
                    "saving",

                "title":
                    "Tienes capacidad de ahorro",

                "description":
                    (
                        f"Tu balance general es de "
                        f"Q{summary['balance']:.2f} y "
                        f"tu tasa de ahorro calculada "
                        f"es de {savings_ratio:.1f}%."
                    ),

                "severity":
                    "low"
            })

    # ========================================================
    # AUMENTO DE GASTOS
    # ========================================================

    expense_change = summary.get(
        "expense_change_percentage"
    )

    if (
        expense_change is not None
        and expense_change > 20
    ):

        insights.append({

            "type":
                "warning",

            "title":
                "Tus gastos aumentaron",

            "description":
                (
                    f"Los gastos de este mes "
                    f"aumentaron {expense_change:.1f}% "
                    "respecto al mes anterior."
                ),

            "severity":
                "medium"
        })

    # ========================================================
    # PRESUPUESTOS
    # ========================================================

    for category, budget in (
        summary.get(
            "budgets",
            {}
        ).items()
    ):

        percentage = budget.get(
            "percentage_used"
        )

        if (
            percentage is not None
            and percentage >= 100
        ):

            insights.append({

                "type":
                    "alert",

                "title":
                    f"Presupuesto superado: {category}",

                "description":
                    (
                        f"Has utilizado el "
                        f"{percentage:.1f}% del presupuesto "
                        f"de {category}."
                    ),

                "severity":
                    "high"
            })

        elif (
            percentage is not None
            and percentage >= 80
        ):

            insights.append({

                "type":
                    "warning",

                "title":
                    f"Presupuesto cerca del límite: {category}",

                "description":
                    (
                        f"Has utilizado el "
                        f"{percentage:.1f}% del presupuesto "
                        f"de {category}."
                    ),

                "severity":
                    "medium"
            })

    return insights
