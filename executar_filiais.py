from pathlib import Path

from database import conectar


def executar():
    caminho = Path(__file__).parent / "migrations" / "012_filiais_estoque.sql"
    sql = caminho.read_text(encoding="utf-8")
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        print("Estrutura de filiais criada com sucesso.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()
