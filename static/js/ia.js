const botao = document.getElementById("enviar");
const input = document.getElementById("pergunta");
const chat = document.getElementById("chat");

function adicionarMensagem(texto, autor) {
    const mensagem = document.createElement("div");
    mensagem.className = `mensagem ${autor}`;
    mensagem.textContent = texto;
    chat.appendChild(mensagem);
    chat.scrollTop = chat.scrollHeight;
    return mensagem;
}

async function enviarMensagem() {
    const texto = input.value.trim();
    if (!texto || botao.disabled) return;

    adicionarMensagem(texto, "usuario");
    input.value = "";
    botao.disabled = true;
    input.disabled = true;
    const carregando = adicionarMensagem("Consultando o Nexus...", "ia carregando");

    try {
        const resposta = await fetch("/ia/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({mensagem: texto})
        });
        const dados = await resposta.json().catch(() => ({}));
        carregando.remove();

        if (!resposta.ok) {
            throw new Error(dados.resposta || dados.erro || "Não foi possível enviar a mensagem.");
        }
        adicionarMensagem(dados.resposta || "A IA não retornou uma resposta.", "ia");
    } catch (erro) {
        carregando.remove();
        adicionarMensagem(erro.message || "Erro de conexão. Tente novamente.", "ia erro");
    } finally {
        botao.disabled = false;
        input.disabled = false;
        input.focus();
    }
}

botao.addEventListener("click", enviarMensagem);
input.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey) {
        evento.preventDefault();
        enviarMensagem();
    }
});
