from flask import *
from database import conectar, criar_cursor
from werkzeug.security import generate_password_hash
from datetime import datetime

def registrar_rotas(app):

    @app.route("/perfis", methods=["GET", "POST"])
    def perfis():
        
        print("ROTA PERFIS EXECUTADA")
        
        if not session.get("logado"):
            return redirect("/")

        if session["nivel"] != "gerente":
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        empresa_id = session["empresa_id"]

        if request.method == "POST":

            usuario = request.form["usuario"]

            senha = generate_password_hash(
                request.form["senha"]
            )

            cursor.execute(
                """
                SELECT id
                FROM usuarios
                WHERE usuario = %s
                """,
                (usuario,)
            )

            usuario_existente = cursor.fetchone()

            if usuario_existente:

                conn.close()

                flash(
                    "Já existe um usuário com esse nome.",
                    "erro"
                )

                return redirect("/perfis")

                
            cursor.execute("""

                SELECT COUNT(*) as total

                FROM usuarios

                WHERE empresa_id = %s
                AND nivel = 'funcionario'

                """, (

                    empresa_id,

                ))

            total_funcionarios = cursor.fetchone()["total"]

            if total_funcionarios >= 2:

                    conn.close()

                    flash(
                        "Seu plano permite apenas 2 funcionários. Faça upgrade para Premium.",
                        "erro"
                    )

                    return redirect("/perfis")

            

            senha = generate_password_hash(
                request.form["senha"]
            )

            comissao = request.form.get("comissao")

            print("USUARIO:", usuario)
            print("COMISSAO RECEBIDA:", comissao)

            if not comissao:

                conn.close()

                flash(
                    "Comissão não enviada pelo formulário",
                    "erro"
                )

                return redirect("/perfis")

            comissao = float(comissao)

            sql = """

            INSERT INTO usuarios(

                usuario,
                senha,
                nivel,
                status,
                empresa_id,
                comissao

            )

            VALUES(%s,%s,%s,%s,%s,%s)

            """

            valores = (

                usuario,
                senha,
                "funcionario",
                "ativo",
                empresa_id,
                comissao

            )

            print("SQL:")
            print(sql)

            print("VALORES:")
            print(valores)

            print("TOTAL DE VALORES:")
            print(len(valores))

            cursor.execute(
                sql,
                valores
            )

            conn.commit()

            flash(
                "Funcionário cadastrado",
                "sucesso"
            )

        cursor.execute(
            """

            SELECT

                usuarios.*,

                COALESCE(
                    SUM(vendas.valor),
                    0
                ) as total_vendido,

                COUNT(vendas.id) as total_vendas,

                MAX(vendas.data_venda) as ultima_venda

            FROM usuarios

            LEFT JOIN vendas
            ON vendas.usuario_id = usuarios.id

            WHERE usuarios.empresa_id = %s
            AND usuarios.nivel = 'funcionario'

            GROUP BY usuarios.id

            ORDER BY usuarios.id DESC

            """,
            (
                empresa_id,
            ),
        )

        funcionarios = cursor.fetchall()
        
        funcionarios_formatados = []

        for funcionario in funcionarios:

            total_vendido = funcionario["total_vendido"]

            comissao_percentual = funcionario["comissao"]

            valor_comissao = (
                total_vendido *
                comissao_percentual
            ) / 100

            funcionario = dict(funcionario)

            funcionario["valor_comissao"] = valor_comissao

            funcionarios_formatados.append(
                funcionario
            )

        funcionarios = funcionarios_formatados
        
        conn.close()

        return render_template(
            "perfis.html",
            funcionarios=funcionarios
        )
    
    @app.route("/historico_funcionario/<int:id>")
    def historico_funcionario(id):

        if not session.get("logado"):
            return jsonify([])

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute("""

        SELECT
            vendas.*,
            produtos.nome AS produto_nome

        FROM vendas

        LEFT JOIN produtos
            ON produtos.id = vendas.produto_id

        WHERE vendas.usuario_id = %s
        AND vendas.empresa_id = %s

        ORDER BY vendas.id DESC

        LIMIT 50

        """, (

            id,
            session["empresa_id"]

        ))

        vendas = cursor.fetchall()

        conn.close()

        resultado = []

        for venda in vendas:

            resultado.append({

                "produto": venda["produto_nome"],
                "quantidade": venda["quantidade"],
                "valor": venda["valor"],
                "pagamento": venda["pagamento"],
                "data": venda["data_venda"]

            })

        return jsonify(resultado)
    
    
    @ app.route("/funcionario/<int:id>")
    def dashboard_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute("""
            SELECT *
            FROM usuarios
            WHERE id = %s
            AND empresa_id = %s
        """, (id, session["empresa_id"]))

        funcionario = cursor.fetchone()

        if not funcionario:
            conn.close()
            flash("Funcionário não encontrado", "erro")
            return redirect("/perfis")

        # segurança contra NULL
        comissao = float(funcionario["comissao"] or 0)

        # ==========================================
        # HOJE
        # ==========================================
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM vendas
            WHERE usuario_id = %s
            AND DATE(data_venda) = CURRENT_DATE
        """, (id,))
        vendas_hoje = cursor.fetchone()["total"]

        # ==========================================
        # MÊS
        # ==========================================
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM vendas
            WHERE usuario_id = %s
            AND DATE_TRUNC('month', data_venda) = DATE_TRUNC('month', CURRENT_DATE)
        """, (id,))
        vendas_mes = cursor.fetchone()["total"]

        # ==========================================
        # ANO
        # ==========================================
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM vendas
            WHERE usuario_id = %s
            AND DATE_TRUNC('year', data_venda) = DATE_TRUNC('year', CURRENT_DATE)
        """, (id,))
        vendas_ano = cursor.fetchone()["total"]

        # ==========================================
        # TOTAL
        # ==========================================
        cursor.execute("""
            SELECT COALESCE(SUM(valor), 0) AS total
            FROM vendas
            WHERE usuario_id = %s
        """, (id,))
        vendas_total = cursor.fetchone()["total"]

        # ==========================================
        # COMISSÕES
        # ==========================================
        comissao_hoje = (vendas_hoje * comissao) / 100
        comissao_mes = (vendas_mes * comissao) / 100
        comissao_ano = (vendas_ano * comissao) / 100
        comissao_total = (vendas_total * comissao) / 100

        conn.close()

        return render_template(
            "dashboard_funcionario.html",
            funcionario=funcionario,
            vendas_hoje=vendas_hoje,
            vendas_mes=vendas_mes,
            vendas_ano=vendas_ano,
            vendas_total=vendas_total,
            comissao_hoje=comissao_hoje,
            comissao_mes=comissao_mes,
            comissao_ano=comissao_ano,
            comissao_total=comissao_total
        )
    
    
    @app.route("/bloquear_funcionario/<int:id>")
    def bloquear_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "gerente":
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute(
            """

        UPDATE usuarios

        SET status = %s

        WHERE id = %s
        AND empresa_id = %s

        """,
            ("bloqueado", id, session["empresa_id"]),
        )

        conn.commit()
        conn.close()

        flash("Funcionário bloqueado", "sucesso")

        return redirect("/perfis")





    @app.route("/liberar_funcionario/<int:id>")
    def liberar_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "gerente":
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute(
            """

        UPDATE usuarios

        SET status = %s

        WHERE id = %s
        AND empresa_id = %s
        
        
        """,
            ("ativo", id, session["empresa_id"]),
        )

        print("ID:", id)
        print("EMPRESA DA SESSAO:", session["empresa_id"])
        print("LINHAS ALTERADAS:", cursor.rowcount)
        
        conn.commit()
        conn.close()

        flash("Funcionário liberado", "sucesso")

        return redirect("/perfis")




    @app.route("/excluir_funcionario/<int:id>")
    def excluir_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "gerente":
            return redirect("/dashboard")

        conn = conectar()
        cursor = criar_cursor(conn)

        cursor.execute(
            """

        DELETE FROM usuarios

        WHERE id = %s
        AND empresa_id = %s
        AND nivel = 'funcionario'

        """,
            (id, session["empresa_id"]),
        )
        print("ID:", id)
        print("EMPRESA DA SESSAO:", session["empresa_id"])
        print("LINHAS EXCLUIDAS:", cursor.rowcount)
        
        conn.commit()
        conn.close()

        flash("Funcionário excluído", "sucesso")

        return redirect("/perfis")

    