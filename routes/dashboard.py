from calendar import monthrange
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import jsonify, redirect, render_template, request, session

from database import conectar, criar_cursor
from services.filiais_service import FiliaisService
from services.pagamentos_service import resumo_pagamentos


ZERO = Decimal("0.00")


def _decimal(valor):
    if valor is None:
        return ZERO

    try:
        return Decimal(str(valor))
    except Exception:
        return ZERO


def _numero(valor):
    return float(_decimal(valor))


def _moeda(valor):
    numero = _decimal(valor).quantize(Decimal("0.01"))
    texto = f"{numero:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def _periodo_dashboard():
    hoje = date.today()
    periodo = request.args.get("periodo", "hoje").strip().lower()

    if periodo == "7dias":
        inicio_data = hoje - timedelta(days=6)
        fim_data = hoje + timedelta(days=1)
        titulo = "Últimos 7 dias"
    elif periodo == "mes":
        inicio_data = hoje.replace(day=1)
        ultimo_dia = monthrange(hoje.year, hoje.month)[1]
        fim_data = hoje.replace(day=ultimo_dia) + timedelta(days=1)
        titulo = "Este mês"
    elif periodo == "personalizado":
        try:
            inicio_data = datetime.strptime(
                request.args.get("inicio", ""), "%Y-%m-%d"
            ).date()
            fim_informado = datetime.strptime(
                request.args.get("fim", ""), "%Y-%m-%d"
            ).date()

            if fim_informado < inicio_data:
                raise ValueError

            if (fim_informado - inicio_data).days > 366:
                raise ValueError

            fim_data = fim_informado + timedelta(days=1)
            titulo = "Período personalizado"
        except (TypeError, ValueError):
            periodo = "hoje"
            inicio_data = hoje
            fim_data = hoje + timedelta(days=1)
            titulo = "Hoje"
    else:
        periodo = "hoje"
        inicio_data = hoje
        fim_data = hoje + timedelta(days=1)
        titulo = "Hoje"

    inicio = datetime.combine(inicio_data, time.min)
    fim = datetime.combine(fim_data, time.min)
    duracao = fim - inicio

    return {
        "chave": periodo,
        "titulo": titulo,
        "inicio": inicio,
        "fim": fim,
        "inicio_anterior": inicio - duracao,
        "fim_anterior": inicio,
        "inicio_data": inicio_data,
        "fim_data": fim_data - timedelta(days=1),
    }


def _variacao(atual, anterior):
    atual = _decimal(atual)
    anterior = _decimal(anterior)

    if anterior == 0:
        if atual == 0:
            return {"valor": 0.0, "tipo": "neutra", "texto": "Sem alteração"}

        return {"valor": 100.0, "tipo": "positiva", "texto": "Novo movimento"}

    valor = ((atual - anterior) / abs(anterior) * Decimal("100")).quantize(
        Decimal("0.1")
    )

    if valor > 0:
        tipo = "positiva"
        prefixo = "+"
    elif valor < 0:
        tipo = "negativa"
        prefixo = ""
    else:
        tipo = "neutra"
        prefixo = ""

    return {
        "valor": float(valor),
        "tipo": tipo,
        "texto": f"{prefixo}{str(valor).replace('.', ',')}%",
    }


def _resolver_filial_dashboard(empresa_id):
    """Resolve a filial sem permitir que um funcionário consulte outra unidade."""
    nivel = str(session.get("nivel") or "").lower()
    pode_alternar = nivel in {"gerente", "admin", "master"}
    filial_id = session.get("filial_id")

    if pode_alternar:
        filial_solicitada = request.args.get("filial_id", type=int)
        if filial_solicitada:
            filial_id = filial_solicitada

    filial = None
    if filial_id:
        filial = FiliaisService.obter(empresa_id, int(filial_id))
        if filial and not bool(filial.get("ativa", True)):
            filial = None

    if not filial:
        matriz_id = FiliaisService.garantir_matriz(empresa_id)
        filial = FiliaisService.obter(empresa_id, matriz_id)

    filiais = FiliaisService.listar(empresa_id) if pode_alternar else [filial]
    return filial, filiais, pode_alternar


def _grafico_vendas(cursor, empresa_id, filial_id, filtro):
    hoje = filtro["chave"] == "hoje"
    agrupamento = "hour" if hoje else "day"

    cursor.execute(
        f"""
        SELECT
            DATE_TRUNC('{agrupamento}', data_venda) AS momento,
            COALESCE(SUM(valor), 0) AS total
        FROM vendas
        WHERE empresa_id = %s
          AND filial_id = %s
          AND COALESCE(cancelada, 0) = 0
          AND data_venda >= %s
          AND data_venda < %s
        GROUP BY 1
        ORDER BY 1
        """,
        (empresa_id, filial_id, filtro["inicio"], filtro["fim"]),
    )

    encontrados = {
        linha["momento"]: _numero(linha["total"])
        for linha in cursor.fetchall()
    }

    labels = []
    valores = []

    if hoje:
        for hora in range(24):
            momento = filtro["inicio"] + timedelta(hours=hora)
            labels.append(f"{hora:02d}h")
            valores.append(encontrados.get(momento, 0.0))
    else:
        momento = filtro["inicio"]
        while momento < filtro["fim"]:
            labels.append(momento.strftime("%d/%m"))
            valores.append(encontrados.get(momento, 0.0))
            momento += timedelta(days=1)

    return {"labels": labels, "valores": valores}


def _insight_nami(metricas, alertas, produto_mais_vendido):
    if alertas:
        primeiro = alertas[0]
        return (
            f"Atenção: {primeiro['titulo'].lower()}. "
            "Vale revisar o estoque antes da próxima venda."
        )

    if metricas["vendas_validas"] == 0:
        return (
            "Ainda não houve vendas neste período. Assim que o movimento começar, "
            "eu acompanho faturamento, ticket médio e possíveis desvios."
        )

    variacao = metricas["variacao_faturamento"]
    if variacao["tipo"] == "positiva":
        mensagem = (
            f"O faturamento está {variacao['texto']} em relação ao período anterior."
        )
    elif variacao["tipo"] == "negativa":
        mensagem = (
            f"O faturamento está {variacao['texto']} em relação ao período anterior. "
            "Pode valer a pena revisar os horários e produtos com menor saída."
        )
    else:
        mensagem = "O faturamento está estável em relação ao período anterior."

    if produto_mais_vendido:
        mensagem += f" O produto de maior saída foi {produto_mais_vendido['nome']}."

    return mensagem


def _carregar_dashboard(empresa_id, filial_id, filtro):
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT
                e.id,
                e.nome,
                f.id AS filial_id,
                f.nome AS filial_nome,
                f.matriz AS filial_matriz
            FROM empresa e
            INNER JOIN filiais f
                ON f.empresa_id = e.id
               AND f.id = %s
            WHERE e.id = %s
            """,
            (filial_id, empresa_id),
        )
        empresa = cursor.fetchone()

        cursor.execute(
            """
            SELECT id, valor_inicial, valor_final, status, data_abertura
            FROM caixa
            WHERE empresa_id = %s
              AND filial_id = %s
              AND status = 'aberto'
            ORDER BY id DESC
            LIMIT 1
            """,
            (empresa_id, filial_id),
        )
        caixa_aberto = cursor.fetchone()

        cursor.execute(
            """
            WITH atual AS (
                SELECT
                    COUNT(*) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ) AS vendas_validas,
                    COUNT(*) FILTER (
                        WHERE COALESCE(cancelada, 0) = 1
                    ) AS vendas_canceladas,
                    COALESCE(SUM(quantidade) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ), 0) AS itens_vendidos,
                    COALESCE(SUM(valor) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ), 0) AS faturamento,
                    COALESCE(SUM(COALESCE(desconto_valor, 0)) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ), 0) AS descontos,
                    COUNT(DISTINCT cliente_id) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                          AND cliente_id IS NOT NULL
                    ) AS clientes_identificados,
                    COALESCE(SUM(valor) FILTER (
                        WHERE COALESCE(cancelada, 0) = 1
                    ), 0) AS total_cancelado
                FROM vendas
                WHERE empresa_id = %s
                  AND filial_id = %s
                  AND data_venda >= %s
                  AND data_venda < %s
            ),
            anterior AS (
                SELECT
                    COUNT(*) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ) AS vendas_validas,
                    COALESCE(SUM(valor) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ), 0) AS faturamento
                FROM vendas
                WHERE empresa_id = %s
                  AND filial_id = %s
                  AND data_venda >= %s
                  AND data_venda < %s
            )
            SELECT atual.*, anterior.vendas_validas AS vendas_anteriores,
                   anterior.faturamento AS faturamento_anterior
            FROM atual CROSS JOIN anterior
            """,
            (
                empresa_id,
                filial_id,
                filtro["inicio"],
                filtro["fim"],
                empresa_id,
                filial_id,
                filtro["inicio_anterior"],
                filtro["fim_anterior"],
            ),
        )
        vendas = cursor.fetchone() or {}

        cursor.execute(
            """
            SELECT
                COALESCE((
                    SELECT SUM(cp.valor)
                    FROM custos_pagamentos cp
                    LEFT JOIN caixa cx
                        ON cx.id = cp.caixa_id
                       AND cx.empresa_id = cp.empresa_id
                    LEFT JOIN usuarios uc
                        ON uc.id = cp.usuario_id
                       AND uc.empresa_id = cp.empresa_id
                    WHERE cp.empresa_id = %s
                      AND COALESCE(
                          cx.filial_id,
                          uc.filial_id,
                          (
                              SELECT fm.id
                              FROM filiais fm
                              WHERE fm.empresa_id = cp.empresa_id
                                AND fm.matriz = TRUE
                              LIMIT 1
                          )
                      ) = %s
                      AND cp.estornado = FALSE
                      AND cp.data_pagamento >= %s
                      AND cp.data_pagamento < %s
                ), 0) AS custos,
                COALESCE((
                    SELECT SUM(fp.valor_total)
                    FROM folha_pagamentos fp
                    INNER JOIN usuarios uf
                        ON uf.id = fp.usuario_id
                       AND uf.empresa_id = fp.empresa_id
                    WHERE fp.empresa_id = %s
                      AND uf.filial_id = %s
                      AND fp.status = 'pago'
                      AND fp.data_pagamento >= %s
                      AND fp.data_pagamento < %s
                ), 0) AS folha,
                COALESCE((
                    SELECT SUM(mc.valor)
                    FROM movimentacoes_caixa mc
                    LEFT JOIN caixa ce
                        ON ce.id = mc.caixa_id
                       AND ce.empresa_id = mc.empresa_id
                    WHERE mc.empresa_id = %s
                      AND COALESCE(
                          ce.filial_id,
                          (
                              SELECT fm.id
                              FROM filiais fm
                              WHERE fm.empresa_id = mc.empresa_id
                                AND fm.matriz = TRUE
                              LIMIT 1
                          )
                      ) = %s
                      AND mc.tipo = 'entrada'
                      AND mc.data >= %s
                      AND mc.data < %s
                      AND LOWER(COALESCE(mc.descricao, '')) <> 'abertura de caixa'
                      AND LOWER(COALESCE(mc.descricao, '')) NOT LIKE 'estorno de custo empresarial%%'
                ), 0) AS outras_entradas,
                COALESCE((
                    SELECT SUM(mc.valor)
                    FROM movimentacoes_caixa mc
                    LEFT JOIN caixa cs
                        ON cs.id = mc.caixa_id
                       AND cs.empresa_id = mc.empresa_id
                    WHERE mc.empresa_id = %s
                      AND COALESCE(
                          cs.filial_id,
                          (
                              SELECT fm.id
                              FROM filiais fm
                              WHERE fm.empresa_id = mc.empresa_id
                                AND fm.matriz = TRUE
                              LIMIT 1
                          )
                      ) = %s
                      AND mc.tipo = 'saida'
                      AND mc.data >= %s
                      AND mc.data < %s
                      AND LOWER(COALESCE(mc.descricao, '')) NOT LIKE 'cancelamento da venda%%'
                      AND LOWER(COALESCE(mc.descricao, '')) NOT LIKE 'pagamento da folha%%'
                      AND LOWER(COALESCE(mc.descricao, '')) NOT LIKE 'custo empresarial%%'
                      AND LOWER(COALESCE(mc.descricao, '')) NOT LIKE 'estorno de custo empresarial%%'
                ), 0) AS outras_saidas
            """,
            (
                empresa_id, filial_id, filtro["inicio"], filtro["fim"],
                empresa_id, filial_id, filtro["inicio"], filtro["fim"],
                empresa_id, filial_id, filtro["inicio"], filtro["fim"],
                empresa_id, filial_id, filtro["inicio"], filtro["fim"],
            ),
        )
        financeiro = cursor.fetchone() or {}

        faturamento = _decimal(vendas.get("faturamento"))
        custos = _decimal(financeiro.get("custos"))
        folha = _decimal(financeiro.get("folha"))
        outras_entradas = _decimal(financeiro.get("outras_entradas"))
        outras_saidas = _decimal(financeiro.get("outras_saidas"))
        total_saidas = custos + folha + outras_saidas
        resultado_liquido = faturamento + outras_entradas - total_saidas
        vendas_validas = int(vendas.get("vendas_validas") or 0)
        ticket_medio = faturamento / vendas_validas if vendas_validas else ZERO

        cursor.execute(
            """
            SELECT
                p.id,
                p.nome,
                COALESCE(pf.estoque, 0) AS estoque
            FROM produto_filial pf
            INNER JOIN produtos p
                ON p.id = pf.produto_id
            WHERE p.empresa_id = %s
              AND pf.filial_id = %s
              AND pf.ativo = TRUE
              AND COALESCE(pf.estoque, 0) <= 5
            ORDER BY COALESCE(pf.estoque, 0) ASC, p.nome
            LIMIT 6
            """,
            (empresa_id, filial_id),
        )
        produtos_baixos = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                p.id,
                p.nome,
                COALESCE(SUM(v.quantidade), 0) AS quantidade,
                COALESCE(SUM(v.valor), 0) AS faturamento
            FROM vendas v
            INNER JOIN produtos p
                ON p.id = v.produto_id
               AND p.empresa_id = v.empresa_id
            WHERE v.empresa_id = %s
              AND v.filial_id = %s
              AND COALESCE(v.cancelada, 0) = 0
              AND v.data_venda >= %s
              AND v.data_venda < %s
            GROUP BY p.id, p.nome
            ORDER BY quantidade DESC, faturamento DESC
            LIMIT 5
            """,
            (empresa_id, filial_id, filtro["inicio"], filtro["fim"]),
        )
        ranking = cursor.fetchall()

        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE status IN ('pendente', 'parcial')
                      AND data_vencimento < CURRENT_DATE
                ) AS despesas_vencidas,
                COALESCE(SUM(GREATEST(valor - valor_pago, 0)) FILTER (
                    WHERE status IN ('pendente', 'parcial')
                      AND data_vencimento < CURRENT_DATE
                ), 0) AS valor_vencido
            FROM custos_parcelas
            WHERE empresa_id = %s
              AND %s = (
                  SELECT fm.id
                  FROM filiais fm
                  WHERE fm.empresa_id = custos_parcelas.empresa_id
                    AND fm.matriz = TRUE
                  LIMIT 1
              )
              AND status <> 'cancelada'
            """,
            (empresa_id, filial_id),
        )
        vencimentos = cursor.fetchone() or {}

        alertas = []
        nome_filial = str(
            (empresa or {}).get("filial_nome") or "Matriz"
        )

        for produto in produtos_baixos:
            estoque = _numero(produto["estoque"])
            if estoque <= 0:
                titulo = f"{produto['nome']} está esgotado"
                nivel = "danger"
            else:
                titulo = f"{produto['nome']} possui apenas {estoque:g} unidade(s)"
                nivel = "warning"

            alertas.append(
                {
                    "titulo": titulo,
                    "descricao": (
                        f"Estoque da unidade {nome_filial}. "
                        "Revisar cadastro e reposição do produto."
                    ),
                    "url": f"/produtos?filial_id={filial_id}",
                    "nivel": nivel,
                }
            )

        despesas_vencidas = int(vencimentos.get("despesas_vencidas") or 0)
        if despesas_vencidas:
            alertas.insert(
                0,
                {
                    "titulo": f"{despesas_vencidas} despesa(s) vencida(s)",
                    "descricao": f"Saldo vencido de {_moeda(vencimentos.get('valor_vencido'))}.",
                    "url": "/custos?status=vencido",
                    "nivel": "critico",
                },
            )

        if not caixa_aberto:
            alertas.insert(
                0,
                {
                    "titulo": "Caixa fechado",
                    "descricao": "Abra o caixa antes de iniciar novas vendas.",
                    "url": "/caixa",
                    "nivel": "atencao",
                },
            )

        grafico = _grafico_vendas(cursor, empresa_id, filial_id, filtro)
        recebimentos = resumo_pagamentos(
            cursor, empresa_id, filtro["inicio"], filtro["fim"], filial_id
        )
        variacao_faturamento = _variacao(
            faturamento, vendas.get("faturamento_anterior")
        )
        variacao_vendas = _variacao(
            vendas_validas, vendas.get("vendas_anteriores")
        )

        metricas = {
            "faturamento": _numero(faturamento),
            "faturamento_formatado": _moeda(faturamento),
            "resultado_liquido": _numero(resultado_liquido),
            "resultado_liquido_formatado": _moeda(resultado_liquido),
            "vendas_validas": vendas_validas,
            "ticket_medio": _numero(ticket_medio),
            "ticket_medio_formatado": _moeda(ticket_medio),
            "itens_vendidos": _numero(vendas.get("itens_vendidos")),
            "clientes_identificados": int(vendas.get("clientes_identificados") or 0),
            "vendas_canceladas": int(vendas.get("vendas_canceladas") or 0),
            "total_cancelado": _numero(vendas.get("total_cancelado")),
            "total_cancelado_formatado": _moeda(vendas.get("total_cancelado")),
            "descontos": _numero(vendas.get("descontos")),
            "descontos_formatado": _moeda(vendas.get("descontos")),
            "total_saidas": _numero(total_saidas),
            "total_saidas_formatado": _moeda(total_saidas),
            "custos": _numero(custos),
            "folha": _numero(folha),
            "outras_saidas": _numero(outras_saidas),
            "variacao_faturamento": variacao_faturamento,
            "variacao_vendas": variacao_vendas,
            "recebimentos": recebimentos,
        }

        produto_mais_vendido = ranking[0] if ranking else None
        insight = _insight_nami(metricas, alertas, produto_mais_vendido)

        return {
            "empresa": empresa,
            "caixa_aberto": caixa_aberto,
            "metricas": metricas,
            "grafico": grafico,
            "alertas": alertas[:6],
            "ranking": ranking,
            "insight_nami": insight,
            "periodo": {
                "chave": filtro["chave"],
                "titulo": filtro["titulo"],
                "inicio": filtro["inicio_data"].isoformat(),
                "fim": filtro["fim_data"].isoformat(),
                "descricao": (
                    f"{filtro['inicio_data'].strftime('%d/%m/%Y')} até "
                    f"{filtro['fim_data'].strftime('%d/%m/%Y')}"
                ),
            },
        }
    finally:
        cursor.close()
        conn.close()


def registrar_rotas(app):
    @app.route("/dashboard")
    def dashboard():
        if not session.get("logado"):
            return redirect("/")

        empresa_id = session.get("empresa_id")
        if not empresa_id:
            return redirect("/")

        filial, filiais, pode_alternar = _resolver_filial_dashboard(empresa_id)
        dados = _carregar_dashboard(
            empresa_id,
            int(filial["id"]),
            _periodo_dashboard(),
        )

        return render_template(
            "dashboard.html",
            usuario=session.get("usuario"),
            nivel=session.get("nivel"),
            filial_atual=filial,
            filiais=filiais,
            pode_alternar_filial=pode_alternar,
            **dados,
        )

    @app.route("/api/dashboard")
    def api_dashboard():
        if not session.get("logado"):
            return jsonify({"erro": "Não autorizado."}), 401

        empresa_id = session.get("empresa_id")
        if not empresa_id:
            return jsonify({"erro": "Empresa não encontrada."}), 400

        try:
            filial, _, _ = _resolver_filial_dashboard(empresa_id)
            dados = _carregar_dashboard(
                empresa_id,
                int(filial["id"]),
                _periodo_dashboard(),
            )

            return jsonify(
                {
                    "metricas": dados["metricas"],
                    "grafico": dados["grafico"],
                    "alertas": dados["alertas"],
                    "ranking": [dict(item) for item in dados["ranking"]],
                    "insight_nami": dados["insight_nami"],
                    "caixa_aberto": bool(dados["caixa_aberto"]),
                }
            )
        except Exception:
            app.logger.exception("Erro ao atualizar o dashboard.")
            return jsonify({"erro": "Não foi possível atualizar o painel."}), 500
