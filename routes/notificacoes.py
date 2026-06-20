from flask import *
from database import conectar

def registrar_rotas(app):

    @app.route("/notificacoes")
    def notificacoes():

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT *

        FROM notificacoes

        ORDER BY id DESC

        LIMIT 100

        """)

        notificacoes = cursor.fetchall()

      
        conn.close()

        return render_template(
            "notificacoes.html",
            notificacoes=notificacoes
        )


    @app.route("/api/notificacoes")
    def api_notificacoes():

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT *

        FROM notificacoes

        WHERE empresa_id = ?

        ORDER BY id DESC

        LIMIT 20

        """,
        (
            session["empresa_id"],
        ))

        notificacoes = cursor.fetchall()

        conn.close()

        resultado = []

        for n in notificacoes:

            resultado.append({

                "funcionario": n["funcionario"],
                "produto": n["produto"],
                "valor": n["valor"],
                "hora": n["data"]

            })

        response = jsonify(resultado)

        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response