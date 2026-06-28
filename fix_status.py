from database import conectar

conn = conectar()
cursor = conn.cursor()

cursor.execute("""
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'ativo';
""")

conn.commit()
conn.close()

print("coluna status adicionada")