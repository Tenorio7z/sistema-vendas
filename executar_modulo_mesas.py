from database import conectar, criar_cursor


def executar():

    conn = conectar()
    cursor = criar_cursor(conn)

    try:

        # =====================================================
        # MESAS
        # =====================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mesas (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,

                numero VARCHAR(20) NOT NULL,
                nome VARCHAR(100),

                capacidade INTEGER NOT NULL DEFAULT 4,

                status VARCHAR(20)
                    NOT NULL
                    DEFAULT 'livre',

                observacoes TEXT,

                criado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                atualizado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT mesas_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT mesas_empresa_numero_uk
                    UNIQUE (empresa_id, numero),

                CONSTRAINT mesas_capacidade_ck
                    CHECK (capacidade > 0),

                CONSTRAINT mesas_status_ck
                    CHECK (
                        status IN (
                            'livre',
                            'ocupada',
                            'reservada',
                            'inativa'
                        )
                    )
            )
            """
        )

        # =====================================================
        # COMANDAS
        # =====================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comandas (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,
                mesa_id BIGINT,
                cliente_id INTEGER,
                funcionario_id INTEGER,

                identificacao VARCHAR(120),

                quantidade_pessoas INTEGER
                    NOT NULL
                    DEFAULT 1,

                status VARCHAR(20)
                    NOT NULL
                    DEFAULT 'aberta',

                subtotal NUMERIC(14, 2)
                    NOT NULL
                    DEFAULT 0,

                desconto_valor NUMERIC(14, 2)
                    NOT NULL
                    DEFAULT 0,

                desconto_percentual NUMERIC(8, 4)
                    NOT NULL
                    DEFAULT 0,

                total NUMERIC(14, 2)
                    NOT NULL
                    DEFAULT 0,

                observacoes TEXT,

                aberta_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                fechada_em TIMESTAMP,

                criado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                atualizado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT comandas_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT comandas_mesa_fk
                    FOREIGN KEY (mesa_id)
                    REFERENCES mesas(id)
                    ON DELETE SET NULL,

                CONSTRAINT comandas_funcionario_fk
                    FOREIGN KEY (funcionario_id)
                    REFERENCES usuarios(id)
                    ON DELETE SET NULL,

                CONSTRAINT comandas_pessoas_ck
                    CHECK (quantidade_pessoas > 0),

                CONSTRAINT comandas_valores_ck
                    CHECK (
                        subtotal >= 0
                        AND desconto_valor >= 0
                        AND desconto_percentual >= 0
                        AND total >= 0
                    ),

                CONSTRAINT comandas_status_ck
                    CHECK (
                        status IN (
                            'aberta',
                            'aguardando_pagamento',
                            'fechada',
                            'cancelada'
                        )
                    )
            )
            """
        )

        # =====================================================
        # ITENS DA COMANDA
        # =====================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comanda_itens (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,
                comanda_id BIGINT NOT NULL,
                produto_id INTEGER,

                produto_nome VARCHAR(200) NOT NULL,

                quantidade NUMERIC(12, 3)
                    NOT NULL
                    DEFAULT 1,

                valor_unitario NUMERIC(14, 2)
                    NOT NULL
                    DEFAULT 0,

                subtotal NUMERIC(14, 2)
                    NOT NULL
                    DEFAULT 0,

                status VARCHAR(20)
                    NOT NULL
                    DEFAULT 'pendente',

                observacoes TEXT,

                criado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                atualizado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT comanda_itens_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT comanda_itens_comanda_fk
                    FOREIGN KEY (comanda_id)
                    REFERENCES comandas(id)
                    ON DELETE CASCADE,

                CONSTRAINT comanda_itens_produto_fk
                    FOREIGN KEY (produto_id)
                    REFERENCES produtos(id)
                    ON DELETE SET NULL,

                CONSTRAINT comanda_itens_quantidade_ck
                    CHECK (quantidade > 0),

                CONSTRAINT comanda_itens_valores_ck
                    CHECK (
                        valor_unitario >= 0
                        AND subtotal >= 0
                    ),

                CONSTRAINT comanda_itens_status_ck
                    CHECK (
                        status IN (
                            'pendente',
                            'preparando',
                            'pronto',
                            'entregue',
                            'cancelado'
                        )
                    )
            )
            """
        )

        # =====================================================
        # HISTÓRICO DA COMANDA
        # =====================================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS comanda_historico (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,
                comanda_id BIGINT NOT NULL,
                usuario_id INTEGER,

                acao VARCHAR(60) NOT NULL,
                descricao TEXT,

                criado_em TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT comanda_historico_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT comanda_historico_comanda_fk
                    FOREIGN KEY (comanda_id)
                    REFERENCES comandas(id)
                    ON DELETE CASCADE,

                CONSTRAINT comanda_historico_usuario_fk
                    FOREIGN KEY (usuario_id)
                    REFERENCES usuarios(id)
                    ON DELETE SET NULL
            )
            """
        )

        # =====================================================
        # ÍNDICES
        # =====================================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                mesas_empresa_status_idx
            ON mesas (
                empresa_id,
                status
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comandas_empresa_status_idx
            ON comandas (
                empresa_id,
                status,
                aberta_em DESC
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comandas_mesa_status_idx
            ON comandas (
                mesa_id,
                status
            )
            """
        )

        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                comandas_mesa_aberta_uk
            ON comandas (
                mesa_id
            )
            WHERE
                mesa_id IS NOT NULL
                AND status IN (
                    'aberta',
                    'aguardando_pagamento'
                )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comanda_itens_comanda_status_idx
            ON comanda_itens (
                comanda_id,
                status
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                comanda_historico_comanda_idx
            ON comanda_historico (
                comanda_id,
                criado_em DESC
            )
            """
        )

        conn.commit()

        print(
            "Módulo de mesas criado com sucesso."
        )

    except Exception:

        conn.rollback()
        raise

    finally:

        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()