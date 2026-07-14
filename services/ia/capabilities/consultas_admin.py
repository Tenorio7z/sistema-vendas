from services.ia.capabilities.consultas import (
    ConsultasNami,
)

from database import (
    conectar,
    criar_cursor,
)


class ConsultasAdminNami:

    @staticmethod
    def _exigir_master(
        nivel,
    ):
        if str(
            nivel or ""
        ).lower() != "master":
            raise PermissionError(
                (
                    "Somente o administrador master "
                    "pode consultar dados globais."
                )
            )

    @staticmethod
    def _normalizar_limite(
        limite,
        padrao=20,
        maximo=100,
    ):
        try:
            limite = int(
                limite
            )

        except (
            TypeError,
            ValueError,
        ):
            limite = padrao

        return max(
            1,
            min(limite, maximo)
        )

    # ==========================================
    # RESUMO DA PLATAFORMA
    # ==========================================

    @classmethod
    def resumo_plataforma(
        cls,
        nivel,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
    ):
        cls._exigir_master(
            nivel
        )

        filtro_periodo, parametros_periodo = (
            ConsultasNami._filtro_periodo(
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                coluna=(
                    "COALESCE("
                    "v.data_venda, "
                    "v.data"
                    ")"
                ),
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_empresas,

                    COUNT(*) FILTER (
                        WHERE LOWER(
                            COALESCE(
                                plano,
                                'comum'
                            )
                        ) = 'comum'
                    ) AS empresas_comum,

                    COUNT(*) FILTER (
                        WHERE LOWER(
                            COALESCE(
                                plano,
                                'comum'
                            )
                        ) = 'premium'
                    ) AS empresas_premium,

                    COUNT(*) FILTER (
                        WHERE COALESCE(
                            emprestimos_ativo,
                            FALSE
                        ) = TRUE
                    ) AS empresas_com_emprestimos

                FROM empresa
                """
            )

            empresas = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_usuarios,

                    COUNT(*) FILTER (
                        WHERE nivel = 'gerente'
                    ) AS gerentes,

                    COUNT(*) FILTER (
                        WHERE nivel = 'funcionario'
                    ) AS funcionarios,

                    COUNT(*) FILTER (
                        WHERE status = 'bloqueado'
                    ) AS usuarios_bloqueados

                FROM usuarios
                """
            )

            usuarios = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS produtos_cadastrados,

                    COALESCE(
                        SUM(estoque),
                        0
                    ) AS unidades_em_estoque,

                    COUNT(*) FILTER (
                        WHERE COALESCE(
                            estoque,
                            0
                        ) = 0
                    ) AS produtos_esgotados,

                    COUNT(*) FILTER (
                        WHERE estoque > 0
                          AND estoque <= 5
                    ) AS produtos_estoque_baixo

                FROM produtos
                """
            )

            produtos = cursor.fetchone()

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
                    ) AS faturamento_total,

                    COUNT(
                        DISTINCT v.empresa_id
                    ) AS empresas_com_vendas

                FROM vendas v

                WHERE COALESCE(
                          v.cancelada,
                          0
                      ) = 0
                  AND {filtro_periodo}
                """,
                parametros_periodo
            )

            vendas = cursor.fetchone()

            return {
                "periodo": periodo,
                "empresas": empresas,
                "usuarios": usuarios,
                "produtos": produtos,
                "vendas": vendas,
            }

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # LISTAR EMPRESAS
    # ==========================================

    @classmethod
    def listar_empresas(
        cls,
        nivel,
        busca=None,
        plano="todos",
        status="todos",
        emprestimos="todos",
        limite=50,
    ):
        cls._exigir_master(
            nivel
        )

        limite = cls._normalizar_limite(
            limite,
            padrao=50,
            maximo=100,
        )

        condicoes = [
            "TRUE",
        ]

        parametros = []

        busca = str(
            busca or ""
        ).strip()

        if busca:
            condicoes.append(
                (
                    "("
                    "LOWER(e.nome) LIKE LOWER(%s) "
                    "OR EXISTS ("
                    "SELECT 1 "
                    "FROM usuarios ub "
                    "WHERE ub.empresa_id = e.id "
                    "AND LOWER(ub.usuario) "
                    "LIKE LOWER(%s)"
                    ")"
                    ")"
                )
            )

            termo = f"%{busca}%"

            parametros.extend([
                termo,
                termo,
            ])

        if plano in (
            "comum",
            "premium",
        ):
            condicoes.append(
                "LOWER(e.plano) = %s"
            )

            parametros.append(
                plano
            )

        if emprestimos == "ativo":
            condicoes.append(
                (
                    "COALESCE("
                    "e.emprestimos_ativo, "
                    "FALSE"
                    ") = TRUE"
                )
            )

        elif emprestimos == "inativo":
            condicoes.append(
                (
                    "COALESCE("
                    "e.emprestimos_ativo, "
                    "FALSE"
                    ") = FALSE"
                )
            )

        if status == "ativo":
            condicoes.append(
                """
                EXISTS (
                    SELECT 1
                    FROM usuarios us
                    WHERE us.empresa_id = e.id
                      AND us.nivel = 'gerente'
                      AND us.status = 'ativo'
                )
                """
            )

        elif status == "bloqueado":
            condicoes.append(
                """
                EXISTS (
                    SELECT 1
                    FROM usuarios us
                    WHERE us.empresa_id = e.id
                      AND us.nivel = 'gerente'
                      AND us.status = 'bloqueado'
                )
                """
            )

        onde = " AND ".join(
            condicoes
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    e.id,
                    e.nome,
                    e.plano,

                    COALESCE(
                        e.emprestimos_ativo,
                        FALSE
                    ) AS emprestimos_ativo,

                    (
                        SELECT ug.usuario
                        FROM usuarios ug
                        WHERE ug.empresa_id = e.id
                          AND ug.nivel = 'gerente'
                        ORDER BY ug.id ASC
                        LIMIT 1
                    ) AS usuario_gerente,

                    (
                        SELECT ug.status
                        FROM usuarios ug
                        WHERE ug.empresa_id = e.id
                          AND ug.nivel = 'gerente'
                        ORDER BY ug.id ASC
                        LIMIT 1
                    ) AS status_acesso,

                    (
                        SELECT COUNT(*)
                        FROM usuarios u
                        WHERE u.empresa_id = e.id
                    ) AS total_usuarios,

                    (
                        SELECT COUNT(*)
                        FROM produtos p
                        WHERE p.empresa_id = e.id
                    ) AS total_produtos,

                    (
                        SELECT COUNT(*)
                        FROM vendas v
                        WHERE v.empresa_id = e.id
                          AND COALESCE(
                              v.cancelada,
                              0
                          ) = 0
                    ) AS registros_venda,

                    (
                        SELECT COALESCE(
                            SUM(v.valor),
                            0
                        )
                        FROM vendas v
                        WHERE v.empresa_id = e.id
                          AND COALESCE(
                              v.cancelada,
                              0
                          ) = 0
                    ) AS faturamento_total

                FROM empresa e

                WHERE {onde}

                ORDER BY
                    e.nome ASC

                LIMIT %s
                """,
                [
                    *parametros,
                    limite,
                ]
            )

            return {
                "filtros": {
                    "busca": busca or None,
                    "plano": plano,
                    "status": status,
                    "emprestimos": emprestimos,
                },
                "empresas": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # CONSULTAR EMPRESA PELO NOME
    # ==========================================

    @classmethod
    def consultar_empresa(
        cls,
        nivel,
        nome_empresa,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
    ):
        cls._exigir_master(
            nivel
        )

        nome_empresa = str(
            nome_empresa or ""
        ).strip()

        if not nome_empresa:
            raise ValueError(
                "Informe o nome da empresa."
            )

        filtro_periodo, parametros_periodo = (
            ConsultasNami._filtro_periodo(
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                coluna=(
                    "COALESCE("
                    "v.data_venda, "
                    "v.data"
                    ")"
                ),
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    e.id,
                    e.nome,
                    e.plano,

                    COALESCE(
                        e.emprestimos_ativo,
                        FALSE
                    ) AS emprestimos_ativo,

                    (
                        SELECT ug.usuario
                        FROM usuarios ug
                        WHERE ug.empresa_id = e.id
                          AND ug.nivel = 'gerente'
                        ORDER BY ug.id ASC
                        LIMIT 1
                    ) AS usuario_gerente,

                    (
                        SELECT ug.status
                        FROM usuarios ug
                        WHERE ug.empresa_id = e.id
                          AND ug.nivel = 'gerente'
                        ORDER BY ug.id ASC
                        LIMIT 1
                    ) AS status_acesso

                FROM empresa e

                WHERE LOWER(e.nome)
                    LIKE LOWER(%s)

                ORDER BY
                    CASE
                        WHEN LOWER(e.nome)
                            = LOWER(%s)
                        THEN 0
                        ELSE 1
                    END,
                    e.nome ASC

                LIMIT 1
                """,
                (
                    f"%{nome_empresa}%",
                    nome_empresa,
                )
            )

            empresa = cursor.fetchone()

            if not empresa:
                return {
                    "encontrada": False,
                    "nome_pesquisado": nome_empresa,
                }

            empresa_id = empresa["id"]

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_usuarios,

                    COUNT(*) FILTER (
                        WHERE nivel = 'gerente'
                    ) AS gerentes,

                    COUNT(*) FILTER (
                        WHERE nivel = 'funcionario'
                    ) AS funcionarios,

                    COUNT(*) FILTER (
                        WHERE status = 'bloqueado'
                    ) AS usuarios_bloqueados

                FROM usuarios

                WHERE empresa_id = %s
                """,
                (
                    empresa_id,
                )
            )

            usuarios = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS produtos_cadastrados,

                    COALESCE(
                        SUM(estoque),
                        0
                    ) AS unidades_em_estoque,

                    COUNT(*) FILTER (
                        WHERE COALESCE(
                            estoque,
                            0
                        ) = 0
                    ) AS produtos_esgotados,

                    COUNT(*) FILTER (
                        WHERE estoque > 0
                          AND estoque <= 5
                    ) AS estoque_baixo,

                    COALESCE(
                        SUM(
                            preco
                            * COALESCE(
                                estoque,
                                0
                            )
                        ),
                        0
                    ) AS valor_potencial_estoque

                FROM produtos

                WHERE empresa_id = %s
                """,
                (
                    empresa_id,
                )
            )

            produtos = cursor.fetchone()

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
                    ) AS ticket_medio_registro

                FROM vendas v

                WHERE v.empresa_id = %s
                  AND COALESCE(
                      v.cancelada,
                      0
                  ) = 0
                  AND {filtro_periodo}
                """,
                [
                    empresa_id,
                    *parametros_periodo,
                ]
            )

            vendas = cursor.fetchone()

            cursor.execute(
                f"""
                SELECT
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
                  AND COALESCE(
                      v.cancelada,
                      0
                  ) = 0
                  AND {filtro_periodo}

                GROUP BY
                    p.id,
                    p.nome

                ORDER BY
                    quantidade DESC,
                    faturamento DESC

                LIMIT 5
                """,
                [
                    empresa_id,
                    *parametros_periodo,
                ]
            )

            produtos_mais_vendidos = (
                cursor.fetchall()
            )

            cursor.execute(
                """
                SELECT
                    id,
                    status,
                    valor_inicial,
                    valor_final,
                    data_abertura,
                    data_fechamento

                FROM caixa

                WHERE empresa_id = %s

                ORDER BY
                    CASE
                        WHEN status = 'aberto'
                        THEN 0
                        ELSE 1
                    END,
                    id DESC

                LIMIT 1
                """,
                (
                    empresa_id,
                )
            )

            caixa = cursor.fetchone()

            return {
                "encontrada": True,
                "periodo": periodo,
                "empresa": empresa,
                "usuarios": usuarios,
                "produtos": produtos,
                "vendas": vendas,
                "produtos_mais_vendidos": (
                    produtos_mais_vendidos
                ),
                "caixa": caixa,
            }

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # RANKING DAS EMPRESAS
    # ==========================================

    @classmethod
    def ranking_empresas(
        cls,
        nivel,
        periodo="mes",
        data_inicio=None,
        data_fim=None,
        ordem="maior_faturamento",
        limite=10,
    ):
        cls._exigir_master(
            nivel
        )

        limite = cls._normalizar_limite(
            limite,
            padrao=10,
            maximo=50,
        )

        filtro_periodo, parametros_periodo = (
            ConsultasNami._filtro_periodo(
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                coluna=(
                    "COALESCE("
                    "v.data_venda, "
                    "v.data"
                    ")"
                ),
            )
        )

        ordens = {
            "maior_faturamento": (
                "faturamento DESC, "
                "itens_vendidos DESC"
            ),

            "menor_faturamento": (
                "faturamento ASC, "
                "itens_vendidos ASC"
            ),

            "mais_itens": (
                "itens_vendidos DESC, "
                "faturamento DESC"
            ),

            "mais_usuarios": (
                "total_usuarios DESC, "
                "e.nome ASC"
            ),

            "mais_produtos": (
                "total_produtos DESC, "
                "e.nome ASC"
            ),
        }

        ordenar_por = ordens.get(
            ordem,
            ordens["maior_faturamento"]
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    e.id,
                    e.nome,
                    e.plano,

                    COALESCE(
                        e.emprestimos_ativo,
                        FALSE
                    ) AS emprestimos_ativo,

                    COUNT(
                        DISTINCT v.id
                    ) AS registros_venda,

                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS faturamento,

                    (
                        SELECT COUNT(*)
                        FROM usuarios u
                        WHERE u.empresa_id = e.id
                    ) AS total_usuarios,

                    (
                        SELECT COUNT(*)
                        FROM produtos p
                        WHERE p.empresa_id = e.id
                    ) AS total_produtos

                FROM empresa e

                LEFT JOIN vendas v
                    ON v.empresa_id = e.id
                   AND COALESCE(
                       v.cancelada,
                       0
                   ) = 0
                   AND {filtro_periodo}

                GROUP BY
                    e.id,
                    e.nome,
                    e.plano,
                    e.emprestimos_ativo

                ORDER BY
                    {ordenar_por}

                LIMIT %s
                """,
                [
                    *parametros_periodo,
                    limite,
                ]
            )

            return {
                "periodo": periodo,
                "ordem": ordem,
                "empresas": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # EMPRESAS SEM VENDAS
    # ==========================================

    @classmethod
    def empresas_sem_vendas(
        cls,
        nivel,
        dias=30,
        limite=50,
    ):
        cls._exigir_master(
            nivel
        )

        try:
            dias = int(
                dias
            )

        except (
            TypeError,
            ValueError,
        ):
            dias = 30

        dias = max(
            1,
            min(dias, 3650)
        )

        limite = cls._normalizar_limite(
            limite,
            padrao=50,
            maximo=100,
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    e.id,
                    e.nome,
                    e.plano,

                    COALESCE(
                        e.emprestimos_ativo,
                        FALSE
                    ) AS emprestimos_ativo,

                    MAX(
                        COALESCE(
                            v.data_venda,
                            v.data
                        )
                    ) AS ultima_venda,

                    CURRENT_DATE
                    - DATE(
                        MAX(
                            COALESCE(
                                v.data_venda,
                                v.data
                            )
                        )
                    ) AS dias_sem_vender

                FROM empresa e

                LEFT JOIN vendas v
                    ON v.empresa_id = e.id
                   AND COALESCE(
                       v.cancelada,
                       0
                   ) = 0

                GROUP BY
                    e.id,
                    e.nome,
                    e.plano,
                    e.emprestimos_ativo

                HAVING
                    MAX(
                        COALESCE(
                            v.data_venda,
                            v.data
                        )
                    ) IS NULL

                    OR MAX(
                        COALESCE(
                            v.data_venda,
                            v.data
                        )
                    ) < (
                        CURRENT_DATE
                        - (%s * INTERVAL '1 day')
                    )

                ORDER BY
                    ultima_venda ASC NULLS FIRST,
                    e.nome ASC

                LIMIT %s
                """,
                (
                    dias,
                    limite,
                )
            )

            return {
                "dias": dias,
                "empresas": cursor.fetchall(),
            }

        finally:
            cursor.close()
            conn.close()