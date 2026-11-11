BEGIN;

CREATE TABLE IF NOT EXISTS fidelidade_campanhas (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    nome VARCHAR(120) NOT NULL,
    slug VARCHAR(80) NOT NULL UNIQUE,
    prazo_dias INTEGER NOT NULL CHECK (prazo_dias BETWEEN 1 AND 3650),
    checkins_meta INTEGER NOT NULL CHECK (checkins_meta BETWEEN 1 AND 10000),
    premio VARCHAR(500) NOT NULL,
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_fidelidade_uma_ativa_empresa
    ON fidelidade_campanhas (empresa_id)
    WHERE ativa = TRUE;

CREATE TABLE IF NOT EXISTS fidelidade_checkins (
    id BIGSERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    campanha_id INTEGER NOT NULL REFERENCES fidelidade_campanhas(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    venda_grupo VARCHAR(64) NOT NULL,
    valido BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    invalidado_em TIMESTAMP,
    CONSTRAINT uq_fidelidade_checkin_venda UNIQUE (campanha_id, venda_grupo)
);

CREATE INDEX IF NOT EXISTS idx_fidelidade_checkins_cliente
    ON fidelidade_checkins (empresa_id, campanha_id, cliente_id, valido);

CREATE TABLE IF NOT EXISTS fidelidade_recompensas (
    id BIGSERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    campanha_id INTEGER NOT NULL REFERENCES fidelidade_campanhas(id) ON DELETE CASCADE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    ciclo INTEGER NOT NULL CHECK (ciclo > 0),
    checkin_id BIGINT NOT NULL REFERENCES fidelidade_checkins(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'disponivel',
    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resgatada_em TIMESTAMP,
    CONSTRAINT uq_fidelidade_recompensa_ciclo UNIQUE (campanha_id, cliente_id, ciclo),
    CONSTRAINT ck_fidelidade_recompensa_status
        CHECK (status IN ('disponivel', 'resgatada', 'revogada', 'revisar_cancelamento'))
);

CREATE INDEX IF NOT EXISTS idx_fidelidade_recompensas_empresa_status
    ON fidelidade_recompensas (empresa_id, status, criada_em DESC);

COMMIT;
