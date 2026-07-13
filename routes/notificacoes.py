from flask import *
from database import conectar, criar_cursor

def registrar_rotas(app):

    @app.route("/notificacoes")
    def notificacoes():

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute("""

        SELECT *

        FROM notificacoes

        ORDER BY id DESC

        LIMIT 100

        """)

        notificacoes = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template(
            "notificacoes.html",
            notificacoes=notificacoes
        )


    @app.route("/api/notificacoes")
    def api_notificacoes():

        if not session.get("logado") or not session.get("empresa_id"):
            return jsonify([]), 401

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute("""

        SELECT *

        FROM notificacoes

        WHERE empresa_id = %s

        ORDER BY id DESC

        LIMIT 1

        """,
        (
            session["empresa_id"],
        ))

        notificacoes = cursor.fetchall()

        cursor.close()
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
