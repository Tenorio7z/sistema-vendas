from database import conectar, criar_cursor

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm


# =========================================================
# CONFIGURAÇÃO DA IMPRESSORA
# =========================================================

# O driver da POS58 trabalha com página de 48 mm.
LARGURA_PAPEL = 48 * mm

# Margem mínima apenas para o texto não ser cortado.
MARGEM_LATERAL = 2 * mm

# 48 mm menos 2 mm de cada lado.
LARGURA_UTIL = 44 * mm

FONTE_NORMAL = "Helvetica"
FONTE_NEGRITO = "Helvetica-Bold"

CENTAVOS = Decimal("0.01")


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def _decimal(valor):
    try:
        return Decimal(
            str(
                valor
                if valor is not None
                else "0"
            )
        ).quantize(CENTAVOS)

    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return Decimal("0.00")


def _moeda(valor):
    valor = _decimal(valor)

    texto = f"{valor:,.2f}"

    texto = (
        texto
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return f"R$ {texto}"


def _texto(valor, padrao=""):
    if valor is None:
        return padrao

    texto = str(valor).strip()

    return texto or padrao


def _quebrar_palavra(
    palavra,
    fonte,
    tamanho,
    largura_maxima,
):
    partes = []
    parte_atual = ""

    for caractere in palavra:
        teste = parte_atual + caractere

        largura = stringWidth(
            teste,
            fonte,
            tamanho,
        )

        if largura <= largura_maxima:
            parte_atual = teste

        else:
            if parte_atual:
                partes.append(parte_atual)

            parte_atual = caractere

    if parte_atual:
        partes.append(parte_atual)

    return partes


def _quebrar_texto(
    texto,
    fonte,
    tamanho,
    largura_maxima,
):
    texto = _texto(texto)

    if not texto:
        return [""]

    palavras = texto.split()
    linhas = []
    linha_atual = ""

    for palavra in palavras:
        if (
            stringWidth(
                palavra,
                fonte,
                tamanho,
            )
            > largura_maxima
        ):
            if linha_atual:
                linhas.append(linha_atual)
                linha_atual = ""

            partes = _quebrar_palavra(
                palavra,
                fonte,
                tamanho,
                largura_maxima,
            )

            linhas.extend(partes[:-1])

            if partes:
                linha_atual = partes[-1]

            continue

        teste = (
            palavra
            if not linha_atual
            else f"{linha_atual} {palavra}"
        )

        largura = stringWidth(
            teste,
            fonte,
            tamanho,
        )

        if largura <= largura_maxima:
            linha_atual = teste

        else:
            if linha_atual:
                linhas.append(linha_atual)

            linha_atual = palavra

    if linha_atual:
        linhas.append(linha_atual)

    return linhas or [""]


def _linha_tracejada(
    pdf,
    esquerda,
    direita,
    y,
):
    pdf.saveState()

    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(0.45)
    pdf.setDash(2, 2)

    pdf.line(
        esquerda,
        y,
        direita,
        y,
    )

    pdf.restoreState()

    return y - (2.3 * mm)


def _linha_continua(
    pdf,
    esquerda,
    direita,
    y,
    espessura=0.7,
):
    pdf.saveState()

    pdf.setStrokeColorRGB(0, 0, 0)
    pdf.setLineWidth(espessura)
    pdf.setDash()

    pdf.line(
        esquerda,
        y,
        direita,
        y,
    )

    pdf.restoreState()

    return y - (2.3 * mm)


def _desenhar_texto_quebrado(
    pdf,
    texto,
    x,
    y,
    largura,
    fonte=FONTE_NORMAL,
    tamanho=6.3,
    entrelinha=2.8 * mm,
):
    linhas = _quebrar_texto(
        texto,
        fonte,
        tamanho,
        largura,
    )

    pdf.setFont(
        fonte,
        tamanho,
    )

    for linha in linhas:
        pdf.drawString(
            x,
            y,
            linha,
        )

        y -= entrelinha

    return y


def _altura_necessaria(vendas):
    altura = 83 * mm

    primeira_venda = vendas[0]

    if primeira_venda.get("cliente_nome"):
        altura += 15 * mm

    possui_desconto = any(
        _decimal(venda.get("desconto")) > 0
        for venda in vendas
    )

    if possui_desconto:
        altura += 5 * mm

    largura_nome = 30 * mm

    for venda in vendas:
        linhas_nome = _quebrar_texto(
            venda.get("nome", "Produto"),
            FONTE_NEGRITO,
            6.4,
            largura_nome,
        )

        altura += (
            len(linhas_nome) * 2.8 * mm
            + 6.5 * mm
        )

    return max(
        altura,
        105 * mm,
    )


# =========================================================
# GERAÇÃO DO CUPOM
# =========================================================

def gerar_cupom_venda(
    venda_ids,
    empresa_id,
):
    if not venda_ids:
        raise ValueError(
            "Nenhum item foi informado para gerar o cupom."
        )

    conn = None
    cursor = None

    try:
        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute(
            """
            SELECT nome
            FROM empresa
            WHERE id = %s
            LIMIT 1
            """,
            (empresa_id,),
        )

        empresa = cursor.fetchone()

        nome_empresa = (
            empresa["nome"]
            if empresa
            else "Nexus PDV"
        )

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()

    # Cada venda recebe um arquivo diferente.
    pasta_cupons = Path("cupons")

    pasta_cupons.mkdir(
        parents=True,
        exist_ok=True,
    )

    venda_grupo = _texto(
        venda_ids[0].get("venda_grupo"),
        str(uuid4()),
    )

    identificador_seguro = "".join(
        caractere
        for caractere in venda_grupo
        if (
            caractere.isalnum()
            or caractere in "-_"
        )
    )

    caminho = pasta_cupons / (
        f"cupom_{empresa_id}_"
        f"{identificador_seguro}.pdf"
    )

    altura_papel = _altura_necessaria(
        venda_ids
    )

    pdf = canvas.Canvas(
        str(caminho),
        pagesize=(
            LARGURA_PAPEL,
            altura_papel,
        ),
        pageCompression=1,
    )

    pdf.setTitle("Cupom de venda")
    pdf.setAuthor("Nexus PDV")
    pdf.setCreator("Nexus PDV")

    esquerda = MARGEM_LATERAL
    direita = (
        LARGURA_PAPEL
        - MARGEM_LATERAL
    )

    centro = LARGURA_PAPEL / 2

    y = altura_papel - (5 * mm)

    # =====================================================
    # CABEÇALHO
    # =====================================================

    linhas_empresa = _quebrar_texto(
        nome_empresa,
        FONTE_NEGRITO,
        10,
        LARGURA_UTIL,
    )

    pdf.setFont(
        FONTE_NEGRITO,
        10,
    )

    for linha in linhas_empresa:
        pdf.drawCentredString(
            centro,
            y,
            linha,
        )

        y -= 4 * mm

    pdf.setFont(
        FONTE_NEGRITO,
        6.5,
    )

    pdf.drawCentredString(
        centro,
        y,
        "NEXUS PDV",
    )

    y -= 3 * mm

    pdf.setFont(
        FONTE_NORMAL,
        5.7,
    )

    pdf.drawCentredString(
        centro,
        y,
        "COMPROVANTE DE VENDA",
    )

    y -= 3 * mm

    y = _linha_tracejada(
        pdf,
        esquerda,
        direita,
        y,
    )

    # =====================================================
    # DADOS DA VENDA
    # =====================================================

    numero_venda = (
        venda_grupo[:8].upper()
        if venda_grupo
        else "NÃO INFORMADO"
    )

    data_emissao = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    pdf.setFont(
        FONTE_NEGRITO,
        5.8,
    )

    pdf.drawString(
        esquerda,
        y,
        "VENDA:",
    )

    pdf.setFont(
        FONTE_NORMAL,
        5.8,
    )

    pdf.drawRightString(
        direita,
        y,
        f"#{numero_venda}",
    )

    y -= 3 * mm

    pdf.setFont(
        FONTE_NEGRITO,
        5.8,
    )

    pdf.drawString(
        esquerda,
        y,
        "EMISSÃO:",
    )

    pdf.setFont(
        FONTE_NORMAL,
        5.8,
    )

    pdf.drawRightString(
        direita,
        y,
        data_emissao,
    )

    y -= 3 * mm

    # =====================================================
    # CLIENTE OPCIONAL
    # =====================================================

    cliente_nome = venda_ids[0].get(
        "cliente_nome"
    )

    if cliente_nome:
        y = _linha_tracejada(
            pdf,
            esquerda,
            direita,
            y,
        )

        pdf.setFont(
            FONTE_NEGRITO,
            5.8,
        )

        pdf.drawString(
            esquerda,
            y,
            "CLIENTE",
        )

        y -= 3 * mm

        y = _desenhar_texto_quebrado(
            pdf,
            cliente_nome,
            esquerda,
            y,
            LARGURA_UTIL,
            fonte=FONTE_NEGRITO,
            tamanho=6.2,
            entrelinha=2.8 * mm,
        )

        cliente_documento = venda_ids[0].get(
            "cliente_cpf_cnpj"
        )

        cliente_telefone = venda_ids[0].get(
            "cliente_telefone"
        )

        if cliente_documento:
            pdf.setFont(
                FONTE_NORMAL,
                5.5,
            )

            pdf.drawString(
                esquerda,
                y,
                (
                    "CPF/CNPJ: "
                    f"{_texto(cliente_documento)}"
                ),
            )

            y -= 2.7 * mm

        if cliente_telefone:
            pdf.setFont(
                FONTE_NORMAL,
                5.5,
            )

            pdf.drawString(
                esquerda,
                y,
                (
                    "TELEFONE: "
                    f"{_texto(cliente_telefone)}"
                ),
            )

            y -= 2.7 * mm

    # =====================================================
    # ITENS
    # =====================================================

    y = _linha_tracejada(
        pdf,
        esquerda,
        direita,
        y,
    )

    pdf.setFont(
        FONTE_NEGRITO,
        5.7,
    )

    pdf.drawString(
        esquerda,
        y,
        "DESCRIÇÃO",
    )

    pdf.drawRightString(
        direita,
        y,
        "VALOR",
    )

    y -= 2 * mm

    y = _linha_continua(
        pdf,
        esquerda,
        direita,
        y,
        espessura=0.5,
    )

    subtotal = Decimal("0.00")
    desconto_total = Decimal("0.00")
    total_liquido = Decimal("0.00")
    quantidade_total = 0

    largura_nome = 30 * mm

    for item in venda_ids:
        quantidade = int(
            item.get("quantidade") or 0
        )

        preco_unitario = _decimal(
            item.get("preco_unitario")
        )

        valor_bruto = _decimal(
            item.get("valor_bruto")
        )

        if valor_bruto <= 0:
            valor_bruto = (
                preco_unitario
                * quantidade
            )

        desconto_item = _decimal(
            item.get("desconto")
        )

        valor_liquido = _decimal(
            item.get("valor")
        )

        subtotal += valor_bruto
        desconto_total += desconto_item
        total_liquido += valor_liquido
        quantidade_total += quantidade

        nome_produto = _texto(
            item.get("nome"),
            "Produto",
        )

        linhas_produto = _quebrar_texto(
            nome_produto,
            FONTE_NEGRITO,
            6.4,
            largura_nome,
        )

        pdf.setFont(
            FONTE_NEGRITO,
            6.4,
        )

        primeiro_y = y

        for linha in linhas_produto:
            pdf.drawString(
                esquerda,
                y,
                linha,
            )

            y -= 2.8 * mm

        pdf.setFont(
            FONTE_NEGRITO,
            6.1,
        )

        pdf.drawRightString(
            direita,
            primeiro_y,
            _moeda(valor_liquido),
        )

        pdf.setFont(
            FONTE_NORMAL,
            5.4,
        )

        pdf.drawString(
            esquerda,
            y,
            (
                f"{quantidade} x "
                f"{_moeda(preco_unitario)}"
            ),
        )

        y -= 2.7 * mm

        if desconto_item > 0:
            pdf.setFont(
                FONTE_NORMAL,
                5.3,
            )

            pdf.drawString(
                esquerda,
                y,
                (
                    "Desconto: - "
                    f"{_moeda(desconto_item)}"
                ),
            )

            y -= 2.7 * mm

        y -= 1.5 * mm

    # =====================================================
    # TOTALIZAÇÃO
    # =====================================================

    y = _linha_tracejada(
        pdf,
        esquerda,
        direita,
        y,
    )

    pdf.setFont(
        FONTE_NORMAL,
        6,
    )

    pdf.drawString(
        esquerda,
        y,
        "Subtotal",
    )

    pdf.drawRightString(
        direita,
        y,
        _moeda(subtotal),
    )

    y -= 3.2 * mm

    if desconto_total > 0:
        pdf.setFont(
            FONTE_NORMAL,
            6,
        )

        pdf.drawString(
            esquerda,
            y,
            "Desconto",
        )

        pdf.drawRightString(
            direita,
            y,
            f"- {_moeda(desconto_total)}",
        )

        y -= 3.2 * mm

    pdf.setFont(
        FONTE_NORMAL,
        6,
    )

    pdf.drawString(
        esquerda,
        y,
        "Quantidade de itens",
    )

    pdf.drawRightString(
        direita,
        y,
        str(quantidade_total),
    )

    y -= 3 * mm

    y = _linha_continua(
        pdf,
        esquerda,
        direita,
        y,
        espessura=0.8,
    )

    pdf.setFont(
        FONTE_NEGRITO,
        9,
    )

    pdf.drawString(
        esquerda,
        y,
        "TOTAL",
    )

    pdf.drawRightString(
        direita,
        y,
        _moeda(total_liquido),
    )

    y -= 4.5 * mm

    # =====================================================
    # PAGAMENTO
    # =====================================================

    forma_pagamento = _texto(
        venda_ids[0].get("pagamento"),
        "Não informado",
    )

    pdf.setFont(
        FONTE_NEGRITO,
        5.8,
    )

    pdf.drawString(
        esquerda,
        y,
        "PAGAMENTO:",
    )

    pdf.setFont(
        FONTE_NORMAL,
        5.8,
    )

    pdf.drawRightString(
        direita,
        y,
        forma_pagamento,
    )

    y -= 3.5 * mm

    # =====================================================
    # RODAPÉ
    # =====================================================

    y = _linha_tracejada(
        pdf,
        esquerda,
        direita,
        y,
    )

    pdf.setFont(
        FONTE_NEGRITO,
        6.2,
    )

    pdf.drawCentredString(
        centro,
        y,
        "Obrigado pela preferência!",
    )

    y -= 3.3 * mm

    pdf.setFont(
        FONTE_NORMAL,
        5.2,
    )

    pdf.drawCentredString(
        centro,
        y,
        "Este documento não possui valor fiscal.",
    )

    y -= 3 * mm

    pdf.drawCentredString(
        centro,
        y,
        "Emitido pelo Nexus PDV",
    )

    y -= 4 * mm

    pdf.setFont(
        FONTE_NORMAL,
        5,
    )

    pdf.drawCentredString(
        centro,
        y,
        "- - - CORTE AQUI - - -",
    )

    pdf.showPage()
    pdf.save()

    return str(caminho)