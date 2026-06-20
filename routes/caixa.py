from flask import *
from database import conectar

from werkzeug.security import (
    check_password_hash
)

from services.pdf_service import (
    gerar_pdf_fechamento
)


def registrar_rotas(app):

    @app.route("/caixa", methods=["GET", "POST"])
    def caixa():

        if not session.get("logado"):
            return redirect("/")

        conn = conectar()
        cursor = conn.cursor()

        empresa_id = session["empresa_id"]

        # ==========================================
        # ÚLTIMO CAIXA
        # ==========================================

        cursor.execute("""

        SELECT *

        FROM caixa

        WHERE empresa_id = ?
        AND status = 'aberto'

        ORDER BY id DESC

        LIMIT 1

        """, (empresa_id,))

        caixa = cursor.fetchone()

   

        # ==========================================
        # POST
        # ==========================================

        if request.method == "POST":

            acao = request.form["acao"]

            senha = request.form["senha"]

            cursor.execute("""

            SELECT *

            FROM usuarios

            WHERE usuario = ?

            """, (

                session["usuario"],

            ))

            usuario = cursor.fetchone()

            if not check_password_hash(
                usuario["senha"],
                senha
            ):

                flash(
                    "Senha incorreta",
                    "erro"
                )

                conn.close()

                return redirect("/caixa")

            # ======================================
            # ABRIR CAIXA
            # ======================================

            if acao == "abrir":

                if caixa and caixa["status"] == "aberto":

                    flash(
                        "Já existe um caixa aberto",
                        "erro"
                    )

                    conn.close()

                    return redirect("/caixa")

                valor = float(
                    request.form["valor"]
                )

                cursor.execute("""

                INSERT INTO caixa(

                    valor_inicial,
                    valor_final,
                    status,
                    empresa_id

                )

                VALUES(?,?,?,?)

                """, (

                    valor,
                    valor,
                    "aberto",
                    empresa_id

                ))

                caixa_id = cursor.lastrowid

                cursor.execute("""

                INSERT INTO movimentacoes_caixa(

                    tipo,
                    descricao,
                    valor,
                    empresa_id,
                    caixa_id

                )

                VALUES(?,?,?,?,?)

                """, (

                    "entrada",
                    "Abertura de caixa",
                    valor,
                    empresa_id,
                    caixa_id

                ))

                conn.commit()

                flash(
                    "Caixa aberto com sucesso",
                    "sucesso"
                )

                conn.close()

                return redirect("/caixa")

            # ======================================
            # ADICIONAR SALDO
            # ======================================

            elif acao == "adicionar":

                valor = float(
                    request.form["valor"]
                )

                novo_valor = (
                    float(caixa["valor_final"])
                    + valor
                )

                cursor.execute("""

                UPDATE caixa

                SET valor_final = ?

                WHERE id = ?

                """, (

                    novo_valor,
                    caixa["id"]

                ))

                cursor.execute("""

                INSERT INTO movimentacoes_caixa(

                    tipo,
                    descricao,
                    valor,
                    empresa_id,
                    caixa_id

                )

                VALUES(?,?,?,?,?)

                """, (

                    "entrada",
                    "Adição manual",
                    valor,
                    empresa_id,
                    caixa["id"]

                ))

                conn.commit()

                flash(
                    "Saldo adicionado",
                    "sucesso"
                )

                conn.close()

                return redirect("/caixa")

            # ======================================
            # SACAR SALDO
            # ======================================

            elif acao == "sacar":

                valor = float(
                    request.form["valor"]
                )

                novo_valor = (
                    float(caixa["valor_final"])
                    - valor
                )

                cursor.execute("""

                UPDATE caixa

                SET valor_final = ?

                WHERE id = ?

                """, (

                    novo_valor,
                    caixa["id"]

                ))

                cursor.execute("""

                INSERT INTO movimentacoes_caixa(

                    tipo,
                    descricao,
                    valor,
                    empresa_id,
                    caixa_id

                )

                VALUES(?,?,?,?,?)

                """, (

                    "saida",
                    "Sangria",
                    valor,
                    empresa_id,
                    caixa["id"]

                ))

                conn.commit()

                flash(
                    "Saque realizado",
                    "sucesso"
                )

                conn.close()

                return redirect("/caixa")

            # ======================================
            # FECHAR CAIXA
            # ======================================

            elif acao == "fechar":

                if not caixa:

                    flash(
                        "Nenhum caixa aberto encontrado",
                        "erro"
                    )

                    conn.close()

                    return redirect("/caixa")

                valor_final = float(caixa["valor_final"])

                cursor.execute("""

                UPDATE caixa

                SET

                    valor_final = ?,
                    status = ?,
                    data_fechamento = CURRENT_TIMESTAMP

                WHERE id = ?

                """, (

                    valor_final,
                    "fechado",
                    caixa["id"]

                ))

                conn.commit()

                caixa_id = caixa["id"]

                conn.close()

                pdf = gerar_pdf_fechamento(
                    caixa_id
                )

                session["carrinho"] = []

                flash(
                    "Caixa fechado com sucesso",
                    "sucesso"
                )

                return send_file(
                    pdf,
                    as_attachment=False
                )

        # ==========================================
        # MOVIMENTAÇÕES
        # ==========================================

        movimentacoes = []

        if caixa:

            cursor.execute("""

            SELECT *

            FROM movimentacoes_caixa

            WHERE caixa_id = ?

            ORDER BY id DESC

            LIMIT 15

            """, (

                caixa["id"],

            ))

            movimentacoes = cursor.fetchall()

        # ==========================================
        # HISTÓRICO DE VENDAS
        # ==========================================

        historico_vendas = []

        if caixa:

            cursor.execute("""

            SELECT

                vendas.id,
                produtos.nome,
                vendas.quantidade,
                vendas.valor,
                vendas.pagamento,
                vendas.data

            FROM vendas

            INNER JOIN produtos
            ON vendas.produto_id = produtos.id

            WHERE vendas.caixa_id = ?
            AND vendas.cancelada = 0

            ORDER BY vendas.id DESC

            LIMIT 20

            """, (

                caixa["id"],

            ))

            historico_vendas = cursor.fetchall()

        # ==========================================
        # RESUMO
        # ==========================================

        saldo = 0
        entradas = 0
        saidas = 0
        total = 0

        if caixa:

            saldo = caixa["valor_final"]
            total = caixa["valor_final"]

        conn.close()

        return render_template(

            "caixa.html",

            caixa=caixa,

            saldo=saldo,

            entradas=entradas,

            saidas=saidas,

            total=total,

            movimentacoes=movimentacoes,

            historico_vendas=historico_vendas

        )
        
    @app.route("/cancelar_venda/<int:venda_id>")
    def cancelar_venda(venda_id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "gerente":

            flash(
                "Apenas gerentes podem cancelar vendas",
                "erro"
            )

            return redirect("/caixa")

        conn = conectar()
        cursor = conn.cursor()

        # ==========================
        # BUSCAR VENDA
        # ==========================

        cursor.execute("""

        SELECT *

        FROM vendas

        WHERE id = ?

        """, (

            venda_id,

        ))

        venda = cursor.fetchone()

        if not venda:

            conn.close()

            flash(
                "Venda não encontrada",
                "erro"
            )

            return redirect("/caixa")

        # ==========================
        # DEVOLVER ESTOQUE
        # ==========================

        cursor.execute("""

        UPDATE produtos

        SET estoque = estoque + ?

        WHERE id = ?

        """, (

            venda["quantidade"],
            venda["produto_id"]

        ))

        # ==========================
        # DESCONTAR DO CAIXA
        # ==========================

        cursor.execute("""

        UPDATE caixa

        SET valor_final = valor_final - ?

        WHERE id = ?

        """, (

            venda["valor"],
            venda["caixa_id"]

        ))

        # ==========================
        # MARCAR COMO CANCELADA
        # ==========================

        cursor.execute("""

        UPDATE vendas

        SET cancelada = 1

        WHERE id = ?

        """, (

            venda_id,

        ))

        # ==========================
        # REGISTRAR MOVIMENTAÇÃO
        # ==========================

        cursor.execute("""

        INSERT INTO movimentacoes_caixa(

            tipo,
            descricao,
            valor,
            empresa_id,
            caixa_id

        )

        VALUES(?,?,?,?,?)

        """, (

            "saida",
            "Cancelamento de venda",
            venda["valor"],
            venda["empresa_id"],
            venda["caixa_id"]

        ))

        conn.commit()
        conn.close()

        flash(
            "Venda cancelada com sucesso",
            "sucesso"
        )

        return redirect("/caixa")