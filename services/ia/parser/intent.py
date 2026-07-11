import re
import unicodedata


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )

    return texto.strip(" \t\r\n?!.,;:\"'“”‘’")


def _extrair_produto(mensagem):
    padroes = (
        r"(?:estoque|preco|valor|codigo(?: de barras)?)\s+(?:do|da|de)\s+(.+)",
        r"quanto\s+(?:tem|custa)\s+(?:do|da|de)?\s*(.+?)(?:\s+(?:no|em)\s+estoque)?$",
        r"(?:tem|possui)\s+(.+?)\s+(?:no|em)\s+estoque$",
        r"produto\s+(.+)",
    )

    for padrao in padroes:
        encontrado = re.search(padrao, mensagem)

        if encontrado:
            produto = encontrado.group(1).strip()

            produto = re.sub(
                r"[?!.,;:]",
                "",
                produto
            )

            produto = re.sub(
                r"\s+(?:hoje|este mes|no mes|este ano)$",
                "",
                produto
            )

            produto = re.sub(
                r"^(?:o|a|produto|item)\s+",
                "",
                produto
            )

            return produto.strip() or None

    return None


def interpretar_mensagem(mensagem):
    msg = _normalizar(mensagem)

    if "hoje" in msg:
        periodo = "hoje"
    elif "ano" in msg:
        periodo = "ano"
    elif "mes" in msg:
        periodo = "mes"
    else:
        periodo = None

    # Precisa ficar antes da intenção geral de vendas
    if (
        re.search(r"\b(produto|produtos|item|itens)\b", msg)
        and re.search(r"\b(vendi|vendeu|vendemos|vendido|vendidos|vendas)\b", msg)
    ):
        return {
            "intencao": "produtos_vendidos",
            "produto": None,
            "periodo": periodo or "mes"
        }

    if any(
        termo in msg
        for termo in (
            "sem estoque",
            "esgotado",
            "esgotados",
            "zerado",
            "zerados",
            "acabou"
        )
    ):
        return {
            "intencao": "sem_estoque",
            "produto": None,
            "periodo": periodo
        }

    if (
        "esgotando" in msg
        or (
            "estoque" in msg
            and any(
                termo in msg
                for termo in ("baixo", "acabando", "pouco")
            )
        )
    ):
        return {
            "intencao": "estoque_baixo",
            "produto": None,
            "periodo": periodo
        }

    produto = _extrair_produto(msg)

    if produto:
        if "estoque" in msg or "quant" in msg:
            intencao = "consultar_estoque_produto"
        elif any(
            termo in msg
            for termo in ("preco", "valor", "custa")
        ):
            intencao = "consultar_preco_produto"
        elif "codigo" in msg:
            intencao = "consultar_codigo_produto"
        else:
            intencao = "consultar_produto"

        return {
            "intencao": intencao,
            "produto": produto,
            "periodo": periodo
        }

    if any(
        termo in msg
        for termo in (
            "quantos produtos",
            "quantos itens",
            "total de produtos",
            "produtos cadastrados"
        )
    ):
        intencao = "total_produtos"

    elif (
        "mais vendido" in msg
        or "campeao de vendas" in msg
    ):
        intencao = "produto_mais_vendido"

    elif any(
        termo in msg
        for termo in (
            "faturamento",
            "faturei",
            "faturou",
            "venda",
            "vendas",
            "vendi"
        )
    ):
        intencao = "resumo_vendas"

    elif "caixa" in msg:
        intencao = "resumo_caixa"

    elif any(
        termo in msg
        for termo in (
            "relatorio",
            "resumo",
            "visao geral"
        )
    ):
        intencao = "relatorio_geral"

    else:
        intencao = "conversa"

    return {
        "intencao": intencao,
        "produto": None,
        "periodo": periodo
    }