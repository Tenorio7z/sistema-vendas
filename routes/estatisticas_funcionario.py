from datetime import date, datetime, timedelta

from flask import (
    redirect,
    render_template,
    request,
    session,
)

from database import conectar, criar_cursor


def _numero(valor):
    return float(valor or 0)


def _data_formulario(valor, padrao):
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

    tipo = request.args.get(
        "periodo",
        "mes",
    ).strip().lower()

    if tipo == "hoje":
        inicio = hoje
        fim = hoje + timedelta(days=1)
        titulo = "Hoje"

    elif tipo == "ano":
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

    elif tipo == "personalizado":
        inicio = _data_formulario(
            request.args.get("inicio"),
            date(
                hoje.year,
                hoje.month,
                1,
            ),
        )

        ultimo_dia = _data_formulario(
            request.args.get("fim"),
            hoje,
        )

        if ultimo_dia < inicio:
            ultimo_dia = inicio

        fim = ultimo_dia + timedelta(days=1)
        titulo = "Período personalizado"

    else:
        tipo = "mes"

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
        "tipo": tipo,
        "titulo": titulo,
        "inicio": inicio,
        "fim": fim,
        "fim_exibicao": fim - timedelta(days=1),
    }


def registrar_rotas(app):

    @app.route("/minhas-estatisticas")
    def minhas_estatisticas():

        if not session.get("logado"):
            return redirect("/")

        # Gerente continua usando a estatística empresarial.
        if session.get("nivel") == "gerente":
            return redirect("/estatisticas")

        if session.get("nivel") != "funcionario":
            return redirect("/dashboard")

        empresa_id = session.get("empresa_id")
        usuario_id = session.get("usuario_id")

        if not empresa_id or not usuario_id:
            session.clear()
            return redirect("/")

        periodo = _obter_periodo()

        inicio = periodo["inicio"]
        fim = periodo["fim"]

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            # =====================================
            # CONFIRMAR FUNCIONÁRIO AUTENTICADO
            # =====================================

            cursor.execute(
                """
                SELECT
                    u.id,
                    u.usuario,
                    u.status,
                    COALESCE(u.comissao, 0) AS percentual_comissao,
                    COALESCE(fc.cargo, 'Funcionário') AS cargo,
                    COALESCE(fc.salario_base, 0) AS salario_base

                FROM usuarios u

                LEFT JOIN funcionarios_config fc
                    ON fc.usuario_id = u.id
                   AND fc.empresa_id = u.empresa_id

                WHERE u.id = %s
                  AND u.empresa_id = %s
                  AND u.nivel = 'funcionario'

                LIMIT 1
                """,
                (
                    usuario_id,
                    empresa_id,
                ),
            )

            funcionario = cursor.fetchone()

            if not funcionario:
                session.clear()
                return redirect("/")

            percentual_comissao = _numero(
                funcionario.get(
                    "percentual_comissao"
                )
            )

            # =====================================
            # RESUMO DAS VENDAS
            # Uma venda pode possuir vários itens.
            # =====================================

            cursor.execute(
                """
                SELECT
                    COUNT(
                        DISTINCT COALESCE(
                            venda_grupo,
                            'legado-' || id::TEXT
                        )
                    ) FILTER (
                        WHERE COALESCE(cancelada, 0) = 0
                    ) AS total_vendas,

                    COUNT(
                        DISTINCT COALESCE(
                            venda_grupo,
                            'legado-' || id::TEXT
                        )
                    ) FILTER (
                        WHERE COALESCE(cancelada, 0) = 1
                    ) AS vendas_canceladas,

                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE COALESCE(cancelada, 0) = 0
                        ),
                        0
                    ) AS faturamento,

                    COALESCE(
                        SUM(
                            COALESCE(valor_bruto, valor)
                        ) FILTER (
                            WHERE COALESCE(cancelada, 0) = 0
                        ),
                        0
                    ) AS faturamento_bruto,

                    COALESCE(
                        SUM(
                            COALESCE(desconto_valor, 0)
                        ) FILTER (
                            WHERE COALESCE(cancelada, 0) = 0
                        ),
                        0
                    ) AS descontos,

                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE COALESCE(cancelada, 0) = 1
                        ),
                        0
                    ) AS total_cancelado,

                    COALESCE(
                        SUM(quantidade) FILTER (
                            WHERE COALESCE(cancelada, 0) = 0
                        ),
                        0
                    ) AS itens_vendidos

                FROM vendas

                WHERE empresa_id = %s
                  AND usuario_id = %s
                  AND data_venda >= %s
                  AND data_venda < %s
                """,
                (
                    empresa_id,
                    usuario_id,
                    inicio,
                    fim,
                ),
            )

            resumo_banco = cursor.fetchone() or {}

            total_vendas = int(
                resumo_banco.get("total_vendas")
                or 0
            )

            vendas_canceladas = int(
                resumo_banco.get(
                    "vendas_canceladas"
                )
                or 0
            )

            itens_vendidos = int(
                resumo_banco.get("itens_vendidos")
                or 0
            )

            faturamento = _numero(
                resumo_banco.get("faturamento")
            )

            faturamento_bruto = _numero(
                resumo_banco.get(
                    "faturamento_bruto"
                )
            )

            descontos = _numero(
                resumo_banco.get("descontos")
            )

            total_cancelado = _numero(
                resumo_banco.get(
                    "total_cancelado"
                )
            )

            ticket_medio = (
                faturamento / total_vendas
                if total_vendas
                else 0
            )

            comissao_gerada = (
                faturamento
                * percentual_comissao
                / 100
            )

            # =====================================
            # COMISSÃO EFETIVAMENTE PAGA
            # =====================================

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(valor_comissao),
                        0
                    ) AS comissao_paga,

                    COALESCE(
                        SUM(valor_bonus),
                        0
                    ) AS bonus_pago,

                    COALESCE(
                        SUM(valor_total),
                        0
                    ) AS total_recebido,

                    COUNT(*) AS pagamentos

                FROM folha_pagamentos

                WHERE empresa_id = %s
                  AND usuario_id = %s
                  AND status = 'pago'
                  AND data_pagamento >= %s
                  AND data_pagamento < %s
                """,
                (
                    empresa_id,
                    usuario_id,
                    inicio,
                    fim,
                ),
            )

            folha = cursor.fetchone() or {}

            comissao_paga = _numero(
                folha.get("comissao_paga")
            )

            bonus_pago = _numero(
                folha.get("bonus_pago")
            )

            total_recebido = _numero(
                folha.get("total_recebido")
            )

            pagamentos_recebidos = int(
                folha.get("pagamentos")
                or 0
            )

            # A comissão pendente nunca pode ficar negativa.
            comissao_pendente = max(
                comissao_gerada - comissao_paga,
                0,
            )

            # =====================================
            # PRODUTOS MAIS VENDIDOS
            # =====================================

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.nome,

                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS quantidade,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS faturamento

                FROM vendas v

                INNER JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND v.usuario_id = %s
                  AND COALESCE(v.cancelada, 0) = 0
                  AND v.data_venda >= %s
                  AND v.data_venda < %s

                GROUP BY
                    p.id,
                    p.nome

                ORDER BY
                    quantidade DESC,
                    faturamento DESC

                LIMIT 8
                """,
                (
                    empresa_id,
                    usuario_id,
                    inicio,
                    fim,
                ),
            )

            produtos = cursor.fetchall() or []

            # =====================================
            # DESEMPENHO DIÁRIO
            # =====================================

            cursor.execute(
                """
                SELECT
                    DATE(data_venda) AS dia,

                    COUNT(
                        DISTINCT COALESCE(
                            venda_grupo,
                            'legado-' || id::TEXT
                        )
                    ) AS vendas,

                    COALESCE(
                        SUM(quantidade),
                        0
                    ) AS itens,

                    COALESCE(
                        SUM(valor),
                        0
                    ) AS faturamento

                FROM vendas

                WHERE empresa_id = %s
                  AND usuario_id = %s
                  AND COALESCE(cancelada, 0) = 0
                  AND data_venda >= %s
                  AND data_venda < %s

                GROUP BY DATE(data_venda)
                ORDER BY dia
                """,
                (
                    empresa_id,
                    usuario_id,
                    inicio,
                    fim,
                ),
            )

            desempenho_diario = (
                cursor.fetchall()
                or []
            )

            maior_faturamento_dia = max(
                (
                    _numero(
                        item.get("faturamento")
                    )
                    for item in desempenho_diario
                ),
                default=0,
            )

            # =====================================
            # HISTÓRICO DAS VENDAS
            # =====================================

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        venda_grupo,
                        'legado-' || id::TEXT
                    ) AS grupo,

                    MIN(data_venda) AS data_venda,

                    MAX(pagamento) AS pagamento,

                    SUM(quantidade) AS quantidade_itens,

                    SUM(
                        COALESCE(valor_bruto, valor)
                    ) AS valor_bruto,

                    SUM(
                        COALESCE(desconto_valor, 0)
                    ) AS desconto,

                    SUM(valor) AS valor,

                    BOOL_OR(
                        COALESCE(cancelada, 0) = 1
                    ) AS cancelada

                FROM vendas

                WHERE empresa_id = %s
                  AND usuario_id = %s
                  AND data_venda >= %s
                  AND data_venda < %s

                GROUP BY COALESCE(
                    venda_grupo,
                    'legado-' || id::TEXT
                )

                ORDER BY MIN(data_venda) DESC

                LIMIT 50
                """,
                (
                    empresa_id,
                    usuario_id,
                    inicio,
                    fim,
                ),
            )

            historico_vendas = (
                cursor.fetchall()
                or []
            )

            return render_template(
                "estatisticas_funcionario.html",

                funcionario=funcionario,
                periodo=periodo,

                total_vendas=total_vendas,
                vendas_canceladas=vendas_canceladas,
                itens_vendidos=itens_vendidos,

                faturamento=faturamento,
                faturamento_bruto=faturamento_bruto,
                descontos=descontos,
                total_cancelado=total_cancelado,
                ticket_medio=ticket_medio,

                percentual_comissao=(
                    percentual_comissao
                ),
                comissao_gerada=comissao_gerada,
                comissao_paga=comissao_paga,
                comissao_pendente=(
                    comissao_pendente
                ),

                bonus_pago=bonus_pago,
                total_recebido=total_recebido,
                pagamentos_recebidos=(
                    pagamentos_recebidos
                ),

                produtos=produtos,
                desempenho_diario=(
                    desempenho_diario
                ),
                maior_faturamento_dia=(
                    maior_faturamento_dia
                ),

                historico_vendas=(
                    historico_vendas
                ),
            )

        finally:
            cursor.close()
            conn.close()