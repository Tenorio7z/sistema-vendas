import calendar

from datetime import (
    date,
    datetime,
    timedelta,
)

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from database import (
    conectar,
    criar_cursor,
)


CENTAVOS = Decimal("0.01")


def _decimal(valor):
    try:
        return Decimal(
            str(valor)
        ).quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

    except Exception:
        raise ValueError(
            "Valor monetário inválido."
        )


def _taxa(valor):
    try:
        taxa = Decimal(
            str(valor or 0)
        )

    except Exception:
        raise ValueError(
            "Taxa de juros inválida."
        )

    if taxa < 0:
        raise ValueError(
            "A taxa não pode ser negativa."
        )

    return taxa


def _adicionar_meses(
    data_original,
    quantidade,
):
    mes_inicial = (
        data_original.month
        - 1
        + quantidade
    )

    ano = (
        data_original.year
        + mes_inicial // 12
    )

    mes = (
        mes_inicial % 12
        + 1
    )

    ultimo_dia = calendar.monthrange(
        ano,
        mes
    )[1]

    dia = min(
        data_original.day,
        ultimo_dia
    )

    return date(
        ano,
        mes,
        dia
    )


def _calcular_vencimento(
    primeira_parcela,
    numero,
    frequencia,
):
    deslocamento = numero - 1

    if frequencia == "semanal":
        return (
            primeira_parcela
            + timedelta(
                days=7 * deslocamento
            )
        )

    if frequencia == "quinzenal":
        return (
            primeira_parcela
            + timedelta(
                days=15 * deslocamento
            )
        )

    if frequencia == "mensal":
        return _adicionar_meses(
            primeira_parcela,
            deslocamento
        )

    raise ValueError(
        "Frequência inválida."
    )


class EmprestimosService:

    FREQUENCIAS = (
        "semanal",
        "quinzenal",
        "mensal",
    )

    TIPOS_JUROS = (
        "simples",
        "composto",
    )

    FORMAS_PAGAMENTO = (
        "dinheiro",
        "pix",
        "cartao",
        "transferencia",
        "boleto",
        "outro",
    )

    @staticmethod
    def calcular_emprestimo(
        valor_emprestado,
        taxa_juros,
        quantidade_parcelas,
        tipo_juros="simples",
    ):
        valor = _decimal(
            valor_emprestado
        )

        taxa = _taxa(
            taxa_juros
        )

        try:
            parcelas = int(
                quantidade_parcelas
            )

        except Exception:
            raise ValueError(
                "Quantidade de parcelas inválida."
            )

        if valor <= 0:
            raise ValueError(
                "O valor emprestado deve ser positivo."
            )

        if parcelas <= 0 or parcelas > 360:
            raise ValueError(
                "A quantidade de parcelas deve "
                "estar entre 1 e 360."
            )

        if (
            tipo_juros
            not in EmprestimosService.TIPOS_JUROS
        ):
            raise ValueError(
                "Tipo de juros inválido."
            )

        taxa_decimal = (
            taxa
            / Decimal("100")
        )

        if tipo_juros == "simples":

            valor_juros = (
                valor
                * taxa_decimal
                * Decimal(parcelas)
            )

            valor_total = (
                valor
                + valor_juros
            )

        else:

            fator = (
                Decimal("1")
                + taxa_decimal
            ) ** parcelas

            valor_total = (
                valor
                * fator
            )

            valor_juros = (
                valor_total
                - valor
            )

        valor_total = valor_total.quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        valor_juros = valor_juros.quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        valor_parcela = (
            valor_total
            / Decimal(parcelas)
        ).quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )

        return {
            "valor_emprestado": valor,
            "taxa_juros": taxa,
            "quantidade_parcelas": parcelas,
            "tipo_juros": tipo_juros,
            "valor_juros": valor_juros,
            "valor_total": valor_total,
            "valor_parcela": valor_parcela,
        }

    @staticmethod
    def criar_emprestimo(
        empresa_id,
        cliente_id,
        usuario_id,
        valor_emprestado,
        taxa_juros,
        quantidade_parcelas,
        primeira_parcela,
        frequencia="mensal",
        tipo_juros="simples",
        data_emprestimo=None,
        observacoes=None,
    ):
        if not empresa_id:
            raise ValueError(
                "Empresa não identificada."
            )

        if not cliente_id:
            raise ValueError(
                "Cliente não informado."
            )

        if (
            frequencia
            not in EmprestimosService.FREQUENCIAS
        ):
            raise ValueError(
                "Frequência inválida."
            )

        if isinstance(
            primeira_parcela,
            str
        ):
            primeira_parcela = (
                datetime.strptime(
                    primeira_parcela,
                    "%Y-%m-%d"
                ).date()
            )

        if not isinstance(
            primeira_parcela,
            date
        ):
            raise ValueError(
                "Data da primeira parcela inválida."
            )

        if data_emprestimo is None:
            data_emprestimo = date.today()

        elif isinstance(
            data_emprestimo,
            str
        ):
            data_emprestimo = (
                datetime.strptime(
                    data_emprestimo,
                    "%Y-%m-%d"
                ).date()
            )

        calculo = (
            EmprestimosService
            .calcular_emprestimo(
                valor_emprestado,
                taxa_juros,
                quantidade_parcelas,
                tipo_juros,
            )
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    status
                FROM emprestimo_clientes
                WHERE id = %s
                  AND empresa_id = %s
                FOR UPDATE
                """,
                (
                    cliente_id,
                    empresa_id,
                )
            )

            cliente = cursor.fetchone()

            if not cliente:
                raise ValueError(
                    "Cliente não encontrado."
                )

            if cliente["status"] != "ativo":
                raise ValueError(
                    "O cliente não está ativo."
                )

            cursor.execute(
                """
                INSERT INTO emprestimos (
                    empresa_id,
                    cliente_id,
                    usuario_id,
                    valor_emprestado,
                    taxa_juros,
                    tipo_juros,
                    quantidade_parcelas,
                    valor_total,
                    valor_pago,
                    data_emprestimo,
                    primeira_parcela,
                    frequencia,
                    status,
                    observacoes
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, 0, %s,
                    %s, %s, 'ativo', %s
                )
                RETURNING id
                """,
                (
                    empresa_id,
                    cliente_id,
                    usuario_id,
                    calculo[
                        "valor_emprestado"
                    ],
                    calculo[
                        "taxa_juros"
                    ],
                    tipo_juros,
                    calculo[
                        "quantidade_parcelas"
                    ],
                    calculo[
                        "valor_total"
                    ],
                    data_emprestimo,
                    primeira_parcela,
                    frequencia,
                    observacoes,
                )
            )

            emprestimo_id = (
                cursor.fetchone()["id"]
            )

            quantidade = calculo[
                "quantidade_parcelas"
            ]

            valor_total = calculo[
                "valor_total"
            ]

            principal_total = calculo[
                "valor_emprestado"
            ]

            juros_total = calculo[
                "valor_juros"
            ]

            valor_base = (
                valor_total
                / Decimal(quantidade)
            ).quantize(
                CENTAVOS,
                rounding=ROUND_HALF_UP,
            )

            principal_base = (
                principal_total
                / Decimal(quantidade)
            ).quantize(
                CENTAVOS,
                rounding=ROUND_HALF_UP,
            )

            soma_parcelas = Decimal("0")
            soma_principal = Decimal("0")

            for numero in range(
                1,
                quantidade + 1
            ):
                if numero == quantidade:

                    valor_parcela = (
                        valor_total
                        - soma_parcelas
                    )

                    valor_principal = (
                        principal_total
                        - soma_principal
                    )

                else:
                    valor_parcela = (
                        valor_base
                    )

                    valor_principal = (
                        principal_base
                    )

                valor_juros_parcela = (
                    valor_parcela
                    - valor_principal
                )

                if valor_juros_parcela < 0:
                    valor_juros_parcela = (
                        Decimal("0")
                    )

                vencimento = (
                    _calcular_vencimento(
                        primeira_parcela,
                        numero,
                        frequencia,
                    )
                )

                cursor.execute(
                    """
                    INSERT INTO emprestimo_parcelas (
                        empresa_id,
                        emprestimo_id,
                        numero,
                        data_vencimento,
                        valor_principal,
                        valor_juros,
                        valor_multa,
                        valor_parcela,
                        valor_pago,
                        status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, 0, %s, 0, 'pendente'
                    )
                    """,
                    (
                        empresa_id,
                        emprestimo_id,
                        numero,
                        vencimento,
                        valor_principal,
                        valor_juros_parcela,
                        valor_parcela,
                    )
                )

                soma_parcelas += (
                    valor_parcela
                )

                soma_principal += (
                    valor_principal
                )

            conn.commit()

            return {
                "sucesso": True,
                "emprestimo_id": (
                    emprestimo_id
                ),
                "cliente": cliente["nome"],
                "valor_total": valor_total,
                "valor_juros": juros_total,
                "quantidade_parcelas": (
                    quantidade
                ),
                "valor_parcela": (
                    calculo["valor_parcela"]
                ),
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def atualizar_atrasos(
        empresa_id
    ):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE emprestimo_parcelas
                SET
                    status = 'atrasada',
                    data_atualizacao =
                        CURRENT_TIMESTAMP
                WHERE empresa_id = %s
                  AND status IN (
                      'pendente',
                      'parcial'
                  )
                  AND data_vencimento
                      < CURRENT_DATE
                  AND valor_pago
                      < (
                          valor_parcela
                          + valor_multa
                      )
                """,
                (
                    empresa_id,
                )
            )

            parcelas_atualizadas = (
                cursor.rowcount
            )

            cursor.execute(
                """
                UPDATE emprestimos e
                SET
                    status = 'atrasado',
                    data_atualizacao =
                        CURRENT_TIMESTAMP
                WHERE e.empresa_id = %s
                  AND e.status = 'ativo'
                  AND EXISTS (
                      SELECT 1
                      FROM emprestimo_parcelas p
                      WHERE p.emprestimo_id = e.id
                        AND p.empresa_id =
                            e.empresa_id
                        AND p.status =
                            'atrasada'
                  )
                """,
                (
                    empresa_id,
                )
            )

            cursor.execute(
                """
                UPDATE emprestimos e
                SET
                    status = 'ativo',
                    data_atualizacao =
                        CURRENT_TIMESTAMP
                WHERE e.empresa_id = %s
                  AND e.status = 'atrasado'
                  AND EXISTS (
                      SELECT 1
                      FROM emprestimo_parcelas p
                      WHERE p.emprestimo_id = e.id
                        AND p.empresa_id =
                            e.empresa_id
                        AND p.status IN (
                            'pendente',
                            'parcial'
                        )
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM emprestimo_parcelas p
                      WHERE p.emprestimo_id = e.id
                        AND p.empresa_id =
                            e.empresa_id
                        AND p.status =
                            'atrasada'
                  )
                """,
                (
                    empresa_id,
                )
            )

            conn.commit()

            return parcelas_atualizadas

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def registrar_pagamento(
        empresa_id,
        emprestimo_id,
        valor,
        usuario_id=None,
        parcela_id=None,
        forma_pagamento="dinheiro",
        observacoes=None,
    ):
        valor_pagamento = _decimal(
            valor
        )

        if valor_pagamento <= 0:
            raise ValueError(
                "O pagamento deve ser positivo."
            )

        if (
            forma_pagamento
            not in EmprestimosService
            .FORMAS_PAGAMENTO
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
                    id,
                    valor_total,
                    valor_pago,
                    status
                FROM emprestimos
                WHERE id = %s
                  AND empresa_id = %s
                FOR UPDATE
                """,
                (
                    emprestimo_id,
                    empresa_id,
                )
            )

            emprestimo = cursor.fetchone()

            if not emprestimo:
                raise ValueError(
                    "Empréstimo não encontrado."
                )

            if emprestimo["status"] in (
                "quitado",
                "cancelado",
                "renegociado",
            ):
                raise ValueError(
                    "Este empréstimo não aceita "
                    "novos pagamentos."
                )

            saldo_emprestimo = (
                _decimal(
                    emprestimo["valor_total"]
                )
                - _decimal(
                    emprestimo["valor_pago"]
                )
            )

            if valor_pagamento > saldo_emprestimo:
                raise ValueError(
                    "O pagamento é maior que "
                    "o saldo devedor."
                )

            if parcela_id:
                cursor.execute(
                    """
                    SELECT *
                    FROM emprestimo_parcelas
                    WHERE id = %s
                      AND emprestimo_id = %s
                      AND empresa_id = %s
                    FOR UPDATE
                    """,
                    (
                        parcela_id,
                        emprestimo_id,
                        empresa_id,
                    )
                )

                parcela = cursor.fetchone()

                if not parcela:
                    raise ValueError(
                        "Parcela não encontrada."
                    )

                parcelas = [parcela]

            else:
                cursor.execute(
                    """
                    SELECT *
                    FROM emprestimo_parcelas
                    WHERE emprestimo_id = %s
                      AND empresa_id = %s
                      AND status IN (
                          'atrasada',
                          'pendente',
                          'parcial'
                      )
                    ORDER BY
                        CASE
                            WHEN status = 'atrasada'
                            THEN 0
                            ELSE 1
                        END,
                        data_vencimento,
                        numero
                    FOR UPDATE
                    """,
                    (
                        emprestimo_id,
                        empresa_id,
                    )
                )

                parcelas = (
                    cursor.fetchall()
                    or []
                )

            restante = valor_pagamento
            primeira_parcela_id = None

            for parcela in parcelas:
                if restante <= 0:
                    break

                total_parcela = (
                    _decimal(
                        parcela["valor_parcela"]
                    )
                    + _decimal(
                        parcela["valor_multa"]
                    )
                )

                pago_parcela = _decimal(
                    parcela["valor_pago"]
                )

                saldo_parcela = (
                    total_parcela
                    - pago_parcela
                )

                if saldo_parcela <= 0:
                    continue

                aplicado = min(
                    restante,
                    saldo_parcela
                )

                novo_pago = (
                    pago_parcela
                    + aplicado
                )

                if novo_pago >= total_parcela:
                    novo_status = "paga"
                    data_pagamento = (
                        datetime.now()
                    )
                else:
                    novo_status = "parcial"
                    data_pagamento = None

                cursor.execute(
                    """
                    UPDATE emprestimo_parcelas
                    SET
                        valor_pago = %s,
                        status = %s,
                        data_pagamento = %s,
                        data_atualizacao =
                            CURRENT_TIMESTAMP
                    WHERE id = %s
                      AND empresa_id = %s
                    """,
                    (
                        novo_pago,
                        novo_status,
                        data_pagamento,
                        parcela["id"],
                        empresa_id,
                    )
                )

                if primeira_parcela_id is None:
                    primeira_parcela_id = (
                        parcela["id"]
                    )

                restante -= aplicado

            if restante > 0:
                raise ValueError(
                    "Não existem parcelas abertas "
                    "suficientes para este pagamento."
                )

            cursor.execute(
                """
                INSERT INTO emprestimo_pagamentos (
                    empresa_id,
                    emprestimo_id,
                    parcela_id,
                    usuario_id,
                    valor,
                    forma_pagamento,
                    observacoes
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING id
                """,
                (
                    empresa_id,
                    emprestimo_id,
                    (
                        parcela_id
                        or primeira_parcela_id
                    ),
                    usuario_id,
                    valor_pagamento,
                    forma_pagamento,
                    observacoes,
                )
            )

            pagamento_id = (
                cursor.fetchone()["id"]
            )

            novo_valor_pago = (
                _decimal(
                    emprestimo["valor_pago"]
                )
                + valor_pagamento
            )

            novo_status = (
                "quitado"
                if novo_valor_pago
                >= _decimal(
                    emprestimo["valor_total"]
                )
                else emprestimo["status"]
            )

            cursor.execute(
                """
                UPDATE emprestimos
                SET
                    valor_pago = %s,
                    status = %s,
                    data_atualizacao =
                        CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    novo_valor_pago,
                    novo_status,
                    emprestimo_id,
                    empresa_id,
                )
            )

            conn.commit()

            return {
                "sucesso": True,
                "pagamento_id": pagamento_id,
                "valor_pago": valor_pagamento,
                "saldo_devedor": (
                    _decimal(
                        emprestimo["valor_total"]
                    )
                    - novo_valor_pago
                ),
                "status": novo_status,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def buscar_emprestimo(
        empresa_id,
        emprestimo_id,
    ):
        EmprestimosService.atualizar_atrasos(
            empresa_id
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    e.*,
                    c.nome AS cliente_nome,
                    c.telefone AS cliente_telefone,
                    c.documento AS cliente_documento
                FROM emprestimos e
                INNER JOIN emprestimo_clientes c
                    ON c.id = e.cliente_id
                   AND c.empresa_id = e.empresa_id
                WHERE e.id = %s
                  AND e.empresa_id = %s
                """,
                (
                    emprestimo_id,
                    empresa_id,
                )
            )

            emprestimo = cursor.fetchone()

            if not emprestimo:
                return None

            cursor.execute(
                """
                SELECT *
                FROM emprestimo_parcelas
                WHERE emprestimo_id = %s
                  AND empresa_id = %s
                ORDER BY numero
                """,
                (
                    emprestimo_id,
                    empresa_id,
                )
            )

            parcelas = (
                cursor.fetchall()
                or []
            )

            cursor.execute(
                """
                SELECT
                    p.*,
                    u.usuario
                        AS recebido_por
                FROM emprestimo_pagamentos p
                LEFT JOIN usuarios u
                    ON u.id = p.usuario_id
                   AND u.empresa_id =
                       p.empresa_id
                WHERE p.emprestimo_id = %s
                  AND p.empresa_id = %s
                ORDER BY
                    p.data_pagamento DESC,
                    p.id DESC
                """,
                (
                    emprestimo_id,
                    empresa_id,
                )
            )

            pagamentos = (
                cursor.fetchall()
                or []
            )

            emprestimo = dict(
                emprestimo
            )

            emprestimo["parcelas"] = (
                parcelas
            )

            emprestimo["pagamentos"] = (
                pagamentos
            )

            emprestimo["saldo_devedor"] = (
                _decimal(
                    emprestimo[
                        "valor_total"
                    ]
                )
                - _decimal(
                    emprestimo[
                        "valor_pago"
                    ]
                )
            )

            return emprestimo

        finally:
            cursor.close()
            conn.close()
