from services.produtos_service import ProdutosService


def buscar_produtos_vendidos_mes(empresa_id):
    return ProdutosService.vendidos_mes(empresa_id)


def buscar_total_produtos(empresa_id):
    return ProdutosService.total_produtos(empresa_id)


def buscar_estoque_baixo(empresa_id):
    return ProdutosService.estoque_baixo(empresa_id)


def buscar_sem_estoque(empresa_id):
    return ProdutosService.sem_estoque(empresa_id)


def buscar_produto_por_nome(empresa_id, nome):
    return ProdutosService.buscar_por_nome(
        empresa_id,
        nome
    )


def buscar_produto_mais_vendido(empresa_id):
    return ProdutosService.produto_mais_vendido(empresa_id)
