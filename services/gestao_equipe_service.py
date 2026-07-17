from calendar import monthrange
from datetime import date, datetime
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)

from database import (
    conectar,
    criar_cursor,
)


ZERO = Decimal("0.00")


class GestaoEquipeService:

    FORMAS_PAGAMENTO = {
        "pix",
        "dinheiro",
        "transferencia",
        "cartao",
        "outro",
    }

    STATUS_FOLHA = {
        "pendente",
        "pago",
        "cancelado",
    }

    @staticmethod
    def _decimal(
        valor,
        padrao="0.00",
    ):
        if valor in (
            None,
            "",
        ):
            valor = padrao

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

        try:
            resultado = Decimal(
                str(valor)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ):
            raise ValueError(
                "Valor monetário inválido."
            )

        return resultado.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _inteiro(
        valor,
        padrao=0,
    ):
        try:
            return int(valor)

        except (
            TypeError,
            ValueError,
        ):
            return padrao

    @staticmethod
    def _competencia(
        valor=None,
    ):
        if not valor:
            hoje = date.today()

            return date(
                hoje.year,
                hoje.month,
                1,
            )

        if isinstance(
            valor,
            date
        ):
            return date(
                valor.year,
                valor.month,
                1,
            )

        texto = str(
            valor
        ).strip()

        formatos = (
            "%Y-%m",
            "%Y-%m-%d",
            "%m/%Y",
        )

        for formato in formatos:
            try:
                data_convertida = (
                    datetime.strptime(
                        texto,
                        formato,
                    ).date()
                )

                return date(
                    data_convertida.year,
                    data_convertida.month,
                    1,
                )

            except ValueError:
                continue

        raise ValueError(
            (
                "Competência inválida. "
                "Utilize AAAA-MM."
            )
        )

    @staticmethod
    def _periodo_competencia(
        competencia,
    ):
        competencia = (
            GestaoEquipeService._competencia(
                competencia
            )
        )

        ultimo_dia = monthrange(
            competencia.year,
            competencia.month,
        )[1]

        inicio = competencia

        fim = date(
            competencia.year,
            competencia.month,
            ultimo_dia,
        )

        return inicio, fim

    @staticmethod
    def _verificar_funcionario(
        cursor,
        empresa_id,
        usuario_id,
    ):
        cursor.execute(
            """
            SELECT
                id,
                usuario,
                nivel,
                status,
                empresa_id,
                COALESCE(
                    comissao,
                    0
                ) AS comissao

            FROM usuarios

            WHERE id = %s
              AND empresa_id = %s
              AND nivel = 'funcionario'

            LIMIT 1
            """,
            (
                usuario_id,
                empresa_id,
            )
        )

        funcionario = cursor.fetchone()

        if not funcionario:
            raise ValueError(
                "Funcionário não encontrado."
            )

        return funcionario

    # ==========================================
    # RESUMO DA EQUIPE
    # ==========================================

    @classmethod
    def resumo_equipe(
        cls,
        empresa_id,
        competencia=None,
    ):
        competencia = cls._competencia(
            competencia
        )

        inicio, fim = (
            cls._periodo_competencia(
                competencia
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'ativo'
                    ) AS funcionarios_ativos,

                    COUNT(*) FILTER (
                        WHERE status = 'bloqueado'
                    ) AS funcionarios_bloqueados,

                    COUNT(*) AS total_funcionarios

                FROM usuarios

                WHERE empresa_id = %s
                  AND nivel = 'funcionario'
                """,
                (
                    empresa_id,
                )
            )

            funcionarios = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS registros_venda,

                    COALESCE(
                        SUM(quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(valor),
                        0
                    ) AS faturamento_equipe

                FROM vendas

                WHERE empresa_id = %s
                  AND COALESCE(
                      cancelada,
                      0
                  ) = 0
                  AND usuario_id IN (
                      SELECT id
                      FROM usuarios
                      WHERE empresa_id = %s
                        AND nivel = 'funcionario'
                  )
                  AND DATE(
                      COALESCE(
                          data_venda,
                          data
                      )
                  ) BETWEEN %s AND %s
                """,
                (
                    empresa_id,
                    empresa_id,
                    inicio,
                    fim,
                )
            )

            vendas = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(
                            v.valor
                            * COALESCE(
                                u.comissao,
                                0
                            )
                            / 100
                        ),
                        0
                    ) AS comissoes_geradas

                FROM vendas v

                INNER JOIN usuarios u
                    ON u.id = v.usuario_id
                   AND u.empresa_id = v.empresa_id

                WHERE v.empresa_id = %s
                  AND u.nivel = 'funcionario'
                  AND COALESCE(
                      v.cancelada,
                      0
                  ) = 0
                  AND DATE(
                      COALESCE(
                          v.data_venda,
                          v.data
                      )
                  ) BETWEEN %s AND %s
                """,
                (
                    empresa_id,
                    inicio,
                    fim,
                )
            )

            comissoes = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'pendente'
                    ) AS folhas_pendentes,

                    COUNT(*) FILTER (
                        WHERE status = 'pago'
                    ) AS folhas_pagas,

                    COALESCE(
                        SUM(valor_total) FILTER (
                            WHERE status = 'pendente'
                        ),
                        0
                    ) AS total_pendente,

                    COALESCE(
                        SUM(valor_total) FILTER (
                            WHERE status = 'pago'
                        ),
                        0
                    ) AS total_pago,

                    COALESCE(
                        SUM(salario_base) FILTER (
                            WHERE status <> 'cancelado'
                        ),
                        0
                    ) AS salarios_calculados,

                    COALESCE(
                        SUM(valor_comissao) FILTER (
                            WHERE status <> 'cancelado'
                        ),
                        0
                    ) AS comissoes_na_folha

                FROM folha_pagamentos

                WHERE empresa_id = %s
                  AND competencia = %s
                """,
                (
                    empresa_id,
                    competencia,
                )
            )

            folha = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE status = 'paga'
                        ),
                        0
                    ) AS despesas_pagas,

                    COALESCE(
                        SUM(valor) FILTER (
                            WHERE status = 'pendente'
                        ),
                        0
                    ) AS despesas_pendentes

                FROM despesas_empresa

                WHERE empresa_id = %s
                  AND competencia = %s
                  AND folha_pagamento_id IS NULL
                  AND status <> 'cancelada'
                """,
                (
                    empresa_id,
                    competencia,
                )
            )

            despesas = cursor.fetchone()

            faturamento = cls._decimal(
                vendas["faturamento_equipe"]
            )

            total_pago = cls._decimal(
                folha["total_pago"]
            )

            despesas_pagas = cls._decimal(
                despesas["despesas_pagas"]
            )

            resultado_operacional = (
                faturamento
                - total_pago
                - despesas_pagas
            ).quantize(
                Decimal("0.01")
            )

            return {
                "competencia": competencia,
                "periodo_inicio": inicio,
                "periodo_fim": fim,
                "funcionarios": funcionarios,
                "vendas": vendas,
                "comissoes": comissoes,
                "folha": folha,
                "despesas": despesas,
                "resultado_operacional": (
                    resultado_operacional
                ),
            }

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # LISTAGEM DOS FUNCIONÁRIOS
    # ==========================================

    @classmethod
    def listar_funcionarios(
        cls,
        empresa_id,
        competencia=None,
    ):
        competencia = cls._competencia(
            competencia
        )

        inicio, fim = (
            cls._periodo_competencia(
                competencia
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    u.id,
                    u.usuario,
                    u.status,

                    CASE
                        WHEN u.foto IS NOT NULL
                        THEN TRUE
                        ELSE FALSE
                    END AS possui_foto,

                    COALESCE(
                        u.comissao,
                        0
                    ) AS percentual_comissao,

                    COALESCE(
                        fc.cargo,
                        'Funcionário'
                    ) AS cargo,

                    COALESCE(
                        fc.salario_base,
                        0
                    ) AS salario_base,

                    COALESCE(
                        fc.dia_pagamento,
                        5
                    ) AS dia_pagamento,

                    fc.data_admissao,

                    COUNT(v.id)
                        AS registros_venda,

                    COALESCE(
                        SUM(v.quantidade),
                        0
                    ) AS itens_vendidos,

                    COALESCE(
                        SUM(v.valor),
                        0
                    ) AS faturamento,

                    ROUND(
                        (
                            COALESCE(
                                SUM(v.valor),
                                0
                            )
                            * COALESCE(
                                u.comissao,
                                0
                            )
                            / 100
                        )::numeric,
                        2
                    ) AS comissao_gerada,

                    fp.id AS folha_id,
                    fp.status AS folha_status,

                    COALESCE(
                        fp.valor_total,
                        0
                    ) AS folha_total,

                    fp.data_pagamento

                FROM usuarios u

                LEFT JOIN funcionarios_config fc
                    ON fc.usuario_id = u.id
                   AND fc.empresa_id = u.empresa_id

                LEFT JOIN vendas v
                    ON v.usuario_id = u.id
                   AND v.empresa_id = u.empresa_id
                   AND COALESCE(
                       v.cancelada,
                       0
                   ) = 0
                   AND DATE(
                       COALESCE(
                           v.data_venda,
                           v.data
                       )
                   ) BETWEEN %s AND %s

                LEFT JOIN folha_pagamentos fp
                    ON fp.usuario_id = u.id
                   AND fp.empresa_id = u.empresa_id
                   AND fp.competencia = %s

                WHERE u.empresa_id = %s
                  AND u.nivel = 'funcionario'

                GROUP BY
                    u.id,
                    u.usuario,
                    u.status,
                    u.foto,
                    u.comissao,
                    fc.cargo,
                    fc.salario_base,
                    fc.dia_pagamento,
                    fc.data_admissao,
                    fp.id,
                    fp.status,
                    fp.valor_total,
                    fp.data_pagamento

                ORDER BY
                    faturamento DESC,
                    u.usuario ASC
                """,
                (
                    inicio,
                    fim,
                    competencia,
                    empresa_id,
                )
            )

            funcionarios = cursor.fetchall()

            return {
                "competencia": competencia,
                "periodo_inicio": inicio,
                "periodo_fim": fim,
                "funcionarios": funcionarios,
            }

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # CONFIGURAÇÃO DO FUNCIONÁRIO
    # ==========================================

    @classmethod
    def salvar_configuracao(
        cls,
        empresa_id,
        usuario_id,
        cargo,
        salario_base,
        dia_pagamento,
        data_admissao=None,
        observacoes=None,
    ):
        cargo = str(
            cargo or "Funcionário"
        ).strip()[:100]

        salario_base = cls._decimal(
            salario_base
        )

        dia_pagamento = cls._inteiro(
            dia_pagamento,
            5,
        )

        if salario_base < ZERO:
            raise ValueError(
                "O salário não pode ser negativo."
            )

        if not 1 <= dia_pagamento <= 31:
            raise ValueError(
                (
                    "O dia de pagamento deve "
                    "estar entre 1 e 31."
                )
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cls._verificar_funcionario(
                cursor,
                empresa_id,
                usuario_id,
            )

            cursor.execute(
                """
                INSERT INTO funcionarios_config (
                    empresa_id,
                    usuario_id,
                    cargo,
                    salario_base,
                    dia_pagamento,
                    data_admissao,
                    observacoes
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT (
                    empresa_id,
                    usuario_id
                )
                DO UPDATE SET
                    cargo = EXCLUDED.cargo,
                    salario_base = EXCLUDED.salario_base,
                    dia_pagamento = EXCLUDED.dia_pagamento,
                    data_admissao = EXCLUDED.data_admissao,
                    observacoes = EXCLUDED.observacoes,
                    atualizado_em = CURRENT_TIMESTAMP

                RETURNING *
                """,
                (
                    empresa_id,
                    usuario_id,
                    cargo,
                    salario_base,
                    dia_pagamento,
                    data_admissao or None,
                    (
                        str(observacoes).strip()
                        if observacoes
                        else None
                    ),
                )
            )

            configuracao = cursor.fetchone()

            conn.commit()

            return configuracao

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # CALCULAR COMISSÃO DO PERÍODO
    # ==========================================

    @classmethod
    def calcular_comissao(
        cls,
        cursor,
        empresa_id,
        usuario_id,
        competencia,
    ):
        inicio, fim = (
            cls._periodo_competencia(
                competencia
            )
        )

        cursor.execute(
            """
            SELECT
                COALESCE(
                    u.comissao,
                    0
                ) AS percentual,

                COALESCE(
                    SUM(v.valor),
                    0
                ) AS faturamento,

                ROUND(
                    (
                        COALESCE(
                            SUM(v.valor),
                            0
                        )
                        * COALESCE(
                            u.comissao,
                            0
                        )
                        / 100
                    )::numeric,
                    2
                ) AS valor_comissao

            FROM usuarios u

            LEFT JOIN vendas v
                ON v.usuario_id = u.id
               AND v.empresa_id = u.empresa_id
               AND COALESCE(
                   v.cancelada,
                   0
               ) = 0
               AND DATE(
                   COALESCE(
                       v.data_venda,
                       v.data
                   )
               ) BETWEEN %s AND %s

            WHERE u.id = %s
              AND u.empresa_id = %s
              AND u.nivel = 'funcionario'

            GROUP BY
                u.id,
                u.comissao
            """,
            (
                inicio,
                fim,
                usuario_id,
                empresa_id,
            )
        )

        dados = cursor.fetchone()

        if not dados:
            raise ValueError(
                "Funcionário não encontrado."
            )

        return dados

    # ==========================================
    # GERAR OU ATUALIZAR FOLHA
    # ==========================================

    @classmethod
    def gerar_folha(
        cls,
        empresa_id,
        usuario_id,
        registrado_por,
        competencia=None,
        bonus=0,
        descontos=0,
        observacoes=None,
    ):
        competencia = cls._competencia(
            competencia
        )

        bonus = cls._decimal(
            bonus
        )

        descontos = cls._decimal(
            descontos
        )

        if (
            bonus < ZERO
            or descontos < ZERO
        ):
            raise ValueError(
                (
                    "Bônus e descontos não podem "
                    "ser negativos."
                )
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            funcionario = (
                cls._verificar_funcionario(
                    cursor,
                    empresa_id,
                    usuario_id,
                )
            )

            cursor.execute(
                """
                SELECT
                    salario_base,
                    dia_pagamento

                FROM funcionarios_config

                WHERE empresa_id = %s
                  AND usuario_id = %s

                LIMIT 1
                """,
                (
                    empresa_id,
                    usuario_id,
                )
            )

            configuracao = cursor.fetchone()

            salario_base = cls._decimal(
                (
                    configuracao["salario_base"]
                    if configuracao
                    else 0
                )
            )

            dia_pagamento = (
                configuracao["dia_pagamento"]
                if configuracao
                else 5
            )

            comissao = cls.calcular_comissao(
                cursor,
                empresa_id,
                usuario_id,
                competencia,
            )

            valor_comissao = cls._decimal(
                comissao["valor_comissao"]
            )

            valor_total = (
                salario_base
                + valor_comissao
                + bonus
                - descontos
            )

            if valor_total < ZERO:
                valor_total = ZERO

            ultimo_dia = monthrange(
                competencia.year,
                competencia.month,
            )[1]

            vencimento = date(
                competencia.year,
                competencia.month,
                min(
                    dia_pagamento,
                    ultimo_dia,
                ),
            )

            cursor.execute(
                """
                SELECT
                    id,
                    status

                FROM folha_pagamentos

                WHERE empresa_id = %s
                  AND usuario_id = %s
                  AND competencia = %s

                FOR UPDATE
                """,
                (
                    empresa_id,
                    usuario_id,
                    competencia,
                )
            )

            folha_existente = cursor.fetchone()

            if (
                folha_existente
                and folha_existente["status"]
                == "pago"
            ):
                raise ValueError(
                    (
                        "Esta folha já foi paga e "
                        "não pode ser recalculada."
                    )
                )

            cursor.execute(
                """
                INSERT INTO folha_pagamentos (
                    empresa_id,
                    usuario_id,
                    registrado_por,
                    competencia,
                    salario_base,
                    valor_comissao,
                    valor_bonus,
                    valor_descontos,
                    valor_total,
                    status,
                    data_vencimento,
                    observacoes
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'pendente',
                    %s,
                    %s
                )

                ON CONFLICT (
                    empresa_id,
                    usuario_id,
                    competencia
                )
                DO UPDATE SET
                    registrado_por = EXCLUDED.registrado_por,
                    salario_base = EXCLUDED.salario_base,
                    valor_comissao = EXCLUDED.valor_comissao,
                    valor_bonus = EXCLUDED.valor_bonus,
                    valor_descontos = EXCLUDED.valor_descontos,
                    valor_total = EXCLUDED.valor_total,
                    data_vencimento = EXCLUDED.data_vencimento,
                    observacoes = EXCLUDED.observacoes,
                    status = 'pendente',
                    atualizado_em = CURRENT_TIMESTAMP

                RETURNING *
                """,
                (
                    empresa_id,
                    usuario_id,
                    registrado_por,
                    competencia,
                    salario_base,
                    valor_comissao,
                    bonus,
                    descontos,
                    valor_total,
                    vencimento,
                    (
                        str(observacoes).strip()
                        if observacoes
                        else None
                    ),
                )
            )

            folha = cursor.fetchone()

            conn.commit()

            return {
                "funcionario": funcionario,
                "faturamento": (
                    comissao["faturamento"]
                ),
                "percentual_comissao": (
                    comissao["percentual"]
                ),
                "folha": folha,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # REGISTRAR PAGAMENTO
    # ==========================================

    @classmethod
    def registrar_pagamento(
        cls,
        empresa_id,
        folha_id,
        registrado_por,
        forma_pagamento,
        registrar_no_caixa=False,
        observacoes=None,
    ):
        forma_pagamento = str(
            forma_pagamento or ""
        ).strip().lower()

        if (
            forma_pagamento
            not in cls.FORMAS_PAGAMENTO
        ):
            raise ValueError(
                "Forma de pagamento inválida."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    fp.*,
                    u.usuario

                FROM folha_pagamentos fp

                INNER JOIN usuarios u
                    ON u.id = fp.usuario_id
                   AND u.empresa_id = fp.empresa_id

                WHERE fp.id = %s
                  AND fp.empresa_id = %s

                FOR UPDATE
                """,
                (
                    folha_id,
                    empresa_id,
                )
            )

            folha = cursor.fetchone()

            if not folha:
                raise ValueError(
                    "Folha de pagamento não encontrada."
                )

            if folha["status"] == "pago":
                raise ValueError(
                    "Esta folha já foi paga."
                )

            if folha["status"] == "cancelado":
                raise ValueError(
                    (
                        "Uma folha cancelada não pode "
                        "ser paga."
                    )
                )

            caixa_id = None

            if registrar_no_caixa:
                cursor.execute(
                    """
                    SELECT id

                    FROM caixa

                    WHERE empresa_id = %s
                      AND status = 'aberto'

                    ORDER BY id DESC

                    LIMIT 1

                    FOR UPDATE
                    """,
                    (
                        empresa_id,
                    )
                )

                caixa = cursor.fetchone()

                if not caixa:
                    raise ValueError(
                        (
                            "Não existe caixa aberto para "
                            "registrar esta saída."
                        )
                    )

                caixa_id = caixa["id"]

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
                            "Pagamento da folha de "
                            f"{folha['usuario']} — "
                            f"{folha['competencia']:%m/%Y}"
                        ),
                        folha["valor_total"],
                        empresa_id,
                        caixa_id,
                    )
                )

            cursor.execute(
                """
                UPDATE folha_pagamentos

                SET
                    status = 'pago',
                    forma_pagamento = %s,
                    data_pagamento = CURRENT_TIMESTAMP,
                    caixa_id = %s,
                    observacoes = COALESCE(
                        %s,
                        observacoes
                    ),
                    registrado_por = %s,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s

                RETURNING *
                """,
                (
                    forma_pagamento,
                    caixa_id,
                    (
                        str(observacoes).strip()
                        if observacoes
                        else None
                    ),
                    registrado_por,
                    folha_id,
                    empresa_id,
                )
            )

            folha_paga = cursor.fetchone()

            cursor.execute(
                """
                INSERT INTO despesas_empresa (
                    empresa_id,
                    registrado_por,
                    categoria,
                    descricao,
                    valor,
                    competencia,
                    data_vencimento,
                    data_pagamento,
                    forma_pagamento,
                    status,
                    recorrente,
                    observacoes,
                    folha_pagamento_id,
                    caixa_id
                )
                VALUES (
                    %s,
                    %s,
                    'folha',
                    %s,
                    %s,
                    %s,
                    %s,
                    CURRENT_TIMESTAMP,
                    %s,
                    'paga',
                    FALSE,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    empresa_id,
                    registrado_por,
                    (
                        "Folha de pagamento — "
                        f"{folha['usuario']} — "
                        f"{folha['competencia']:%m/%Y}"
                    ),
                    folha["valor_total"],
                    folha["competencia"],
                    folha["data_vencimento"],
                    forma_pagamento,
                    (
                        str(observacoes).strip()
                        if observacoes
                        else None
                    ),
                    folha_id,
                    caixa_id,
                )
            )

            conn.commit()

            return folha_paga

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # ==========================================
    # HISTÓRICO DA FOLHA
    # ==========================================

    @staticmethod
    def historico_pagamentos(
        empresa_id,
        usuario_id=None,
        limite=100,
    ):
        try:
            limite = int(
                limite
            )

        except (
            TypeError,
            ValueError,
        ):
            limite = 100

        limite = max(
            1,
            min(limite, 500)
        )

        condicao_usuario = ""

        parametros = [
            empresa_id,
        ]

        if usuario_id:
            condicao_usuario = (
                "AND fp.usuario_id = %s"
            )

            parametros.append(
                usuario_id
            )

        parametros.append(
            limite
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    fp.*,
                    u.usuario,
                    COALESCE(
                        fc.cargo,
                        'Funcionário'
                    ) AS cargo

                FROM folha_pagamentos fp

                INNER JOIN usuarios u
                    ON u.id = fp.usuario_id
                   AND u.empresa_id = fp.empresa_id

                LEFT JOIN funcionarios_config fc
                    ON fc.usuario_id = fp.usuario_id
                   AND fc.empresa_id = fp.empresa_id

                WHERE fp.empresa_id = %s
                  {condicao_usuario}

                ORDER BY
                    fp.competencia DESC,
                    fp.id DESC

                LIMIT %s
                """,
                parametros
            )

            return cursor.fetchall()

        finally:
            cursor.close()
            conn.close()