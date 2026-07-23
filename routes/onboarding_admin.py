from functools import wraps

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.onboarding_empresa_service import (
    OnboardingEmpresaErro,
    OnboardingEmpresaService,
)


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def _endereco_ip():
    encaminhado = request.headers.get(
        "X-Forwarded-For",
        "",
    )

    if encaminhado:
        return encaminhado.split(",")[0].strip()

    return request.remote_addr


def _valor_booleano(valor):
    return str(
        valor or ""
    ).strip().lower() in {
        "1",
        "true",
        "on",
        "sim",
        "yes",
    }


def _rota_master(funcao):

    @wraps(funcao)
    def protegida(*args, **kwargs):

        if not session.get("logado"):
            flash(
                "Faça login para acessar o sistema.",
                "erro",
            )

            return redirect("/")

        if session.get("nivel") != "master":
            flash(
                "Acesso permitido somente ao administrador Master.",
                "erro",
            )

            return redirect("/dashboard")

        if not session.get("usuario_id"):
            session.clear()

            flash(
                "Sua sessão expirou. Faça login novamente.",
                "erro",
            )

            return redirect("/")

        return funcao(*args, **kwargs)

    return protegida


# =========================================================
# REGISTRAR ROTAS
# =========================================================

def registrar_rotas_onboarding_admin(app):

    # =====================================================
    # LISTAR SOLICITAÇÕES
    # =====================================================

    @app.route(
        "/admin/solicitacoes",
        methods=["GET"],
    )
    @_rota_master
    def onboarding_solicitacoes():

        status = request.args.get(
            "status",
            "",
        ).strip().lower()

        busca = request.args.get(
            "busca",
            "",
        ).strip()

        status_validos = {
            "",
            "aguardando",
            "em_analise",
            "aprovada",
            "rejeitada",
            "cancelada",
        }

        if status not in status_validos:
            status = ""

        try:
            solicitacoes = (
                OnboardingEmpresaService
                .listar_solicitacoes(
                    status=status,
                    busca=busca,
                    limite=200,
                )
            )

        except OnboardingEmpresaErro as erro:
            flash(
                str(erro),
                "erro",
            )

            solicitacoes = []

        except Exception:
            app.logger.exception(
                "Erro ao listar solicitações de empresas."
            )

            flash(
                "Não foi possível carregar as solicitações.",
                "erro",
            )

            solicitacoes = []

        totais = {
            "todas": len(solicitacoes),
            "aguardando": 0,
            "em_analise": 0,
            "aprovada": 0,
            "rejeitada": 0,
            "cancelada": 0,
        }

        # Quando existe filtro, buscamos um resumo separado
        # para os cards não exibirem apenas o resultado filtrado.
        try:
            todas_solicitacoes = (
                solicitacoes
                if not status and not busca
                else OnboardingEmpresaService
                .listar_solicitacoes(
                    status="",
                    busca="",
                    limite=500,
                )
            )

            totais["todas"] = len(
                todas_solicitacoes
            )

            for item in todas_solicitacoes:
                status_item = item.get(
                    "status",
                    "",
                )

                if status_item in totais:
                    totais[status_item] += 1

        except Exception:
            app.logger.exception(
                "Erro ao calcular resumo das solicitações."
            )

        return render_template(
            "onboarding_solicitacoes.html",
            solicitacoes=solicitacoes,
            totais=totais,
            filtro_status=status,
            filtro_busca=busca,
        )

    # =====================================================
    # DETALHES DA SOLICITAÇÃO
    # =====================================================

    @app.route(
        "/admin/solicitacoes/<int:solicitacao_id>",
        methods=["GET"],
    )
    @_rota_master
    def onboarding_solicitacao_detalhes(
        solicitacao_id,
    ):

        try:
            solicitacao = (
                OnboardingEmpresaService
                .buscar_solicitacao(
                    solicitacao_id
                )
            )

        except OnboardingEmpresaErro as erro:
            flash(
                str(erro),
                "erro",
            )

            return redirect(
                url_for(
                    "onboarding_solicitacoes"
                )
            )

        except Exception:
            app.logger.exception(
                (
                    "Erro ao consultar solicitação "
                    "%s."
                ),
                solicitacao_id,
            )

            flash(
                "Não foi possível carregar a solicitação.",
                "erro",
            )

            return redirect(
                url_for(
                    "onboarding_solicitacoes"
                )
            )

        return render_template(
            "onboarding_solicitacao_detalhes.html",
            solicitacao=solicitacao,
        )

    # =====================================================
    # MARCAR COMO EM ANÁLISE
    # =====================================================

    @app.route(
        (
            "/admin/solicitacoes/"
            "<int:solicitacao_id>/analisar"
        ),
        methods=["POST"],
    )
    @_rota_master
    def onboarding_solicitacao_analisar(
        solicitacao_id,
    ):

        try:
            alterada = (
                OnboardingEmpresaService
                .marcar_em_analise(
                    solicitacao_id=solicitacao_id,
                    usuario_id=session["usuario_id"],
                    endereco_ip=_endereco_ip(),
                )
            )

            if alterada:
                flash(
                    "Solicitação marcada como em análise.",
                    "sucesso",
                )

            else:
                flash(
                    "A solicitação já estava em análise.",
                    "info",
                )

        except OnboardingEmpresaErro as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                (
                    "Erro ao marcar solicitação "
                    "%s como em análise."
                ),
                solicitacao_id,
            )

            flash(
                "Não foi possível atualizar a solicitação.",
                "erro",
            )

        return redirect(
            url_for(
                "onboarding_solicitacao_detalhes",
                solicitacao_id=solicitacao_id,
            )
        )

    # =====================================================
    # APROVAR SOLICITAÇÃO
    # =====================================================

    @app.route(
        (
            "/admin/solicitacoes/"
            "<int:solicitacao_id>/aprovar"
        ),
        methods=["POST"],
    )
    @_rota_master
    def onboarding_solicitacao_aprovar(
        solicitacao_id,
    ):

        plano = request.form.get(
            "plano",
            "",
        )

        emprestimos_ativo = _valor_booleano(
            request.form.get(
                "emprestimos_ativo"
            )
        )

        dias_teste = request.form.get(
            "dias_teste",
            "0",
        )

        observacoes_admin = request.form.get(
            "observacoes_admin",
            "",
        )

        try:
            resultado = (
                OnboardingEmpresaService
                .aprovar_solicitacao(
                    solicitacao_id=solicitacao_id,
                    usuario_id=session["usuario_id"],
                    plano=plano,
                    emprestimos_ativo=emprestimos_ativo,
                    dias_teste=dias_teste,
                    observacoes_admin=(
                        observacoes_admin
                    ),
                    url_login=(
                        request.url_root.rstrip("/")
                    ),
                    endereco_ip=_endereco_ip(),
                )
            )

            flash(
                (
                    "Empresa aprovada com sucesso. "
                    f"Usuário criado: "
                    f"{resultado['usuario']}."
                ),
                "sucesso",
            )

            if resultado.get(
                "mensagem_whatsapp_id"
            ):
                flash(
                    (
                        "A mensagem de aprovação foi "
                        "adicionada à fila do WhatsApp."
                    ),
                    "info",
                )

            return redirect(
                url_for(
                    "onboarding_solicitacao_detalhes",
                    solicitacao_id=solicitacao_id,
                )
            )

        except OnboardingEmpresaErro as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                (
                    "Erro ao aprovar solicitação "
                    "%s."
                ),
                solicitacao_id,
            )

            flash(
                (
                    "Não foi possível aprovar a empresa. "
                    "Nenhuma conta foi criada."
                ),
                "erro",
            )

        return redirect(
            url_for(
                "onboarding_solicitacao_detalhes",
                solicitacao_id=solicitacao_id,
            )
        )

    # =====================================================
    # REJEITAR SOLICITAÇÃO
    # =====================================================

    @app.route(
        (
            "/admin/solicitacoes/"
            "<int:solicitacao_id>/rejeitar"
        ),
        methods=["POST"],
    )
    @_rota_master
    def onboarding_solicitacao_rejeitar(
        solicitacao_id,
    ):

        motivo = request.form.get(
            "motivo",
            "",
        )

        observacoes_admin = request.form.get(
            "observacoes_admin",
            "",
        )

        try:
            resultado = (
                OnboardingEmpresaService
                .rejeitar_solicitacao(
                    solicitacao_id=solicitacao_id,
                    usuario_id=session["usuario_id"],
                    motivo=motivo,
                    observacoes_admin=(
                        observacoes_admin
                    ),
                    endereco_ip=_endereco_ip(),
                )
            )

            flash(
                "Solicitação rejeitada.",
                "sucesso",
            )

            if resultado.get(
                "mensagem_whatsapp_id"
            ):
                flash(
                    (
                        "A mensagem de rejeição foi "
                        "adicionada à fila do WhatsApp."
                    ),
                    "info",
                )

            return redirect(
                url_for(
                    "onboarding_solicitacao_detalhes",
                    solicitacao_id=solicitacao_id,
                )
            )

        except OnboardingEmpresaErro as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                (
                    "Erro ao rejeitar solicitação "
                    "%s."
                ),
                solicitacao_id,
            )

            flash(
                "Não foi possível rejeitar a solicitação.",
                "erro",
            )

        return redirect(
            url_for(
                "onboarding_solicitacao_detalhes",
                solicitacao_id=solicitacao_id,
            )
        )

    # =====================================================
    # VOLTAR AO PAINEL MASTER
    # =====================================================

    @app.route(
        "/admin/solicitacoes/voltar",
        methods=["GET"],
    )
    @_rota_master
    def onboarding_solicitacoes_voltar():

        return redirect(
            url_for("admin")
        )