from database import get_db_connection

class ProductoModel:

    @staticmethod
    def obtener_disponibles():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre, descripcion, precio, stock, imagen FROM productos WHERE stock > 0")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def obtener_todos():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre, descripcion, precio, stock, imagen FROM productos ORDER BY stock ASC")
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def obtener_por_id(producto_id):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, nombre, descripcion, precio, stock, imagen FROM productos WHERE id = %s", (producto_id,))
                return cur.fetchone()
        finally:
            conn.close()

    @staticmethod
    def obtener_por_lista_ids(ids):
        if not ids:
            return []

        sanitized_ids = [int(i) for i in ids if str(i).isdigit()]
        if not sanitized_ids:
            return []

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                resultados = []
                for pid in sanitized_ids:
                    cur.execute(
                        "SELECT id, nombre, precio, stock, imagen FROM productos WHERE id = %s",
                        (pid,)
                    )
                    prod = cur.fetchone()
                    if prod:
                        resultados.append(prod)
                return resultados
        finally:
            conn.close()

    @staticmethod
    def reabastecer_stock(producto_id, cantidad_a_sumar, usuario_id=None, motivo="Reabastecimiento de bodega"):
        if cantidad_a_sumar <= 0:
            return False, "La cantidad a reponer debe ser mayor a 0."

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT stock FROM productos WHERE id = %s FOR UPDATE", (producto_id,))
                prod = cur.fetchone()
                if not prod:
                    conn.rollback()
                    return False, "El producto no existe."

                stock_anterior = prod['stock']
                stock_nuevo = stock_anterior + cantidad_a_sumar

                cur.execute("UPDATE productos SET stock = %s WHERE id = %s", (stock_nuevo, producto_id))

                cur.execute("""
                    INSERT INTO movimientos_stock
                    (producto_id, usuario_id, tipo, cantidad, stock_anterior, stock_nuevo, motivo)
                    VALUES (%s, %s, 'ENTRADA', %s, %s, %s, %s)
                """, (producto_id, usuario_id, cantidad_a_sumar, stock_anterior, stock_nuevo, motivo))

                conn.commit()
                return True, "Stock actualizado y movimiento registrado."
        except Exception:
            conn.rollback()
            return False, "Error interno de base de datos al reabastecer stock."
        finally:
            conn.close()

    @staticmethod
    def actualizar_precio(producto_id, nuevo_precio):
        if nuevo_precio <= 0:
            return False, "El precio debe ser mayor a 0."

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE productos SET precio = %s WHERE id = %s", (nuevo_precio, producto_id))
                conn.commit()
                return True, "Precio actualizado correctamente."
        except Exception:
            conn.rollback()
            return False, "Error interno al actualizar el precio."
        finally:
            conn.close()

    @staticmethod
    def procesar_venta(items_carrito, usuario_id=None):
        if not items_carrito:
            return False, "El carrito no contiene productos."

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                productos_bloqueados = {}

                # 1. Bloqueo pesimista y verificación de stock
                for prod_id, cantidad in items_carrito.items():
                    cur.execute("SELECT id, stock, nombre FROM productos WHERE id = %s FOR UPDATE", (prod_id,))
                    prod = cur.fetchone()
                    if not prod or prod['stock'] < cantidad:
                        conn.rollback()
                        nombre = prod['nombre'] if prod else "desconocido"
                        return False, f"Stock insuficiente para {nombre}."
                    productos_bloqueados[prod_id] = prod

                # 2. Descuento e inserción de Kardex
                for prod_id, cantidad in items_carrito.items():
                    prod = productos_bloqueados[prod_id]
                    stock_anterior = prod['stock']
                    stock_nuevo = stock_anterior - cantidad

                    cur.execute("UPDATE productos SET stock = %s WHERE id = %s", (stock_nuevo, prod_id))

                    cur.execute("""
                        INSERT INTO movimientos_stock
                        (producto_id, usuario_id, tipo, cantidad, stock_anterior, stock_nuevo, motivo)
                        VALUES (%s, %s, 'SALIDA', %s, %s, %s, 'Venta en tienda')
                    """, (prod_id, usuario_id, cantidad, stock_anterior, stock_nuevo))

                conn.commit()
                return True, "¡Compra realizada con éxito! Movimientos registrados en el histórico."
        except Exception:
            conn.rollback()
            return False, "Ocurrió un error transaccional al procesar la venta."
        finally:
            conn.close()

    @staticmethod
    def obtener_movimientos(limite=50):
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT m.id, m.tipo, m.cantidad, m.stock_anterior, m.stock_nuevo, m.motivo, m.fecha,
                           p.nombre AS producto_nombre,
                           COALESCE(u.nombre, 'Cliente Web') AS usuario_nombre,
                           COALESCE(u.rol, 'cliente') AS usuario_rol
                    FROM movimientos_stock m
                    INNER JOIN productos p ON m.producto_id = p.id
                    LEFT JOIN usuarios u ON m.usuario_id = u.id
                    ORDER BY m.fecha DESC
                    LIMIT %s
                """, (int(limite),))
                return cur.fetchall()
        finally:
            conn.close()

    @staticmethod
    def obtener_resumen_movimientos():
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tipo, SUM(cantidad) AS total_unidades, COUNT(*) AS total_eventos
                    FROM movimientos_stock
                    GROUP BY tipo
                """)
                resumen_tipo = cur.fetchall()

                cur.execute("""
                    SELECT p.nombre, SUM(m.cantidad) AS total_movido
                    FROM movimientos_stock m
                    INNER JOIN productos p ON m.producto_id = p.id
                    GROUP BY p.nombre
                    ORDER BY total_movido DESC
                    LIMIT 5
                """)
                top_productos = cur.fetchall()
                return resumen_tipo, top_productos
        finally:
            conn.close()