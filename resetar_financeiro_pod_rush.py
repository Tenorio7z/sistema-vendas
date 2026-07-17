from database import conectar


NOME_EMPRESA = "Pod Rush"
USUARIO_GERENTE = "Ricardo"

CONFIRMACAO_EXIGIDA = (
    "APAGAR FINANCEIRO POD RUSH"
)


def tabela_existe(cursor, tabela):

    cursor.execute(
        """
        SELECT to_regclass(%s)
        """,
        (
            f"public.{tabela}",
        ),
    )

    return (
        cursor.fetchone()[0]
        is not None
    )


def contar(cursor, tabela, empresa_id):

    if not tabela_existe(
        cursor,
        tabela,
    ):
        return None

    consultas = {
        "vendas": """
            SELECT COUNT(*)
            FROM vendas
            WHERE empresa_id = %s
        """,

        "caixa": """
            SELECT COUNT(*)
            FROM caixa
            WHERE empresa_id = %s
        """,

        "movimentacoes_caixa": """
            SELECT COUNT(*)
            FROM movimentacoes_caixa
            WHERE empresa_id = %s
        """,

        "folha_pagamentos": """
            SELECT COUNT(*)
            FROM folha_pagamentos
            WHERE empresa_id = %s
        """,

        "despesas_empresa": """
            SELECT COUNT(*)
            FROM despesas_empresa
            WHERE empresa_id = %s
        """,
    }

    cursor.execute(
        consultas[tabela],
        (
            empresa_id,
        ),
    )

    return cursor.fetchone()[0]


def localizar_empresa(cursor):

    cursor.execute(
        """
        SELECT DISTINCT
            e.id,
            e.nome,
            u.usuario

        FROM empresa e

        INNER JOIN usuarios u
            ON u.empresa_id = e.id

        WHERE LOWER(TRIM(e.nome))
              LIKE LOWER(%s)

          AND LOWER(TRIM(u.usuario))
              = LOWER(TRIM(%s))
        """,
        (
            f"%{NOME_EMPRESA}%",
            USUARIO_GERENTE,
        ),
    )

    empresas = cursor.fetchall()

    if not empresas:
        raise RuntimeError(
            (
                "Nenhuma empresa Pod Rush "
                "vinculada ao usuário Ricardo "
                "foi encontrada."
            )
        )

    if len(empresas) > 1:

        print(
            "\nForam encontradas várias contas:"
        )

        for empresa in empresas:
            print(
                (
                    f"- ID {empresa[0]} | "
                    f"{empresa[1]} | "
                    f"Usuário: {empresa[2]}"
                )
            )

        raise RuntimeError(
            (
                "Mais de uma empresa foi encontrada. "
                "Interrompido para evitar apagar "
                "a conta errada."
            )
        )

    return empresas[0]


def executar_reset():

    conn = conectar()
    cursor = conn.cursor()

    try:
        empresa = localizar_empresa(
            cursor
        )

        empresa_id = empresa[0]
        empresa_nome = empresa[1]
        usuario = empresa[2]

        print()
        print("=" * 58)
        print("RESET FINANCEIRO DO NEXUS")
        print("=" * 58)

        print(
            f"Empresa: {empresa_nome}"
        )

        print(
            f"Empresa ID: {empresa_id}"
        )

        print(
            f"Usuário encontrado: {usuario}"
        )

        print()
        print("REGISTROS ENCONTRADOS")
        print("-" * 58)

        tabelas = (
            "vendas",
            "caixa",
            "movimentacoes_caixa",
            "folha_pagamentos",
            "despesas_empresa",
        )

        totais = {}

        for tabela in tabelas:

            total = contar(
                cursor,
                tabela,
                empresa_id,
            )

            totais[tabela] = total

            if total is None:
                print(
                    f"{tabela}: tabela inexistente"
                )

            else:
                print(
                    f"{tabela}: {total}"
                )

        print()
        print(
            "Produtos, estoque, usuários e "
            "funcionários NÃO serão apagados."
        )

        print()
        print(
            "Para confirmar, digite exatamente:"
        )

        print(
            CONFIRMACAO_EXIGIDA
        )

        confirmacao = input(
            "\nConfirmação: "
        ).strip()

        if confirmacao != CONFIRMACAO_EXIGIDA:

            conn.rollback()

            print()
            print(
                "Confirmação incorreta."
            )

            print(
                "Nenhum registro foi apagado."
            )

            return

        # =====================================
        # BLOQUEIA A EMPRESA DURANTE O RESET
        # =====================================

        cursor.execute(
            """
            SELECT id
            FROM empresa
            WHERE id = %s
            FOR UPDATE
            """,
            (
                empresa_id,
            ),
        )

        apagados = {}

        # =====================================
        # DESPESAS E FOLHAS
        # =====================================

        if tabela_existe(
            cursor,
            "despesas_empresa",
        ):
            cursor.execute(
                """
                DELETE FROM despesas_empresa
                WHERE empresa_id = %s
                """,
                (
                    empresa_id,
                ),
            )

            apagados[
                "despesas_empresa"
            ] = cursor.rowcount

        if tabela_existe(
            cursor,
            "folha_pagamentos",
        ):
            cursor.execute(
                """
                DELETE FROM folha_pagamentos
                WHERE empresa_id = %s
                """,
                (
                    empresa_id,
                ),
            )

            apagados[
                "folha_pagamentos"
            ] = cursor.rowcount

        # =====================================
        # MOVIMENTAÇÕES DO CAIXA
        # =====================================

        cursor.execute(
            """
            DELETE FROM movimentacoes_caixa
            WHERE empresa_id = %s
            """,
            (
                empresa_id,
            ),
        )

        apagados[
            "movimentacoes_caixa"
        ] = cursor.rowcount

        # =====================================
        # VENDAS
        # =====================================

        cursor.execute(
            """
            DELETE FROM vendas
            WHERE empresa_id = %s
            """,
            (
                empresa_id,
            ),
        )

        apagados[
            "vendas"
        ] = cursor.rowcount

        # =====================================
        # CAIXAS
        # =====================================

        cursor.execute(
            """
            DELETE FROM caixa
            WHERE empresa_id = %s
            """,
            (
                empresa_id,
            ),
        )

        apagados[
            "caixa"
        ] = cursor.rowcount

        conn.commit()

        print()
        print("=" * 58)
        print("RESET CONCLUÍDO")
        print("=" * 58)

        for tabela, quantidade in (
            apagados.items()
        ):
            print(
                (
                    f"{tabela}: "
                    f"{quantidade} apagados"
                )
            )

        print()
        print(
            "O histórico financeiro da empresa "
            "foi zerado com sucesso."
        )

        print(
            "Produtos, estoque, usuários e "
            "funcionários foram preservados."
        )

    except Exception as erro:

        conn.rollback()

        print()
        print(
            "ERRO: nenhum dado foi apagado."
        )

        print(erro)

        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar_reset()