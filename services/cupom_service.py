from database import conectar, criar_cursor

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm

import os


def gerar_cupom_venda(venda_ids, empresa_id):

    conn = conectar()
    cursor = criar_cursor(conn)

    # ==========================================
    # BUSCAR EMPRESA
    # ==========================================

    cursor.execute("""
        SELECT nome
        FROM empresa
        WHERE id = %s
    """, (empresa_id,))

    empresa = cursor.fetchone()

    if not empresa:
        empresa = {"nome": "Empresa não encontrada"}

    # ==========================================
    # CRIAR PASTA DE CUPONS
    # ==========================================

    if not os.path.exists("cupons"):
        os.makedirs("cupons")

    caminho = "cupons/cupom.pdf"

    doc = SimpleDocTemplate(
        caminho,
        pagesize=(80 * mm, 300 * mm),
        leftMargin=5,
        rightMargin=5,
        topMargin=5,
        bottomMargin=5
    )

    estilos = getSampleStyleSheet()
    elementos = []

    # ==========================================
    # CABEÇALHO
    # ==========================================

    elementos.append(
        Paragraph(
            "<b>NEXUS PDV</b>",
            estilos["Title"]
        )
    )

    elementos.append(
        Paragraph(
            empresa["nome"],
            estilos["Heading3"]
        )
    )

    elementos.append(Spacer(1, 10))

    # ==========================================
    # ITENS
    # ==========================================

    total = 0

    for venda in venda_ids:
        total += venda["valor"]

        elementos.append(
            Paragraph(
                f'{venda["nome"]} ({venda["quantidade"]}x)',
                estilos["BodyText"]
            )
        )

        elementos.append(
            Paragraph(
                f'R$ {venda["valor"]:.2f}',
                estilos["BodyText"]
            )
        )

        elementos.append(Spacer(1, 3))

    # ==========================================
    # TOTAL
    # ==========================================

    elementos.append(Spacer(1, 10))

    elementos.append(
        Paragraph(
            f"<b>TOTAL: R$ {total:.2f}</b>",
            estilos["Heading2"]
        )
    )

    if venda_ids:
        elementos.append(
            Paragraph(
                f'Pagamento: {venda_ids[0]["pagamento"]}',
                estilos["BodyText"]
            )
        )

    elementos.append(Spacer(1, 15))

    # ==========================================
    # RODAPÉ
    # ==========================================

    elementos.append(
        Paragraph(
            "Obrigado pela preferência!",
            estilos["BodyText"]
        )
    )

    doc.build(elementos)

    conn.close()

    return caminho