from database import conectar, criar_cursor

conn = conectar()
cursor = criar_cursor(conn)

# adiciona coluna status se não existir
cursor.execute("""
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ativo'
""")

conn.commit()
conn.close()

print("Tabela usuarios corrigida com sucesso.")