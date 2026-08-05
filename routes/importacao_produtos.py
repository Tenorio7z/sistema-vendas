import secrets

from flask import flash, redirect, render_template, request, session, url_for

from services.importacao_produtos_service import ImportacaoProdutosService


def registrar_rotas(app):
    @app.route("/produtos/importar", methods=["GET", "POST"])
    def importar_produtos():
        if not session.get("logado"):
            return redirect("/")
        if not session.get("empresa_id"):
            flash("Empresa não identificada.", "erro")
            return redirect("/produtos")

        previa = None
        if request.method == "POST":
            arquivo = request.files.get("arquivo")
            try:
                if not arquivo or not arquivo.filename:
                    raise ValueError("Selecione uma planilha.")
                resultado = ImportacaoProdutosService.analisar(arquivo.filename, arquivo.read())
                token = secrets.token_urlsafe(24)
                ImportacaoProdutosService.salvar_temporario(token, resultado)
                session["token_importacao_produtos"] = token
                previa = resultado
                previa["token"] = token
            except ValueError as erro:
                flash(str(erro), "erro")
        return render_template("importacao_produtos.html", previa=previa)

    @app.post("/produtos/importar/confirmar")
    def confirmar_importacao_produtos():
        if not session.get("logado") or not session.get("empresa_id"):
            return redirect("/")
        token = request.form.get("token", "")
        if not token or token != session.get("token_importacao_produtos"):
            flash("Prévia inválida ou expirada.", "erro")
            return redirect(url_for("importar_produtos"))
        try:
            previa = ImportacaoProdutosService.carregar_temporario(token)
            resumo = ImportacaoProdutosService.importar(
                session["empresa_id"], previa["produtos"], request.form.get("estrategia", "atualizar")
            )
            ImportacaoProdutosService.remover_temporario(token)
            session.pop("token_importacao_produtos", None)
            flash(
                f"Importação concluída: {resumo['inseridos']} novos, "
                f"{resumo['atualizados']} atualizados e {resumo['ignorados']} ignorados.",
                "sucesso",
            )
            return redirect("/produtos")
        except (ValueError, OSError) as erro:
            flash(str(erro), "erro")
            return redirect(url_for("importar_produtos"))
