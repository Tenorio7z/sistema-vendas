from database import conectar, criar_cursor

conn = conectar()
cursor = criar_cursor(conn)

cursor.execute("""
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';
""")

print(cursor.fetchall())

conn.close()