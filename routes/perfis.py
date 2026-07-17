from datetime import date
from io import BytesIO

import psycopg2

from PIL import (
    Image,
    ImageOps,
    UnidentifiedImageError,
)

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
)

from werkzeug.security import (
    generate_password_hash,
)

from database import (
    conectar,
    criar_cursor,
)

from services.gestao_equipe_service import (
    GestaoEquipeService,
)


# ==========================================
# CONFIGURAÇÃO DA FOTO
# ==========================================

TIPOS_FOTO_PERMITIDOS = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

TAMANHO_MAXIMO_FOTO = 5 * 1024 * 1024
TAMANHO_FOTO_FUNCIONARIO = 400


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def _gerente_logado():
    return (
        session.get("logado")
        and session.get("nivel") == "gerente"
        and session.get("empresa_id")
    )


def _competencia_formulario():
    return (
        request.form.get("competencia")
        or request.args.get("competencia")
        or date.today().strftime("%Y-%m")
    )


def _voltar_perfis(
    competencia=None,
):
    competencia = (
        competencia
        or _competencia_formulario()
    )

    return redirect(
        f"/perfis?competencia={competencia}"
    )


def _processar_foto_funcionario(
    arquivo,
):
    if (
        not arquivo
        or not arquivo.filename
    ):
        return None, None

    mimetype = str(
        arquivo.mimetype or ""
    ).lower()

    if mimetype not in TIPOS_FOTO_PERMITIDOS:
        raise ValueError(
            "Use uma foto JPG, PNG ou WEBP."
        )

    dados = arquivo.read(
        TAMANHO_MAXIMO_FOTO + 1
    )

    if not dados:
        raise ValueError(
            "A foto enviada está vazia."
        )

    if len(dados) > TAMANHO_MAXIMO_FOTO:
        raise ValueError(
            "A foto original deve ter no máximo 5 MB."
        )

    try:
        with Image.open(
            BytesIO(dados)
        ) as imagem:

            imagem = ImageOps.exif_transpose(
                imagem
            )

            if imagem.mode not in (
                "RGB",
                "RGBA",
            ):
                imagem = imagem.convert(
                    "RGB"
                )

            imagem = ImageOps.fit(
                imagem,
                (
                    TAMANHO_FOTO_FUNCIONARIO,
                    TAMANHO_FOTO_FUNCIONARIO,
                ),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

            saida = BytesIO()

            imagem.save(
                saida,
                format="WEBP",
                quality=82,
                method=6,
                optimize=True,
            )

            return (
                saida.getvalue(),
                "image/webp",
            )

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as erro:
        raise ValueError(
            "O arquivo enviado não é uma foto válida."
        ) from erro


def registrar_rotas(app):

    # ==========================================
    # DASHBOARD E CADASTRO
    # ==========================================

    @app.route(
        "/perfis",
        methods=["GET", "POST"],
    )
    def perfis():

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        empresa_id = session["empresa_id"]

        competencia = (
            request.form.get("competencia")
            or request.args.get("competencia")
            or date.today().strftime("%Y-%m")
        )

        # ======================================
        # CADASTRAR FUNCIONÁRIO
        # ======================================

        if request.method == "POST":

            usuario = request.form.get(
                "usuario",
                "",
            ).strip()

            senha_texto = request.form.get(
                "senha",
                "",
            )

            comissao_texto = request.form.get(
                "comissao",
                "",
            ).strip()

            cargo = request.form.get(
                "cargo",
                "Funcionário",
            ).strip()

            salario_base = request.form.get(
                "salario_base",
                "0",
            )

            dia_pagamento = request.form.get(
                "dia_pagamento",
                "5",
            )

            data_admissao = (
                request.form.get(
                    "data_admissao"
                )
                or None
            )

            arquivo_foto = request.files.get(
                "foto"
            )

            if not usuario:
                flash(
                    "Informe o usuário do funcionário.",
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            if len(senha_texto) < 6:
                flash(
                    (
                        "A senha deve possuir pelo "
                        "menos 6 caracteres."
                    ),
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            try:
                comissao = float(
                    comissao_texto.replace(
                        ",",
                        ".",
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                flash(
                    "Informe uma comissão válida.",
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            if not 0 <= comissao <= 100:
                flash(
                    (
                        "A comissão deve ficar entre "
                        "0% e 100%."
                    ),
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            try:
                salario_validado = (
                    GestaoEquipeService._decimal(
                        salario_base
                    )
                )

                dia_validado = (
                    GestaoEquipeService._inteiro(
                        dia_pagamento,
                        5,
                    )
                )

                if salario_validado < 0:
                    raise ValueError(
                        "O salário não pode ser negativo."
                    )

                if not 1 <= dia_validado <= 31:
                    raise ValueError(
                        (
                            "O dia de pagamento deve "
                            "ficar entre 1 e 31."
                        )
                    )

                foto, foto_mime = (
                    _processar_foto_funcionario(
                        arquivo_foto
                    )
                )

            except ValueError as erro:
                flash(
                    str(erro),
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            cargo = (
                cargo
                or "Funcionário"
            )[:100]

            conn = conectar()
            cursor = criar_cursor(conn)

            try:
                # Bloqueia a empresa enquanto verifica
                # o limite de funcionários.
                cursor.execute(
                    """
                    SELECT
                        LOWER(
                            COALESCE(
                                plano,
                                'comum'
                            )
                        ) AS plano

                    FROM empresa

                    WHERE id = %s

                    LIMIT 1

                    FOR UPDATE
                    """,
                    (
                        empresa_id,
                    ),
                )

                empresa = cursor.fetchone()

                if not empresa:
                    raise ValueError(
                        "Empresa não encontrada."
                    )

                plano_atual = empresa["plano"]

                session["plano"] = plano_atual

                cursor.execute(
                    """
                    SELECT id

                    FROM usuarios

                    WHERE LOWER(usuario) = LOWER(%s)

                    LIMIT 1
                    """,
                    (
                        usuario,
                    ),
                )

                if cursor.fetchone():
                    raise ValueError(
                        (
                            "Já existe um usuário "
                            "com esse nome."
                        )
                    )

                # Somente o plano comum possui limite.
                if plano_atual == "comum":
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS total

                        FROM usuarios

                        WHERE empresa_id = %s
                          AND nivel = 'funcionario'
                        """,
                        (
                            empresa_id,
                        ),
                    )

                    total_funcionarios = (
                        cursor.fetchone()["total"]
                    )

                    if total_funcionarios >= 2:
                        raise ValueError(
                            (
                                "O plano Comum permite no "
                                "máximo 2 funcionários. "
                                "Faça upgrade para Premium."
                            )
                        )

                senha_hash = generate_password_hash(
                    senha_texto
                )

                cursor.execute(
                    """
                    INSERT INTO usuarios (
                        usuario,
                        senha,
                        nivel,
                        status,
                        empresa_id,
                        comissao,
                        foto,
                        foto_mime
                    )
                    VALUES (
                        %s,
                        %s,
                        'funcionario',
                        'ativo',
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    RETURNING id
                    """,
                    (
                        usuario,
                        senha_hash,
                        empresa_id,
                        comissao,
                        (
                            psycopg2.Binary(foto)
                            if foto
                            else None
                        ),
                        foto_mime,
                    ),
                )

                funcionario_id = (
                    cursor.fetchone()["id"]
                )

                cursor.execute(
                    """
                    INSERT INTO funcionarios_config (
                        empresa_id,
                        usuario_id,
                        cargo,
                        salario_base,
                        dia_pagamento,
                        data_admissao
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        empresa_id,
                        funcionario_id,
                        cargo,
                        salario_validado,
                        dia_validado,
                        data_admissao,
                    ),
                )

                # Usuário e dados profissionais
                # são confirmados juntos.
                conn.commit()

            except ValueError as erro:
                conn.rollback()

                flash(
                    str(erro),
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            except Exception:
                conn.rollback()

                app.logger.exception(
                    "Erro ao cadastrar funcionário."
                )

                flash(
                    (
                        "Não foi possível cadastrar o "
                        "funcionário. Nenhum dado foi salvo."
                    ),
                    "erro",
                )

                return _voltar_perfis(
                    competencia
                )

            finally:
                cursor.close()
                conn.close()

            flash(
                "Funcionário cadastrado com sucesso.",
                "sucesso",
            )

            return _voltar_perfis(
                competencia
            )

        # ======================================
        # DADOS DO DASHBOARD
        # ======================================

        try:
            resumo = (
                GestaoEquipeService.resumo_equipe(
                    empresa_id=empresa_id,
                    competencia=competencia,
                )
            )

            resultado_funcionarios = (
                GestaoEquipeService.listar_funcionarios(
                    empresa_id=empresa_id,
                    competencia=competencia,
                )
            )

            funcionarios = (
                resultado_funcionarios[
                    "funcionarios"
                ]
            )

            funcionarios_formatados = []

            for funcionario in funcionarios:

                item = dict(
                    funcionario
                )

                item["comissao"] = item.get(
                    "percentual_comissao",
                    0,
                )

                item["total_vendido"] = item.get(
                    "faturamento",
                    0,
                )

                item["total_vendas"] = item.get(
                    "registros_venda",
                    0,
                )

                item["valor_comissao"] = item.get(
                    "comissao_gerada",
                    0,
                )

                funcionarios_formatados.append(
                    item
                )

            historico = (
                GestaoEquipeService.historico_pagamentos(
                    empresa_id=empresa_id,
                    limite=20,
                )
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

            return redirect("/dashboard")

        except Exception:
            app.logger.exception(
                "Erro ao carregar dashboard da equipe."
            )

            flash(
                (
                    "Não foi possível carregar o "
                    "dashboard da equipe."
                ),
                "erro",
            )

            return redirect("/dashboard")

        return render_template(
            "perfis.html",
            funcionarios=funcionarios_formatados,
            resumo=resumo,
            historico_folha=historico,
            competencia=competencia,
            periodo_inicio=(
                resultado_funcionarios[
                    "periodo_inicio"
                ]
            ),
            periodo_fim=(
                resultado_funcionarios[
                    "periodo_fim"
                ]
            ),
        )

    # ==========================================
    # FOTO DO FUNCIONÁRIO
    # ==========================================

    @app.route(
        "/foto_funcionario/<int:id>"
    )
    def foto_funcionario(id):

        if not session.get("logado"):
            abort(401)

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            abort(401)

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    foto,
                    foto_mime

                FROM usuarios

                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'

                LIMIT 1
                """,
                (
                    id,
                    empresa_id,
                ),
            )

            funcionario = cursor.fetchone()

            if (
                not funcionario
                or not funcionario.get("foto")
            ):
                abort(404)

            foto = funcionario["foto"]

            if isinstance(
                foto,
                memoryview,
            ):
                foto = foto.tobytes()

            resposta = send_file(
                BytesIO(foto),
                mimetype=(
                    funcionario.get("foto_mime")
                    or "image/webp"
                ),
                max_age=604800,
                conditional=True,
                download_name=(
                    f"funcionario-{id}.webp"
                ),
            )

            resposta.cache_control.private = True
            resposta.cache_control.max_age = 604800

            return resposta

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # CONFIGURAR FUNCIONÁRIO
    # ==========================================

    @app.route(
        "/funcionario/configurar/<int:id>",
        methods=["POST"],
    )
    def configurar_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        competencia = (
            _competencia_formulario()
        )

        try:
            GestaoEquipeService.salvar_configuracao(
                empresa_id=session["empresa_id"],
                usuario_id=id,
                cargo=request.form.get(
                    "cargo",
                    "Funcionário",
                ),
                salario_base=request.form.get(
                    "salario_base",
                    "0",
                ),
                dia_pagamento=request.form.get(
                    "dia_pagamento",
                    "5",
                ),
                data_admissao=(
                    request.form.get(
                        "data_admissao"
                    )
                    or None
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
            )

            flash(
                "Dados profissionais atualizados.",
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao configurar funcionário."
            )

            flash(
                (
                    "Não foi possível atualizar "
                    "o funcionário."
                ),
                "erro",
            )

        return _voltar_perfis(
            competencia
        )

    # ==========================================
    # GERAR FOLHA
    # ==========================================

    @app.route(
        "/folha/gerar/<int:id>",
        methods=["POST"],
    )
    def gerar_folha_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        competencia = (
            _competencia_formulario()
        )

        try:
            resultado = (
                GestaoEquipeService.gerar_folha(
                    empresa_id=(
                        session["empresa_id"]
                    ),
                    usuario_id=id,
                    registrado_por=(
                        session["usuario_id"]
                    ),
                    competencia=competencia,
                    bonus=request.form.get(
                        "bonus",
                        "0",
                    ),
                    descontos=request.form.get(
                        "descontos",
                        "0",
                    ),
                    observacoes=request.form.get(
                        "observacoes"
                    ),
                )
            )

            folha = resultado["folha"]

            flash(
                (
                    "Folha gerada com sucesso. "
                    f"Total: R$ {folha['valor_total']}"
                ),
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao gerar folha."
            )

            flash(
                (
                    "Não foi possível gerar "
                    "a folha de pagamento."
                ),
                "erro",
            )

        return _voltar_perfis(
            competencia
        )

    # ==========================================
    # PAGAR FOLHA
    # ==========================================

    @app.route(
        "/folha/pagar/<int:id>",
        methods=["POST"],
    )
    def pagar_folha(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        competencia = (
            _competencia_formulario()
        )

        registrar_no_caixa = (
            request.form.get(
                "registrar_no_caixa"
            ) == "1"
        )

        try:
            folha = (
                GestaoEquipeService.registrar_pagamento(
                    empresa_id=(
                        session["empresa_id"]
                    ),
                    folha_id=id,
                    registrado_por=(
                        session["usuario_id"]
                    ),
                    forma_pagamento=(
                        request.form.get(
                            "forma_pagamento",
                            "pix",
                        )
                    ),
                    registrar_no_caixa=(
                        registrar_no_caixa
                    ),
                    observacoes=request.form.get(
                        "observacoes"
                    ),
                )
            )

            flash(
                (
                    "Pagamento registrado. "
                    f"Total: R$ {folha['valor_total']}"
                ),
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao pagar folha."
            )

            flash(
                (
                    "Não foi possível registrar "
                    "o pagamento."
                ),
                "erro",
            )

        return _voltar_perfis(
            competencia
        )

    # ==========================================
    # HISTÓRICO DA FOLHA
    # ==========================================

    @app.route("/folha/historico")
    def historico_folha():

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        usuario_id = request.args.get(
            "usuario_id",
            type=int,
        )

        try:
            pagamentos = (
                GestaoEquipeService.historico_pagamentos(
                    empresa_id=session["empresa_id"],
                    usuario_id=usuario_id,
                    limite=300,
                )
            )

        except Exception:
            app.logger.exception(
                "Erro ao consultar histórico da folha."
            )

            flash(
                (
                    "Não foi possível carregar "
                    "o histórico da folha."
                ),
                "erro",
            )

            return redirect("/perfis")

        return render_template(
            "historico_folha.html",
            pagamentos=pagamentos,
        )

    # ==========================================
    # DASHBOARD INDIVIDUAL
    # ==========================================

    @app.route("/funcionario/<int:id>")
    def dashboard_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT id

                FROM usuarios

                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'

                LIMIT 1
                """,
                (
                    id,
                    session["empresa_id"],
                ),
            )

            funcionario = cursor.fetchone()

            if not funcionario:
                flash(
                    "Funcionário não encontrado.",
                    "erro",
                )

                return redirect("/perfis")

        finally:
            cursor.close()
            conn.close()

        return redirect(
            f"/painel-funcionario/{id}"
        )

    # ==========================================
    # BLOQUEAR FUNCIONÁRIO
    # ==========================================

    @app.route(
        "/bloquear_funcionario/<int:id>",
        methods=["POST"],
    )
    def bloquear_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE usuarios

                SET status = 'bloqueado'

                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'
                """,
                (
                    id,
                    session["empresa_id"],
                ),
            )

            if cursor.rowcount == 0:
                conn.rollback()

                flash(
                    "Funcionário não encontrado.",
                    "erro",
                )

                return redirect("/perfis")

            conn.commit()

            flash(
                "Funcionário bloqueado.",
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao bloquear funcionário."
            )

            flash(
                "Não foi possível bloquear o funcionário.",
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect("/perfis")

    # ==========================================
    # LIBERAR FUNCIONÁRIO
    # ==========================================

    @app.route(
        "/liberar_funcionario/<int:id>",
        methods=["POST"],
    )
    def liberar_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE usuarios

                SET status = 'ativo'

                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'
                """,
                (
                    id,
                    session["empresa_id"],
                ),
            )

            if cursor.rowcount == 0:
                conn.rollback()

                flash(
                    "Funcionário não encontrado.",
                    "erro",
                )

                return redirect("/perfis")

            conn.commit()

            flash(
                "Funcionário liberado.",
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao liberar funcionário."
            )

            flash(
                "Não foi possível liberar o funcionário.",
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect("/perfis")

    # ==========================================
    # EXCLUIR FUNCIONÁRIO
    # ==========================================

    @app.route(
        "/excluir_funcionario/<int:id>",
        methods=["POST"],
    )
    def excluir_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if not _gerente_logado():
            return redirect("/dashboard")

        empresa_id = session["empresa_id"]

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT id

                FROM usuarios

                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'

                LIMIT 1

                FOR UPDATE
                """,
                (
                    id,
                    empresa_id,
                ),
            )

            funcionario = cursor.fetchone()

            if not funcionario:
                flash(
                    "Funcionário não encontrado.",
                    "erro",
                )

                return redirect("/perfis")

            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1

                    FROM folha_pagamentos

                    WHERE usuario_id = %s
                      AND empresa_id = %s
                ) AS possui_historico
                """,
                (
                    id,
                    empresa_id,
                ),
            )

            possui_historico = (
                cursor.fetchone()[
                    "possui_historico"
                ]
            )

            if possui_historico:
                flash(
                    (
                        "Este funcionário possui histórico "
                        "financeiro e não pode ser excluído. "
                        "Bloqueie o acesso para preservar "
                        "as folhas de pagamento."
                    ),
                    "erro",
                )

                return redirect("/perfis")

            cursor.execute(
                """
                DELETE FROM usuarios

                WHERE id = %s
                  AND empresa_id = %s
                  AND nivel = 'funcionario'
                """,
                (
                    id,
                    empresa_id,
                ),
            )

            if cursor.rowcount == 0:
                conn.rollback()

                flash(
                    "Funcionário não encontrado.",
                    "erro",
                )

                return redirect("/perfis")

            conn.commit()

            flash(
                "Funcionário excluído.",
                "sucesso",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao excluir funcionário."
            )

            flash(
                (
                    "Não foi possível excluir o funcionário. "
                    "Use a opção de bloquear acesso."
                ),
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect("/perfis")