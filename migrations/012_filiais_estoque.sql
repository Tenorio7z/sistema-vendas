BEGIN;

CREATE TABLE IF NOT EXISTS filiais (
    id BIGSERIAL PRIMARY KEY,
    empresa_id BIGINT NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    nome VARCHAR(150) NOT NULL,
    codigo VARCHAR(40),
    matriz BOOLEAN NOT NULL DEFAULT FALSE,
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS filiais_empresa_nome_uidx
    ON filiais (empresa_id, LOWER(nome));

CREATE UNIQUE INDEX IF NOT EXISTS filiais_uma_matriz_por_empresa_uidx
    ON filiais (empresa_id)
    WHERE matriz = TRUE;

INSERT INTO filiais (empresa_id, nome, codigo, matriz, ativa)
SELECT e.id, 'Matriz', 'MATRIZ', TRUE, TRUE
FROM empresa e
WHERE NOT EXISTS (
    SELECT 1 FROM filiais f
    WHERE f.empresa_id = e.id AND f.matriz = TRUE
);

ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS filial_id BIGINT;
ALTER TABLE vendas ADD COLUMN IF NOT EXISTS filial_id BIGINT;
ALTER TABLE caixa ADD COLUMN IF NOT EXISTS filial_id BIGINT;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_filial_fk') THEN
        ALTER TABLE usuarios ADD CONSTRAINT usuarios_filial_fk
            FOREIGN KEY (filial_id) REFERENCES filiais(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'vendas_filial_fk') THEN
        ALTER TABLE vendas ADD CONSTRAINT vendas_filial_fk
            FOREIGN KEY (filial_id) REFERENCES filiais(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'caixa_filial_fk') THEN
        ALTER TABLE caixa ADD CONSTRAINT caixa_filial_fk
            FOREIGN KEY (filial_id) REFERENCES filiais(id) ON DELETE SET NULL;
    END IF;
END $$;

UPDATE usuarios u
SET filial_id = f.id
FROM filiais f
WHERE u.filial_id IS NULL
  AND f.empresa_id = u.empresa_id
  AND f.matriz = TRUE;

UPDATE vendas v
SET filial_id = COALESCE(
    (SELECT u.filial_id FROM usuarios u WHERE u.id = v.usuario_id),
    f.id
)
FROM filiais f
WHERE v.filial_id IS NULL
  AND f.empresa_id = v.empresa_id
  AND f.matriz = TRUE;

UPDATE caixa c
SET filial_id = f.id
FROM filiais f
WHERE c.filial_id IS NULL
  AND f.empresa_id = c.empresa_id
  AND f.matriz = TRUE;

CREATE TABLE IF NOT EXISTS produto_filial (
    produto_id BIGINT NOT NULL REFERENCES produtos(id) ON DELETE CASCADE,
    filial_id BIGINT NOT NULL REFERENCES filiais(id) ON DELETE CASCADE,
    estoque INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
    estoque_minimo INTEGER NOT NULL DEFAULT 0 CHECK (estoque_minimo >= 0),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (produto_id, filial_id)
);

INSERT INTO produto_filial (produto_id, filial_id, estoque, estoque_minimo, ativo)
SELECT p.id, f.id, GREATEST(COALESCE(p.estoque, 0), 0), 0, TRUE
FROM produtos p
JOIN filiais f ON f.empresa_id = p.empresa_id AND f.matriz = TRUE
ON CONFLICT (produto_id, filial_id) DO NOTHING;

CREATE INDEX IF NOT EXISTS produto_filial_filial_idx
    ON produto_filial (filial_id, ativo, produto_id);
CREATE INDEX IF NOT EXISTS usuarios_filial_idx ON usuarios (filial_id);
CREATE INDEX IF NOT EXISTS vendas_filial_data_idx ON vendas (filial_id, data_venda DESC);
CREATE INDEX IF NOT EXISTS caixa_filial_status_idx ON caixa (filial_id, status);

COMMIT;
