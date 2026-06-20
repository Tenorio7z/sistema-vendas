from flask import *
from database import conectar
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
        cursor = conn.cursor()

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
                WHERE usuario = ?
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

                WHERE empresa_id = ?
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

            VALUES(?,?,?,?,?,?)

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

                IFNULL(
                    SUM(vendas.valor),
                    0
                ) as total_vendido,

                COUNT(vendas.id) as total_vendas,

                MAX(vendas.data_venda) as ultima_venda

            FROM usuarios

            LEFT JOIN vendas
            ON vendas.usuario_id = usuarios.id

            WHERE usuarios.empresa_id = ?
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
        cursor = conn.cursor()

        cursor.execute("""

        SELECT
            vendas.*,
            produtos.nome AS produto_nome

        FROM vendas

        LEFT JOIN produtos
            ON produtos.id = vendas.produto_id

        WHERE vendas.usuario_id = ?
        AND vendas.empresa_id = ?

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
    
    
    @app.route("/funcionario/<int:id>")
    def dashboard_funcionario(id):

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT *

        FROM usuarios

        WHERE id = ?
        AND empresa_id = ?

        """, (

            id,
            session["empresa_id"]

        ))

        funcionario = cursor.fetchone()

    
        mes_atual = datetime.now().strftime("%Y-%m")
        ano_atual = datetime.now().strftime("%Y")
        
        if not funcionario:

            conn.close()

            flash(
                "Funcionário não encontrado",
                "erro"
            )

            return redirect("/perfis")


        # ==========================================
        # FATURAMENTO HOJE
        # ==========================================

        cursor.execute("""
        SELECT
            IFNULL(SUM(valor),0) AS total
        FROM vendas
        WHERE usuario_id = ?
        AND DATE(data_venda) = DATE('now')
        """, (id,))

        vendas_hoje = cursor.fetchone()["total"]


        # ==========================================
        # FATURAMENTO MÊS
        # ==========================================

        cursor.execute("""
        SELECT
            IFNULL(SUM(valor),0) AS total
        FROM vendas
        WHERE usuario_id = ?
        AND strftime('%Y-%m', data_venda) = ?
        """, (id, mes_atual))

        vendas_mes = cursor.fetchone()["total"]


        # ==========================================
        # FATURAMENTO ANO
        # ==========================================

        cursor.execute("""
        SELECT
            IFNULL(SUM(valor),0) AS total
        FROM vendas
        WHERE usuario_id = ?
        AND strftime('%Y', data_venda) = ?
        """, (id, ano_atual))

        vendas_ano = cursor.fetchone()["total"]


        # ==========================================
        # FATURAMENTO TOTAL
        # ==========================================

        cursor.execute("""
        SELECT
            IFNULL(SUM(valor),0) AS total
        FROM vendas
        WHERE usuario_id = ?
        """, (id,))

        vendas_total = cursor.fetchone()["total"]


        # ==========================================
        # COMISSÕES
        # ==========================================

        comissao = funcionario["comissao"]

        comissao_hoje = (
            vendas_hoje * comissao
        ) / 100

        comissao_mes = (
            vendas_mes * comissao
        ) / 100

        comissao_ano = (
            vendas_ano * comissao
        ) / 100

        comissao_total = (
            vendas_total * comissao
        ) / 100
        

        print("HOJE:", vendas_hoje)
        print("MES:", vendas_mes)
        print("ANO:", vendas_ano)
        print("TOTAL:", vendas_total)
        
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
        cursor = conn.cursor()

        cursor.execute(
            """

        UPDATE usuarios

        SET status = ?

        WHERE id = ?
        AND empresa_id = ?

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
        cursor = conn.cursor()

        cursor.execute(
            """

        UPDATE usuarios

        SET status = ?

        WHERE id = ?
        AND empresa_id = ?
        
        
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
        cursor = conn.cursor()

        cursor.execute(
            """

        DELETE FROM usuarios

        WHERE id = ?
        AND empresa_id = ?
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

    