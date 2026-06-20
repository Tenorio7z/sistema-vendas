import sqlite3

# ==========================================
# CONECTAR
# ==========================================

conn = sqlite3.connect("database/database.db")

cursor = conn.cursor()

# ==========================================
# TABELA EMPRESA
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS empresa(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nome TEXT,

    plano TEXT DEFAULT 'comum'

)

""")

# ==========================================
# TABELA USUÁRIOS
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS usuarios(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    usuario TEXT UNIQUE,
    senha TEXT,

    nivel TEXT,

    status TEXT,

    empresa_id INTEGER

)

""")

# ==========================================
# TABELA PRODUTOS
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS produtos(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nome TEXT,
    preco REAL,
    estoque INTEGER,

    codigo_barras TEXT,

    empresa_id INTEGER

)

""")

# ==========================================
# TABELA VENDAS
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS vendas(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    produto_id INTEGER,

    quantidade INTEGER,

    valor REAL,

    pagamento TEXT,

    empresa_id INTEGER,

    caixa_id INTEGER,

    cancelada INTEGER DEFAULT 0,

    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)

""")

# ==========================================
# TABELA CLIENTES
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS clientes(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    nome TEXT,

    empresa_id INTEGER

)

""")

# ==========================================
# TABELA CAIXA
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS caixa(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    valor_inicial REAL,
    valor_final REAL,

    status TEXT,

    empresa_id INTEGER,

    data_abertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    data_fechamento TIMESTAMP

)

""")

# ==========================================
# TABELA MOVIMENTAÇÕES
# ==========================================

cursor.execute("""

CREATE TABLE IF NOT EXISTS movimentacoes_caixa(

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    tipo TEXT,
    descricao TEXT,
    valor REAL,

    empresa_id INTEGER,

    caixa_id INTEGER,

    data TIMESTAMP DEFAULT CURRENT_TIMESTAMP

)

""")

conn.commit()

conn.close()

print("Banco criado com sucesso")