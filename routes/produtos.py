from io import BytesIO

import psycopg2

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
)

from database import (
    conectar,
    criar_cursor,
)


TIPOS_IMAGEM_PERMITIDOS = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

TAMANHO_MAXIMO_IMAGEM = (
    2 * 1024 * 1024
)


def _validar_imagem(
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

    if mimetype not in TIPOS_IMAGEM_PERMITIDOS:
        raise ValueError(
            "Use uma imagem JPG, PNG ou WEBP."
        )

    imagem = arquivo.read(
        TAMANHO_MAXIMO_IMAGEM + 1
    )

    if not imagem:
        raise ValueError(
            "O arquivo de imagem está vazio."
        )

    if len(imagem) > TAMANHO_MAXIMO_IMAGEM:
        raise ValueError(
            "A imagem deve ter no máximo 2 MB."
        )

    # Validação básica da assinatura do arquivo.
    assinaturas_validas = {
        "image/jpeg": (
            imagem.startswith(b"\xff\xd8\xff")
        ),

        "image/png": (
            imagem.startswith(
                b"\x89PNG\r\n\x1a\n"
            )
        ),

        "image/webp": (
            len(imagem) >= 12
            and imagem[:4] == b"RIFF"
            and imagem[8:12] == b"WEBP"
        ),
    }

    if not assinaturas_validas.get(
        mimetype,
        False
    ):
        raise ValueError(
            (
                "O conteúdo do arquivo não corresponde "
                "a uma imagem válida."
            )
        )

    return imagem, mimetype


def registrar_rotas(app):

    # ==========================================
    # PRODUTOS
    # ==========================================

    @app.route(
        "/produtos",
        methods=[
            "GET",
            "POST",
        ]
    )
    def produtos():

        if not session.get("logado"):
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            session.clear()
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            if request.method == "POST":

                if (
                    session.get("nivel")
                    == "funcionario"
                ):
                    flash(
                        (
                            "Você não possui permissão "
                            "para cadastrar produtos."
                        ),
                        "erro"
                    )

                    return redirect("/produtos")

                # ==================================
                # LIMITE DO PLANO COMUM
                # ==================================

                if (
                    session.get("plano")
                    == "comum"
                ):
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS total
                        FROM produtos
                        WHERE empresa_id = %s
                        """,
                        (
                            empresa_id,
                        )
                    )

                    total_produtos = (
                        cursor.fetchone()["total"]
                    )

                    if total_produtos >= 50:
                        flash(
                            (
                                "Seu plano permite no máximo "
                                "50 produtos. Faça upgrade "
                                "para o Premium."
                            ),
                            "erro"
                        )

                        return redirect("/produtos")

                nome = request.form.get(
                    "nome",
                    ""
                ).strip()

                preco_texto = request.form.get(
                    "preco",
                    ""
                ).strip()

                estoque_texto = request.form.get(
                    "estoque",
                    ""
                ).strip()

                codigo_barras = request.form.get(
                    "codigo_barras",
                    ""
                ).strip()

                if not nome:
                    flash(
                        "Informe o nome do produto.",
                        "erro"
                    )

                    return redirect("/produtos")

                try:
                    preco = float(
                        preco_texto.replace(
                            ",",
                            "."
                        )
                    )

                    estoque = int(
                        estoque_texto
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    flash(
                        (
                            "Informe um preço e um estoque "
                            "válidos."
                        ),
                        "erro"
                    )

                    return redirect("/produtos")

                if preco < 0:
                    flash(
                        (
                            "O preço não pode ser "
                            "negativo."
                        ),
                        "erro"
                    )

                    return redirect("/produtos")

                if estoque < 0:
                    flash(
                        (
                            "O estoque não pode ser "
                            "negativo."
                        ),
                        "erro"
                    )

                    return redirect("/produtos")

                arquivo_imagem = request.files.get(
                    "imagem"
                )

                try:
                    imagem, imagem_mime = (
                        _validar_imagem(
                            arquivo_imagem
                        )
                    )

                except ValueError as erro:
                    flash(
                        str(erro),
                        "erro"
                    )

                    return redirect("/produtos")

                cursor.execute(
                    """
                    INSERT INTO produtos (
                        nome,
                        preco,
                        estoque,
                        codigo_barras,
                        empresa_id,
                        imagem,
                        imagem_mime
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        nome,
                        preco,
                        estoque,
                        codigo_barras,
                        empresa_id,
                        (
                            psycopg2.Binary(imagem)
                            if imagem
                            else None
                        ),
                        imagem_mime,
                    )
                )

                conn.commit()

                flash(
                    (
                        "Produto cadastrado "
                        "com sucesso."
                    ),
                    "sucesso"
                )

                return redirect("/produtos")

            # Não carregamos o BYTEA nesta consulta,
            # evitando deixar a página pesada.
            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    preco,
                    estoque,
                    codigo_barras,
                    empresa_id,

                    CASE
                        WHEN imagem IS NOT NULL
                        THEN TRUE
                        ELSE FALSE
                    END AS possui_imagem

                FROM produtos

                WHERE empresa_id = %s

                ORDER BY id DESC
                """,
                (
                    empresa_id,
                )
            )

            produtos_cadastrados = (
                cursor.fetchall()
            )

            return render_template(
                "produtos.html",
                produtos=produtos_cadastrados,
            )

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # IMAGEM DO PRODUTO
    # ==========================================

    @app.route(
        "/produto_imagem/<int:id>"
    )
    def produto_imagem(id):

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
                    imagem,
                    imagem_mime

                FROM produtos

                WHERE id = %s
                  AND empresa_id = %s

                LIMIT 1
                """,
                (
                    id,
                    empresa_id,
                )
            )

            produto = cursor.fetchone()

            if (
                not produto
                or not produto.get("imagem")
            ):
                abort(404)

            imagem = produto["imagem"]

            if isinstance(
                imagem,
                memoryview
            ):
                imagem = imagem.tobytes()

            return send_file(
                BytesIO(imagem),
                mimetype=(
                    produto.get("imagem_mime")
                    or "image/jpeg"
                ),
                max_age=86400,
                conditional=True,
            )

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # EXCLUIR PRODUTO
    # ==========================================

    @app.route(
        "/excluir_produto/<int:id>"
    )
    def excluir_produto(id):

        if not session.get("logado"):
            return redirect("/")

        if (
            session.get("nivel")
            == "funcionario"
        ):
            flash(
                "Você não possui permissão.",
                "erro"
            )

            return redirect("/produtos")

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                DELETE FROM produtos
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    id,
                    session["empresa_id"],
                )
            )

            if cursor.rowcount == 0:
                conn.rollback()

                flash(
                    "Produto não encontrado.",
                    "erro"
                )

                return redirect("/produtos")

            conn.commit()

            flash(
                "Produto removido.",
                "sucesso"
            )

            return redirect("/produtos")

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # EDITAR PRODUTO
    # ==========================================

    @app.route(
        "/editar_produto/<int:id>",
        methods=[
            "GET",
            "POST",
        ]
    )
    def editar_produto(id):

        if not session.get("logado"):
            return redirect("/")

        if (
            session.get("nivel")
            == "funcionario"
        ):
            flash(
                "Você não possui permissão.",
                "erro"
            )

            return redirect("/produtos")

        empresa_id = session.get(
            "empresa_id"
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            if request.method == "POST":

                nome = request.form.get(
                    "nome",
                    ""
                ).strip()

                preco_texto = request.form.get(
                    "preco",
                    ""
                ).strip()

                estoque_texto = request.form.get(
                    "estoque",
                    ""
                ).strip()

                codigo_barras = request.form.get(
                    "codigo_barras",
                    ""
                ).strip()

                if not nome:
                    flash(
                        "Informe o nome do produto.",
                        "erro"
                    )

                    return redirect(
                        f"/editar_produto/{id}"
                    )

                try:
                    preco = float(
                        preco_texto.replace(
                            ",",
                            "."
                        )
                    )

                    estoque = int(
                        estoque_texto
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    flash(
                        (
                            "Informe um preço e um "
                            "estoque válidos."
                        ),
                        "erro"
                    )

                    return redirect(
                        f"/editar_produto/{id}"
                    )

                if (
                    preco < 0
                    or estoque < 0
                ):
                    flash(
                        (
                            "Preço e estoque não podem "
                            "ser negativos."
                        ),
                        "erro"
                    )

                    return redirect(
                        f"/editar_produto/{id}"
                    )

                cursor.execute(
                    """
                    UPDATE produtos

                    SET
                        nome = %s,
                        preco = %s,
                        estoque = %s,
                        codigo_barras = %s

                    WHERE id = %s
                      AND empresa_id = %s
                    """,
                    (
                        nome,
                        preco,
                        estoque,
                        codigo_barras,
                        id,
                        empresa_id,
                    )
                )

                if cursor.rowcount == 0:
                    conn.rollback()

                    flash(
                        "Produto não encontrado.",
                        "erro"
                    )

                    return redirect("/produtos")

                conn.commit()

                flash(
                    "Produto atualizado.",
                    "sucesso"
                )

                return redirect("/produtos")

            # Também evita carregar a imagem inteira
            # na página de edição.
            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    preco,
                    estoque,
                    codigo_barras,
                    empresa_id,

                    CASE
                        WHEN imagem IS NOT NULL
                        THEN TRUE
                        ELSE FALSE
                    END AS possui_imagem

                FROM produtos

                WHERE id = %s
                  AND empresa_id = %s

                LIMIT 1
                """,
                (
                    id,
                    empresa_id,
                )
            )

            produto = cursor.fetchone()

            if not produto:
                flash(
                    "Produto não encontrado.",
                    "erro"
                )

                return redirect("/produtos")

            return render_template(
                "editar_produto.html",
                produto=produto,
            )

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()