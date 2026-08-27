import os
from flask import Blueprint, request, render_template, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename
from services.voice_service import transcribe_and_parse
from flask_login import login_required, current_user
from datetime import datetime
from routes.expenses import CATEGORIES, PAYMENT_METHODS

voice_bp = Blueprint('voice', __name__, template_folder='../templates')


def _is_allowed_audio(filename: str) -> bool:
    allowed = {ext.lower() for ext in current_app.config.get('UPLOAD_EXTENSIONS', [])}
    return os.path.splitext(filename)[1].lower() in allowed


@voice_bp.route('/record', methods=['GET', 'POST'])
@login_required
def record_voice():
    if request.method == 'POST':
        f = request.files.get('audio')
        if not f:
            flash('Selecciona un archivo de audio', 'danger')
            return redirect(url_for('voice.record_voice'))
        filename = secure_filename(f.filename)
        if not filename or not _is_allowed_audio(filename):
            flash('Formato de audio no permitido. Usa WAV, MP3, M4A, OGG o WEBM.', 'danger')
            return redirect(url_for('voice.record_voice'))
        upload_dir = current_app.config.get('UPLOAD_PATH')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, filename)
        f.save(file_path)
        result = transcribe_and_parse(file_path)
        return render_template('voice_review.html', result=result, categories=CATEGORIES, payment_methods=PAYMENT_METHODS)
    return render_template('voice_review.html', result=None, categories=CATEGORIES, payment_methods=PAYMENT_METHODS)


@voice_bp.route('/parse', methods=['POST'])
@login_required
def parse_audio():
    f = request.files.get('audio')
    if not f:
        return jsonify({'error': 'no file'}), 400
    filename = secure_filename(f.filename)
    if not filename or not _is_allowed_audio(filename):
        return jsonify({'error': 'Formato de audio no permitido. Usa WAV, MP3, M4A, OGG o WEBM.'}), 400
    upload_dir = current_app.config.get('UPLOAD_PATH')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    f.save(file_path)
    result = transcribe_and_parse(file_path)
    return jsonify(result)


@voice_bp.route('/confirm', methods=['POST'])
@login_required
def confirm_voice():
    # Save parsed voice proposal as Expense
    from extensions import db
    from models import Expense
    data = request.form or request.json or {}
    try:
        amount = float(data.get('amount')) if data.get('amount') not in (None, '', 'null') else None
    except Exception:
        amount = None
    currency = data.get('currency') or 'GTQ'
    merchant = data.get('merchant')
    description = data.get('description')
    category = data.get('category')
    payment_method = data.get('payment_method')
    date_str = data.get('expense_date')
    expense_date = None
    if date_str:
        try:
            expense_date = datetime.fromisoformat(date_str).date()
        except Exception:
            try:
                expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except Exception:
                expense_date = None
    if amount is None:
        flash('Monto inválido, no se guardó', 'danger')
        return redirect(url_for('voice.record_voice'))
    transaction_type = (data.get('transaction_type') or 'expense')
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
        transaction_type=transaction_type
    )
    db.session.add(exp)
    db.session.commit()
    flash(f'{"Ingreso" if transaction_type=="income" else "Gasto"} guardado desde voz', 'success')
    return redirect(url_for('expenses.list_expenses'))
