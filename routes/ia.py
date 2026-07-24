import logging

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
)

from services.ia.chat import assistente


logger = logging.getLogger(__name__)

ia_bp = Blueprint(
    "ia",
    __name__,
)


def _usuario_sessao():
    return {
        "empresa_id": session.get(
            "empresa_id"
        ),
        "usuario_id": session.get(
            "usuario_id"
        ),
        "usuario": session.get(
            "usuario"
        ),
        "nivel": str(
            session.get("nivel")
            or "funcionario"
        ).strip().lower(),
        "emprestimos_ativo": bool(
            session.get(
                "emprestimos_ativo",
                False,
            )
        ),
    }


@ia_bp.route("/ia")
def pagina_ia():
    if not session.get("logado"):
        return redirect("/")

    return render_template(
        "ia/chat.html"
    )


@ia_bp.route(
    "/ia/chat",
    methods=["POST"],
)
def chat():
    if not session.get("logado"):
        return jsonify({
            "erro": "Usuário não autenticado.",
        }), 401

    dados = request.get_json(
        silent=True
    )

    if not isinstance(dados, dict):
        return jsonify({
            "resposta": "Nenhum dado recebido.",
        }), 400

    pergunta = str(
        dados.get("mensagem") or ""
    ).strip()

    if not pergunta:
        return jsonify({
            "resposta": "Digite uma pergunta.",
        }), 400

    if len(pergunta) > 1000:
        return jsonify({
            "resposta": (
                "A mensagem deve ter no máximo "
                "1.000 caracteres."
            ),
        }), 400

    usuario = _usuario_sessao()

    if not usuario["empresa_id"]:
        return jsonify({
            "resposta": (
                "A empresa não foi identificada "
                "na sessão."
            ),
        }), 401

    if not usuario["usuario_id"]:
        return jsonify({
            "resposta": (
                "O usuário não foi identificado "
                "na sessão."
            ),
        }), 401

    try:
        resposta = assistente.responder(
            pergunta,
            usuario,
        )

        return jsonify({
            "resposta": resposta,
        })

    except ValueError as erro:
        return jsonify({
            "resposta": str(erro),
        }), 400

    except Exception:
        logger.exception(
            "Erro ao processar mensagem da Nami."
        )

        return jsonify({
            "resposta": (
                "Desculpe, ocorreu um erro ao "
                "consultar a Nami."
            ),
        }), 500


@ia_bp.route(
    "/ia/chat/limpar",
    methods=["POST"],
)
def limpar_chat():
    if not session.get("logado"):
        return jsonify({
            "erro": "Usuário não autenticado.",
        }), 401

    assistente.limpar_memoria(
        _usuario_sessao()
    )

    return jsonify({
        "ok": True,
    })
