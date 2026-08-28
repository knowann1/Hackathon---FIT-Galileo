from datetime import date, timedelta
from collections import defaultdict

from extensions import db
from models import Expense, Budget


# ============================================================
# RESUMEN FINANCIERO DEL USUARIO
# ============================================================

def summarize_user_finances(user_id: int) -> dict:
    """
    Obtiene y resume la información financiera del usuario.

    Esta función solamente recopila y calcula datos.
    No determina si una situación financiera es buena o mala.
    Esa interpretación corresponde a la IA.
    """

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
        first_day_month -
        timedelta(days=1)
    )

    previous_month_start = (
        previous_month_end.replace(
            day=1
        )
    )

    since_90_days = (
        today -
        timedelta(days=90)
    )


    # ========================================================
    # MES ACTUAL - GASTOS
    # ========================================================

    expenses_month = Expense.query.filter(

        Expense.user_id == user_id,

        Expense.expense_date >= first_day_month,

        Expense.expense_date <= today,

        Expense.transaction_type == 'expense'

    ).all()


    # ========================================================
    # MES ACTUAL - INGRESOS
    # ========================================================

    incomes_month = Expense.query.filter(

        Expense.user_id == user_id,

        Expense.expense_date >= first_day_month,

        Expense.expense_date <= today,

        Expense.transaction_type == 'income'

    ).all()


    # ========================================================
    # MES ANTERIOR - GASTOS
    # ========================================================

    expenses_previous = Expense.query.filter(

        Expense.user_id == user_id,

        Expense.expense_date >= previous_month_start,

        Expense.expense_date <= previous_month_end,

        Expense.transaction_type == 'expense'

    ).all()


    # ========================================================
    # MES ANTERIOR - INGRESOS
    # ========================================================

    incomes_previous = Expense.query.filter(

        Expense.user_id == user_id,

        Expense.expense_date >= previous_month_start,

        Expense.expense_date <= previous_month_end,

        Expense.transaction_type == 'income'

    ).all()


    # ========================================================
    # TOTALES
    # ========================================================

    total_expenses_month = sum(

        float(
            expense.amount or 0
        )

        for expense in expenses_month

    )


    total_income_month = sum(

        float(
            income.amount or 0
        )

        for income in incomes_month

    )


    total_expenses_previous = sum(

        float(
            expense.amount or 0
        )

        for expense in expenses_previous

    )


    total_income_previous = sum(

        float(
            income.amount or 0
        )

        for income in incomes_previous

    )


    # ========================================================
    # BALANCES
    # ========================================================

    balance_month = (
        total_income_month -
        total_expenses_month
    )


    balance_previous = (
        total_income_previous -
        total_expenses_previous
    )


    # ========================================================
    # GASTOS POR CATEGORÍA
    # ========================================================

    expense_by_category = defaultdict(float)


    for expense in expenses_month:

        category = (
            expense.category
            or 'Otros'
        )

        expense_by_category[
            category
        ] += float(
            expense.amount or 0
        )


    # ========================================================
    # CATEGORÍAS MES ANTERIOR
    # ========================================================

    previous_expense_by_category = defaultdict(float)


    for expense in expenses_previous:

        category = (
            expense.category
            or 'Otros'
        )

        previous_expense_by_category[
            category
        ] += float(
            expense.amount or 0
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

        category = budget.category

        limit = float(
            budget.amount or 0
        )

        spent = float(
            expense_by_category.get(
                category,
                0
            )
        )


        remaining = (
            limit -
            spent
        )


        percentage = None


        if limit > 0:

            percentage = round(

                (
                    spent /
                    limit
                ) * 100,

                2
            )


        budget_usage[category] = {

            'limit': round(
                limit,
                2
            ),

            'spent': round(
                spent,
                2
            ),

            'remaining': round(
                remaining,
                2
            ),

            'percentage_used': percentage
        }


    # ========================================================
    # CAMBIO DE GASTOS
    # ========================================================

    expense_growth_pct = None


    if total_expenses_previous > 0:

        expense_growth_pct = round(

            (
                (
                    total_expenses_month -
                    total_expenses_previous
                )
                /
                total_expenses_previous
            )
            * 100,

            2
        )


    # ========================================================
    # CAMBIO DE INGRESOS
    # ========================================================

    income_growth_pct = None


    if total_income_previous > 0:

        income_growth_pct = round(

            (
                (
                    total_income_month -
                    total_income_previous
                )
                /
                total_income_previous
            )
            * 100,

            2
        )


    # ========================================================
    # TRANSACCIONES ÚLTIMOS 90 DÍAS
    # ========================================================

    recent_transactions = Expense.query.filter(

        Expense.user_id == user_id,

        Expense.expense_date >= since_90_days

    ).order_by(

        Expense.expense_date.desc(),

        Expense.id.desc()

    ).all()


    recent_data = []


    for transaction in recent_transactions:

        recent_data.append({

            'id': transaction.id,

            'date': (

                transaction.expense_date.isoformat()

                if transaction.expense_date

                else None
            ),

            'amount': round(

                float(
                    transaction.amount or 0
                ),

                2
            ),

            'currency': (
                transaction.currency
                or 'GTQ'
            ),

            'category': (

                transaction.category
                or 'Otros'
            ),

            'merchant': (

                transaction.merchant
                or None
            ),

            'description': (

                transaction.description
                or None
            ),

            'payment_method': (

                transaction.payment_method
                or None
            ),

            'transaction_type': (

                transaction.transaction_type
                or 'expense'
            )
        })


    # ========================================================
    # COMERCIOS FRECUENTES
    # ========================================================

    merchant_counts = defaultdict(int)


    for transaction in recent_transactions:

        if (

            transaction.transaction_type
            == 'expense'

            and transaction.merchant

        ):

            merchant_counts[
                transaction.merchant
            ] += 1


    recurring_merchants = [

        {
            'merchant': merchant,

            'transactions': count

        }

        for merchant, count
        in merchant_counts.items()

        if count >= 3

    ]


    # ========================================================
    # PORCENTAJE DE AHORRO
    # ========================================================

    savings_rate = None


    if total_income_month > 0:

        savings_rate = round(

            (
                balance_month /
                total_income_month
            )
            * 100,

            2
        )


    # ========================================================
    # CATEGORÍA PRINCIPAL
    # ========================================================

    top_category = None


    if expense_by_category:

        top_category = max(

            expense_by_category.items(),

            key=lambda item: item[1]

        )


    top_category_data = None


    if top_category:

        top_category_data = {

            'category': top_category[0],

            'amount': round(
                top_category[1],
                2
            )
        }


    # ========================================================
    # RESUMEN
    # ========================================================

    summary = {

        # ----------------------------------------------------
        # Periodos
        # ----------------------------------------------------

        'period': {

            'current_month':
                first_day_month.strftime(
                    '%Y-%m'
                ),

            'previous_month':
                previous_month_start.strftime(
                    '%Y-%m'
                ),

            'analyzed_last_days':
                90
        },


        # ----------------------------------------------------
        # Mes actual
        # ----------------------------------------------------

        'current_month': {

            'expenses':
                round(
                    total_expenses_month,
                    2
                ),

            'income':
                round(
                    total_income_month,
                    2
                ),

            'balance':
                round(
                    balance_month,
                    2
                ),

            'savings_rate':
                savings_rate
        },


        # ----------------------------------------------------
        # Mes anterior
        # ----------------------------------------------------

        'previous_month': {

            'expenses':
                round(
                    total_expenses_previous,
                    2
                ),

            'income':
                round(
                    total_income_previous,
                    2
                ),

            'balance':
                round(
                    balance_previous,
                    2
                )
        },


        # ----------------------------------------------------
        # Cambios
        # ----------------------------------------------------

        'changes': {

            'expense_percentage':
                expense_growth_pct,

            'income_percentage':
                income_growth_pct
        },


        # ----------------------------------------------------
        # Categorías
        # ----------------------------------------------------

        'expense_by_category': {

            category: round(
                amount,
                2
            )

            for category, amount
            in expense_by_category.items()

        },


        'previous_expense_by_category': {

            category: round(
                amount,
                2
            )

            for category, amount
            in previous_expense_by_category.items()

        },


        'top_expense_category':
            top_category_data,


        # ----------------------------------------------------
        # Presupuestos
        # ----------------------------------------------------

        'budgets':
            budget_usage,


        # ----------------------------------------------------
        # Comercios recurrentes
        # ----------------------------------------------------

        'recurring_merchants':
            recurring_merchants,


        # ----------------------------------------------------
        # Transacciones recientes
        # ----------------------------------------------------

        'recent_transactions':
            recent_data,


        # ----------------------------------------------------
        # Fecha de actualización
        # ----------------------------------------------------

        'as_of':
            today.isoformat(),


        # ====================================================
        # COMPATIBILIDAD CON EL DASHBOARD ANTIGUO
        # ====================================================

        'monthly_expenses':
            round(
                total_expenses_month,
                2
            ),

        'monthly_incomes':
            round(
                total_income_month,
                2
            ),

        'previous_month_expenses':
            round(
                total_expenses_previous,
                2
            )
    }


    return summary
