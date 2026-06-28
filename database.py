import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# carrega variáveis do .env
load_dotenv()

def conectar():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT")
        )
        return conn

    except Exception as e:
        print("Erro ao conectar no banco:", e)
        raise


def criar_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)