from pathlib import Path

from database import conectar


def executar():
    caminho = (
        Path(__file__).resolve().parent
        / "migrations"
        / "013_acertos_comissao.sql"
    )

    sql = caminho.read_text(encoding="utf-8")
    conn = conectar()
    cursor = conn.cursor()

    try:
        print("Atualizando o modelo de acertos de comissão...")
        cursor.execute(sql)
        conn.commit()
        print("Migração concluída com sucesso.")
        print("Agora são permitidos vários acertos no mesmo mês.")

    except Exception:
        conn.rollback()
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()
