from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from models import db, Recordatorio, Usuario, Evento
from whatsapp_utils import enviar_whatsapp
from flask import current_app

def enviar_recordatorios(app):
    with app.app_context():
        hoy = datetime.now().date()
        print(f"🕒 Ejecutando recordatorios para {hoy}...")

        recordatorios = Recordatorio.query.filter_by(enviado=False, fecha_recordatorio=hoy).all()
        print(f"🔍 Recordatorios pendientes encontrados: {len(recordatorios)}")

        for r in recordatorios:
            usuario = Usuario.query.get(r.usuario_id)
            evento = Evento.query.get(r.evento_id)

            if not usuario or not evento:
                print(f"❌ Usuario o evento no encontrado para Recordatorio ID {r.id}")
                continue

            print(f"➡️ Procesando recordatorio ({r.tipo}) para {usuario.nombre} - {usuario.telefono}")

            try:
                if r.tipo == "evento":
                    mensaje = (
                        f"🎉 ¡Hola {usuario.nombre}!\n\n"
                        f"⏰ Recuerda que mañana es el concierto *{evento.nombre}* en {evento.lugar}.\n"
                        f"🗓️ Fecha: {evento.fecha.strftime('%d/%m/%Y')}\n\n"
                        f"🎟️ ¡Lleva tu boleto y disfruta! 🎶"
                    )

                elif r.tipo == "pago":
                    mensaje = (
                        f"💸 Hola {usuario.nombre},\n\n"
                        f"📅 Hoy te toca realizar un *pago parcial* para el evento *{evento.nombre}*.\n"
                        f"🔔 {r.notas or 'Mantente al corriente para conservar tu asiento.'}"
                    )
                else:
                    print(f"⚠️ Tipo de recordatorio desconocido: {r.tipo}")
                    continue

                enviar_whatsapp(usuario.telefono, mensaje)
                print(f"✅ Mensaje enviado a {usuario.telefono}")

                r.enviado = True
                db.session.add(r)

            except Exception as e:
                print(f"❌ Error al enviar recordatorio a {usuario.telefono}: {e}")
                continue

        db.session.commit()
        print("🟢 Todos los recordatorios procesados correctamente ✅")

def iniciar_scheduler(app):
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=lambda: enviar_recordatorios(app), trigger="cron", hour=12, minute=19)  # Ajusta la hora aquí
    scheduler.start()
    print("📅 Scheduler iniciado para enviar recordatorios diarios.")

# from apscheduler.schedulers.background import BackgroundScheduler
# from datetime import datetime
# from models import db, Recordatorio, Usuario, Evento
# from whatsapp_utils import enviar_whatsapp
# from flask import current_app

# def enviar_recordatorios(app):
#     with app.app_context():
#         hoy = datetime.now().date()
#         print(f"🕒 Ejecutando recordatorios para {hoy}...")

#         recordatorios = Recordatorio.query.filter_by(enviado=False, fecha_recordatorio=hoy).all()
#         print(f"🔍 Recordatorios encontrados: {len(recordatorios)}")

#         for r in recordatorios:
#             usuario = Usuario.query.get(r.usuario_id)
#             evento = Evento.query.get(r.evento_id)
#             print(f"➡️ Procesando recordatorio: {r.tipo} para {usuario.nombre} - {usuario.telefono}")

#             if not usuario or not evento:
#                 print("❌ Usuario o evento no encontrado.")
#                 continue

#             if r.tipo == "evento":
#                 mensaje = (
#                     f"🎉 ¡Hola {usuario.nombre}!\n\n"
#                     f"⏰ Recuerda que mañana es el concierto *{evento.nombre}* en {evento.lugar}.\n"
#                     f"Te esperamos el {evento.fecha.strftime('%d/%m/%Y')}.\n\n"
#                     f"🎟️ ¡Lleva tu boleto y disfruta!"
#                 )
#             elif r.tipo == "pago":
#                 mensaje = (
#                     f"💸 Hola {usuario.nombre}, recuerda que hoy tienes que hacer un pago "
#                     f"para el evento *{evento.nombre}*. Mantente al corriente para no perder tu asiento. 🎫"
#                 )
#             else:
#                 print("⚠️ Tipo de recordatorio no válido.")
#                 continue

#             print(f"📤 Enviando mensaje a {usuario.telefono}...")
#             enviar_whatsapp(usuario.telefono, mensaje)
#             print("✅ Mensaje enviado")

#             r.enviado = True
#             db.session.add(r)

#         db.session.commit()
#         print("🟢 Todos los recordatorios procesados")


# def iniciar_scheduler(app):
#     scheduler = BackgroundScheduler()
#     scheduler.add_job(func=lambda: enviar_recordatorios(app), trigger="cron", hour=11, minute='25')  # o la hora que pongas
#     scheduler.start()
