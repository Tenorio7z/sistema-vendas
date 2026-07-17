ALTER TABLE vendas
ADD COLUMN IF NOT EXISTS cancelada_em TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_vendas_empresa_data_cancelada
ON vendas (
    empresa_id,
    data_venda,
    cancelada
);

CREATE INDEX IF NOT EXISTS idx_vendas_cancelada_em
ON vendas (
    empresa_id,
    cancelada_em
)
WHERE cancelada = 1;

CREATE INDEX IF NOT EXISTS idx_movimentacoes_empresa_data
ON movimentacoes_caixa (
    empresa_id,
    data
);

CREATE INDEX IF NOT EXISTS idx_folha_empresa_pagamento
ON folha_pagamentos (
    empresa_id,
    data_pagamento
)
WHERE status = 'pago';