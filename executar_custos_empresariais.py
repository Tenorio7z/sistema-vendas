from database import conectar, criar_cursor


def executar():
    conn = None
    cursor = None

    try:
        conn = conectar()
        cursor = criar_cursor(conn)

        conn.autocommit = False

        # ==========================================
        # CADASTRO PRINCIPAL DOS CUSTOS
        # ==========================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custos_empresariais (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,

                descricao VARCHAR(160) NOT NULL,
                categoria VARCHAR(80) NOT NULL
                    DEFAULT 'Outras despesas',

                fornecedor VARCHAR(160),
                observacoes TEXT,

                tipo VARCHAR(20) NOT NULL
                    DEFAULT 'variavel',

                recorrente BOOLEAN NOT NULL
                    DEFAULT FALSE,

                periodicidade VARCHAR(20),

                quantidade_parcelas INTEGER NOT NULL
                    DEFAULT 1,

                dia_vencimento INTEGER,

                valor_total NUMERIC(14, 2) NOT NULL,

                data_inicio DATE NOT NULL
                    DEFAULT CURRENT_DATE,

                data_fim DATE,

                forma_pagamento_padrao VARCHAR(40),

                ativo BOOLEAN NOT NULL
                    DEFAULT TRUE,

                criado_em TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                atualizado_em TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT custos_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT custos_valor_positivo_ck
                    CHECK (valor_total >= 0),

                CONSTRAINT custos_quantidade_parcelas_ck
                    CHECK (quantidade_parcelas >= 1),

                CONSTRAINT custos_tipo_ck
                    CHECK (
                        tipo IN (
                            'fixa',
                            'variavel',
                            'eventual'
                        )
                    ),

                CONSTRAINT custos_periodicidade_ck
                    CHECK (
                        periodicidade IS NULL
                        OR periodicidade IN (
                            'semanal',
                            'quinzenal',
                            'mensal',
                            'bimestral',
                            'trimestral',
                            'semestral',
                            'anual'
                        )
                    ),

                CONSTRAINT custos_dia_vencimento_ck
                    CHECK (
                        dia_vencimento IS NULL
                        OR dia_vencimento BETWEEN 1 AND 31
                    )
            )
            """
        )

        # ==========================================
        # PARCELAS E VENCIMENTOS
        # ==========================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custos_parcelas (
                id BIGSERIAL PRIMARY KEY,

                custo_id BIGINT NOT NULL,
                empresa_id INTEGER NOT NULL,

                numero_parcela INTEGER NOT NULL
                    DEFAULT 1,

                competencia DATE NOT NULL,
                data_vencimento DATE NOT NULL,

                valor NUMERIC(14, 2) NOT NULL,

                valor_pago NUMERIC(14, 2) NOT NULL
                    DEFAULT 0,

                status VARCHAR(20) NOT NULL
                    DEFAULT 'pendente',

                paga_em TIMESTAMP,
                cancelada_em TIMESTAMP,

                observacoes TEXT,

                criado_em TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                atualizado_em TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT custos_parcela_custo_fk
                    FOREIGN KEY (custo_id)
                    REFERENCES custos_empresariais(id)
                    ON DELETE CASCADE,

                CONSTRAINT custos_parcela_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT custos_parcela_unica_uk
                    UNIQUE (
                        custo_id,
                        numero_parcela
                    ),

                CONSTRAINT custos_parcela_valor_ck
                    CHECK (valor >= 0),

                CONSTRAINT custos_parcela_valor_pago_ck
                    CHECK (valor_pago >= 0),

                CONSTRAINT custos_parcela_status_ck
                    CHECK (
                        status IN (
                            'pendente',
                            'parcial',
                            'paga',
                            'cancelada'
                        )
                    )
            )
            """
        )

        # ==========================================
        # PAGAMENTOS DAS DESPESAS
        # ==========================================

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS custos_pagamentos (
                id BIGSERIAL PRIMARY KEY,

                empresa_id INTEGER NOT NULL,
                custo_id BIGINT NOT NULL,
                parcela_id BIGINT NOT NULL,

                usuario_id INTEGER,
                caixa_id INTEGER,

                valor NUMERIC(14, 2) NOT NULL,

                forma_pagamento VARCHAR(40) NOT NULL,

                data_pagamento TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                observacoes TEXT,

                estornado BOOLEAN NOT NULL
                    DEFAULT FALSE,

                estornado_em TIMESTAMP,
                motivo_estorno TEXT,

                criado_em TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT custos_pagamento_empresa_fk
                    FOREIGN KEY (empresa_id)
                    REFERENCES empresa(id)
                    ON DELETE CASCADE,

                CONSTRAINT custos_pagamento_custo_fk
                    FOREIGN KEY (custo_id)
                    REFERENCES custos_empresariais(id)
                    ON DELETE CASCADE,

                CONSTRAINT custos_pagamento_parcela_fk
                    FOREIGN KEY (parcela_id)
                    REFERENCES custos_parcelas(id)
                    ON DELETE CASCADE,

                CONSTRAINT custos_pagamento_caixa_fk
                    FOREIGN KEY (caixa_id)
                    REFERENCES caixa(id)
                    ON DELETE SET NULL,

                CONSTRAINT custos_pagamento_valor_ck
                    CHECK (valor > 0)
            )
            """
        )

        # ==========================================
        # ÍNDICES DE DESEMPENHO
        # ==========================================

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_empresa_ativo_idx
            ON custos_empresariais (
                empresa_id,
                ativo
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_empresa_categoria_idx
            ON custos_empresariais (
                empresa_id,
                categoria
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_parcelas_vencimento_idx
            ON custos_parcelas (
                empresa_id,
                data_vencimento
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_parcelas_status_idx
            ON custos_parcelas (
                empresa_id,
                status
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_parcelas_competencia_idx
            ON custos_parcelas (
                empresa_id,
                competencia
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_pagamentos_data_idx
            ON custos_pagamentos (
                empresa_id,
                data_pagamento
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS
                custos_pagamentos_parcela_idx
            ON custos_pagamentos (
                parcela_id,
                estornado
            )
            """
        )

        conn.commit()

        print("==========================================")
        print("MÓDULO DE CUSTOS EMPRESARIAIS CRIADO")
        print("==========================================")
        print("Tabela: custos_empresariais")
        print("Tabela: custos_parcelas")
        print("Tabela: custos_pagamentos")
        print("Índices de desempenho criados.")
        print("Tudo pronto, caralho.")

    except Exception as erro:
        if conn:
            conn.rollback()

        print("==========================================")
        print("ERRO AO CRIAR O MÓDULO DE CUSTOS")
        print("==========================================")
        print(erro)

        raise

    finally:
        if cursor:
            cursor.close()

        if conn:
            conn.close()


if __name__ == "__main__":
    executar()