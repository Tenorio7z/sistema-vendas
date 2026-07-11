import json
import logging

from services.ia.capabilities.caixa import (
    buscar_resumo_caixa,
)

from services.ia.capabilities.produtos import (
    buscar_estoque_baixo,
    buscar_produto_mais_vendido,
    buscar_produto_por_nome,
    buscar_produtos_vendidos_mes,
    buscar_sem_estoque,
    buscar_total_produtos,
)

from services.ia.capabilities.relatorios import (
    buscar_relatorio_geral,
)

from services.ia.capabilities.vendas import (
    buscar_vendas_ano,
    buscar_vendas_hoje,
    buscar_vendas_mes,
)


logger = logging.getLogger(__name__)


FERRAMENTAS = [
    {
        "type": "function",
        "name": "buscar_produto",
        "description": (
            "Busca um produto pelo nome e retorna nome, "
            "preco, estoque e codigo de barras."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "description": (
                        "Nome completo ou parcial do produto."
                    ),
                }
            },
            "required": ["nome"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "consultar_vendas",
        "description": (
            "Consulta quantidade de vendas e faturamento "
            "de hoje, do mes atual ou do ano atual."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": [
                        "hoje",
                        "mes",
                        "ano",
                    ],
                    "description": (
                        "Periodo que deve ser consultado."
                    ),
                }
            },
            "required": ["periodo"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "listar_produtos_vendidos_mes",
        "description": (
            "Lista os produtos vendidos no mes atual, "
            "incluindo quantidade e valor total."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "consultar_estoque",
        "description": (
            "Lista produtos com estoque baixo ou "
            "produtos completamente sem estoque."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "situacao": {
                    "type": "string",
                    "enum": [
                        "baixo",
                        "sem_estoque",
                    ],
                    "description": (
                        "Situacao de estoque que deve "
                        "ser consultada."
                    ),
                }
            },
            "required": ["situacao"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "consultar_total_produtos",
        "description": (
            "Retorna a quantidade total de produtos "
            "cadastrados na empresa."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "consultar_produto_mais_vendido",
        "description": (
            "Retorna o produto mais vendido pela empresa."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "consultar_caixa",
        "description": (
            "Consulta o caixa aberto, saldo, quantidade "
            "de vendas e faturamento do caixa."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "consultar_visao_geral",
        "description": (
            "Retorna uma visao geral da empresa, com "
            "vendas, produtos, estoque baixo e caixa."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def _converter_para_json(dados):
    return json.dumps(
        dados,
        ensure_ascii=False,
        default=str,
    )


def executar_ferramenta(
    nome,
    argumentos,
    empresa_id,
):
    if not empresa_id:
        raise ValueError(
            "Empresa nao identificada na sessao."
        )

    if not isinstance(argumentos, dict):
        argumentos = {}

    try:
        if nome == "buscar_produto":
            nome_produto = str(
                argumentos.get("nome", "")
            ).strip()

            if not nome_produto:
                return _converter_para_json({
                    "sucesso": False,
                    "erro": (
                        "Nome do produto nao informado."
                    ),
                })

            produto = buscar_produto_por_nome(
                empresa_id,
                nome_produto,
            )

            if not produto:
                return _converter_para_json({
                    "sucesso": True,
                    "encontrado": False,
                    "produto_pesquisado": nome_produto,
                })

            return _converter_para_json({
                "sucesso": True,
                "encontrado": True,
                "produto": produto,
            })

        if nome == "consultar_vendas":
            periodo = argumentos.get(
                "periodo",
                "mes",
            )

            funcoes = {
                "hoje": buscar_vendas_hoje,
                "mes": buscar_vendas_mes,
                "ano": buscar_vendas_ano,
            }

            funcao = funcoes.get(periodo)

            if not funcao:
                return _converter_para_json({
                    "sucesso": False,
                    "erro": "Periodo invalido.",
                })

            dados = funcao(empresa_id)

            return _converter_para_json({
                "sucesso": True,
                "periodo": periodo,
                "dados": dados,
            })

        if nome == "listar_produtos_vendidos_mes":
            produtos = buscar_produtos_vendidos_mes(
                empresa_id
            )

            return _converter_para_json({
                "sucesso": True,
                "periodo": "mes",
                "quantidade_produtos": len(
                    produtos or []
                ),
                "produtos": produtos or [],
            })

        if nome == "consultar_estoque":
            situacao = argumentos.get(
                "situacao"
            )

            if situacao == "baixo":
                produtos = buscar_estoque_baixo(
                    empresa_id
                )

            elif situacao == "sem_estoque":
                produtos = buscar_sem_estoque(
                    empresa_id
                )

            else:
                return _converter_para_json({
                    "sucesso": False,
                    "erro": (
                        "Situacao de estoque invalida."
                    ),
                })

            return _converter_para_json({
                "sucesso": True,
                "situacao": situacao,
                "quantidade_produtos": len(
                    produtos or []
                ),
                "produtos": produtos or [],
            })

        if nome == "consultar_total_produtos":
            dados = buscar_total_produtos(
                empresa_id
            )

            return _converter_para_json({
                "sucesso": True,
                "dados": dados,
            })

        if nome == "consultar_produto_mais_vendido":
            produto = buscar_produto_mais_vendido(
                empresa_id
            )

            return _converter_para_json({
                "sucesso": True,
                "encontrado": bool(produto),
                "produto": produto,
            })

        if nome == "consultar_caixa":
            dados = buscar_resumo_caixa(
                empresa_id
            )

            return _converter_para_json({
                "sucesso": True,
                "caixa_aberto": bool(dados),
                "dados": dados,
            })

        if nome == "consultar_visao_geral":
            dados = buscar_relatorio_geral(
                empresa_id
            )

            return _converter_para_json({
                "sucesso": True,
                "dados": dados,
            })

        logger.warning(
            "Tentativa de executar ferramenta desconhecida: %s",
            nome,
        )

        return _converter_para_json({
            "sucesso": False,
            "erro": "Ferramenta nao autorizada.",
        })

    except Exception:
        logger.exception(
            "Erro ao executar ferramenta %s",
            nome,
        )

        return _converter_para_json({
            "sucesso": False,
            "erro": (
                "Nao foi possivel consultar "
                "os dados do sistema."
            ),
        })