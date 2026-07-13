BEGIN;


-- ==========================================
-- MÓDULOS HABILITADOS POR EMPRESA
-- ==========================================

ALTER TABLE empresa
ADD COLUMN IF NOT EXISTS emprestimos_ativo BOOLEAN;

UPDATE empresa
SET emprestimos_ativo = TRUE
WHERE emprestimos_ativo IS NULL;

ALTER TABLE empresa
ALTER COLUMN emprestimos_ativo SET DEFAULT FALSE;

ALTER TABLE empresa
ALTER COLUMN emprestimos_ativo SET NOT NULL;


-- ==========================================
-- TOKENS DE LOGIN PERSISTENTE
-- ==========================================

CREATE TABLE IF NOT EXISTS login_tokens (

    id BIGSERIAL PRIMARY KEY,

    usuario_id INTEGER NOT NULL,

    token_hash VARCHAR(64) NOT NULL,

    criado_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    ultimo_uso_em TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    expira_em TIMESTAMP NOT NULL,

    revogado_em TIMESTAMP,

    user_agent VARCHAR(500),

    endereco_ip VARCHAR(100),

    CONSTRAINT login_token_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE CASCADE,

    CONSTRAINT login_token_hash_unico
        UNIQUE (token_hash)

);


-- ==========================================
-- ÍNDICES
-- ==========================================

CREATE INDEX IF NOT EXISTS idx_login_tokens_usuario
ON login_tokens(usuario_id);

CREATE INDEX IF NOT EXISTS idx_login_tokens_hash_ativo
ON login_tokens(token_hash)
WHERE revogado_em IS NULL;

CREATE INDEX IF NOT EXISTS idx_login_tokens_expiracao
ON login_tokens(expira_em)
WHERE revogado_em IS NULL;

CREATE INDEX IF NOT EXISTS idx_empresa_emprestimos_ativo
ON empresa(emprestimos_ativo);


COMMIT;