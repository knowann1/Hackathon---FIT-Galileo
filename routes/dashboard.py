
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

from services.financial_analyzer import summarize_user_finances


dashboard_bp = Blueprint(
    'dashboard',
    __name__,
    template_folder='../templates'
)


@dashboard_bp.route('/dashboard')
@login_required
def index():

    # Obtener el resumen financiero del usuario
    summary = summarize_user_finances(current_user.id)

    # Renderizar el dashboard
    # Las recomendaciones NO se generan aquí.
    # Se generarán mediante IA cuando el usuario pulse
    # "Analizar mis finanzas".
    return render_template(
        'dashboard.html',
        summary=summary
    )


# ============================================================
# ENDPOINT PARA REFRESCAR DATOS (API)
# ============================================================

@dashboard_bp.route('/api/dashboard/summary', methods=['GET'])
@login_required
def get_summary():
    """
    Obtiene el resumen financiero actualizado del usuario.
    
    Usado para refrescar los datos sin recargar toda la página.
    """
    
    summary = summarize_user_finances(current_user.id)
    
    return jsonify({
        'success': True,
        'data': {
            'monthly_expenses': summary['current_month']['expenses'],
            'monthly_incomes': summary['current_month']['income'],
            'balance': summary['current_month']['balance'],
            'previous_month_expenses': summary['previous_month']['expenses'],
            'expense_by_category': summary['expense_by_category']
        }
    })

