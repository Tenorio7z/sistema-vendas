from services.ia.capabilities.caixa import buscar_resumo_caixa
from services.ia.capabilities.produtos import buscar_estoque_baixo, buscar_total_produtos
from services.ia.capabilities.vendas import buscar_vendas_mes


def buscar_relatorio_geral(empresa_id):
    return {
        "vendas_mes": buscar_vendas_mes(empresa_id),
        "total_produtos": buscar_total_produtos(empresa_id),
        "estoque_baixo": buscar_estoque_baixo(empresa_id),
        "caixa": buscar_resumo_caixa(empresa_id),
    }
