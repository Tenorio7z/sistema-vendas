from database import conectar, criar_cursor

from services.ia.capabilities.consultas import (
    ConsultasNami,
)


class ConsultasCustosNami:

    @staticmethod
    def _limite(valor, padrao=20, maximo=50):
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            valor = padrao

        return max(1, min(valor, maximo))

    @classmethod
    def resumo(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
    ):
        filtro, parametros_periodo = (
            ConsultasNami._filtro_periodo(
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                coluna="p.data_vencimento",
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    COALESCE(SUM(p.valor), 0) AS total_previsto,
                    COALESCE(SUM(p.valor_pago), 0) AS total_pago,
                    COALESCE(SUM(
                        GREATEST(p.valor - p.valor_pago, 0)
                    ), 0) AS total_pendente,
                    COALESCE(SUM(
                        CASE
                            WHEN p.status IN ('pendente', 'parcial')
                             AND p.data_vencimento < CURRENT_DATE
                            THEN GREATEST(
                                p.valor - p.valor_pago,
                                0
                            )
                            ELSE 0
                        END
                    ), 0) AS total_vencido,
                    COUNT(*) AS quantidade_parcelas,
                    COUNT(*) FILTER (
                        WHERE p.status = 'paga'
                    ) AS parcelas_pagas,
                    COUNT(*) FILTER (
                        WHERE p.status IN ('pendente', 'parcial')
                    ) AS parcelas_pendentes,
                    COUNT(*) FILTER (
                        WHERE p.status IN ('pendente', 'parcial')
                          AND p.data_vencimento < CURRENT_DATE
                    ) AS parcelas_vencidas
                FROM custos_parcelas p
                INNER JOIN custos_empresariais c
                    ON c.id = p.custo_id
                   AND c.empresa_id = p.empresa_id
                WHERE p.empresa_id = %s
                  AND c.ativo = TRUE
                  AND {filtro}
                """,
                tuple(
                    [empresa_id]
                    + parametros_periodo
                ),
            )

            resumo = cursor.fetchone() or {}

            cursor.execute(
                f"""
                SELECT
                    c.categoria,
                    COALESCE(SUM(p.valor), 0) AS total
                FROM custos_parcelas p
                INNER JOIN custos_empresariais c
                    ON c.id = p.custo_id
                   AND c.empresa_id = p.empresa_id
                WHERE p.empresa_id = %s
                  AND c.ativo = TRUE
                  AND {filtro}
                GROUP BY c.categoria
                ORDER BY total DESC
                LIMIT 10
                """,
                tuple(
                    [empresa_id]
                    + parametros_periodo
                ),
            )

            categorias = cursor.fetchall()

            return {
                "periodo": periodo,
                "resumo": resumo,
                "categorias": categorias,
            }

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def listar(
        cls,
        empresa_id,
        situacao="todas",
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        limite=20,
    ):
        limite = cls._limite(limite)

        filtro, parametros_periodo = (
            ConsultasNami._filtro_periodo(
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                coluna="p.data_vencimento",
            )
        )

        situacao = str(
            situacao or "todas"
        ).strip().lower()

        filtros = [
            "p.empresa_id = %s",
            "c.ativo = TRUE",
            filtro,
        ]

        parametros = (
            [empresa_id]
            + parametros_periodo
        )

        if situacao == "pagas":
            filtros.append("p.status = 'paga'")
        elif situacao == "pendentes":
            filtros.append(
                "p.status IN ('pendente', 'parcial')"
            )
        elif situacao == "vencidas":
            filtros.append(
                "p.status IN ('pendente', 'parcial') "
                "AND p.data_vencimento < CURRENT_DATE"
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    c.id AS custo_id,
                    c.descricao,
                    c.categoria,
                    c.fornecedor,
                    c.tipo,
                    p.numero_parcela,
                    p.data_vencimento,
                    p.valor,
                    p.valor_pago,
                    GREATEST(
                        p.valor - p.valor_pago,
                        0
                    ) AS saldo,
                    CASE
                        WHEN p.status IN ('pendente', 'parcial')
                         AND p.data_vencimento < CURRENT_DATE
                        THEN 'vencida'
                        ELSE p.status
                    END AS situacao
                FROM custos_parcelas p
                INNER JOIN custos_empresariais c
                    ON c.id = p.custo_id
                   AND c.empresa_id = p.empresa_id
                WHERE {' AND '.join(filtros)}
                ORDER BY
                    p.data_vencimento ASC,
                    c.descricao ASC
                LIMIT %s
                """,
                tuple(
                    parametros
                    + [limite]
                ),
            )

            return {
                "situacao": situacao,
                "periodo": periodo,
                "despesas": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()
