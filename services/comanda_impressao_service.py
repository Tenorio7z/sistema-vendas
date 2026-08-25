from datetime import datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from database import conectar, criar_cursor
from services.mesas_service import MesasErro, MesasService


LARGURAS_PERMITIDAS = (48, 58, 80)
FONTE = "Helvetica"
FONTE_NEGRITO = "Helvetica-Bold"
_estrutura_lock = Lock()
_estrutura_pronta = False
_configuracoes_cache = {}
_cache_lock = Lock()
_CACHE_TTL_SEGUNDOS = 300


def _numero(valor):
    return Decimal(str(valor or 0))


def _moeda(valor):
    return f"R$ {float(_numero(valor)):,.2f}".replace(
        ",", "X"
    ).replace(".", ",").replace("X", ".")


def _quantidade(valor):
    numero = _numero(valor)
    if numero == numero.to_integral_value():
        return str(int(numero))
    return f"{numero:.3f}".rstrip("0").rstrip(".").replace(".", ",")


def _quebrar(texto, fonte, tamanho, largura):
    palavras = str(texto or "").strip().split()
    if not palavras:
        return [""]

    linhas = []
    atual = ""
    for palavra in palavras:
        tentativa = f"{atual} {palavra}".strip()
        if stringWidth(tentativa, fonte, tamanho) <= largura:
            atual = tentativa
            continue
        if atual:
            linhas.append(atual)
        atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def garantir_estrutura_impressao():
    global _estrutura_pronta

    if _estrutura_pronta:
        return

    with _estrutura_lock:
        if _estrutura_pronta:
            return

        conn = conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS configuracao_impressao (
                    empresa_id INTEGER PRIMARY KEY REFERENCES empresa(id) ON DELETE CASCADE,
                    largura_papel_mm INTEGER NOT NULL DEFAULT 58
                        CHECK (largura_papel_mm IN (48, 58, 80)),
                    copias_pre_conta INTEGER NOT NULL DEFAULT 1
                        CHECK (copias_pre_conta BETWEEN 1 AND 3),
                    atualizado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
                    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            _estrutura_pronta = True
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()


def obter_configuracao_impressao(empresa_id):
    chave = int(empresa_id)
    agora = monotonic()

    with _cache_lock:
        entrada = _configuracoes_cache.get(chave)
        if entrada and agora - entrada[0] < _CACHE_TTL_SEGUNDOS:
            return dict(entrada[1])

    garantir_estrutura_impressao()
    conn = conectar()
    cursor = criar_cursor(conn)
    try:
        cursor.execute(
            """
            SELECT largura_papel_mm, copias_pre_conta
            FROM configuracao_impressao
            WHERE empresa_id = %s
            LIMIT 1
            """,
            (empresa_id,),
        )
        configuracao = cursor.fetchone()
        resultado = configuracao or {
            "largura_papel_mm": 58,
            "copias_pre_conta": 1,
        }
        resultado = dict(resultado)
        with _cache_lock:
            _configuracoes_cache[chave] = (agora, resultado)
        return dict(resultado)
    finally:
        cursor.close()
        conn.close()


def salvar_configuracao_impressao(
    empresa_id,
    usuario_id,
    largura_papel_mm,
    copias_pre_conta=1,
):
    try:
        largura = int(largura_papel_mm)
        copias = int(copias_pre_conta)
    except (TypeError, ValueError) as erro:
        raise ValueError("Configuração de impressão inválida.") from erro

    if largura not in LARGURAS_PERMITIDAS:
        raise ValueError("Escolha uma bobina de 48, 58 ou 80 mm.")
    if copias not in range(1, 4):
        raise ValueError("A quantidade de cópias deve ficar entre 1 e 3.")

    garantir_estrutura_impressao()
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO configuracao_impressao (
                empresa_id, largura_papel_mm, copias_pre_conta,
                atualizado_por, atualizado_em
            ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (empresa_id) DO UPDATE SET
                largura_papel_mm = EXCLUDED.largura_papel_mm,
                copias_pre_conta = EXCLUDED.copias_pre_conta,
                atualizado_por = EXCLUDED.atualizado_por,
                atualizado_em = CURRENT_TIMESTAMP
            """,
            (empresa_id, largura, copias, usuario_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

    resultado = {"largura_papel_mm": largura, "copias_pre_conta": copias}
    with _cache_lock:
        _configuracoes_cache[int(empresa_id)] = (monotonic(), resultado)
    return dict(resultado)


def _altura_documento(itens, largura_util):
    # Cabeçalho, identificação, total e rodapé ocupam cerca de 60 mm.
    # O cálculo evita tanto corte quanto desperdício excessivo de bobina.
    altura = 60 * mm
    for item in itens:
        nome = item.get("produto_nome") or "Produto"
        linhas = _quebrar(nome, FONTE_NEGRITO, 7.2, largura_util)
        altura += (len(linhas) * 3.2 + 5.2) * mm
        if item.get("observacoes"):
            observacoes = _quebrar(
                f"Obs.: {item['observacoes']}", FONTE, 6.2, largura_util
            )
            altura += len(observacoes) * 2.8 * mm
    return max(altura, 90 * mm)


def gerar_pre_conta(empresa_id, comanda_id):
    dados = MesasService.detalhar_comanda(
        empresa_id=empresa_id,
        comanda_id=comanda_id,
    )
    comanda = dados["comanda"]
    itens = [item for item in dados["itens"] if item["status"] != "cancelado"]

    if comanda["status"] not in {"aberta", "aguardando_pagamento"}:
        raise MesasErro("Somente comandas em atendimento podem gerar uma conta.")
    if not itens:
        raise MesasErro("Adicione pelo menos um item antes de imprimir a conta.")

    configuracao = obter_configuracao_impressao(empresa_id)
    largura_mm = int(configuracao["largura_papel_mm"])
    largura = largura_mm * mm
    margem = 2.5 * mm
    largura_util = largura - (margem * 2)
    altura = _altura_documento(itens, largura_util)

    pasta = Path("cupons") / "pre_contas"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / (
        f"conta_{empresa_id}_{comanda_id}_"
        f"{datetime.now():%Y%m%d_%H%M%S}_{uuid4().hex[:6]}.pdf"
    )

    pdf = canvas.Canvas(str(caminho), pagesize=(largura, altura))
    pdf.setTitle(f"Conta da mesa {comanda['mesa_numero']}")
    y = altura - 5 * mm

    def central(texto, fonte=FONTE, tamanho=7):
        nonlocal y
        pdf.setFont(fonte, tamanho)
        pdf.drawCentredString(largura / 2, y, str(texto))
        y -= 3.5 * mm

    def linha():
        nonlocal y
        pdf.setStrokeColorRGB(0.35, 0.35, 0.35)
        pdf.setDash(1, 1)
        pdf.line(margem, y, largura - margem, y)
        pdf.setDash()
        y -= 3 * mm

    central(comanda.get("empresa_nome") or "Nexus PDV", FONTE_NEGRITO, 9.5)
    central("CONTA PARA CONFERÊNCIA", FONTE_NEGRITO, 7.5)
    central("Documento não fiscal", FONTE, 6.2)
    y -= 1 * mm
    linha()

    pdf.setFont(FONTE_NEGRITO, 8)
    pdf.drawString(margem, y, f"Mesa {comanda['mesa_numero']}")
    pdf.drawRightString(largura - margem, y, f"Comanda #{comanda_id}")
    y -= 4 * mm
    pdf.setFont(FONTE, 6.4)
    pdf.drawString(margem, y, f"Emissão: {datetime.now():%d/%m/%Y %H:%M}")
    y -= 3.2 * mm
    if comanda.get("funcionario_nome"):
        pdf.drawString(margem, y, f"Atendimento: {comanda['funcionario_nome']}")
        y -= 3.2 * mm
    if comanda.get("cliente_nome"):
        pdf.drawString(margem, y, f"Cliente: {comanda['cliente_nome']}")
        y -= 3.2 * mm
    linha()

    total = Decimal("0")
    for item in itens:
        nome = item.get("produto_nome") or "Produto"
        subtotal = _numero(item.get("subtotal"))
        total += subtotal
        for texto in _quebrar(nome, FONTE_NEGRITO, 7.2, largura_util):
            pdf.setFont(FONTE_NEGRITO, 7.2)
            pdf.drawString(margem, y, texto)
            y -= 3.2 * mm
        detalhe = f"{_quantidade(item['quantidade'])} x {_moeda(item['valor_unitario'])}"
        pdf.setFont(FONTE, 6.6)
        pdf.drawString(margem, y, detalhe)
        pdf.setFont(FONTE_NEGRITO, 6.8)
        pdf.drawRightString(largura - margem, y, _moeda(subtotal))
        y -= 3.4 * mm
        if item.get("observacoes"):
            for texto in _quebrar(
                f"Obs.: {item['observacoes']}", FONTE, 6.1, largura_util
            ):
                pdf.setFont(FONTE, 6.1)
                pdf.drawString(margem, y, texto)
                y -= 2.8 * mm
        y -= 1.8 * mm

    linha()
    pdf.setFont(FONTE_NEGRITO, 9.5)
    pdf.drawString(margem, y, "TOTAL")
    pdf.drawRightString(largura - margem, y, _moeda(total))
    y -= 6 * mm
    central("Confira os itens antes do pagamento.", FONTE, 6.4)
    central("Pagamento ainda não registrado.", FONTE_NEGRITO, 6.4)
    central("Nexus PDV", FONTE, 5.8)

    pdf.showPage()
    pdf.save()
    return caminho.resolve(), configuracao
