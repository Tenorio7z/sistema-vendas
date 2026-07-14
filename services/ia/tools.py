import json
import logging

from services.ia.capabilities.consultas import (
    ConsultasNami,
)

from services.ia.capabilities.consultas_admin import (
    ConsultasAdminNami,
)

logger = logging.getLogger(__name__)


PERIODOS = [
    "hoje",
    "ontem",
    "ultimos_7_dias",
    "ultimos_30_dias",
    "semana",
    "mes",
    "mes_passado",
    "ano",
    "ano_passado",
    "periodo",
    "tudo",
]


FERRAMENTAS = [

    # ==========================================
    # VENDAS
    # ==========================================

    {
        "type": "function",
        "name": "consultar_resumo_vendas",
        "description": (
            "Consulta faturamento, quantidade de itens, "
            "quantidade de registros, ticket médio, maior "
            "e menor venda. Use para perguntas como quanto "
            "faturei, quantas vendas fiz, como estão as "
            "vendas ou qual foi o faturamento."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                    "description": (
                        "Período desejado. Use periodo quando "
                        "houver datas inicial e final."
                    ),
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                    "description": (
                        "Data inicial no formato AAAA-MM-DD. "
                        "Use null quando não for necessário."
                    ),
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                    "description": (
                        "Data final no formato AAAA-MM-DD. "
                        "Use null quando não for necessário."
                    ),
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "listar_produtos_vendidos",
        "description": (
            "Lista quais produtos foram vendidos, suas "
            "quantidades e faturamento. Use para perguntas "
            "como quais itens vendi, o que foi vendido, "
            "produtos mais vendidos ou menos vendidos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "ordem": {
                    "type": "string",
                    "enum": [
                        "mais_vendidos",
                        "menos_vendidos",
                    ],
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
                "ordem",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "listar_vendas",
        "description": (
            "Lista vendas individuais recentes com produto, "
            "quantidade, valor, pagamento, data e vendedor. "
            "Use para perguntas como quais vendas, mostre as "
            "últimas vendas, quem vendeu ou detalhes das vendas."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "consultar_formas_pagamento",
        "description": (
            "Consulta quanto foi recebido em PIX, dinheiro, "
            "cartão e outras formas de pagamento. Use para "
            "perguntas sobre pagamentos ou divisão do faturamento."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    # ==========================================
    # PRODUTOS E ESTOQUE
    # ==========================================

    {
        "type": "function",
        "name": "buscar_produto",
        "description": (
            "Busca produtos pelo nome completo, nome parcial "
            "ou código de barras. Retorna preço, estoque e "
            "quantidade total já vendida."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "termo": {
                    "type": "string",
                    "description": (
                        "Nome, parte do nome ou código de barras."
                    ),
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": [
                "termo",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "consultar_estoque",
        "description": (
            "Consulta resumo do estoque ou lista produtos "
            "com estoque baixo, sem estoque, disponíveis ou "
            "todos os produtos. Também calcula unidades e "
            "valor potencial de venda do estoque."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "situacao": {
                    "type": "string",
                    "enum": [
                        "resumo",
                        "baixo",
                        "sem_estoque",
                        "disponivel",
                        "todos",
                    ],
                },
                "limite_estoque_baixo": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 1000,
                    "description": (
                        "Quantidade máxima considerada estoque baixo."
                    ),
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [
                "situacao",
                "limite_estoque_baixo",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    # ==========================================
    # FUNCIONÁRIOS
    # ==========================================

    {
        "type": "function",
        "name": "consultar_ranking_funcionarios",
        "description": (
            "Consulta ranking de funcionários, faturamento, "
            "itens vendidos, percentual de comissão e valor "
            "da comissão. Disponível somente para gerente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    # ==========================================
    # CAIXA
    # ==========================================

    {
        "type": "function",
        "name": "consultar_caixa",
        "description": (
            "Consulta status do caixa, abertura, faturamento, "
            "entradas, saídas, itens vendidos e saldo estimado."
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
        "name": "listar_movimentacoes_caixa",
        "description": (
            "Lista entradas, saídas, suprimentos e sangrias "
            "recentes do caixa. Disponível somente para gerente."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": [
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    # ==========================================
    # VISÃO GERAL
    # ==========================================

    {
        "type": "function",
        "name": "consultar_visao_geral",
        "description": (
            "Retorna uma visão geral da empresa reunindo "
            "vendas do mês, vendas de hoje, estoque, caixa "
            "e produtos mais vendidos."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    
        # ==========================================
    # PAINEL MASTER
    # ==========================================

    {
        "type": "function",
        "name": "admin_resumo_plataforma",
        "description": (
            "Retorna uma visão global da plataforma Nexus, "
            "incluindo quantidade de empresas, planos, módulos, "
            "usuários, produtos e faturamento conjunto. Use "
            "somente quando o usuário for master."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "admin_listar_empresas",
        "description": (
            "Lista as empresas cadastradas na plataforma. "
            "Permite pesquisar por nome, filtrar por plano, "
            "status e módulo de empréstimos. Use para perguntas "
            "como quantas empresas existem, quais estão ativas, "
            "quais são Premium ou quais usam empréstimos."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "busca": {
                    "type": [
                        "string",
                        "null",
                    ],
                    "description": (
                        "Nome da empresa ou usuário. "
                        "Use null para listar todas."
                    ),
                },
                "plano": {
                    "type": "string",
                    "enum": [
                        "todos",
                        "comum",
                        "premium",
                    ],
                },
                "status": {
                    "type": "string",
                    "enum": [
                        "todos",
                        "ativo",
                        "bloqueado",
                    ],
                },
                "emprestimos": {
                    "type": "string",
                    "enum": [
                        "todos",
                        "ativo",
                        "inativo",
                    ],
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [
                "busca",
                "plano",
                "status",
                "emprestimos",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "admin_consultar_empresa",
        "description": (
            "Consulta informações detalhadas de uma empresa "
            "específica pelo nome: plano, status, usuários, "
            "produtos, estoque, vendas, faturamento, caixa e "
            "produtos mais vendidos. Somente para master."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "nome_empresa": {
                    "type": "string",
                    "description": (
                        "Nome completo ou parcial da empresa."
                    ),
                },
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
            },
            "required": [
                "nome_empresa",
                "periodo",
                "data_inicio",
                "data_fim",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "admin_ranking_empresas",
        "description": (
            "Cria um ranking das empresas por faturamento, "
            "itens vendidos, quantidade de usuários ou produtos. "
            "Use para comparar desempenho entre empresas. "
            "Somente para master."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "periodo": {
                    "type": "string",
                    "enum": PERIODOS,
                },
                "data_inicio": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "data_fim": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
                "ordem": {
                    "type": "string",
                    "enum": [
                        "maior_faturamento",
                        "menor_faturamento",
                        "mais_itens",
                        "mais_usuarios",
                        "mais_produtos",
                    ],
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": [
                "periodo",
                "data_inicio",
                "data_fim",
                "ordem",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },

    {
        "type": "function",
        "name": "admin_empresas_sem_vendas",
        "description": (
            "Lista empresas que nunca venderam ou estão sem "
            "vendas há determinada quantidade de dias. "
            "Somente para o administrador master."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dias": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 3650,
                },
                "limite": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [
                "dias",
                "limite",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
    
]


def _json(dados):
    return json.dumps(
        dados,
        ensure_ascii=False,
        default=str,
    )


def _erro(mensagem):
    return _json({
        "sucesso": False,
        "erro": mensagem,
    })


def _sucesso(dados):
    return _json({
        "sucesso": True,
        "dados": dados,
    })


def _normalizar_usuario(
    contexto_usuario,
):
    # Compatibilidade temporária com a versão antiga,
    # que enviava somente o empresa_id.
    if isinstance(
        contexto_usuario,
        dict
    ):
        return {
            "empresa_id": contexto_usuario.get(
                "empresa_id"
            ),
            "usuario_id": contexto_usuario.get(
                "usuario_id"
            ),
            "nivel": (
                contexto_usuario.get(
                    "nivel"
                )
                or "funcionario"
            ).lower(),
            "emprestimos_ativo": bool(
                contexto_usuario.get(
                    "emprestimos_ativo",
                    False
                )
            ),
        }

    return {
        "empresa_id": contexto_usuario,
        "usuario_id": None,
        "nivel": "gerente",
        "emprestimos_ativo": False,
    }


def _somente_gerente(
    usuario,
):
    return usuario["nivel"] in (
        "gerente",
        "master",
    )


def executar_ferramenta(
    nome,
    argumentos,
    contexto_usuario,
):
    usuario = _normalizar_usuario(
        contexto_usuario
    )

    empresa_id = usuario.get(
        "empresa_id"
    )

    usuario_id = usuario.get(
        "usuario_id"
    )

    nivel = usuario.get(
        "nivel"
    )

    if not empresa_id:
        return _erro(
            "Empresa não identificada na sessão."
        )

    if not isinstance(
        argumentos,
        dict
    ):
        argumentos = {}

    periodo = argumentos.get(
        "periodo",
        "mes"
    )

    data_inicio = argumentos.get(
        "data_inicio"
    )

    data_fim = argumentos.get(
        "data_fim"
    )

    try:

        # ======================================
        # RESUMO DE VENDAS
        # ======================================

        if nome == "consultar_resumo_vendas":
            dados = ConsultasNami.resumo_vendas(
                empresa_id=empresa_id,
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                nivel=nivel,
                usuario_id=usuario_id,
            )

            return _sucesso(dados)

        # ======================================
        # PRODUTOS VENDIDOS
        # ======================================

        if nome == "listar_produtos_vendidos":
            dados = ConsultasNami.produtos_vendidos(
                empresa_id=empresa_id,
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                limite=argumentos.get(
                    "limite",
                    20
                ),
                ordem=argumentos.get(
                    "ordem",
                    "mais_vendidos"
                ),
                nivel=nivel,
                usuario_id=usuario_id,
            )

            return _sucesso(dados)

        # ======================================
        # VENDAS INDIVIDUAIS
        # ======================================

        if nome == "listar_vendas":
            dados = ConsultasNami.ultimas_vendas(
                empresa_id=empresa_id,
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                limite=argumentos.get(
                    "limite",
                    10
                ),
                nivel=nivel,
                usuario_id=usuario_id,
            )

            return _sucesso(dados)

        # ======================================
        # FORMAS DE PAGAMENTO
        # ======================================

        if nome == "consultar_formas_pagamento":
            dados = ConsultasNami.formas_pagamento(
                empresa_id=empresa_id,
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                nivel=nivel,
                usuario_id=usuario_id,
            )

            return _sucesso(dados)

        # ======================================
        # BUSCA DE PRODUTO
        # ======================================

        if nome == "buscar_produto":
            dados = ConsultasNami.buscar_produto(
                empresa_id=empresa_id,
                termo=argumentos.get(
                    "termo",
                    ""
                ),
                limite=argumentos.get(
                    "limite",
                    10
                ),
            )

            return _sucesso(dados)

        # ======================================
        # ESTOQUE
        # ======================================

        if nome == "consultar_estoque":
            dados = ConsultasNami.consultar_estoque(
                empresa_id=empresa_id,
                situacao=argumentos.get(
                    "situacao",
                    "resumo"
                ),
                limite_estoque_baixo=(
                    argumentos.get(
                        "limite_estoque_baixo",
                        5
                    )
                ),
                limite=argumentos.get(
                    "limite",
                    30
                ),
            )

            return _sucesso(dados)

        # ======================================
        # RANKING DE FUNCIONÁRIOS
        # ======================================

        if nome == "consultar_ranking_funcionarios":
            if not _somente_gerente(
                usuario
            ):
                return _erro(
                    (
                        "Somente o gerente pode consultar "
                        "o ranking completo da equipe."
                    )
                )

            dados = ConsultasNami.ranking_funcionarios(
                empresa_id=empresa_id,
                periodo=periodo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                limite=argumentos.get(
                    "limite",
                    10
                ),
            )

            return _sucesso(dados)

        # ======================================
        # CAIXA
        # ======================================

        if nome == "consultar_caixa":
            dados = ConsultasNami.resumo_caixa(
                empresa_id
            )

            return _sucesso(dados)

        # ======================================
        # MOVIMENTAÇÕES
        # ======================================

        if nome == "listar_movimentacoes_caixa":
            if not _somente_gerente(
                usuario
            ):
                return _erro(
                    (
                        "Somente o gerente pode consultar "
                        "as movimentações completas do caixa."
                    )
                )

            dados = (
                ConsultasNami.movimentacoes_caixa(
                    empresa_id=empresa_id,
                    limite=argumentos.get(
                        "limite",
                        20
                    ),
                )
            )

            return _sucesso(dados)

        # ======================================
        # VISÃO GERAL
        # ======================================

        if nome == "consultar_visao_geral":
            vendas_hoje = (
                ConsultasNami.resumo_vendas(
                    empresa_id=empresa_id,
                    periodo="hoje",
                    nivel=nivel,
                    usuario_id=usuario_id,
                )
            )

            vendas_mes = (
                ConsultasNami.resumo_vendas(
                    empresa_id=empresa_id,
                    periodo="mes",
                    nivel=nivel,
                    usuario_id=usuario_id,
                )
            )

            estoque = (
                ConsultasNami.consultar_estoque(
                    empresa_id=empresa_id,
                    situacao="resumo",
                    limite_estoque_baixo=5,
                )
            )

            produtos_vendidos = (
                ConsultasNami.produtos_vendidos(
                    empresa_id=empresa_id,
                    periodo="mes",
                    limite=5,
                    ordem="mais_vendidos",
                    nivel=nivel,
                    usuario_id=usuario_id,
                )
            )

            caixa = (
                ConsultasNami.resumo_caixa(
                    empresa_id
                )
            )

            return _sucesso({
                "vendas_hoje": vendas_hoje,
                "vendas_mes": vendas_mes,
                "estoque": estoque,
                "produtos_mais_vendidos": (
                    produtos_vendidos
                ),
                "caixa": caixa,
            })

                # ======================================
        # ADMIN — RESUMO DA PLATAFORMA
        # ======================================

        if nome == "admin_resumo_plataforma":
            if nivel != "master":
                return _erro(
                    (
                        "Somente o administrador master "
                        "pode consultar dados globais."
                    )
                )

            dados = (
                ConsultasAdminNami.resumo_plataforma(
                    nivel=nivel,
                    periodo=periodo,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                )
            )

            return _sucesso(
                dados
            )

        # ======================================
        # ADMIN — LISTAR EMPRESAS
        # ======================================

        if nome == "admin_listar_empresas":
            if nivel != "master":
                return _erro(
                    (
                        "Somente o administrador master "
                        "pode listar todas as empresas."
                    )
                )

            dados = (
                ConsultasAdminNami.listar_empresas(
                    nivel=nivel,
                    busca=argumentos.get(
                        "busca"
                    ),
                    plano=argumentos.get(
                        "plano",
                        "todos"
                    ),
                    status=argumentos.get(
                        "status",
                        "todos"
                    ),
                    emprestimos=argumentos.get(
                        "emprestimos",
                        "todos"
                    ),
                    limite=argumentos.get(
                        "limite",
                        50
                    ),
                )
            )

            return _sucesso(
                dados
            )

        # ======================================
        # ADMIN — EMPRESA ESPECÍFICA
        # ======================================

        if nome == "admin_consultar_empresa":
            if nivel != "master":
                return _erro(
                    (
                        "Somente o administrador master "
                        "pode consultar outra empresa."
                    )
                )

            dados = (
                ConsultasAdminNami.consultar_empresa(
                    nivel=nivel,
                    nome_empresa=argumentos.get(
                        "nome_empresa",
                        ""
                    ),
                    periodo=periodo,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                )
            )

            return _sucesso(
                dados
            )

        # ======================================
        # ADMIN — RANKING DAS EMPRESAS
        # ======================================

        if nome == "admin_ranking_empresas":
            if nivel != "master":
                return _erro(
                    (
                        "Somente o administrador master "
                        "pode comparar empresas."
                    )
                )

            dados = (
                ConsultasAdminNami.ranking_empresas(
                    nivel=nivel,
                    periodo=periodo,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    ordem=argumentos.get(
                        "ordem",
                        "maior_faturamento"
                    ),
                    limite=argumentos.get(
                        "limite",
                        10
                    ),
                )
            )

            return _sucesso(
                dados
            )

        # ======================================
        # ADMIN — EMPRESAS SEM VENDAS
        # ======================================

        if nome == "admin_empresas_sem_vendas":
            if nivel != "master":
                return _erro(
                    (
                        "Somente o administrador master "
                        "pode consultar empresas inativas."
                    )
                )

            dados = (
                ConsultasAdminNami.empresas_sem_vendas(
                    nivel=nivel,
                    dias=argumentos.get(
                        "dias",
                        30
                    ),
                    limite=argumentos.get(
                        "limite",
                        50
                    ),
                )
            )

            return _sucesso(
                dados
            )
        
        logger.warning(
            "Ferramenta desconhecida: %s",
            nome
        )

        return _erro(
            "Ferramenta não autorizada."
        )

    except ValueError as erro:
        return _erro(
            str(erro)
        )

    except Exception:
        logger.exception(
            "Erro na ferramenta da Nami: %s",
            nome
        )

        return _erro(
            (
                "Não foi possível consultar os dados "
                "do sistema neste momento."
            )
        )