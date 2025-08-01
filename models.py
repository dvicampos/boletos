from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    edad = db.Column(db.Integer)
    telefono = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120))  # NUEVO
    ciudad = db.Column(db.String(100))  # NUEVO
    plan_pago = db.Column(db.String(20))  # semanal, quincenal, mensual, contado
    estado = db.Column(db.String(20), default='vigente')  # vigente, moroso, cancelado

    pagos = db.relationship('Pago', backref='usuario', lazy=True)


class Evento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    lugar = db.Column(db.String(150), nullable=False)
    asientos = db.Column(db.Text, nullable=True)  # separados por coma
    imagen_asientos = db.Column(db.String(255), nullable=True)
    precios_por_zona = db.Column(db.Text)  # JSON como: {"A": 500, "B": 300}

    pagos = db.relationship('Pago', backref='evento', lazy=True)
    portada = db.Column(db.String(255), nullable=True)  # Imagen de cartel promocional
    descripcion = db.Column(db.Text, nullable=True)  # Detalles generales del evento
    latitud = db.Column(db.Float)
    longitud = db.Column(db.Float)


# parcialidad
class PlanParcialidad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # contado, mensual, quincenal, semanal
    numero_parcialidades = db.Column(db.Integer, nullable=False)
    dias_entre_pagos = db.Column(db.Integer)
    incluye_comision = db.Column(db.Boolean, default=False)
    porcentaje_comision = db.Column(db.Float, default=0.0)
    descripcion = db.Column(db.Text)

    pagos = db.relationship('Pago', backref='plan_parcialidad', lazy=True)

class Pago(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento.id'), nullable=False)
    asiento = db.Column(db.String(50), nullable=False)
    fecha_pago = db.Column(db.DateTime, default=datetime.utcnow)
    monto = db.Column(db.Float, nullable=False)  # Total a pagar
    abonado = db.Column(db.Float, nullable=True)  # Lo que pagó en este pago

    confirmado = db.Column(db.Boolean, default=False)

    plan_parcialidad_id = db.Column(db.Integer, db.ForeignKey('plan_parcialidad.id'), nullable=True)

    numero_parcialidad = db.Column(db.Integer)  # Ej: 1, 2, 3
    total_parcialidades = db.Column(db.Integer)  # Ej: 4
    estatus_pago = db.Column(db.String(20), default='pendiente')  # pendiente, pagado, vencido
    notas = db.Column(db.Text)


class Recordatorio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('evento.id', ondelete='CASCADE'), nullable=False)
    fecha_recordatorio = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(20))
    enviado = db.Column(db.Boolean, default=False)

class AdminUser(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    reset_token = db.Column(db.String(100), nullable=True)

    def set_password(self, password):
        from flask_bcrypt import generate_password_hash
        self.password_hash = generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        from flask_bcrypt import check_password_hash
        return check_password_hash(self.password_hash, password)