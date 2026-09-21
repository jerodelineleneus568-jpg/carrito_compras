import io

from urllib.parse import urlparse
import requests
import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from models.producto_model import ProductoModel
from controllers.auth_controller import role_required

carrito_bp = Blueprint('carrito', __name__)

def es_url_interna_segura(target):
    """Valida que la URL de redirección pertenezca estrictamente al mismo host (Anti-Open Redirect)."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(target)
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@carrito_bp.route('/')
def catalogo():
    productos = ProductoModel.obtener_disponibles()
    return render_template('productos.html', productos=productos)


@carrito_bp.route('/carrito', methods=['GET'])
def ver_carrito():
    carrito = session.get('carrito', {})
    items = []
    total = 0.0

    for prod_id_str, val in carrito.items():
        cantidad = val['cantidad'] if isinstance(val, dict) else int(val)
        prod = ProductoModel.obtener_por_id(int(prod_id_str))
        if prod:
            subtotal = float(prod['precio']) * cantidad
            total += subtotal
            items.append({
                'id': prod['id'],
                'nombre': prod['nombre'],
                'precio': prod['precio'],
                'cantidad': cantidad,
                'subtotal': subtotal,
                'imagen': prod.get('imagen')
            })

    return render_template('carrito.html', items=items, total=total)


@carrito_bp.route('/carrito/agregar/<int:producto_id>', methods=['POST'])
def agregar(producto_id):
    try:
        cantidad = int(request.form.get('cantidad', 1))
        if cantidad <= 0:
            cantidad = 1
    except (ValueError, TypeError):
        cantidad = 1

    producto = ProductoModel.obtener_por_id(producto_id)
    if not producto:
        flash("El producto no existe.", "danger")
        return redirect(url_for('carrito.catalogo'))

    if 'carrito' not in session:
        session['carrito'] = {}

    carrito = session['carrito']
    prod_id_str = str(producto_id)
    cantidad_actual = carrito.get(prod_id_str, 0)

    if cantidad_actual + cantidad > producto['stock']:
        flash(f"Stock insuficiente. Solo quedan {producto['stock']} unidades.", "warning")
    else:
        carrito[prod_id_str] = cantidad_actual + cantidad
        session['carrito'] = carrito
        session.modified = True
        flash(f"'{producto['nombre']}' añadido al carrito.", "success")

    return redirect(url_for('carrito.ver_carrito'))


@carrito_bp.route('/carrito/actualizar/<int:producto_id>', methods=['POST'])
def actualizar(producto_id):
    try:
        nueva_cantidad = int(request.form.get('cantidad', 0))
    except (ValueError, TypeError):
        nueva_cantidad = 0

    carrito = session.get('carrito', {})
    prod_id_str = str(producto_id)

    if prod_id_str in carrito:
        if nueva_cantidad <= 0:
            carrito.pop(prod_id_str)
            flash("Producto eliminado del carrito.", "info")
        else:
            producto = ProductoModel.obtener_por_id(producto_id)
            if producto and nueva_cantidad > producto['stock']:
                flash(f"No hay stock suficiente. Máximo: {producto['stock']}", "warning")
            else:
                carrito[prod_id_str] = nueva_cantidad
                flash("Cantidad actualizada correctamente.", "success")

        session['carrito'] = carrito
        session.modified = True

    return redirect(url_for('carrito.ver_carrito'))


@carrito_bp.route('/carrito/eliminar/<int:producto_id>', methods=['POST'])
def eliminar(producto_id):
    carrito = session.get('carrito', {})
    prod_id_str = str(producto_id)
    if prod_id_str in carrito:
        carrito.pop(prod_id_str)
        session['carrito'] = carrito
        session.modified = True
        flash("Producto quitado del carrito.", "info")
    return redirect(url_for('carrito.ver_carrito'))


@carrito_bp.route('/carrito/finalizar', methods=['POST'])
def finalizar():
    carrito = session.get('carrito', {})
    if not carrito:
        flash("El carrito está vacío.", "warning")
        return redirect(url_for('carrito.catalogo'))

    usuario_id = session.get('usuario_id')
    exito, mensaje = ProductoModel.procesar_venta(carrito, usuario_id=usuario_id)
    if exito:
        session.pop('carrito', None)
        session.modified = True
        flash(mensaje, "success")
    else:
        flash(f"Error al procesar la compra: {mensaje}", "danger")

    return redirect(url_for('carrito.ver_carrito'))


@carrito_bp.route('/producto/reabastecer/<int:producto_id>', methods=['POST'])
@role_required('admin', 'bodega')
def reabastecer(producto_id):
    try:
        cantidad = int(request.form.get('cantidad_stock', 0))
    except (ValueError, TypeError):
        cantidad = 0

    motivo = request.form.get('motivo', 'Reposición manual').strip()[:100]
    usuario_id = session.get('usuario_id')

    if cantidad <= 0:
        flash("Ingresa una cantidad válida a reponer.", "warning")
    else:
        exito, mensaje = ProductoModel.reabastecer_stock(producto_id, cantidad, usuario_id=usuario_id, motivo=motivo)
        if exito:
            flash(f"Stock reabastecido (+{cantidad} unidades).", "success")
        else:
            flash(f"Error: {mensaje}", "danger")

    return redirect(url_for('carrito.inventario'))


@carrito_bp.route('/producto/actualizar-precio/<int:producto_id>', methods=['POST'])
@role_required('admin')
def actualizar_precio(producto_id):
    raw_precio = str(request.form.get('nuevo_precio', '0')).strip().lower()

    # Mitigación estricta de NaN Injection (semgrep: nan-injection)
    if 'nan' in raw_precio or 'inf' in raw_precio:
        flash("Valor numérico inválido.", "danger")
        return redirect(url_for('carrito.inventario'))

    try:
        nuevo_precio = float(raw_precio)
    except (ValueError, TypeError):
        nuevo_precio = 0.0

    if nuevo_precio <= 0:
        flash("Ingresa un precio válido mayor a 0.", "warning")
    else:
        exito, mensaje = ProductoModel.actualizar_precio(producto_id, nuevo_precio)
        if exito:
            flash(mensaje, "success")
        else:
            flash(f"Error: {mensaje}", "danger")

    return redirect(url_for('carrito.inventario'))


@carrito_bp.route('/bodega/inventario')
@role_required('admin', 'bodega')
def inventario():
    productos = ProductoModel.obtener_todos()
    return render_template('inventario.html', productos=productos)


@carrito_bp.route('/bodega/movimientos')
@role_required('admin', 'bodega')
def movimientos():
    lista_movimientos = ProductoModel.obtener_movimientos(limite=100)
    return render_template('movimientos.html', movimientos=lista_movimientos)


@carrito_bp.route('/bodega/reportes')
@role_required('admin', 'bodega')
def reportes():
    resumen_tipo, top_productos = ProductoModel.obtener_resumen_movimientos()
    return render_template(
        'reportes.html',
        resumen_tipo=resumen_tipo,
        top_productos=top_productos
    )


@carrito_bp.route('/bodega/reportes/exportar/excel')
@role_required('admin', 'bodega')
def exportar_excel():
    movimientos = ProductoModel.obtener_movimientos(limite=1000)
    
    data = []
    for m in movimientos:
        data.append({
            'ID Evento': m['id'],
            'Fecha': m['fecha'].strftime('%Y-%m-%d %H:%M:%S') if m['fecha'] else '',
            'Tipo': m['tipo'],
            'Producto': m['producto_nombre'],
            'Cantidad': m['cantidad'],
            'Stock Previo': m['stock_anterior'],
            'Stock Posterior': m['stock_nuevo'],
            'Motivo': m['motivo'],
            'Responsable': f"{m['usuario_nombre']} ({m['usuario_rol']})"
        })

    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Historico_Stock')
    output.seek(0)

    return send_file(
        output,
        download_name="reporte_movimientos_stock.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@carrito_bp.route('/bodega/reportes/exportar/pdf')
@role_required('admin', 'bodega')
def exportar_pdf():
    movimientos = ProductoModel.obtener_movimientos(limite=100)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle(
        'TituloDoc',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#212529"),
        spaceAfter=14
    )
    
    elementos.append(Paragraph("Auditoría de Movimientos e Histórico de Stock", titulo_style))
    elementos.append(Paragraph("Reporte consolidado de entradas, despachos y ajustes de bodega.", styles['Normal']))
    elementos.append(Spacer(1, 15))

    encabezados = ['Fecha', 'Tipo', 'Producto', 'Cant.', 'Prev -> Post', 'Responsable']
    tabla_datos = [encabezados]

    for m in movimientos:
        tabla_datos.append([
            m['fecha'].strftime('%d/%m/%Y %H:%M') if m['fecha'] else 'N/A',
            m['tipo'],
            m['producto_nombre'][:18],
            str(m['cantidad']),
            f"{m['stock_anterior']} -> {m['stock_nuevo']}",
            m['usuario_nombre'][:15]
        ])

    tabla = Table(tabla_datos, colWidths=[95, 60, 140, 45, 90, 120])
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#212529")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8F9FA")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
    ]))

    elementos.append(tabla)
    doc.build(elementos)
    buffer.seek(0)

    return send_file(
        buffer,
        download_name="reporte_movimientos_stock.pdf",
        as_attachment=True,
        mimetype="application/pdf"
    )

BANCO_API_URL = "https://127.0.0.1:6001/api/v1/pagar"
BANCO_API_TOKEN = "Bearer token_secreto_carrito_banco_2026"

@carrito_bp.route('/checkout', methods=['GET'])
def checkout():
    carrito = session.get('carrito', {})
    if not carrito:
        flash('Tu carrito está vacío.', 'warning')
        return redirect(url_for('carrito.catalogo'))

    total = 0.0
    for prod_id_str, item in carrito.items():
        cantidad = item['cantidad'] if isinstance(item, dict) else int(item)
        try:
            prod = ProductoModel.obtener_por_id(int(prod_id_str))
            if prod:
                total += float(prod['precio']) * cantidad
        except Exception:
            continue

    if total <= 0:
        flash('Error al calcular el total de los productos.', 'danger')
        return redirect(url_for('carrito.ver_carrito'))

    session['total_pago'] = total
    session.modified = True

    return render_template('checkout.html', total=total)

@carrito_bp.route('/checkout/procesar', methods=['POST'])
def checkout_procesar():
    carrito = session.get('carrito', {})
    if not carrito:
        flash('El carrito está vacío.', 'danger')
        return redirect(url_for('carrito.catalogo'))

    # Formatear carrito a {int(id): int(cantidad)}
    items_carrito = {}
    total_real = 0.0

    for prod_id_str, item in carrito.items():
        cant = item['cantidad'] if isinstance(item, dict) else int(item)
        pid = int(prod_id_str)
        items_carrito[pid] = cant

        prod = ProductoModel.obtener_por_id(pid)
        if prod:
            total_real += float(prod['precio']) * cant

    # Datos bancarios del formulario
    num_tarjeta = request.form.get('numero_tarjeta', '').replace(' ', '').replace('-', '').strip()
    fecha_exp = request.form.get('expiracion', '').strip()
    cvv = request.form.get('cvv', '').strip()

    payload = {
        "numero_tarjeta": num_tarjeta,
        "fecha_expiracion": fecha_exp,
        "cvv": cvv,
        "monto": total_real,
        "comercio": "Tienda Pokémon"
    }

    headers = {
        "Authorization": "Bearer token_secreto_carrito_banco_2026",
        "Content-Type": "application/json"
    }

    try:
        respuesta = requests.post(
            "https://127.0.0.1:6001/api/v1/pagar",
            json=payload,
            headers=headers,
            timeout=5,
            verify=False
        )
        data = respuesta.json()

        if respuesta.status_code == 200 and data.get('exito'):
            # PAGO EXITOSO: Descontar stock usando el método nativo con Kardex
            exito_stock, msg_stock = ProductoModel.procesar_venta(items_carrito, usuario_id=session.get('user_id'))
            if not exito_stock:
                flash(f"Advertencia: {msg_stock}", 'warning')

            session['carrito'] = {}
            session.pop('total_pago', None)
            session.modified = True

            session['ultimo_comprobante'] = {
                'codigo': data.get('codigo_autorizacion'),
                'titular': data.get('titular'),
                'monto': total_real,
                'nuevo_saldo': data.get('nuevo_saldo')
            }
            return redirect(url_for('carrito.compra_exitosa'))
        else:
            mensaje = data.get('mensaje', 'Operación rechazada por el banco.')
            flash(f"Rechazo bancario: {mensaje}", 'danger')
            return redirect(url_for('carrito.checkout'))

    except requests.exceptions.RequestException:
        flash('No se pudo conectar con el servidor bancario (puerto 6001).', 'danger')
        return redirect(url_for('carrito.checkout'))

@carrito_bp.route('/compra-exitosa', methods=['GET'])
def compra_exitosa():
    comprobante = session.pop('ultimo_comprobante', None)
    if not comprobante:
        return redirect(url_for('carrito.catalogo'))
    return render_template('exito.html', comprobante=comprobante)