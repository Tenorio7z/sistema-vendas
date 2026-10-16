BEGIN;

CREATE TABLE IF NOT EXISTS financeiro_configuracao (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    valor_mensalidade NUMERIC(12, 2) NOT NULL DEFAULT 150.00
        CHECK (valor_mensalidade >= 0),
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO financeiro_configuracao (id, valor_mensalidade)
VALUES (1, 150.00)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS financeiro_pagamentos (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT REFERENCES empresa(id) ON DELETE SET NULL,
    empresa_nome VARCHAR(150) NOT NULL,
    competencia DATE NOT NULL CHECK (EXTRACT(DAY FROM competencia) = 1),
    valor_mensalidade NUMERIC(12, 2) NOT NULL CHECK (valor_mensalidade >= 0),
    valor_pago NUMERIC(12, 2) NOT NULL CHECK (valor_pago >= 0),
    extra NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (extra >= 0),
    data_pagamento DATE NOT NULL DEFAULT CURRENT_DATE,
    forma_pagamento VARCHAR(40),
    observacao VARCHAR(500),
    registrado_por BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT financeiro_pagamento_empresa_competencia_unico
        UNIQUE (empresa_id, competencia)
);

CREATE INDEX IF NOT EXISTS financeiro_pagamentos_competencia_idx
    ON financeiro_pagamentos (competencia DESC);

CREATE TABLE IF NOT EXISTS financeiro_despesas (
    id BIGSERIAL PRIMARY KEY,
    descricao VARCHAR(180) NOT NULL,
    categoria VARCHAR(40) NOT NULL DEFAULT 'Outros',
    valor NUMERIC(12, 2) NOT NULL CHECK (valor > 0),
    data_despesa DATE NOT NULL DEFAULT CURRENT_DATE,
    competencia DATE NOT NULL CHECK (EXTRACT(DAY FROM competencia) = 1),
    observacao VARCHAR(500),
    registrado_por BIGINT REFERENCES usuarios(id) ON DELETE SET NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS financeiro_despesas_competencia_idx
    ON financeiro_despesas (competencia DESC);

COMMIT;
