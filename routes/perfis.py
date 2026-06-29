from flask import *
from database import conectar, criar_cursor
from werkzeug.security import generate_password_hash


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

            cursor.execute(
                """
                SELECT id
                FROM usuarios
                WHERE usuario = %s
                AND empresa_id = %s
                """,
                (usuario, empresa_id)
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

            comissao = float(
                comissao.replace(",", ".")
            )

            sql = """

            INSERT INTO usuarios(

                usuario,
                senha,
                nivel,
                status,
                empresa_id,
                comissao,
                data_venda

            )

            VALUES(%s,%s,%s,%s,%s,%s, NOW())

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

            conn.close()

            return redirect("/perfis")

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
            AND vendas.empresa_id = usuarios.empresa_id

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

            total_vendido = float(
                funcionario["total_vendido"] or 0
            )

            comissao_percentual = float(
                funcionario["comissao"] or 0
            )

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
                "valor": float(venda["valor"]),
                "pagamento": venda["pagamento"],
                "data": str(venda["data_venda"])

            })

        return jsonify(resultado)
    
    
    @app.route("/funcionario/<int:id>")
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
        comissao = float(funcionario.get("comissao") or 0)

        print("FUNCIONARIO ID:", id)
        print("EMPRESA SESSAO:", session["empresa_id"])
        
        cursor.execute("""
            SELECT
                COALESCE(SUM(valor) FILTER (
                    WHERE data_venda >= CURRENT_DATE
                    AND data_venda < CURRENT_DATE + INTERVAL '1 day'
                ), 0) AS vendas_hoje,

                COALESCE(SUM(valor) FILTER (
                    WHERE data_venda >= date_trunc('month', CURRENT_DATE)
                    AND data_venda < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month'
                ), 0) AS vendas_mes,

                COALESCE(SUM(valor) FILTER (
                    WHERE data_venda >= date_trunc('year', CURRENT_DATE)
                    AND data_venda < date_trunc('year', CURRENT_DATE) + INTERVAL '1 year'
                ), 0) AS vendas_ano,

                COALESCE(SUM(valor), 0) AS vendas_total
            FROM vendas
            WHERE usuario_id = %s
            AND empresa_id = %s
        """, (id, session["empresa_id"]))

        row = cursor.fetchone()

        if not row:
            row = {
                "vendas_hoje": 0,
                "vendas_mes": 0,
                "vendas_ano": 0,
                "vendas_total": 0
            }

        vendas_hoje = float(row["vendas_hoje"] or 0)
        vendas_mes = float(row["vendas_mes"] or 0)
        vendas_ano = float(row["vendas_ano"] or 0)
        vendas_total = float(row["vendas_total"] or 0)

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

    