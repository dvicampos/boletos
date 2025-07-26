from models import Evento, Pago, Usuario  # Asegúrate que Pago y Usuario estén importados
from flask import Blueprint, request
from twilio.twiml.messaging_response import MessagingResponse
from models import Evento
import json
import re

bot_bp = Blueprint('bot_bp', __name__)

@bot_bp.route("/whatsapp/webhook", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "").lower()
    sender_phone = request.values.get("From", "").replace("whatsapp:", "")

    # ✅ Normalizar número si viene con +521
    if sender_phone.startswith("+521"):
        sender_phone = sender_phone.replace("+521", "")

    response = MessagingResponse()
    msg = response.message()

    print("🧾 Mensaje recibido:", incoming_msg)
    print("📱 Teléfono normalizado:", sender_phone)

    # 1️⃣ Mostrar conciertos
    if "concierto" in incoming_msg or "eventos" in incoming_msg:
        eventos = Evento.query.all()
        if not eventos:
            msg.body("🎤 No hay conciertos disponibles en este momento.")
        else:
            mensaje = "🎤 Próximos conciertos:\n\n"
            for e in eventos:
                mensaje += f"- {e.nombre} en {e.lugar}, el {e.fecha.strftime('%d/%m/%Y')}\n"
            msg.body(mensaje)

    # 2️⃣ Precios
    elif "precio" in incoming_msg:
        eventos = Evento.query.all()
        encontrado = False
        for e in eventos:
            if e.nombre.lower() in incoming_msg:
                try:
                    zonas = json.loads(e.precios_por_zona)
                    mensaje = f"💵 Precios por zona para *{e.nombre}*:\n"
                    for zona, precio in zonas.items():
                        mensaje += f"- {zona}: ${precio:.2f}\n"
                    msg.body(mensaje)
                except:
                    msg.body(f"💵 El precio general para *{e.nombre}* es ${e.precio:.2f}")
                encontrado = True
                break
        if not encontrado:
            msg.body("❌ No encontré el concierto que mencionas. Escribe 'conciertos' para ver la lista.")

    # 3️⃣ Asientos
    elif "asiento" in incoming_msg or "asientos" in incoming_msg:
        eventos = Evento.query.all()
        for e in eventos:
            if e.nombre.lower() in incoming_msg:
                msg.body(f"🎫 Asientos disponibles para *{e.nombre}*:\n{e.asientos}")
                return str(response)
        msg.body("❌ No encontré el concierto que mencionas. Escribe 'conciertos' para ver la lista.")

    # 4️⃣ Mis boletos
    elif "mis boletos" in incoming_msg or "mis tickets" in incoming_msg:
        usuario = Usuario.query.filter_by(telefono=sender_phone).first()
        if not usuario:
            msg.body("❌ No encontramos tu registro. Asegúrate de haber comprado boletos con este número.")
        else:
            pagos = Pago.query.filter_by(usuario_id=usuario.id).all()
            if not pagos:
                msg.body("🎫 No encontramos boletos registrados a tu nombre.")
            else:
                resumen = f"🎟️ Boletos de {usuario.nombre}:\n\n"
                for p in pagos:
                    evento = Evento.query.get(p.evento_id)
                    resumen += (
                        f"- {evento.nombre} en {evento.lugar}, {evento.fecha.strftime('%d/%m/%Y')}\n"
                        f"  Asiento: {p.asiento} | Monto: ${p.monto:.2f}\n"
                        f"  Tipo: {p.tipo_pago or 'contado'} | Confirmado: {'✅' if p.confirmado else '❌'}\n\n"
                    )
                msg.body(resumen)

    # 5️⃣ Ayuda
    elif "ayuda" in incoming_msg or "hola" in incoming_msg:
        msg.body(
            "👋 ¡Hola! Soy tu asistente de boletos.\n\n"
            "Puedes escribirme:\n"
            "• *conciertos* → ver la lista\n"
            "• *precio concierto* → precios por zona\n"
            "• *asientos concierto* → ver asientos disponibles\n"
            "• *mis boletos* → ver tus entradas\n"
            "• *ayuda* → mostrar este menú"
        )

    else:
        msg.body("❓ No entendí tu mensaje. Escribe 'ayuda' para ver lo que puedo hacer.")

    return str(response)

from twilio.rest import Client
from flask import current_app

def enviar_whatsapp(telefono, mensaje):
    client = Client(
        current_app.config['TWILIO_ACCOUNT_SID'],
        current_app.config['TWILIO_AUTH_TOKEN']
    )
    from_number = current_app.config['TWILIO_WHATSAPP_NUMBER']
    to_number = f"whatsapp:+52{telefono}" if not telefono.startswith("+") else f"whatsapp:{telefono}"

    try:
        client.messages.create(
            body=mensaje,
            from_=from_number,
            to=to_number
        )
    except Exception as e:
        print("❌ Error al enviar WhatsApp:", e)


# from flask import Blueprint, request
# from twilio.twiml.messaging_response import MessagingResponse
# from models import Evento
# import json
# import re

# bot_bp = Blueprint('bot_bp', __name__)

# @bot_bp.route("/whatsapp/webhook", methods=["POST"])
# def whatsapp_webhook():
#     incoming_msg = request.values.get("Body", "").lower()
#     response = MessagingResponse()
#     msg = response.message()

#     # 1️⃣ Lista de conciertos
#     if "concierto" in incoming_msg or "eventos" in incoming_msg:
#         eventos = Evento.query.all()
#         if not eventos:
#             msg.body("🎤 No hay conciertos disponibles en este momento.")
#         else:
#             mensaje = "🎤 Próximos conciertos:\n\n"
#             for e in eventos:
#                 mensaje += f"- {e.nombre} en {e.lugar}, el {e.fecha.strftime('%d/%m/%Y')}\n"
#             msg.body(mensaje)

#     # 2️⃣ Precios por zona
#     elif "precio" in incoming_msg:
#         conciertos = Evento.query.all()
#         encontrado = False
#         for e in conciertos:
#             if e.nombre.lower() in incoming_msg:
#                 try:
#                     zonas = json.loads(e.precios_por_zona)
#                     mensaje = f"💵 Precios por zona para *{e.nombre}*:\n"
#                     for zona, precio in zonas.items():
#                         mensaje += f"- {zona}: ${precio:.2f}\n"
#                     msg.body(mensaje)
#                 except:
#                     msg.body(f"💵 El precio general para *{e.nombre}* es ${e.precio:.2f}")
#                 encontrado = True
#                 break
#         if not encontrado:
#             msg.body("❌ No encontré el concierto que mencionas. Escribe 'conciertos' para ver la lista.")

#     # 3️⃣ Asientos disponibles
#     elif "asiento" in incoming_msg or "asientos" in incoming_msg:
#         conciertos = Evento.query.all()
#         encontrado = False
#         for e in conciertos:
#             if e.nombre.lower() in incoming_msg:
#                 msg.body(f"🎫 Asientos disponibles para *{e.nombre}*:\n{e.asientos}")
#                 encontrado = True
#                 break
#         if not encontrado:
#             msg.body("❌ No encontré el concierto que mencionas. Escribe 'conciertos' para ver la lista.")

#     # 4️⃣ Ayuda
#     elif "ayuda" in incoming_msg or "hola" in incoming_msg:
#         msg.body(
#             "👋 Hola! Puedes escribirme para:\n"
#             "• *conciertos* → ver la lista\n"
#             "• *precio nombre_del_concierto* → precios por zona\n"
#             "• *asientos nombre_del_concierto* → ver asientos disponibles\n"
#             "• *ayuda* → mostrar este menú"
#         )

#     # 5️⃣ Catch-all
#     else:
#         msg.body("❓ No entendí tu mensaje. Escribe 'ayuda' para ver lo que puedo hacer.")

#     return str(response)
