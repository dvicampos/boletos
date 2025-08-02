from app import db
from models import MetodoPago

metodos = [
    MetodoPago(nombre="Efectivo", porcentaje_comision=0.0),
    MetodoPago(nombre="Transferencia", porcentaje_comision=4.9),
    MetodoPago(nombre="Tarjeta", porcentaje_comision=4.9),
    MetodoPago(nombre="MercadoPago", porcentaje_comision=4.9),
    MetodoPago(nombre="PayPal", porcentaje_comision=4.9),
]

db.session.bulk_save_objects(metodos)
db.session.commit()

print("✅ Métodos de pago insertados correctamente.")
