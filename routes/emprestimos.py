from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import (
    conectar,
    criar_cursor,
)

from services.emprestimos_service import (
    EmprestimosService,
)

from services.emprestimo_clientes_service import (
    EmprestimoClientesService,
)


emprestimos_bp = Blueprint(
    "emprestimos",
    __name__,
    url_prefix="/emprestimos",
)


def login_obrigatorio(
    funcao
):
    @wraps(funcao)
    def wrapper(
        *args,
        **kwargs
    ):
        if not session.get("logado"):
            return redirect("/")

        if not session.get("empresa_id"):
            flash(
                "Empresa não identificada.",
                "erro"
            )

            return redirect("/dashboard")

        return funcao(
            *args,
            **kwargs
        )

    return wrapper


def gerente_obrigatorio(
    funcao
):
    @wraps(funcao)
    def wrapper(
        *args,
        **kwargs
    ):
        if not session.get("logado"):
            return redirect("/")

        if session.get("nivel") != "gerente":
            flash(
                "Você não possui permissão "
                "para acessar empréstimos.",
                "erro"
            )

            return redirect("/dashboard")

        if not session.get("empresa_id"):
            return redirect("/dashboard")

        return funcao(
            *args,
            **kwargs
        )

    return wrapper


def _valor_formulario(
    nome,
    padrao=None,
):
    valor = request.form.get(
        nome,
        padrao
    )

    if isinstance(
        valor,
        str
    ):
        valor = valor.strip()

        if "," in valor:
            valor = (
                valor
                .replace(".", "")
                .replace(",", ".")
            )

    return valor


def _buscar_resumo(
    empresa_id
):
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        cursor.execute(
            """
            SELECT
                COUNT(*)
                    AS total_clientes,

                COUNT(*) FILTER (
                    WHERE status = 'ativo'
                ) AS clientes_ativos,

                COUNT(*) FILTER (
                    WHERE status = 'bloqueado'
                ) AS clientes_bloqueados

            FROM emprestimo_clientes

            WHERE empresa_id = %s
            """,
            (
                empresa_id,
            )
        )

        clientes = (
            cursor.fetchone()
            or {}
        )

        cursor.execute(
            """
            SELECT
                COUNT(*)
                    AS total_emprestimos,

                COUNT(*) FILTER (
                    WHERE status = 'ativo'
                ) AS emprestimos_ativos,

                COUNT(*) FILTER (
                    WHERE status = 'atrasado'
                ) AS emprestimos_atrasados,

                COUNT(*) FILTER (
                    WHERE status = 'quitado'
                ) AS emprestimos_quitados,

                COALESCE(
                    SUM(valor_emprestado)
                    FILTER (
                        WHERE status != 'cancelado'
                    ),
                    0
                ) AS total_emprestado,

                COALESCE(
                    SUM(valor_pago)
                    FILTER (
                        WHERE status != 'cancelado'
                    ),
                    0
                ) AS total_recebido,

                COALESCE(
                    SUM(
                        valor_total
                        - valor_pago
                    )
                    FILTER (
                        WHERE status IN (
                            'ativo',
                            'atrasado'
                        )
                    ),
                    0
                ) AS total_a_receber

            FROM emprestimos

            WHERE empresa_id = %s
            """,
            (
                empresa_id,
            )
        )

        emprestimos = (
            cursor.fetchone()
            or {}
        )

        cursor.execute(
            """
            SELECT
                COUNT(*)
                    AS parcelas_atrasadas,

                COALESCE(
                    SUM(
                        valor_parcela
                        + valor_multa
                        - valor_pago
                    ),
                    0
                ) AS valor_atrasado

            FROM emprestimo_parcelas

            WHERE empresa_id = %s
              AND status = 'atrasada'
            """,
            (
                empresa_id,
            )
        )

        atrasos = (
            cursor.fetchone()
            or {}
        )

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(valor),
                    0
                ) AS recebido_hoje

            FROM emprestimo_pagamentos

            WHERE empresa_id = %s
              AND estornado = FALSE
              AND data_pagamento >=
                    CURRENT_DATE
              AND data_pagamento <
                    CURRENT_DATE
                    + INTERVAL '1 day'
            """,
            (
                empresa_id,
            )
        )

        pagamentos = (
            cursor.fetchone()
            or {}
        )

        return {
            **clientes,
            **emprestimos,
            **atrasos,
            **pagamentos,
        }

    finally:
        cursor.close()
        conn.close()


def _listar_emprestimos(
    empresa_id,
    status=None,
    limite=100,
):
    conn = conectar()
    cursor = criar_cursor(conn)

    try:
        filtros = [
            "e.empresa_id = %s"
        ]

        parametros = [
            empresa_id
        ]

        status_validos = (
            "ativo",
            "atrasado",
            "quitado",
            "cancelado",
            "renegociado",
        )

        if status in status_validos:
            filtros.append(
                "e.status = %s"
            )

            parametros.append(
                status
            )

        parametros.append(
            limite
        )

        where_sql = " AND ".join(
            filtros
        )

        cursor.execute(
            f"""
            SELECT
                e.*,

                c.nome AS cliente_nome,
                c.telefone
                    AS cliente_telefone,

                (
                    e.valor_total
                    - e.valor_pago
                ) AS saldo_devedor,

                COUNT(p.id) FILTER (
                    WHERE p.status =
                        'atrasada'
                ) AS parcelas_atrasadas,

                MIN(
                    p.data_vencimento
                ) FILTER (
                    WHERE p.status IN (
                        'pendente',
                        'parcial',
                        'atrasada'
                    )
                ) AS proximo_vencimento

            FROM emprestimos e

            INNER JOIN emprestimo_clientes c
                ON c.id = e.cliente_id
               AND c.empresa_id =
                   e.empresa_id

            LEFT JOIN emprestimo_parcelas p
                ON p.emprestimo_id = e.id
               AND p.empresa_id =
                   e.empresa_id

            WHERE {where_sql}

            GROUP BY
                e.id,
                c.id

            ORDER BY
                CASE
                    WHEN e.status = 'atrasado'
                    THEN 0

                    WHEN e.status = 'ativo'
                    THEN 1

                    ELSE 2
                END,

                proximo_vencimento,
                e.id DESC

            LIMIT %s
            """,
            tuple(parametros)
        )

        return (
            cursor.fetchall()
            or []
        )

    finally:
        cursor.close()
        conn.close()


@emprestimos_bp.route("")
@gerente_obrigatorio
def dashboard():
    empresa_id = session[
        "empresa_id"
    ]

    EmprestimosService.atualizar_atrasos(
        empresa_id
    )

    status = request.args.get(
        "status"
    )

    resumo = _buscar_resumo(
        empresa_id
    )

    emprestimos = _listar_emprestimos(
        empresa_id,
        status=status,
    )

    clientes = (
        EmprestimoClientesService
        .listar(
            empresa_id,
            status="ativo",
            limite=500,
        )
    )

    return render_template(
        "emprestimos/index.html",

        resumo=resumo,
        emprestimos=emprestimos,
        clientes=clientes,
        status_selecionado=status,
    )


@emprestimos_bp.route(
    "/clientes",
    methods=[
        "GET",
        "POST",
    ]
)
@gerente_obrigatorio
def clientes():
    empresa_id = session[
        "empresa_id"
    ]

    if request.method == "POST":
        try:
            cliente_id = (
                EmprestimoClientesService
                .criar(
                    empresa_id=empresa_id,

                    nome=request.form.get(
                        "nome"
                    ),

                    telefone=request.form.get(
                        "telefone"
                    ),

                    documento=request.form.get(
                        "documento"
                    ),

                    email=request.form.get(
                        "email"
                    ),

                    endereco=request.form.get(
                        "endereco"
                    ),

                    observacoes=request.form.get(
                        "observacoes"
                    ),
                )
            )

            flash(
                "Cliente cadastrado "
                "com sucesso.",
                "sucesso"
            )

            return redirect(
                url_for(
                    "emprestimos.cliente_detalhe",
                    cliente_id=cliente_id,
                )
            )

        except ValueError as erro:
            flash(
                str(erro),
                "erro"
            )

        except Exception as erro:
            print(
                "Erro ao cadastrar cliente:",
                erro
            )

            flash(
                "Não foi possível "
                "cadastrar o cliente.",
                "erro"
            )

    busca = request.args.get(
        "busca",
        ""
    )

    status = request.args.get(
        "status"
    )

    lista_clientes = (
        EmprestimoClientesService
        .listar(
            empresa_id=empresa_id,
            busca=busca,
            status=status,
        )
    )

    return render_template(
        "emprestimos/clientes.html",

        clientes=lista_clientes,
        busca=busca,
        status_selecionado=status,
    )


@emprestimos_bp.route(
    "/clientes/<int:cliente_id>"
)
@gerente_obrigatorio
def cliente_detalhe(
    cliente_id
):
    empresa_id = session[
        "empresa_id"
    ]

    EmprestimosService.atualizar_atrasos(
        empresa_id
    )

    cliente = (
        EmprestimoClientesService
        .buscar(
            empresa_id,
            cliente_id,
        )
    )

    if not cliente:
        flash(
            "Cliente não encontrado.",
            "erro"
        )

        return redirect(
            url_for(
                "emprestimos.clientes"
            )
        )

    emprestimos = (
        EmprestimoClientesService
        .listar_emprestimos(
            empresa_id,
            cliente_id,
        )
    )

    return render_template(
        "emprestimos/cliente_detalhe.html",

        cliente=cliente,
        emprestimos=emprestimos,
    )


@emprestimos_bp.route(
    "/clientes/<int:cliente_id>/editar",
    methods=["POST"]
)
@gerente_obrigatorio
def cliente_editar(
    cliente_id
):
    empresa_id = session[
        "empresa_id"
    ]

    try:
        EmprestimoClientesService.atualizar(
            empresa_id=empresa_id,
            cliente_id=cliente_id,

            nome=request.form.get(
                "nome"
            ),

            telefone=request.form.get(
                "telefone"
            ),

            documento=request.form.get(
                "documento"
            ),

            email=request.form.get(
                "email"
            ),

            endereco=request.form.get(
                "endereco"
            ),

            observacoes=request.form.get(
                "observacoes"
            ),

            status=request.form.get(
                "status",
                "ativo"
            ),
        )

        flash(
            "Cliente atualizado.",
            "sucesso"
        )

    except ValueError as erro:
        flash(
            str(erro),
            "erro"
        )

    except Exception as erro:
        print(
            "Erro ao editar cliente:",
            erro
        )

        flash(
            "Não foi possível "
            "atualizar o cliente.",
            "erro"
        )

    return redirect(
        url_for(
            "emprestimos.cliente_detalhe",
            cliente_id=cliente_id,
        )
    )


@emprestimos_bp.route(
    "/clientes/<int:cliente_id>/status",
    methods=["POST"]
)
@gerente_obrigatorio
def cliente_status(
    cliente_id
):
    empresa_id = session[
        "empresa_id"
    ]

    status = request.form.get(
        "status"
    )

    try:
        EmprestimoClientesService.alterar_status(
            empresa_id,
            cliente_id,
            status,
        )

        flash(
            "Status do cliente atualizado.",
            "sucesso"
        )

    except ValueError as erro:
        flash(
            str(erro),
            "erro"
        )

    except Exception as erro:
        print(
            "Erro ao alterar status:",
            erro
        )

        flash(
            "Não foi possível "
            "alterar o status.",
            "erro"
        )

    return redirect(
        url_for(
            "emprestimos.cliente_detalhe",
            cliente_id=cliente_id,
        )
    )


@emprestimos_bp.route(
    "/novo",
    methods=["POST"]
)
@gerente_obrigatorio
def novo_emprestimo():
    empresa_id = session[
        "empresa_id"
    ]

    usuario_id = session.get(
        "usuario_id"
    )

    try:
        resultado = (
            EmprestimosService
            .criar_emprestimo(
                empresa_id=empresa_id,

                cliente_id=request.form.get(
                    "cliente_id"
                ),

                usuario_id=usuario_id,

                valor_emprestado=(
                    _valor_formulario(
                        "valor_emprestado"
                    )
                ),

                taxa_juros=(
                    _valor_formulario(
                        "taxa_juros",
                        "0"
                    )
                ),

                quantidade_parcelas=(
                    request.form.get(
                        "quantidade_parcelas"
                    )
                ),

                primeira_parcela=(
                    request.form.get(
                        "primeira_parcela"
                    )
                ),

                frequencia=(
                    request.form.get(
                        "frequencia",
                        "mensal"
                    )
                ),

                tipo_juros=(
                    request.form.get(
                        "tipo_juros",
                        "simples"
                    )
                ),

                data_emprestimo=(
                    request.form.get(
                        "data_emprestimo"
                    )
                    or None
                ),

                observacoes=(
                    request.form.get(
                        "observacoes"
                    )
                ),
            )
        )

        flash(
            (
                "Empréstimo criado. "
                f"Total: R$ "
                f"{resultado['valor_total']}"
            ),
            "sucesso"
        )

        return redirect(
            url_for(
                "emprestimos.emprestimo_detalhe",
                emprestimo_id=(
                    resultado[
                        "emprestimo_id"
                    ]
                ),
            )
        )

    except ValueError as erro:
        flash(
            str(erro),
            "erro"
        )

    except Exception as erro:
        print(
            "Erro ao criar empréstimo:",
            erro
        )

        flash(
            "Não foi possível criar "
            "o empréstimo.",
            "erro"
        )

    return redirect(
        url_for(
            "emprestimos.dashboard"
        )
    )


@emprestimos_bp.route(
    "/<int:emprestimo_id>"
)
@gerente_obrigatorio
def emprestimo_detalhe(
    emprestimo_id
):
    empresa_id = session[
        "empresa_id"
    ]

    emprestimo = (
        EmprestimosService
        .buscar_emprestimo(
            empresa_id,
            emprestimo_id,
        )
    )

    if not emprestimo:
        flash(
            "Empréstimo não encontrado.",
            "erro"
        )

        return redirect(
            url_for(
                "emprestimos.dashboard"
            )
        )

    return render_template(
        "emprestimos/emprestimo_detalhe.html",

        emprestimo=emprestimo,
    )


@emprestimos_bp.route(
    "/<int:emprestimo_id>/pagamento",
    methods=["POST"]
)
@gerente_obrigatorio
def registrar_pagamento(
    emprestimo_id
):
    empresa_id = session[
        "empresa_id"
    ]

    usuario_id = session.get(
        "usuario_id"
    )

    parcela_id = request.form.get(
        "parcela_id"
    )

    if parcela_id:
        try:
            parcela_id = int(
                parcela_id
            )

        except ValueError:
            parcela_id = None

    try:
        resultado = (
            EmprestimosService
            .registrar_pagamento(
                empresa_id=empresa_id,

                emprestimo_id=(
                    emprestimo_id
                ),

                valor=_valor_formulario(
                    "valor"
                ),

                usuario_id=usuario_id,

                parcela_id=parcela_id,

                forma_pagamento=(
                    request.form.get(
                        "forma_pagamento",
                        "dinheiro"
                    )
                ),

                observacoes=(
                    request.form.get(
                        "observacoes"
                    )
                ),
            )
        )

        flash(
            (
                "Pagamento registrado. "
                f"Saldo devedor: R$ "
                f"{resultado['saldo_devedor']}"
            ),
            "sucesso"
        )

    except ValueError as erro:
        flash(
            str(erro),
            "erro"
        )

    except Exception as erro:
        print(
            "Erro ao registrar pagamento:",
            erro
        )

        flash(
            "Não foi possível registrar "
            "o pagamento.",
            "erro"
        )

    return redirect(
        url_for(
            "emprestimos.emprestimo_detalhe",
            emprestimo_id=emprestimo_id,
        )
    )


@emprestimos_bp.route(
    "/simular",
    methods=["POST"]
)
@gerente_obrigatorio
def simular():
    dados = request.get_json(
        silent=True
    ) or {}

    try:
        resultado = (
            EmprestimosService
            .calcular_emprestimo(
                valor_emprestado=(
                    str(
                        dados.get(
                            "valor_emprestado",
                            ""
                        )
                    )
                    .replace(".", "")
                    .replace(",", ".")
                ),

                taxa_juros=(
                    str(
                        dados.get(
                            "taxa_juros",
                            "0"
                        )
                    )
                    .replace(",", ".")
                ),

                quantidade_parcelas=(
                    dados.get(
                        "quantidade_parcelas"
                    )
                ),

                tipo_juros=(
                    dados.get(
                        "tipo_juros",
                        "simples"
                    )
                ),
            )
        )

        return jsonify({
            "sucesso": True,

            "valor_emprestado": str(
                resultado[
                    "valor_emprestado"
                ]
            ),

            "valor_juros": str(
                resultado[
                    "valor_juros"
                ]
            ),

            "valor_total": str(
                resultado[
                    "valor_total"
                ]
            ),

            "valor_parcela": str(
                resultado[
                    "valor_parcela"
                ]
            ),

            "quantidade_parcelas": (
                resultado[
                    "quantidade_parcelas"
                ]
            ),
        })

    except ValueError as erro:

        return jsonify({
            "sucesso": False,
            "erro": str(erro),
        }), 400

    except Exception as erro:
        print(
            "Erro na simulação:",
            erro
        )

        return jsonify({
            "sucesso": False,
            "erro": (
                "Não foi possível realizar "
                "a simulação."
            ),
        }), 500
