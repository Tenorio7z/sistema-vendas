from functools import wraps

from flask import flash, redirect, render_template, request, session, url_for

from services.filiais_service import FiliaisService


def _gerente(funcao):
    @wraps(funcao)
    def protegida(*args, **kwargs):
        if not session.get("logado"):
            return redirect("/")
        if session.get("nivel") not in ("gerente", "master"):
            flash("Apenas o gerente pode administrar filiais.", "erro")
            return redirect("/dashboard")
        return funcao(*args, **kwargs)
    return protegida


def registrar_rotas(app):
    @app.route("/filiais", methods=["GET", "POST"])
    @_gerente
    def filiais():
        empresa_id = session.get("empresa_id")
        if request.method == "POST":
            try:
                FiliaisService.criar(
                    empresa_id=empresa_id,
                    nome=request.form.get("nome"),
                    codigo=request.form.get("codigo"),
                    copiar_matriz=request.form.get("copiar_catalogo") == "1",
                    estoque_zerado=request.form.get("copiar_estoque") != "1",
                )
                flash("Filial criada com sucesso.", "sucesso")
            except Exception as erro:
                app.logger.exception("Erro ao criar filial")
                flash(str(erro), "erro")
            return redirect(url_for("filiais"))

        FiliaisService.garantir_matriz(empresa_id)
        return render_template(
            "filiais.html",
            filiais=FiliaisService.listar(empresa_id, somente_ativas=False),
        )

    @app.post("/filiais/<int:filial_id>/status")
    @_gerente
    def filial_status(filial_id):
        try:
            FiliaisService.alterar_status(
                session["empresa_id"],
                filial_id,
                request.form.get("ativa") == "1",
            )
            flash("Situação da filial atualizada.", "sucesso")
        except Exception as erro:
            flash(str(erro), "erro")
        return redirect(url_for("filiais"))

    @app.post("/filiais/<int:filial_id>/copiar-catalogo")
    @_gerente
    def copiar_catalogo_filial(filial_id):
        try:
            FiliaisService.copiar_catalogo(
                session["empresa_id"],
                filial_id,
                estoque_zerado=True,
            )
            flash("Catálogo da matriz disponibilizado na filial.", "sucesso")
        except Exception as erro:
            flash(str(erro), "erro")
        return redirect(url_for("filiais"))

    @app.post("/usuarios/<int:usuario_id>/filial")
    @_gerente
    def vincular_usuario_filial(usuario_id):
        from database import conectar, criar_cursor

        empresa_id = session["empresa_id"]
        filial_id = request.form.get("filial_id", type=int)
        filial = FiliaisService.obter(empresa_id, filial_id)
        if not filial or not filial.get("ativa"):
            flash("Selecione uma filial ativa.", "erro")
            return redirect("/perfis")

        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                UPDATE usuarios SET filial_id = %s
                WHERE id = %s AND empresa_id = %s AND nivel = 'funcionario'
                """,
                (filial_id, usuario_id, empresa_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("Funcionário não encontrado.")
            conn.commit()
            flash("Filial do funcionário atualizada.", "sucesso")
        except Exception as erro:
            conn.rollback()
            flash(str(erro), "erro")
        finally:
            cursor.close()
            conn.close()
        return redirect("/perfis")
