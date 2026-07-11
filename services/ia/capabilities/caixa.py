from database import conectar, criar_cursor


def buscar_resumo_caixa(empresa_id):
    conn = conectar()
    cursor = criar_cursor(conn)
    try:
        cursor.execute("""
            SELECT id, status, valor_inicial, valor_final, data_abertura
            FROM caixa
            WHERE empresa_id = %s AND status = 'aberto'
            ORDER BY id DESC LIMIT 1
        """, (empresa_id,))
        caixa = cursor.fetchone()
        if not caixa:
            return None

        cursor.execute("""
            SELECT COUNT(*) AS quantidade, COALESCE(SUM(valor), 0) AS total
            FROM vendas
            WHERE empresa_id = %s AND caixa_id = %s AND cancelada = 0
        """, (empresa_id, caixa["id"]))
        vendas = cursor.fetchone()
        return {"caixa": caixa, "vendas": vendas}
    finally:
        cursor.close()
        conn.close()
