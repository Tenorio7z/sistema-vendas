from flask import *
from database import conectar, criar_cursor
from services.cupom_service import gerar_cupom_venda
from services.notificacoes import notificar_gerente
from services.fcm_services import enviar_notificacao

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

        empresa_id = session.get("empresa_id")
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
        cursor.execute("""
            SELECT *
            FROM produtos
            WHERE empresa_id = %s
        """, (empresa_id,))

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

        empresa_id = session.get("empresa_id")

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


    @app.route("/finalizar_venda", methods=["POST"])
    def finalizar_venda():

        if not session.get("logado"):
            return redirect("/")

        forma_pagamento = request.form["pagamento"]
        carrinho = session.get("carrinho", [])

        if not carrinho:
            flash("Carrinho vazio", "erro")
            return redirect("/vendas")

        conn = conectar()
        cursor = criar_cursor(conn)

        # ==========================================
        # BUSCAR CAIXA ABERTO
        # ==========================================
        
        empresa_id = session.get("empresa_id")

        if not empresa_id:
            conn.close()
            return redirect("/")
        
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
            flash("Nenhum caixa aberto", "erro")
            return redirect("/vendas")

        valor_venda = 0
        vendas_cupom = []

        # ==========================================
        # PROCESSAR ITENS DO CARRINHO
        # ==========================================
        try:
            for item in carrinho:

                cursor.execute("""
                    SELECT *
                    FROM produtos
                    WHERE id = %s
                    AND empresa_id = %s
                    FOR UPDATE
                """, (item["id"], empresa_id))

                produto = cursor.fetchone()

                if not produto:
                    conn.rollback()
                    conn.close()
                    flash("Produto não encontrado", "erro")
                    return redirect("/vendas")

                if produto["estoque"] < item["quantidade"]:
                    conn.rollback()
                    conn.close()
                    flash(f'Estoque insuficiente para {produto["nome"]}', "erro")
                    return redirect("/vendas")
                
                novo_estoque = produto["estoque"] - item["quantidade"]
                valor_total = float(item["preco"]) * int(item["quantidade"])

                valor_venda += valor_total

                # ==========================================
                # ATUALIZAR ESTOQUE
                # ==========================================
                
                cursor.execute("""
                    UPDATE produtos
                    SET estoque = %s
                    WHERE id = %s
                    AND empresa_id = %s
                """, (novo_estoque, item["id"], empresa_id))

                # ==========================================
                # REGISTRAR VENDA
                # ==========================================
                cursor.execute("""
                INSERT INTO vendas (
                    produto_id,
                    quantidade,
                    valor,
                    pagamento,
                    empresa_id,
                    caixa_id,
                    usuario_id
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                """, (
                item["id"],
                item["quantidade"],
                valor_total,
                forma_pagamento,
                empresa_id,
                caixa["id"],
                session["usuario_id"]
                ))

                vendas_cupom.append({
                    "nome": produto["nome"],
                    "quantidade": item["quantidade"],
                    "valor": valor_total,
                    "pagamento": forma_pagamento,
                    "empresa_id": empresa_id
                })
                
                
        except Exception as e:
            conn.rollback()
            conn.close()
            flash(f"Erro ao finalizar venda: {str(e)}", "erro")
            return redirect("/vendas")
        
        
        # ==========================================
        # ATUALIZAR CAIXA
        # ==========================================
        cursor.execute("""
            UPDATE caixa
            SET valor_final = COALESCE(valor_final, 0) + %s
            WHERE id = %s
        """, (valor_venda, caixa["id"]))

        conn.commit()

        # ==========================================
        # NOTIFICAÇÃO GERENTE (CORRIGIDA)
        # ==========================================
        notificar_gerente(
            session["usuario_id"],
            "Venda realizada",
            valor_venda,
            empresa_id
        )

        # ==========================================
        # PUSH NOTIFICATION
        # ==========================================
        cursor.execute("""
            SELECT fcm_token
            FROM usuarios
            WHERE empresa_id = %s
            AND nivel = 'gerente'
            LIMIT 1
        """, (empresa_id,))

        gerente = cursor.fetchone()

        if gerente and gerente["fcm_token"]:
            enviar_notificacao(
                gerente["fcm_token"],
                "Nova Venda",
                f'{session["usuario"]} realizou uma venda de R$ {valor_venda:.2f}'
            )

        conn.close()

        # ==========================================
        # CUPOM
        # ==========================================
        pdf = gerar_cupom_venda(vendas_cupom, empresa_id)

        session["carrinho"] = []
        session["ultimo_cupom"] = pdf

        flash("Venda finalizada", "sucesso")

        return redirect("/vendas")
        
        
    @app.route("/codigo/<codigo>")
    def codigo(codigo):

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session.get("empresa_id")

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


