from database import conectar

conn = conectar()
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM usuarios
    WHERE usuario = %s
""", ("Tenório_7z",))

conn.commit()
conn.close()

print("Admin removido com sucesso.")