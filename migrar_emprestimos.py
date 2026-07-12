from pathlib import Path

from database import conectar


def executar_migracao():
    caminho = (
        Path(__file__).parent
        / "migrations"
        / "001_emprestimos.sql"
    )

    if not caminho.exists():
        raise FileNotFoundError(
            f"Migration não encontrada: {caminho}"
        )

    sql = caminho.read_text(
        encoding="utf-8"
    )

    conn = conectar()
    cursor = conn.cursor()

    try:
        cursor.execute(sql)

        conn.commit()

        print(
            "Migration de empréstimos "
            "executada com sucesso."
        )

    except Exception as erro:
        conn.rollback()

        print(
            "Erro ao executar migration:"
        )

        print(erro)

        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar_migracao()