from flask import request
from database import conectar, criar_cursor
from datetime import datetime


def validar_token():

    token = request.headers.get(
        "Authorization"
    )

    if not token:
        return None

    conn = conectar()
    cursor = criar_cursor(conn)

    cursor.execute("""

    SELECT *

    FROM api_tokens

    WHERE token = %s

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

        WHERE id = %s

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

    WHERE id = %s

    """,

    (
        resultado["usuario_id"],
    ))

    usuario = cursor.fetchone()

    conn.close()

    return usuario