from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

class UsuarioModel:

    @staticmethod
    def obtener_por_email(email):
        if not email:
            return None
            
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, nombre, email, password_hash, rol FROM usuarios WHERE email = %s", 
                    (email.strip().lower(),)
                )
                return cur.fetchone()
        finally:
            conn.close()

    @staticmethod
    def crear_usuario(nombre, email, password, rol='cliente'):
        # Validación de parámetros base
        if not nombre or not email or not password:
            return False, "Todos los campos son obligatorios."
            
        if len(password) < 8:
            return False, "La contraseña debe tener al menos 8 caracteres."

        roles_validos = {'admin', 'bodega', 'cliente'}
        rol_limpio = rol.lower() if rol in roles_validos else 'cliente'

        # Hashing criptográfico robusto (OWASP Top 10 - A02)
        hashed_pwd = generate_password_hash(password, method='scrypt')

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Se completan los parámetros que faltaban en la tupla
                cur.execute(
                    "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (%s, %s, %s, %s)",
                    (nombre.strip(), email.strip().lower(), hashed_pwd, rol_limpio)
                )
                conn.commit()
                return True, "Usuario registrado correctamente."

        except Exception:
            conn.rollback()
            # Mensaje controlado sin filtrar datos de la BD (CWE-209)
            return False, "El correo electrónico ya está registrado o los datos no son válidos."
        finally:
            conn.close()