from database import conectar, criar_cursor

from services.mesas_service import (
    MesasErro,
    MesasService,
)

from services.modulos_empresa_service import (
    modulo_obrigatorio,
)

from services.cupom_service import (
    gerar_cupom_venda,
)

from services.notificacoes import (
    notificar_gerente,
)

from flask import (
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask_socketio import join_room

def _voltar_mesas():

    return redirect(
        url_for("mesas")
    )


def _buscar_clientes(
    empresa_id,
):

    conn = conectar()
    cursor = criar_cursor(conn)

    try:

        cursor.execute(
            """
            SELECT
                id,
                nome,
                telefone

            FROM clientes

            WHERE empresa_id = %s
              AND ativo = TRUE

            ORDER BY nome

            LIMIT 500
            """,
            (empresa_id,),
        )

        return cursor.fetchall()

    finally:

        cursor.close()
        conn.close()


def registrar_rotas(
    app,
    socketio,
):
    
    # =====================================================
    # SOCKET.IO — ENTRAR NOS CANAIS DA EMPRESA
    # =====================================================

    @socketio.on("entrar_operacao")
    def entrar_operacao(
        dados=None,
    ):

        if not session.get("logado"):
            return

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            return

        dados = dados or {}

        setor = str(
            dados.get(
                "setor",
                ""
            )
        ).strip().lower()

        somente_setor = bool(
            dados.get("somente_setor")
        )

        if not somente_setor:
            join_room(
                f"empresa_{empresa_id}"
            )

        if setor in {
            "cozinha",
            "bar",
            "caixa",
            "garcom",
        }:

            join_room(
                f"empresa_{empresa_id}_{setor}"
            )

    # =====================================================
    # PAINEL DE MESAS
    # =====================================================

    @app.route(
        "/mesas",
        methods=["GET"],
    )
    @modulo_obrigatorio("mesas")
    def mesas():

        empresa_id = session.get(
            "empresa_id"
        )

        try:

            mesas_lista = (
                MesasService.listar_mesas(
                    empresa_id
                )
            )

            resumo = MesasService.resumo(
                empresa_id
            )

            clientes = _buscar_clientes(
                empresa_id
            )

            return render_template(
                "mesas.html",
                mesas=mesas_lista,
                resumo=resumo,
                clientes=clientes,
            )

        except Exception:

            app.logger.exception(
                "Erro ao carregar o painel de mesas."
            )

            flash(
                (
                    "Não foi possível carregar "
                    "o painel de mesas."
                ),
                "erro",
            )

            return redirect(
                url_for("dashboard")
            )

    # =====================================================
    # CATÁLOGO SIMPLIFICADO DAS MESAS
    # =====================================================

    @app.route(
        "/mesas/produtos-disponiveis",
        methods=["GET"],
    )
    @modulo_obrigatorio("mesas")
    def produtos_disponiveis_mesa():

        try:
            produtos = MesasService.listar_produtos(
                session.get("empresa_id")
            )

            return jsonify(
                {
                    "ok": True,
                    "produtos": [
                        {
                            "id": produto["id"],
                            "nome": produto["nome"],
                            "preco": float(
                                produto["preco"] or 0
                            ),
                            "estoque": float(
                                produto["estoque"] or 0
                            ),
                        }
                        for produto in produtos
                    ],
                }
            )

        except Exception:
            app.logger.exception(
                "Erro ao carregar produtos das mesas."
            )

            return jsonify(
                {
                    "ok": False,
                    "erro": (
                        "Não foi possível carregar os produtos."
                    ),
                }
            ), 500

    # =====================================================
    # LANÇAR VÁRIOS PRODUTOS DIRETAMENTE NA MESA
    # =====================================================

    @app.route(
        "/mesas/<int:mesa_id>/lancar-produtos",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def lancar_produtos_mesa(
        mesa_id,
    ):

        dados = request.get_json(
            silent=True
        ) or {}

        try:
            resultado = (
                MesasService.lancar_produtos_mesa(
                    empresa_id=session.get(
                        "empresa_id"
                    ),
                    mesa_id=mesa_id,
                    usuario_id=session.get(
                        "usuario_id"
                    ),
                    itens=dados.get(
                        "itens",
                        [],
                    ),
                )
            )

            return jsonify(
                {
                    "ok": True,
                    "mensagem": (
                        "Produtos lançados na mesa."
                    ),
                    "mesa_id": resultado["mesa_id"],
                    "comanda_id": resultado["comanda_id"],
                    "comanda_criada": resultado[
                        "comanda_criada"
                    ],
                    "quantidade_produtos": resultado[
                        "quantidade_produtos"
                    ],
                    "valor_adicionado": float(
                        resultado["valor_adicionado"]
                    ),
                    "subtotal": float(
                        resultado["subtotal"]
                    ),
                    "total": float(
                        resultado["total"]
                    ),
                }
            )

        except MesasErro as erro:
            return jsonify(
                {
                    "ok": False,
                    "erro": str(erro),
                }
            ), 400

        except Exception:
            app.logger.exception(
                (
                    "Erro ao lançar produtos "
                    "diretamente na mesa %s."
                ),
                mesa_id,
            )

            return jsonify(
                {
                    "ok": False,
                    "erro": (
                        "Não foi possível lançar os produtos."
                    ),
                }
            ), 500

    # =====================================================
    # CADASTRAR MESA
    # =====================================================

    @app.route(
        "/mesas/nova",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def nova_mesa():

        try:

            mesa = MesasService.criar_mesa(
                empresa_id=session.get(
                    "empresa_id"
                ),
                numero=request.form.get(
                    "numero"
                ),
                nome=request.form.get(
                    "nome"
                ),
                capacidade=request.form.get(
                    "capacidade",
                    4,
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
            )

            flash(
                (
                    f"Mesa {mesa['numero']} "
                    "cadastrada com sucesso."
                ),
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                "Erro ao cadastrar mesa."
            )

            flash(
                "Não foi possível cadastrar a mesa.",
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # CONFIGURAR QUANTIDADE DE MESAS
    # =====================================================

    @app.route(
        "/mesas/configurar",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def configurar_mesas():

        try:
            resultado = (
                MesasService
                .configurar_quantidade_mesas(
                    empresa_id=session.get(
                        "empresa_id"
                    ),
                    quantidade=request.form.get(
                        "quantidade"
                    ),
                    capacidade=request.form.get(
                        "capacidade",
                        4,
                    ),
                )
            )

            if resultado["criadas"]:
                flash(
                    (
                        f"{resultado['criadas']} mesa(s) "
                        "criada(s) com sucesso. "
                        f"Total atual: {resultado['total']}."
                    ),
                    "sucesso",
                )
            else:
                flash(
                    (
                        "As mesas solicitadas já estavam "
                        "cadastradas. Nenhuma duplicação foi feita."
                    ),
                    "info",
                )

        except MesasErro as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao configurar quantidade de mesas."
            )

            flash(
                "Não foi possível configurar as mesas.",
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # EDITAR MESA
    # =====================================================

    @app.route(
        "/mesas/<int:mesa_id>/editar",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def editar_mesa(
        mesa_id,
    ):

        try:

            mesa = MesasService.editar_mesa(
                empresa_id=session.get(
                    "empresa_id"
                ),
                mesa_id=mesa_id,
                numero=request.form.get(
                    "numero"
                ),
                nome=request.form.get(
                    "nome"
                ),
                capacidade=request.form.get(
                    "capacidade",
                    4,
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
            )

            flash(
                (
                    f"Mesa {mesa['numero']} "
                    "atualizada com sucesso."
                ),
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                "Erro ao editar a mesa %s.",
                mesa_id,
            )

            flash(
                "Não foi possível editar a mesa.",
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # RESERVAR MESA
    # =====================================================

    @app.route(
        "/mesas/<int:mesa_id>/reservar",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def reservar_mesa(
        mesa_id,
    ):

        try:

            MesasService.alterar_status_mesa(
                empresa_id=session.get(
                    "empresa_id"
                ),
                mesa_id=mesa_id,
                status="reservada",
            )

            flash(
                "Mesa reservada com sucesso.",
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                "Erro ao reservar a mesa %s.",
                mesa_id,
            )

            flash(
                "Não foi possível reservar a mesa.",
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # LIBERAR MESA
    # =====================================================

    @app.route(
        "/mesas/<int:mesa_id>/liberar",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def liberar_mesa(
        mesa_id,
    ):

        try:

            MesasService.alterar_status_mesa(
                empresa_id=session.get(
                    "empresa_id"
                ),
                mesa_id=mesa_id,
                status="livre",
            )

            flash(
                "Mesa liberada com sucesso.",
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                "Erro ao liberar a mesa %s.",
                mesa_id,
            )

            flash(
                "Não foi possível liberar a mesa.",
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # ATIVAR OU INATIVAR MESA
    # =====================================================

    @app.route(
        "/mesas/<int:mesa_id>/status",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def status_mesa(
        mesa_id,
    ):

        status = request.form.get(
            "status",
            "",
        )

        try:

            MesasService.alterar_status_mesa(
                empresa_id=session.get(
                    "empresa_id"
                ),
                mesa_id=mesa_id,
                status=status,
            )

            flash(
                "Status da mesa atualizado.",
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                (
                    "Erro ao atualizar o status "
                    "da mesa %s."
                ),
                mesa_id,
            )

            flash(
                (
                    "Não foi possível atualizar "
                    "o status da mesa."
                ),
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # ABRIR COMANDA
    # =====================================================

    @app.route(
        "/mesas/<int:mesa_id>/abrir-comanda",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def abrir_comanda(
        mesa_id,
    ):

        try:

            comanda = MesasService.abrir_comanda(
                empresa_id=session.get(
                    "empresa_id"
                ),
                mesa_id=mesa_id,
                usuario_id=session.get(
                    "usuario_id"
                ),
                cliente_id=request.form.get(
                    "cliente_id"
                ) or None,
                identificacao=request.form.get(
                    "identificacao"
                ),
                quantidade_pessoas=request.form.get(
                    "quantidade_pessoas",
                    1,
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
            )

            flash(
                (
                    f"Comanda #{comanda['id']} "
                    "aberta com sucesso."
                ),
                "sucesso",
            )

            return redirect(
                url_for(
                    "detalhes_comanda",
                    comanda_id=comanda["id"],
                )
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                (
                    "Erro ao abrir comanda "
                    "na mesa %s."
                ),
                mesa_id,
            )

            flash(
                "Não foi possível abrir a comanda.",
                "erro",
            )

        return _voltar_mesas()

        # =====================================================
    # DETALHES DA COMANDA
    # =====================================================

    @app.route(
        "/comandas/<int:comanda_id>",
        methods=["GET"],
    )
    @modulo_obrigatorio("mesas")
    def detalhes_comanda(
        comanda_id,
    ):

        try:

            dados = MesasService.detalhar_comanda(
                empresa_id=session.get(
                    "empresa_id"
                ),
                comanda_id=comanda_id,
            )

            produtos = MesasService.listar_produtos(
                session.get(
                    "empresa_id"
                )
            )

            return render_template(
                "comanda.html",
                comanda=dados["comanda"],
                itens=dados["itens"],
                historico=dados["historico"],
                produtos=produtos,
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                "Erro ao carregar a comanda %s.",
                comanda_id,
            )

            flash(
                "Não foi possível carregar a comanda.",
                "erro",
            )

        return _voltar_mesas()

    # =====================================================
    # ADICIONAR ITEM À COMANDA
    # =====================================================

    @app.route(
        "/comandas/<int:comanda_id>/itens",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def adicionar_item_comanda(
        comanda_id,
    ):

        try:

            MesasService.adicionar_item(
                empresa_id=session.get(
                    "empresa_id"
                ),
                comanda_id=comanda_id,
                produto_id=request.form.get(
                    "produto_id"
                ),
                quantidade=request.form.get(
                    "quantidade",
                    1,
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
                usuario_id=session.get(
                    "usuario_id"
                ),
            )

            flash(
                "Item adicionado à comanda.",
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                (
                    "Erro ao adicionar item "
                    "à comanda %s."
                ),
                comanda_id,
            )

            flash(
                (
                    "Não foi possível adicionar "
                    "o item à comanda."
                ),
                "erro",
            )

        return redirect(
            url_for(
                "detalhes_comanda",
                comanda_id=comanda_id,
            )
        )

    # =====================================================
    # FINALIZAR E RECEBER COMANDA
    # =====================================================

    @app.route(
        "/comandas/<int:comanda_id>/finalizar",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def finalizar_comanda(
        comanda_id,
    ):

        try:
            resultado = (
                MesasService.finalizar_comanda(
                    empresa_id=session.get(
                        "empresa_id"
                    ),
                    comanda_id=comanda_id,
                    recebido_por=session.get(
                        "usuario_id"
                    ),
                    pagamento=request.form.get(
                        "pagamento"
                    ),
                    tipo_desconto=request.form.get(
                        "desconto_tipo",
                        "nenhum",
                    ),
                    desconto_informado=request.form.get(
                        "desconto_valor",
                        "0",
                    ),
                    cliente_id=request.form.get(
                        "cliente_id"
                    ),
                )
            )

        except MesasErro as erro:
            flash(
                str(erro),
                "erro",
            )

            return redirect(
                url_for("mesas")
            )

        except Exception:
            app.logger.exception(
                "Erro ao finalizar comanda %s.",
                comanda_id,
            )

            flash(
                "Não foi possível finalizar a comanda.",
                "erro",
            )

            return redirect(
                url_for("mesas")
            )

        # A transação financeira já foi confirmada.
        # Cupom e notificação são tarefas secundárias:
        # uma falha nelas não pode duplicar a venda.
        try:
            caminho_cupom = gerar_cupom_venda(
                resultado["cupom"],
                session.get("empresa_id"),
            )

            if caminho_cupom:
                session[
                    "ultimo_cupom"
                ] = caminho_cupom
                session.modified = True

        except Exception:
            app.logger.exception(
                "Comanda recebida, mas o cupom falhou."
            )

        try:
            notificar_gerente(
                resultado["usuario_venda"],
                (
                    "Comanda da mesa "
                    f"{resultado['mesa_numero']}"
                ),
                float(resultado["total"]),
                session.get("empresa_id"),
            )

        except Exception:
            app.logger.exception(
                "Erro ao notificar fechamento da comanda."
            )

        socketio.emit(
            "comanda_finalizada",
            {
                "comanda_id": resultado[
                    "comanda_id"
                ],
                "mesa_id": resultado[
                    "mesa_id"
                ],
                "total": float(
                    resultado["total"]
                ),
            },
            to=(
                f"empresa_"
                f"{session.get('empresa_id')}"
            ),
        )

        flash(
            (
                "Comanda finalizada. "
                f"Total recebido: "
                f"R$ {resultado['total']:.2f}."
            ),
            "sucesso",
        )

        return redirect(
            url_for("mesas")
        )

    # =====================================================
    # PAINEL DE PRODUÇÃO — COZINHA E BAR
    # =====================================================

    @app.route(
        "/producao/<setor>",
        methods=["GET"],
    )
    @modulo_obrigatorio("mesas")
    def painel_producao(
        setor,
    ):

        setor = str(
            setor or ""
        ).strip().lower()

        if setor not in {
            "cozinha",
            "bar",
        }:
            return redirect(
                url_for(
                    "painel_producao",
                    setor="cozinha",
                )
            )

        try:
            pedidos = (
                MesasService
                .listar_pedidos_producao(
                    empresa_id=session.get(
                        "empresa_id"
                    ),
                    setor=setor,
                )
            )

        except MesasErro as erro:
            flash(
                str(erro),
                "erro",
            )
            pedidos = []

        except Exception:
            app.logger.exception(
                "Erro ao carregar painel %s.",
                setor,
            )

            flash(
                "Não foi possível carregar os pedidos.",
                "erro",
            )

            pedidos = []

        return render_template(
            "producao.html",
            setor=setor,
            pedidos=pedidos,
        )

    # =====================================================
    # ALTERAR STATUS DO ITEM NA PRODUÇÃO
    # =====================================================

    @app.route(
        "/producao/<setor>/itens/<int:item_id>/status",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def status_item_producao(
        setor,
        item_id,
    ):

        dados = (
            request.get_json(
                silent=True
            )
            or request.form
        )

        status = dados.get(
            "status",
            "",
        )

        try:
            resultado = (
                MesasService
                .atualizar_item_producao(
                    empresa_id=session.get(
                        "empresa_id"
                    ),
                    item_id=item_id,
                    setor=setor,
                    status=status,
                    usuario_id=session.get(
                        "usuario_id"
                    ),
                )
            )

            empresa_id = session.get(
                "empresa_id"
            )

            socketio.emit(
                "item_producao_atualizado",
                resultado,
                to=f"empresa_{empresa_id}",
            )

            socketio.emit(
                "item_producao_atualizado",
                resultado,
                to=(
                    f"empresa_{empresa_id}_"
                    f"{setor}"
                ),
            )

            if resultado["status"] == "pronto":
                socketio.emit(
                    "item_pronto",
                    resultado,
                    to=(
                        f"empresa_{empresa_id}_"
                        "garcom"
                    ),
                )

            if request.is_json:
                return jsonify(
                    {
                        "ok": True,
                        "item": resultado,
                    }
                )

            flash(
                "Status atualizado.",
                "sucesso",
            )

        except MesasErro as erro:
            if request.is_json:
                return jsonify(
                    {
                        "ok": False,
                        "erro": str(erro),
                    }
                ), 400

            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao atualizar item %s.",
                item_id,
            )

            if request.is_json:
                return jsonify(
                    {
                        "ok": False,
                        "erro": (
                            "Não foi possível "
                            "atualizar o item."
                        ),
                    }
                ), 500

            flash(
                "Não foi possível atualizar o item.",
                "erro",
            )

        return redirect(
            url_for(
                "painel_producao",
                setor=setor,
            )
        )

    # =====================================================
    # ALTERAR QUANTIDADE DO ITEM
    # =====================================================

    @app.route(
        (
            "/comandas/<int:comanda_id>/"
            "itens/<int:item_id>/quantidade"
        ),
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def quantidade_item_comanda(
        comanda_id,
        item_id,
    ):

        try:

            MesasService.alterar_quantidade_item(
                empresa_id=session.get(
                    "empresa_id"
                ),
                comanda_id=comanda_id,
                item_id=item_id,
                quantidade=request.form.get(
                    "quantidade"
                ),
                usuario_id=session.get(
                    "usuario_id"
                ),
            )

            flash(
                "Quantidade atualizada.",
                "sucesso",
            )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                (
                    "Erro ao alterar o item %s "
                    "da comanda %s."
                ),
                item_id,
                comanda_id,
            )

            flash(
                (
                    "Não foi possível alterar "
                    "a quantidade."
                ),
                "erro",
            )

        return redirect(
            url_for(
                "detalhes_comanda",
                comanda_id=comanda_id,
            )
        )

    # =====================================================
    # ALTERAR STATUS OU CANCELAR ITEM
    # =====================================================

    @app.route(
        (
            "/comandas/<int:comanda_id>/"
            "itens/<int:item_id>/status"
        ),
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def status_item_comanda(
        comanda_id,
        item_id,
    ):

        try:

            status = request.form.get(
                "status",
                "",
            )

            MesasService.alterar_status_item(
                empresa_id=session.get(
                    "empresa_id"
                ),
                comanda_id=comanda_id,
                item_id=item_id,
                status=status,
                usuario_id=session.get(
                    "usuario_id"
                ),
            )

            if status == "cancelado":

                flash(
                    "Item cancelado com sucesso.",
                    "sucesso",
                )

            else:

                flash(
                    "Status do item atualizado.",
                    "sucesso",
                )

        except MesasErro as erro:

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                (
                    "Erro ao alterar o status "
                    "do item %s."
                ),
                item_id,
            )

            flash(
                (
                    "Não foi possível atualizar "
                    "o item."
                ),
                "erro",
            )

        return redirect(
            url_for(
                "detalhes_comanda",
                comanda_id=comanda_id,
            )
        )
        
        # =====================================================
    # ENVIAR PEDIDO PARA PRODUÇÃO
    # =====================================================

    @app.route(
        "/comandas/<int:comanda_id>/enviar-pedido",
        methods=["POST"],
    )
    @modulo_obrigatorio("mesas")
    def enviar_pedido_comanda(
        comanda_id,
    ):

        dados = (
            request.get_json(
                silent=True
            )
            or request.form
        )

        try:

            pedido = MesasService.enviar_pedido(
                empresa_id=session.get(
                    "empresa_id"
                ),
                comanda_id=comanda_id,
                usuario_id=session.get(
                    "usuario_id"
                ),
                observacoes=dados.get(
                    "observacoes"
                ),
            )

            empresa_id = session.get(
                "empresa_id"
            )

            # =============================================
            # AVISAR CAIXA E PAINEL GERAL
            # =============================================

            socketio.emit(
                "novo_pedido",
                pedido,
                to=f"empresa_{empresa_id}",
            )

            socketio.emit(
                "comanda_atualizada",
                {
                    "comanda_id": comanda_id,
                    "pedido_id": pedido[
                        "pedido_id"
                    ],
                    "numero": pedido[
                        "numero"
                    ],
                },
                to=f"empresa_{empresa_id}",
            )

            # =============================================
            # SEPARAR OS ITENS POR SETOR
            # =============================================

            setores = {
                "cozinha": [],
                "bar": [],
                "direto": [],
            }

            for item in pedido["itens"]:

                setor = item.get(
                    "setor",
                    "cozinha",
                )

                if setor not in setores:
                    setor = "cozinha"

                setores[setor].append(
                    item
                )

            # =============================================
            # ENVIAR PARA A COZINHA
            # =============================================

            if setores["cozinha"]:

                socketio.emit(
                    "novo_pedido_setor",
                    {
                        **pedido,
                        "setor": "cozinha",
                        "itens": setores[
                            "cozinha"
                        ],
                    },
                    to=(
                        f"empresa_"
                        f"{empresa_id}_cozinha"
                    ),
                )

            # =============================================
            # ENVIAR PARA O BAR
            # =============================================

            if setores["bar"]:

                socketio.emit(
                    "novo_pedido_setor",
                    {
                        **pedido,
                        "setor": "bar",
                        "itens": setores[
                            "bar"
                        ],
                    },
                    to=(
                        f"empresa_"
                        f"{empresa_id}_bar"
                    ),
                )

            # =============================================
            # ITENS DIRETOS JÁ AVISAM O GARÇOM
            # =============================================

            if setores["direto"]:

                socketio.emit(
                    "itens_diretos",
                    {
                        **pedido,
                        "setor": "direto",
                        "itens": setores[
                            "direto"
                        ],
                    },
                    to=(
                        f"empresa_"
                        f"{empresa_id}_garcom"
                    ),
                )

            mensagem = (
                f"Pedido #{pedido['numero']} "
                "enviado com sucesso."
            )

            if request.is_json:

                return jsonify(
                    {
                        "ok": True,
                        "mensagem": mensagem,
                        "pedido": pedido,
                    }
                )

            flash(
                mensagem,
                "sucesso",
            )

        except MesasErro as erro:

            if request.is_json:

                return jsonify(
                    {
                        "ok": False,
                        "erro": str(erro),
                    }
                ), 400

            flash(
                str(erro),
                "erro",
            )

        except Exception:

            app.logger.exception(
                (
                    "Erro ao enviar pedido "
                    "da comanda %s."
                ),
                comanda_id,
            )

            if request.is_json:

                return jsonify(
                    {
                        "ok": False,
                        "erro": (
                            "Não foi possível "
                            "enviar o pedido."
                        ),
                    }
                ), 500

            flash(
                "Não foi possível enviar o pedido.",
                "erro",
            )

        return redirect(
            url_for(
                "detalhes_comanda",
                comanda_id=comanda_id,
            )
        )
