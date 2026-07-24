import re

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import (
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import conectar, criar_cursor
from services.custos_service import CustosService


CATEGORIAS_CUSTOS = [
    "Aluguel",
    "Água",
    "Energia",
    "Internet",
    "Telefone",
    "Impostos",
    "Fornecedores",
    "Manutenção",
    "Marketing",
    "Transporte",
    "Software e assinaturas",
    "Equipamentos",
    "Materiais",
    "Contabilidade",
    "Segurança",
    "Limpeza",
    "Taxas bancárias",
    "Outras despesas",
]


FORMAS_PAGAMENTO = [
    "Dinheiro",
    "PIX",
    "Cartão",
    "Boleto",
    "Transferência",
    "Débito automático",
    "Outro",
]


def _converter_moeda_brasileira(valor):
    """
    Converte valores digitados nos formatos:

    5.020       -> 5020.00
    5.020,50    -> 5020.50
    5020        -> 5020.00
    5020,50     -> 5020.50
    5020.50     -> 5020.50
    R$ 5.020,50 -> 5020.50
    """

    texto = str(
        valor or ""
    ).strip()

    texto = (
        texto
        .replace("R$", "")
        .replace("\u00a0", "")
        .replace(" ", "")
        .strip()
    )

    if not texto:
        raise ValueError(
            "Informe um valor válido."
        )

    if not re.fullmatch(
        r"-?[\d.,]+",
        texto,
    ):
        raise ValueError(
            "Informe um valor monetário válido."
        )

    # Formato brasileiro com vírgula decimal.
    # Exemplo: 5.020,50
    if "," in texto:
        if texto.count(",") > 1:
            raise ValueError(
                "Informe um valor monetário válido."
            )

        parte_inteira, parte_decimal = (
            texto.split(",", 1)
        )

        if (
            parte_decimal
            and not parte_decimal.isdigit()
        ):
            raise ValueError(
                "Informe um valor monetário válido."
            )

        if len(parte_decimal) > 2:
            raise ValueError(
                "Use no máximo duas casas decimais."
            )

        parte_inteira = (
            parte_inteira.replace(".", "")
        )

        texto_normalizado = parte_inteira

        if parte_decimal:
            texto_normalizado += (
                "." + parte_decimal
            )

    # Quando existem pontos no padrão de milhar,
    # remove todos eles.
    # Exemplo: 5.020 ou 1.250.000
    elif re.fullmatch(
        r"-?\d{1,3}(\.\d{3})+",
        texto,
    ):
        texto_normalizado = (
            texto.replace(".", "")
        )

    else:
        # Permite também valor decimal no padrão
        # técnico, por exemplo: 5020.50
        if texto.count(".") > 1:
            raise ValueError(
                "Informe um valor monetário válido."
            )

        texto_normalizado = texto

    if not re.fullmatch(
        r"-?\d+(\.\d{1,2})?",
        texto_normalizado,
    ):
        raise ValueError(
            "Informe um valor monetário válido."
        )

    try:
        resultado = Decimal(
            texto_normalizado
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    except InvalidOperation as erro:
        raise ValueError(
            "Informe um valor monetário válido."
        ) from erro

    if resultado <= 0:
        raise ValueError(
            "O valor deve ser maior que zero."
        )

    return resultado


def _inicio_mes(data_base=None):
    data_base = data_base or date.today()

    return date(
        data_base.year,
        data_base.month,
        1,
    )


def _fim_mes(data_base=None):
    data_base = data_base or date.today()

    if data_base.month == 12:
        proximo_mes = date(
            data_base.year + 1,
            1,
            1,
        )

    else:
        proximo_mes = date(
            data_base.year,
            data_base.month + 1,
            1,
        )

    return (
        proximo_mes
        - timedelta(days=1)
    )


def _converter_data(
    valor,
    padrao,
):
    if not valor:
        return padrao

    try:
        return datetime.strptime(
            valor,
            "%Y-%m-%d",
        ).date()

    except ValueError:
        return padrao


def _periodo_selecionado():
    hoje = date.today()

    periodo = str(
        request.args.get(
            "periodo",
            "mes",
        )
    ).strip().lower()

    if periodo == "hoje":
        return {
            "tipo": "hoje",
            "titulo": "Hoje",
            "data_inicial": hoje,
            "data_final": hoje,
        }

    if periodo == "ano":
        return {
            "tipo": "ano",
            "titulo": "Este ano",
            "data_inicial": date(
                hoje.year,
                1,
                1,
            ),
            "data_final": date(
                hoje.year,
                12,
                31,
            ),
        }

    if periodo == "personalizado":
        data_inicial = _converter_data(
            request.args.get("inicio"),
            _inicio_mes(hoje),
        )

        data_final = _converter_data(
            request.args.get("fim"),
            _fim_mes(hoje),
        )

        if data_final < data_inicial:
            data_final = data_inicial

        return {
            "tipo": "personalizado",
            "titulo": "Período personalizado",
            "data_inicial": data_inicial,
            "data_final": data_final,
        }

    return {
        "tipo": "mes",
        "titulo": "Este mês",
        "data_inicial": _inicio_mes(hoje),
        "data_final": _fim_mes(hoje),
    }


def _caixa_aberto(empresa_id):
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT id
            FROM caixa
            WHERE empresa_id = %s
              AND status = 'aberto'
            ORDER BY id DESC
            LIMIT 1
            """,
            (empresa_id,),
        )

        caixa = cursor.fetchone()

        return (
            caixa["id"]
            if caixa
            else None
        )

    finally:
        cursor.close()
        conn.close()


def _exigir_login():
    if not session.get("logado"):
        return False

    if not session.get("empresa_id"):
        return False

    nivel = str(
        session.get("nivel") or ""
    ).strip().lower()

    # Funcionários não devem visualizar
    # os custos financeiros da empresa.
    if nivel == "funcionario":
        return False

    return True


def registrar_rotas(app):

    # ==========================================
    # PÁGINA PRINCIPAL
    # ==========================================

    @app.route("/custos")
    def custos():

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        periodo = _periodo_selecionado()

        status = str(
            request.args.get(
                "status",
                "",
            )
        ).strip().lower()

        categoria = str(
            request.args.get(
                "categoria",
                "",
            )
        ).strip()

        busca = str(
            request.args.get(
                "q",
                "",
            )
        ).strip()

        try:
            despesas = CustosService.listar(
                empresa_id=empresa_id,
                status=status or None,
                categoria=categoria or None,
                busca=busca or None,
            )

            resumo = CustosService.resumo(
                empresa_id=empresa_id,
                data_inicial=periodo[
                    "data_inicial"
                ],
                data_final=periodo[
                    "data_final"
                ],
            )

        except Exception:
            app.logger.exception(
                "Erro ao carregar custos empresariais."
            )

            flash(
                "Não foi possível carregar as despesas.",
                "erro",
            )

            despesas = []

            resumo = {
                "custos_fixos": 0,
                "custos_variaveis": 0,
                "custos_eventuais": 0,
                "total_previsto": 0,
                "total_pago": 0,
                "total_pendente": 0,
                "total_vencido": 0,
                "contas_pendentes": 0,
                "contas_vencidas": 0,
            }

        return render_template(
            "custos.html",
            despesas=despesas,
            resumo=resumo,
            periodo=periodo,
            categorias=CATEGORIAS_CUSTOS,
            formas_pagamento=FORMAS_PAGAMENTO,
            filtro_status=status,
            filtro_categoria=categoria,
            busca=busca,
            hoje=date.today(),
        )

    # ==========================================
    # CRIAR DESPESA
    # ==========================================

    @app.route(
        "/custos/criar",
        methods=["POST"],
    )
    def criar_custo():

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        usuario_id = session.get(
            "usuario_id"
        )

        recorrente = (
            request.form.get(
                "recorrente"
            )
            == "on"
        )

        ja_pago = (
            request.form.get(
                "ja_pago"
            )
            == "on"
        )

        caixa_id = None

        if ja_pago:
            try:
                caixa_id = _caixa_aberto(
                    empresa_id
                )

            except Exception:
                app.logger.exception(
                    "Erro ao consultar caixa aberto."
                )

        try:
            valor = _converter_moeda_brasileira(
                request.form.get("valor")
            )

            resultado = CustosService.criar(
                empresa_id=empresa_id,
                descricao=request.form.get(
                    "descricao"
                ),
                categoria=request.form.get(
                    "categoria"
                ),
                fornecedor=request.form.get(
                    "fornecedor"
                ),
                valor=valor,
                data_inicio=request.form.get(
                    "data_inicio"
                ),
                data_vencimento=(
                    request.form.get(
                        "data_vencimento"
                    )
                ),
                tipo=request.form.get(
                    "tipo",
                    "variavel",
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
                recorrente=recorrente,
                periodicidade=request.form.get(
                    "periodicidade"
                ),
                quantidade_parcelas=request.form.get(
                    "quantidade_parcelas",
                    1,
                ),
                dia_vencimento=request.form.get(
                    "dia_vencimento"
                ),
                forma_pagamento_padrao=(
                    request.form.get(
                        "forma_pagamento_padrao"
                    )
                ),
                ja_pago=ja_pago,
                usuario_id=usuario_id,
                caixa_id=caixa_id,
            )

            custo = resultado["custo"]

            flash(
                (
                    "Despesa cadastrada com sucesso. "
                    f"Código #{custo['id']}."
                ),
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao cadastrar despesa."
            )

            flash(
                "Não foi possível cadastrar a despesa.",
                "erro",
            )

        return redirect(
            url_for("custos")
        )

    # ==========================================
    # EDITAR DESPESA
    # ==========================================

    @app.route(
        "/custos/<int:custo_id>/editar",
        methods=["POST"],
    )
    def editar_custo(custo_id):

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        recorrente = (
            request.form.get("recorrente")
            == "on"
        )

        try:
            valor = _converter_moeda_brasileira(
                request.form.get("valor")
            )

            CustosService.editar(
                empresa_id=empresa_id,
                custo_id=custo_id,
                descricao=request.form.get(
                    "descricao"
                ),
                categoria=request.form.get(
                    "categoria"
                ),
                fornecedor=request.form.get(
                    "fornecedor"
                ),
                valor=valor,
                data_inicio=request.form.get(
                    "data_inicio"
                ),
                data_vencimento=request.form.get(
                    "data_vencimento"
                ),
                tipo=request.form.get(
                    "tipo",
                    "variavel",
                ),
                observacoes=request.form.get(
                    "observacoes"
                ),
                recorrente=recorrente,
                periodicidade=request.form.get(
                    "periodicidade"
                ),
                quantidade_parcelas=request.form.get(
                    "quantidade_parcelas",
                    1,
                ),
                dia_vencimento=request.form.get(
                    "dia_vencimento"
                ),
                forma_pagamento_padrao=(
                    request.form.get(
                        "forma_pagamento_padrao"
                    )
                ),
            )

            flash(
                "Despesa atualizada com sucesso.",
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao editar despesa."
            )

            flash(
                "Não foi possível editar a despesa.",
                "erro",
            )

        return redirect(
            request.referrer
            or url_for("custos")
        )
        
    # ==========================================
    # PREPARAR CORREÇÃO DA DESPESA
    # ==========================================

    @app.route(
        "/custos/<int:custo_id>/corrigir",
        methods=["POST"],
    )
    def corrigir_custo(custo_id):

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        motivo = request.form.get(
            "motivo"
        )

        try:
            resultado = (
                CustosService.preparar_correcao(
                    empresa_id=empresa_id,
                    custo_id=custo_id,
                    motivo=motivo,
                )
            )

            quantidade = resultado[
                "pagamentos_estornados"
            ]

            total = resultado[
                "total_estornado"
            ]

            total_formatado = (
                f"{total:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )

            if quantidade:
                mensagem = (
                    f"{quantidade} pagamento(s) estornado(s). "
                    f"Total: R$ {total_formatado}. "
                    "A despesa já pode ser editada ou excluída."
                )

            else:
                mensagem = (
                    "A despesa não possui pagamentos ativos "
                    "e já pode ser editada ou excluída."
                )

            flash(
                mensagem,
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao preparar correção da despesa."
            )

            flash(
                "Não foi possível preparar o lançamento "
                "para correção.",
                "erro",
            )

        return redirect(
            request.referrer
            or url_for("custos")
        )
    
    

    # ==========================================
    # EXCLUIR OU ARQUIVAR DESPESA
    # ==========================================

    @app.route(
        "/custos/<int:custo_id>/excluir",
        methods=["POST"],
    )
    def excluir_custo(custo_id):

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        try:
            resultado = CustosService.excluir(
                empresa_id=empresa_id,
                custo_id=custo_id,
            )

            if resultado["acao"] == "arquivada":
                mensagem = (
                    "Despesa arquivada com sucesso. "
                    "O histórico estornado foi preservado."
                )

            else:
                mensagem = (
                    "Despesa excluída com sucesso."
                )

            flash(
                mensagem,
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao excluir despesa."
            )

            flash(
                "Não foi possível excluir a despesa.",
                "erro",
            )

        return redirect(
            url_for("custos")
        )
    
    # ==========================================
    # PAGAR PARCELA
    # ==========================================

    @app.route(
        "/custos/parcela/<int:parcela_id>/pagar",
        methods=["POST"],
    )
    def pagar_custo(parcela_id):

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        usuario_id = session.get(
            "usuario_id"
        )

        try:
            valor_pagamento = (
                _converter_moeda_brasileira(
                    request.form.get("valor")
                )
            )

            caixa_id = _caixa_aberto(
                empresa_id
            )

            resultado = CustosService.pagar(
                empresa_id=empresa_id,
                parcela_id=parcela_id,
                valor=valor_pagamento,
                forma_pagamento=request.form.get(
                    "forma_pagamento"
                ),
                usuario_id=usuario_id,
                caixa_id=caixa_id,
                observacoes=request.form.get(
                    "observacoes"
                ),
            )

            saldo = Decimal(
                str(
                    resultado.get(
                        "saldo",
                        0,
                    )
                )
            )

            if saldo <= Decimal("0.00"):
                mensagem = (
                    "Pagamento registrado. "
                    "A despesa foi quitada."
                )

            else:
                saldo_formatado = (
                    f"{saldo:,.2f}"
                    .replace(",", "X")
                    .replace(".", ",")
                    .replace("X", ".")
                )

                mensagem = (
                    "Pagamento parcial registrado. "
                    f"Saldo restante: R$ {saldo_formatado}."
                )

            flash(
                mensagem,
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao pagar despesa."
            )

            flash(
                "Não foi possível registrar o pagamento.",
                "erro",
            )

        return redirect(
            request.referrer
            or url_for("custos")
        )

    # ==========================================
    # ESTORNAR PAGAMENTO
    # ==========================================

    @app.route(
        "/custos/pagamento/<int:pagamento_id>/estornar",
        methods=["POST"],
    )
    def estornar_pagamento_custo(
        pagamento_id
    ):

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        try:
            CustosService.estornar_pagamento(
                empresa_id=empresa_id,
                pagamento_id=pagamento_id,
                motivo=request.form.get(
                    "motivo"
                ),
            )

            flash(
                "Pagamento estornado com sucesso.",
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao estornar pagamento."
            )

            flash(
                "Não foi possível estornar o pagamento.",
                "erro",
            )

        return redirect(
            request.referrer
            or url_for("custos")
        )

    # ==========================================
    # ATIVAR OU DESATIVAR DESPESA
    # ==========================================

    @app.route(
        "/custos/<int:custo_id>/status",
        methods=["POST"],
    )
    def alterar_status_custo(custo_id):

        if not _exigir_login():
            return redirect("/")

        empresa_id = session.get(
            "empresa_id"
        )

        acao = str(
            request.form.get(
                "acao",
                "",
            )
        ).strip().lower()

        if acao not in {
            "ativar",
            "desativar",
        }:
            flash(
                "Ação inválida.",
                "erro",
            )

            return redirect(
                url_for("custos")
            )

        ativo = (
            acao == "ativar"
        )

        try:
            CustosService.alterar_status(
                empresa_id=empresa_id,
                custo_id=custo_id,
                ativo=ativo,
            )

            mensagem = (
                "Despesa ativada."
                if ativo
                else "Despesa desativada."
            )

            flash(
                mensagem,
                "sucesso",
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro",
            )

        except Exception:
            app.logger.exception(
                "Erro ao alterar status da despesa."
            )

            flash(
                "Não foi possível alterar a despesa.",
                "erro",
            )
 
        return redirect(
            request.referrer
            or url_for("custos")
        )