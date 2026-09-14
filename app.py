import os
from flask import Flask
from dotenv import load_dotenv
from controllers.carrito_controller import carrito_bp
from controllers.auth_controller import auth_bp

load_dotenv()

app = Flask(__name__)

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
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;"
    )
    return response

# Registrar controladores
app.register_blueprint(carrito_bp)
app.register_blueprint(auth_bp)

if __name__ == '__main__':
    # Configuración limpia de producción/auditoría (debug=False para Bandit)
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.app.run(host='0.0.0.0', port=5001, debug=debug_mode, ssl_context='adhoc')run(host='127.0.0.1', port=5001, debug=debug_mode, ssl_context='adhoc')