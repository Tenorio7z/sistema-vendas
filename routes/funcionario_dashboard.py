from datetime import date, datetime, timedelta

from flask import (
    abort,
    redirect,
    render_template,
    request,
    session,
)

from database import conectar, criar_cursor


def _converter_data(valor):
    if not valor:
        return None

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d"
        ).date()

    except ValueError:
        return None


def _calcular_periodo(
    periodo,
    data_inicial_texto=None,
    data_final_texto=None,
):
    hoje = date.today()

    if periodo == "hoje":
        inicio = hoje
        fim = hoje + timedelta(days=1)
        titulo = "Hoje"

    elif periodo == "7_dias":
        inicio = hoje - timedelta(days=6)
        fim = hoje + timedelta(days=1)
        titulo = "Ultimos 7 dias"

    elif periodo == "30_dias":
        inicio = hoje - timedelta(days=29)
        fim = hoje + timedelta(days=1)
        titulo = "Ultimos 30 dias"

    elif periodo == "ano":
        inicio = date(
            hoje.year,
            1,
            1
        )

        fim = date(
            hoje.year + 1,
            1,
            1
        )

        titulo = "Este ano"

    elif periodo == "personalizado":
        inicio = _converter_data(
            data_inicial_texto
        )

        data_final = _converter_data(
            data_final_texto
        )

        if not inicio or not data_final:
            periodo = "mes"

            inicio = date(
                hoje.year,
                hoje.month,
                1
            )

            if hoje.month == 12:
                fim = date(
                    hoje.year + 1,
                    1,
                    1
                )
            else:
                fim = date(
                    hoje.year,
                    hoje.month + 1,
                    1
                )

            titulo = "Este mes"

        else:
            if data_final < inicio:
                inicio, data_final = (
                    data_final,
                    inicio,
                )

            fim = (
                data_final
                + timedelta(days=1)
            )

            titulo = (
                f"{inicio.strftime('%d/%m/%Y')} "
                f"ate "
                f"{data_final.strftime('%d/%m/%Y')}"
            )

    else:
        periodo = "mes"

        inicio = date(
            hoje.year,
            hoje.month,
            1
        )

        if hoje.month == 12:
            fim = date(
                hoje.year + 1,
                1,
                1
            )
        else:
            fim = date(
                hoje.year,
                hoje.month + 1,
                1
            )

        titulo = "Este mes"

    return {
        "periodo": periodo,
        "inicio": inicio,
        "fim": fim,
        "titulo": titulo,
    }


def registrar_rotas(app):

    @app.route(
        "/painel-funcionario/<int:funcionario_id>"
    )
    
    @app.route(
        "/dashboard_funcionario/<int:funcionario_id>"
    )
    def painel_funcionario(
        funcionario_id
    ):
        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "gerente":
            return redirect("/dashboard")

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            return redirect("/")

        periodo_selecionado = request.args.get(
            "periodo",
            "mes"
        )

        data_inicial_texto = request.args.get(
            "data_inicial",
            ""
        )

        data_final_texto = request.args.get(
            "data_final",
            ""
        )

        periodo = _calcular_periodo(
            periodo_selecionado,
            data_inicial_texto,
            data_final_texto,
        )

        inicio = periodo["inicio"]
        fim = periodo["fim"]

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.usuario,
                    u.nivel,
                    u.status,
                    u.empresa_id,
                    COALESCE(u.comissao, 0) AS comissao,
                    u.filial_id,
                    COALESCE(fc.salario_base, 0) AS salario_base
                FROM usuarios u
                LEFT JOIN funcionarios_config fc
                  ON fc.usuario_id = u.id AND fc.empresa_id = u.empresa_id
                WHERE u.id = %s
                  AND u.empresa_id = %s
                  AND u.nivel = 'funcionario'
                """,
                (
                    funcionario_id,
                    empresa_id,
                ),
            )

            funcionario = cursor.fetchone()

            if not funcionario:
                abort(404)

            percentual_comissao = float(
                funcionario["comissao"]
                or 0
            )

            cursor.execute(
                """
                SELECT
                    COUNT(id)
                        AS total_vendas,

                    COALESCE(
                        SUM(quantidade),
                        0
                    ) AS total_itens,

                    COALESCE(
                        SUM(valor),
                        0
                    ) AS faturamento,

                    COALESCE(
                        AVG(valor),
                        0
                    ) AS ticket_medio,

                    MAX(data_venda)
                        AS ultima_venda

                FROM vendas

                WHERE usuario_id = %s
                  AND empresa_id = %s
                  AND cancelada = 0
                  AND data_venda >= %s
                  AND data_venda < %s
                """,
                (
                    funcionario_id,
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            resumo = cursor.fetchone() or {}

            faturamento = float(
                resumo.get(
                    "faturamento",
                    0
                )
                or 0
            )

            total_vendas = int(
                resumo.get(
                    "total_vendas",
                    0
                )
                or 0
            )

            total_itens = int(
                resumo.get(
                    "total_itens",
                    0
                )
                or 0
            )

            ticket_medio = float(
                resumo.get(
                    "ticket_medio",
                    0
                )
                or 0
            )

            valor_comissao = (
                faturamento
                * percentual_comissao
                / 100
            )

            filial_id = funcionario.get("filial_id")

            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE pf.ativo = TRUE
                    ) AS total_produtos,

                    COALESCE(
                        SUM(
                            CASE
                                WHEN pf.ativo = TRUE
                                THEN COALESCE(p.preco, 0)
                                   * COALESCE(pf.estoque, 0)
                                ELSE 0
                            END
                        ),
                        0
                    ) AS valor_total_estoque

                FROM produto_filial pf

                INNER JOIN produtos p
                    ON p.id = pf.produto_id

                WHERE pf.filial_id = %s
                  AND p.empresa_id = %s
                """,
                (
                    filial_id,
                    empresa_id,
                ),
            )

            resumo_estoque = cursor.fetchone() or {}

            total_produtos_cadastrados = int(
                resumo_estoque.get(
                    "total_produtos",
                    0
                )
                or 0
            )

            total_esperado = float(
                resumo_estoque.get(
                    "valor_total_estoque",
                    0
                )
                or 0
            )
            
            comissao_esperada = (
                total_esperado
                * percentual_comissao
                / 100
            )

            salario_base = float(
                funcionario.get(
                    "salario_base",
                    0
                )
                or 0
            )

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
                    ) AS total_vendido,

                    COUNT(v.id)
                        AS quantidade_vendas

                FROM vendas v

                INNER JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                WHERE v.usuario_id = %s
                  AND v.empresa_id = %s
                  AND v.cancelada = 0
                  AND v.data_venda >= %s
                  AND v.data_venda < %s

                GROUP BY
                    p.id,
                    p.nome

                ORDER BY
                    quantidade DESC,
                    total_vendido DESC,
                    p.nome ASC

                LIMIT 20
                """,
                (
                    funcionario_id,
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            produtos_vendidos = (
                cursor.fetchall()
                or []
            )

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        NULLIF(
                            TRIM(pagamento),
                            ''
                        ),
                        'Nao informado'
                    ) AS pagamento,

                    COUNT(id)
                        AS quantidade,

                    COALESCE(
                        SUM(valor),
                        0
                    ) AS total

                FROM vendas

                WHERE usuario_id = %s
                  AND empresa_id = %s
                  AND cancelada = 0
                  AND data_venda >= %s
                  AND data_venda < %s

                GROUP BY
                    COALESCE(
                        NULLIF(
                            TRIM(pagamento),
                            ''
                        ),
                        'Nao informado'
                    )

                ORDER BY total DESC
                """,
                (
                    funcionario_id,
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            formas_pagamento = (
                cursor.fetchall()
                or []
            )

            cursor.execute(
                """
                SELECT
                    v.id,
                    v.quantidade,
                    v.valor,
                    v.pagamento,
                    v.data_venda,
                    v.cancelada,
                    p.nome AS produto_nome

                FROM vendas v

                LEFT JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                WHERE v.usuario_id = %s
                  AND v.empresa_id = %s
                  AND v.data_venda >= %s
                  AND v.data_venda < %s

                ORDER BY
                    v.data_venda DESC,
                    v.id DESC

                LIMIT 100
                """,
                (
                    funcionario_id,
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            historico = (
                cursor.fetchall()
                or []
            )

            cursor.execute(
                """
                SELECT
                    COUNT(id)
                        AS quantidade_canceladas,

                    COALESCE(
                        SUM(valor),
                        0
                    ) AS valor_cancelado

                FROM vendas

                WHERE usuario_id = %s
                  AND empresa_id = %s
                  AND cancelada = 1
                  AND data_venda >= %s
                  AND data_venda < %s
                """,
                (
                    funcionario_id,
                    empresa_id,
                    inicio,
                    fim,
                ),
            )

            cancelamentos = (
                cursor.fetchone()
                or {}
            )

            return render_template(
                "dashboard_funcionario_novo.html",

                funcionario=funcionario,

                periodo=periodo,
                data_inicial=data_inicial_texto,
                data_final=data_final_texto,

                faturamento=faturamento,
                total_vendas=total_vendas,
                total_itens=total_itens,
                ticket_medio=ticket_medio,

                percentual_comissao=(
                    percentual_comissao
                ),

                valor_comissao=(
                    valor_comissao
                ),
                total_produtos_cadastrados=total_produtos_cadastrados,
                salario_base=salario_base,
                total_esperado=total_esperado,
                comissao_esperada=comissao_esperada,

                ultima_venda=resumo.get(
                    "ultima_venda"
                ),

                produtos_vendidos=(
                    produtos_vendidos
                ),

                formas_pagamento=(
                    formas_pagamento
                ),

                historico=historico,

                cancelamentos=(
                    cancelamentos
                ),
            )

        finally:
            cursor.close()
            conn.close()
