from database import conectar, criar_cursor


def executar():

    conn = conectar()
    cursor = criar_cursor(conn)

    try:

        # =====================================================
        # SETOR RESPONSÁVEL PELO PRODUTO
        # =====================================================

        cursor.execute(
            """
            ALTER TABLE produtos

            ADD COLUMN IF NOT EXISTS
                setor_preparo VARCHAR(30)
                NOT NULL
                DEFAULT 'cozinha'
            """
        )

        # Valores:
        #
        # cozinha = aparece na cozinha
        # bar     = aparece no bar
        # direto  = não exige preparação

        # =====================================================
        # LOTES DE PEDIDOS ENVIADOS
        # =====================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comanda_pedidos (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,
                comanda_id BIGINT NOT NULL,

                enviado_por INTEGER,

                numero_sequencial INTEGER
                    NOT NULL
                    DEFAULT 1,

                origem VARCHAR(20)
                    NOT NULL
                    DEFAULT 'garcom',

                status VARCHAR(30)
                    NOT NULL
                    DEFAULT 'recebido',

                observacoes TEXT,

                enviado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                iniciado_em TIMESTAMP,
                pronto_em TIMESTAMP,
                entregue_em TIMESTAMP,
                cancelado_em TIMESTAMP,

                criado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                atualizado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT comanda_pedidos_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT comanda_pedidos_comanda_fk
                    FOREIGN KEY (comanda_id)
                    REFERENCES comandas(id)
                    ON DELETE CASCADE,

                CONSTRAINT comanda_pedidos_usuario_fk
                    FOREIGN KEY (enviado_por)
                    REFERENCES usuarios(id)
                    ON DELETE SET NULL,

                CONSTRAINT comanda_pedidos_sequencial_uk
                    UNIQUE (
                        comanda_id,
                        numero_sequencial
                    )
            )
            """
        )

        # =====================================================
        # VINCULAR ITENS AO PEDIDO ENVIADO
        # =====================================================

        cursor.execute(
            """
            ALTER TABLE comanda_itens

            ADD COLUMN IF NOT EXISTS
                pedido_id BIGINT
            """
        )

        cursor.execute(
            """
            ALTER TABLE comanda_itens

            ADD COLUMN IF NOT EXISTS
                setor_preparo VARCHAR(30)
                NOT NULL
                DEFAULT 'cozinha'
            """
        )

        cursor.execute(
            """
            ALTER TABLE comanda_itens

            ADD COLUMN IF NOT EXISTS
                enviado_em TIMESTAMP
            """
        )

        cursor.execute(
            """
            ALTER TABLE comanda_itens

            ADD COLUMN IF NOT EXISTS
                preparo_iniciado_em TIMESTAMP
            """
        )

        cursor.execute(
            """
            ALTER TABLE comanda_itens

            ADD COLUMN IF NOT EXISTS
                pronto_em TIMESTAMP
            """
        )

        cursor.execute(
            """
            ALTER TABLE comanda_itens

            ADD COLUMN IF NOT EXISTS
                entregue_em TIMESTAMP
            """
        )

        # =====================================================
        # CRIAR A FK APENAS SE AINDA NÃO EXISTIR
        # =====================================================

        cursor.execute(
            """
            DO $$
            BEGIN

                IF NOT EXISTS (
                    SELECT 1

                    FROM pg_constraint

                    WHERE conname =
                        'comanda_itens_pedido_fk'
                ) THEN

                    ALTER TABLE comanda_itens

                    ADD CONSTRAINT
                        comanda_itens_pedido_fk

                    FOREIGN KEY (pedido_id)

                    REFERENCES comanda_pedidos(id)

                    ON DELETE SET NULL;

                END IF;

            END
            $$;
            """
        )

        # =====================================================
        # PREENCHER SETOR DOS ITENS EXISTENTES
        # =====================================================

        cursor.execute(
            """
            UPDATE comanda_itens ci

            SET setor_preparo = COALESCE(
                p.setor_preparo,
                'cozinha'
            )

            FROM produtos p

            WHERE p.id = ci.produto_id
              AND p.empresa_id = ci.empresa_id
              AND (
                    ci.setor_preparo IS NULL
                    OR ci.setor_preparo = ''
              )
            """
        )

        # =====================================================
        # ÍNDICES PARA PAINEL EM TEMPO REAL
        # =====================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comanda_pedidos_empresa_status_idx

            ON comanda_pedidos (
                empresa_id,
                status,
                enviado_em
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comanda_pedidos_comanda_idx

            ON comanda_pedidos (
                comanda_id,
                numero_sequencial
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comanda_itens_pedido_setor_status_idx

            ON comanda_itens (
                pedido_id,
                setor_preparo,
                status
            )

            WHERE pedido_id IS NOT NULL
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comanda_itens_empresa_setor_idx

            ON comanda_itens (
                empresa_id,
                setor_preparo,
                status,
                enviado_em
            )

            WHERE pedido_id IS NOT NULL
            """
        )

        conn.commit()

        print(
            "Fluxo do garçom e produção criado com sucesso."
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()