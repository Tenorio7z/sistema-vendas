from flask import *
from database import conectar, criar_cursor


def registrar_rotas(app):

    # ==========================================
    # PRODUTOS
    # ==========================================

    @app.route("/produtos", methods=["GET", "POST"])
    def produtos():

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session["empresa_id"]

        # Apenas gerente pode cadastrar
        if request.method == "POST":

            if session["nivel"] == "funcionario":

                flash(
                    "Você não possui permissão para cadastrar produtos",
                    "erro"
                )

                conn.close()

                return redirect("/produtos")

            # ==========================================
            # LIMITE DO PLANO COMUM
            # ==========================================

            if session.get("plano") == "comum":

                cursor.execute("""

                SELECT COUNT(*) as total

                FROM produtos

                WHERE empresa_id = %s

                """, (

                    empresa_id,

                ))

                total_produtos = cursor.fetchone()["total"]

                if total_produtos >= 50:

                    flash(
                        "Seu plano permite no máximo 50 produtos. Faça upgrade para Premium.",
                        "erro"
                    )

                    conn.close()

                    return redirect("/produtos")

            nome = request.form["nome"]
            preco = float(request.form["preco"].replace(",", "."))
            estoque = int(request.form["estoque"])
            codigo_barras = request.form["codigo_barras"]

            cursor.execute("""

            INSERT INTO produtos(

                nome,
                preco,
                estoque,
                codigo_barras,
                empresa_id

            )

            VALUES(%s,%s,%s,%s,%s)

            """, (

                nome,
                preco,
                estoque,
                codigo_barras,
                empresa_id

            ))

            conn.commit()

            flash(
                "Produto cadastrado com sucesso",
                "sucesso"
            )

            cursor.close()
            conn.close()

            return redirect("/produtos")

        cursor.execute("""

        SELECT *

        FROM produtos

        WHERE empresa_id = %s

        ORDER BY id DESC

        """, (

            empresa_id,

        ))

        produtos = cursor.fetchall()

        conn.close()

        return render_template(
            "produtos.html",
            produtos=produtos
        )

    # ==========================================
    # EXCLUIR PRODUTO
    # ==========================================

    @app.route("/excluir_produto/<int:id>")
    def excluir_produto(id):

        if not session.get("logado"):
            return redirect("/")

        if session["nivel"] == "funcionario":

            flash(
                "Você não possui permissão",
                "erro"
            )

            return redirect("/produtos")

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute("""

        DELETE FROM produtos

        WHERE id = %s
        AND empresa_id = %s

        """, (

            id,
            session["empresa_id"]

        ))

        conn.commit()
        conn.close()

        flash(
            "Produto removido",
            "sucesso"
        )

        return redirect("/produtos")

    # ==========================================
    # EDITAR PRODUTO
    # ==========================================

    @app.route("/editar_produto/<int:id>", methods=["GET", "POST"])
    def editar_produto(id):

        if not session.get("logado"):
            return redirect("/")

        if session["nivel"] == "funcionario":

            flash(
                "Você não possui permissão",
                "erro"
            )

            return redirect("/produtos")

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session["empresa_id"]

        if request.method == "POST":

            nome = request.form["nome"]
            preco = float(request.form["preco"].replace(",", "."))
            estoque = int(request.form["estoque"])
            codigo_barras = request.form["codigo_barras"]

            cursor.execute("""

            UPDATE produtos

            SET

                nome = %s,
                preco = %s,
                estoque = %s,
                codigo_barras = %s

            WHERE id = %s
            AND empresa_id = %s

            """, (

                nome,
                preco,
                estoque,
                codigo_barras,
                id,
                empresa_id

            ))

            conn.commit()
            conn.close()

            flash(
                "Produto atualizado",
                "sucesso"
            )

            return redirect("/produtos")

        cursor.execute("""

        SELECT *

        FROM produtos

        WHERE id = %s
        AND empresa_id = %s

        """, (

            id,
            empresa_id

        ))

        produto = cursor.fetchone()

        conn.close()

        return render_template(
            "editar_produto.html",
            produto=produto
        )
