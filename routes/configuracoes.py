from io import BytesIO
import re

from PIL import Image, ImageOps, UnidentifiedImageError
from flask import abort, flash, make_response, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import conectar, criar_cursor

TAMANHO_MAXIMO_IMAGEM = 5 * 1024 * 1024
FORMATOS_IMAGEM_PERMITIDOS = {"JPEG", "PNG", "WEBP"}


def _processar_imagem(arquivo, *, avatar=False):
    if not arquivo or not arquivo.filename:
        return None, None
    dados = arquivo.read(TAMANHO_MAXIMO_IMAGEM + 1)
    if not dados:
        raise ValueError("O arquivo enviado está vazio.")
    if len(dados) > TAMANHO_MAXIMO_IMAGEM:
        raise ValueError("A imagem deve ter no máximo 5 MB.")
    try:
        with Image.open(BytesIO(dados)) as original:
            if original.format not in FORMATOS_IMAGEM_PERMITIDOS:
                raise ValueError("Use uma imagem JPG, PNG ou WEBP.")
            if original.width > 8000 or original.height > 8000 or original.width * original.height > 25000000:
                raise ValueError("A imagem excede as dimensões permitidas.")
            imagem = ImageOps.exif_transpose(original)
            if imagem.mode not in ("RGB", "RGBA"):
                imagem = imagem.convert("RGBA" if "transparency" in imagem.info else "RGB")
            if avatar:
                imagem = ImageOps.fit(imagem, (400, 400), method=Image.Resampling.LANCZOS)
            else:
                imagem.thumbnail((800, 500), Image.Resampling.LANCZOS)
            saida = BytesIO()
            imagem.save(saida, format="WEBP", quality=84, method=6)
            return saida.getvalue(), "image/webp"
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as erro:
        raise ValueError("O arquivo enviado não é uma imagem válida.") from erro


def _resposta_imagem(dados, mime):
    if isinstance(dados, memoryview):
        dados = dados.tobytes()
    resposta = make_response(send_file(BytesIO(dados), mimetype=mime or "image/webp"))
    resposta.headers["Cache-Control"] = "no-store"
    return resposta


def registrar_rotas(app):
    @app.route("/configuracoes", methods=["GET", "POST"])
    def configuracoes():
        if not session.get("logado") or not session.get("usuario_id"):
            return redirect(url_for("login"))
        usuario_id = session["usuario_id"]
        nivel = session.get("nivel")
        empresa_id = session.get("empresa_id")

        if request.method == "POST":
            secao = request.form.get("secao", "")
            if secao == "perfil":
                nome = request.form.get("nome_exibicao", "").strip()
                if not nome:
                    flash("Informe seu nome.", "erro")
                    return redirect(url_for("configuracoes"))
                if len(nome) > 120:
                    flash("O nome deve ter no máximo 120 caracteres.", "erro")
                    return redirect(url_for("configuracoes"))
                try:
                    foto, foto_mime = _processar_imagem(request.files.get("foto"), avatar=True)
                except ValueError as erro:
                    flash(str(erro), "erro")
                    return redirect(url_for("configuracoes"))
                conn = conectar()
                cursor = criar_cursor(conn)
                try:
                    if foto is not None:
                        cursor.execute(
                            "UPDATE usuarios SET nome_exibicao=%s, foto=%s, foto_mime=%s WHERE id=%s",
                            (nome, foto, foto_mime, usuario_id),
                        )
                    elif request.form.get("remover_foto") == "1":
                        cursor.execute(
                            "UPDATE usuarios SET nome_exibicao=%s, foto=NULL, foto_mime=NULL WHERE id=%s",
                            (nome, usuario_id),
                        )
                    else:
                        cursor.execute("UPDATE usuarios SET nome_exibicao=%s WHERE id=%s", (nome, usuario_id))
                    if cursor.rowcount != 1:
                        conn.rollback()
                        flash("Não encontramos sua conta para atualizar.", "erro")
                        return redirect(url_for("configuracoes"))
                    conn.commit()
                    session["nome_exibicao"] = nome
                    flash("Seu perfil foi atualizado.", "sucesso")
                except Exception:
                    conn.rollback()
                    app.logger.exception("Erro ao atualizar perfil do usuário %s.", usuario_id)
                    flash("Não foi possível atualizar seu perfil agora.", "erro")
                finally:
                    cursor.close()
                    conn.close()
                return redirect(url_for("configuracoes"))

            if secao == "senha":
                atual = request.form.get("senha_atual", "")
                nova = request.form.get("nova_senha", "")
                confirmar = request.form.get("confirmar_senha", "")
                if len(nova) < 8:
                    flash("A nova senha deve ter pelo menos 8 caracteres.", "erro")
                    return redirect(url_for("configuracoes"))
                if nova != confirmar:
                    flash("A confirmação da senha não confere.", "erro")
                    return redirect(url_for("configuracoes"))
                conn = conectar()
                cursor = criar_cursor(conn)
                try:
                    cursor.execute("SELECT senha FROM usuarios WHERE id=%s", (usuario_id,))
                    conta = cursor.fetchone()
                    if not conta or not check_password_hash(conta["senha"], atual):
                        flash("A senha atual está incorreta.", "erro")
                        return redirect(url_for("configuracoes"))
                    cursor.execute(
                        "UPDATE usuarios SET senha=%s WHERE id=%s",
                        (generate_password_hash(nova), usuario_id),
                    )
                    conn.commit()
                    flash("Sua senha foi alterada.", "sucesso")
                except Exception:
                    conn.rollback()
                    app.logger.exception("Erro ao alterar senha do usuário %s.", usuario_id)
                    flash("Não foi possível alterar sua senha agora.", "erro")
                finally:
                    cursor.close()
                    conn.close()
                return redirect(url_for("configuracoes"))

            if secao == "empresa":
                if nivel != "gerente" or not empresa_id:
                    abort(403)
                nome = request.form.get("nome_empresa", "").strip()
                telefone = request.form.get("telefone", "").strip()
                email = request.form.get("email", "").strip().lower()
                endereco = request.form.get("endereco", "").strip()
                if not nome:
                    flash("Informe o nome da empresa.", "erro")
                    return redirect(url_for("configuracoes"))
                if len(nome) > 150 or len(telefone) > 30 or len(email) > 180 or len(endereco) > 255:
                    flash("Revise os campos: um deles excede o tamanho permitido.", "erro")
                    return redirect(url_for("configuracoes"))
                if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                    flash("Informe um e-mail válido para a empresa.", "erro")
                    return redirect(url_for("configuracoes"))
                try:
                    logo, logo_mime = _processar_imagem(request.files.get("logo"))
                except ValueError as erro:
                    flash(str(erro), "erro")
                    return redirect(url_for("configuracoes"))
                conn = conectar()
                cursor = criar_cursor(conn)
                try:
                    if logo is not None:
                        cursor.execute(
                            """
                            UPDATE empresa SET nome=%s, telefone=%s, email=%s, endereco=%s,
                                logo=%s, logo_mime=%s WHERE id=%s
                            """,
                            (nome, telefone or None, email or None, endereco or None, logo, logo_mime, empresa_id),
                        )
                    elif request.form.get("remover_logo") == "1":
                        cursor.execute(
                            """
                            UPDATE empresa SET nome=%s, telefone=%s, email=%s, endereco=%s,
                                logo=NULL, logo_mime=NULL WHERE id=%s
                            """,
                            (nome, telefone or None, email or None, endereco or None, empresa_id),
                        )
                    else:
                        cursor.execute(
                            "UPDATE empresa SET nome=%s, telefone=%s, email=%s, endereco=%s WHERE id=%s",
                            (nome, telefone or None, email or None, endereco or None, empresa_id),
                        )
                    conn.commit()
                    flash("Os dados da empresa foram atualizados.", "sucesso")
                except Exception:
                    conn.rollback()
                    app.logger.exception("Erro ao atualizar empresa %s.", empresa_id)
                    flash("Não foi possível atualizar os dados da empresa agora.", "erro")
                finally:
                    cursor.close()
                    conn.close()
                return redirect(url_for("configuracoes"))

            flash("Ação de configuração inválida.", "erro")
            return redirect(url_for("configuracoes"))

        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                SELECT usuario, nome_exibicao,
                       CASE WHEN foto IS NOT NULL THEN TRUE ELSE FALSE END AS possui_foto
                FROM usuarios WHERE id=%s
                """,
                (usuario_id,),
            )
            perfil = cursor.fetchone()
            if not perfil:
                session.clear()
                return redirect(url_for("login"))
            empresa = None
            if nivel == "gerente" and empresa_id:
                cursor.execute(
                    """
                    SELECT nome, telefone, email, endereco,
                           CASE WHEN logo IS NOT NULL THEN TRUE ELSE FALSE END AS possui_logo
                    FROM empresa WHERE id=%s
                    """,
                    (empresa_id,),
                )
                empresa = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()
        session["nome_exibicao"] = perfil.get("nome_exibicao") or perfil["usuario"]
        return render_template("configuracoes.html", perfil=perfil, empresa=empresa)

    @app.get("/configuracoes/foto")
    def configuracoes_foto_usuario():
        if not session.get("logado") or not session.get("usuario_id"):
            abort(401)
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute("SELECT foto, foto_mime FROM usuarios WHERE id=%s", (session["usuario_id"],))
            registro = cursor.fetchone()
            if not registro or not registro.get("foto"):
                abort(404)
            return _resposta_imagem(registro["foto"], registro.get("foto_mime"))
        finally:
            cursor.close()
            conn.close()

    @app.get("/configuracoes/logo")
    def configuracoes_logo_empresa():
        if not session.get("logado") or session.get("nivel") != "gerente" or not session.get("empresa_id"):
            abort(404)
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute("SELECT logo, logo_mime FROM empresa WHERE id=%s", (session["empresa_id"],))
            registro = cursor.fetchone()
            if not registro or not registro.get("logo"):
                abort(404)
            return _resposta_imagem(registro["logo"], registro.get("logo_mime"))
        finally:
            cursor.close()
            conn.close()
