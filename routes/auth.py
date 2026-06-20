from flask import *

from database import conectar

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
            cursor = conn.cursor()

            cursor.execute("""

            SELECT *

            FROM usuarios

            WHERE usuario = ?

            """, (usuario,))

            user = cursor.fetchone()
            
            
            empresa = None
            
            if user:

                cursor.execute("""

                SELECT plano

                FROM empresa

                WHERE id = ?

                """, (user["empresa_id"],))

                empresa = cursor.fetchone() 
            
    

            if user:

                if user["status"] == "bloqueado":

                    conn.close()

                    flash(
                        "Usuário bloqueado, consulte o suporte.",
                        "erro"
                    )

                    return redirect("/")

                if check_password_hash(
                    user["senha"],
                    senha
                ):

                    cursor.execute("""

                    SELECT *

                    FROM empresa

                    WHERE id = ?

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