from flask import (
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


def _endereco_ip():
    encaminhado = request.headers.get(
        "X-Forwarded-For",
        "",
    )

    if encaminhado:
        return encaminhado.split(",")[0].strip()

    return request.remote_addr or ""


def registrar_rotas(app):

    @app.route(
        "/convite/<token>",
        methods=["GET", "POST"],
    )
    def cadastro_empresa_convite(token):

        try:
            convite = (
                OnboardingEmpresaService.validar_convite(
                    token
                )
            )

        except OnboardingEmpresaErro as erro:
            return render_template(
                "cadastro_empresa_publico.html",
                estado="erro",
                mensagem=str(erro),
                convite=None,
                dados={},
            ), 410

        if request.method == "GET":
            dados = {
                "nome_responsavel": (
                    convite.get(
                        "nome_destinatario"
                    )
                    or ""
                ),
                "telefone": (
                    convite.get(
                        "telefone_destinatario"
                    )
                    or ""
                ),
                "email": (
                    convite.get(
                        "email_destinatario"
                    )
                    or ""
                ),
            }

            return render_template(
                "cadastro_empresa_publico.html",
                estado="formulario",
                mensagem=None,
                convite=convite,
                dados=dados,
            )

        # Campo invisível contra robôs.
        if request.form.get("site_empresa"):
            return render_template(
                "cadastro_empresa_publico.html",
                estado="erro",
                mensagem=(
                    "Não foi possível enviar o cadastro."
                ),
                convite=None,
                dados={},
            ), 400

        dados = {
            "nome_empresa": request.form.get(
                "nome_empresa",
                "",
            ),
            "nome_responsavel": request.form.get(
                "nome_responsavel",
                "",
            ),
            "cpf_cnpj": request.form.get(
                "cpf_cnpj",
                "",
            ),
            "telefone": request.form.get(
                "telefone",
                "",
            ),
            "email": request.form.get(
                "email",
                "",
            ),
            "usuario": request.form.get(
                "usuario",
                "",
            ),
            "segmento": request.form.get(
                "segmento",
                "",
            ),
            "cidade": request.form.get(
                "cidade",
                "",
            ),
            "estado": request.form.get(
                "estado",
                "",
            ),
            "observacoes_cliente": request.form.get(
                "observacoes_cliente",
                "",
            ),
        }

        try:
            solicitacao = (
                OnboardingEmpresaService.criar_solicitacao(
                    token=token,

                    nome_empresa=dados[
                        "nome_empresa"
                    ],

                    nome_responsavel=dados[
                        "nome_responsavel"
                    ],

                    cpf_cnpj=dados[
                        "cpf_cnpj"
                    ],

                    telefone=dados[
                        "telefone"
                    ],

                    email=dados[
                        "email"
                    ],

                    usuario=dados[
                        "usuario"
                    ],

                    senha=request.form.get(
                        "senha",
                        "",
                    ),

                    confirmar_senha=request.form.get(
                        "confirmar_senha",
                        "",
                    ),

                    segmento=dados[
                        "segmento"
                    ],

                    cidade=dados[
                        "cidade"
                    ],

                    estado=dados[
                        "estado"
                    ],

                    observacoes_cliente=dados[
                        "observacoes_cliente"
                    ],

                    aceitou_termos=(
                        request.form.get(
                            "aceitou_termos"
                        )
                        == "on"
                    ),

                    aceitou_whatsapp=(
                        request.form.get(
                            "aceitou_whatsapp"
                        )
                        == "on"
                    ),

                    endereco_ip=_endereco_ip(),

                    user_agent=request.headers.get(
                        "User-Agent",
                        "",
                    ),
                )
            )

        except OnboardingEmpresaErro as erro:
            return render_template(
                "cadastro_empresa_publico.html",
                estado="formulario",
                mensagem=str(erro),
                convite=convite,
                dados=dados,
            ), 400

        session[
            "onboarding_solicitacao_enviada"
        ] = {
            "id": solicitacao["id"],
            "nome_empresa": solicitacao[
                "nome_empresa"
            ],
            "nome_responsavel": solicitacao[
                "nome_responsavel"
            ],
        }

        return redirect(
            url_for(
                "cadastro_empresa_enviado"
            )
        )


    @app.route("/cadastro-enviado")
    def cadastro_empresa_enviado():

        solicitacao = session.pop(
            "onboarding_solicitacao_enviada",
            None,
        )

        if not solicitacao:
            return redirect("/")

        return render_template(
            "cadastro_empresa_publico.html",
            estado="sucesso",
            mensagem=None,
            convite=None,
            dados=solicitacao,
        )