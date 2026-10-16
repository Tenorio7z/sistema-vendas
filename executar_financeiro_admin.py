from pathlib import Path
from database import conectar


def executar():
    caminho = Path(__file__).resolve().parent / "migrations" / "019_financeiro_admin.sql"
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(caminho.read_text(encoding="utf-8"))
        conn.commit()
        print("Migração do financeiro admin executada com sucesso.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()
