from database import conectar, criar_cursor

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

import os


def gerar_pdf_fechamento(caixa_id):

    conn = conectar()
    cursor = criar_cursor(conn)

    # ==========================
    # DADOS DO CAIXA
    # ==========================

    cursor.execute("""
        SELECT
            caixa.*,
            empresa.nome AS empresa
        FROM caixa
        INNER JOIN empresa
            ON empresa.id = caixa.empresa_id
        WHERE caixa.id = %s
    """, (caixa_id,))

    caixa = cursor.fetchone()

    if not caixa:
        conn.close()
        return None

    # ==========================
    # PAGAMENTOS
    # ==========================

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE caixa_id = %s
        AND pagamento = 'PIX'
    """, (caixa_id,))
    total_pix = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE caixa_id = %s
        AND pagamento = 'Dinheiro'
    """, (caixa_id,))
    total_dinheiro = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE caixa_id = %s
        AND pagamento = 'Cartão'
    """, (caixa_id,))
    total_cartao = cursor.fetchone()["total"]

    # ==========================
    # ADIÇÕES
    # ==========================

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE caixa_id = %s
        AND descricao = 'Adição manual'
    """, (caixa_id,))
    total_adicoes = cursor.fetchone()["total"]

    # ==========================
    # SANGRIAS
    # ==========================

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM movimentacoes_caixa
        WHERE caixa_id = %s
        AND descricao = 'Sangria'
    """, (caixa_id,))
    total_sangrias = cursor.fetchone()["total"]

    # ==========================
    # PRODUTOS VENDIDOS
    # ==========================

    cursor.execute("""
        SELECT
            produtos.nome,
            produtos.estoque,
            vendas.quantidade,
            vendas.valor
        FROM vendas
        INNER JOIN produtos
            ON produtos.id = vendas.produto_id
        WHERE vendas.caixa_id = %s
        ORDER BY produtos.nome
    """, (caixa_id,))

    vendas = cursor.fetchall()

    # ==========================
    # TOTAIS
    # ==========================

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE caixa_id = %s
    """, (caixa_id,))
    faturamento = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COALESCE(SUM(quantidade), 0) AS total
        FROM vendas
        WHERE caixa_id = %s
    """, (caixa_id,))
    total_itens = cursor.fetchone()["total"]

    conn.close()

    # ==========================
    # GERAR PDF
    # ==========================

    if not os.path.exists("relatorios"):
        os.makedirs("relatorios")

    caminho_pdf = f"relatorios/caixa_{caixa_id}.pdf"

    doc = SimpleDocTemplate(caminho_pdf)
    elementos = []
    estilos = getSampleStyleSheet()

    # CABEÇALHO

    elementos.append(
        Paragraph("NEXUS PDV SAAS", estilos["Title"])
    )

    elementos.append(
        Paragraph(caixa["empresa"], estilos["Heading2"])
    )

    elementos.append(Spacer(1, 20))

    # INFO CAIXA

    elementos.append(
        Paragraph(f"<b>Caixa Nº:</b> {caixa['id']}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Abertura:</b> {caixa['data_abertura']}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Fechamento:</b> {caixa['data_fechamento']}", estilos["BodyText"])
    )

    elementos.append(Spacer(1, 15))

    # VALORES

    elementos.append(
        Paragraph(f"<b>Valor Inicial:</b> R$ {float(caixa['valor_inicial'] or 0):.2f}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>PIX:</b> R$ {float(total_pix):.2f}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Dinheiro:</b> R$ {float(total_dinheiro):.2f}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Cartão:</b> R$ {float(total_cartao):.2f}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Adições:</b> R$ {float(total_adicoes):.2f}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Sangrias:</b> R$ {float(total_sangrias):.2f}", estilos["BodyText"])
    )

    elementos.append(
        Paragraph(f"<b>Valor Final:</b> R$ {float(caixa['valor_final'] or 0):.2f}", estilos["BodyText"])
    )

    elementos.append(Spacer(1, 20))

    # TABELA DE PRODUTOS

    dados = [["Produto", "Qtd", "Estoque", "Valor"]]

    for venda in vendas:
        dados.append([
            venda["nome"],
            str(venda["quantidade"]),
            str(venda["estoque"]),
            f"R$ {float(venda['valor']):.2f}"
        ])

    tabela = Table(dados)

    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.black),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))

    elementos.append(tabela)

    elementos.append(Spacer(1, 20))

    # RESUMO FINAL

    elementos.append(
        Paragraph(
            f"<b>Total de itens vendidos:</b> {total_itens}",
            estilos["BodyText"]
        )
    )

    elementos.append(
        Paragraph(
            f"<b>Faturamento:</b> R$ {float(faturamento):.2f}",
            estilos["BodyText"]
        )
    )

    doc.build(elementos)

    return caminho_pdf