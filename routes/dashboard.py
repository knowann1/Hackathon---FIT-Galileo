from flask import Blueprint, render_template
from flask_login import login_required, current_user
from services.financial_analyzer import summarize_user_finances, detect_insights


dashboard_bp = Blueprint('dashboard', __name__, template_folder='../templates')


@dashboard_bp.route('/dashboard')
@login_required
def index():
    summary = summarize_user_finances(current_user.id)
    insights = detect_insights(current_user.id)
    # Compute a simple top category for quick tips
    top_category = None
    try:
        if summary.get('expense_by_category'):
            top_category = max(summary['expense_by_category'].items(), key=lambda x: x[1])
    except Exception:
        top_category = None
    return render_template('dashboard.html', summary=summary, insights=insights, top_category=top_category)
