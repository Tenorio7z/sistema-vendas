CREATE TABLE IF NOT EXISTS configuracao_impressao (
    empresa_id INTEGER PRIMARY KEY REFERENCES empresa(id) ON DELETE CASCADE,
    largura_papel_mm INTEGER NOT NULL DEFAULT 58,
    copias_pre_conta INTEGER NOT NULL DEFAULT 1,
    atualizado_por INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT configuracao_impressao_largura_valida
        CHECK (largura_papel_mm IN (48, 58, 80)),
    CONSTRAINT configuracao_impressao_copias_validas
        CHECK (copias_pre_conta BETWEEN 1 AND 3)
);

