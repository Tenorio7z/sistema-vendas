from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from database import conectar, criar_cursor


AZUL = colors.HexColor("#2563EB")
AZUL_ESCURO = colors.HexColor("#14213D")
AZUL_CLARO = colors.HexColor("#EAF2FF")
CINZA_FUNDO = colors.HexColor("#F5F7FB")
CINZA_BORDA = colors.HexColor("#DCE4EF")
CINZA_TEXTO = colors.HexColor("#64748B")
VERDE = colors.HexColor("#059669")
VERMELHO = colors.HexColor("#DC3545")
BRANCO = colors.white


def moeda(valor):
    numero = float(valor or 0)

    texto = f"{numero:,.2f}"

    texto = (
        texto
        .replace(",", "TEMP")
        .replace(".", ",")
        .replace("TEMP", ".")
    )

    return f"R$ {texto}"


def data_hora(valor):
    if not valor:
        return "Não informado"

    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y às %H:%M")

    return str(valor)


def desenhar_pagina(canvas, documento):
    canvas.saveState()

    largura, altura = A4

    canvas.setFillColor(AZUL_ESCURO)
    canvas.rect(
        0,
        altura - 18 * mm,
        largura,
        18 * mm,
        stroke=0,
        fill=1,
    )

    canvas.setFillColor(BRANCO)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(
        18 * mm,
        altura - 11 * mm,
        "NEXUS PDV",
    )

    canvas.setFillColor(colors.HexColor("#BFD4FF"))
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        largura - 18 * mm,
        altura - 11 * mm,
        "Relatório de fechamento de caixa",
    )

    canvas.setStrokeColor(CINZA_BORDA)
    canvas.line(
        18 * mm,
        14 * mm,
        largura - 18 * mm,
        14 * mm,
    )

    canvas.setFillColor(CINZA_TEXTO)
    canvas.setFont("Helvetica", 7)

    canvas.drawString(
        18 * mm,
        9 * mm,
        "Documento gerado pelo Nexus PDV",
    )

    canvas.drawRightString(
        largura - 18 * mm,
        9 * mm,
        f"Página {documento.page}",
    )

    canvas.restoreState()


def gerar_pdf_fechamento(
    caixa_id,
    empresa_id,
):
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT
                c.*,
                e.nome AS empresa
            FROM caixa c

            INNER JOIN empresa e
                ON e.id = c.empresa_id

            WHERE c.id = %s
              AND c.empresa_id = %s
            """,
            (
                caixa_id,
                empresa_id,
            )
        )

        caixa = cursor.fetchone()

        if not caixa:
            return None

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(v.valor),
                    0
                ) AS faturamento,

                COALESCE(
                    SUM(v.quantidade),
                    0
                ) AS total_itens,

                COALESCE(
                    SUM(v.valor)
                    FILTER (
                        WHERE UPPER(v.pagamento) = 'PIX'
                    ),
                    0
                ) AS total_pix,

                COALESCE(
                    SUM(v.valor)
                    FILTER (
                        WHERE LOWER(v.pagamento) = 'dinheiro'
                    ),
                    0
                ) AS total_dinheiro,

                COALESCE(
                    SUM(v.valor)
                    FILTER (
                        WHERE LOWER(v.pagamento)
                        IN (
                            'cartão',
                            'cartao'
                        )
                    ),
                    0
                ) AS total_cartao

            FROM vendas v

            WHERE v.caixa_id = %s
              AND v.empresa_id = %s
              AND v.cancelada = 0
            """,
            (
                caixa_id,
                empresa_id,
            )
        )

        totais = cursor.fetchone() or {}

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(valor)
                    FILTER (
                        WHERE descricao = 'Adição manual'
                    ),
                    0
                ) AS total_adicoes,

                COALESCE(
                    SUM(valor)
                    FILTER (
                        WHERE descricao = 'Sangria'
                    ),
                    0
                ) AS total_sangrias

            FROM movimentacoes_caixa

            WHERE caixa_id = %s
            """,
            (
                caixa_id,
            )
        )

        movimentacoes = cursor.fetchone() or {}

        cursor.execute(
            """
            SELECT
                p.nome,
                v.quantidade,
                v.valor,
                v.pagamento

            FROM vendas v

            INNER JOIN produtos p
                ON p.id = v.produto_id
               AND p.empresa_id = v.empresa_id

            WHERE v.caixa_id = %s
              AND v.empresa_id = %s
              AND v.cancelada = 0

            ORDER BY
                p.nome,
                v.id
            """,
            (
                caixa_id,
                empresa_id,
            )
        )

        vendas = cursor.fetchall() or []

    finally:
        cursor.close()
        conn.close()

    pasta = Path("relatorios")
    pasta.mkdir(
        parents=True,
        exist_ok=True,
    )

    caminho_pdf = (
        pasta
        / f"fechamento_caixa_{empresa_id}_{caixa_id}.pdf"
    )

    documento = SimpleDocTemplate(
        str(caminho_pdf),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=27 * mm,
        bottomMargin=20 * mm,
        title=f"Fechamento do Caixa #{caixa_id}",
        author="Nexus PDV",
        subject="Relatório de fechamento de caixa",
    )

    estilos_base = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "TituloNexus",
        parent=estilos_base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=AZUL_ESCURO,
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    subtitulo = ParagraphStyle(
        "SubtituloNexus",
        parent=estilos_base["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=12,
        textColor=CINZA_TEXTO,
        spaceAfter=14,
    )

    titulo_secao = ParagraphStyle(
        "TituloSecao",
        parent=estilos_base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=AZUL_ESCURO,
        spaceBefore=6,
        spaceAfter=8,
    )

    texto_normal = ParagraphStyle(
        "TextoNormal",
        parent=estilos_base["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=AZUL_ESCURO,
    )

    texto_pequeno = ParagraphStyle(
        "TextoPequeno",
        parent=texto_normal,
        fontSize=7,
        leading=9,
        textColor=CINZA_TEXTO,
    )

    texto_direita = ParagraphStyle(
        "TextoDireita",
        parent=texto_normal,
        alignment=TA_RIGHT,
    )

    elementos = []

    elementos.append(
        Paragraph(
            f"Fechamento do Caixa #{caixa['id']}",
            titulo,
        )
    )

    elementos.append(
        Paragraph(
            escape(str(caixa["empresa"])),
            subtitulo,
        )
    )

    periodo = [
        [
            Paragraph(
                "<b>Abertura</b><br/>"
                + escape(data_hora(caixa["data_abertura"])),
                texto_normal,
            ),
            Paragraph(
                "<b>Fechamento</b><br/>"
                + escape(data_hora(caixa["data_fechamento"])),
                texto_normal,
            ),
            Paragraph(
                "<b>Status</b><br/>Encerrado",
                texto_normal,
            ),
        ]
    ]

    tabela_periodo = Table(
        periodo,
        colWidths=[
            58 * mm,
            58 * mm,
            42 * mm,
        ],
    )

    tabela_periodo.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, -1),
                CINZA_FUNDO,
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.6,
                CINZA_BORDA,
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.4,
                CINZA_BORDA,
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                10,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                10,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                9,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                9,
            ),
        ])
    )

    elementos.append(tabela_periodo)
    elementos.append(Spacer(1, 7 * mm))

    elementos.append(
        Paragraph(
            "Resumo financeiro",
            titulo_secao,
        )
    )

    resumo = [
        [
            Paragraph("Valor inicial", texto_pequeno),
            Paragraph(
                moeda(caixa["valor_inicial"]),
                texto_direita,
            ),
            Paragraph("Faturamento", texto_pequeno),
            Paragraph(
                moeda(totais.get("faturamento")),
                texto_direita,
            ),
        ],
        [
            Paragraph("PIX", texto_pequeno),
            Paragraph(
                moeda(totais.get("total_pix")),
                texto_direita,
            ),
            Paragraph("Dinheiro", texto_pequeno),
            Paragraph(
                moeda(totais.get("total_dinheiro")),
                texto_direita,
            ),
        ],
        [
            Paragraph("Cartão", texto_pequeno),
            Paragraph(
                moeda(totais.get("total_cartao")),
                texto_direita,
            ),
            Paragraph("Itens vendidos", texto_pequeno),
            Paragraph(
                str(totais.get("total_itens") or 0),
                texto_direita,
            ),
        ],
        [
            Paragraph("Adições", texto_pequeno),
            Paragraph(
                moeda(movimentacoes.get("total_adicoes")),
                texto_direita,
            ),
            Paragraph("Sangrias", texto_pequeno),
            Paragraph(
                moeda(movimentacoes.get("total_sangrias")),
                texto_direita,
            ),
        ],
        [
            Paragraph(
                "<b>Valor final</b>",
                texto_normal,
            ),
            Paragraph(
                "<b>"
                + moeda(caixa["valor_final"])
                + "</b>",
                texto_direita,
            ),
            "",
            "",
        ],
    ]

    tabela_resumo = Table(
        resumo,
        colWidths=[
            35 * mm,
            44 * mm,
            35 * mm,
            44 * mm,
        ],
    )

    tabela_resumo.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, -2),
                CINZA_FUNDO,
            ),
            (
                "BACKGROUND",
                (0, -1),
                (1, -1),
                AZUL_CLARO,
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.6,
                CINZA_BORDA,
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.35,
                CINZA_BORDA,
            ),
            (
                "SPAN",
                (2, -1),
                (3, -1),
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE",
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                8,
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7,
            ),
        ])
    )

    elementos.append(tabela_resumo)
    elementos.append(Spacer(1, 7 * mm))

    elementos.append(
        Paragraph(
            "Produtos vendidos",
            titulo_secao,
        )
    )

    dados_vendas = [[
        Paragraph("<b>Produto</b>", texto_normal),
        Paragraph("<b>Qtd.</b>", texto_normal),
        Paragraph("<b>Pagamento</b>", texto_normal),
        Paragraph("<b>Total</b>", texto_direita),
    ]]

    for venda in vendas:
        dados_vendas.append([
            Paragraph(
                escape(str(venda["nome"])),
                texto_normal,
            ),
            Paragraph(
                str(venda["quantidade"]),
                texto_normal,
            ),
            Paragraph(
                escape(str(venda["pagamento"])),
                texto_normal,
            ),
            Paragraph(
                moeda(venda["valor"]),
                texto_direita,
            ),
        ])

    if not vendas:
        dados_vendas.append([
            Paragraph(
                "Nenhuma venda registrada neste caixa.",
                texto_pequeno,
            ),
            "",
            "",
            "",
        ])

    tabela_vendas = Table(
        dados_vendas,
        colWidths=[
            72 * mm,
            18 * mm,
            36 * mm,
            32 * mm,
        ],
        repeatRows=1,
    )

    estilo_tabela = [
        (
            "BACKGROUND",
            (0, 0),
            (-1, 0),
            AZUL_ESCURO,
        ),
        (
            "TEXTCOLOR",
            (0, 0),
            (-1, 0),
            BRANCO,
        ),
        (
            "BOX",
            (0, 0),
            (-1, -1),
            0.6,
            CINZA_BORDA,
        ),
        (
            "INNERGRID",
            (0, 1),
            (-1, -1),
            0.3,
            CINZA_BORDA,
        ),
        (
            "VALIGN",
            (0, 0),
            (-1, -1),
            "MIDDLE",
        ),
        (
            "LEFTPADDING",
            (0, 0),
            (-1, -1),
            7,
        ),
        (
            "RIGHTPADDING",
            (0, 0),
            (-1, -1),
            7,
        ),
        (
            "TOPPADDING",
            (0, 0),
            (-1, -1),
            7,
        ),
        (
            "BOTTOMPADDING",
            (0, 0),
            (-1, -1),
            7,
        ),
    ]

    for linha in range(
        1,
        len(dados_vendas)
    ):
        if linha % 2 == 0:
            estilo_tabela.append(
                (
                    "BACKGROUND",
                    (0, linha),
                    (-1, linha),
                    CINZA_FUNDO,
                )
            )

    if not vendas:
        estilo_tabela.append(
            (
                "SPAN",
                (0, 1),
                (-1, 1),
            )
        )

    tabela_vendas.setStyle(
        TableStyle(estilo_tabela)
    )

    elementos.append(tabela_vendas)

    documento.build(
        elementos,
        onFirstPage=desenhar_pagina,
        onLaterPages=desenhar_pagina,
    )

    return str(caminho_pdf)