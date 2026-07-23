from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import (
    conectar,
    criar_cursor,
)

from services.onboarding_empresa_service import (
    OnboardingEmpresaErro,
    OnboardingEmpresaService,
)


def registrar_rotas(app):

    # =====================================================
    # FUNÇÕES INTERNAS
    # =====================================================

    def acesso_master():
        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "master":
            return redirect("/dashboard")

        return None

    def endereco_ip():
        encaminhado = request.headers.get(
            "X-Forwarded-For",
            "",
        )

        if encaminhado:
            return encaminhado.split(",")[0].strip()

        return request.remote_addr

    # =====================================================
    # PAINEL MASTER
    # =====================================================

    @app.route(
        "/admin",
        methods=["GET"],
    )
    def admin():

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            # ==========================================
            # EMPRESAS
            # ==========================================

            cursor.execute(
                """
                SELECT
                    usuarios.id,
                    usuarios.usuario,
                    usuarios.status,

                    empresa.nome,
                    empresa.plano,
                    empresa.emprestimos_ativo,
                    empresa.id AS empresa_id,

                    (
                        SELECT COUNT(*)

                        FROM produtos

                        WHERE produtos.empresa_id = empresa.id
                    ) AS total_produtos,

                    (
                        SELECT COUNT(*)

                        FROM vendas

                        WHERE vendas.empresa_id = empresa.id
                    ) AS total_vendas,

                    (
                        SELECT COUNT(*)

                        FROM usuarios u

                        WHERE u.empresa_id = empresa.id
                    ) AS total_usuarios

                FROM usuarios

                INNER JOIN empresa
                    ON usuarios.empresa_id = empresa.id

                WHERE usuarios.nivel = 'gerente'

                ORDER BY usuarios.id DESC
                """
            )

            empresas = cursor.fetchall() or []

            # ==========================================
            # ESTATÍSTICAS GERAIS
            # ==========================================

            total_empresas = len(empresas)

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM produtos
                """
            )

            total_produtos = (
                cursor.fetchone()["total"]
                or 0
            )

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM vendas
                """
            )

            total_vendas = (
                cursor.fetchone()["total"]
                or 0
            )

            cursor.execute(
                """
                SELECT COUNT(*) AS total

                FROM usuarios

                WHERE nivel = 'gerente'
                """
            )

            total_usuarios = (
                cursor.fetchone()["total"]
                or 0
            )

            # ==========================================
            # SOLICITAÇÕES DE ACESSO
            # ==========================================

            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'aguardando'
                    ) AS aguardando,

                    COUNT(*) FILTER (
                        WHERE status = 'em_analise'
                    ) AS em_analise,

                    COUNT(*) FILTER (
                        WHERE status IN (
                            'aguardando',
                            'em_analise'
                        )
                    ) AS pendentes

                FROM onboarding_solicitacoes
                """
            )

            resumo_onboarding = (
                cursor.fetchone()
                or {}
            )

            solicitacoes_aguardando = int(
                resumo_onboarding.get(
                    "aguardando"
                )
                or 0
            )

            solicitacoes_em_analise = int(
                resumo_onboarding.get(
                    "em_analise"
                )
                or 0
            )

            solicitacoes_pendentes = int(
                resumo_onboarding.get(
                    "pendentes"
                )
                or 0
            )

            ultimo_convite = session.pop(
                "ultimo_convite_onboarding",
                None,
            )

            return render_template(
                "admin.html",

                empresas=empresas,

                total_empresas=total_empresas,
                total_produtos=total_produtos,
                total_vendas=total_vendas,
                total_usuarios=total_usuarios,

                solicitacoes_aguardando=(
                    solicitacoes_aguardando
                ),

                solicitacoes_em_analise=(
                    solicitacoes_em_analise
                ),

                solicitacoes_pendentes=(
                    solicitacoes_pendentes
                ),

                ultimo_convite=ultimo_convite,
            )

        except Exception:
            app.logger.exception(
                "Erro ao carregar o Painel Master."
            )

            flash(
                "Não foi possível carregar o Painel Master.",
                "erro",
            )

            return redirect("/dashboard")

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # GERAR CONVITE DE EMPRESA
    # =====================================================

    @app.route(
        "/admin/convites/criar",
        methods=["POST"],
    )
    def criar_convite_empresa():

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        nome_destinatario = request.form.get(
            "nome_destinatario",
            "",
        )

        telefone_destinatario = request.form.get(
            "telefone_destinatario",
            "",
        )

        email_destinatario = request.form.get(
            "email_destinatario",
            "",
        )

        validade_horas = request.form.get(
            "validade_horas",
            "72",
        )

        try:
            convite = (
                OnboardingEmpresaService
                .criar_convite(
                    criado_por=session["usuario_id"],

                    url_base=(
                        request.url_root.rstrip("/")
                    ),

                    validade_horas=validade_horas,

                    nome_destinatario=(
                        nome_destinatario
                    ),

                    telefone_destinatario=(
                        telefone_destinatario
                    ),

                    email_destinatario=(
                        email_destinatario
                    ),

                    endereco_ip=endereco_ip(),
                )
            )

            session[
                "ultimo_convite_onboarding"
            ] = {
                "id": convite["id"],
                "link": convite["link"],

                "nome_destinatario": (
                    nome_destinatario.strip()
                ),

                "telefone_destinatario": (
                    telefone_destinatario.strip()
                ),

                "email_destinatario": (
                    email_destinatario.strip()
                ),
            }

            flash(
                "Link de cadastro gerado com sucesso.",
                "sucesso",
            )

        except OnboardingEmpresaErro as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao gerar convite de empresa."
            )

            flash(
                "Não foi possível gerar o convite.",
                "erro",
            )

        return redirect(
            url_for("admin")
        )

    # =====================================================
    # BLOQUEAR USUÁRIO
    # =====================================================

    @app.route(
        "/bloquear_usuario/<int:id>"
    )
    def bloquear_usuario(id):

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE usuarios

                SET status = 'bloqueado'

                WHERE id = %s
                  AND nivel = 'gerente'

                RETURNING id
                """,
                (id,),
            )

            usuario = cursor.fetchone()

            if not usuario:
                conn.rollback()

                flash(
                    "Usuário gerente não encontrado.",
                    "erro",
                )

                return redirect(
                    url_for("admin")
                )

            conn.commit()

            flash(
                "Usuário bloqueado.",
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao bloquear usuário %s.",
                id,
            )

            flash(
                "Não foi possível bloquear o usuário.",
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect(
            url_for("admin")
        )

    # =====================================================
    # LIBERAR USUÁRIO
    # =====================================================

    @app.route(
        "/liberar_usuario/<int:id>"
    )
    def liberar_usuario(id):

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE usuarios

                SET status = 'ativo'

                WHERE id = %s
                  AND nivel = 'gerente'

                RETURNING id
                """,
                (id,),
            )

            usuario = cursor.fetchone()

            if not usuario:
                conn.rollback()

                flash(
                    "Usuário gerente não encontrado.",
                    "erro",
                )

                return redirect(
                    url_for("admin")
                )

            conn.commit()

            flash(
                "Usuário liberado.",
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao liberar usuário %s.",
                id,
            )

            flash(
                "Não foi possível liberar o usuário.",
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect(
            url_for("admin")
        )

    # =====================================================
    # ALTERAR PLANO
    # =====================================================

    @app.route(
        "/alterar_plano_empresa/<int:empresa_id>",
        methods=["POST"],
    )
    def alterar_plano_empresa(
        empresa_id,
    ):

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        plano = request.form.get(
            "plano",
            "",
        ).strip().lower()

        if plano not in (
            "comum",
            "premium",
        ):
            flash(
                "Plano inválido.",
                "erro",
            )

            return redirect(
                url_for("admin")
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE empresa

                SET plano = %s

                WHERE id = %s

                RETURNING
                    id,
                    nome,
                    plano
                """,
                (
                    plano,
                    empresa_id,
                ),
            )

            empresa = cursor.fetchone()

            if not empresa:
                conn.rollback()

                flash(
                    "Empresa não encontrada.",
                    "erro",
                )

                return redirect(
                    url_for("admin")
                )

            conn.commit()

            flash(
                (
                    f"Plano da empresa "
                    f"{empresa['nome']} alterado "
                    f"para {plano.upper()}."
                ),
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                (
                    "Erro ao alterar o plano "
                    "da empresa %s."
                ),
                empresa_id,
            )

            flash(
                "Não foi possível alterar o plano.",
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect(
            url_for("admin")
        )

    # =====================================================
    # ALTERAR MÓDULO DE EMPRÉSTIMOS
    # =====================================================

    @app.route(
        (
            "/alterar_modulo_emprestimos/"
            "<int:empresa_id>"
        ),
        methods=["POST"],
    )
    def alterar_modulo_emprestimos(
        empresa_id,
    ):

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        valores_modulo = request.form.getlist(
            "emprestimos_ativo"
        )

        emprestimos_ativo = (
            "1" in valores_modulo
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE empresa

                SET emprestimos_ativo = %s

                WHERE id = %s

                RETURNING nome
                """,
                (
                    emprestimos_ativo,
                    empresa_id,
                ),
            )

            empresa = cursor.fetchone()

            if not empresa:
                conn.rollback()

                flash(
                    "Empresa não encontrada.",
                    "erro",
                )

                return redirect(
                    url_for("admin")
                )

            conn.commit()

            estado = (
                "ativado"
                if emprestimos_ativo
                else "desativado"
            )

            flash(
                (
                    f"Módulo de empréstimos {estado} "
                    f"para {empresa['nome']}."
                ),
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                (
                    "Erro ao alterar módulo "
                    "da empresa %s."
                ),
                empresa_id,
            )

            flash(
                "Não foi possível alterar o módulo.",
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect(
            url_for("admin")
        )

    # =====================================================
    # EXCLUIR EMPRESA
    # =====================================================

    @app.route(
        "/excluir_empresa/<int:id>"
    )
    def excluir_empresa(id):

        bloqueio = acesso_master()

        if bloqueio:
            return bloqueio

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT empresa_id

                FROM usuarios

                WHERE id = %s
                  AND nivel = 'gerente'

                LIMIT 1
                """,
                (id,),
            )

            usuario = cursor.fetchone()

            if not usuario:
                flash(
                    "Empresa não encontrada.",
                    "erro",
                )

                return redirect(
                    url_for("admin")
                )

            empresa_id = usuario["empresa_id"]

            cursor.execute(
                """
                DELETE FROM usuarios
                WHERE empresa_id = %s
                """,
                (empresa_id,),
            )

            cursor.execute(
                """
                DELETE FROM empresa
                WHERE id = %s
                """,
                (empresa_id,),
            )

            conn.commit()

            flash(
                "Empresa excluída.",
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao excluir empresa."
            )

            flash(
                (
                    "Não foi possível excluir a empresa. "
                    "Ela pode possuir registros vinculados."
                ),
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect(
            url_for("admin")
        )