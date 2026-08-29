
import os

from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify
)
from flask_babel import gettext as _

from werkzeug.utils import secure_filename

from services.voice_service import transcribe_and_parse

from flask_login import login_required, current_user

from datetime import datetime

from routes.expenses import (
    CATEGORIES,
    PAYMENT_METHODS
)


voice_bp = Blueprint(
    'voice',
    __name__,
    template_folder='../templates'
)


# ============================================================
# VALIDAR FORMATO DE AUDIO
# ============================================================

def _is_allowed_audio(filename: str) -> bool:

    allowed = {
        ext.lower()
        for ext in current_app.config.get(
            'UPLOAD_EXTENSIONS',
            []
        )
    }

    return (
        os.path.splitext(filename)[1].lower()
        in allowed
    )


# ============================================================
# GRABAR / SUBIR AUDIO
# ============================================================

@voice_bp.route(
    '/record',
    methods=['GET', 'POST']
)
@login_required
def record_voice():

    if request.method == 'POST':

        # ----------------------------------------------------
        # 1. Obtener archivo
        # ----------------------------------------------------

        f = request.files.get('audio')

        if not f:

            flash(
                _('Selecciona un archivo de audio'),
                'danger'
            )

            return redirect(
                url_for('voice.record_voice')
            )

        # ----------------------------------------------------
        # 2. Validar nombre
        # ----------------------------------------------------

        filename = secure_filename(
            f.filename
        )

        if not filename:

            flash(
                _('El archivo de audio no es válido.'),
                'danger'
            )

            return redirect(
                url_for('voice.record_voice')
            )

        # ----------------------------------------------------
        # 3. Validar extensión
        # ----------------------------------------------------

        if not _is_allowed_audio(filename):

            flash(
                _('Formato de audio no permitido. Usa WAV, MP3, M4A, OGG o WEBM.'),
                'danger'
            )

            return redirect(
                url_for('voice.record_voice')
            )

        # ----------------------------------------------------
        # 4. Crear carpeta de uploads
        # ----------------------------------------------------

        upload_dir = current_app.config.get(
            'UPLOAD_PATH'
        )

        if not upload_dir:

            flash(
                _('La carpeta de archivos no está configurada.'),
                'danger'
            )

            return redirect(
                url_for('voice.record_voice')
            )

        os.makedirs(
            upload_dir,
            exist_ok=True
        )

        # ----------------------------------------------------
        # 5. Generar nombre seguro
        # ----------------------------------------------------

        file_path = os.path.join(
            upload_dir,
            filename
        )

        # ----------------------------------------------------
        # 6. Guardar audio
        # ----------------------------------------------------

        f.save(file_path)

        # ----------------------------------------------------
        # 7. Enviar audio a IA
        #
        # La función realiza:
        #
        # AUDIO
        #   ↓
        # TRANSCRIPCIÓN
        #   ↓
        # ANÁLISIS
        #   ↓
        # DATOS FINANCIEROS
        # ----------------------------------------------------

        try:

            result = transcribe_and_parse(
                file_path
            )

        except Exception as exc:

            print(
                'Voice processing error:',
                type(exc).__name__,
                str(exc)
            )

            flash(
                _('No se pudo procesar el audio.'),
                'danger'
            )

            return redirect(
                url_for('voice.record_voice')
            )

        # ----------------------------------------------------
        # 8. Mostrar resultado para revisión
        # ----------------------------------------------------

        return render_template(
            'voice_review.html',
            result=result,
            categories=CATEGORIES,
            payment_methods=PAYMENT_METHODS
        )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    return render_template(
        'voice_review.html',
        result=None,
        categories=CATEGORIES,
        payment_methods=PAYMENT_METHODS
    )


# ============================================================
# PROCESAR AUDIO DESDE AJAX / API
# ============================================================

@voice_bp.route(
    '/parse',
    methods=['POST']
)
@login_required
def parse_audio():

    f = request.files.get(
        'audio'
    )

    if not f:

        return jsonify({
            'error': 'No se recibió ningún archivo de audio.'
        }), 400

    # --------------------------------------------------------
    # Validar archivo
    # --------------------------------------------------------

    filename = secure_filename(
        f.filename
    )

    if not filename:

        return jsonify({
            'error': 'Archivo de audio inválido.'
        }), 400

    if not _is_allowed_audio(filename):

        return jsonify({
            'error': (
                'Formato de audio no permitido. '
                'Usa WAV, MP3, M4A, OGG o WEBM.'
            )
        }), 400

    # --------------------------------------------------------
    # Directorio
    # --------------------------------------------------------

    upload_dir = current_app.config.get(
        'UPLOAD_PATH'
    )

    if not upload_dir:

        return jsonify({
            'error': 'UPLOAD_PATH no está configurado.'
        }), 500

    os.makedirs(
        upload_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # Guardar archivo
    # --------------------------------------------------------

    file_path = os.path.join(
        upload_dir,
        filename
    )

    f.save(file_path)

    # --------------------------------------------------------
    # IA
    # --------------------------------------------------------

    try:

        result = transcribe_and_parse(
            file_path
        )

        return jsonify(
            result
        )

    except Exception as exc:

        print(
            'Voice parse error:',
            type(exc).__name__,
            str(exc)
        )

        return jsonify({
            'error': str(exc)
        }), 500


# ============================================================
# CONFIRMAR Y GUARDAR TRANSACCIÓN
# ============================================================

@voice_bp.route(
    '/confirm',
    methods=['POST']
)
@login_required
def confirm_voice():

    from extensions import db
    from models import Expense

    # --------------------------------------------------------
    # Obtener datos
    # --------------------------------------------------------

    if request.form:

        data = request.form

    else:

        data = (
            request.get_json(
                silent=True
            ) or {}
        )

    # --------------------------------------------------------
    # Monto
    # --------------------------------------------------------

    try:

        raw_amount = data.get(
            'amount'
        )

        if raw_amount in (
            None,
            '',
            'null'
        ):

            amount = None

        else:

            amount = float(
                raw_amount
            )

    except (
        ValueError,
        TypeError
    ):

        amount = None

    # --------------------------------------------------------
    # Datos extraídos por IA
    # --------------------------------------------------------

    currency = (
        data.get('currency')
        or 'GTQ'
    )

    merchant = data.get(
        'merchant'
    )

    description = data.get(
        'description'
    )

    category = data.get(
        'category'
    )

    payment_method = data.get(
        'payment_method'
    )

    transaction_type = (
        data.get('transaction_type')
        or 'expense'
    )

    # --------------------------------------------------------
    # Fecha
    # --------------------------------------------------------

    date_str = data.get(
        'expense_date'
    )

    expense_date = None

    if date_str:

        try:

            expense_date = (
                datetime
                .fromisoformat(
                    date_str
                )
                .date()
            )

        except (
            ValueError,
            TypeError
        ):

            try:

                expense_date = (
                    datetime
                    .strptime(
                        date_str,
                        '%Y-%m-%d'
                    )
                    .date()
                )

            except (
                ValueError,
                TypeError
            ):

                expense_date = None

    # --------------------------------------------------------
    # Validar monto
    # --------------------------------------------------------

    if amount is None:

        flash(
            _('Monto inválido, no se guardó.'),
            'danger'
        )

        return redirect(
            url_for('voice.record_voice')
        )

    # --------------------------------------------------------
    # Validar tipo de transacción
    # --------------------------------------------------------

    if transaction_type not in (
        'expense',
        'income'
    ):

        transaction_type = 'expense'

    # --------------------------------------------------------
    # Crear registro
    # --------------------------------------------------------

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

    db.session.add(
        exp
    )

    db.session.commit()

    # --------------------------------------------------------
    # Mensaje
    # --------------------------------------------------------

    if transaction_type == 'income':

        flash(
            _('Ingreso guardado desde voz.'),
            'success'
        )

    else:

        flash(
            _('Gasto guardado desde voz.'),
            'success'
        )

    return redirect(
        url_for(
            'expenses.list_expenses'
        )
    )

