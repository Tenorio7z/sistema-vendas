from flask import *
from database import conectar, criar_cursor

def registrar_rotas(app):

    @app.route("/estatisticas")
    def estatisticas():

        if not session.get("logado"):
            return redirect("/")

        if session["plano"] == "comum":

            return render_template(
                "estatisticas.html",
                bloqueado=True,
                labels=[],
                valores=[]
)

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session["empresa_id"]

        # ==========================================
        # TOTAL DE VENDAS
        # ==========================================

        cursor.execute("""

        SELECT COUNT(*) as total

        FROM vendas

        WHERE empresa_id = %s

        """, (

            empresa_id,

        ))

        total_vendas = cursor.fetchone()["total"]

        # ==========================================
        # FATURAMENTO TOTAL
        # ==========================================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE empresa_id = %s

        """, (

            empresa_id,

        ))

        faturamento = cursor.fetchone()["total"]

        # ==========================================
        # FATURAMENTO HOJE
        # ==========================================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE empresa_id = %s
        AND DATE(data) = CURRENT_DATE

        """, (

            empresa_id,

        ))

        faturamento_dia = cursor.fetchone()["total"]

        # ==========================================
        # FATURAMENTO MÊS
        # ==========================================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE empresa_id = %s
        AND TO_CHAR(data, 'YYYY-MM') = TO_CHAR(NOW(), 'YYYY-MM')

        """, (

            empresa_id,

        ))

        faturamento_mes = cursor.fetchone()["total"]

        # ==========================================
        # FATURAMENTO ANO
        # ==========================================

        cursor.execute("""

        SELECT COALESCE(SUM(valor),0) as total

        FROM vendas

        WHERE empresa_id = %s
        AND TO_CHAR(data, 'YYYY') = TO_CHAR(NOW(), 'YYYY')

        """, (

            empresa_id,

        ))

        faturamento_ano = cursor.fetchone()["total"]

        # ==========================================
        # TICKET MÉDIO
        # ==========================================

        ticket_medio = 0

        if total_vendas > 0:

            ticket_medio = round(
                faturamento / total_vendas,
                2
            )

        # ==========================================
        # PRODUTO MAIS VENDIDO
        # ==========================================

        cursor.execute("""

        SELECT

            produtos.nome,
            COUNT(vendas.id) as quantidade

        FROM vendas

        INNER JOIN produtos
        ON produtos.id = vendas.produto_id

        WHERE vendas.empresa_id = %s

        GROUP BY produtos.nome

        ORDER BY quantidade DESC

        LIMIT 1

        """, (

            empresa_id,

        ))

        produto_top = cursor.fetchone()

        if produto_top:

            produto_top = produto_top["nome"]

        else:

            produto_top = "Nenhum"

        # ==========================================
        # GRÁFICO
        # ==========================================

        cursor.execute("""

        SELECT

            DATE(data) as dia,
            SUM(valor) as total

        FROM vendas

        WHERE empresa_id = %s

        GROUP BY DATE(data)

        ORDER BY DATE(data)

        """, (

            empresa_id,

        ))

        dados_grafico = cursor.fetchall()

        labels = []
        valores = []

        for item in dados_grafico:

            labels.append(item["dia"])
            valores.append(item["total"])

        conn.close()

        return render_template(

            "estatisticas.html",

            bloqueado=False,

            total_vendas=total_vendas,

            faturamento=faturamento,

            faturamento_dia=faturamento_dia,

            faturamento_mes=faturamento_mes,

            faturamento_ano=faturamento_ano,

            ticket_medio=ticket_medio,

            produto_top=produto_top,

            labels=labels,

            valores=valores

        )