ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS valor_bruto
    NUMERIC(14, 2);

ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS desconto_valor
    NUMERIC(14, 2)
    NOT NULL
    DEFAULT 0;

ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS desconto_percentual
    NUMERIC(8, 4)
    NOT NULL
    DEFAULT 0;

ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS venda_grupo
    VARCHAR(36);

UPDATE vendas
SET valor_bruto = valor
WHERE valor_bruto IS NULL;

ALTER TABLE vendas
ALTER COLUMN valor_bruto
SET NOT NULL;

CREATE INDEX IF NOT EXISTS
    idx_vendas_empresa_grupo
ON vendas (
    empresa_id,
    venda_grupo
);

CREATE INDEX IF NOT EXISTS
    idx_vendas_empresa_data_liquido
ON vendas (
    empresa_id,
    data_venda,
    cancelada
);