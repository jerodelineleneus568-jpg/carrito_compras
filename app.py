import os
from flask import Flask
from dotenv import load_dotenv
from controllers.carrito_controller import carrito_bp
from controllers.auth_controller import auth_bp
import secrets

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Registrar el controlador (Blueprint)
app.register_blueprint(carrito_bp)
app.register_blueprint(auth_bp)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True, ssl_context='adhoc')