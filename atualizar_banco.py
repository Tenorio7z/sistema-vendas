import sqlite3

conn = sqlite3.connect("database/database.db")
cursor = conn.cursor()

try:
    cursor.execute("""

    ALTER TABLE usuarios

    ADD COLUMN fcm_token TEXT

    """)

    print("Coluna fcm_token adicionada com sucesso")

except Exception as e:
    print("Erro:", e)

conn.commit()
conn.close()