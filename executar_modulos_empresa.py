from database import conectar, criar_cursor


MODULOS_PADRAO = (
    "vendas",
    "produtos",
    "clientes",
    "caixa",
    "estatisticas",
    "custos",
    "nami",
)


def executar():
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS empresa_modulos (
                id BIGSERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL,
                modulo VARCHAR(40) NOT NULL,
                ativo BOOLEAN NOT NULL DEFAULT FALSE,
                configuracoes JSONB NOT NULL DEFAULT '{}'::jsonb,
                criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT empresa_modulos_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT empresa_modulos_empresa_modulo_uk
                    UNIQUE (empresa_id, modulo)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                empresa_modulos_empresa_ativo_idx
            ON empresa_modulos (empresa_id, ativo)
            """
        )

        cursor.execute(
            """
            INSERT INTO empresa_modulos (
                empresa_id,
                modulo,
                ativo
            )
            SELECT
                e.id,
                modulo,
                TRUE
            FROM empresa e
            CROSS JOIN unnest(%s::text[]) AS modulo
            ON CONFLICT (empresa_id, modulo)
            DO NOTHING
            """,
            (list(MODULOS_PADRAO),),
        )

        cursor.execute(
            """
            INSERT INTO empresa_modulos (
                empresa_id,
                modulo,
                ativo
            )
            SELECT
                id,
                'emprestimos',
                COALESCE(emprestimos_ativo, FALSE)
            FROM empresa
            ON CONFLICT (empresa_id, modulo)
            DO UPDATE SET
                ativo = EXCLUDED.ativo,
                atualizado_em = CURRENT_TIMESTAMP
            """
        )

        cursor.execute(
            """
            INSERT INTO empresa_modulos (
                empresa_id,
                modulo,
                ativo
            )
            SELECT
                id,
                'mesas',
                FALSE
            FROM empresa
            ON CONFLICT (empresa_id, modulo)
            DO NOTHING
            """
        )

        conn.commit()
        print("Módulos empresariais criados e empresas atuais migradas.")

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()

