from decimal import Decimal, ROUND_HALF_UP


ZERO = Decimal("0.00")


def _dinheiro(valor):
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resumo_pagamentos(cursor, empresa_id, inicio, fim, filial_id=None):
    """Retorna recebimentos líquidos sem duplicar vendas ou cancelamentos."""
    filtros = [
        "v.empresa_id = %s",
        "v.data_venda >= %s",
        "v.data_venda < %s",
        "COALESCE(v.cancelada, 0) = 0",
    ]
    parametros = [empresa_id, inicio, fim]
    if filial_id is not None:
        filtros.append("v.filial_id = %s")
        parametros.append(filial_id)

    where = " AND ".join(filtros)
    cursor.execute(
        f"""
        WITH recebimentos AS (
            SELECT vp.forma, vp.valor
            FROM venda_pagamentos vp
            INNER JOIN vendas v ON v.id = vp.venda_id
            WHERE {where}

            UNION ALL

            SELECT
                CASE
                    WHEN LOWER(COALESCE(v.pagamento, '')) = 'pix' THEN 'PIX'
                    WHEN LOWER(COALESCE(v.pagamento, '')) LIKE '%%cart%%' THEN 'Cartão'
                    ELSE 'Dinheiro'
                END,
                COALESCE(v.valor, 0)
            FROM vendas v
            WHERE {where}
              AND NOT EXISTS (
                  SELECT 1 FROM venda_pagamentos vp WHERE vp.venda_id = v.id
              )
        )
        SELECT forma, COALESCE(SUM(valor), 0) AS valor
        FROM recebimentos
        GROUP BY forma
        """,
        tuple(parametros + parametros),
    )
    valores = {"Dinheiro": ZERO, "PIX": ZERO, "Cartão": ZERO}
    for linha in cursor.fetchall() or []:
        valores[linha["forma"]] = _dinheiro(linha["valor"])
    total = sum(valores.values(), ZERO)
    return {
        "total": float(total),
        "itens": [
            {
                "forma": forma,
                "valor": float(valor),
                "percentual": float((valor * 100 / total) if total else ZERO),
            }
            for forma, valor in valores.items()
        ],
        "dinheiro": float(valores["Dinheiro"]),
        "pix": float(valores["PIX"]),
        "cartao": float(valores["Cartão"]),
    }
