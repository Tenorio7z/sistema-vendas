BEGIN;

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL,
    nome VARCHAR(150) NOT NULL
);

/* Atualiza uma tabela clientes que já exista */
ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS telefone VARCHAR(30);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS email VARCHAR(180);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS cpf_cnpj VARCHAR(20);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS data_nascimento DATE;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS endereco VARCHAR(255);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS numero VARCHAR(30);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS complemento VARCHAR(120);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS bairro VARCHAR(120);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS cidade VARCHAR(120);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS estado VARCHAR(2);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS cep VARCHAR(12);

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS observacoes TEXT;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE clientes
    ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP;

/* Relacionamento entre clientes e empresas */
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'clientes_empresa_fk'
    ) THEN
        ALTER TABLE clientes
            ADD CONSTRAINT clientes_empresa_fk
            FOREIGN KEY (empresa_id)
            REFERENCES empresa(id)
            ON DELETE CASCADE;
    END IF;
END
$$;

/* Índices dos clientes */
CREATE INDEX IF NOT EXISTS idx_clientes_empresa
    ON clientes (empresa_id);

CREATE INDEX IF NOT EXISTS idx_clientes_empresa_nome
    ON clientes (empresa_id, nome);

CREATE INDEX IF NOT EXISTS idx_clientes_empresa_telefone
    ON clientes (empresa_id, telefone);

CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_cpf_cnpj_unico
    ON clientes (empresa_id, cpf_cnpj)
    WHERE cpf_cnpj IS NOT NULL
      AND TRIM(cpf_cnpj) <> '';

/* Vínculo opcional da venda com o cliente */
ALTER TABLE vendas
    ADD COLUMN IF NOT EXISTS cliente_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'vendas_cliente_fk'
    ) THEN
        ALTER TABLE vendas
            ADD CONSTRAINT vendas_cliente_fk
            FOREIGN KEY (cliente_id)
            REFERENCES clientes(id)
            ON DELETE SET NULL;
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_vendas_empresa_cliente
    ON vendas (empresa_id, cliente_id);

COMMIT;