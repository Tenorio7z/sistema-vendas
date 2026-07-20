from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from database import conectar, criar_cursor


CENTAVOS = Decimal("0.01")

PERIODICIDADES = {
    "semanal",
    "quinzenal",
    "mensal",
    "bimestral",
    "trimestral",
    "semestral",
    "anual",
}

TIPOS_CUSTO = {
    "fixa",
    "variavel",
    "eventual",
}


def _decimal(valor, campo="Valor"):
    try:
        texto = str(valor if valor is not None else "0").strip()
        texto = texto.replace("R$", "").strip()

        if "," in texto and "." in texto:
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", ".")

        return Decimal(texto or "0").quantize(
            CENTAVOS,
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, TypeError, ValueError) as erro:
        raise ValueError(f"{campo} inválido.") from erro


def _data(valor, campo="Data"):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor

    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (TypeError, ValueError) as erro:
        raise ValueError(f"{campo} inválida.") from erro


def _somar_meses(data_base, quantidade):
    novo_mes = data_base.month - 1 + quantidade
    ano = data_base.year + novo_mes // 12
    mes = novo_mes % 12 + 1
    dia = min(data_base.day, monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def _aplicar_dia_vencimento(data_base, dia_vencimento):
    if not dia_vencimento:
        return data_base

    dia = min(
        int(dia_vencimento),
        monthrange(data_base.year, data_base.month)[1],
    )
    return date(data_base.year, data_base.month, dia)


def _proxima_data(data_base, periodicidade, indice):
    if indice == 0:
        return data_base
    if periodicidade == "semanal":
        return data_base + timedelta(weeks=indice)
    if periodicidade == "quinzenal":
        return data_base + timedelta(days=15 * indice)

    meses_por_periodo = {
        "mensal": 1,
        "bimestral": 2,
        "trimestral": 3,
        "semestral": 6,
        "anual": 12,
    }
    return _somar_meses(
        data_base,
        meses_por_periodo.get(periodicidade, 1) * indice,
    )


def _dividir_valor(valor_total, quantidade):
    valor_total = _decimal(valor_total)
    quantidade = int(quantidade)
    valor_base = (valor_total / quantidade).quantize(
        CENTAVOS,
        rounding=ROUND_HALF_UP,
    )

    valores = []
    acumulado = Decimal("0.00")

    for indice in range(quantidade):
        if indice == quantidade - 1:
            valor_parcela = valor_total - acumulado
        else:
            valor_parcela = valor_base

        valores.append(valor_parcela)
        acumulado += valor_parcela

    return valores


def _registrar_saida_caixa(
    cursor,
    empresa_id,
    caixa_id,
    valor,
    descricao,
):
    if caixa_id is None:
        return

    cursor.execute(
        """
        SELECT id, status
        FROM caixa
        WHERE id = %s
          AND empresa_id = %s
        FOR UPDATE
        """,
        (caixa_id, empresa_id),
    )
    caixa = cursor.fetchone()

    if not caixa:
        raise ValueError("O caixa informado não foi encontrado.")
    if caixa["status"] != "aberto":
        raise ValueError("O caixa informado já está fechado.")

    cursor.execute(
        """
        UPDATE caixa
        SET valor_final = COALESCE(valor_final, 0) - %s
        WHERE id = %s
          AND empresa_id = %s
          AND status = 'aberto'
        """,
        (valor, caixa_id, empresa_id),
    )

    if cursor.rowcount != 1:
        raise ValueError("Não foi possível atualizar o caixa.")

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
        VALUES ('saida', %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (descricao, valor, empresa_id, caixa_id),
    )


def _registrar_entrada_caixa(
    cursor,
    empresa_id,
    caixa_id,
    valor,
    descricao,
):
    if caixa_id is None:
        return

    cursor.execute(
        """
        SELECT id, status
        FROM caixa
        WHERE id = %s
          AND empresa_id = %s
        FOR UPDATE
        """,
        (caixa_id, empresa_id),
    )
    caixa = cursor.fetchone()

    if not caixa:
        raise ValueError("O caixa do pagamento não foi encontrado.")
    if caixa["status"] != "aberto":
        raise ValueError(
            "Não é possível estornar porque o caixa original já foi fechado."
        )

    cursor.execute(
        """
        UPDATE caixa
        SET valor_final = COALESCE(valor_final, 0) + %s
        WHERE id = %s
          AND empresa_id = %s
          AND status = 'aberto'
        """,
        (valor, caixa_id, empresa_id),
    )

    if cursor.rowcount != 1:
        raise ValueError("Não foi possível devolver o valor ao caixa.")

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
        VALUES ('entrada', %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (descricao, valor, empresa_id, caixa_id),
    )


class CustosService:
    @staticmethod
    def criar(
        empresa_id,
        descricao,
        categoria,
        valor,
        data_inicio,
        data_vencimento=None,
        tipo="variavel",
        fornecedor=None,
        observacoes=None,
        recorrente=False,
        periodicidade=None,
        quantidade_parcelas=1,
        dia_vencimento=None,
        forma_pagamento_padrao=None,
        ja_pago=False,
        usuario_id=None,
        caixa_id=None,
    ):
        descricao = str(descricao or "").strip()
        categoria = str(categoria or "Outras despesas").strip()
        fornecedor = str(fornecedor or "").strip() or None
        observacoes = str(observacoes or "").strip() or None
        tipo = str(tipo or "variavel").strip().lower()
        periodicidade = str(periodicidade or "").strip().lower() or None
        forma_pagamento_padrao = (
            str(forma_pagamento_padrao or "").strip() or None
        )
        valor = _decimal(valor, "Valor da despesa")
        data_inicio = _data(data_inicio, "Data inicial")
        primeiro_vencimento = _data(
            data_vencimento or data_inicio,
            "Data de vencimento",
        )

        try:
            quantidade_parcelas = int(quantidade_parcelas or 1)
        except (TypeError, ValueError) as erro:
            raise ValueError("Quantidade de parcelas inválida.") from erro

        recorrente = bool(recorrente)

        if not empresa_id:
            raise ValueError("Empresa não identificada.")
        if not descricao:
            raise ValueError("Informe a descrição da despesa.")
        if len(descricao) > 160:
            raise ValueError("A descrição pode ter no máximo 160 caracteres.")
        if valor <= 0:
            raise ValueError("O valor da despesa deve ser maior que zero.")
        if tipo not in TIPOS_CUSTO:
            raise ValueError("Tipo de despesa inválido.")
        if not 1 <= quantidade_parcelas <= 240:
            raise ValueError("A quantidade deve estar entre 1 e 240.")
        if recorrente and periodicidade not in PERIODICIDADES:
            raise ValueError("Selecione a periodicidade da despesa recorrente.")
        if not recorrente:
            periodicidade = None

        if dia_vencimento not in (None, ""):
            try:
                dia_vencimento = int(dia_vencimento)
            except (TypeError, ValueError) as erro:
                raise ValueError("Dia de vencimento inválido.") from erro
            if not 1 <= dia_vencimento <= 31:
                raise ValueError("O dia do vencimento deve estar entre 1 e 31.")
        else:
            dia_vencimento = None

        conn = conectar()
        cursor = criar_cursor(conn)
        conn.autocommit = False

        try:
            cursor.execute(
                """
                INSERT INTO custos_empresariais (
                    empresa_id, descricao, categoria, fornecedor,
                    observacoes, tipo, recorrente, periodicidade,
                    quantidade_parcelas, dia_vencimento, valor_total,
                    data_inicio, forma_pagamento_padrao, ativo
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, TRUE
                )
                RETURNING *
                """,
                (
                    empresa_id,
                    descricao,
                    categoria,
                    fornecedor,
                    observacoes,
                    tipo,
                    recorrente,
                    periodicidade,
                    quantidade_parcelas,
                    dia_vencimento,
                    valor,
                    data_inicio,
                    forma_pagamento_padrao,
                ),
            )
            custo = cursor.fetchone()

            valores = (
                [valor] * quantidade_parcelas
                if recorrente
                else _dividir_valor(valor, quantidade_parcelas)
            )
            parcelas = []
            ultimo_vencimento = primeiro_vencimento

            for indice, valor_parcela in enumerate(valores):
                vencimento = (
                    _proxima_data(primeiro_vencimento, periodicidade, indice)
                    if recorrente
                    else _somar_meses(primeiro_vencimento, indice)
                )

                if periodicidade not in {"semanal", "quinzenal"}:
                    vencimento = _aplicar_dia_vencimento(
                        vencimento,
                        dia_vencimento,
                    )

                ultimo_vencimento = vencimento
                competencia = date(vencimento.year, vencimento.month, 1)

                # Recorrência: somente a primeira cobrança é paga agora.
                # Parcelamento comum: "já pago" quita todas as parcelas.
                pagar_agora = ja_pago and (not recorrente or indice == 0)
                status = "paga" if pagar_agora else "pendente"
                valor_pago = valor_parcela if pagar_agora else Decimal("0.00")

                cursor.execute(
                    """
                    INSERT INTO custos_parcelas (
                        custo_id, empresa_id, numero_parcela, competencia,
                        data_vencimento, valor, valor_pago, status, paga_em
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END
                    )
                    RETURNING *
                    """,
                    (
                        custo["id"],
                        empresa_id,
                        indice + 1,
                        competencia,
                        vencimento,
                        valor_parcela,
                        valor_pago,
                        status,
                        pagar_agora,
                    ),
                )
                parcela = cursor.fetchone()
                parcelas.append(parcela)

                if pagar_agora:
                    forma = forma_pagamento_padrao or "Outro"
                    cursor.execute(
                        """
                        INSERT INTO custos_pagamentos (
                            empresa_id, custo_id, parcela_id, usuario_id,
                            caixa_id, valor, forma_pagamento, observacoes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (
                            empresa_id,
                            custo["id"],
                            parcela["id"],
                            usuario_id,
                            caixa_id,
                            valor_parcela,
                            forma,
                            "Pagamento registrado no cadastro da despesa.",
                        ),
                    )
                    pagamento = cursor.fetchone()
                    _registrar_saida_caixa(
                        cursor,
                        empresa_id,
                        caixa_id,
                        valor_parcela,
                        f"Custo empresarial #{pagamento['id']} - {descricao}",
                    )

            cursor.execute(
                """
                UPDATE custos_empresariais
                SET data_fim = %s,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (ultimo_vencimento, custo["id"], empresa_id),
            )

            conn.commit()
            return {"custo": custo, "parcelas": parcelas}
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def pagar(
        empresa_id,
        parcela_id,
        valor,
        forma_pagamento,
        usuario_id=None,
        caixa_id=None,
        observacoes=None,
    ):
        valor = _decimal(valor, "Valor do pagamento")
        forma_pagamento = str(forma_pagamento or "").strip()
        observacoes = str(observacoes or "").strip() or None

        if valor <= 0:
            raise ValueError("O pagamento deve ser maior que zero.")
        if not forma_pagamento:
            raise ValueError("Informe a forma de pagamento.")

        conn = conectar()
        cursor = criar_cursor(conn)
        conn.autocommit = False

        try:
            cursor.execute(
                """
                SELECT p.*, c.descricao, c.ativo AS custo_ativo
                FROM custos_parcelas p
                INNER JOIN custos_empresariais c
                    ON c.id = p.custo_id
                   AND c.empresa_id = p.empresa_id
                WHERE p.id = %s
                  AND p.empresa_id = %s
                FOR UPDATE
                """,
                (parcela_id, empresa_id),
            )
            parcela = cursor.fetchone()

            if not parcela:
                raise ValueError("Parcela não encontrada.")
            if not parcela["custo_ativo"]:
                raise ValueError("Esta despesa está desativada.")
            if parcela["status"] == "cancelada":
                raise ValueError("A parcela está cancelada.")

            valor_parcela = _decimal(parcela["valor"])
            valor_pago_atual = _decimal(parcela["valor_pago"])
            saldo = valor_parcela - valor_pago_atual

            if saldo <= 0:
                raise ValueError("Esta parcela já está paga.")
            if valor > saldo:
                raise ValueError(
                    f"O pagamento ultrapassa o saldo de R$ {saldo:.2f}."
                )

            cursor.execute(
                """
                INSERT INTO custos_pagamentos (
                    empresa_id, custo_id, parcela_id, usuario_id,
                    caixa_id, valor, forma_pagamento, observacoes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    empresa_id,
                    parcela["custo_id"],
                    parcela_id,
                    usuario_id,
                    caixa_id,
                    valor,
                    forma_pagamento,
                    observacoes,
                ),
            )
            pagamento = cursor.fetchone()

            _registrar_saida_caixa(
                cursor,
                empresa_id,
                caixa_id,
                valor,
                f"Custo empresarial #{pagamento['id']} - {parcela['descricao']}",
            )

            novo_valor_pago = (valor_pago_atual + valor).quantize(CENTAVOS)
            novo_status = "paga" if novo_valor_pago >= valor_parcela else "parcial"

            cursor.execute(
                """
                UPDATE custos_parcelas
                SET valor_pago = %s,
                    status = %s,
                    paga_em = CASE
                        WHEN %s = 'paga' THEN CURRENT_TIMESTAMP
                        ELSE NULL
                    END,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                RETURNING *
                """,
                (
                    novo_valor_pago,
                    novo_status,
                    novo_status,
                    parcela_id,
                    empresa_id,
                ),
            )
            parcela_atualizada = cursor.fetchone()
            conn.commit()

            return {
                "pagamento": pagamento,
                "parcela": parcela_atualizada,
                "saldo": (valor_parcela - novo_valor_pago).quantize(CENTAVOS),
            }
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def estornar_pagamento(empresa_id, pagamento_id, motivo):
        motivo = str(motivo or "").strip()
        if not motivo:
            raise ValueError("Informe o motivo do estorno.")

        conn = conectar()
        cursor = criar_cursor(conn)
        conn.autocommit = False

        try:
            cursor.execute(
                """
                SELECT cp.*, c.descricao
                FROM custos_pagamentos cp
                INNER JOIN custos_empresariais c
                    ON c.id = cp.custo_id
                   AND c.empresa_id = cp.empresa_id
                WHERE cp.id = %s
                  AND cp.empresa_id = %s
                FOR UPDATE
                """,
                (pagamento_id, empresa_id),
            )
            pagamento = cursor.fetchone()

            if not pagamento:
                raise ValueError("Pagamento não encontrado.")
            if pagamento["estornado"]:
                raise ValueError("Este pagamento já foi estornado.")

            cursor.execute(
                """
                SELECT *
                FROM custos_parcelas
                WHERE id = %s
                  AND empresa_id = %s
                FOR UPDATE
                """,
                (pagamento["parcela_id"], empresa_id),
            )
            parcela = cursor.fetchone()

            if not parcela:
                raise ValueError("Parcela vinculada não encontrada.")

            _registrar_entrada_caixa(
                cursor,
                empresa_id,
                pagamento["caixa_id"],
                pagamento["valor"],
                f"Estorno de custo empresarial #{pagamento_id} - {pagamento['descricao']}",
            )

            novo_valor_pago = max(
                Decimal("0.00"),
                _decimal(parcela["valor_pago"]) - _decimal(pagamento["valor"]),
            )
            valor_parcela = _decimal(parcela["valor"])

            if novo_valor_pago <= 0:
                novo_status = "pendente"
            elif novo_valor_pago < valor_parcela:
                novo_status = "parcial"
            else:
                novo_status = "paga"

            cursor.execute(
                """
                UPDATE custos_pagamentos
                SET estornado = TRUE,
                    estornado_em = CURRENT_TIMESTAMP,
                    motivo_estorno = %s
                WHERE id = %s
                  AND empresa_id = %s
                  AND estornado = FALSE
                """,
                (motivo, pagamento_id, empresa_id),
            )

            if cursor.rowcount != 1:
                raise ValueError("Este pagamento já foi estornado.")

            cursor.execute(
                """
                UPDATE custos_parcelas
                SET valor_pago = %s,
                    status = %s,
                    paga_em = CASE
                        WHEN %s = 'paga' THEN paga_em
                        ELSE NULL
                    END,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                RETURNING *
                """,
                (
                    novo_valor_pago,
                    novo_status,
                    novo_status,
                    parcela["id"],
                    empresa_id,
                ),
            )
            parcela_atualizada = cursor.fetchone()
            conn.commit()
            return parcela_atualizada
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def alterar_status(empresa_id, custo_id, ativo):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                UPDATE custos_empresariais
                SET ativo = %s,
                    atualizado_em = CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                RETURNING *
                """,
                (bool(ativo), custo_id, empresa_id),
            )
            custo = cursor.fetchone()
            if not custo:
                raise ValueError("Despesa não encontrada.")
            conn.commit()
            return custo
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def listar(empresa_id, status=None, categoria=None, busca=None):
        filtros = ["c.empresa_id = %s", "c.ativo = TRUE"]
        parametros = [empresa_id]

        if categoria:
            filtros.append("LOWER(c.categoria) = LOWER(%s)")
            parametros.append(categoria)

        if busca:
            termo = f"%{busca}%"
            filtros.append(
                """
                (
                    c.descricao ILIKE %s
                    OR COALESCE(c.fornecedor, '') ILIKE %s
                    OR c.categoria ILIKE %s
                )
                """
            )
            parametros.extend([termo, termo, termo])

        if status == "vencidas":
            filtros.append(
                "p.status IN ('pendente', 'parcial') "
                "AND p.data_vencimento < CURRENT_DATE"
            )
        elif status in {"pendente", "parcial", "paga", "cancelada"}:
            filtros.append("p.status = %s")
            parametros.append(status)

        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                f"""
                SELECT
                    c.id AS custo_id,
                    c.descricao,
                    c.categoria,
                    c.fornecedor,
                    c.tipo,
                    c.recorrente,
                    c.periodicidade,
                    c.valor_total,
                    c.forma_pagamento_padrao,
                    p.id AS parcela_id,
                    p.numero_parcela,
                    p.competencia,
                    p.data_vencimento,
                    p.valor,
                    p.valor_pago,
                    GREATEST(p.valor - p.valor_pago, 0) AS saldo,
                    CASE
                        WHEN p.status IN ('pendente', 'parcial')
                         AND p.data_vencimento < CURRENT_DATE
                        THEN 'vencida'
                        ELSE p.status
                    END AS status_exibicao
                FROM custos_empresariais c
                INNER JOIN custos_parcelas p
                    ON p.custo_id = c.id
                   AND p.empresa_id = c.empresa_id
                WHERE {' AND '.join(filtros)}
                ORDER BY
                    CASE
                        WHEN p.status IN ('pendente', 'parcial')
                         AND p.data_vencimento < CURRENT_DATE
                        THEN 0 ELSE 1
                    END,
                    p.data_vencimento ASC,
                    c.descricao ASC
                """,
                tuple(parametros),
            )
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def resumo(empresa_id, data_inicial, data_final):
        data_inicial = _data(data_inicial, "Data inicial")
        data_final = _data(data_final, "Data final")
        if data_final < data_inicial:
            raise ValueError("A data final não pode ser anterior à inicial.")

        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(p.valor) FILTER (WHERE c.tipo = 'fixa'), 0)
                        AS custos_fixos,
                    COALESCE(SUM(p.valor) FILTER (WHERE c.tipo = 'variavel'), 0)
                        AS custos_variaveis,
                    COALESCE(SUM(p.valor) FILTER (WHERE c.tipo = 'eventual'), 0)
                        AS custos_eventuais,
                    COALESCE(SUM(p.valor), 0) AS total_previsto,
                    COALESCE(SUM(p.valor_pago), 0) AS total_registrado_parcelas,
                    COALESCE(SUM(GREATEST(p.valor - p.valor_pago, 0)), 0)
                        AS total_pendente,
                    COALESCE(
                        SUM(GREATEST(p.valor - p.valor_pago, 0)) FILTER (
                            WHERE p.status IN ('pendente', 'parcial')
                              AND p.data_vencimento < CURRENT_DATE
                        ),
                        0
                    ) AS total_vencido,
                    COUNT(*) FILTER (
                        WHERE p.status IN ('pendente', 'parcial')
                    ) AS contas_pendentes,
                    COUNT(*) FILTER (
                        WHERE p.status IN ('pendente', 'parcial')
                          AND p.data_vencimento < CURRENT_DATE
                    ) AS contas_vencidas
                FROM custos_parcelas p
                INNER JOIN custos_empresariais c
                    ON c.id = p.custo_id
                   AND c.empresa_id = p.empresa_id
                WHERE p.empresa_id = %s
                  AND c.ativo = TRUE
                  AND p.data_vencimento BETWEEN %s AND %s
                  AND p.status <> 'cancelada'
                """,
                (empresa_id, data_inicial, data_final),
            )
            resumo = cursor.fetchone() or {}

            cursor.execute(
                """
                SELECT COALESCE(SUM(valor), 0) AS total_pago_periodo
                FROM custos_pagamentos
                WHERE empresa_id = %s
                  AND estornado = FALSE
                  AND data_pagamento::date BETWEEN %s AND %s
                """,
                (empresa_id, data_inicial, data_final),
            )
            pagamentos = cursor.fetchone() or {}
            resumo["total_pago"] = pagamentos.get(
                "total_pago_periodo",
                Decimal("0.00"),
            )
            return resumo
        finally:
            cursor.close()
            conn.close()
