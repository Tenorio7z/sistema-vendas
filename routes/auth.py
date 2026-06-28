from flask import *

from database import conectar
import psycopg2.extras

from werkzeug.security import (
    check_password_hash
)

def registrar_rotas(app):

    @app.route("/", methods=["GET", "POST"])
    def login():

        if request.method == "POST":

            usuario = request.form["usuario"]
            senha = request.form["senha"]

            conn = conectar()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""

            SELECT *

            FROM usuarios

            WHERE usuario = %s

            """, (usuario,))

            user = cursor.fetchone()
            
            
            empresa = None
            
            
            if user:

                if user.get("nivel") != "master":
                    if user.get("status") == "bloqueado":
                        conn.close()
                        flash("Usuário bloqueado, consulte o suporte.", "erro")
                        return redirect("/")

                if check_password_hash(
                    user["senha"],
                    senha
                ):

                    cursor.execute("""

                    SELECT *

                    FROM empresa

                    WHERE id = %s

                    """, (

                        user["empresa_id"],

                    ))

                    empresa = cursor.fetchone()

                    session["empresa_id"] = user["empresa_id"]
                    session["nivel"] = user["nivel"]
                    session["logado"] = True
                    session["usuario"] = user["usuario"]
                    session["usuario_id"] = user["id"]

                    if empresa:
                        session["plano"] = empresa["plano"]
                    else:
                        session["plano"] = "comum"

                    conn.close()
                  
                    
                    return redirect("/dashboard")

            conn.close()

            flash(
                "Usuário ou senha incorretos",
                "erro"
            )

        return render_template(
            "login.html"
        )



    @app.route("/logout")
    def logout():

        session.clear()

        return redirect("/")