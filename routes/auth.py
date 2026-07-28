import os
import time

import psycopg2.extras

from flask import (
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
    session,
)

from werkzeug.security import check_password_hash

from database import conectar
from services.login_token_service import LoginTokenService


_login_persistente_indisponivel_ate = 0.0


def _preencher_sessao(usuario):
    session.clear()

    session["logado"] = True
    session["usuario_id"] = usuario["id"]
    session["usuario"] = usuario["usuario"]
    session["nivel"] = usuario["nivel"]
    session["empresa_id"] = usuario.get("empresa_id")
    session["plano"] = usuario.get("plano") or "comum"

    session["emprestimos_ativo"] = bool(
        usuario.get("emprestimos_ativo", False)
    )


def _endereco_ip():
    encaminhado = request.headers.get(
        "X-Forwarded-For",
        ""
    )

    if encaminhado:
        return encaminhado.split(",")[0].strip()

    return request.remote_addr or ""


def _cookie_seguro():
    configuracao = os.getenv(
        "COOKIE_SECURE",
        ""
    ).strip().lower()

    if configuracao in (
        "1",
        "true",
        "sim",
        "yes",
        "on",
    ):
        return True

    if configuracao in (
        "0",
        "false",
        "nao",
        "não",
        "no",
        "off",
    ):
        return False

    # No Render, a conexão externa é HTTPS.
    if request.headers.get(
        "X-Forwarded-Proto",
        ""
    ).lower() == "https":
        return True

    return request.is_secure


def _salvar_cookie(
    response,
    token,
):
    response.set_cookie(
        LoginTokenService.COOKIE_NAME,
        token,
        max_age=(
            LoginTokenService.DURACAO_DIAS
            * 24
            * 60
            * 60
        ),
        httponly=True,
        secure=_cookie_seguro(),
        samesite="Lax",
        path="/",
    )

    return response


def _remover_cookie(response):
    response.delete_cookie(
        LoginTokenService.COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_cookie_seguro(),
        samesite="Lax",
    )

    return response


def registrar_rotas(app):

    # ==========================================
    # RESTAURAÇÃO AUTOMÁTICA DO LOGIN
    # ==========================================

    @app.before_request
    def restaurar_login_persistente():
        global _login_persistente_indisponivel_ate

        if session.get("logado"):
            return None

        token = request.cookies.get(
            LoginTokenService.COOKIE_NAME
        )

        if not token:
            return None

        if (
            time.monotonic()
            < _login_persistente_indisponivel_ate
        ):
            return None

        try:
            usuario = LoginTokenService.autenticar(
                token
            )

        except (
            psycopg2.InterfaceError,
            psycopg2.OperationalError,
        ) as erro:
            _login_persistente_indisponivel_ate = (
                time.monotonic() + 30
            )

            app.logger.warning(
                "Banco indisponível ao restaurar login: %s",
                erro,
            )

            return None

        if not usuario:
            g.remover_login_token = True
            return None

        _preencher_sessao(usuario)

        return None

    @app.after_request
    def remover_cookie_invalido(response):
        if getattr(
            g,
            "remover_login_token",
            False
        ):
            _remover_cookie(response)

        return response

    # ==========================================
    # LOGIN
    # ==========================================

    @app.route(
        "/",
        methods=["GET", "POST"]
    )
    def login():
        if session.get("logado"):
            return redirect("/dashboard")

        if request.method == "POST":
            usuario_informado = request.form.get(
                "usuario",
                ""
            ).strip()

            senha = request.form.get(
                "senha",
                ""
            )

            manter_conectado = True

            conn = None
            cursor = None
            usuario = None

            try:
                conn = conectar()

                cursor = conn.cursor(
                    cursor_factory=(
                        psycopg2.extras.RealDictCursor
                    )
                )

                cursor.execute(
                    """
                    SELECT
                        u.id,
                        u.usuario,
                        u.senha,
                        u.nivel,
                        u.empresa_id,
                        u.status,

                        e.nome AS empresa_nome,
                        e.plano,

                        COALESCE(
                            e.emprestimos_ativo,
                            FALSE
                        ) AS emprestimos_ativo

                    FROM usuarios u

                    LEFT JOIN empresa e
                        ON e.id = u.empresa_id

                    WHERE LOWER(u.usuario) = LOWER(%s)

                    LIMIT 1
                    """,
                    (
                        usuario_informado,
                    )
                )

                usuario = cursor.fetchone()

            except (
                psycopg2.InterfaceError,
                psycopg2.OperationalError,
            ) as erro:
                app.logger.warning(
                    "Banco indisponível durante o login: %s",
                    erro,
                )

                flash(
                    (
                        "O banco de dados está temporariamente "
                        "indisponível. Tente novamente em instantes."
                    ),
                    "erro",
                )

                return (
                    render_template("login.html"),
                    503,
                )

            finally:
                if cursor is not None:
                    cursor.close()

                if conn is not None:
                    conn.close()

            if usuario:
                usuario_bloqueado = (
                    usuario.get("nivel") != "master"
                    and usuario.get("status") == "bloqueado"
                )

                if usuario_bloqueado:
                    flash(
                        "Usuário bloqueado. Consulte o suporte.",
                        "erro"
                    )

                    return redirect("/")

                senha_correta = check_password_hash(
                    usuario["senha"],
                    senha
                )

                if senha_correta:
                    _preencher_sessao(usuario)

                    response = make_response(
                        redirect("/dashboard")
                    )

                    if manter_conectado:
                        try:
                            token = LoginTokenService.criar(
                                usuario_id=usuario["id"],
                                user_agent=request.headers.get(
                                    "User-Agent",
                                    ""
                                ),
                                endereco_ip=_endereco_ip(),
                            )

                            _salvar_cookie(
                                response,
                                token
                            )

                        except Exception as erro:
                            # O login comum continua funcionando
                            # mesmo se o token não puder ser criado.
                            app.logger.exception(
                                "Erro ao criar token persistente: %s",
                                erro
                            )

                    else:
                        token_anterior = request.cookies.get(
                            LoginTokenService.COOKIE_NAME
                        )

                        if token_anterior:
                            LoginTokenService.revogar(
                                token_anterior
                            )

                        _remover_cookie(response)

                    return response

            flash(
                "Usuário ou senha incorretos.",
                "erro"
            )

        return render_template(
            "login.html"
        )

    # ==========================================
    # LOGOUT
    # ==========================================

    @app.route("/logout")
    def logout():
        token = request.cookies.get(
            LoginTokenService.COOKIE_NAME
        )

        if token:
            LoginTokenService.revogar(
                token
            )

        session.clear()

        response = make_response(
            redirect("/")
        )

        _remover_cookie(response)

        return response
