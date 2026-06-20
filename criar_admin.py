from werkzeug.security import generate_password_hash
import sqlite3

conn = sqlite3.connect(
    "database/database.db"
)

cursor = conn.cursor()

# ==========================================
# EMPRESA MASTER
# ==========================================

cursor.execute("""

INSERT INTO empresa(

    nome,
    plano

)

VALUES(?,?)

""", (

    "Nexus Master",
    "premium"

))

empresa_id = cursor.lastrowid

# ==========================================
# ADMIN MASTER
# ==========================================

senha = generate_password_hash(
    "admin123"
)

cursor.execute("""

INSERT INTO usuarios(

    usuario,
    senha,
    nivel,
    empresa_id,
    status

)

VALUES(?,?,?,?,?)

""", (

    "admin",
    senha,
    "master",
    empresa_id,
    "ativo"

))

conn.commit()

conn.close()

print("""

==================================
MASTER CRIADO
==================================

usuario: admin
senha: admin123

==================================

""")