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
                    id,
                    usuario,
                    nivel,
                    status,
                    empresa_id,
                    COALESCE(comissao, 0)
                        AS comissao
                FROM usuarios
                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'
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