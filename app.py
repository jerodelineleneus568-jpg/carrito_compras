import os
from flask import Flask
from dotenv import load_dotenv
from controllers.carrito_controller import carrito_bp
from controllers.auth_controller import auth_bp

import requests  # <-- AGREGAR AQUÍ
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_wtf.csrf import CSRFProtect


load_dotenv()

app = Flask(__name__)

# --- CONEXIÓN CON LA PASARELA BANCARIA (PUERTO 6001) ---
BANCO_API_URL = "https://127.0.0.1:6001/api/v1/pagar"
BANCO_API_TOKEN = "Bearer token_secreto_carrito_banco_2026"
# 1. Usar el SECRET_KEY del .env (evita regeneración de sesiones)
app.secret_key = os.getenv('SECRET_KEY')

# 2. Hardening de Cookies de Sesión (Mitiga OWASP ZAP / A05)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True  # True ya que usas ssl_context='adhoc' (HTTPS)
)

# 3. Cabeceras HTTP de Seguridad (Cero alertas en OWASP ZAP Pasivo)
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' data: http: https: https://via.placeholder.com https://images.unsplash.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
    )
    return response

# Registrar controladores
app.register_blueprint(carrito_bp)
app.register_blueprint(auth_bp)

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5001, debug=debug_mode, ssl_context='adhoc')


# ====================================================================
# RUTAS DE INTEGRACIÓN CON PASARELA BANCARIA
# ====================================================================

@app.route('/checkout')
def checkout():
    """Muestra el formulario para ingresar la tarjeta bancaria."""
    carrito = session.get('carrito', {})
    if not carrito:
        flash('Tu carrito está vacío. Agrega productos antes de pagar.', 'warning')
        return redirect(url_for('index'))
    
    total = sum(float(item['precio']) * int(item['cantidad']) for item in carrito.values())
    return render_template('checkout.html', total=total)


@app.route('/checkout/procesar', methods=['POST'])
def checkout_procesar():
    """Envía los datos de la tarjeta a la API del Banco en el puerto 6001."""
    carrito = session.get('carrito', {})
    if not carrito:
        flash('El carrito está vacío.', 'danger')
        return redirect(url_for('index'))

    total_monto = sum(float(item['precio']) * int(item['cantidad']) for item in carrito.values())

    payload = {
        "numero_tarjeta": request.form.get('numero_tarjeta', '').strip(),
        "fecha_expiracion": request.form.get('expiracion', '').strip(),
        "cvv": request.form.get('cvv', '').strip(),
        "monto": total_monto,
        "comercio": "Tienda Carrito Flask"
    }

    headers = {
        "Authorization": BANCO_API_TOKEN,
        "Content-Type": "application/json"
    }

    try:
        # timeout=5 obligatorio para cumplir con la regla Bandit B113
        # verify=False porque el banco usa certificados autofirmados locales
        respuesta = requests.post(
            BANCO_API_URL,
            json=payload,
            headers=headers,
            timeout=5,
            verify=False
        )
        data = respuesta.json()

        if respuesta.status_code == 200 and data.get('exito'):
            session['carrito'] = {}
            session.modified = True
            
            session['ultimo_comprobante'] = {
                'codigo': data.get('codigo_autorizacion'),
                'titular': data.get('titular'),
                'monto': total_monto,
                'nuevo_saldo': data.get('nuevo_saldo')
            }
            return redirect(url_for('compra_exitosa'))
        else:
            mensaje = data.get('mensaje', 'Operación rechazada por la entidad bancaria.')
            flash(f"Rechazo bancario: {mensaje}", 'danger')
            return redirect(url_for('checkout'))

    except requests.exceptions.RequestException:
        flash('No se pudo conectar con el Banco. Verifique que el servicio bancario esté activo.', 'danger')
        return redirect(url_for('checkout'))


@app.route('/compra-exitosa')
def compra_exitosa():
    """Muestra el comprobante emitido por el banco."""
    comprobante = session.pop('ultimo_comprobante', None)
    if not comprobante:
        return redirect(url_for('index'))
    return render_template('exito.html', comprobante=comprobante)    