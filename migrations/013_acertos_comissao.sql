BEGIN;

ALTER TABLE folha_pagamentos
    ADD COLUMN IF NOT EXISTS periodo_inicio TIMESTAMP,
    ADD COLUMN IF NOT EXISTS periodo_fim TIMESTAMP,
    ADD COLUMN IF NOT EXISTS faturamento_base NUMERIC(14, 2)
        NOT NULL DEFAULT 0;

-- Folhas antigas pagas passam a encerrar o saldo na data do pagamento.
-- O histórico permanece intacto e vendas posteriores ficam disponíveis.
UPDATE folha_pagamentos
SET periodo_fim = COALESCE(
        periodo_fim,
        data_pagamento,
        atualizado_em,
        criado_em
    )
WHERE status = 'pago'
  AND periodo_fim IS NULL;

UPDATE folha_pagamentos
SET periodo_fim = COALESCE(
        periodo_fim,
        criado_em
    )
WHERE status = 'pendente'
  AND periodo_fim IS NULL;

ALTER TABLE folha_pagamentos
    DROP CONSTRAINT IF EXISTS folha_competencia_unica;

-- Bases antigas podem possuir uma pendência em mais de uma competência.
-- Mantemos a mais recente aberta e preservamos as demais como canceladas.
WITH pendencias_repetidas AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY empresa_id, usuario_id
            ORDER BY criado_em DESC NULLS LAST, id DESC
        ) AS ordem
    FROM folha_pagamentos
    WHERE status = 'pendente'
)
UPDATE folha_pagamentos fp
SET
    status = 'cancelado',
    observacoes = CONCAT_WS(
        E'\n',
        NULLIF(fp.observacoes, ''),
        'Acerto antigo encerrado automaticamente na migração.'
    ),
    atualizado_em = CURRENT_TIMESTAMP
FROM pendencias_repetidas pr
WHERE fp.id = pr.id
  AND pr.ordem > 1;

-- Pode haver vários acertos no mês, mas somente um pendente por funcionário.
CREATE UNIQUE INDEX IF NOT EXISTS folha_um_acerto_pendente_idx
    ON folha_pagamentos (empresa_id, usuario_id)
    WHERE status = 'pendente';

CREATE INDEX IF NOT EXISTS folha_usuario_pagamento_idx
    ON folha_pagamentos (
        empresa_id,
        usuario_id,
        status,
        data_pagamento DESC,
        id DESC
    );

CREATE INDEX IF NOT EXISTS vendas_usuario_acerto_idx
    ON vendas (
        empresa_id,
        usuario_id,
        cancelada,
        data_venda,
        id
    );

COMMIT;
