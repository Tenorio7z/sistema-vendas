from database import conectar, criar_cursor


SQL_ONBOARDING = """
-- =========================================================
-- CONVITES DE CADASTRO
-- =========================================================

CREATE TABLE IF NOT EXISTS onboarding_convites (
    id BIGSERIAL PRIMARY KEY,

    token_hash VARCHAR(64) NOT NULL UNIQUE,

    criado_por INTEGER NULL,

    nome_destinatario VARCHAR(160),
    telefone_destinatario VARCHAR(30),
    email_destinatario VARCHAR(180),

    status VARCHAR(20) NOT NULL DEFAULT 'ativo',

    expira_em TIMESTAMP NOT NULL,
    utilizado_em TIMESTAMP NULL,
    revogado_em TIMESTAMP NULL,

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT onboarding_convite_status_check
        CHECK (
            status IN (
                'ativo',
                'utilizado',
                'expirado',
                'revogado'
            )
        ),

    CONSTRAINT onboarding_convite_criado_por_fk
        FOREIGN KEY (criado_por)
        REFERENCES usuarios(id)
        ON DELETE SET NULL
);


-- =========================================================
-- SOLICITAÇÕES DE EMPRESA
-- =========================================================

CREATE TABLE IF NOT EXISTS onboarding_solicitacoes (
    id BIGSERIAL PRIMARY KEY,

    convite_id BIGINT NOT NULL UNIQUE,

    nome_empresa VARCHAR(180) NOT NULL,
    nome_responsavel VARCHAR(180) NOT NULL,

    cpf_cnpj VARCHAR(30),
    cpf_cnpj_normalizado VARCHAR(20),

    telefone VARCHAR(30) NOT NULL,
    telefone_normalizado VARCHAR(20) NOT NULL,

    email VARCHAR(180) NOT NULL,
    usuario VARCHAR(120) NOT NULL,

    senha_hash TEXT NOT NULL,

    segmento VARCHAR(120),
    cidade VARCHAR(120),
    estado VARCHAR(2),

    observacoes_cliente TEXT,

    aceitou_termos BOOLEAN NOT NULL DEFAULT FALSE,
    aceitou_whatsapp BOOLEAN NOT NULL DEFAULT FALSE,

    aceitou_termos_em TIMESTAMP NULL,
    ip_cadastro VARCHAR(80),
    user_agent TEXT,

    status VARCHAR(30) NOT NULL DEFAULT 'aguardando',

    plano_aprovado VARCHAR(30),
    emprestimos_ativo BOOLEAN NOT NULL DEFAULT FALSE,
    dias_teste INTEGER NOT NULL DEFAULT 0,

    observacoes_admin TEXT,
    motivo_rejeicao TEXT,

    analisada_por INTEGER NULL,
    analisada_em TIMESTAMP NULL,

    empresa_criada_id INTEGER NULL,
    usuario_criado_id INTEGER NULL,

    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT onboarding_solicitacao_status_check
        CHECK (
            status IN (
                'aguardando',
                'em_analise',
                'aprovada',
                'rejeitada',
                'cancelada'
            )
        ),

    CONSTRAINT onboarding_solicitacao_plano_check
        CHECK (
            plano_aprovado IS NULL
            OR plano_aprovado IN (
                'comum',
                'premium'
            )
        ),

    CONSTRAINT onboarding_solicitacao_dias_teste_check
        CHECK (
            dias_teste >= 0
            AND dias_teste <= 365
        ),

    CONSTRAINT onboarding_solicitacao_convite_fk
        FOREIGN KEY (convite_id)
        REFERENCES onboarding_convites(id)
        ON DELETE RESTRICT,

    CONSTRAINT onboarding_solicitacao_analisada_por_fk
        FOREIGN KEY (analisada_por)
        REFERENCES usuarios(id)
        ON DELETE SET NULL,

    CONSTRAINT onboarding_solicitacao_empresa_fk
        FOREIGN KEY (empresa_criada_id)
        REFERENCES empresa(id)
        ON DELETE SET NULL,

    CONSTRAINT onboarding_solicitacao_usuario_fk
        FOREIGN KEY (usuario_criado_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL
);


-- =========================================================
-- FILA DE MENSAGENS DO WHATSAPP
-- =========================================================

CREATE TABLE IF NOT EXISTS whatsapp_mensagens (
    id BIGSERIAL PRIMARY KEY,

    solicitacao_id BIGINT NULL,
    empresa_id INTEGER NULL,

    telefone VARCHAR(30) NOT NULL,
    telefone_normalizado VARCHAR(20) NOT NULL,

    tipo VARCHAR(40) NOT NULL,
    mensagem TEXT NOT NULL,

    provedor VARCHAR(50),

    status VARCHAR(20) NOT NULL DEFAULT 'pendente',

    tentativas INTEGER NOT NULL DEFAULT 0,
    maximo_tentativas INTEGER NOT NULL DEFAULT 5,

    identificador_externo VARCHAR(255),
    ultimo_erro TEXT,

    proxima_tentativa_em TIMESTAMP NULL,
    enviada_em TIMESTAMP NULL,

    criada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT whatsapp_mensagem_status_check
        CHECK (
            status IN (
                'pendente',
                'processando',
                'enviada',
                'falhou',
                'cancelada'
            )
        ),

    CONSTRAINT whatsapp_mensagem_tentativas_check
        CHECK (
            tentativas >= 0
            AND maximo_tentativas BETWEEN 1 AND 20
        ),

    CONSTRAINT whatsapp_mensagem_solicitacao_fk
        FOREIGN KEY (solicitacao_id)
        REFERENCES onboarding_solicitacoes(id)
        ON DELETE SET NULL,

    CONSTRAINT whatsapp_mensagem_empresa_fk
        FOREIGN KEY (empresa_id)
        REFERENCES empresa(id)
        ON DELETE SET NULL
);


-- =========================================================
-- HISTÓRICO E AUDITORIA
-- =========================================================

CREATE TABLE IF NOT EXISTS onboarding_auditoria (
    id BIGSERIAL PRIMARY KEY,

    solicitacao_id BIGINT NULL,
    convite_id BIGINT NULL,

    usuario_id INTEGER NULL,

    acao VARCHAR(80) NOT NULL,
    descricao TEXT,

    dados_anteriores JSONB,
    dados_novos JSONB,

    endereco_ip VARCHAR(80),
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT onboarding_auditoria_solicitacao_fk
        FOREIGN KEY (solicitacao_id)
        REFERENCES onboarding_solicitacoes(id)
        ON DELETE SET NULL,

    CONSTRAINT onboarding_auditoria_convite_fk
        FOREIGN KEY (convite_id)
        REFERENCES onboarding_convites(id)
        ON DELETE SET NULL,

    CONSTRAINT onboarding_auditoria_usuario_fk
        FOREIGN KEY (usuario_id)
        REFERENCES usuarios(id)
        ON DELETE SET NULL
);


-- =========================================================
-- ÍNDICES
-- =========================================================

CREATE INDEX IF NOT EXISTS onboarding_convites_status_idx
    ON onboarding_convites(status);

CREATE INDEX IF NOT EXISTS onboarding_convites_expira_em_idx
    ON onboarding_convites(expira_em);

CREATE INDEX IF NOT EXISTS onboarding_convites_criado_por_idx
    ON onboarding_convites(criado_por);


CREATE INDEX IF NOT EXISTS onboarding_solicitacoes_status_idx
    ON onboarding_solicitacoes(status);

CREATE INDEX IF NOT EXISTS onboarding_solicitacoes_criada_em_idx
    ON onboarding_solicitacoes(criada_em DESC);

CREATE INDEX IF NOT EXISTS onboarding_solicitacoes_telefone_idx
    ON onboarding_solicitacoes(telefone_normalizado);

CREATE INDEX IF NOT EXISTS onboarding_solicitacoes_cpf_cnpj_idx
    ON onboarding_solicitacoes(cpf_cnpj_normalizado);

CREATE INDEX IF NOT EXISTS onboarding_solicitacoes_email_lower_idx
    ON onboarding_solicitacoes(LOWER(email));

CREATE INDEX IF NOT EXISTS onboarding_solicitacoes_usuario_lower_idx
    ON onboarding_solicitacoes(LOWER(usuario));


CREATE INDEX IF NOT EXISTS whatsapp_mensagens_fila_idx
    ON whatsapp_mensagens(
        status,
        proxima_tentativa_em,
        criada_em
    );

CREATE INDEX IF NOT EXISTS whatsapp_mensagens_solicitacao_idx
    ON whatsapp_mensagens(solicitacao_id);


CREATE INDEX IF NOT EXISTS onboarding_auditoria_solicitacao_idx
    ON onboarding_auditoria(
        solicitacao_id,
        criado_em DESC
    );
"""


def verificar_tabelas(cursor):
    tabelas = (
        "onboarding_convites",
        "onboarding_solicitacoes",
        "whatsapp_mensagens",
        "onboarding_auditoria",
    )

    resultado = []

    for tabela in tabelas:
        cursor.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            ) AS existe
            """,
            (tabela,),
        )

        registro = cursor.fetchone() or {}

        resultado.append(
            {
                "tabela": tabela,
                "existe": bool(
                    registro.get("existe")
                ),
            }
        )

    return resultado


def executar():
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        print(
            "Criando estrutura de convites "
            "e aprovação de empresas..."
        )

        cursor.execute(SQL_ONBOARDING)

        conn.commit()

        tabelas = verificar_tabelas(
            cursor
        )

        print()
        print("Resultado da instalação:")

        for item in tabelas:
            status = (
                "OK"
                if item["existe"]
                else "ERRO"
            )

            print(
                f"  [{status}] "
                f"{item['tabela']}"
            )

        if not all(
            item["existe"]
            for item in tabelas
        ):
            raise RuntimeError(
                "Uma ou mais tabelas não foram criadas."
            )

        print()
        print(
            "Estrutura de onboarding "
            "instalada com sucesso."
        )

    except Exception:
        conn.rollback()

        print()
        print(
            "Erro ao instalar a estrutura "
            "de onboarding."
        )

        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()