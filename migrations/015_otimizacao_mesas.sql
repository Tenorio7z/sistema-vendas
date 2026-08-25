-- Índices específicos do painel de mesas e comandas.
-- São idempotentes e podem ser executados novamente com segurança.

CREATE INDEX IF NOT EXISTS idx_mesas_empresa_status_numero
    ON mesas (empresa_id, status, numero);

CREATE INDEX IF NOT EXISTS idx_comandas_empresa_status_mesa
    ON comandas (empresa_id, status, mesa_id);

CREATE INDEX IF NOT EXISTS idx_comandas_abertas_empresa_mesa
    ON comandas (empresa_id, mesa_id, id)
    WHERE status IN ('aberta', 'aguardando_pagamento');

CREATE INDEX IF NOT EXISTS idx_comanda_itens_empresa_comanda_status
    ON comanda_itens (empresa_id, comanda_id, status);

CREATE INDEX IF NOT EXISTS idx_comanda_itens_pendentes_pedido
    ON comanda_itens (empresa_id, comanda_id, pedido_id)
    WHERE status != 'cancelado';

CREATE INDEX IF NOT EXISTS idx_produtos_empresa_disponiveis_nome
    ON produtos (empresa_id, nome, id)
    WHERE estoque > 0;

