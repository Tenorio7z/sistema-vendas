from database import conectar, criar_cursor


class ProdutosService:

    @staticmethod
    def vendidos_mes(empresa_id):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute("""
                SELECT
                    p.id,
                    p.nome,
                    SUM(v.quantidade) AS quantidade,
                    COALESCE(SUM(v.valor),0) AS total
                FROM vendas v
                INNER JOIN produtos p
                    ON p.id = v.produto_id
                WHERE
                    v.empresa_id=%s
                    AND v.cancelada=0
                    AND DATE_TRUNC('month', v.data_venda)=
                        DATE_TRUNC('month', CURRENT_DATE)
                GROUP BY
                    p.id,
                    p.nome
                ORDER BY
                    quantidade DESC
            """, (empresa_id,))

            return cursor.fetchall()

        finally:

            cursor.close()
            conn.close()


    @staticmethod
    def estoque_baixo(empresa_id, limite=5):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute("""
                SELECT
                    id,
                    nome,
                    estoque
                FROM produtos
                WHERE
                    empresa_id=%s
                    AND estoque<=%s
                ORDER BY
                    estoque ASC,
                    nome
            """, (empresa_id, limite))

            return cursor.fetchall()

        finally:

            cursor.close()
            conn.close()


    @staticmethod
    def sem_estoque(empresa_id):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute("""
                SELECT
                    id,
                    nome
                FROM produtos
                WHERE
                    empresa_id=%s
                    AND estoque=0
                ORDER BY nome
            """, (empresa_id,))

            return cursor.fetchall()

        finally:

            cursor.close()
            conn.close()


    @staticmethod
    def total_produtos(empresa_id):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute("""
                SELECT
                    COUNT(*) AS total
                FROM produtos
                WHERE empresa_id=%s
            """, (empresa_id,))

            return cursor.fetchone()

        finally:

            cursor.close()
            conn.close()
    
    
    @staticmethod
    def produto_mais_vendido(empresa_id):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute("""
                SELECT
                    p.nome,
                    SUM(v.quantidade) AS quantidade
                FROM vendas v
                INNER JOIN produtos p
                    ON p.id = v.produto_id
                WHERE
                    v.empresa_id=%s
                    AND v.cancelada=0
                GROUP BY
                    p.id,
                    p.nome
                ORDER BY
                    quantidade DESC
                LIMIT 1
            """, (empresa_id,))

            return cursor.fetchone()

        finally:

            cursor.close()
            conn.close()
            
    @staticmethod
    def buscar_por_nome(empresa_id, nome):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute("""
                SELECT
                    id,
                    nome,
                    preco,
                    estoque,
                    codigo_barras
                FROM produtos
                WHERE
                    empresa_id=%s
                    AND LOWER(nome) LIKE LOWER(%s)
                LIMIT 1
            """, (
                empresa_id,
                f"%{nome}%"
            ))

            return cursor.fetchone()

        finally:

            cursor.close()
            conn.close()