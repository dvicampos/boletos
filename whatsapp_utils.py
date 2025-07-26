# whatsapp_utils.py

# from twilio.rest import Client
# from flask import current_app

# def enviar_whatsapp(telefono, mensaje):
#     client = Client(
#         current_app.config['TWILIO_ACCOUNT_SID'],
#         current_app.config['TWILIO_AUTH_TOKEN']
#     )
#     from_number = current_app.config['TWILIO_WHATSAPP_NUMBER']
#     to_number = f"whatsapp:+52{telefono}" if not telefono.startswith("+") else f"whatsapp:{telefono}"

#     print(f"📲 Preparando mensaje para {to_number}...")

#     try:
#         client.messages.create(
#             body=mensaje,
#             from_=from_number,
#             to=to_number
#         )
#         print("✅ WhatsApp enviado correctamente")
#     except Exception as e:
#         print("❌ Error al enviar WhatsApp:", repr(e))


# whatsapp_utils.py

from twilio.rest import Client
from flask import current_app

def normalizar_numero(telefono):
    """
    Normaliza el número a formato E.164 para Twilio WhatsApp.
    Si es de México y no tiene prefijo, se le antepone +521 (sandbox).
    """
    numero = telefono.strip().replace(" ", "").replace("-", "")

    if numero.startswith("+"):
        return f"whatsapp:{numero}"
    elif numero.startswith("52"):
        return f"whatsapp:+{numero}"
    elif numero.startswith("1"):
        return f"whatsapp:+{numero}"
    else:
        # Supone número nacional sin prefijo internacional (ej. 2463095291)
        return f"whatsapp:+521{numero}"  # +521 es requerido en sandbox para México

def enviar_whatsapp(telefono, mensaje):
    """
    Envía un mensaje de WhatsApp usando Twilio y muestra logs detallados.
    """
    try:
        client = Client(
            current_app.config['TWILIO_ACCOUNT_SID'],
            current_app.config['TWILIO_AUTH_TOKEN']
        )
        from_number = current_app.config['TWILIO_WHATSAPP_NUMBER']
        to_number = normalizar_numero(telefono)

        print("📲 Enviando WhatsApp...")
        print(f"   🔸 De: {from_number}")
        print(f"   🔹 Para: {to_number}")
        print(f"   ✉️  Mensaje: {mensaje}")

        message = client.messages.create(
            body=mensaje,
            from_=from_number,
            to=to_number
        )

        print("✅ WhatsApp enviado correctamente.")
        print(f"   🆔 SID del mensaje: {message.sid}")

    except Exception as e:
        print("❌ Error al enviar WhatsApp:", repr(e))
