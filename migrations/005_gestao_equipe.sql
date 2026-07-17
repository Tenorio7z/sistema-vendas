BEGIN;


-- ==========================================
-- CONFIGURAÇÕES PROFISSIONAIS DO FUNCIONÁRIO
-- ==========================================

CREATE TABLE IF NOT EXISTS funcionarios_config (

    id BIGSERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    usuario_id INTEGER NOT NULL,

    cargo VARCHAR(100)
        NOT NULL
        DEFAULT 'Funcionário',

    salario_base NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    dia_pagamento INTEGER
        NOT NULL
        DEFAULT 5,

    data_admissao DATE,

    observacoes TEXT,

    criado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    atualizado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT funcionario_config_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT funcionario_config_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE,

    CONSTRAINT funcionario_config_unico
        UNIQUE (
            empresa_id,
            usuario_id
        ),

    CONSTRAINT funcionario_salario_valido
        CHECK (
            salario_base >= 0
        ),

    CONSTRAINT funcionario_dia_pagamento_valido
        CHECK (
            dia_pagamento
            BETWEEN 1 AND 31
        )
);


-- ==========================================
-- FOLHA DE PAGAMENTO
-- ==========================================

CREATE TABLE IF NOT EXISTS folha_pagamentos (

    id BIGSERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    usuario_id INTEGER NOT NULL,

    registrado_por INTEGER,

    competencia DATE NOT NULL,

    salario_base NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    valor_comissao NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    valor_bonus NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    valor_descontos NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    valor_total NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    forma_pagamento VARCHAR(30),

    status VARCHAR(20)
        NOT NULL
        DEFAULT 'pendente',

    data_vencimento DATE,

    data_pagamento TIMESTAMP,

    observacoes TEXT,

    caixa_id INTEGER,

    criado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    atualizado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT folha_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT folha_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE,

    CONSTRAINT folha_registrado_por_fk
        FOREIGN KEY (registrado_por)
        REFERENCES usuarios(id)
        ON DELETE SET NULL,

    CONSTRAINT folha_caixa_fk
        FOREIGN KEY (caixa_id)
        REFERENCES caixa(id)
        ON DELETE SET NULL,

    CONSTRAINT folha_status_valido
        CHECK (
            status IN (
                'pendente',
                'pago',
                'cancelado'
            )
        ),

    CONSTRAINT folha_forma_pagamento_valida
        CHECK (
            forma_pagamento IS NULL
            OR forma_pagamento IN (
                'pix',
                'dinheiro',
                'transferencia',
                'cartao',
                'outro'
            )
        ),

    CONSTRAINT folha_valores_validos
        CHECK (
            salario_base >= 0
            AND valor_comissao >= 0
            AND valor_bonus >= 0
            AND valor_descontos >= 0
            AND valor_total >= 0
        ),

    CONSTRAINT folha_competencia_unica
        UNIQUE (
            empresa_id,
            usuario_id,
            competencia
        )
);


-- ==========================================
-- DESPESAS DA EMPRESA
-- ==========================================

CREATE TABLE IF NOT EXISTS despesas_empresa (

    id BIGSERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    registrado_por INTEGER,

    categoria VARCHAR(50)
        NOT NULL
        DEFAULT 'outros',

    descricao VARCHAR(200) NOT NULL,

    valor NUMERIC(14, 2)
        NOT NULL,

    competencia DATE,

    data_vencimento DATE,

    data_pagamento TIMESTAMP,

    forma_pagamento VARCHAR(30),

    status VARCHAR(20)
        NOT NULL
        DEFAULT 'pendente',

    recorrente BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    observacoes TEXT,

    folha_pagamento_id BIGINT,

    caixa_id INTEGER,

    criado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    atualizado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT despesa_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT despesa_registrado_por_fk
        FOREIGN KEY (registrado_por)
        REFERENCES usuarios(id)
        ON DELETE SET NULL,

    CONSTRAINT despesa_folha_fk
        FOREIGN KEY (folha_pagamento_id)
        REFERENCES folha_pagamentos(id)
        ON DELETE SET NULL,

    CONSTRAINT despesa_caixa_fk
        FOREIGN KEY (caixa_id)
        REFERENCES caixa(id)
        ON DELETE SET NULL,

    CONSTRAINT despesa_valor_valido
        CHECK (
            valor > 0
        ),

    CONSTRAINT despesa_status_valido
        CHECK (
            status IN (
                'pendente',
                'paga',
                'cancelada'
            )
        ),

    CONSTRAINT despesa_categoria_valida
        CHECK (
            categoria IN (
                'salario',
                'comissao',
                'folha',
                'aluguel',
                'energia',
                'agua',
                'internet',
                'fornecedor',
                'imposto',
                'manutencao',
                'marketing',
                'transporte',
                'outros'
            )
        ),

    CONSTRAINT despesa_forma_pagamento_valida
        CHECK (
            forma_pagamento IS NULL
            OR forma_pagamento IN (
                'pix',
                'dinheiro',
                'transferencia',
                'cartao',
                'boleto',
                'outro'
            )
        )
);


-- ==========================================
-- ÍNDICES
-- ==========================================

CREATE INDEX IF NOT EXISTS
idx_funcionarios_config_empresa
ON funcionarios_config (
    empresa_id
);


CREATE INDEX IF NOT EXISTS
idx_funcionarios_config_usuario
ON funcionarios_config (
    usuario_id
);


CREATE INDEX IF NOT EXISTS
idx_folha_empresa_competencia
ON folha_pagamentos (
    empresa_id,
    competencia DESC
);


CREATE INDEX IF NOT EXISTS
idx_folha_usuario_competencia
ON folha_pagamentos (
    usuario_id,
    competencia DESC
);


CREATE INDEX IF NOT EXISTS
idx_folha_empresa_status
ON folha_pagamentos (
    empresa_id,
    status
);


CREATE INDEX IF NOT EXISTS
idx_despesas_empresa_competencia
ON despesas_empresa (
    empresa_id,
    competencia DESC
);


CREATE INDEX IF NOT EXISTS
idx_despesas_empresa_status
ON despesas_empresa (
    empresa_id,
    status
);


CREATE INDEX IF NOT EXISTS
idx_despesas_folha
ON despesas_empresa (
    folha_pagamento_id
)
WHERE folha_pagamento_id IS NOT NULL;


COMMIT;