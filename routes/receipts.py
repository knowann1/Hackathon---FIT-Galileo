import os
from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app, jsonify
from flask_babel import gettext as _
from werkzeug.utils import secure_filename
from services.receipt_service import parse_receipt_image
from flask_login import login_required, current_user
from datetime import datetime
from routes.expenses import CATEGORIES, PAYMENT_METHODS

receipts_bp = Blueprint('receipts', __name__, template_folder='../templates')


def _is_allowed_upload(filename: str) -> bool:
    allowed = {ext.lower() for ext in current_app.config.get('UPLOAD_EXTENSIONS', [])}
    return os.path.splitext(filename)[1].lower() in allowed


@receipts_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_receipt():
    if request.method == 'POST':
        f = request.files.get('receipt')
        if not f:
            flash(_('Selecciona un archivo'), 'danger')
            return redirect(url_for('receipts.upload_receipt'))
        filename = secure_filename(f.filename)
        if not filename or not _is_allowed_upload(filename):
            flash(_('Formato no permitido. Sube una imagen PNG, JPG o PDF.'), 'danger')
            return redirect(url_for('receipts.upload_receipt'))
        upload_dir = current_app.config.get('UPLOAD_PATH')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        f.save(file_path)
        # Send to receipt service for parsing
        result = parse_receipt_image(file_path)
        # Include uploaded filename so we can save reference when confirming
        return render_template('receipt_review.html', result=result, uploaded_filename=filename, categories=CATEGORIES, payment_methods=PAYMENT_METHODS)
    return render_template('receipt_review.html', result=None, categories=CATEGORIES, payment_methods=PAYMENT_METHODS)


@receipts_bp.route('/parse', methods=['POST'])
@login_required
def parse_only():
    # API endpoint to accept an uploaded file and return parsed JSON
    f = request.files.get('receipt')
    if not f:
        return jsonify({'error': 'no file'}), 400
    filename = secure_filename(f.filename)
    if not filename or not _is_allowed_upload(filename):
        return jsonify({'error': 'Formato no permitido. Usa PNG, JPG, JPEG o PDF.'}), 400
    upload_dir = current_app.config.get('UPLOAD_PATH')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    f.save(file_path)
    result = parse_receipt_image(file_path)
    return jsonify(result)


@receipts_bp.route('/confirm', methods=['POST'])
@login_required
def confirm_receipt():
    # Save parsed receipt as an Expense (proposal must be reviewed before calling)
    from extensions import db
    from models import Expense
    data = request.form or request.json or {}
    try:
        total = float(data.get('total')) if data.get('total') not in (None, '', 'null') else None
    except Exception:
        total = None
    merchant = data.get('merchant') or data.get('comercio')
    description = data.get('description') or data.get('descripcion')
    date_str = data.get('date') or data.get('expense_date') or data.get('fecha')
    expense_date = None
    if date_str:
        try:
            expense_date = datetime.fromisoformat(date_str).date()
        except Exception:
            try:
                expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except Exception:
                try:
                    expense_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                except Exception:
                    expense_date = None
    currency = data.get('currency') or 'GTQ'
    category = data.get('category')
    payment_method = data.get('payment_method')
    ai_confidence = None
    try:
        ai_confidence = float(data.get('confidence')) if data.get('confidence') else None
    except Exception:
        ai_confidence = None

    if total is None:
        flash(_('Total no detectado, no se puede guardar'), 'danger')
        return redirect(url_for('receipts.upload_receipt'))

    if not description:
        description = 'Recibo importado'
        if merchant:
            description = f'{description}: {merchant}'
        if data.get('invoice_number'):
            description = f'{description} - {data.get("invoice_number")}'

    uploaded_filename = data.get('uploaded_filename')
    receipt_url = None
    if uploaded_filename:
        # store relative path
        receipt_url = os.path.join(current_app.config.get('UPLOAD_PATH', ''), uploaded_filename)

    transaction_type = (data.get('transaction_type') or 'expense')
    exp = Expense(
        user_id=current_user.id,
        amount=total,
        currency=currency,
        description=description,
        merchant=merchant,
        category=category,
        payment_method=payment_method,
        expense_date=expense_date,
        ai_generated=True,
        ai_confidence=ai_confidence,
        receipt_image_url=receipt_url,
        transaction_type=transaction_type
    )
    db.session.add(exp)
    db.session.commit()
    if transaction_type == "income":
        flash(_('Factura guardada como ingreso'), 'success')
    else:
        flash(_('Factura guardada como gasto'), 'success')
    return redirect(url_for('expenses.list_expenses'))
