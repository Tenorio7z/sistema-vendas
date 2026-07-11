from services.produtos_service import ProdutosService


def buscar_estoque_baixo(empresa_id):

    return ProdutosService.estoque_baixo(empresa_id)


def buscar_sem_estoque(empresa_id):

    return ProdutosService.sem_estoque(empresa_id)


def buscar_total_produtos(empresa_id):

    return ProdutosService.total_produtos(empresa_id)