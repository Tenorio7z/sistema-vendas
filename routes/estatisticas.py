from datetime import date, datetime, timedelta

from flask import (
    redirect,
    render_template,
    request,
    session,
)

from database import conectar, criar_cursor


def _converter_data(valor, padrao):

    if not valor:
        return padrao

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        return padrao


def _obter_periodo():

    hoje = date.today()

    periodo = request.args.get(
        "periodo",
        "mes",
    ).strip().lower()

    if periodo == "hoje":
        inicio = hoje
        fim = hoje + timedelta(days=1)
        titulo = "Hoje"

    elif periodo == "ano":
        inicio = date(
            hoje.year,
            1,
            1,
        )

        fim = date(
            hoje.year + 1,
            1,
            1,
        )

        titulo = "Este ano"

    elif periodo == "personalizado":
        inicio = _converter_data(
            request.args.get("inicio"),
            date(
                hoje.year,
                hoje.month,
                1,
            ),
        )

        fim_informado = _converter_data(
            request.args.get("fim"),
            hoje,
        )

        if fim_informado < inicio:
            fim_informado = inicio

        fim = fim_informado + timedelta(days=1)
        titulo = "Período personalizado"

    else:
        periodo = "mes"

        inicio = date(
            hoje.year,
            hoje.month,
            1,
        )

        if hoje.month == 12:
            fim = date(
                hoje.year + 1,
                1,
                1,
            )

        else:
            fim = date(
                hoje.year,
                hoje.month + 1,
                1,
            )

        titulo = "Este mês"

    return {
        "periodo": periodo,
        "inicio": inicio,
        "fim": fim,
        "fim_exibicao": (
            fim - timedelta(days=1)
        ),
        "titulo": titulo,
    }


def _decimal_para_float(valor):

    return float(
        valor or 0
    )


def registrar_rotas(app):

    @app.route("/estatisticas")
    def estatisticas():

        if not session.get("logado"):
            return redirect("/")

        if session.get("plano") == "comum":
            return render_template(
                "estatisticas.html",
                bloqueado=True,
                labels=[],
                valores=[],
            )

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            return redirect("/")

        filtro = _obter_periodo()

        inicio = filtro["inicio"]
        fim = filtro["fim"]

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            # =====================================
            # VENDAS DO PERÍODO
            # =====================================

            cursor.execute(
            """
            SELECT
                COUNT(*) AS quantidade_bruta,

                COALESCE(
                    SUM(
                        COALESCE(
                            valor_bruto,
                            valor
                        )
                    ),
                    0
                ) AS faturamento_bruto,

                COUNT(*) FILTER (
                    WHERE COALESCE(cancelada, 0) = 0
                ) AS vendas_validas,

                COALESCE(
                    SUM(valor) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ),
                    0
                ) AS faturamento_realizado,

                COALESCE(
                    SUM(
                        COALESCE(
                            desconto_valor,
                            0
                        )
                    ) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ),
                    0
                ) AS descontos_comerciais,

                COUNT(*) FILTER (
                    WHERE COALESCE(cancelada, 0) = 1
                ) AS vendas_canceladas,

                COALESCE(
                    SUM(valor) FILTER (
                        WHERE COALESCE(cancelada, 0) = 1
                    ),
                    0
                ) AS total_cancelado

            FROM vendas

            WHERE empresa_id = %s
            AND data_venda >= %s
            AND data_venda < %s
            """,
            (
                empresa_id,
                inicio,
                fim,
            ),
        )

            vendas = cursor.fetchone() or {}

            # =====================================
            # CANCELAMENTOS FEITOS NO PERÍODO
            # =====================================

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS quantidade,
                    COALESCE(
                        SUM(valor),
                        0
                    ) AS total

                FROM vendas

                WHERE empresa_id = %s
                  AND COALESCE(cancelada, 0) = 1
                  AND COALESCE(
                      cancelada_em,
                      data_venda
                  ) >= %s
                  AND COALESCE(
                      cancelada_em,
                      data_venda
                  ) < %s
                """,
                (
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            cancelamentos_periodo = (
                cursor.fetchone()
                or {}
            )

            # =====================================
            # FOLHAS EFETIVAMENTE PAGAS
            # =====================================

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS quantidade,

                    COALESCE(
                        SUM(salario_base),
                        0
                    ) AS salarios,

                    COALESCE(
                        SUM(valor_comissao),
                        0
                    ) AS comissoes,

                    COALESCE(
                        SUM(valor_bonus),
                        0
                    ) AS bonus,

                    COALESCE(
                        SUM(valor_descontos),
                        0
                    ) AS descontos_folha,

                    COALESCE(
                        SUM(valor_total),
                        0
                    ) AS total_pago

                FROM folha_pagamentos

                WHERE empresa_id = %s
                  AND status = 'pago'
                  AND data_pagamento >= %s
                  AND data_pagamento < %s
                """,
                (
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            folha = cursor.fetchone() or {}

            # =====================================
            # OUTRAS MOVIMENTAÇÕES DO CAIXA
            # Evita duplicar folha e cancelamentos.
            # =====================================

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE tipo = 'entrada'
                              AND LOWER(
                                  COALESCE(descricao, '')
                              ) <> 'abertura de caixa'
                        ),
                        0
                    ) AS outras_entradas,

                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE tipo = 'saida'
                              AND LOWER(
                                  COALESCE(descricao, '')
                              ) NOT LIKE
                                  'cancelamento da venda%%'
                              AND LOWER(
                                  COALESCE(descricao, '')
                              ) NOT LIKE
                                  'pagamento da folha%%'
                        ),
                        0
                    ) AS outras_saidas

                FROM movimentacoes_caixa

                WHERE empresa_id = %s
                  AND data >= %s
                  AND data < %s
                """,
                (
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            caixa = cursor.fetchone() or {}

            faturamento_bruto = _decimal_para_float(
                vendas.get("faturamento_bruto")
            )

            descontos_comerciais = (
                _decimal_para_float(
                    vendas.get(
                        "descontos_comerciais"
                    )
                )
            )

            faturamento_realizado = _decimal_para_float(
                vendas.get("faturamento_realizado")
            )

            total_cancelado = _decimal_para_float(
                cancelamentos_periodo.get("total")
            )

            salarios = _decimal_para_float(
                folha.get("salarios")
            )

            comissoes = _decimal_para_float(
                folha.get("comissoes")
            )

            bonus = _decimal_para_float(
                folha.get("bonus")
            )

            descontos_folha = _decimal_para_float(
                folha.get("descontos_folha")
            )

            total_folha = _decimal_para_float(
                folha.get("total_pago")
            )

            outras_entradas = _decimal_para_float(
                caixa.get("outras_entradas")
            )

            outras_saidas = _decimal_para_float(
                caixa.get("outras_saidas")
            )

            total_saidas = (
                total_folha
                + outras_saidas
            )

            resultado_liquido = (
                faturamento_realizado
                + outras_entradas
                - total_saidas
            )

            vendas_validas = int(
                vendas.get("vendas_validas")
                or 0
            )

            ticket_medio = (
                faturamento_realizado
                / vendas_validas
                if vendas_validas
                else 0
            )

            margem_liquida = (
                resultado_liquido
                / faturamento_realizado
                * 100
                if faturamento_realizado
                else 0
            )

            # =====================================
            # PRODUTO MAIS VENDIDO
            # =====================================

            cursor.execute(
                """
                SELECT
                    p.nome,
                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS quantidade

                FROM vendas v

                INNER JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND COALESCE(v.cancelada, 0) = 0
                  AND v.data_venda >= %s
                  AND v.data_venda < %s

                GROUP BY
                    p.id,
                    p.nome

                ORDER BY quantidade DESC

                LIMIT 1
                """,
                (
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            produto_top = cursor.fetchone()

            # =====================================
            # GRÁFICO FINANCEIRO DIÁRIO
            # =====================================

            cursor.execute(
                """
                SELECT
                    dia,

                    COALESCE(
                        SUM(entradas),
                        0
                    ) AS entradas,

                    COALESCE(
                        SUM(saidas),
                        0
                    ) AS saidas

                FROM (
                    SELECT
                        DATE(data_venda) AS dia,

                        SUM(valor) FILTER (
                            WHERE COALESCE(cancelada, 0) = 0
                        ) AS entradas,

                        0::NUMERIC AS saidas

                    FROM vendas

                    WHERE empresa_id = %s
                      AND data_venda >= %s
                      AND data_venda < %s

                    GROUP BY DATE(data_venda)

                    UNION ALL

                    SELECT
                        DATE(data_pagamento) AS dia,
                        0::NUMERIC AS entradas,
                        SUM(valor_total) AS saidas

                    FROM folha_pagamentos

                    WHERE empresa_id = %s
                      AND status = 'pago'
                      AND data_pagamento >= %s
                      AND data_pagamento < %s

                    GROUP BY DATE(data_pagamento)

                    UNION ALL

                    SELECT
                        DATE(data) AS dia,
                        0::NUMERIC AS entradas,
                        SUM(valor) AS saidas

                    FROM movimentacoes_caixa

                    WHERE empresa_id = %s
                      AND tipo = 'saida'
                      AND data >= %s
                      AND data < %s
                      AND LOWER(
                          COALESCE(descricao, '')
                      ) NOT LIKE
                          'cancelamento da venda%%'
                      AND LOWER(
                          COALESCE(descricao, '')
                      ) NOT LIKE
                          'pagamento da folha%%'

                    GROUP BY DATE(data)
                ) financeiro

                GROUP BY dia
                ORDER BY dia
                """,
                (
                    empresa_id,
                    inicio,
                    fim,

                    empresa_id,
                    inicio,
                    fim,

                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            dados_grafico = (
                cursor.fetchall()
                or []
            )

            labels = [
                item["dia"].strftime(
                    "%d/%m"
                )
                for item in dados_grafico
            ]

            valores = [
                _decimal_para_float(
                    item["entradas"]
                )
                for item in dados_grafico
            ]

            valores_saidas = [
                _decimal_para_float(
                    item["saidas"]
                )
                for item in dados_grafico
            ]

            # =====================================
            # ÚLTIMAS SAÍDAS
            # =====================================

            # =====================================
            # EXTRATO FINANCEIRO COMPLETO
            # =====================================

            cursor.execute(
                """
                SELECT *
                FROM (
                    -- =================================
                    -- VENDAS VÁLIDAS
                    -- =================================

                    SELECT
                        MIN(v.data_venda) AS data,

                        (
                            'Venda'
                            ||
                            CASE
                                WHEN v.venda_grupo IS NOT NULL
                                THEN
                                    ' #' ||
                                    LEFT(
                                        v.venda_grupo,
                                        8
                                    )

                                ELSE
                                    ' #' ||
                                    MIN(v.id)::TEXT
                            END
                        ) AS descricao,

                        SUM(v.valor) AS valor,

                        'Vendas' AS categoria,

                        'entrada' AS tipo

                    FROM vendas v

                    WHERE v.empresa_id = %s
                    AND COALESCE(v.cancelada, 0) = 0
                    AND v.data_venda >= %s
                    AND v.data_venda < %s

                    GROUP BY
                        COALESCE(
                            v.venda_grupo,
                            'legado-' || v.id::TEXT
                        ),
                        v.venda_grupo

                    UNION ALL

                    -- =================================
                    -- MOVIMENTAÇÕES DO CAIXA
                    -- =================================

                    SELECT
                        mc.data,
                        mc.descricao,
                        mc.valor,
                        'Caixa' AS categoria,
                        mc.tipo

                    FROM movimentacoes_caixa mc

                    WHERE mc.empresa_id = %s
                    AND mc.data >= %s
                    AND mc.data < %s

                    UNION ALL

                    -- =================================
                    -- FOLHAS PAGAS FORA DO CAIXA
                    -- =================================

                    SELECT
                        fp.data_pagamento AS data,

                        (
                            'Folha de pagamento - '
                            || u.usuario
                        ) AS descricao,

                        fp.valor_total AS valor,

                        'Funcionários' AS categoria,

                        'saida' AS tipo

                    FROM folha_pagamentos fp

                    INNER JOIN usuarios u
                        ON u.id = fp.usuario_id
                    AND u.empresa_id = fp.empresa_id

                    WHERE fp.empresa_id = %s
                    AND fp.status = 'pago'
                    AND fp.data_pagamento >= %s
                    AND fp.data_pagamento < %s
                    AND fp.caixa_id IS NULL
                ) extrato

                ORDER BY data DESC

                LIMIT 30
                """,
                (
                    empresa_id,
                    inicio,
                    fim,

                    empresa_id,
                    inicio,
                    fim,

                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            movimentacoes_financeiras = (
                cursor.fetchall()
                or []
            )

            return render_template(
                "estatisticas.html",

                bloqueado=False,
                filtro=filtro,

                faturamento_bruto=faturamento_bruto,

                descontos_comerciais=(
                    descontos_comerciais
                ),

                faturamento_realizado=(
                    faturamento_realizado
                ),

                resultado_liquido=(
                    resultado_liquido
                ),

                total_cancelado=total_cancelado,
                quantidade_cancelamentos=int(
                    cancelamentos_periodo.get(
                        "quantidade"
                    )
                    or 0
                ),

                salarios=salarios,
                comissoes=comissoes,
                bonus=bonus,
                descontos_folha=descontos_folha,
                total_folha=total_folha,

                outras_entradas=outras_entradas,
                outras_saidas=outras_saidas,
                total_saidas=total_saidas,

                total_vendas=vendas_validas,
                ticket_medio=ticket_medio,
                margem_liquida=margem_liquida,

                produto_top=(
                    produto_top["nome"]
                    if produto_top
                    else "Nenhum"
                ),

                produto_top_quantidade=(
                    int(
                        produto_top["quantidade"]
                        or 0
                    )
                    if produto_top
                    else 0
                ),

                folhas_pagas=int(
                    folha.get("quantidade")
                    or 0
                ),

                labels=labels,
                valores=valores,
                valores_saidas=valores_saidas,

                movimentacoes_financeiras=(
                    movimentacoes_financeiras
                ),
            )

        finally:
            cursor.close()
            conn.close()