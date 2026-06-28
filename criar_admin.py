from werkzeug.security import generate_password_hash
from database import conectar, criar_cursor

conn = conectar()
cursor = criar_cursor(conn)

# ==========================================
# EMPRESA MASTER
# ==========================================

cursor.execute("""
INSERT INTO empresa (
    nome,
    plano
)
VALUES (%s, %s)
RETURNING id
""", (
    "Nexus Master",
    "premium"
))

empresa_id = cursor.fetchone()["id"]

# ==========================================
# ADMIN MASTER
# ==========================================

senha = generate_password_hash("admin123")

cursor.execute("""
INSERT INTO usuarios (
    usuario,
    senha,
    nivel,
    empresa_id
    
)
VALUES (%s, %s, %s, %s)
""", (
    "admin",
    senha,
    "master",
    empresa_id
    
))

conn.commit()
conn.close()

print("""
==================================
MASTER CRIADO NO POSTGRES
==================================

usuario: admin
senha: admin123

==================================
""")