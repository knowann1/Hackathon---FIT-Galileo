
from flask import Blueprint, render_template
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


