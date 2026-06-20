import sqlite3

conn = sqlite3.connect("database/database.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(usuarios)")
colunas = cursor.fetchall()

for c in colunas:
    print(c)

conn.close()