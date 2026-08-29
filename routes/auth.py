from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_babel import gettext as _
from extensions import db
from models import User
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        if not username or not email or not password:
            flash(_('Completa todos los campos'), 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash(_('Usuario o correo ya existe'), 'danger')
            return redirect(url_for('auth.register'))
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        # Iniciar sesión automáticamente y redirigir al panel
        login_user(user)
        flash(_('Registro exitoso. Bienvenido.'), 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('login.html', register=True)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash(_('Has iniciado sesión'), 'success')
            return redirect(url_for('dashboard.index'))
        flash(_('Credenciales inválidas'), 'danger')
        return redirect(url_for('auth.login'))
    return render_template('login.html', register=False)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash(_('Sesión cerrada'), 'info')
    return redirect(url_for('auth.login'))
