import sqlite3


def conectar():

    conn = sqlite3.connect("database/database.db", timeout=30)

    conn.execute("PRAGMA journal_mode=WAL")

    conn.row_factory = sqlite3.Row

    return conn
