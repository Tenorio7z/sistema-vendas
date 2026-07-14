from flask import Blueprint, render_template, request, jsonify, session, redirect

from services.ia.chat import assistente

ia_bp = Blueprint("ia", __name__)


@ia_bp.route("/ia")
def pagina_ia():

    if not session.get("logado"):
        return redirect("/")

    return render_template("ia/chat.html")


@ia_bp.route("/ia/chat", methods=["POST"])
def chat():

    if not session.get("logado"):

        return jsonify({"erro": "Usuário não autenticado."}), 401

    dados = request.get_json(silent=True)

    if not dados:

        return jsonify({"resposta": "Nenhum dado recebido."}), 400

    pergunta = dados.get("mensagem", "").strip()

    if not pergunta:

        return jsonify({"resposta": "Digite uma pergunta."})

    if len(pergunta) > 1000:
        return (
            jsonify({"resposta": "A mensagem deve ter no máximo 1.000 caracteres."}),
            400,
        )

    usuario = {
        "empresa_id": session.get("empresa_id"),
        "usuario_id": session.get("usuario_id"),
        "usuario": session.get("usuario"),
        "nivel": session.get("nivel"),
        "emprestimos_ativo": session.get("emprestimos_ativo", False),
    }

    try:

        resposta = assistente.responder(pergunta, usuario)

        return jsonify({"resposta": resposta})

    except Exception as e:

        print("Erro na IA:", e)

        return (
            jsonify(
                {
                    "resposta": (
                        "Desculpe, ocorreu um erro ao consultar o Assistente Nexus."
                    )
                }
            ),
            500,
        )


@ia_bp.route("/ia/chat/limpar", methods=["POST"])
def limpar_chat():
    if not session.get("logado"):
        return jsonify({"erro": "Usuário não autenticado."}), 401

    assistente.limpar_memoria(
        {
            "empresa_id": session.get("empresa_id"),
            "usuario_id": session.get("usuario_id"),
        }
    )
    return jsonify({"ok": True})
