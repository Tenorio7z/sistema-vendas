from pathlib import Path

from database import conectar


ARQUIVO_MIGRACAO = Path(__file__).resolve().parent / 'migrations' / '020_fidelidade.sql'


def main():
    sql = ARQUIVO_MIGRACAO.read_text(encoding='utf-8-sig')
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        print('Migração 020_fidelidade.sql aplicada com sucesso.')
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
