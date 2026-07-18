from pathlib import Path

from database import conectar


def executar():
    caminho = (
        Path(__file__).resolve().parent
        / "migrations"
        / "010_clientes.sql"
    )

    sql = caminho.read_text(encoding="utf-8")

    conexao = conectar()
    cursor = conexao.cursor()

    try:
        cursor.execute(sql)
        conexao.commit()

        print("Migração de clientes executada com sucesso.")

    except Exception:
        conexao.rollback()
        raise

    finally:
        cursor.close()
        conexao.close()


if __name__ == "__main__":
    executar()