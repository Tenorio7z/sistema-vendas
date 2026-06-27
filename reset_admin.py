from database import conectar

conn = conectar()
cursor = conn.cursor()

cursor.execute("""
DELETE FROM usuarios
WHERE usuario = 'Tenorio_7z'
""")

conn.commit()
conn.close()

print("Admin antigo removido")