from database import conectar, criar_cursor

conn = conectar()
cursor = criar_cursor(conn)


cursor.execute("""
CREATE TABLE IF NOT EXISTS empresa (
    id SERIAL PRIMARY KEY,
    nome TEXT,
    plano TEXT DEFAULT 'comum'
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    usuario TEXT UNIQUE,
    senha TEXT,
    nivel TEXT,
    status TEXT,
    empresa_id INTEGER,
    comissao NUMERIC DEFAULT 0,
    fcm_token TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS api_tokens (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    token TEXT NOT NULL,
    data_criacao TIMESTAMP NOT NULL,
    expira_em TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    nome TEXT,
    preco NUMERIC,
    estoque INTEGER,
    codigo_barras TEXT,
    empresa_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT,
    empresa_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS caixa (
    id SERIAL PRIMARY KEY,
    valor_inicial NUMERIC,
    valor_final NUMERIC,
    status TEXT,
    empresa_id INTEGER,
    data_abertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_fechamento TIMESTAMP
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS movimentacoes_caixa (
    id SERIAL PRIMARY KEY,
    tipo TEXT,
    descricao TEXT,
    valor NUMERIC,
    empresa_id INTEGER,
    caixa_id INTEGER,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")



cursor.execute("""
CREATE TABLE IF NOT EXISTS vendas (
    id SERIAL PRIMARY KEY,
    produto_id INTEGER,
    quantidade INTEGER,
    valor NUMERIC,
    pagamento TEXT,
    empresa_id INTEGER,
    caixa_id INTEGER,
    cancelada INTEGER DEFAULT 0,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usuario_id INTEGER,
    data_venda TIMESTAMP
)
""")



cursor.execute("""
CREATE TABLE IF NOT EXISTS notificacoes (
    id SERIAL PRIMARY KEY,
    empresa_id INTEGER,
    funcionario TEXT,
    valor NUMERIC,
    titulo TEXT,
    mensagem TEXT,
    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lida INTEGER DEFAULT 0,
    produto TEXT
)
""")

conn.commit()
conn.close()

print("Banco PostgreSQL criado com sucesso.")