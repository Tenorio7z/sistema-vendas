from database import conectar, criar_cursor

from services.ia.capabilities.consultas import (
    ConsultasNami,
)


class ConsultasClientesNami:

    @staticmethod
    def _limite(valor, padrao=10, maximo=50):
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            valor = padrao

        return max(1, min(valor, maximo))

    @classmethod
    def resumo(
        cls,
        empresa_id,
    ):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE ativo = TRUE
                    ) AS ativos,
                    COUNT(*) FILTER (
                        WHERE ativo = FALSE
                    ) AS inativos,
                    COUNT(*) FILTER (
                        WHERE criado_em::date = CURRENT_DATE
                    ) AS cadastrados_hoje,
                    COUNT(*) FILTER (
                        WHERE criado_em >=
                            DATE_TRUNC('month', CURRENT_DATE)
                    ) AS cadastrados_mes
                FROM clientes
                WHERE empresa_id = %s
                """,
                (empresa_id,),
            )

            return cursor.fetchone() or {}

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def ranking(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        ordem="maior_valor",
        limite=10,
    ):
        limite = cls._limite(limite)

        filtro, parametros_periodo = (
            ConsultasNami._filtro_periodo(
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                coluna="COALESCE(v.data_venda, v.data)",
            )
        )

        ordem_sql = {
            "maior_valor": "total_gasto DESC",
            "mais_compras": "quantidade_compras DESC",
            "mais_recente": "ultima_compra DESC NULLS LAST",
        }.get(
            ordem,
            "total_gasto DESC",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    c.id,
                    c.nome,
                    c.telefone,
                    c.email,
                    COUNT(v.id) AS quantidade_compras,
                    COALESCE(SUM(
                        CASE
                            WHEN COALESCE(v.cancelada, FALSE)
                            THEN 0
                            ELSE v.valor
                        END
                    ), 0) AS total_gasto,
                    MAX(
                        COALESCE(v.data_venda, v.data)
                    ) AS ultima_compra
                FROM clientes c
                LEFT JOIN vendas v
                    ON v.cliente_id = c.id
                   AND v.empresa_id = c.empresa_id
                   AND {filtro}
                WHERE c.empresa_id = %s
                  AND c.ativo = TRUE
                GROUP BY
                    c.id,
                    c.nome,
                    c.telefone,
                    c.email
                ORDER BY {ordem_sql}
                LIMIT %s
                """,
                tuple(
                    parametros_periodo
                    + [
                        empresa_id,
                        limite,
                    ]
                ),
            )

            return {
                "periodo": periodo,
                "ordem": ordem,
                "clientes": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()
