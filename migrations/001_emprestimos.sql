BEGIN;


-- ==========================================
-- CLIENTES DE EMPRÉSTIMOS
-- ==========================================

CREATE TABLE IF NOT EXISTS emprestimo_clientes (

    id SERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    nome VARCHAR(150) NOT NULL,

    telefone VARCHAR(30) NOT NULL,

    documento VARCHAR(30),

    email VARCHAR(150),

    endereco TEXT,

    observacoes TEXT,

    status VARCHAR(20)
        NOT NULL
        DEFAULT 'ativo',

    data_criacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    data_atualizacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT emprestimo_cliente_status_valido
        CHECK (
            status IN (
                'ativo',
                'inativo',
                'bloqueado'
            )
        ),

    CONSTRAINT emprestimo_cliente_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE

);


-- ==========================================
-- EMPRÉSTIMOS
-- ==========================================

CREATE TABLE IF NOT EXISTS emprestimos (

    id SERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    cliente_id INTEGER NOT NULL,

    usuario_id INTEGER,

    valor_emprestado NUMERIC(14, 2)
        NOT NULL,

    taxa_juros NUMERIC(8, 4)
        NOT NULL
        DEFAULT 0,

    tipo_juros VARCHAR(20)
        NOT NULL
        DEFAULT 'simples',

    quantidade_parcelas INTEGER
        NOT NULL,

    valor_total NUMERIC(14, 2)
        NOT NULL,

    valor_pago NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    data_emprestimo DATE
        NOT NULL
        DEFAULT CURRENT_DATE,

    primeira_parcela DATE
        NOT NULL,

    frequencia VARCHAR(20)
        NOT NULL
        DEFAULT 'mensal',

    status VARCHAR(30)
        NOT NULL
        DEFAULT 'ativo',

    observacoes TEXT,

    data_criacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    data_atualizacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT emprestimo_valor_positivo
        CHECK (
            valor_emprestado > 0
        ),

    CONSTRAINT emprestimo_total_valido
        CHECK (
            valor_total >= valor_emprestado
        ),

    CONSTRAINT emprestimo_valor_pago_valido
        CHECK (
            valor_pago >= 0
        ),

    CONSTRAINT emprestimo_taxa_valida
        CHECK (
            taxa_juros >= 0
        ),

    CONSTRAINT emprestimo_parcelas_validas
        CHECK (
            quantidade_parcelas > 0
            AND quantidade_parcelas <= 360
        ),

    CONSTRAINT emprestimo_tipo_juros_valido
        CHECK (
            tipo_juros IN (
                'simples',
                'composto'
            )
        ),

    CONSTRAINT emprestimo_frequencia_valida
        CHECK (
            frequencia IN (
                'semanal',
                'quinzenal',
                'mensal'
            )
        ),

    CONSTRAINT emprestimo_status_valido
        CHECK (
            status IN (
                'ativo',
                'atrasado',
                'quitado',
                'cancelado',
                'renegociado'
            )
        ),

    CONSTRAINT emprestimo_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT emprestimo_cliente_fk
        FOREIGN KEY (cliente_id)
        REFERENCES emprestimo_clientes(id)
        ON DELETE RESTRICT,

    CONSTRAINT emprestimo_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL

);


-- ==========================================
-- PARCELAS
-- ==========================================

CREATE TABLE IF NOT EXISTS emprestimo_parcelas (

    id SERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    emprestimo_id INTEGER NOT NULL,

    numero INTEGER NOT NULL,

    data_vencimento DATE NOT NULL,

    valor_principal NUMERIC(14, 2)
        NOT NULL,

    valor_juros NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    valor_multa NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    valor_parcela NUMERIC(14, 2)
        NOT NULL,

    valor_pago NUMERIC(14, 2)
        NOT NULL
        DEFAULT 0,

    status VARCHAR(25)
        NOT NULL
        DEFAULT 'pendente',

    data_pagamento TIMESTAMP,

    data_criacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    data_atualizacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT parcela_numero_valido
        CHECK (
            numero > 0
        ),

    CONSTRAINT parcela_valores_validos
        CHECK (
            valor_principal >= 0
            AND valor_juros >= 0
            AND valor_multa >= 0
            AND valor_parcela > 0
            AND valor_pago >= 0
        ),

    CONSTRAINT parcela_status_valido
        CHECK (
            status IN (
                'pendente',
                'parcial',
                'paga',
                'atrasada',
                'cancelada',
                'renegociada'
            )
        ),

    CONSTRAINT parcela_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT parcela_emprestimo_fk
        FOREIGN KEY (emprestimo_id)
        REFERENCES emprestimos(id)
        ON DELETE CASCADE,

    CONSTRAINT parcela_numero_unico
        UNIQUE (
            emprestimo_id,
            numero
        )

);


-- ==========================================
-- PAGAMENTOS
-- ==========================================

CREATE TABLE IF NOT EXISTS emprestimo_pagamentos (

    id SERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    emprestimo_id INTEGER NOT NULL,

    parcela_id INTEGER,

    usuario_id INTEGER,

    valor NUMERIC(14, 2)
        NOT NULL,

    forma_pagamento VARCHAR(30)
        NOT NULL
        DEFAULT 'dinheiro',

    data_pagamento TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    observacoes TEXT,

    estornado BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    data_estorno TIMESTAMP,

    motivo_estorno TEXT,

    data_criacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT pagamento_valor_positivo
        CHECK (
            valor > 0
        ),

    CONSTRAINT pagamento_forma_valida
        CHECK (
            forma_pagamento IN (
                'dinheiro',
                'pix',
                'cartao',
                'transferencia',
                'outro'
            )
        ),

    CONSTRAINT pagamento_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT pagamento_emprestimo_fk
        FOREIGN KEY (emprestimo_id)
        REFERENCES emprestimos(id)
        ON DELETE RESTRICT,

    CONSTRAINT pagamento_parcela_fk
        FOREIGN KEY (parcela_id)
        REFERENCES emprestimo_parcelas(id)
        ON DELETE SET NULL,

    CONSTRAINT pagamento_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL

);


-- ==========================================
-- MODELOS DE MENSAGEM
-- ==========================================

CREATE TABLE IF NOT EXISTS emprestimo_modelos_cobranca (

    id SERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    nome VARCHAR(100) NOT NULL,

    tipo VARCHAR(30) NOT NULL,

    mensagem TEXT NOT NULL,

    ativo BOOLEAN
        NOT NULL
        DEFAULT TRUE,

    data_criacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    data_atualizacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT modelo_tipo_valido
        CHECK (
            tipo IN (
                'lembrete',
                'vence_hoje',
                'atrasada',
                'confirmacao_pagamento'
            )
        ),

    CONSTRAINT modelo_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE

);


-- ==========================================
-- COBRANÇAS
-- ==========================================

CREATE TABLE IF NOT EXISTS emprestimo_cobrancas (

    id SERIAL PRIMARY KEY,

    empresa_id INTEGER NOT NULL,

    cliente_id INTEGER NOT NULL,

    emprestimo_id INTEGER NOT NULL,

    parcela_id INTEGER,

    modelo_id INTEGER,

    canal VARCHAR(20)
        NOT NULL
        DEFAULT 'whatsapp',

    telefone VARCHAR(30) NOT NULL,

    mensagem TEXT NOT NULL,

    status VARCHAR(25)
        NOT NULL
        DEFAULT 'agendada',

    data_agendada TIMESTAMP,

    data_envio TIMESTAMP,

    tentativa INTEGER
        NOT NULL
        DEFAULT 0,

    erro TEXT,

    resposta_externa TEXT,

    data_criacao TIMESTAMP
        NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT cobranca_canal_valido
        CHECK (
            canal IN (
                'whatsapp',
                'manual'
            )
        ),

    CONSTRAINT cobranca_status_valido
        CHECK (
            status IN (
                'agendada',
                'processando',
                'enviada',
                'falhou',
                'cancelada',
                'manual'
            )
        ),

    CONSTRAINT cobranca_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE CASCADE,

    CONSTRAINT cobranca_cliente_fk
        FOREIGN KEY (cliente_id)
        REFERENCES emprestimo_clientes(id)
        ON DELETE CASCADE,

    CONSTRAINT cobranca_emprestimo_fk
        FOREIGN KEY (emprestimo_id)
        REFERENCES emprestimos(id)
        ON DELETE CASCADE,

    CONSTRAINT cobranca_parcela_fk
        FOREIGN KEY (parcela_id)
        REFERENCES emprestimo_parcelas(id)
        ON DELETE SET NULL,

    CONSTRAINT cobranca_modelo_fk
        FOREIGN KEY (modelo_id)
        REFERENCES emprestimo_modelos_cobranca(id)
        ON DELETE SET NULL

);


-- ==========================================
-- ÍNDICES
-- ==========================================

CREATE INDEX IF NOT EXISTS idx_emprestimo_clientes_empresa
ON emprestimo_clientes (
    empresa_id
);


CREATE INDEX IF NOT EXISTS idx_emprestimo_clientes_nome
ON emprestimo_clientes (
    empresa_id,
    nome
);


CREATE INDEX IF NOT EXISTS idx_emprestimos_empresa_status
ON emprestimos (
    empresa_id,
    status
);


CREATE INDEX IF NOT EXISTS idx_emprestimos_cliente
ON emprestimos (
    empresa_id,
    cliente_id
);


CREATE INDEX IF NOT EXISTS idx_parcelas_vencimento
ON emprestimo_parcelas (
    empresa_id,
    status,
    data_vencimento
);


CREATE INDEX IF NOT EXISTS idx_parcelas_emprestimo
ON emprestimo_parcelas (
    empresa_id,
    emprestimo_id
);


CREATE INDEX IF NOT EXISTS idx_pagamentos_emprestimo
ON emprestimo_pagamentos (
    empresa_id,
    emprestimo_id,
    data_pagamento
);


CREATE INDEX IF NOT EXISTS idx_cobrancas_agendadas
ON emprestimo_cobrancas (
    empresa_id,
    status,
    data_agendada
);


-- ==========================================
-- MODELOS PADRÃO PARA EMPRESAS EXISTENTES
-- ==========================================

INSERT INTO emprestimo_modelos_cobranca (
    empresa_id,
    nome,
    tipo,
    mensagem
)

SELECT
    empresa.id,
    'Lembrete de vencimento',
    'lembrete',
    'Olá, {cliente}! Lembramos que sua parcela de {valor}, com vencimento em {vencimento}, está próxima. Caso já tenha realizado o pagamento, desconsidere esta mensagem.'

FROM empresa

WHERE NOT EXISTS (

    SELECT 1

    FROM emprestimo_modelos_cobranca modelo

    WHERE modelo.empresa_id = empresa.id
      AND modelo.tipo = 'lembrete'

);


INSERT INTO emprestimo_modelos_cobranca (
    empresa_id,
    nome,
    tipo,
    mensagem
)

SELECT
    empresa.id,
    'Parcela vencendo hoje',
    'vence_hoje',
    'Olá, {cliente}! Sua parcela de {valor} vence hoje. Entre em contato caso precise de ajuda.'

FROM empresa

WHERE NOT EXISTS (

    SELECT 1

    FROM emprestimo_modelos_cobranca modelo

    WHERE modelo.empresa_id = empresa.id
      AND modelo.tipo = 'vence_hoje'

);


INSERT INTO emprestimo_modelos_cobranca (
    empresa_id,
    nome,
    tipo,
    mensagem
)

SELECT
    empresa.id,
    'Parcela atrasada',
    'atrasada',
    'Olá, {cliente}. Identificamos uma parcela de {valor} vencida em {vencimento}. Entre em contato para regularizar ou informar o pagamento.'

FROM empresa

WHERE NOT EXISTS (

    SELECT 1

    FROM emprestimo_modelos_cobranca modelo

    WHERE modelo.empresa_id = empresa.id
      AND modelo.tipo = 'atrasada'

);


COMMIT;