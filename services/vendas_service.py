from database import conectar, criar_cursor


class VendasService:

    FILTROS = {

        "hoje":
            "DATE(data_venda)=CURRENT_DATE",

        "mes":
            """
            DATE_TRUNC('month', data_venda)=
            DATE_TRUNC('month', CURRENT_DATE)
            """,

        "ano":
            """
            DATE_TRUNC('year', data_venda)=
            DATE_TRUNC('year', CURRENT_DATE)
            """
    }

    @staticmethod
    def consultar(empresa_id, periodo):

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            sql = f"""
                SELECT
                    COUNT(*) AS quantidade,
                    COALESCE(SUM(valor),0) AS total
                FROM vendas
                WHERE empresa_id=%s
                  AND cancelada=0
                  AND {VendasService.FILTROS[periodo]}
            """

            cursor.execute(sql, (empresa_id,))

            return cursor.fetchone()

        finally:

            cursor.close()
            conn.close()


    @staticmethod
    def vendas_hoje(empresa_id):
        return VendasService.consultar(
            empresa_id,
            "hoje"
        )


    @staticmethod
    def vendas_mes(empresa_id):
        return VendasService.consultar(
            empresa_id,
            "mes"
        )


    @staticmethod
    def vendas_ano(empresa_id):
        return VendasService.consultar(
            empresa_id,
            "ano"
        )