"use strict";


const botao = document.getElementById("enviar");
const input = document.getElementById("pergunta");
const chat = document.getElementById("chat");

let enviandoMensagem = false;


/* =========================================================
   SEGURANÇA E FORMATAÇÃO
========================================================= */

function escaparHtml(texto) {
    return String(texto ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatarInline(texto) {
    return texto
        .replace(
            /\*\*(.+?)\*\*/g,
            "<strong>$1</strong>"
        )
        .replace(
            /__(.+?)__/g,
            "<strong>$1</strong>"
        )
        .replace(
            /`([^`]+)`/g,
            "<code>$1</code>"
        );
}


function formatarResposta(texto) {
    let conteudo = String(texto ?? "")
        .replace(/\r\n/g, "\n")
        .replace(/\r/g, "\n")
        .trim();

    /*
     * Alguns modelos retornam marcadores na mesma linha.
     * Aqui forçamos uma quebra antes deles.
     */
    conteudo = conteudo
        .replace(
            /(\*\*)\s*[•]\s*/g,
            "$1\n• "
        )
        .replace(
            /([.!?])\s+[•]\s*/g,
            "$1\n• "
        )
        .replace(
            /\s+(?=\d+\.\s)/g,
            "\n"
        );

    const linhas = conteudo.split("\n");

    const resultado = [];

    let listaAberta = false;

    function fecharLista() {
        if (!listaAberta) {
            return;
        }

        resultado.push("</ul>");
        listaAberta = false;
    }

    linhas.forEach(function (linhaOriginal) {
        const linha = linhaOriginal.trim();

        if (!linha) {
            fecharLista();

            resultado.push(
                '<div class="nami-espaco"></div>'
            );

            return;
        }

        const linhaSegura = formatarInline(
            escaparHtml(linha)
        );

        if (linha.startsWith("### ")) {
            fecharLista();

            resultado.push(
                "<h4>" +
                formatarInline(
                    escaparHtml(
                        linha.slice(4)
                    )
                ) +
                "</h4>"
            );

            return;
        }

        if (linha.startsWith("## ")) {
            fecharLista();

            resultado.push(
                "<h3>" +
                formatarInline(
                    escaparHtml(
                        linha.slice(3)
                    )
                ) +
                "</h3>"
            );

            return;
        }

        if (linha.startsWith("# ")) {
            fecharLista();

            resultado.push(
                "<h2>" +
                formatarInline(
                    escaparHtml(
                        linha.slice(2)
                    )
                ) +
                "</h2>"
            );

            return;
        }

        const itemLista = linha.match(
            /^(?:[-*•]|(\d+)\.)\s+(.+)$/
        );

        if (itemLista) {
            if (!listaAberta) {
                resultado.push(
                    '<ul class="nami-lista">'
                );

                listaAberta = true;
            }

            const textoItem =
                itemLista[2] || "";

            resultado.push(
                "<li>" +
                formatarInline(
                    escaparHtml(textoItem)
                ) +
                "</li>"
            );

            return;
        }

        fecharLista();

        resultado.push(
            "<p>" + linhaSegura + "</p>"
        );
    });

    fecharLista();

    return resultado.join("");
}


/* =========================================================
   ELEMENTOS DAS MENSAGENS
========================================================= */

function criarAvatarNami() {
    const avatar = document.createElement("div");

    avatar.className = "mensagem-avatar";

    const imagem = document.createElement("img");

    imagem.src = "/static/img/mascote-nami.png";
    imagem.alt = "Nami";

    const status = document.createElement("span");

    avatar.appendChild(imagem);
    avatar.appendChild(status);

    return avatar;
}


function adicionarMensagemUsuario(texto) {
    const mensagem = document.createElement("div");

    mensagem.className =
        "mensagem usuario mensagem-dinamica";

    const balao = document.createElement("div");

    balao.className = "balao-usuario";
    balao.textContent = texto;

    mensagem.appendChild(balao);
    chat.appendChild(mensagem);

    rolarChat();
}


function adicionarMensagemNami(texto) {
    const mensagem = document.createElement("div");

    mensagem.className =
        "mensagem ia mensagem-dinamica";

    const avatar = criarAvatarNami();

    const estrutura = document.createElement("div");

    estrutura.className =
        "mensagem-conteudo mensagem-nami-conteudo";

    const identidade =
        document.createElement("div");

    identidade.className =
        "mensagem-identidade";

    const nome = document.createElement("strong");

    nome.textContent = "Nami";

    const etiqueta = document.createElement("span");

    etiqueta.textContent = "Assistente Nexus";

    identidade.appendChild(nome);
    identidade.appendChild(etiqueta);

    const balao = document.createElement("div");

    balao.className =
        "balao-nami mensagem-formatada";

    balao.innerHTML = formatarResposta(texto);

    estrutura.appendChild(identidade);
    estrutura.appendChild(balao);

    mensagem.appendChild(avatar);
    mensagem.appendChild(estrutura);

    chat.appendChild(mensagem);

    rolarChat();

    return mensagem;
}


function adicionarCarregamento() {
    const mensagem = document.createElement("div");

    mensagem.className =
        "mensagem ia mensagem-dinamica nami-carregando";

    mensagem.appendChild(
        criarAvatarNami()
    );

    const estrutura = document.createElement("div");

    estrutura.className =
        "mensagem-conteudo mensagem-nami-conteudo";

    const identidade =
        document.createElement("div");

    identidade.className =
        "mensagem-identidade";

    identidade.innerHTML =
        "<strong>Nami</strong>" +
        "<span>Consultando</span>";

    const balao = document.createElement("div");

    balao.className =
        "balao-nami digitando";

    balao.innerHTML = `
        <span></span>
        <span></span>
        <span></span>
    `;

    estrutura.appendChild(identidade);
    estrutura.appendChild(balao);

    mensagem.appendChild(estrutura);
    chat.appendChild(mensagem);

    rolarChat();

    return mensagem;
}


/* =========================================================
   CONTROLE DA INTERFACE
========================================================= */

function rolarChat() {
    window.requestAnimationFrame(function () {
        chat.scrollTo({
            top: chat.scrollHeight,
            behavior: "smooth"
        });
    });
}


function alterarEstadoEnvio(enviando) {
    enviandoMensagem = enviando;

    botao.disabled = enviando;
    input.disabled = enviando;

    if (enviando) {
        botao.innerHTML = `
            <span>Consultando</span>
            <strong class="spinner-envio"></strong>
        `;
    } else {
        botao.innerHTML = `
            <span>Enviar</span>
            <strong>➜</strong>
        `;
    }
}


/* =========================================================
   ENVIO
========================================================= */

async function enviarMensagem() {
    if (enviandoMensagem) {
        return;
    }

    const texto = input.value.trim();

    if (!texto) {
        input.focus();
        return;
    }

    adicionarMensagemUsuario(texto);

    input.value = "";

    alterarEstadoEnvio(true);

    const carregamento =
        adicionarCarregamento();

    try {
        const respostaHttp = await fetch(
            "/ia/chat",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    mensagem: texto
                })
            }
        );

        const dados = await respostaHttp.json();

        carregamento.remove();

        const resposta =
            dados.resposta ||
            dados.erro ||
            "Não consegui responder agora.";

        adicionarMensagemNami(resposta);

    } catch (erro) {
        carregamento.remove();

        adicionarMensagemNami(
            "Não consegui consultar o sistema agora. " +
            "Tente novamente em alguns instantes."
        );

        console.error(
            "Erro ao consultar a Nami:",
            erro
        );

    } finally {
        alterarEstadoEnvio(false);

        input.focus();
    }
}


/* =========================================================
   EVENTOS
========================================================= */

botao.addEventListener(
    "click",
    enviarMensagem
);


input.addEventListener(
    "keydown",
    function (evento) {
        if (
            evento.key === "Enter" &&
            !evento.shiftKey
        ) {
            evento.preventDefault();

            enviarMensagem();
        }
    }
);


document
    .querySelectorAll("[data-pergunta]")
    .forEach(function (botaoSugestao) {
        botaoSugestao.addEventListener(
            "click",
            function () {
                input.value =
                    botaoSugestao.dataset.pergunta || "";

                input.focus();
            }
        );
    });