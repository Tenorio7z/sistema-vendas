import re

import psycopg2

from flask import (
    flash,
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


def _somente_numeros(valor):
    return re.sub(
        r"\D",
        "",
        str(valor or ""),
    )


def _texto_formulario(nome, limite=None):
    valor = str(
        request.form.get(nome, "") or ""
    ).strip()

    if limite:
        valor = valor[:limite]

    return valor or None


def _validar_cliente(dados):
    if not dados["nome"]:
        return "Informe o nome do cliente."

    if (
        dados["email"]
        and "@" not in dados["email"]
    ):
        return "Informe um e-mail válido."

    cpf_cnpj = dados["cpf_cnpj"]

    if cpf_cnpj and len(cpf_cnpj) not in (11, 14):
        return "O CPF/CNPJ deve possuir 11 ou 14 números."

    telefone = dados["telefone"]

    if telefone and len(telefone) < 10:
        return "Informe um telefone válido com DDD."

    return None


def _obter_dados_cliente():
    return {
        "nome": _texto_formulario(
            "nome",
            150,
        ),
        "telefone": (
            _somente_numeros(
                request.form.get("telefone")
            )[:20]
            or None
        ),
        "email": _texto_formulario(
            "email",
            180,
        ),
        "cpf_cnpj": (
            _somente_numeros(
                request.form.get("cpf_cnpj")
            )[:14]
            or None
        ),
        "data_nascimento": (
            _texto_formulario(
                "data_nascimento",
                10,
            )
        ),
        "endereco": _texto_formulario(
            "endereco",
            255,
        ),
        "numero": _texto_formulario(
            "numero",
            30,
        ),
        "complemento": _texto_formulario(
            "complemento",
            120,
        ),
        "bairro": _texto_formulario(
            "bairro",
            120,
        ),
        "cidade": _texto_formulario(
            "cidade",
            120,
        ),
        "estado": (
            str(
                request.form.get(
                    "estado",
                    "",
                )
                or ""
            )
            .strip()
            .upper()[:2]
            or None
        ),
        "cep": (
            _somente_numeros(
                request.form.get("cep")
            )[:8]
            or None
        ),
        "observacoes": _texto_formulario(
            "observacoes",
            2000,
        ),
    }


def _verificar_login():
    return bool(
        session.get("logado")
        and session.get("empresa_id")
    )


def registrar_rotas(app):

    # ==========================================
    # LISTAR E CADASTRAR CLIENTES
    # ==========================================

    @app.route(
        "/clientes",
        methods=["GET", "POST"],
    )
    def clientes():

        if not _verificar_login():
            return redirect("/")

        empresa_id = session["empresa_id"]

        conexao = conectar()
        cursor = criar_cursor(conexao)

        try:
            if request.method == "POST":
                dados = _obter_dados_cliente()
                erro = _validar_cliente(dados)

                if erro:
                    flash(erro, "erro")
                    return redirect(
                        url_for("clientes")
                    )

                cursor.execute(
                    """
                    INSERT INTO clientes (
                        empresa_id,
                        nome,
                        telefone,
                        email,
                        cpf_cnpj,
                        data_nascimento,
                        endereco,
                        numero,
                        complemento,
                        bairro,
                        cidade,
                        estado,
                        cep,
                        observacoes,
                        ativo
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, TRUE
                    )
                    RETURNING id
                    """,
                    (
                        empresa_id,
                        dados["nome"],
                        dados["telefone"],
                        dados["email"],
                        dados["cpf_cnpj"],
                        dados["data_nascimento"],
                        dados["endereco"],
                        dados["numero"],
                        dados["complemento"],
                        dados["bairro"],
                        dados["cidade"],
                        dados["estado"],
                        dados["cep"],
                        dados["observacoes"],
                    ),
                )

                cliente_criado = cursor.fetchone()

                conexao.commit()

                flash(
                    "Cliente cadastrado com sucesso.",
                    "sucesso",
                )

                return redirect(
                    url_for(
                        "clientes",
                        destaque=cliente_criado["id"],
                    )
                )

            pesquisa = str(
                request.args.get("q", "") or ""
            ).strip()

            status = str(
                request.args.get(
                    "status",
                    "ativos",
                )
                or "ativos"
            ).lower()

            parametros = [empresa_id]

            filtros = [
                "c.empresa_id = %s"
            ]

            if status == "ativos":
                filtros.append(
                    "c.ativo = TRUE"
                )

            elif status == "inativos":
                filtros.append(
                    "c.ativo = FALSE"
                )

            if pesquisa:
                termo = f"%{pesquisa}%"

                filtros.append(
                    """
                    (
                        c.nome ILIKE %s
                        OR COALESCE(c.telefone, '') ILIKE %s
                        OR COALESCE(c.email, '') ILIKE %s
                        OR COALESCE(c.cpf_cnpj, '') ILIKE %s
                    )
                    """
                )

                parametros.extend(
                    [
                        termo,
                        termo,
                        termo,
                        termo,
                    ]
                )

            cursor.execute(
                f"""
                SELECT
                    c.id,
                    c.nome,
                    c.telefone,
                    c.email,
                    c.cpf_cnpj,
                    c.data_nascimento,
                    c.endereco,
                    c.numero,
                    c.complemento,
                    c.bairro,
                    c.cidade,
                    c.estado,
                    c.cep,
                    c.observacoes,
                    c.ativo,
                    c.criado_em,

                    COUNT(
                        DISTINCT COALESCE(
                            v.venda_grupo,
                            v.id::TEXT
                        )
                    ) FILTER (
                        WHERE COALESCE(
                            v.cancelada,
                            0
                        ) = 0
                    ) AS total_compras,

                    COALESCE(
                        SUM(v.valor) FILTER (
                            WHERE COALESCE(
                                v.cancelada,
                                0
                            ) = 0
                        ),
                        0
                    ) AS total_gasto,

                    MAX(v.data_venda) FILTER (
                        WHERE COALESCE(
                            v.cancelada,
                            0
                        ) = 0
                    ) AS ultima_compra

                FROM clientes c

                LEFT JOIN vendas v
                    ON v.cliente_id = c.id
                    AND v.empresa_id = c.empresa_id

                WHERE {" AND ".join(filtros)}

                GROUP BY c.id

                ORDER BY
                    c.ativo DESC,
                    c.nome ASC
                """,
                tuple(parametros),
            )

            clientes_cadastrados = (
                cursor.fetchall()
            )

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,

                    COUNT(*) FILTER (
                        WHERE ativo = TRUE
                    ) AS ativos,

                    COUNT(*) FILTER (
                        WHERE ativo = FALSE
                    ) AS inativos

                FROM clientes

                WHERE empresa_id = %s
                """,
                (empresa_id,),
            )

            resumo = cursor.fetchone()

            return render_template(
                "clientes.html",
                clientes=clientes_cadastrados,
                resumo=resumo,
                pesquisa=pesquisa,
                status=status,
            )

        except psycopg2.errors.UniqueViolation:
            conexao.rollback()

            flash(
                (
                    "Já existe um cliente com esse "
                    "CPF/CNPJ nesta empresa."
                ),
                "erro",
            )

            return redirect(
                url_for("clientes")
            )

        except Exception:
            conexao.rollback()
            raise

        finally:
            cursor.close()
            conexao.close()
            
            
    # ==========================================
    # DETALHES E HISTÓRICO DO CLIENTE
    # ==========================================

    @app.route(
        "/clientes/<int:cliente_id>",
        methods=["GET"],
    )
    def detalhes_cliente(cliente_id):

        if not _verificar_login():
            return redirect("/")

        empresa_id = session["empresa_id"]

        conexao = conectar()
        cursor = criar_cursor(conexao)

        try:
            # ======================================
            # DADOS DO CLIENTE
            # ======================================

            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    telefone,
                    email,
                    cpf_cnpj,
                    data_nascimento,
                    endereco,
                    numero,
                    complemento,
                    bairro,
                    cidade,
                    estado,
                    cep,
                    observacoes,
                    ativo,
                    criado_em,
                    atualizado_em

                FROM clientes

                WHERE id = %s
                  AND empresa_id = %s

                LIMIT 1
                """,
                (
                    cliente_id,
                    empresa_id,
                ),
            )

            cliente = cursor.fetchone()

            if not cliente:
                flash(
                    "Cliente não encontrado.",
                    "erro",
                )

                return redirect(
                    url_for("clientes")
                )

            # ======================================
            # RESUMO FINANCEIRO
            # ======================================

            cursor.execute(
                """
                SELECT
                    COUNT(
                        DISTINCT COALESCE(
                            venda_grupo,
                            'venda-' || id::TEXT
                        )
                    ) FILTER (
                        WHERE COALESCE(
                            cancelada,
                            0
                        ) = 0
                    ) AS total_compras,

                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE COALESCE(
                                cancelada,
                                0
                            ) = 0
                        ),
                        0
                    ) AS total_gasto,

                    COALESCE(
                        SUM(
                            COALESCE(
                                valor_bruto,
                                valor
                            )
                        ) FILTER (
                            WHERE COALESCE(
                                cancelada,
                                0
                            ) = 0
                        ),
                        0
                    ) AS total_bruto,

                    COALESCE(
                        SUM(
                            COALESCE(
                                desconto_valor,
                                0
                            )
                        ) FILTER (
                            WHERE COALESCE(
                                cancelada,
                                0
                            ) = 0
                        ),
                        0
                    ) AS total_descontos,

                    COALESCE(
                        SUM(quantidade) FILTER (
                            WHERE COALESCE(
                                cancelada,
                                0
                            ) = 0
                        ),
                        0
                    ) AS itens_comprados,

                    COUNT(
                        DISTINCT COALESCE(
                            venda_grupo,
                            'venda-' || id::TEXT
                        )
                    ) FILTER (
                        WHERE COALESCE(
                            cancelada,
                            0
                        ) <> 0
                    ) AS compras_canceladas,

                    MAX(data_venda) FILTER (
                        WHERE COALESCE(
                            cancelada,
                            0
                        ) = 0
                    ) AS ultima_compra

                FROM vendas

                WHERE empresa_id = %s
                  AND cliente_id = %s
                """,
                (
                    empresa_id,
                    cliente_id,
                ),
            )

            resumo = cursor.fetchone()

            total_compras = int(
                resumo["total_compras"] or 0
            )

            total_gasto = float(
                resumo["total_gasto"] or 0
            )

            ticket_medio = (
                total_gasto / total_compras
                if total_compras > 0
                else 0
            )

            resumo["ticket_medio"] = (
                ticket_medio
            )

            # ======================================
            # PRODUTOS MAIS COMPRADOS
            # ======================================

            cursor.execute(
                """
                SELECT
                    p.id,
                    p.nome,

                    SUM(v.quantidade) AS quantidade,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS total_gasto,

                    COUNT(
                        DISTINCT COALESCE(
                            v.venda_grupo,
                            'venda-' || v.id::TEXT
                        )
                    ) AS total_compras

                FROM vendas v

                INNER JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND v.cliente_id = %s
                  AND COALESCE(
                        v.cancelada,
                        0
                      ) = 0

                GROUP BY
                    p.id,
                    p.nome

                ORDER BY
                    quantidade DESC,
                    total_gasto DESC,
                    p.nome ASC

                LIMIT 8
                """,
                (
                    empresa_id,
                    cliente_id,
                ),
            )

            produtos_preferidos = (
                cursor.fetchall()
            )

            # ======================================
            # HISTÓRICO AGRUPADO POR VENDA
            # ======================================

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        v.venda_grupo,
                        'venda-' || v.id::TEXT
                    ) AS venda_grupo,

                    MIN(v.id) AS venda_id,

                    MAX(v.data_venda) AS data_venda,

                    MAX(v.pagamento) AS pagamento,

                    MAX(
                        COALESCE(
                            u.usuario,
                            'Sistema'
                        )
                    ) AS vendedor,

                    SUM(v.quantidade) AS quantidade_itens,

                    COALESCE(
                        SUM(
                            COALESCE(
                                v.valor_bruto,
                                v.valor
                            )
                        ),
                        0
                    ) AS valor_bruto,

                    COALESCE(
                        SUM(
                            COALESCE(
                                v.desconto_valor,
                                0
                            )
                        ),
                        0
                    ) AS desconto,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS valor_total,

                    BOOL_OR(
                        COALESCE(
                            v.cancelada,
                            0
                        ) <> 0
                    ) AS cancelada,

                    JSON_AGG(
                        JSON_BUILD_OBJECT(
                            'produto_id',
                            p.id,

                            'produto',
                            COALESCE(
                                p.nome,
                                'Produto removido'
                            ),

                            'quantidade',
                            v.quantidade,

                            'valor_bruto',
                            COALESCE(
                                v.valor_bruto,
                                v.valor
                            ),

                            'desconto',
                            COALESCE(
                                v.desconto_valor,
                                0
                            ),

                            'valor',
                            v.valor
                        )

                        ORDER BY v.id ASC
                    ) AS itens

                FROM vendas v

                LEFT JOIN produtos p
                    ON p.id = v.produto_id
                   AND p.empresa_id = v.empresa_id

                LEFT JOIN usuarios u
                    ON u.id = v.usuario_id
                   AND u.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND v.cliente_id = %s

                GROUP BY
                    COALESCE(
                        v.venda_grupo,
                        'venda-' || v.id::TEXT
                    )

                ORDER BY
                    MAX(v.data_venda) DESC,
                    MIN(v.id) DESC

                LIMIT 100
                """,
                (
                    empresa_id,
                    cliente_id,
                ),
            )

            historico = cursor.fetchall()

            # ======================================
            # FORMA DE PAGAMENTO FAVORITA
            # ======================================

            cursor.execute(
                """
                SELECT
                    pagamento,
                    COUNT(
                        DISTINCT COALESCE(
                            venda_grupo,
                            'venda-' || id::TEXT
                        )
                    ) AS total

                FROM vendas

                WHERE empresa_id = %s
                  AND cliente_id = %s
                  AND COALESCE(
                        cancelada,
                        0
                      ) = 0

                GROUP BY pagamento

                ORDER BY total DESC

                LIMIT 1
                """,
                (
                    empresa_id,
                    cliente_id,
                ),
            )

            pagamento_favorito = (
                cursor.fetchone()
            )

            return render_template(
                "cliente_detalhes.html",
                cliente=cliente,
                resumo=resumo,
                produtos_preferidos=produtos_preferidos,
                historico=historico,
                pagamento_favorito=pagamento_favorito,
            )

        except Exception:
            conexao.rollback()
            raise

        finally:
            cursor.close()
            conexao.close()

    # ==========================================
    # EDITAR CLIENTE
    # ==========================================

    @app.route(
        "/clientes/<int:cliente_id>/editar",
        methods=["POST"],
    )
    def editar_cliente(cliente_id):

        if not _verificar_login():
            return redirect("/")

        empresa_id = session["empresa_id"]
        dados = _obter_dados_cliente()
        erro = _validar_cliente(dados)

        if erro:
            flash(erro, "erro")

            return redirect(
                url_for("clientes")
            )

        conexao = conectar()
        cursor = criar_cursor(conexao)

        try:
            cursor.execute(
                """
                UPDATE clientes

                SET
                    nome = %s,
                    telefone = %s,
                    email = %s,
                    cpf_cnpj = %s,
                    data_nascimento = %s,
                    endereco = %s,
                    numero = %s,
                    complemento = %s,
                    bairro = %s,
                    cidade = %s,
                    estado = %s,
                    cep = %s,
                    observacoes = %s,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    dados["nome"],
                    dados["telefone"],
                    dados["email"],
                    dados["cpf_cnpj"],
                    dados["data_nascimento"],
                    dados["endereco"],
                    dados["numero"],
                    dados["complemento"],
                    dados["bairro"],
                    dados["cidade"],
                    dados["estado"],
                    dados["cep"],
                    dados["observacoes"],
                    cliente_id,
                    empresa_id,
                ),
            )

            if cursor.rowcount == 0:
                conexao.rollback()

                flash(
                    "Cliente não encontrado.",
                    "erro",
                )

                return redirect(
                    url_for("clientes")
                )

            conexao.commit()

            flash(
                "Cliente atualizado com sucesso.",
                "sucesso",
            )

        except psycopg2.errors.UniqueViolation:
            conexao.rollback()

            flash(
                (
                    "Já existe outro cliente com "
                    "esse CPF/CNPJ."
                ),
                "erro",
            )

        except Exception:
            conexao.rollback()
            raise

        finally:
            cursor.close()
            conexao.close()

        return redirect(
            url_for(
                "clientes",
                destaque=cliente_id,
            )
        )

    # ==========================================
    # ATIVAR OU DESATIVAR CLIENTE
    # ==========================================

    @app.route(
        "/clientes/<int:cliente_id>/status",
        methods=["POST"],
    )
    def alterar_status_cliente(cliente_id):

        if not _verificar_login():
            return redirect("/")

        empresa_id = session["empresa_id"]

        conexao = conectar()
        cursor = criar_cursor(conexao)

        try:
            cursor.execute(
                """
                UPDATE clientes

                SET
                    ativo = NOT ativo,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s

                RETURNING ativo
                """,
                (
                    cliente_id,
                    empresa_id,
                ),
            )

            cliente = cursor.fetchone()

            if not cliente:
                conexao.rollback()

                flash(
                    "Cliente não encontrado.",
                    "erro",
                )

                return redirect(
                    url_for("clientes")
                )

            conexao.commit()

            mensagem = (
                "Cliente ativado com sucesso."
                if cliente["ativo"]
                else "Cliente desativado com sucesso."
            )

            flash(
                mensagem,
                "sucesso",
            )

        except Exception:
            conexao.rollback()
            raise

        finally:
            cursor.close()
            conexao.close()

        return redirect(
            url_for(
                "clientes",
                destaque=cliente_id,
            )
        )