from services.ia.memory import memory

from services.ia.openai_client import (
    perguntar_openai,
)

from services.ia.prompts import (
    PROMPT_SISTEMA,
)

from services.ia.fast_router import (
    tentar_resposta_rapida,
)


class AssistenteNexus:

    def responder(
        self,
        mensagem,
        usuario,
    ):
        empresa_id = usuario.get(
            "empresa_id"
        )

        usuario_id = usuario.get(
            "usuario_id"
        )

        if not empresa_id:
            raise ValueError(
                "Sessao sem empresa."
            )

        if not usuario_id:
            raise ValueError(
                "Sessao sem usuario."
            )

        mensagem = str(
            mensagem or ""
        ).strip()

        if not mensagem:
            return "Digite uma pergunta."

        if len(mensagem) > 1000:
            return (
                "A mensagem deve ter no maximo "
                "1.000 caracteres."
            )

        chave_memoria = (
            empresa_id,
            usuario_id,
        )

        historico = memory.get(
            chave_memoria
        )

        resposta = tentar_resposta_rapida(
            mensagem=mensagem,
            usuario=usuario,
        )

        if resposta is None:
            resposta = perguntar_openai(
                mensagem=mensagem,
                contexto=PROMPT_SISTEMA,
                historico=historico,
                usuario=usuario,
            )

        if not resposta:
            resposta = (
                "Nao consegui responder "
                "essa pergunta agora."
            )

        memory.add_turn(
            chave_memoria,
            mensagem,
            resposta,
        )

        return resposta

    def limpar_memoria(
        self,
        usuario,
    ):
        chave_memoria = (
            usuario.get("empresa_id"),
            usuario.get("usuario_id"),
        )

        memory.clear(
            chave_memoria
        )


assistente = AssistenteNexus()
