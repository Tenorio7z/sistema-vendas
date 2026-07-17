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
            caixa_fechado=False,
            abrir_cupom=abrir_cupom
        )

    # ==========================================
    # ADICIONAR CARRINHO
    # ==========================================

    @app.route("/adicionar_carrinho/<int:id>")
    def adicionar_carrinho(id):

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
        
        cursor.execute(
            """
        SELECT *
        FROM produtos
        WHERE id = %s
        AND empresa_id = %s
        """,
            (id, empresa_id),
        )

        produto = cursor.fetchone()

        conn.close()

        if not produto:
            return redirect("/vendas")

        if produto["estoque"] <= 0:
            flash(f'{produto["nome"]} sem estoque', "erro")
            return redirect("/vendas")

        carrinho = session.get("carrinho", [])

        encontrado = False

        for item in carrinho:

            if item["id"] == produto["id"]:

                if item["quantidade"] >= produto["estoque"]:

                    flash("Limite de estoque atingido", "erro")

                    return redirect("/vendas")

                item["quantidade"] += 1
                encontrado = True

        if not encontrado:

            carrinho.append(
                {
                    "id": produto["id"],
                    "nome": produto["nome"],
                    "preco": produto["preco"],
                    "quantidade": 1,
                }
            )

        session["carrinho"] = carrinho

        return redirect("/vendas")

    # ==========================================
    # REMOVER ITEM
    # ==========================================

    @app.route("/remover_carrinho/<int:id>")
    def remover_carrinho(id):

        carrinho = session.get("carrinho", [])

        novo_carrinho = []

        for item in carrinho:

            if item["id"] == id:

                item["quantidade"] -= 1

                if item["quantidade"] > 0:
                    novo_carrinho.append(item)

            else:
                novo_carrinho.append(item)

        session["carrinho"] = novo_carrinho

        return redirect("/vendas")

    # ==========================================
    # LIMPAR CARRINHO
    # ==========================================

    @app.route("/limpar_carrinho")
    def limpar_carrinho():

        session["carrinho"] = []

        flash("Carrinho limpo", "sucesso")

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

        usuario_id = session.get(
            "usuario_id"
        )

        empresa_id = session.get(
            "empresa_id"
        )

        if not usuario_id or not empresa_id:

            flash(
                (
                    "Sessão inválida. "
                    "Faça login novamente."
                ),
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
            request.form.get(
                "pagamento",
                "",
            )
        ).strip().lower()

        forma_pagamento = (
            pagamentos_permitidos.get(
                pagamento_recebido
            )
        )

        if not forma_pagamento:

            flash(
                "Forma de pagamento inválida.",
                "erro",
            )

            return redirect("/vendas")

        carrinho = session.get(
            "carrinho",
            [],
        )

        if not carrinho:

            flash(
                "Carrinho vazio.",
                "erro",
            )

            return redirect("/vendas")

        tipo_desconto = request.form.get(
            "desconto_tipo",
            "nenhum",
        )

        desconto_informado = request.form.get(
            "desconto_valor",
            "0",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        conn.autocommit = False

        try:

            # =====================================
            # CAIXA ABERTO
            # =====================================

            cursor.execute(
                """
                SELECT *

                FROM caixa

                WHERE empresa_id = %s
                AND status = 'aberto'

                ORDER BY id DESC

                LIMIT 1

                FOR UPDATE
                """,
                (
                    empresa_id,
                ),
            )

            caixa = cursor.fetchone()

            if not caixa:
                raise ValueError(
                    "Nenhum caixa aberto."
                )

            # =====================================
            # PRODUTOS E VALORES REAIS
            # =====================================

            itens_processados = []
            total_bruto = Decimal("0.00")

            for item in carrinho:

                produto_id = int(
                    item["id"]
                )

                quantidade = int(
                    item["quantidade"]
                )

                if quantidade <= 0:
                    raise ValueError(
                        "Quantidade inválida."
                    )

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

                    FOR UPDATE
                    """,
                    (
                        produto_id,
                        empresa_id,
                    ),
                )

                produto = cursor.fetchone()

                if not produto:
                    raise ValueError(
                        "Produto não encontrado."
                    )

                if (
                    int(produto["estoque"])
                    < quantidade
                ):
                    raise ValueError(
                        (
                            "Estoque insuficiente para "
                            f"{produto['nome']}."
                        )
                    )

                preco_unitario = (
                    _decimal_monetario(
                        produto["preco"]
                    )
                )

                valor_bruto_item = (
                    preco_unitario
                    * quantidade
                ).quantize(
                    CENTAVOS,
                    rounding=ROUND_HALF_UP,
                )

                total_bruto += (
                    valor_bruto_item
                )

                itens_processados.append(
                    {
                        "produto": produto,
                        "quantidade": quantidade,
                        "preco_unitario": (
                            preco_unitario
                        ),
                        "valor_bruto": (
                            valor_bruto_item
                        ),
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

            # =====================================
            # DESCONTO GERAL DA VENDA
            # =====================================

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

            venda_grupo = str(
                uuid4()
            )

            desconto_restante = (
                desconto_total
            )

            vendas_cupom = []

            # =====================================
            # RATEAR DESCONTO E REGISTRAR ITENS
            # =====================================

            for indice, item in enumerate(
                itens_processados
            ):

                produto = item["produto"]
                quantidade = item["quantidade"]
                valor_bruto_item = (
                    item["valor_bruto"]
                )

                ultimo_item = (
                    indice
                    == len(itens_processados) - 1
                )

                if ultimo_item:
                    desconto_item = (
                        desconto_restante
                    )

                else:
                    desconto_item = (
                        desconto_total
                        * valor_bruto_item
                        / total_bruto
                    ).quantize(
                        CENTAVOS,
                        rounding=ROUND_HALF_UP,
                    )

                    if (
                        desconto_item
                        > desconto_restante
                    ):
                        desconto_item = (
                            desconto_restante
                        )

                desconto_restante -= (
                    desconto_item
                )

                valor_liquido_item = (
                    valor_bruto_item
                    - desconto_item
                ).quantize(
                    CENTAVOS,
                    rounding=ROUND_HALF_UP,
                )

                novo_estoque = (
                    int(produto["estoque"])
                    - quantidade
                )

                cursor.execute(
                    """
                    UPDATE produtos

                    SET estoque = %s

                    WHERE id = %s
                    AND empresa_id = %s
                    """,
                    (
                        novo_estoque,
                        produto["id"],
                        empresa_id,
                    ),
                )

                cursor.execute(
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
                        data_venda
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        produto["id"],
                        quantidade,
                        valor_liquido_item,
                        valor_bruto_item,
                        desconto_item,
                        percentual,
                        venda_grupo,
                        forma_pagamento,
                        empresa_id,
                        caixa["id"],
                        usuario_id,
                    ),
                )

                vendas_cupom.append(
                    {
                        "nome": produto["nome"],
                        "quantidade": quantidade,
                        "preco_unitario": (
                            item["preco_unitario"]
                        ),
                        "valor_bruto": (
                            valor_bruto_item
                        ),
                        "desconto": (
                            desconto_item
                        ),
                        "valor": (
                            valor_liquido_item
                        ),
                        "pagamento": (
                            forma_pagamento
                        ),
                        "empresa_id": (
                            empresa_id
                        ),
                        "venda_grupo": (
                            venda_grupo
                        ),
                    }
                )

            # =====================================
            # ATUALIZAR CAIXA PELO TOTAL LÍQUIDO
            # =====================================

            cursor.execute(
                """
                UPDATE caixa

                SET valor_final =
                    COALESCE(valor_final, 0)
                    + %s

                WHERE id = %s
                AND empresa_id = %s
                """,
                (
                    total_liquido,
                    caixa["id"],
                    empresa_id,
                ),
            )

            conn.commit()

        except ValueError as erro:

            conn.rollback()

            flash(
                str(erro),
                "erro",
            )

            return redirect("/vendas")

        except Exception as erro:

            conn.rollback()

            flash(
                (
                    "Erro ao finalizar venda: "
                    f"{erro}"
                ),
                "erro",
            )

            return redirect("/vendas")

        finally:
            cursor.close()
            conn.close()

        # =====================================
        # NOTIFICAÇÃO COM VALOR LÍQUIDO
        # =====================================

        try:
            notificar_gerente(
                usuario_id,
                "Venda realizada",
                float(total_liquido),
                empresa_id,
            )

        except Exception:
            app.logger.exception(
                "Erro ao notificar gerente."
            )

        # =====================================
        # CUPOM
        # =====================================

        pdf = gerar_cupom_venda(
            vendas_cupom,
            empresa_id,
        )

        session["carrinho"] = []
        session["ultimo_cupom"] = pdf

        flash(
            (
                "Venda finalizada. "
                f"Total bruto: R$ {total_bruto:.2f} | "
                f"Desconto: R$ {desconto_total:.2f} | "
                f"Total pago: R$ {total_liquido:.2f}"
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


