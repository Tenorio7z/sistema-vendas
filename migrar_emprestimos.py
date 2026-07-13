from pathlib import Path

from database import conectar


def executar_migracoes():
    pasta = Path(__file__).parent / "migrations"
    arquivos = sorted(pasta.glob("*.sql"))

    if not arquivos:
        raise FileNotFoundError(
            f"Nenhuma migration encontrada em: {pasta}"
        )

    conn = conectar()
    cursor = conn.cursor()

    try:
        for caminho in arquivos:
            sql = caminho.read_text(encoding="utf-8")
            cursor.execute(sql)
            print(f"Migration executada: {caminho.name}")

        conn.commit()
        print("Todas as migrations foram executadas com sucesso.")

    except Exception as erro:
        conn.rollback()
        print("Erro ao executar migrations:", erro)
        raise

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar_migracoes()
