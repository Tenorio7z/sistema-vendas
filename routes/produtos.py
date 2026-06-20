from flask import *
from database import conectar


def registrar_rotas(app):

    # ==========================================
    # PRODUTOS
    # ==========================================

    @app.route("/produtos", methods=["GET", "POST"])
    def produtos():

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = conn.cursor()

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

                WHERE empresa_id = ?

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
            preco = request.form["preco"]
            estoque = request.form["estoque"]
            codigo_barras = request.form["codigo_barras"]

            cursor.execute("""

            INSERT INTO produtos(

                nome,
                preco,
                estoque,
                codigo_barras,
                empresa_id

            )

            VALUES(?,?,?,?,?)

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

        cursor.execute("""

        SELECT *

        FROM produtos

        WHERE empresa_id = ?

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
        cursor = conn.cursor()

        cursor.execute("""

        DELETE FROM produtos

        WHERE id = ?
        AND empresa_id = ?

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
        cursor = conn.cursor()

        empresa_id = session["empresa_id"]

        if request.method == "POST":

            nome = request.form["nome"]
            preco = request.form["preco"]
            estoque = request.form["estoque"]
            codigo_barras = request.form["codigo_barras"]

            cursor.execute("""

            UPDATE produtos

            SET

                nome = ?,
                preco = ?,
                estoque = ?,
                codigo_barras = ?

            WHERE id = ?
            AND empresa_id = ?

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

        WHERE id = ?
        AND empresa_id = ?

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