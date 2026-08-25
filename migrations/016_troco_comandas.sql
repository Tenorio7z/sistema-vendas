ALTER TABLE comandas
    ADD COLUMN IF NOT EXISTS pagamento VARCHAR(30),
    ADD COLUMN IF NOT EXISTS valor_recebido NUMERIC(14, 2),
    ADD COLUMN IF NOT EXISTS troco NUMERIC(14, 2);

ALTER TABLE comandas
    DROP CONSTRAINT IF EXISTS comandas_valor_recebido_valido;

ALTER TABLE comandas
    ADD CONSTRAINT comandas_valor_recebido_valido
        CHECK (valor_recebido IS NULL OR valor_recebido >= 0);

ALTER TABLE comandas
    DROP CONSTRAINT IF EXISTS comandas_troco_valido;

ALTER TABLE comandas
    ADD CONSTRAINT comandas_troco_valido
        CHECK (troco IS NULL OR troco >= 0);

