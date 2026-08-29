from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_babel import gettext as _
from flask_login import login_required, current_user
from extensions import db
from models import Expense
from datetime import datetime

expenses_bp = Blueprint('expenses', __name__, template_folder='../templates')

CATEGORIES = [
    'Venta de servicios', 'Venta de artículos', 'Compra de inventario', 'Gastos operativos',
    'Alimentación', 'Transporte', 'Entretenimiento', 'Supermercado', 'Educación',
    'Salud', 'Vivienda', 'Nómina', 'Marketing', 'Tecnología', 'Impuestos', 'Otros'
]
PAYMENT_METHODS = ['Efectivo', 'Tarjeta de débito', 'Tarjeta de crédito', 'Transferencia', 'Otro']


@expenses_bp.route('/')
@login_required
def list_expenses():
    eps = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.expense_date.desc()).all()
    return render_template('expenses.html', expenses=eps)


@expenses_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_expense():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
        except (TypeError, ValueError):
            flash(_('Monto inválido'), 'danger')
            return redirect(url_for('expenses.new_expense'))
        currency = request.form.get('currency') or 'GTQ'
        description = request.form.get('description')
        merchant = request.form.get('merchant')
        category = request.form.get('category')
        payment_method = request.form.get('payment_method')
        transaction_type = request.form.get('transaction_type') or 'expense'
        date_str = request.form.get('expense_date')
        try:
            expense_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None
        except ValueError:
            flash(_('Fecha inválida'), 'danger')
            return redirect(url_for('expenses.new_expense'))
        exp = Expense(
            user_id=current_user.id,
            amount=amount,
            currency=currency,
            description=description,
            merchant=merchant,
            category=category,
            payment_method=payment_method,
            expense_date=expense_date,
            ai_generated=False,
            transaction_type=transaction_type
        )
        db.session.add(exp)
        db.session.commit()
        if transaction_type == "income":
            flash(_('Ingreso registrado'), 'success')
        else:
            flash(_('Gasto registrado'), 'success')
        return redirect(url_for('expenses.list_expenses'))
    return render_template('expense_form.html', categories=CATEGORIES, payment_methods=PAYMENT_METHODS)


@expenses_bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    exp = Expense.query.get_or_404(expense_id)
    if exp.user_id != current_user.id:
        flash(_('No autorizado'), 'danger')
        return redirect(url_for('expenses.list_expenses'))
    db.session.delete(exp)
    db.session.commit()
    flash(_('Gasto eliminado'), 'info')
    return redirect(url_for('expenses.list_expenses'))
