from pathlib import Path

from database import conectar


def executar():
    caminho = Path(__file__).resolve().parent / "migrations" / "018_configuracoes_base.sql"
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(caminho.read_text(encoding="utf-8"))
        conn.commit()
        print("Migração das configurações base executada com sucesso.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()
