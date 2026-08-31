BEGIN;

CREATE TABLE IF NOT EXISTS venda_pagamentos (
    id BIGSERIAL PRIMARY KEY,
    venda_id BIGINT NOT NULL REFERENCES vendas(id) ON DELETE CASCADE,
    forma VARCHAR(20) NOT NULL CHECK (forma IN ('Dinheiro', 'PIX', 'Cartão')),
    valor NUMERIC(14, 2) NOT NULL CHECK (valor > 0),
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS venda_pagamentos_venda_idx
    ON venda_pagamentos (venda_id);
CREATE INDEX IF NOT EXISTS venda_pagamentos_forma_idx
    ON venda_pagamentos (forma);

COMMIT;
