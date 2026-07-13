-- Índices para as telas e operações mais acessadas do Nexus PDV.
-- Todos são idempotentes e podem ser executados novamente com segurança.

CREATE INDEX IF NOT EXISTS idx_produtos_empresa_id
    ON produtos (empresa_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_produtos_empresa_nome
    ON produtos (empresa_id, nome);

CREATE INDEX IF NOT EXISTS idx_produtos_empresa_estoque
    ON produtos (empresa_id, estoque);

CREATE INDEX IF NOT EXISTS idx_vendas_empresa_data
    ON vendas (empresa_id, data_venda DESC)
    WHERE cancelada = 0;

CREATE INDEX IF NOT EXISTS idx_vendas_caixa_ativas
    ON vendas (caixa_id)
    WHERE cancelada = 0;

CREATE INDEX IF NOT EXISTS idx_vendas_empresa_produto
    ON vendas (empresa_id, produto_id)
    WHERE cancelada = 0;

CREATE INDEX IF NOT EXISTS idx_caixa_empresa_status_id
    ON caixa (empresa_id, status, id DESC);

CREATE INDEX IF NOT EXISTS idx_notificacoes_empresa_id
    ON notificacoes (empresa_id, id DESC);

CREATE INDEX IF NOT EXISTS idx_usuarios_empresa_id
    ON usuarios (empresa_id, id);

CREATE INDEX IF NOT EXISTS idx_emprestimo_clientes_empresa_status
    ON emprestimo_clientes (empresa_id, status, id DESC);

CREATE INDEX IF NOT EXISTS idx_emprestimos_empresa_status
    ON emprestimos (empresa_id, status, id DESC);

CREATE INDEX IF NOT EXISTS idx_emprestimo_parcelas_empresa_status_vencimento
    ON emprestimo_parcelas (empresa_id, status, data_vencimento);
