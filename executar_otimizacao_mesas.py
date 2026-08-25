from pathlib import Path

from database import conectar


def executar():
    raiz = Path(__file__).resolve().parent
    migracoes = (
        raiz / "migrations" / "014_configuracao_impressao.sql",
        raiz / "migrations" / "015_otimizacao_mesas.sql",
    )

    conn = conectar()
    cursor = conn.cursor()

    try:
        for caminho in migracoes:
            print(f"Executando {caminho.name}...")
            cursor.execute(caminho.read_text(encoding="utf-8"))
        conn.commit()
        print("Painel de mesas otimizado com sucesso.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    executar()

