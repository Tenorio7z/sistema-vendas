from pathlib import Path

from database import conectar


def executar():
    caminho = (
        Path(__file__).resolve().parent
        / "migrations"
        / "014_configuracao_impressao.sql"
    )
    sql = caminho.read_text(encoding="utf-8")

    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(sql)
        conn.commit()
        print("Configuração de impressão instalada com sucesso.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()

