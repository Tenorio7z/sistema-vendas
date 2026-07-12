import os
import json
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging


FCM_DISPONIVEL = False


def _inicializar_firebase():
    global FCM_DISPONIVEL

    if firebase_admin._apps:
        FCM_DISPONIVEL = True
        return

    try:
        credencial_json = os.getenv("FIREBASE_CREDENTIALS")

        if credencial_json:
            credencial = credentials.Certificate(
                json.loads(credencial_json)
            )
        else:
            caminho = Path("firebase_key.json")

            if not caminho.is_file():
                print(
                    "FCM desativado: firebase_key.json não encontrado."
                )
                return

            credencial = credentials.Certificate(str(caminho))

        firebase_admin.initialize_app(credencial)
        FCM_DISPONIVEL = True

    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        print("FCM desativado: credencial inválida:", erro)
    except Exception as erro:
        print("FCM desativado: falha na inicialização:", erro)


_inicializar_firebase()


def enviar_notificacao(token, titulo, mensagem):
    if not FCM_DISPONIVEL or not token:
        return None

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
