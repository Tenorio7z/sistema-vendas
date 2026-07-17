from flask import *
from database import conectar
import psycopg2.extras

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
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        empresa_id = session["empresa_id"]

        # ==========================================
        # ÚLTIMO CAIXA
        # ==========================================

        cursor.execute("""

        SELECT *

        FROM caixa

        WHERE empresa_id = %s
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

            WHERE usuario = %s

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
                    empresa_id,
                    data_abertura
                )
                VALUES(%s,%s,%s,%s,NOW())
                RETURNING id
                """, (
                    valor,
                    valor,
                    "aberto",
                    empresa_id
                ))

                caixa_id = cursor.fetchone()["id"]

                cursor.execute("""

                INSERT INTO movimentacoes_caixa(

                    tipo,
                    descricao,
                    valor,
                    empresa_id,
                    caixa_id

                )

                VALUES(%s,%s,%s,%s,%s)

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

                SET valor_final = %s

                WHERE id = %s

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

                VALUES(%s,%s,%s,%s,%s)

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

                SET valor_final = %s

                WHERE id = %s

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

                VALUES(%s,%s,%s,%s,%s)

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

                    valor_final = %s,
                    status = %s,
                    data_fechamento = CURRENT_TIMESTAMP

                WHERE id = %s

                """, (

                    valor_final,
                    "fechado",
                    caixa["id"]

                ))

                conn.commit()

                caixa_id = caixa["id"]

                conn.close()

                pdf = gerar_pdf_fechamento(
                    caixa_id,
                    session["empresa_id"]
                )

                session["carrinho"] = []

                flash(
                    "Caixa fechado com sucesso",
                    "sucesso"
                )

            
                
                if not pdf:
                    flash(
                        "Não foi possível gerar o relatório do caixa.",
                        "erro"
                    )

                    return redirect("/caixa")

                return send_file(
                    pdf,
                    mimetype="application/pdf",
                    as_attachment=False,
                    download_name=f"fechamento_caixa_{caixa_id}.pdf"
                )

        # ==========================================
        # MOVIMENTAÇÕES
        # ==========================================

        movimentacoes = []

        if caixa:

            cursor.execute("""

            SELECT *

            FROM movimentacoes_caixa

            WHERE caixa_id = %s

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

            WHERE vendas.caixa_id = %s
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
        
        # ==========================================
    # CANCELAR VENDA
    # ==========================================

    @app.route(
        "/cancelar_venda/<int:venda_id>",
        methods=["POST"],
    )
    def cancelar_venda(venda_id):

        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") not in (
            "gerente",
            "funcionario",
        ):
            flash(
                (
                    "Você não possui permissão "
                    "para cancelar vendas."
                ),
                "erro",
            )

            return redirect("/caixa")

        empresa_id = session.get(
            "empresa_id"
        )

        if not empresa_id:
            session.clear()
            return redirect("/")

        conn = conectar()

        cursor = conn.cursor(
            cursor_factory=(
                psycopg2.extras.RealDictCursor
            )
        )

        try:
            # A venda é bloqueada durante o cancelamento.
            # Também verificamos a empresa para impedir
            # acesso aos registros de outro cliente.
            cursor.execute(
                """
                SELECT
                    id,
                    produto_id,
                    quantidade,
                    valor,
                    caixa_id,
                    empresa_id,

                    COALESCE(
                        cancelada,
                        0
                    ) AS cancelada

                FROM vendas

                WHERE id = %s
                  AND empresa_id = %s

                LIMIT 1

                FOR UPDATE
                """,
                (
                    venda_id,
                    empresa_id,
                ),
            )

            venda = cursor.fetchone()

            if not venda:
                raise ValueError(
                    "Venda não encontrada."
                )

            if venda["cancelada"]:
                raise ValueError(
                    "Esta venda já foi cancelada."
                )

            # ======================================
            # DEVOLVER ESTOQUE
            # ======================================

            cursor.execute(
                """
                UPDATE produtos

                SET estoque = estoque + %s

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    venda["quantidade"],
                    venda["produto_id"],
                    empresa_id,
                ),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    (
                        "O produto relacionado à venda "
                        "não foi encontrado."
                    )
                )

            # ======================================
            # ATUALIZAR O CAIXA
            # ======================================

            cursor.execute(
                """
                UPDATE caixa

                SET valor_final = (
                    COALESCE(
                        valor_final,
                        0
                    ) - %s
                )

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    venda["valor"],
                    venda["caixa_id"],
                    empresa_id,
                ),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    (
                        "O caixa relacionado à venda "
                        "não foi encontrado."
                    )
                )

            # ======================================
            # MARCAR A VENDA COMO CANCELADA
            # ======================================

            cursor.execute(
                """
                UPDATE vendas

                SET
                    cancelada = 1,
                    cancelada_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s
                  AND COALESCE(
                      cancelada,
                      0
                  ) = 0
                """,
                (
                    venda_id,
                    empresa_id,
                ),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Esta venda já foi cancelada."
                )

            # ======================================
            # REGISTRAR MOVIMENTAÇÃO
            # ======================================

            cursor.execute(
                """
                INSERT INTO movimentacoes_caixa (
                    tipo,
                    descricao,
                    valor,
                    empresa_id,
                    caixa_id,
                    data
                )
                VALUES (
                    'saida',
                    %s,
                    %s,
                    %s,
                    %s,
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    (
                        "Cancelamento da venda "
                        f"#{venda_id} por "
                        f"{session.get('usuario', 'usuário')}"
                    ),
                    venda["valor"],
                    empresa_id,
                    venda["caixa_id"],
                ),
            )

            conn.commit()

            flash(
                "Venda cancelada com sucesso.",
                "sucesso",
            )

        except ValueError as erro:
            conn.rollback()

            flash(
                str(erro),
                "erro",
            )

        except Exception:
            conn.rollback()

            app.logger.exception(
                "Erro ao cancelar venda."
            )

            flash(
                (
                    "Não foi possível cancelar "
                    "a venda."
                ),
                "erro",
            )

        finally:
            cursor.close()
            conn.close()

        return redirect("/caixa")