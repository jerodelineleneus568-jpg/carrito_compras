from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from models.usuario_model import UsuarioModel
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def role_required(*roles_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            rol_actual = session.get('rol')
            if not rol_actual:
                flash("Debes iniciar sesión para realizar esta acción.", "warning")
                return redirect(url_for('auth.login'))
            if rol_actual not in roles_permitidos:
                flash("No tienes permisos suficientes para realizar esta acción.", "danger")
                return redirect(url_for('carrito.catalogo'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        usuario = UsuarioModel.obtener_por_email(email)
        if usuario and check_password_hash(usuario['password_hash'], password):
            session['usuario_id'] = usuario['id']
            session['nombre'] = usuario['nombre']
            session['rol'] = usuario['rol']
            flash(f"Bienvenido de nuevo, {usuario['nombre']} ({usuario['rol'].capitalize()})", "success")
            return redirect(url_for('carrito.catalogo'))

        flash("Correo o contraseña incorrectos.", "danger")

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Has cerrado sesión.", "info")
    return redirect(url_for('carrito.catalogo'))