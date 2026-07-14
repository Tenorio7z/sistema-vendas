from datetime import date

from database import (
    conectar,
    criar_cursor,
)


class ConsultasNami:

    PERIODOS_VALIDOS = {
        "hoje",
        "ontem",
        "ultimos_7_dias",
        "ultimos_30_dias",
        "semana",
        "mes",
        "mes_passado",
        "ano",
        "ano_passado",
        "periodo",
        "tudo",
    }

    @staticmethod
    def _normalizar_limite(
        limite,
        padrao=10,
        maximo=50,
    ):
        try:
            limite = int(limite)

        except (
            TypeError,
            ValueError,
        ):
            limite = padrao

        return max(
            1,
            min(limite, maximo)
        )

    @staticmethod
    def _validar_data(valor):
        if not valor:
            return None

        try:
            return date.fromisoformat(
                str(valor)
            )

        except ValueError:
            raise ValueError(
                "Data inválida. Utilize AAAA-MM-DD."
            )

    @classmethod
    def _filtro_periodo(
        cls,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        coluna="COALESCE(v.data_venda, v.data)",
    ):
        periodo = str(
            periodo or "mes"
        ).strip().lower()

        if periodo not in cls.PERIODOS_VALIDOS:
            raise ValueError(
                "Período de consulta inválido."
            )

        if periodo == "hoje":
            return (
                f"DATE({coluna}) = CURRENT_DATE",
                [],
            )

        if periodo == "ontem":
            return (
                (
                    f"DATE({coluna}) = "
                    "CURRENT_DATE - INTERVAL '1 day'"
                ),
                [],
            )

        if periodo == "ultimos_7_dias":
            return (
                (
                    f"{coluna} >= "
                    "CURRENT_DATE - INTERVAL '6 days'"
                ),
                [],
            )

        if periodo == "ultimos_30_dias":
            return (
                (
                    f"{coluna} >= "
                    "CURRENT_DATE - INTERVAL '29 days'"
                ),
                [],
            )

        if periodo == "semana":
            return (
                (
                    f"{coluna} >= "
                    "DATE_TRUNC('week', CURRENT_DATE) "
                    f"AND {coluna} < "
                    "DATE_TRUNC('week', CURRENT_DATE) "
                    "+ INTERVAL '7 days'"
                ),
                [],
            )

        if periodo == "mes":
            return (
                (
                    f"{coluna} >= "
                    "DATE_TRUNC('month', CURRENT_DATE) "
                    f"AND {coluna} < "
                    "DATE_TRUNC('month', CURRENT_DATE) "
                    "+ INTERVAL '1 month'"
                ),
                [],
            )

        if periodo == "mes_passado":
            return (
                (
                    f"{coluna} >= "
                    "DATE_TRUNC('month', CURRENT_DATE) "
                    "- INTERVAL '1 month' "
                    f"AND {coluna} < "
                    "DATE_TRUNC('month', CURRENT_DATE)"
                ),
                [],
            )

        if periodo == "ano":
            return (
                (
                    f"{coluna} >= "
                    "DATE_TRUNC('year', CURRENT_DATE) "
                    f"AND {coluna} < "
                    "DATE_TRUNC('year', CURRENT_DATE) "
                    "+ INTERVAL '1 year'"
                ),
                [],
            )

        if periodo == "ano_passado":
            return (
                (
                    f"{coluna} >= "
                    "DATE_TRUNC('year', CURRENT_DATE) "
                    "- INTERVAL '1 year' "
                    f"AND {coluna} < "
                    "DATE_TRUNC('year', CURRENT_DATE)"
                ),
                [],
            )

        if periodo == "periodo":
            inicio = cls._validar_data(
                data_inicio
            )

            fim = cls._validar_data(
                data_fim
            )

            if not inicio or not fim:
                raise ValueError(
                    (
                        "Informe data_inicio e data_fim "
                        "para consultar um período."
                    )
                )

            if inicio > fim:
                raise ValueError(
                    (
                        "A data inicial não pode ser "
                        "maior que a data final."
                    )
                )

            return (
                (
                    f"DATE({coluna}) "
                    "BETWEEN %s AND %s"
                ),
                [
                    inicio,
                    fim,
                ],
            )

        return (
            "TRUE",
            [],
        )

    @staticmethod
    def _filtro_usuario(
        nivel,
        usuario_id,
        coluna="v.usuario_id",
    ):
        if (
            str(nivel).lower()
            == "funcionario"
        ):
            if not usuario_id:
                raise ValueError(
                    "Funcionário não identificado."
                )

            return (
                f"{coluna} = %s",
                [
                    usuario_id,
                ],
            )

        return (
            "TRUE",
            [],
        )

    @classmethod
    def resumo_vendas(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        nivel="gerente",
        usuario_id=None,
    ):
        filtro_periodo, parametros_periodo = (
            cls._filtro_periodo(
                periodo,
                data_inicio,
                data_fim,
            )
        )

        filtro_usuario, parametros_usuario = (
            cls._filtro_usuario(
                nivel,
                usuario_id,
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    COUNT(*) AS registros_venda,

                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS faturamento,

                    COALESCE(
                        AVG(v.valor),
                        0
                    ) AS ticket_medio_registro,

                    COALESCE(
                        MAX(v.valor),
                        0
                    ) AS maior_valor,

                    COALESCE(
                        MIN(v.valor),
                        0
                    ) AS menor_valor

                FROM vendas v

                WHERE v.empresa_id = %s
                  AND COALESCE(v.cancelada, 0) = 0
                  AND {filtro_periodo}
                  AND {filtro_usuario}
                """,
                [
                    empresa_id,
                    *parametros_periodo,
                    *parametros_usuario,
                ]
            )

            dados = cursor.fetchone()

            return {
                "periodo": periodo,
                "resumo": dados,
            }

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def produtos_vendidos(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        limite=20,
        ordem="mais_vendidos",
        nivel="gerente",
        usuario_id=None,
    ):
        limite = cls._normalizar_limite(
            limite,
            padrao=20,
            maximo=50,
        )

        filtro_periodo, parametros_periodo = (
            cls._filtro_periodo(
                periodo,
                data_inicio,
                data_fim,
            )
        )

        filtro_usuario, parametros_usuario = (
            cls._filtro_usuario(
                nivel,
                usuario_id,
            )
        )

        direcao = (
            "ASC"
            if ordem == "menos_vendidos"
            else "DESC"
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
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
                    ) AS faturamento,

                    COUNT(*) AS registros_venda

                FROM vendas v

                INNER JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND COALESCE(v.cancelada, 0) = 0
                  AND {filtro_periodo}
                  AND {filtro_usuario}

                GROUP BY
                    p.id,
                    p.nome

                ORDER BY
                    quantidade {direcao},
                    faturamento {direcao},
                    p.nome ASC

                LIMIT %s
                """,
                [
                    empresa_id,
                    *parametros_periodo,
                    *parametros_usuario,
                    limite,
                ]
            )

            return {
                "periodo": periodo,
                "ordem": ordem,
                "produtos": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def ultimas_vendas(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        limite=10,
        nivel="gerente",
        usuario_id=None,
    ):
        limite = cls._normalizar_limite(
            limite,
            padrao=10,
            maximo=30,
        )

        filtro_periodo, parametros_periodo = (
            cls._filtro_periodo(
                periodo,
                data_inicio,
                data_fim,
            )
        )

        filtro_usuario, parametros_usuario = (
            cls._filtro_usuario(
                nivel,
                usuario_id,
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    v.id,
                    p.nome AS produto,
                    v.quantidade,
                    v.valor,
                    v.pagamento,
                    COALESCE(
                        v.data_venda,
                        v.data
                    ) AS data_venda,

                    COALESCE(
                        u.usuario,
                        'Não informado'
                    ) AS vendedor

                FROM vendas v

                LEFT JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                LEFT JOIN usuarios u
                    ON u.id = v.usuario_id
                   AND u.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND COALESCE(v.cancelada, 0) = 0
                  AND {filtro_periodo}
                  AND {filtro_usuario}

                ORDER BY
                    COALESCE(
                        v.data_venda,
                        v.data
                    ) DESC,
                    v.id DESC

                LIMIT %s
                """,
                [
                    empresa_id,
                    *parametros_periodo,
                    *parametros_usuario,
                    limite,
                ]
            )

            return {
                "periodo": periodo,
                "vendas": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def formas_pagamento(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        nivel="gerente",
        usuario_id=None,
    ):
        filtro_periodo, parametros_periodo = (
            cls._filtro_periodo(
                periodo,
                data_inicio,
                data_fim,
            )
        )

        filtro_usuario, parametros_usuario = (
            cls._filtro_usuario(
                nivel,
                usuario_id,
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    COALESCE(
                        NULLIF(
                            TRIM(v.pagamento),
                            ''
                        ),
                        'Não informado'
                    ) AS forma_pagamento,

                    COUNT(*) AS registros_venda,

                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS faturamento

                FROM vendas v

                WHERE v.empresa_id = %s
                  AND COALESCE(v.cancelada, 0) = 0
                  AND {filtro_periodo}
                  AND {filtro_usuario}

                GROUP BY forma_pagamento

                ORDER BY faturamento DESC
                """,
                [
                    empresa_id,
                    *parametros_periodo,
                    *parametros_usuario,
                ]
            )

            return {
                "periodo": periodo,
                "formas_pagamento": (
                    cursor.fetchall()
                ),
            }

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def ranking_funcionarios(
        cls,
        empresa_id,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        limite=10,
    ):
        limite = cls._normalizar_limite(
            limite,
            padrao=10,
            maximo=30,
        )

        filtro_periodo, parametros_periodo = (
            cls._filtro_periodo(
                periodo,
                data_inicio,
                data_fim,
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    u.id,
                    u.usuario,
                    u.nivel,

                    COALESCE(
                        u.comissao,
                        0
                    ) AS percentual_comissao,

                    COUNT(v.id) AS registros_venda,

                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS faturamento,

                    ROUND(
                        (
                            COALESCE(
                                SUM(v.valor),
                                0
                            )
                            *
                            COALESCE(
                                u.comissao,
                                0
                            )
                            / 100
                        )::numeric,
                        2
                    ) AS valor_comissao

                FROM usuarios u

                LEFT JOIN vendas v
                    ON v.usuario_id = u.id
                   AND v.empresa_id = u.empresa_id
                   AND COALESCE(
                       v.cancelada,
                       0
                   ) = 0
                   AND {filtro_periodo}

                WHERE u.empresa_id = %s
                  AND u.nivel = 'funcionario'

                GROUP BY
                    u.id,
                    u.usuario,
                    u.nivel,
                    u.comissao

                ORDER BY
                    faturamento DESC,
                    itens_vendidos DESC,
                    u.usuario ASC

                LIMIT %s
                """,
                [
                    *parametros_periodo,
                    empresa_id,
                    limite,
                ]
            )

            return {
                "periodo": periodo,
                "funcionarios": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def consultar_estoque(
        empresa_id,
        situacao="resumo",
        limite_estoque_baixo=5,
        limite=30,
    ):
        limite = ConsultasNami._normalizar_limite(
            limite,
            padrao=30,
            maximo=100,
        )

        try:
            limite_estoque_baixo = int(
                limite_estoque_baixo
            )

        except (
            TypeError,
            ValueError,
        ):
            limite_estoque_baixo = 5

        limite_estoque_baixo = max(
            0,
            min(limite_estoque_baixo, 1000)
        )

        situacoes = {
            "todos": "TRUE",
            "baixo": (
                "p.estoque > 0 "
                "AND p.estoque <= %s"
            ),
            "sem_estoque": (
                "COALESCE(p.estoque, 0) = 0"
            ),
            "disponivel": (
                "COALESCE(p.estoque, 0) > 0"
            ),
        }

        if situacao == "resumo":
            conn = conectar()
            cursor = criar_cursor(conn)

            try:
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) AS produtos_cadastrados,

                        COUNT(*) FILTER (
                            WHERE COALESCE(estoque, 0) = 0
                        ) AS produtos_sem_estoque,

                        COUNT(*) FILTER (
                            WHERE estoque > 0
                              AND estoque <= %s
                        ) AS produtos_estoque_baixo,

                        COALESCE(
                            SUM(estoque),
                            0
                        ) AS unidades_em_estoque,

                        COALESCE(
                            SUM(
                                preco
                                * COALESCE(estoque, 0)
                            ),
                            0
                        ) AS valor_potencial_estoque

                    FROM produtos

                    WHERE empresa_id = %s
                    """,
                    (
                        limite_estoque_baixo,
                        empresa_id,
                    )
                )

                return {
                    "situacao": "resumo",
                    "limite_estoque_baixo": (
                        limite_estoque_baixo
                    ),
                    "resumo": cursor.fetchone(),
                }

            finally:
                cursor.close()
                conn.close()

        filtro = situacoes.get(situacao)

        if not filtro:
            raise ValueError(
                "Situação de estoque inválida."
            )

        parametros = [
            empresa_id,
        ]

        if situacao == "baixo":
            parametros.append(
                limite_estoque_baixo
            )

        parametros.append(limite)

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    p.id,
                    p.nome,
                    p.preco,
                    p.estoque,
                    p.codigo_barras,

                    COALESCE(
                        p.preco
                        * p.estoque,
                        0
                    ) AS valor_potencial

                FROM produtos p

                WHERE p.empresa_id = %s
                  AND {filtro}

                ORDER BY
                    p.estoque ASC,
                    p.nome ASC

                LIMIT %s
                """,
                parametros
            )

            return {
                "situacao": situacao,
                "limite_estoque_baixo": (
                    limite_estoque_baixo
                ),
                "produtos": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def buscar_produto(
        empresa_id,
        termo,
        limite=10,
    ):
        termo = str(
            termo or ""
        ).strip()

        if not termo:
            raise ValueError(
                "Informe o nome ou código do produto."
            )

        limite = ConsultasNami._normalizar_limite(
            limite,
            padrao=10,
            maximo=20,
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.nome,
                    p.preco,
                    p.estoque,
                    p.codigo_barras,

                    COALESCE(
                        (
                            SELECT SUM(v.quantidade)
                            FROM vendas v
                            WHERE v.empresa_id = p.empresa_id
                              AND v.produto_id = p.id
                              AND COALESCE(
                                  v.cancelada,
                                  0
                              ) = 0
                        ),
                        0
                    ) AS total_vendido

                FROM produtos p

                WHERE p.empresa_id = %s
                  AND (
                      LOWER(p.nome)
                          LIKE LOWER(%s)

                      OR p.codigo_barras = %s
                  )

                ORDER BY
                    CASE
                        WHEN LOWER(p.nome)
                             = LOWER(%s)
                        THEN 0
                        ELSE 1
                    END,
                    p.nome ASC

                LIMIT %s
                """,
                (
                    empresa_id,
                    f"%{termo}%",
                    termo,
                    termo,
                    limite,
                )
            )

            return {
                "termo": termo,
                "produtos": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def resumo_caixa(
        empresa_id,
    ):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.status,
                    c.valor_inicial,
                    c.valor_final,
                    c.data_abertura,
                    c.data_fechamento

                FROM caixa c

                WHERE c.empresa_id = %s

                ORDER BY
                    CASE
                        WHEN c.status = 'aberto'
                        THEN 0
                        ELSE 1
                    END,
                    c.id DESC

                LIMIT 1
                """,
                (
                    empresa_id,
                )
            )

            caixa = cursor.fetchone()

            if not caixa:
                return {
                    "caixa_encontrado": False,
                    "caixa": None,
                }

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS registros_venda,

                    COALESCE(
                        SUM(quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(valor),
                        0
                    ) AS faturamento

                FROM vendas

                WHERE empresa_id = %s
                  AND caixa_id = %s
                  AND COALESCE(cancelada, 0) = 0
                """,
                (
                    empresa_id,
                    caixa["id"],
                )
            )

            vendas = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE LOWER(tipo)
                                IN (
                                    'entrada',
                                    'suprimento'
                                )
                        ),
                        0
                    ) AS entradas,

                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE LOWER(tipo)
                                IN (
                                    'saida',
                                    'saída',
                                    'sangria'
                                )
                        ),
                        0
                    ) AS saidas

                FROM movimentacoes_caixa

                WHERE empresa_id = %s
                  AND caixa_id = %s
                """,
                (
                    empresa_id,
                    caixa["id"],
                )
            )

            movimentacoes = cursor.fetchone()

            saldo_estimado = (
                caixa["valor_inicial"]
                + movimentacoes["entradas"]
                + vendas["faturamento"]
                - movimentacoes["saidas"]
            )

            return {
                "caixa_encontrado": True,
                "caixa": caixa,
                "vendas": vendas,
                "movimentacoes": movimentacoes,
                "saldo_estimado": saldo_estimado,
            }

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def movimentacoes_caixa(
        empresa_id,
        limite=20,
    ):
        limite = ConsultasNami._normalizar_limite(
            limite,
            padrao=20,
            maximo=50,
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    m.id,
                    m.tipo,
                    m.descricao,
                    m.valor,
                    m.data,
                    m.caixa_id

                FROM movimentacoes_caixa m

                WHERE m.empresa_id = %s

                ORDER BY
                    m.data DESC,
                    m.id DESC

                LIMIT %s
                """,
                (
                    empresa_id,
                    limite,
                )
            )

            return {
                "movimentacoes": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()