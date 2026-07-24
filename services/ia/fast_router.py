import json
import re
import time
import unicodedata

from decimal import Decimal, InvalidOperation

from services.ia.tools import executar_ferramenta


_CACHE = {}
_CACHE_TTL = 20


def _normalizar(texto):
    texto = unicodedata.normalize(
        "NFKD",
        str(texto or "").lower(),
    )

    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(
            caractere
        )
    )

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def _moeda(valor):
    try:
        numero = Decimal(
            str(valor or 0)
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        numero = Decimal("0")

    return (
        f"R$ {numero:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def _periodo(texto):
    if "hoje" in texto:
        return "hoje"
    if "ontem" in texto:
        return "ontem"
    if (
        "mes passado" in texto
        or "ultimo mes" in texto
    ):
        return "mes_passado"
    if (
        "ano passado" in texto
        or "ultimo ano" in texto
    ):
        return "ano_passado"
    if "ano" in texto:
        return "ano"
    if "semana" in texto:
        return "semana"
    if "30 dias" in texto:
        return "ultimos_30_dias"
    if "7 dias" in texto:
        return "ultimos_7_dias"

    return "mes"


def _executar(
    nome,
    argumentos,
    usuario,
):
    bruto = executar_ferramenta(
        nome=nome,
        argumentos=argumentos,
        contexto_usuario=usuario,
    )

    try:
        resultado = json.loads(bruto)
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    if not resultado.get("sucesso"):
        return None

    return resultado.get("dados")


def _argumentos_periodo(texto):
    return {
        "periodo": _periodo(texto),
        "data_inicio": None,
        "data_fim": None,
    }


def _resposta_vendas(texto, usuario):
    argumentos = _argumentos_periodo(
        texto
    )

    dados = _executar(
        "consultar_resumo_vendas",
        argumentos,
        usuario,
    )

    if not dados:
        return None

    resumo = dados.get(
        "resumo",
        {},
    )

    return "\n".join([
        "**📊 Resumo de vendas**",
        "",
        f"• Faturamento: **{_moeda(resumo.get('faturamento'))}**",
        f"• Vendas: **{resumo.get('registros_venda', 0)}**",
        f"• Itens vendidos: **{resumo.get('itens_vendidos', 0)}**",
        f"• Ticket médio: **{_moeda(resumo.get('ticket_medio_registro'))}**",
    ])


def _resposta_estoque(texto, usuario):
    situacao = "resumo"

    if any(
        termo in texto
        for termo in (
            "baixo",
            "acabando",
            "esgotando",
        )
    ):
        situacao = "baixo"
    elif any(
        termo in texto
        for termo in (
            "esgotado",
            "sem estoque",
            "zerado",
        )
    ):
        situacao = "sem_estoque"

    dados = _executar(
        "consultar_estoque",
        {
            "situacao": situacao,
            "limite_estoque_baixo": 5,
            "limite": 20,
        },
        usuario,
    )

    if not dados:
        return None

    produtos = (
        dados.get("produtos")
        or dados.get("itens")
        or []
    )

    if produtos:
        linhas = [
            "**📦 Situação do estoque**",
            "",
        ]

        for produto in produtos[:20]:
            linhas.append(
                "• "
                f"**{produto.get('nome', 'Produto')}** — "
                f"{produto.get('estoque', 0)} unidade(s)"
            )

        return "\n".join(linhas)

    resumo = dados.get(
        "resumo",
        {},
    )

    return "\n".join([
        "**📦 Situação do estoque**",
        "",
        f"• Produtos cadastrados: **{resumo.get('produtos_cadastrados', 0)}**",
        f"• Estoque total: **{resumo.get('unidades_em_estoque', 0)}**",
        f"• Estoque baixo: **{resumo.get('produtos_estoque_baixo', 0)}**",
        f"• Sem estoque: **{resumo.get('produtos_sem_estoque', 0)}**",
    ])


def _resposta_caixa(usuario):
    dados = _executar(
        "consultar_caixa",
        {},
        usuario,
    )

    if not dados:
        return None

    if not dados.get(
        "caixa_encontrado"
    ):
        return (
            "**💳 Resumo do caixa**\n\n"
            "Nenhum caixa foi encontrado."
        )

    caixa = dados.get(
        "caixa",
        {},
    )

    movimentacoes = dados.get(
        "movimentacoes",
        {},
    )

    status = caixa.get(
        "status",
        "fechado",
    )

    return "\n".join([
        "**💳 Resumo do caixa**",
        "",
        f"• Status: **{str(status).title()}**",
        f"• Valor inicial: **{_moeda(caixa.get('valor_inicial'))}**",
        f"• Entradas: **{_moeda(movimentacoes.get('entradas'))}**",
        f"• Saídas: **{_moeda(movimentacoes.get('saidas'))}**",
        f"• Saldo estimado: **{_moeda(dados.get('saldo_estimado'))}**",
    ])


def _resposta_custos(
    texto,
    usuario,
):
    argumentos = _argumentos_periodo(
        texto
    )

    if any(
        termo in texto
        for termo in (
            "vencida",
            "vencido",
            "atrasada",
            "atrasado",
        )
    ):
        dados = _executar(
            "listar_custos",
            {
                **argumentos,
                "situacao": "vencidas",
                "limite": 20,
            },
            usuario,
        )

        if not dados:
            return None

        despesas = dados.get(
            "despesas",
            [],
        )

        if not despesas:
            return (
                "**✅ Despesas vencidas**\n\n"
                "Nenhuma despesa vencida foi encontrada."
            )

        linhas = [
            "**⚠️ Despesas vencidas**",
            "",
        ]

        for despesa in despesas:
            linhas.append(
                "• "
                f"**{despesa.get('descricao')}** — "
                f"{_moeda(despesa.get('saldo'))} — "
                f"vencimento {despesa.get('data_vencimento')}"
            )

        return "\n".join(linhas)

    dados = _executar(
        "consultar_resumo_custos",
        argumentos,
        usuario,
    )

    if not dados:
        return None

    resumo = dados.get(
        "resumo",
        {},
    )

    return "\n".join([
        "**💸 Custos empresariais**",
        "",
        f"• Total previsto: **{_moeda(resumo.get('total_previsto'))}**",
        f"• Total pago: **{_moeda(resumo.get('total_pago'))}**",
        f"• Total pendente: **{_moeda(resumo.get('total_pendente'))}**",
        f"• Total vencido: **{_moeda(resumo.get('total_vencido'))}**",
        f"• Contas pendentes: **{resumo.get('parcelas_pendentes', 0)}**",
    ])


def _resposta_clientes(
    texto,
    usuario,
):
    if any(
        termo in texto
        for termo in (
            "melhor cliente",
            "melhores clientes",
            "mais comprou",
            "mais gastou",
            "ranking de clientes",
        )
    ):
        ordem = (
            "mais_compras"
            if "mais compr" in texto
            else "maior_valor"
        )

        dados = _executar(
            "consultar_ranking_clientes",
            {
                **_argumentos_periodo(texto),
                "ordem": ordem,
                "limite": 10,
            },
            usuario,
        )

        if not dados:
            return None

        clientes = dados.get(
            "clientes",
            [],
        )

        if not clientes:
            return (
                "**👥 Ranking de clientes**\n\n"
                "Nenhuma compra vinculada a clientes "
                "foi encontrada."
            )

        linhas = [
            "**👥 Melhores clientes**",
            "",
        ]

        for indice, cliente in enumerate(
            clientes,
            start=1,
        ):
            linhas.append(
                f"{indice}. **{cliente.get('nome')}** — "
                f"{_moeda(cliente.get('total_gasto'))} — "
                f"{cliente.get('quantidade_compras', 0)} compra(s)"
            )

        return "\n".join(linhas)

    dados = _executar(
        "consultar_resumo_clientes",
        {},
        usuario,
    )

    if not dados:
        return None

    return "\n".join([
        "**👥 Resumo de clientes**",
        "",
        f"• Total: **{dados.get('total', 0)}**",
        f"• Ativos: **{dados.get('ativos', 0)}**",
        f"• Inativos: **{dados.get('inativos', 0)}**",
        f"• Cadastrados hoje: **{dados.get('cadastrados_hoje', 0)}**",
        f"• Cadastrados este mês: **{dados.get('cadastrados_mes', 0)}**",
    ])


def _detectar(texto):
    if any(
        termo in texto
        for termo in (
            "faturei",
            "faturamento",
            "quantas vendas",
            "quanto vendi",
            "vendas fiz",
            "ticket medio",
        )
    ):
        return "vendas"

    if any(
        termo in texto
        for termo in (
            "estoque baixo",
            "sem estoque",
            "esgotado",
            "esgotando",
            "acabando",
            "resumo do estoque",
        )
    ):
        return "estoque"

    if any(
        termo in texto
        for termo in (
            "como esta o caixa",
            "resumo do caixa",
            "saldo do caixa",
            "caixa aberto",
            "caixa fechado",
        )
    ):
        return "caixa"

    if any(
        termo in texto
        for termo in (
            "despesa",
            "despesas",
            "custo",
            "custos",
            "contas vencidas",
            "contas pendentes",
        )
    ):
        return "custos"

    if any(
        termo in texto
        for termo in (
            "quantos clientes",
            "quantidade de clientes",
            "melhor cliente",
            "melhores clientes",
            "mais comprou",
            "mais gastou",
            "ranking de clientes",
        )
    ):
        return "clientes"

    return None


def tentar_resposta_rapida(
    mensagem,
    usuario,
):
    texto = _normalizar(
        mensagem
    )

    intencao = _detectar(
        texto
    )

    if not intencao:
        return None

    nivel = str(
        usuario.get("nivel")
        or "funcionario"
    ).lower()

    if (
        intencao in {"custos", "clientes"}
        and nivel not in {"gerente", "master"}
    ):
        return None

    chave = (
        usuario.get("empresa_id"),
        usuario.get("usuario_id"),
        nivel,
        texto,
    )

    agora = time.monotonic()
    armazenado = _CACHE.get(chave)

    if armazenado:
        criado_em, resposta = armazenado

        if agora - criado_em <= _CACHE_TTL:
            return resposta

        _CACHE.pop(
            chave,
            None,
        )

    funcoes = {
        "vendas": _resposta_vendas,
        "estoque": _resposta_estoque,
        "custos": _resposta_custos,
        "clientes": _resposta_clientes,
    }

    if intencao == "caixa":
        resposta = _resposta_caixa(
            usuario
        )
    else:
        resposta = funcoes[intencao](
            texto,
            usuario,
        )

    if resposta:
        _CACHE[chave] = (
            agora,
            resposta,
        )

    return resposta
