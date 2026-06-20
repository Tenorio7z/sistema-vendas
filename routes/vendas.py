from flask import *
from database import conectar
from services.cupom_service import gerar_cupom_venda
from datetime import datetime
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
        cursor = conn.cursor()

        empresa_id = session["empresa_id"]

        cursor.execute(
            """

        SELECT *

        FROM caixa

        WHERE empresa_id = ?
        AND status = 'aberto'

        ORDER BY id DESC

        LIMIT 1

        """,
            (empresa_id,),
        )

        caixa = cursor.fetchone()

        if not caixa:

            conn.close()

            return render_template("vendas.html", caixa_fechado=True)

        cursor.execute(
            """

        SELECT *

        FROM produtos

        WHERE empresa_id = ?

        """,
            (empresa_id,),
        )

        produtos = cursor.fetchall()

        carrinho = session.get("carrinho", [])

        total = sum(item["preco"] * item["quantidade"] for item in carrinho)
        
       

        cursor.execute(
            """

        SELECT id

        FROM caixa

        WHERE empresa_id = ?
        AND status = 'aberto'

        ORDER BY id DESC

        LIMIT 1

        """,
            (session["empresa_id"],),
        )

        caixa = cursor.fetchone()

        if not caixa:

            flash("Nenhum caixa aberto", "erro")

        
            return redirect("/vendas")
        
        conn.close()

        abrir_cupom = False

        if session.get("ultimo_cupom"):
            
            abrir_cupom = True
        
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
        cursor = conn.cursor()

        cursor.execute(
            """

        SELECT *

        FROM produtos

        WHERE id = ?
        AND empresa_id = ?

        """,
            (id, session["empresa_id"]),
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
        cursor = conn.cursor()

        # ==========================================
        # BUSCAR CAIXA ABERTO
        # ==========================================

        cursor.execute(
            """

        SELECT *

        FROM caixa

        WHERE empresa_id = ?
        AND status = 'aberto'

        ORDER BY id DESC

        LIMIT 1

        """,
            (session["empresa_id"],),
        )

        caixa = cursor.fetchone()

        if not caixa:

            conn.close()

            flash("Nenhum caixa aberto", "erro")

            return redirect("/vendas")

        valor_venda = 0

        vendas_cupom = []
        
        # ==========================================
        # PROCESSAR ITENS
        # ==========================================

        for item in carrinho:

            cursor.execute(
                """

            SELECT *

            FROM produtos

            WHERE id = ?
            AND empresa_id = ?

            """,
                (item["id"], session["empresa_id"]),
            )

            produto = cursor.fetchone()

            if not produto:
                continue

            if produto["estoque"] < item["quantidade"]:

                flash(f'Estoque insuficiente para {produto["nome"]}', "erro")

                conn.close()

                return redirect("/vendas")

            novo_estoque = produto["estoque"] - item["quantidade"]

            valor_total = item["preco"] * item["quantidade"]

            valor_venda += valor_total
            
            # Atualiza estoque

            cursor.execute(
                """

            UPDATE produtos

            SET estoque = ?

            WHERE id = ?

            """,
                (novo_estoque, item["id"]),
            )

            # Registra venda

            cursor.execute(
                """

            INSERT INTO vendas(

                produto_id,
                quantidade,
                valor,
                pagamento,
                empresa_id,
                caixa_id,
                usuario_id,
                data_venda

            )

            VALUES(?,?,?,?,?,?,?,?)

            """,
                (
                    item["id"],
                    item["quantidade"],
                    valor_total,
                    forma_pagamento,
                    session["empresa_id"],  
                    caixa["id"],
                    session["usuario"],
                    datetime.now()
                ),
            )
            
            vendas_cupom.append({

                    "nome": produto["nome"],
                    "quantidade": item["quantidade"],
                    "valor": valor_total,
                    "pagamento": forma_pagamento,
                    "empresa_id": session["empresa_id"]

                })
            
        # ==========================================
        # SOMAR AO CAIXA
        # ==========================================

        cursor.execute(
            """

        UPDATE caixa

        SET valor_final = valor_final + ?

        WHERE id = ?

        """,
            (valor_venda, caixa["id"]),
        )

        conn.commit()
        
        notificar_gerente(
                session["usuario"],
                produto["nome"],
                valor_total,
                session["empresa_id"]
            )
        
        # ==========================================
        # ENVIAR PUSH PARA GERENTE
        # ==========================================

        cursor.execute("""

        SELECT fcm_token

        FROM usuarios

        WHERE empresa_id = ?
        AND nivel = 'gerente'

        LIMIT 1

        """, (session["empresa_id"],))

        gerente = cursor.fetchone()

        if gerente and gerente["fcm_token"]:

            enviar_notificacao(

                gerente["fcm_token"],

                "Nova Venda",

                f'{session["usuario"]} vendeu {produto["nome"]} por R$ {valor_total:.2f}'

            )
        
        socketio.emit(
            "nova_venda",
            {
                "produto": produto["nome"],
                "valor": valor_total,
                "usuario": session["usuario"],
                "empresa_id": session["empresa_id"]
            }
        )
        
        socketio.emit(
            "nova_notificacao",
            {
                "produto": produto["nome"],
                "valor": valor_total,
                "funcionario": session["usuario"],
                "empresa_id": session["empresa_id"]
            }
        )
        
        conn.close()

      

        # LIMPA O CARRINHO IMEDIATAMENTE
        pdf = gerar_cupom_venda(vendas_cupom)

        session["carrinho"] = []
        session["ultimo_cupom"] = pdf

        flash("Venda finalizada", "sucesso")

        return redirect("/vendas")
        
        
    @app.route("/codigo/<codigo>")
    def codigo(codigo):

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute(
            """

            SELECT *

            FROM produtos

            WHERE codigo_barras = ?
            AND empresa_id = ?

            """,
            (codigo, session["empresa_id"]),
        )

        produto = cursor.fetchone()

        conn.close()

        if not produto:

            flash("Produto não cadastrado", "erro")

            return redirect("/vendas")

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


