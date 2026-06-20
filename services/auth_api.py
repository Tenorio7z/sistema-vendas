from flask import request
from database import conectar
from datetime import datetime


def validar_token():

    token = request.headers.get(
        "Authorization"
    )

    if not token:
        return None

    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT *

    FROM api_tokens

    WHERE token = ?

    """,

    (
        token,
    ))

    resultado = cursor.fetchone()

    if not resultado:

        conn.close()
        return None

    expira_em = datetime.fromisoformat(
    resultado["expira_em"]
    )

    if datetime.now() > expira_em:

        cursor.execute("""

        DELETE FROM api_tokens

        WHERE id = ?

        """,

        (
            resultado["id"],
        ))

        conn.commit()
        conn.close()

        return None
    
    cursor.execute("""

    SELECT *

    FROM usuarios

    WHERE id = ?

    """,

    (
        resultado["usuario_id"],
    ))

    usuario = cursor.fetchone()

    conn.close()

    return usuario