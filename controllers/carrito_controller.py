import io
import pandas as pd
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.producto_model import ProductoModel
from controllers.auth_controller import role_required

carrito_bp = Blueprint('carrito', __name__)

@carrito_bp.route('/')
def catalogo():
    productos = ProductoModel.obtener_todos()
    return render_template('productos.html', productos=productos)

@carrito_bp.route('/carrito')
def ver_carrito():
    carrito = session.get('carrito', {})
    items = []
    total = 0.0

    if carrito:
        ids = [int(pid) for pid in carrito.keys()]
        productos = ProductoModel.obtener_por_lista_ids(ids)
        for prod in productos:
            cant = carrito.get(str(prod['id']), 0)
            subtotal = float(prod['precio']) * cant
            total += subtotal
            items.append({
                'id': prod['id'],
                'nombre': prod['nombre'],
                'precio': float(prod['precio']),
                'stock': prod['stock'],
                'imagen': prod.get('imagen', ''),
                'cantidad': cant,
                'subtotal': round(subtotal, 2)
            })

    return render_template('carrito.html', items=items, total=round(total, 2))

@carrito_bp.route('/carrito/agregar/<int:producto_id>', methods=['POST'])
def agregar(producto_id):
    try:
        cantidad = int(request.form.get('cantidad', 1))
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

    motivo = request.form.get('motivo', 'Reposición manual').strip()
    usuario_id = session.get('usuario_id')

    if cantidad <= 0:
        flash("Ingresa una cantidad válida a reponer.", "warning")
    else:
        exito, mensaje = ProductoModel.reabastecer_stock(producto_id, cantidad, usuario_id=usuario_id, motivo=motivo)
        if exito:
            flash(f"Stock reabastecido (+{cantidad} unidades).", "success")
        else:
            flash(f"Error: {mensaje}", "danger")

    # Si viene desde la vista de inventario, redirigir a ella
    next_url = request.referrer or url_for('carrito.catalogo')
    return redirect(next_url)

@carrito_bp.route('/producto/actualizar-precio/<int:producto_id>', methods=['POST'])
@role_required('admin')
def actualizar_precio(producto_id):
    try:
        nuevo_precio = float(request.form.get('nuevo_precio', 0))
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

    next_url = request.referrer or url_for('carrito.catalogo')
    return redirect(next_url)

# --- REPOSITORIO DE STOCK (PANEL DE INVENTARIO) ---
@carrito_bp.route('/bodega/inventario')
@role_required('admin', 'bodega')
def inventario():
    productos = ProductoModel.obtener_todos()
    return render_template('inventario.html', productos=productos)

# --- HISTÓRICO DE MOVIMIENTOS ---
@carrito_bp.route('/bodega/movimientos')
@role_required('admin', 'bodega')
def movimientos():
    lista_movimientos = ProductoModel.obtener_movimientos(limite=100)
    return render_template('movimientos.html', movimientos=lista_movimientos)



 # --- PANEL DE REPORTERÍA Y GRÁFICOS ---
@carrito_bp.route('/bodega/reportes')
@role_required('admin', 'bodega')
def reportes():
    resumen_tipo, top_productos = ProductoModel.obtener_resumen_movimientos()
    return render_template(
        'reportes.html',
        resumen_tipo=resumen_tipo,
        top_productos=top_productos
    )

# --- EXPORTAR A EXCEL ---
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

# --- EXPORTAR A PDF ---
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