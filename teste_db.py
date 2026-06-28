from database import conectar
import os
print("DB_HOST =", os.getenv("DB_HOST"))
print("DB_NAME =", os.getenv("DB_NAME"))
print("DB_USER =", os.getenv("DB_USER"))

try:
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT 1")
    print("Banco conectado com sucesso")

    conn.close()

except Exception as e:
    print("Erro ao conectar:", e)