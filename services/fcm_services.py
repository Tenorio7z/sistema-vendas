import os
import json
import firebase_admin
from firebase_admin import credentials, messaging


# Inicializa uma única vez
if not firebase_admin._apps:

    if os.getenv("FIREBASE_CREDENTIALS"):
        cred_dict = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
        cred = credentials.Certificate(cred_dict)
    else:
        cred = credentials.Certificate("firebase_key.json")

    firebase_admin.initialize_app(cred)


def enviar_notificacao(token, titulo, mensagem):
    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=titulo,
                body=mensagem
            ),
            token=token
        )

        response = messaging.send(message)

        print("PUSH ENVIADO:", response)

        return response

    except Exception as e:
        print("ERRO FCM:", e)
        return None