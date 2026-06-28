from flask import *
from database import conectar, criar_cursor

def registrar_rotas(app):

    @app.route("/dashboard")
    def dashboard():

        if not session.get("logado"):

            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session.get("empresa_id")
        if not empresa_id:
            conn.close()
            return redirect("/")

        # PRODUTOS

        cursor.execute("""

        SELECT COUNT(*) as total
        FROM produtos

        WHERE empresa_id = %s

        """, (empresa_id,))

        total_produtos = cursor.fetchone()["total"]

        

        # EMPRESA

        cursor.execute("""

        SELECT *

        FROM empresa

        WHERE id = %s

        """, (empresa_id,))

        empresa = cursor.fetchone()

        # CAIXA

        cursor.execute("""

        SELECT *

        FROM caixa

        WHERE empresa_id = %s
        AND status = 'aberto'

        ORDER BY id DESC

        LIMIT 1

        """, (empresa_id,))

        caixa_aberto = cursor.fetchone()

       
        
        if caixa_aberto:

            caixa_id = caixa_aberto["id"]

        else:

            caixa_id = None


        if caixa_id:

            cursor.execute("""

            SELECT
                COUNT(*) as total_vendas,
                COALESCE(SUM(valor), 0) as faturamento,
                COALESCE(SUM(quantidade), 0) as itens_vendidos

            FROM vendas

            WHERE caixa_id = %s
            AND cancelada = 0

            """, (caixa_id,))

            dados = cursor.fetchone()

            total_vendas = dados["total_vendas"]
            faturamento = dados["faturamento"]
            itens_vendidos = dados["itens_vendidos"]

            clientes_atendidos = total_vendas

        else:

            total_vendas = 0
            faturamento = 0
            itens_vendidos = 0
            clientes_atendidos = 0

        # ALERTAS

        cursor.execute("""

        SELECT nome, estoque

        FROM produtos

        WHERE empresa_id = %s
        AND estoque <= 5

        ORDER BY estoque ASC

        """, (empresa_id,))

        produtos_alerta = cursor.fetchall()

        alertas = []

        for produto in produtos_alerta:

            alertas.append(
                f'{produto["nome"]} com apenas {produto["estoque"]} unidades'
            )

        ultimos_7_dias = []

        conn.close()

        return render_template(

            "dashboard.html",

            usuario=session.get("usuario"),

            total_produtos=total_produtos,

            total_vendas=total_vendas,

            faturamento=faturamento,

            empresa=empresa,

            caixa_aberto=caixa_aberto,

            clientes_atendidos=clientes_atendidos,

            itens_vendidos=itens_vendidos,

            ultimos_7_dias=ultimos_7_dias,

            alertas=alertas

        )
        
    @app.route("/api/dashboard")
    def api_dashboard():

        if not session.get("logado"):
            return jsonify({"erro": "não autorizado"})

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session.get("empresa_id")
        if not empresa_id:
            conn.close()
            return jsonify({"erro": "empresa não encontrada"})

        cursor.execute("""

        SELECT id

        FROM caixa

        WHERE empresa_id = %s
        AND status = 'aberto'

        ORDER BY id DESC

        LIMIT 1

        """, (empresa_id,))

        caixa = cursor.fetchone()

        if caixa:

            caixa_id = caixa["id"]

            cursor.execute("""

            SELECT
                COUNT(*) as total_vendas,
                COALESCE(SUM(valor), 0) as faturamento,
                COALESCE(SUM(quantidade), 0) as itens_vendidos

            FROM vendas

            WHERE caixa_id = %s
            AND cancelada = 0

            """, (caixa_id,))

            dados = cursor.fetchone()

            total_vendas = dados["total_vendas"]
            faturamento = dados["faturamento"]
            itens_vendidos = dados["itens_vendidos"]

            clientes_atendidos = total_vendas

        else:

            total_vendas = 0
            faturamento = 0
            itens_vendidos = 0
            clientes_atendidos = 0

        conn.close()

        return jsonify({

            "total_vendas": total_vendas,
            "faturamento": faturamento,
            "clientes_atendidos": clientes_atendidos,
            "itens_vendidos": itens_vendidos

        })