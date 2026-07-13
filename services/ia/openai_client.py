import json
import logging
import os

from openai import OpenAI

from services.ia.tools import (
    FERRAMENTAS,
    executar_ferramenta,
)


logger = logging.getLogger(__name__)


INSTRUCOES_FERRAMENTAS = """
Voce é a assistente Nami, integrada a um sistema de vendas.

REGRAS OBRIGATORIAS:

- Responda sempre em portugues do Brasil.
- Seja claro, objetivo e profissional.
- Nunca invente produtos, vendas, valores ou quantidades.
- Para perguntas sobre dados da empresa, use uma ferramenta.
- Nunca responda dados empresariais usando apenas memoria.
- Nunca diga que executou uma consulta se nao usou uma ferramenta.
- Nao solicite empresa_id ou usuario_id ao usuario.
- O servidor identifica a empresa pela sessao autenticada.
- Nao tente executar SQL.
- Nao revele nomes internos de ferramentas.
- Se uma consulta nao encontrar dados, informe isso claramente.
- Formate valores monetarios no padrao brasileiro.
- Prefira respostas curtas e organizadas.
- Nao use blocos HTML.

ESCOLHA DAS FERRAMENTAS:

- Perguntas sobre um produto especifico:
  use buscar_produto.

- Perguntas sobre faturamento ou quantidade de vendas:
  use consultar_vendas.

- Perguntas sobre quais produtos ou itens foram vendidos:
  use listar_produtos_vendidos_mes.

- Perguntas sobre estoque baixo, acabando ou sem estoque:
  use consultar_estoque.

- Perguntas sobre quantidade de produtos cadastrados:
  use consultar_total_produtos.

- Perguntas sobre o produto mais vendido:
  use consultar_produto_mais_vendido.

- Perguntas sobre o caixa:
  use consultar_caixa.

- Perguntas sobre resumo ou visao geral:
  use consultar_visao_geral.

Quando receber o resultado de uma ferramenta, transforme os dados
em uma resposta natural. Nao mostre JSON ao usuario.
"""


def _criar_cliente():
    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY nao configurada."
        )

    return OpenAI(
        api_key=api_key,
        timeout=30.0,
        max_retries=2,
    )


def _montar_entrada(
    mensagem,
    historico,
):
    entrada = []

    for item in historico or []:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if (
            role not in ("user", "assistant")
            or not content
        ):
            continue

        entrada.append({
            "role": role,
            "content": str(content),
        })

    entrada.append({
        "role": "user",
        "content": mensagem,
    })

    return entrada


def perguntar_openai(
    mensagem,
    contexto,
    historico=None,
    empresa_id=None,
):
    try:
        client = _criar_cliente()

    except RuntimeError:
        logger.exception(
            "OpenAI nao configurada."
        )

        return (
            "A Assistente Nami ainda nao foi "
            "configurada. Contate o administrador."
        )

    instrucoes = (
        INSTRUCOES_FERRAMENTAS
        + "\n\n"
        + str(contexto or "")
    )

    entrada = _montar_entrada(
        mensagem,
        historico,
    )

    try:
        resposta = client.responses.create(
            model=os.getenv(
                "OPENAI_MODEL",
                "gpt-5-mini",
            ),
            instructions=instrucoes,
            input=entrada,
            tools=FERRAMENTAS,
            tool_choice="auto",
            max_output_tokens=600,
        )

        # Limita a quantidade de rodadas para impedir loops.
        for _ in range(3):
            chamadas = [
                item
                for item in resposta.output
                if item.type == "function_call"
            ]

            if not chamadas:
                texto = (
                    resposta.output_text
                    or ""
                ).strip()

                if texto:
                    return texto

                return (
                    "Nao consegui produzir uma "
                    "resposta para essa pergunta."
                )

            # Preserva toda a saida do modelo, inclusive
            # itens de raciocinio exigidos pelos modelos GPT.
            entrada += resposta.output

            for chamada in chamadas:
                try:
                    argumentos = json.loads(
                        chamada.arguments
                        or "{}"
                    )

                except json.JSONDecodeError:
                    argumentos = {}

                resultado = executar_ferramenta(
                    chamada.name,
                    argumentos,
                    empresa_id,
                )

                entrada.append({
                    "type": "function_call_output",
                    "call_id": chamada.call_id,
                    "output": resultado,
                })

            resposta = client.responses.create(
                model=os.getenv(
                    "OPENAI_MODEL",
                    "gpt-5-mini",
                ),
                instructions=instrucoes,
                input=entrada,
                tools=FERRAMENTAS,
                tool_choice="auto",
                max_output_tokens=600,
            )

        logger.warning(
            "Limite de chamadas de ferramentas atingido."
        )

        return (
            "Nao consegui concluir a consulta. "
            "Tente reformular a pergunta."
        )

    except Exception:
        logger.exception(
            "Falha ao consultar a OpenAI."
        )

        return (
            "Desculpe, nao consegui consultar "
            "a Assistente Nami agora. "
            "Tente novamente em instantes."
        )