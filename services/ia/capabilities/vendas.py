from services.vendas_service import VendasService


def buscar_vendas_hoje(empresa_id):
    return VendasService.vendas_hoje(empresa_id)


def buscar_vendas_mes(empresa_id):
    return VendasService.vendas_mes(empresa_id)


def buscar_vendas_ano(empresa_id):
    return VendasService.vendas_ano(empresa_id)