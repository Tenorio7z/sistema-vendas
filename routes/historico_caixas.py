from flask import *
from database import conectar
from services.pdf_service import gerar_pdf_fechamento

def registrar_rotas(app):

    @app.route("/historico_caixas")
    def historico_caixas():

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT *

        FROM caixa

        WHERE empresa_id = %s
        AND status = 'fechado'

        ORDER BY id DESC

        """, (

            session["empresa_id"],

        ))

        caixas = cursor.fetchall()

        conn.close()

        return render_template(

            "historico_caixas.html",

            caixas=caixas

        )
        
    @app.route("/historico_caixa/<int:caixa_id>")
    def historico_caixa(caixa_id):

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = conn.cursor()

        empresa_id = session["empresa_id"]

        # ==========================
        # DADOS DO CAIXA
        # ==========================

        cursor.execute("""

        SELECT *

        FROM caixa

        WHERE id = %s
        AND empresa_id = %s

        """, (

            caixa_id,
            empresa_id

        ))

        caixa = cursor.fetchone()

        if not caixa:

            conn.close()

            return redirect("/historico_caixas")

        # ==========================
        # VENDAS DO CAIXA
        # ==========================

        cursor.execute("""

        SELECT

            produtos.nome,
            vendas.quantidade,
            vendas.valor,
            vendas.pagamento

        FROM vendas

        INNER JOIN produtos
        ON produtos.id = vendas.produto_id

        WHERE vendas.caixa_id = %s

        ORDER BY vendas.id DESC

        """, (

            caixa_id,

        ))

        vendas = cursor.fetchall()

        # ==========================
        # TOTAL FATURADO
        # ==========================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE caixa_id = %s

        """, (

            caixa_id,

        ))

        total_faturado = cursor.fetchone()["total"]

        
        # ==========================
        # PIX
        # ==========================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE caixa_id = %s
        AND pagamento = 'PIX'

        """, (

            caixa_id,

        ))

        total_pix = cursor.fetchone()["total"]

        # ==========================
        # DINHEIRO
        # ==========================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE caixa_id = %s
        AND pagamento = 'Dinheiro'

        """, (

            caixa_id,

        ))

        total_dinheiro = cursor.fetchone()["total"]

        # ==========================
        # CARTÃO
        # ==========================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE caixa_id = %s
        AND pagamento = 'Cartão'

        """, (

            caixa_id,

        ))

        total_cartao = cursor.fetchone()["total"]
        
        # ==========================
        # TOTAL ITENS
        # ==========================

        cursor.execute("""

        SELECT COALESCE(SUM(quantidade),0) as total

        FROM vendas

        WHERE caixa_id = %s

        """, (

            caixa_id,

        ))

        total_itens = cursor.fetchone()["total"]

        conn.close()

        

        return render_template(

        "historico_caixa.html",

        caixa=caixa,

        vendas=vendas,

        total_faturado=total_faturado,

        total_itens=total_itens,

        total_pix=total_pix,

        total_dinheiro=total_dinheiro,

        total_cartao=total_cartao

    ) 
        
    @app.route("/relatorio_caixa/<int:caixa_id>")
    def relatorio_caixa(caixa_id):

        if not session.get("logado"):
            return redirect("/")

        pdf = gerar_pdf_fechamento(caixa_id)

    

        import os

      

        return send_file(
            pdf,
            as_attachment=False
        )