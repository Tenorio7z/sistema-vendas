from flask import *
from database import conectar, criar_cursor
from services.cupom_service import gerar_cupom_venda
from services.notificacoes import notificar_gerente
from services.fcm_services import enviar_notificacao
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)

from uuid import uuid4
from psycopg2.extras import execute_values

CENTAVOS = Decimal("0.01")


def _decimal_monetario(valor):

    try:
        texto = str(
            valor
            if valor is not None
            else "0"
        ).strip()

        texto = texto.replace(
            "R$",
            "",
        ).strip()

        if (
            "," in texto
            and "." in texto
        ):
            texto = texto.replace(
                ".",
                "",
            ).replace(
                ",",
                ".",
            )

        else:
            texto = texto.replace(
                ",",
                ".",
            )

        return Decimal(
            texto or "0"
        ).quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as erro:
        raise ValueError(
            "Valor de desconto inválido."
        ) from erro


def _calcular_desconto(
    total_bruto,
    tipo_desconto,
    valor_informado,
):

    total_bruto = _decimal_monetario(
        total_bruto
    )

    tipo_desconto = str(
        tipo_desconto or "nenhum"
    ).strip().lower()

    valor_informado = _decimal_monetario(
        valor_informado
    )

    if tipo_desconto in (
        "",
        "nenhum",
    ):
        return (
            Decimal("0.00"),
            Decimal("0.0000"),
        )

    if valor_informado < 0:
        raise ValueError(
            "O desconto não pode ser negativo."
        )

    if tipo_desconto == "percentual":

        if valor_informado > 100:
            raise ValueError(
                (
                    "O desconto percentual não "
                    "pode ultrapassar 100%."
                )
            )

        percentual = valor_informado

        desconto = (
            total_bruto
            * percentual
            / Decimal("100")
        ).quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

    elif tipo_desconto == "valor":

        desconto = valor_informado

        if desconto > total_bruto:
            raise ValueError(
                (
                    "O desconto não pode ser maior "
                    "que o total da venda."
                )
            )

        percentual = (
            desconto
            / total_bruto
            * Decimal("100")
            if total_bruto > 0
            else Decimal("0")
        ).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )

    else:
        raise ValueError(
            "Tipo de desconto inválido."
        )

    return (
        desconto,
        percentual,
    )
    
    
def _carrinho_serializado():

    carrinho = session.get(
        "carrinho",
        [],
    )

    itens = []
    total = Decimal("0.00")

    for item in carrinho:

        preco = _decimal_monetario(
            item.get("preco", 0)
        )

        quantidade = int(
            item.get("quantidade", 0)
        )

        subtotal = (
            preco * quantidade
        ).quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        total += subtotal

        itens.append(
            {
                "id": int(item["id"]),
                "nome": str(item["nome"]),
                "preco": float(preco),
                "quantidade": quantidade,
                "subtotal": float(subtotal),
            }
        )

    return {
        "sucesso": True,
        "itens": itens,
        "quantidade": sum(
            item["quantidade"]
            for item in itens
        ),
        "tipos_itens": len(itens),
        "total": float(
            total.quantize(
                CENTAVOS,
                rounding=ROUND_HALF_UP,
            )
        ),
    }


def _requisicao_ajax():

    return (
        request.headers.get(
            "X-Requested-With"
        )
        == "XMLHttpRequest"
    )


def _erro_carrinho(
    mensagem,
    status=400,
):

    if _requisicao_ajax():

        resposta = _carrinho_serializado()

        resposta["sucesso"] = False
        resposta["mensagem"] = mensagem

        return jsonify(
            resposta
        ), status

    flash(
        mensagem,
        "erro",
    )

    return redirect("/vendas")

def registrar_rotas(app, socketio):

    # ==========================================
    # VENDAS
    # ==========================================

    @app.route("/vendas")
    def vendas():

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)
        conn.autocommit = False
        
        empresa_id = session.get("empresa_id")
        usuario_id = session.get("usuario_id") or None
        if not empresa_id:
            conn.close()
            return redirect("/")

        # ==========================================
        # BUSCAR CAIXA ABERTO (OBRIGATÓRIO)
        # ==========================================
        cursor.execute("""
            SELECT *
            FROM caixa
            WHERE empresa_id = %s
            AND status = 'aberto'
            ORDER BY id DESC
            LIMIT 1
        """, (empresa_id,))

        caixa = cursor.fetchone()

        if not caixa:
            conn.close()
            return render_template("vendas.html", caixa_fechado=True)

        # ==========================================
        # BUSCAR PRODUTOS
        # ==========================================
        cursor.execute(
            """
            SELECT
                id,
                nome,
                preco,
                estoque,
                codigo_barras,
                empresa_id,

                CASE
                    WHEN imagem IS NOT NULL
                    THEN TRUE
                    ELSE FALSE
                END AS possui_imagem

            FROM produtos

            WHERE empresa_id = %s

            ORDER BY nome ASC
            """,
            (
                empresa_id,
            )
        )
        produtos = cursor.fetchall()
        
        # ==========================================
        # CLIENTES ATIVOS DA EMPRESA
        # ==========================================

        cursor.execute(
            """
            SELECT
                id,
                nome,
                telefone,
                cpf_cnpj

            FROM clientes

            WHERE empresa_id = %s
            AND ativo = TRUE

            ORDER BY nome ASC
            """,
            (
                empresa_id,
            ),
        )

        clientes = cursor.fetchall()

        # ==========================================
        # CARRINHO DA SESSÃO
        # ==========================================
        carrinho = session.get("carrinho", [])

        total = sum(float(item["preco"]) * int(item["quantidade"]) for item in carrinho)

        conn.close()

        # ==========================================
        # CONTROLE DO CUPOM
        # ==========================================
        abrir_cupom = bool(session.get("ultimo_cupom"))

        return render_template(
            "vendas.html",
            produtos=produtos,
            carrinho=carrinho,
            total=total,
            clientes=clientes,
            caixa_fechado=False,
            abrir_cupom=abrir_cupom
        )

        # ==========================================
    # ADICIONAR AO CARRINHO
    # ==========================================

    @app.route(
        "/adicionar_carrinho/<int:id>",
        methods=["GET", "POST"],
    )
    
    
    def adicionar_carrinho(id):

        if not session.get("logado"):

            if _requisicao_ajax():
                return jsonify(
                    {
                        "sucesso": False,
                        "mensagem": (
                            "Sua sessão expirou."
                        ),
                        "redirecionar": "/",
                    }
                ), 401

            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            return _erro_carrinho(
                "Empresa não identificada.",
                401,
            )

        conexao = conectar()
        cursor = criar_cursor(conexao)

        try:
            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    preco,
                    estoque

                FROM produtos

                WHERE id = %s
                  AND empresa_id = %s

                LIMIT 1
                """,
                (
                    id,
                    empresa_id,
                ),
            )

            produto = cursor.fetchone()

            if not produto:
                return _erro_carrinho(
                    "Produto não encontrado.",
                    404,
                )

            estoque = int(
                produto["estoque"] or 0
            )

            if estoque <= 0:
                return _erro_carrinho(
                    (
                        f"{produto['nome']} "
                        "está sem estoque."
                    )
                )

            carrinho = session.get(
                "carrinho",
                [],
            )

            encontrado = False

            for item in carrinho:

                if int(item["id"]) != id:
                    continue

                quantidade_atual = int(
                    item["quantidade"]
                )

                if quantidade_atual >= estoque:
                    return _erro_carrinho(
                        (
                            "Limite de estoque "
                            "atingido."
                        )
                    )

                item["quantidade"] = (
                    quantidade_atual + 1
                )

                encontrado = True
                break

            if not encontrado:

                carrinho.append(
                    {
                        "id": int(
                            produto["id"]
                        ),
                        "nome": str(
                            produto["nome"]
                        ),
                        "preco": float(
                            produto["preco"]
                        ),
                        "quantidade": 1,
                    }
                )

            session["carrinho"] = carrinho
            session.modified = True

            if _requisicao_ajax():

                resposta = (
                    _carrinho_serializado()
                )

                resposta["mensagem"] = (
                    f"{produto['nome']} "
                    "adicionado."
                )

                return jsonify(resposta)

            return redirect("/vendas")

        finally:
            cursor.close()
            conexao.close()

        # ==========================================
    # REMOVER DO CARRINHO
    # ==========================================

    @app.route(
        "/remover_carrinho/<int:id>",
        methods=["GET", "POST"],
    )
    def remover_carrinho(id):

        if not session.get("logado"):

            if _requisicao_ajax():
                return jsonify(
                    {
                        "sucesso": False,
                        "mensagem": (
                            "Sua sessão expirou."
                        ),
                        "redirecionar": "/",
                    }
                ), 401

            return redirect("/")

        carrinho = session.get(
            "carrinho",
            [],
        )

        novo_carrinho = []

        for item in carrinho:

            if int(item["id"]) == id:

                quantidade = (
                    int(item["quantidade"])
                    - 1
                )

                if quantidade > 0:

                    item["quantidade"] = (
                        quantidade
                    )

                    novo_carrinho.append(
                        item
                    )

            else:
                novo_carrinho.append(
                    item
                )

        session["carrinho"] = (
            novo_carrinho
        )

        session.modified = True

        if _requisicao_ajax():
            return jsonify(
                _carrinho_serializado()
            )

        return redirect("/vendas")
    
        # ==========================================
    # LIMPAR CARRINHO
    # ==========================================

    @app.route(
        "/limpar_carrinho",
        methods=["GET", "POST"],
    )
    def limpar_carrinho():

        if not session.get("logado"):

            if _requisicao_ajax():
                return jsonify(
                    {
                        "sucesso": False,
                        "mensagem": (
                            "Sua sessão expirou."
                        ),
                        "redirecionar": "/",
                    }
                ), 401

            return redirect("/")

        session["carrinho"] = []
        session.modified = True

        if _requisicao_ajax():
            return jsonify(
                _carrinho_serializado()
            )

        flash(
            "Carrinho limpo.",
            "sucesso",
        )

        return redirect("/vendas")

    # ==========================================
    # FINALIZAR VENDA
    # ==========================================


    @app.route(
        "/finalizar_venda",
        methods=["POST"],
    
    )
    
    def finalizar_venda():

        if not session.get("logado"):
            return redirect("/")

        usuario_id = session.get("usuario_id")
        empresa_id = session.get("empresa_id")

        if not usuario_id or not empresa_id:
            flash(
                "Sessão inválida. Faça login novamente.",
                "erro",
            )
            return redirect("/vendas")

        pagamentos_permitidos = {
            "dinheiro": "Dinheiro",
            "pix": "PIX",
            "cartão": "Cartão",
            "cartao": "Cartão",
        }

        pagamento_recebido = str(
            request.form.get("pagamento", "")
        ).strip().lower()

        forma_pagamento = pagamentos_permitidos.get(
            pagamento_recebido
        )

        if not forma_pagamento:
            flash(
                "Forma de pagamento inválida.",
                "erro",
            )
            return redirect("/vendas")

        carrinho = session.get("carrinho", [])

        if not carrinho:
            flash("Carrinho vazio.", "erro")
            return redirect("/vendas")

        tipo_desconto = request.form.get(
            "desconto_tipo",
            "nenhum",
        )

        desconto_informado = request.form.get(
            "desconto_valor",
            "0",
        )

        cliente_id_recebido = str(
            request.form.get("cliente_id", "") or ""
        ).strip()

        cliente_id = None

        if cliente_id_recebido:
            try:
                cliente_id = int(cliente_id_recebido)

            except (TypeError, ValueError):
                flash(
                    "Cliente selecionado inválido.",
                    "erro",
                )
                return redirect("/vendas")

        # Une produtos repetidos no carrinho antes de consultar o banco.
        quantidades_por_produto = {}

        try:
            for item in carrinho:
                produto_id = int(item["id"])
                quantidade = int(item["quantidade"])

                if quantidade <= 0:
                    raise ValueError(
                        "Quantidade inválida no carrinho."
                    )

                quantidades_por_produto[produto_id] = (
                    quantidades_por_produto.get(
                        produto_id,
                        0,
                    )
                    + quantidade
                )

        except (KeyError, TypeError, ValueError):
            flash(
                "O carrinho contém dados inválidos.",
                "erro",
            )
            return redirect("/vendas")

        produtos_ids = list(
            quantidades_por_produto.keys()
        )

        conn = conectar()
        cursor = criar_cursor(conn)
        conn.autocommit = False

        cliente_venda = None
        vendas_cupom = []

        total_bruto = Decimal("0.00")
        desconto_total = Decimal("0.00")
        total_liquido = Decimal("0.00")

        try:
            # Bloqueia o caixa durante a finalização.
            cursor.execute(
                """
                SELECT
                    id,
                    valor_final
                FROM caixa
                WHERE empresa_id = %s
                  AND status = 'aberto'
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
                """,
                (empresa_id,),
            )

            caixa = cursor.fetchone()

            if not caixa:
                raise ValueError(
                    "Nenhum caixa aberto."
                )

            # Valida o cliente opcional.
            if cliente_id is not None:
                cursor.execute(
                    """
                    SELECT
                        id,
                        nome,
                        telefone,
                        cpf_cnpj
                    FROM clientes
                    WHERE id = %s
                      AND empresa_id = %s
                      AND ativo = TRUE
                    LIMIT 1
                    """,
                    (
                        cliente_id,
                        empresa_id,
                    ),
                )

                cliente_venda = cursor.fetchone()

                if not cliente_venda:
                    raise ValueError(
                        "O cliente selecionado não existe, "
                        "está inativo ou pertence a outra empresa."
                    )

            # Busca todos os produtos em uma única consulta.
            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    preco,
                    estoque
                FROM produtos
                WHERE empresa_id = %s
                  AND id = ANY(%s)
                ORDER BY id
                FOR UPDATE
                """,
                (
                    empresa_id,
                    produtos_ids,
                ),
            )

            produtos_encontrados = cursor.fetchall()

            produtos_por_id = {
                int(produto["id"]): produto
                for produto in produtos_encontrados
            }

            if len(produtos_por_id) != len(produtos_ids):
                ids_encontrados = set(
                    produtos_por_id.keys()
                )

                ids_ausentes = [
                    produto_id
                    for produto_id in produtos_ids
                    if produto_id not in ids_encontrados
                ]

                raise ValueError(
                    "Um ou mais produtos não foram encontrados: "
                    + ", ".join(
                        str(produto_id)
                        for produto_id in ids_ausentes
                    )
                )

            itens_processados = []

            # Calcula preços e valida estoques em memória.
            for produto_id in produtos_ids:
                produto = produtos_por_id[produto_id]
                quantidade = quantidades_por_produto[
                    produto_id
                ]

                estoque_atual = int(
                    produto["estoque"] or 0
                )

                if estoque_atual < quantidade:
                    raise ValueError(
                        "Estoque insuficiente para "
                        f"{produto['nome']}. "
                        f"Disponível: {estoque_atual}."
                    )

                preco_unitario = _decimal_monetario(
                    produto["preco"]
                )

                valor_bruto_item = (
                    preco_unitario
                    * quantidade
                ).quantize(
                    CENTAVOS,
                    rounding=ROUND_HALF_UP,
                )

                total_bruto += valor_bruto_item

                itens_processados.append(
                    {
                        "produto": produto,
                        "quantidade": quantidade,
                        "preco_unitario": preco_unitario,
                        "valor_bruto": valor_bruto_item,
                    }
                )

            total_bruto = total_bruto.quantize(
                CENTAVOS,
                rounding=ROUND_HALF_UP,
            )

            if total_bruto <= 0:
                raise ValueError(
                    "O total da venda é inválido."
                )

            desconto_total, percentual = (
                _calcular_desconto(
                    total_bruto,
                    tipo_desconto,
                    desconto_informado,
                )
            )

            total_liquido = (
                total_bruto
                - desconto_total
            ).quantize(
                CENTAVOS,
                rounding=ROUND_HALF_UP,
            )

            venda_grupo = str(uuid4())
            desconto_restante = desconto_total

            linhas_estoque = []
            linhas_vendas = []

            for indice, item in enumerate(
                itens_processados
            ):
                produto = item["produto"]
                quantidade = item["quantidade"]
                valor_bruto_item = item["valor_bruto"]

                ultimo_item = (
                    indice
                    == len(itens_processados) - 1
                )

                if ultimo_item:
                    desconto_item = desconto_restante

                else:
                    desconto_item = (
                        desconto_total
                        * valor_bruto_item
                        / total_bruto
                    ).quantize(
                        CENTAVOS,
                        rounding=ROUND_HALF_UP,
                    )

                    if desconto_item > desconto_restante:
                        desconto_item = desconto_restante

                desconto_restante -= desconto_item

                valor_liquido_item = (
                    valor_bruto_item
                    - desconto_item
                ).quantize(
                    CENTAVOS,
                    rounding=ROUND_HALF_UP,
                )

                linhas_estoque.append(
                    (
                        int(produto["id"]),
                        quantidade,
                        empresa_id,
                    )
                )

                linhas_vendas.append(
                    (
                        int(produto["id"]),
                        quantidade,
                        valor_liquido_item,
                        valor_bruto_item,
                        desconto_item,
                        percentual,
                        venda_grupo,
                        forma_pagamento,
                        empresa_id,
                        int(caixa["id"]),
                        usuario_id,
                        cliente_id,
                    )
                )

                vendas_cupom.append(
                    {
                        "nome": produto["nome"],
                        "quantidade": quantidade,
                        "preco_unitario": (
                            item["preco_unitario"]
                        ),
                        "valor_bruto": valor_bruto_item,
                        "desconto": desconto_item,
                        "valor": valor_liquido_item,
                        "pagamento": forma_pagamento,
                        "empresa_id": empresa_id,
                        "venda_grupo": venda_grupo,
                        "cliente_id": cliente_id,
                        "cliente_nome": (
                            cliente_venda["nome"]
                            if cliente_venda
                            else None
                        ),
                        "cliente_telefone": (
                            cliente_venda["telefone"]
                            if cliente_venda
                            else None
                        ),
                        "cliente_cpf_cnpj": (
                            cliente_venda["cpf_cnpj"]
                            if cliente_venda
                            else None
                        ),
                    }
                )

            # Atualiza todos os estoques em uma única operação.
            estoques_atualizados = execute_values(
                cursor,
                """
                WITH dados (
                    produto_id,
                    quantidade,
                    empresa_id
                ) AS (
                    VALUES %s
                )
                UPDATE produtos AS p
                SET estoque = (
                    p.estoque
                    - dados.quantidade
                )
                FROM dados
                WHERE p.id = dados.produto_id
                  AND p.empresa_id = dados.empresa_id
                  AND p.estoque >= dados.quantidade
                RETURNING p.id
                """,
                linhas_estoque,
                template="(%s, %s, %s)",
                page_size=len(linhas_estoque),
                fetch=True,
            )

            if len(estoques_atualizados) != len(
                linhas_estoque
            ):
                raise ValueError(
                    "O estoque de algum produto foi alterado "
                    "durante a venda. Confira o carrinho novamente."
                )

            # Registra todos os itens em uma única operação.
            execute_values(
                cursor,
                """
                INSERT INTO vendas (
                    produto_id,
                    quantidade,
                    valor,
                    valor_bruto,
                    desconto_valor,
                    desconto_percentual,
                    venda_grupo,
                    pagamento,
                    empresa_id,
                    caixa_id,
                    usuario_id,
                    cliente_id,
                    data_venda
                )
                VALUES %s
                """,
                linhas_vendas,
                template=(
                    "("
                    "%s, %s, %s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, "
                    "CURRENT_TIMESTAMP"
                    ")"
                ),
                page_size=len(linhas_vendas),
            )

            cursor.execute(
                """
                UPDATE caixa
                SET valor_final = (
                    COALESCE(valor_final, 0)
                    + %s
                )
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    total_liquido,
                    caixa["id"],
                    empresa_id,
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError(
                    "Não foi possível atualizar o caixa."
                )

            conn.commit()

        except ValueError as erro:
            conn.rollback()

            flash(
                str(erro),
                "erro",
            )

            return redirect("/vendas")

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro inesperado ao finalizar venda."
            )

            flash(
                "Não foi possível finalizar a venda. "
                "Tente novamente.",
                "erro",
            )

            return redirect("/vendas")

        finally:
            cursor.close()
            conn.close()

        # A venda já foi confirmada no banco.
        # Limpa o carrinho antes das tarefas secundárias.
        session["carrinho"] = []
        session.modified = True

        try:
            notificar_gerente(
                usuario_id,
                "Venda realizada",
                float(total_liquido),
                empresa_id,
            )

        except Exception:
            app.logger.exception(
                "Erro ao notificar gerente sobre a venda."
            )

        try:
            pdf = gerar_cupom_venda(
                vendas_cupom,
                empresa_id,
            )

            if pdf:
                session["ultimo_cupom"] = pdf
                session.modified = True

        except Exception:
            # Falha no cupom não pode duplicar ou desfazer a venda.
            app.logger.exception(
                "Venda concluída, mas o cupom não foi gerado."
            )

        cliente_mensagem = (
            f" | Cliente: {cliente_venda['nome']}"
            if cliente_venda
            else " | Venda sem cliente"
        )

        flash(
            (
                "Venda finalizada. "
                f"Total bruto: R$ {total_bruto:.2f} | "
                f"Desconto: R$ {desconto_total:.2f} | "
                f"Total pago: R$ {total_liquido:.2f}"
                f"{cliente_mensagem}"
            ),
            "sucesso",
        )

        return redirect("/vendas")
        
        
    @app.route("/codigo/<codigo>")
    def codigo(codigo):

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)
        conn.autocommit = False
        
        
        empresa_id = session.get("empresa_id")
        usuario_id = session.get("usuario_id")
        

        if not empresa_id:
            conn.close()
            return redirect("/")

        cursor.execute("""
            SELECT *
            FROM produtos
            WHERE codigo_barras = %s
            AND empresa_id = %s
        """, (codigo, empresa_id))

        produto = cursor.fetchone()

        if not produto:
            conn.close()
            flash("Produto não encontrado", "erro")
            return redirect("/vendas")

        conn.close()

        return redirect(f"/adicionar_carrinho/{produto['id']}")
    
    
    @app.route("/abrir_cupom")
    def abrir_cupom():

        if not session.get("logado"):
            return redirect("/")

        pdf = session.get("ultimo_cupom")

        if not pdf:
            return ""

        session.pop("ultimo_cupom", None)

        return send_file(
            pdf,
            as_attachment=False
        )


