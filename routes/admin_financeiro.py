from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from flask import flash, redirect, render_template, request, session, url_for
from database import conectar, criar_cursor

def registrar_rotas(app):
    categorias = ("Hospedagem", "Infraestrutura", "Taxas", "Marketing", "Outros")
    def master_only():
        if not session.get("logado"): return redirect("/")
        if session.get("nivel") != "master": return redirect("/dashboard")
        return None
    def decimal_form(value, allow_zero=True):
        raw = str(value or "").strip().replace("R$", "").replace(" ", "")
        if "," in raw: raw = raw.replace(".", "").replace(",", ".")
        try: amount = Decimal(raw).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError): raise ValueError("Informe um valor válido.")
        if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0): raise ValueError("O valor precisa ser maior que zero.")
        return amount
    def month_date(raw):
        if not re.fullmatch(r"\d{4}-\d{2}", raw or ""): raise ValueError("Competência inválida.")
        return datetime.strptime(raw, "%Y-%m").date().replace(day=1)
    def currency(value):
        value = Decimal(str(value or 0))
        return ("R$ " + f"{value:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")
    app.jinja_env.filters["brl"] = currency

    @app.get("/admin/financeiro")
    def admin_financeiro():
        denied = master_only()
        if denied: return denied
        today = date.today()
        try: competencia = month_date(request.args.get("mes", today.strftime("%Y-%m")))
        except ValueError: competencia = today.replace(day=1)
        conn = conectar(); cursor = criar_cursor(conn)
        try:
            cursor.execute("SELECT valor_mensalidade FROM financeiro_configuracao WHERE id = 1")
            config = cursor.fetchone(); mensalidade = Decimal(str(config["valor_mensalidade"] if config else 150))
            cursor.execute("""
                SELECT e.id AS empresa_id, e.nome AS empresa_nome, u.usuario, u.status,
                       p.id AS pagamento_id, p.valor_mensalidade, p.valor_pago, p.extra,
                       p.data_pagamento, p.forma_pagamento, p.observacao
                FROM empresa e JOIN LATERAL (
                    SELECT usuario, status FROM usuarios WHERE empresa_id = e.id AND nivel = 'gerente' ORDER BY id LIMIT 1
                ) u ON TRUE
                LEFT JOIN financeiro_pagamentos p ON p.empresa_id = e.id AND p.competencia = %s
                ORDER BY e.nome
            """, (competencia,)); empresas = cursor.fetchall()
            cursor.execute("SELECT id, descricao, categoria, valor, data_despesa, observacao FROM financeiro_despesas WHERE competencia = %s ORDER BY data_despesa DESC, id DESC", (competencia,)); despesas = cursor.fetchall()
            cursor.execute("SELECT COALESCE(SUM(valor_pago),0) AS recebido, COALESCE(SUM(extra),0) AS extras, COUNT(*) AS pagamentos FROM financeiro_pagamentos WHERE competencia=%s", (competencia,)); resumo = cursor.fetchone()
            cursor.execute("""
                SELECT date_trunc('month', g.mes)::date AS competencia,
                  COALESCE((SELECT SUM(valor_pago) FROM financeiro_pagamentos p WHERE p.competencia=date_trunc('month',g.mes)::date),0) AS recebido,
                  COALESCE((SELECT SUM(valor) FROM financeiro_despesas d WHERE d.competencia=date_trunc('month',g.mes)::date),0) AS despesas
                FROM generate_series(%s::date - INTERVAL '5 months', %s::date, INTERVAL '1 month') AS g(mes)
                ORDER BY competencia
            """, (competencia, competencia)); grafico = cursor.fetchall()
        finally:
            cursor.close(); conn.close()
        for row in empresas: row["ativa"] = row["status"] == "ativo"
        pagas_ativas = [e for e in empresas if e["ativa"] and e["pagamento_id"]]
        pendentes = [e for e in empresas if e["ativa"] and not e["pagamento_id"]]
        total_despesas = sum((Decimal(str(d["valor"])) for d in despesas), Decimal("0"))
        esperado = sum((Decimal(str(e["valor_mensalidade"] if e["pagamento_id"] else mensalidade)) for e in empresas if e["ativa"]), Decimal("0"))
        recebido = Decimal(str(resumo["recebido"]))
        for row in grafico:
            row["recebido"] = Decimal(str(row["recebido"])); row["despesas"] = Decimal(str(row["despesas"])); row["rotulo"] = row["competencia"].strftime("%b/%y")
        max_bar = max((max(r["recebido"], r["despesas"]) for r in grafico), default=Decimal("1")) or Decimal("1")
        for row in grafico:
            row["recebido_pct"] = max(4, int(row["recebido"] / max_bar * 100)) if row["recebido"] else 0
            row["despesas_pct"] = max(4, int(row["despesas"] / max_bar * 100)) if row["despesas"] else 0
        return render_template("admin_financeiro.html", competencia=competencia.strftime("%Y-%m"), mensalidade=mensalidade, empresas=empresas, despesas=despesas, categorias=categorias, resumo=resumo, recebido=recebido, extras=Decimal(str(resumo["extras"])), total_despesas=total_despesas, saldo=recebido-total_despesas, esperado=esperado, pendentes=pendentes, pagas_ativas=pagas_ativas, pendente_valor=sum((Decimal(str(e["valor_mensalidade"] if e["pagamento_id"] else mensalidade)) for e in pendentes), Decimal("0")), grafico=grafico, mes_atual=today.strftime("%Y-%m"))

    @app.post("/admin/financeiro/mensalidade")
    def admin_financeiro_mensalidade():
        denied=master_only()
        if denied:return denied
        try:
            valor=decimal_form(request.form.get("valor")); conn=conectar(); cursor=criar_cursor(conn)
            cursor.execute("INSERT INTO financeiro_configuracao(id,valor_mensalidade) VALUES(1,%s) ON CONFLICT(id) DO UPDATE SET valor_mensalidade=EXCLUDED.valor_mensalidade, atualizado_em=CURRENT_TIMESTAMP",(valor,)); conn.commit(); cursor.close(); conn.close()
            flash("Mensalidade padrão atualizada. O histórico foi preservado.","success")
        except ValueError as exc: flash(str(exc),"error")
        return redirect(url_for("admin_financeiro",mes=request.form.get("mes")))

    @app.post("/admin/financeiro/pagamento")
    def admin_financeiro_pagamento():
        denied=master_only()
        if denied:return denied
        try:
            competencia=month_date(request.form.get("mes","")); valor_pago=decimal_form(request.form.get("valor_pago")); data_pagamento=date.fromisoformat(request.form.get("data_pagamento","")); empresa_id=int(request.form.get("empresa_id","")); forma=(request.form.get("forma_pagamento") or "").strip()[:40] or None; observacao=(request.form.get("observacao") or "").strip()[:500] or None
            conn=conectar(); cursor=criar_cursor(conn)
            cursor.execute("SELECT e.nome, COALESCE(c.valor_mensalidade,150) AS mensalidade FROM empresa e LEFT JOIN financeiro_configuracao c ON c.id=1 WHERE e.id=%s",(empresa_id,)); empresa=cursor.fetchone()
            if not empresa: raise ValueError("Empresa não encontrada.")
            fee=Decimal(str(empresa["mensalidade"])); extra=max(valor_pago-fee,Decimal("0"))
            cursor.execute("""
                INSERT INTO financeiro_pagamentos(empresa_id,empresa_nome,competencia,valor_mensalidade,valor_pago,extra,data_pagamento,forma_pagamento,observacao,registrado_por)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(empresa_id,competencia) DO UPDATE SET empresa_nome=EXCLUDED.empresa_nome, valor_mensalidade=EXCLUDED.valor_mensalidade, valor_pago=EXCLUDED.valor_pago, extra=EXCLUDED.extra, data_pagamento=EXCLUDED.data_pagamento, forma_pagamento=EXCLUDED.forma_pagamento, observacao=EXCLUDED.observacao, registrado_por=EXCLUDED.registrado_por, atualizado_em=CURRENT_TIMESTAMP
            """,(empresa_id,empresa["nome"],competencia,fee,valor_pago,extra,data_pagamento,forma,observacao,session.get("usuario_id"))); conn.commit(); cursor.close(); conn.close()
            flash("Pagamento confirmado e registrado.","success")
        except (ValueError,TypeError,InvalidOperation) as exc: flash(str(exc) or "Confira os dados informados.","error")
        return redirect(url_for("admin_financeiro",mes=request.form.get("mes")))

    @app.post("/admin/financeiro/despesa")
    def admin_financeiro_despesa():
        denied=master_only()
        if denied:return denied
        try:
            competencia=month_date(request.form.get("mes","")); valor=decimal_form(request.form.get("valor"),allow_zero=False); data_despesa=date.fromisoformat(request.form.get("data_despesa","")); descricao=(request.form.get("descricao") or "").strip()[:180]; categoria=request.form.get("categoria","Outros"); observacao=(request.form.get("observacao") or "").strip()[:500] or None
            if not descricao or categoria not in categorias: raise ValueError("Informe uma descrição e categoria válidas.")
            conn=conectar(); cursor=criar_cursor(conn); cursor.execute("INSERT INTO financeiro_despesas(descricao,categoria,valor,data_despesa,competencia,observacao,registrado_por) VALUES(%s,%s,%s,%s,%s,%s,%s)",(descricao,categoria,valor,data_despesa,competencia,observacao,session.get("usuario_id"))); conn.commit(); cursor.close(); conn.close()
            flash("Despesa adicionada ao mês.","success")
        except (ValueError,TypeError) as exc: flash(str(exc),"error")
        return redirect(url_for("admin_financeiro",mes=request.form.get("mes")))
