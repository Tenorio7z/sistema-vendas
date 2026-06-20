from flask import *

def registrar_rotas(app):

    @app.route("/planos")
    def planos():

        if not session.get("logado"):
            return redirect("/")

        return render_template(
            "planos.html"
        )