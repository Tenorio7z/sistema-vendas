from flask import *
from database import conectar

from werkzeug.security import (
    generate_password_hash
)

def registrar_rotas(app):

    # ==========================================
    # ADMIN MASTER
    # ==========================================

    @app.route("/admin", methods=["GET", "POST"])
    def admin():

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "master":
            return redirect("/dashboard")

        conn = conectar()
        cursor = conn.cursor()

        if request.method == "POST":

            nome_empresa = request.form["empresa"]
            usuario = request.form["usuario"]
            plano = request.form["plano"]
            
            senha = generate_password_hash(
                request.form["senha"]
            )

            cursor.execute("""

            INSERT INTO empresa(

            nome,
            plano

            )

            VALUES(?,?)

            """, (

                nome_empresa,
                plano
            ))

            empresa_id = cursor.lastrowid

            cursor.execute("""

            INSERT INTO usuarios(

                usuario,
                senha,
                nivel,
                empresa_id,
                status

            )

            VALUES(?,?,?,?,?)

            """, (

                usuario,
                senha,
                "gerente",
                empresa_id,
                "ativo"

            ))

            conn.commit()

            flash(
                "Empresa cadastrada",
                "sucesso"
            )

        # ==========================================
        # EMPRESAS
        # ==========================================

        cursor.execute("""

        SELECT

            usuarios.id,
            usuarios.usuario,
            usuarios.status,

            empresa.nome,
            empresa.plano,
            empresa.id as empresa_id,

            (
                SELECT COUNT(*)
                FROM produtos
                WHERE produtos.empresa_id = empresa.id
            ) as total_produtos,

            (
                SELECT COUNT(*)
                FROM vendas
                WHERE vendas.empresa_id = empresa.id
            ) as total_vendas,

            (
                SELECT COUNT(*)
                FROM usuarios u
                WHERE u.empresa_id = empresa.id
            ) as total_usuarios

        FROM usuarios

        INNER JOIN empresa
        ON usuarios.empresa_id = empresa.id

        WHERE usuarios.nivel = 'gerente'

        ORDER BY usuarios.id DESC

        """)

        empresas = cursor.fetchall()
        
       

        # ==========================================
        # ESTATÍSTICAS GERAIS
        # ==========================================

        total_empresas = len(empresas)

        cursor.execute("""

        SELECT COUNT(*) as total

        FROM produtos

        """)

        total_produtos = cursor.fetchone()["total"]

        cursor.execute("""

        SELECT COUNT(*) as total

        FROM vendas

        """)

        total_vendas = cursor.fetchone()["total"]

        cursor.execute("""

        SELECT COUNT(*) as total

        FROM usuarios

        WHERE nivel = 'gerente'

        """)

        total_usuarios = cursor.fetchone()["total"]

        conn.close()

        return render_template(

            "admin.html",

            empresas=empresas,

            total_empresas=total_empresas,

            total_produtos=total_produtos,

            total_vendas=total_vendas,

            total_usuarios=total_usuarios

        )
        
            # ==========================================
    # BLOQUEAR USUÁRIO
    # ==========================================

    @app.route("/bloquear_usuario/<int:id>")
    def bloquear_usuario(id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "master":
            return redirect("/dashboard")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        UPDATE usuarios

        SET status = ?

        WHERE id = ?

        """, (

            "bloqueado",
            id

        ))

        conn.commit()
        conn.close()

        flash(
            "Usuário bloqueado",
            "sucesso"
        )

        return redirect("/admin")


    # ==========================================
    # LIBERAR USUÁRIO
    # ==========================================

    @app.route("/liberar_usuario/<int:id>")
    def liberar_usuario(id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "master":
            return redirect("/dashboard")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        UPDATE usuarios

        SET status = ?

        WHERE id = ?

        """, (

            "ativo",
            id

        ))

        conn.commit()
        conn.close()

        flash(
            "Usuário liberado",
            "sucesso"
        )

        return redirect("/admin")


    # ==========================================
    # EXCLUIR EMPRESA
    # ==========================================

    @app.route("/excluir_empresa/<int:id>")
    def excluir_empresa(id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "master":
            return redirect("/dashboard")

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""

        SELECT empresa_id

        FROM usuarios

        WHERE id = ?

        """, (id,))

        usuario = cursor.fetchone()

        if usuario:

            empresa_id = usuario["empresa_id"]

            cursor.execute("""

            DELETE FROM usuarios

            WHERE empresa_id = ?

            """, (empresa_id,))

            cursor.execute("""

            DELETE FROM empresa

            WHERE id = ?

            """, (empresa_id,))

        conn.commit()
        conn.close()

        flash(
            "Empresa excluída",
            "sucesso"
        )

        return redirect("/admin")