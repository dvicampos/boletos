from flask import Flask, render_template, request, redirect
from db import init_db
from models import db, Usuario, Evento, Pago, Recordatorio, PlanParcialidad
from whatsapp_bot import bot_bp
from reminders import iniciar_scheduler
from flask_login import LoginManager
from flask_mail import Mail
from models import AdminUser
from flask import session, flash, url_for, render_template
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from flask_migrate import Migrate
import os
from werkzeug.utils import secure_filename
import json
from reminders import iniciar_scheduler
from datetime import datetime, timedelta
from sqlalchemy import text
from datetime import date
from datetime import datetime
from flask import request, send_file
from sqlalchemy import func, and_, or_
from datetime import date, timedelta, datetime
import pandas as pd
import io

login_manager = LoginManager()
mail = Mail()

app = Flask(__name__)
login_manager.init_app(app)
init_db(app)
mail.init_app(app)
migrate = Migrate(app, db)

app.config['SECRET_KEY'] = 'clave-super-secreta'
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'dvicamp@gmail.com'
app.config['MAIL_PASSWORD'] = 'pwsd gwrz lzdi cyzv'

# twilio
app.config['TWILIO_ACCOUNT_SID'] = 'AC411c94cb166377f45f82a2898d28a173'
app.config['TWILIO_AUTH_TOKEN'] = 'b9d6a45fd9198c08ed06c029432ff5e1'
app.config['TWILIO_WHATSAPP_NUMBER'] = 'whatsapp:+14155238886'

# carpetas 

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static/uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Máx 5 MB
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# ----------------------------
# CRUD PAGOS DE BOLETOS
# ----------------------------

from whatsapp_utils import enviar_whatsapp
import json
app.jinja_env.filters['cargar_json'] = lambda val: json.loads(val or "{}")

@app.route('/pagos', methods=['GET', 'POST'])
@login_required
def registrar_pagos():
    eventos = Evento.query.all()
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    planes = PlanParcialidad.query.all()
    telefono_prellenado = request.args.get('telefono', '')

    if request.method == 'POST':
        evento_id = request.form.get('evento_id')
        telefono = request.form.get('telefono') or request.form.get('telefono_hidden')
        monto = request.form.get('monto')
        abonado = request.form.get('abonado')
        asientos_seleccionados = request.form.getlist('asientos')
        plan_id = request.form.get('plan_parcialidad_id')  # NUEVO
        notas = request.form.get("notas")
        evento = Evento.query.get(int(evento_id)) if evento_id else None
        plan = PlanParcialidad.query.get(plan_id) if plan_id else None

        try:
            abonado_float = float(abonado)
            monto_float = float(monto)
        except (ValueError, TypeError):
            abonado_float = 0.0
            monto_float = 0.0

        estatus = 'liquidado' if abonado_float >= monto_float else 'parcial' if abonado_float > 0 else 'pendiente'

        errores = []
        if not telefono:
            errores.append("📱 Teléfono no seleccionado.")
        if not monto:
            errores.append("💰 Monto no ingresado.")
        if not evento:
            errores.append("🎤 Evento no válido.")
        if not asientos_seleccionados:
            errores.append("🪑 No se seleccionaron asientos.")

        if errores:
            for e in errores:
                flash(e)
            return render_template('pagos/pagos.html', eventos=eventos, evento=evento, usuarios=usuarios, telefono=telefono, planes=planes)

        usuario = Usuario.query.filter_by(telefono=telefono).first()
        if not usuario:
            flash(f"ℹ️ El teléfono {telefono} no está registrado. Regístralo primero.")
            return redirect(url_for('registrar_usuario', telefono=telefono))

        disponibles = evento.asientos.split(', ')
        if not all(a in disponibles for a in asientos_seleccionados):
            flash("❌ Uno o más asientos ya no están disponibles.")
            return render_template('pagos/pagos.html', eventos=eventos, evento=evento, usuarios=usuarios, telefono=telefono, planes=planes)

        monto_total = float(monto)
        pago_unitario_total = monto_total / len(asientos_seleccionados)

        recordatorios_generados = []

        # 🧾 Crear pagos con o sin plan
        for asiento in asientos_seleccionados:
            if plan and plan.numero_parcialidades > 1:
                monto_con_comision = pago_unitario_total * (1 + plan.porcentaje_comision) if plan.incluye_comision else pago_unitario_total

                for i in range(plan.numero_parcialidades):
                    fecha_pago = datetime.now() + timedelta(days=i * plan.dias_entre_pagos)
                    pago = Pago(
                        usuario_id=usuario.id,
                        evento_id=evento.id,
                        asiento=asiento,
                        fecha_pago=fecha_pago,
                        monto=round(monto_con_comision, 2),
                        abonado=(abonado_float / len(asientos_seleccionados)) if i == 0 else 0,
                        confirmado=(i == 0),
                        tipo_pago=plan.tipo,
                        parcialidad=f"{i+1} de {plan.numero_parcialidades}",
                        notas=notas if i == 0 else "",
                        estatus_pago='parcial' if i == 0 else 'pendiente',
                        plan_parcialidad_id=plan.id,
                        numero_parcialidad=i+1,
                        total_parcialidades=plan.numero_parcialidades
                    )
                    db.session.add(pago)

                    if i == 0:
                        disponibles.remove(asiento)

                    if i > 0:
                        fecha_r = fecha_pago.date()
                        recordatorios_generados.append((fecha_r, monto_con_comision))
                        db.session.add(Recordatorio(
                            usuario_id=usuario.id,
                            evento_id=evento.id,
                            fecha_recordatorio=fecha_r,
                            tipo="pago",
                            enviado=False,
                            notas=f"Pago {i+1} de {plan.numero_parcialidades} - Monto ${monto_con_comision:.2f}"
                        ))
            else:
                pago = Pago(
                    usuario_id=usuario.id,
                    evento_id=evento.id,
                    asiento=asiento,
                    fecha_pago=datetime.now(),
                    monto=pago_unitario_total,
                    abonado=abonado_float / len(asientos_seleccionados),
                    confirmado=True,
                    tipo_pago='contado',
                    parcialidad='1 de 1',
                    notas=notas,
                    estatus_pago=estatus,
                    numero_parcialidad=1,
                    total_parcialidades=1
                )
                db.session.add(pago)
                disponibles.remove(asiento)

        evento.asientos = ', '.join(disponibles)
        db.session.commit()

        # ✅ Verificar si ya liquidó
        pagos_usuario = Pago.query.filter_by(usuario_id=usuario.id, evento_id=evento.id).all()
        total_abonado = sum(p.abonado for p in pagos_usuario)
        if total_abonado >= monto_total:
            for p in pagos_usuario:
                p.estatus_pago = 'liquidado'
            db.session.commit()

        # 📅 Recordatorio antes del evento
        recordatorio_evento = Recordatorio(
            usuario_id=usuario.id,
            evento_id=evento.id,
            fecha_recordatorio=evento.fecha - timedelta(days=1),
            tipo="evento",
            enviado=False
        )
        db.session.add(recordatorio_evento)
        db.session.commit()

        # 📲 WhatsApp resumen
        try:
            mensaje_resumen = f"🎟️ *Resumen de tu compra para {evento.nombre}*\n"
            mensaje_resumen += f"👤 {usuario.nombre}\n"
            mensaje_resumen += f"🎫 Asientos: {', '.join(asientos_seleccionados)}\n"
            mensaje_resumen += f"💰 Monto total: ${monto_total:.2f}\n"
            mensaje_resumen += f"📅 Tipo de pago: *{plan.nombre if plan else 'Contado'}*\n"
            mensaje_resumen += f"💸 Abonado: ${abonado_float:.2f}\n"

            if recordatorios_generados:
                mensaje_resumen += "\n📅 Próximos pagos:\n"
                for fecha, monto in recordatorios_generados:
                    mensaje_resumen += f"• {fecha.strftime('%d/%m/%Y')} → ${monto:.2f}\n"

            mensaje_resumen += "\n✅ ¡Gracias por tu compra! Recibirás recordatorios automáticos."
            enviar_whatsapp(usuario.telefono, mensaje_resumen)

        except Exception as e:
            print("❌ Error al enviar resumen por WhatsApp:", e)

        flash(f"✅ Pago registrado para {len(asientos_seleccionados)} asiento(s).")
        return redirect(url_for('registrar_pagos'))

    return render_template(
        'pagos/pagos.html',
        eventos=eventos,
        evento=None,
        usuarios=usuarios,
        telefono=telefono_prellenado,
        planes=planes
    )


@app.route('/pagos/listar')
@login_required
def listar_pagos():
    pagos = Pago.query.order_by(Pago.fecha_pago.desc()).all()
    return render_template('pagos/listar.html', pagos=pagos)

@app.route('/pagos/<int:pago_id>')
@login_required
def detalle_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    return render_template('pagos/detalle.html', pago=pago)

@app.route('/pagos/editar/<int:pago_id>', methods=['GET', 'POST'])
@login_required
def editar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    eventos = Evento.query.all()
    usuarios = Usuario.query.all()

    if request.method == 'POST':
        pago.monto = float(request.form['monto'])
        pago.asiento = request.form['asiento']
        pago.confirmado = 'confirmado' in request.form
        db.session.commit()
        flash("✅ Pago actualizado.")
        return redirect(url_for('listar_pagos'))

    return render_template('pagos/editar.html', pago=pago, eventos=eventos, usuarios=usuarios)

@app.route('/pagos/eliminar/<int:pago_id>', methods=['POST'])
@login_required
def eliminar_pago(pago_id):
    pago = Pago.query.get_or_404(pago_id)
    evento = Evento.query.get(pago.evento_id)

    if evento:
        # Convertir a lista
        disponibles = evento.asientos.split(', ') if evento.asientos else []
        # Evitar duplicados
        if pago.asiento not in disponibles:
            disponibles.append(pago.asiento)
            disponibles.sort()  # opcional, por orden

        evento.asientos = ', '.join(disponibles)

    db.session.delete(pago)
    db.session.commit()
    flash("🗑️ Pago eliminado y asiento liberado.")
    return redirect(url_for('listar_pagos'))


# ----------------------------
# CRUD CLIENTES USUARIOS
# ----------------------------

# 🟡 CREAR
@app.route("/registrar-usuario", methods=["GET", "POST"])
@login_required
def registrar_usuario():
    telefono = request.args.get("telefono", "")
    if request.method == "POST":
        nuevo = Usuario(
            nombre=request.form["nombre"],
            direccion=request.form["direccion"],
            edad=int(request.form["edad"]),
            telefono=request.form["telefono"],
            email=request.form["email"],
            ciudad=request.form["ciudad"],
            plan_pago=request.form["plan_pago"],
            estado="vigente"
        )
        db.session.add(nuevo)
        db.session.commit()
        flash("✅ Usuario registrado.")
        return redirect(url_for("listar_usuarios"))
    return render_template("usuarios/crear.html", telefono=telefono)


# 🟢 LISTADO
@app.route("/usuarios")
@login_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nombre).all()
    return render_template("usuarios/listar.html", usuarios=usuarios)

# 🟠 EDITAR
@app.route("/usuarios/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if request.method == "POST":
        usuario.nombre = request.form["nombre"]
        usuario.direccion = request.form["direccion"]
        usuario.edad = int(request.form["edad"])
        usuario.telefono = request.form["telefono"]
        usuario.email = request.form["email"]
        usuario.ciudad = request.form["ciudad"]
        usuario.plan_pago = request.form["plan_pago"]
        db.session.commit()
        flash("✅ Usuario actualizado.")
        return redirect(url_for("listar_usuarios"))
    return render_template("usuarios/editar.html", usuario=usuario)

# 🔴 ELIMINAR
@app.route("/usuarios/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash("🗑️ Usuario eliminado.")
    return redirect(url_for("listar_usuarios"))

# ----------------------------
# CRUD LOGEO
# ----------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = AdminUser(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Usuario registrado, inicia sesión.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = AdminUser.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("registrar_pagos"))
        flash("Credenciales inválidas")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/reset", methods=["GET", "POST"])
def reset_request():
    if request.method == "POST":
        email = request.form["email"]
        user = AdminUser.query.filter_by(email=email).first()
        if user:
            s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = s.dumps(email, salt='reset-salt')
            user.reset_token = token
            db.session.commit()

            msg = Message("Reestablece tu contraseña", sender="no-reply@credi.com", recipients=[email])
            reset_url = url_for('reset_token', token=token, _external=True)
            msg.body = f"Da clic aquí para restablecer tu contraseña:\n{reset_url}"
            mail.send(msg)
            flash("Correo enviado")
        else:
            flash("Correo no encontrado")
    return render_template("reset_request.html")

@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_token(token):
    s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='reset-salt', max_age=3600)
    except:
        flash("Token inválido o expirado")
        return redirect(url_for("reset_request"))

    user = AdminUser.query.filter_by(email=email).first()

    if request.method == "POST":
        new_pass = request.form["password"]
        user.set_password(new_pass)
        user.reset_token = None
        db.session.commit()
        flash("Contraseña restablecida, inicia sesión.")
        return redirect(url_for("login"))

    return render_template("reset_form.html")

# Agrega esto a tu app.py
from datetime import datetime

# ----------------------------
# CRUD CONCIERTOS
# ----------------------------
@app.route("/vista_eventos")
def vista_eventos():
    eventos = Evento.query.all()
    eventos_info = []

    for evento in eventos:
        total_asientos = len(evento.asientos.split(',')) if evento.asientos else 0
        boletos_vendidos = Pago.query.filter_by(evento_id=evento.id).count()

        zonas = []
        if evento.precios_por_zona:
            import json
            try:
                zonas = json.loads(evento.precios_por_zona).items()
            except:
                zonas = []

        eventos_info.append({
            "id": evento.id,
            "nombre": evento.nombre,
            "fecha": evento.fecha.strftime("%d/%m/%Y"),
            "lugar": evento.lugar,
            "asientos_totales": total_asientos,
            "boletos_vendidos": boletos_vendidos,
            "zonas": zonas,
            "portada": evento.portada
        })

    return render_template("eventos/vista_publica.html", eventos=eventos_info, year=datetime.now().year)

@app.route("/eventos")
@login_required
def listar_eventos():
    eventos = Evento.query.all()
    return render_template("eventos/listar.html", eventos=eventos)

@app.route("/eventos/nuevo", methods=["GET", "POST"])
@login_required
def crear_evento():
    if request.method == "POST":
        nombre = request.form['nombre']
        lugar = request.form['lugar']
        fecha = datetime.strptime(request.form['fecha'], "%Y-%m-%d")
        descripcion = request.form.get('descripcion', '')
        asientos = request.form['asientos']
        latitud = request.form.get('latitud')
        longitud = request.form.get('longitud')

        # Subida de imagen del cartel
        cartel_file = request.files.get('portada')
        portada_path = None
        if cartel_file and allowed_file(cartel_file.filename):
            filename = secure_filename("portada_" + cartel_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            cartel_file.save(filepath)
            portada_path = filename

        # Subida de mapa de asientos
        mapa_file = request.files.get('imagen_asientos')
        imagen_path = None
        if mapa_file and allowed_file(mapa_file.filename):
            filename = secure_filename("mapa_" + mapa_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            mapa_file.save(filepath)
            imagen_path = filename

        zonas = request.form.getlist('zona[]')
        precios = request.form.getlist('precio_zona[]')
        precios_dict = {}
        for zona, p in zip(zonas, precios):
            zona = zona.strip().upper()
            try:
                precios_dict[zona] = float(p)
            except ValueError:
                continue

        evento = Evento(
            nombre=nombre,
            lugar=lugar,
            fecha=fecha,
            descripcion=descripcion,
            asientos=asientos,
            imagen_asientos=imagen_path,
            portada=portada_path,
            precios_por_zona=json.dumps(precios_dict),
            latitud=latitud,
            longitud=longitud
        )

        db.session.add(evento)
        db.session.commit()
        flash("✅ Evento creado correctamente.")
        return redirect(url_for("listar_eventos"))

    return render_template("eventos/nuevo.html")

@app.route("/evento/<int:evento_id>")
def ver_evento(evento_id):
    evento = Evento.query.get_or_404(evento_id)

    zonas = json.loads(evento.precios_por_zona or "{}")
    asientos = evento.asientos.split(",") if evento.asientos else []

    return render_template("eventos/ver_evento.html", evento=evento, zonas=zonas, asientos=asientos)

@app.route("/eventos/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_evento(id):
    evento = Evento.query.get_or_404(id)

    if request.method == "POST":
        evento.nombre = request.form['nombre']
        evento.lugar = request.form['lugar']
        evento.fecha = datetime.strptime(request.form['fecha'], "%Y-%m-%d")
        evento.asientos = request.form['asientos']

        imagen_file = request.files.get('imagen_asientos')
        if imagen_file and allowed_file(imagen_file.filename):
            filename = secure_filename(imagen_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            imagen_file.save(filepath)
            evento.imagen_asientos = f"/static/uploads/{filename}"

        # Actualizar zonas
        zonas = request.form.getlist('zona[]')
        precios = request.form.getlist('precio_zona[]')
        precios_dict = {}
        for zona, p in zip(zonas, precios):
            zona = zona.strip().upper()
            try:
                precios_dict[zona] = float(p)
            except ValueError:
                continue
        evento.precios_por_zona = json.dumps(precios_dict)

        db.session.commit()
        flash("✅ Evento actualizado correctamente.")
        return redirect(url_for("listar_eventos"))

    return render_template("eventos/editar.html", evento=evento)


@app.route('/eventos/eliminar/<int:evento_id>', methods=['POST'])
@login_required
def eliminar_evento(evento_id):
    evento = Evento.query.get_or_404(evento_id)
    Recordatorio.query.filter_by(evento_id=evento.id).delete()
    Pago.query.filter_by(evento_id=evento.id).delete()
    db.session.delete(evento)
    db.session.commit()
    flash('🎤 Evento eliminado correctamente.')
    return redirect(url_for('listar_eventos'))


# ----------------------------
# CRUD DE PLANES DE PARCIALIDAD
# ----------------------------

@app.route("/planes", methods=["GET"])
@login_required
def listar_planes():
    planes = PlanParcialidad.query.all()
    return render_template("planes/listar.html", planes=planes)

@app.route("/planes/nuevo", methods=["GET", "POST"])
@login_required
def crear_plan():
    if request.method == "POST":
        nuevo = PlanParcialidad(
            nombre=request.form["nombre"],
            tipo=request.form["tipo"],
            numero_parcialidades=int(request.form["numero_parcialidades"]),
            dias_entre_pagos=int(request.form["dias_entre_pagos"]),
            incluye_comision='incluye_comision' in request.form,
            porcentaje_comision=float(request.form.get("porcentaje_comision", 0)),
            descripcion=request.form.get("descripcion", "")
        )
        db.session.add(nuevo)
        db.session.commit()
        flash("✅ Plan creado correctamente.")
        return redirect(url_for("listar_planes"))
    return render_template("planes/nuevo.html")

@app.route("/planes/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_plan(id):
    plan = PlanParcialidad.query.get_or_404(id)
    if request.method == "POST":
        plan.nombre = request.form["nombre"]
        plan.tipo = request.form["tipo"]
        plan.numero_parcialidades = int(request.form["numero_parcialidades"])
        plan.dias_entre_pagos = int(request.form["dias_entre_pagos"])
        plan.incluye_comision = 'incluye_comision' in request.form
        plan.porcentaje_comision = float(request.form.get("porcentaje_comision", 0))
        plan.descripcion = request.form.get("descripcion", "")
        db.session.commit()
        flash("✅ Plan actualizado.")
        return redirect(url_for("listar_planes"))
    return render_template("planes/editar.html", plan=plan)

@app.route("/planes/eliminar/<int:id>", methods=["POST"])
@login_required
def eliminar_plan(id):
    plan = PlanParcialidad.query.get_or_404(id)
    db.session.delete(plan)
    db.session.commit()
    flash("🗑️ Plan eliminado.")
    return redirect(url_for("listar_planes"))


from flask import request, send_file
from sqlalchemy import func, and_, or_
from datetime import date, timedelta, datetime
import pandas as pd
import io

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    # Filtros
    filtro = request.args.get('filtro', 'hoy')
    inicio = request.args.get('inicio')
    fin = request.args.get('fin')

    hoy = date.today()
    if filtro == 'semana':
        fecha_inicio = hoy - timedelta(days=7)
        fecha_fin = hoy
    elif filtro == 'mes':
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy
    elif filtro == 'rango' and inicio and fin:
        fecha_inicio = datetime.strptime(inicio, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fin, '%Y-%m-%d').date()
    else:
        fecha_inicio = hoy
        fecha_fin = hoy

    # Pagos filtrados
    pagos_filtrados = db.session.query(Pago, Usuario, Evento)\
        .join(Usuario, Pago.usuario_id == Usuario.id)\
        .join(Evento, Pago.evento_id == Evento.id)\
        .filter(Pago.fecha_pago >= fecha_inicio, Pago.fecha_pago <= fecha_fin).all()

    # Exportar a Excel si se pidió
    if request.args.get('excel') == '1':
        data = [
            [p.usuario.nombre, p.usuario.telefono, p.evento.nombre, p.fecha_pago.strftime('%Y-%m-%d'), p.monto, p.abonado]
            for p, _, _ in pagos_filtrados
        ]
        df = pd.DataFrame(data, columns=["Cliente", "Teléfono", "Evento", "Fecha", "Monto", "Abonado"])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Pagos')
        output.seek(0)
        return send_file(output, download_name="pagos_dashboard.xlsx", as_attachment=True)

    # Datos del dashboard
    recordatorios = db.session.execute(text("""
        SELECT tipo, enviado, COUNT(*) as total
        FROM Recordatorio
        GROUP BY tipo, enviado
    """)).fetchall()

    pagos_por_mes = db.session.execute(text("""
        SELECT TO_CHAR(fecha_pago, 'YYYY-MM') as mes, SUM(abonado) as total
        FROM Pago
        WHERE confirmado = TRUE
        GROUP BY mes
        ORDER BY mes
    """)).fetchall()

    total_ganado = db.session.query(func.sum(Pago.abonado)).filter(Pago.confirmado == True).scalar() or 0

    proxima_semana = hoy + timedelta(days=7)
    pagos_proximos = db.session.query(func.sum(Pago.monto))\
        .join(Recordatorio, and_(Recordatorio.usuario_id == Pago.usuario_id,
                                 Recordatorio.evento_id == Pago.evento_id))\
        .filter(Recordatorio.tipo == 'pago',
                Recordatorio.fecha_recordatorio >= hoy,
                Recordatorio.fecha_recordatorio <= proxima_semana,
                Recordatorio.enviado == False).scalar() or 0

    # Pagos vencidos porque el evento ya pasó y no se ha liquidado
    pagos_vencidos = db.session.execute(text("""
        SELECT u.nombre, u.telefono, e.nombre AS evento, e.fecha
        FROM Pago p
        JOIN Usuario u ON p.usuario_id = u.id
        JOIN Evento e ON p.evento_id = e.id
        WHERE p.abonado < p.monto AND e.fecha < :hoy
        ORDER BY e.fecha ASC
    """), {"hoy": hoy}).fetchall()


    boletos_vendidos = db.session.execute(text("""
        SELECT e.nombre, COUNT(p.id) as boletos, SUM(p.abonado) as total
        FROM Pago p
        JOIN Evento e ON p.evento_id = e.id
        WHERE p.confirmado = TRUE
        GROUP BY e.nombre
        ORDER BY boletos DESC
    """)).fetchall()

    eventos_no_liquidados = db.session.execute(text("""
        SELECT e.nombre, COUNT(p.id) as pendientes
        FROM Pago p
        JOIN Evento e ON p.evento_id = e.id
        WHERE p.abonado < p.monto
        GROUP BY e.nombre
        HAVING COUNT(p.id) > 0
        ORDER BY pendientes DESC
    """)).fetchall()

    # Top clientes por dinero abonado
    top_clientes = db.session.execute(text("""
        SELECT u.nombre, u.telefono, SUM(p.abonado) as total_abonado
        FROM Pago p
        JOIN Usuario u ON p.usuario_id = u.id
        GROUP BY u.nombre, u.telefono
        ORDER BY total_abonado DESC
        LIMIT 5
    """)).fetchall()

    return render_template('dashboard.html',
                           recordatorios=recordatorios,
                           pagos_por_mes=pagos_por_mes,
                           total_ganado=total_ganado,
                           pagos_proximos=pagos_proximos,
                           pagos_vencidos=pagos_vencidos,
                           boletos_vendidos=boletos_vendidos,
                           eventos_no_liquidados=eventos_no_liquidados,
                           top_clientes=top_clientes,
                           filtro=filtro,
                           fecha_inicio=fecha_inicio,
                           fecha_fin=fecha_fin)

iniciar_scheduler(app)
app.register_blueprint(bot_bp)

if __name__ == '__main__':
    app.run(debug=True)
