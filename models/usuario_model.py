from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

class UsuarioModel:
    @staticmethod
    def obtener_por_email(email):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre, email, password_hash, rol FROM usuarios WHERE email = %s", (email,))
                return cur.fetchone()
        finally:
            conn.close()

    @staticmethod
    def crear_usuario(nombre, email, password, rol='cliente'):
        conn = get_db_connection()
        try:
            hashed_pwd = generate_password_hash(password)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO usuarios(nombre, email, password_hash, rol) VALUES (%s, %s, %s,)",
                
                )
                conn.commit()
                return True, "Usuario registrado correctamente."

        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()                           