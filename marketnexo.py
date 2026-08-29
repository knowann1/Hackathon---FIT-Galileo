from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from extensions import db
from models import MarketPost


marketnexo_bp = Blueprint('marketnexo', __name__, template_folder='../templates')


@marketnexo_bp.route('/')
@login_required
def index():
    posts = MarketPost.query.order_by(MarketPost.created_at.desc()).all()
    return render_template('marketnexo.html', posts=posts)


@marketnexo_bp.route('/new', methods=['POST'])
@login_required
def create_post():
    product = (request.form.get('product') or '').strip()
    description = (request.form.get('description') or '').strip()
    email = (request.form.get('email') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    whatsapp = (request.form.get('whatsapp') or '').strip()
    social_media = (request.form.get('social_media') or '').strip()

    if not product or not description or not email:
        flash(_('Completa el producto o servicio, la descripción y el correo.'), 'danger')
        return redirect(url_for('marketnexo.index'))

    if not phone and not whatsapp:
        flash(_('Agrega un teléfono o un WhatsApp para que puedan contactarte.'), 'danger')
        return redirect(url_for('marketnexo.index'))

    post = MarketPost(
        user_id=current_user.id,
        product=product,
        description=description,
        email=email,
        phone=phone or None,
        whatsapp=whatsapp or None,
        social_media=social_media or None,
    )
    db.session.add(post)
    db.session.commit()
    flash(_('Tu publicación se agregó a Marketnexo.'), 'success')
    return redirect(url_for('marketnexo.index'))
