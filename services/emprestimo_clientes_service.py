import re

from database import (
    conectar,
    criar_cursor,
)


def _texto_limpo(
    valor,
    limite=None,
):
    if valor is None:
        return None

    valor = str(
        valor
    ).strip()

    if not valor:
        return None

    if limite:
        valor = valor[:limite]

    return valor


def _somente_numeros(
    valor
):
    return re.sub(
        r"\D",
        "",
        str(valor or "")
    )


def _normalizar_telefone(
    telefone
):
    numero = _somente_numeros(
        telefone
    )

    if numero.startswith("00"):
        numero = numero[2:]

    if numero.startswith("55"):
        numero_nacional = numero[2:]
    else:
        numero_nacional = numero

    if len(numero_nacional) not in (
        10,
        11,
    ):
        raise ValueError(
            "Informe um telefone com DDD."
        )

    ddd = numero_nacional[:2]

    if ddd == "00":
        raise ValueError(
            "DDD inválido."
        )

    return numero_nacional


def _normalizar_documento(
    documento
):
    documento = _somente_numeros(
        documento
    )

    if not documento:
        return None

    if len(documento) not in (
        11,
        14,
    ):
        raise ValueError(
            "O documento deve possuir "
            "11 ou 14 números."
        )

    return documento


class EmprestimoClientesService:

    STATUS_VALIDOS = (
        "ativo",
        "inativo",
        "bloqueado",
    )

    @staticmethod
    def criar(
        empresa_id,
        nome,
        telefone,
        documento=None,
        email=None,
        endereco=None,
        observacoes=None,
    ):
        if not empresa_id:
            raise ValueError(
                "Empresa não identificada."
            )

        nome = _texto_limpo(
            nome,
            150
        )

        if not nome:
            raise ValueError(
                "Informe o nome do cliente."
            )

        telefone = _normalizar_telefone(
            telefone
        )

        documento = _normalizar_documento(
            documento
        )

        email = _texto_limpo(
            email,
            150
        )

        endereco = _texto_limpo(
            endereco
        )

        observacoes = _texto_limpo(
            observacoes
        )

        if (
            email
            and not re.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                email
            )
        ):
            raise ValueError(
                "E-mail inválido."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT id
                FROM emprestimo_clientes
                WHERE empresa_id = %s
                  AND telefone = %s
                  AND status != 'inativo'
                LIMIT 1
                """,
                (
                    empresa_id,
                    telefone,
                )
            )

            if cursor.fetchone():
                raise ValueError(
                    "Já existe um cliente ativo "
                    "com este telefone."
                )

            if documento:
                cursor.execute(
                    """
                    SELECT id
                    FROM emprestimo_clientes
                    WHERE empresa_id = %s
                      AND documento = %s
                    LIMIT 1
                    """,
                    (
                        empresa_id,
                        documento,
                    )
                )

                if cursor.fetchone():
                    raise ValueError(
                        "Já existe um cliente "
                        "com este documento."
                    )

            cursor.execute(
                """
                INSERT INTO emprestimo_clientes (
                    empresa_id,
                    nome,
                    telefone,
                    documento,
                    email,
                    endereco,
                    observacoes,
                    status
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, 'ativo'
                )
                RETURNING id
                """,
                (
                    empresa_id,
                    nome,
                    telefone,
                    documento,
                    email,
                    endereco,
                    observacoes,
                )
            )

            cliente_id = (
                cursor.fetchone()["id"]
            )

            conn.commit()

            return cliente_id

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def atualizar(
        empresa_id,
        cliente_id,
        nome,
        telefone,
        documento=None,
        email=None,
        endereco=None,
        observacoes=None,
        status="ativo",
    ):
        if not empresa_id:
            raise ValueError(
                "Empresa não identificada."
            )

        nome = _texto_limpo(
            nome,
            150
        )

        if not nome:
            raise ValueError(
                "Informe o nome do cliente."
            )

        telefone = _normalizar_telefone(
            telefone
        )

        documento = _normalizar_documento(
            documento
        )

        email = _texto_limpo(
            email,
            150
        )

        endereco = _texto_limpo(
            endereco
        )

        observacoes = _texto_limpo(
            observacoes
        )

        status = _texto_limpo(
            status,
            20
        )

        if (
            status
            not in EmprestimoClientesService
            .STATUS_VALIDOS
        ):
            raise ValueError(
                "Status inválido."
            )

        if (
            email
            and not re.match(
                r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                email
            )
        ):
            raise ValueError(
                "E-mail inválido."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT id
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

            if not cursor.fetchone():
                raise ValueError(
                    "Cliente não encontrado."
                )

            cursor.execute(
                """
                SELECT id
                FROM emprestimo_clientes
                WHERE empresa_id = %s
                  AND telefone = %s
                  AND id != %s
                  AND status != 'inativo'
                LIMIT 1
                """,
                (
                    empresa_id,
                    telefone,
                    cliente_id,
                )
            )

            if cursor.fetchone():
                raise ValueError(
                    "Outro cliente já utiliza "
                    "este telefone."
                )

            if documento:
                cursor.execute(
                    """
                    SELECT id
                    FROM emprestimo_clientes
                    WHERE empresa_id = %s
                      AND documento = %s
                      AND id != %s
                    LIMIT 1
                    """,
                    (
                        empresa_id,
                        documento,
                        cliente_id,
                    )
                )

                if cursor.fetchone():
                    raise ValueError(
                        "Outro cliente já utiliza "
                        "este documento."
                    )

            cursor.execute(
                """
                UPDATE emprestimo_clientes
                SET
                    nome = %s,
                    telefone = %s,
                    documento = %s,
                    email = %s,
                    endereco = %s,
                    observacoes = %s,
                    status = %s,
                    data_atualizacao =
                        CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    nome,
                    telefone,
                    documento,
                    email,
                    endereco,
                    observacoes,
                    status,
                    cliente_id,
                    empresa_id,
                )
            )

            conn.commit()

            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def buscar(
        empresa_id,
        cliente_id,
    ):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    c.*,

                    COUNT(
                        DISTINCT e.id
                    ) AS total_emprestimos,

                    COUNT(
                        DISTINCT e.id
                    ) FILTER (
                        WHERE e.status IN (
                            'ativo',
                            'atrasado'
                        )
                    ) AS emprestimos_abertos,

                    COALESCE(
                        SUM(
                            e.valor_total
                            - e.valor_pago
                        ) FILTER (
                            WHERE e.status IN (
                                'ativo',
                                'atrasado'
                            )
                        ),
                        0
                    ) AS saldo_devedor,

                    COALESCE(
                        SUM(
                            e.valor_pago
                        ),
                        0
                    ) AS total_pago,

                    COUNT(
                        DISTINCT p.id
                    ) FILTER (
                        WHERE p.status =
                            'atrasada'
                    ) AS parcelas_atrasadas

                FROM emprestimo_clientes c

                LEFT JOIN emprestimos e
                    ON e.cliente_id = c.id
                   AND e.empresa_id =
                       c.empresa_id

                LEFT JOIN emprestimo_parcelas p
                    ON p.emprestimo_id = e.id
                   AND p.empresa_id =
                       e.empresa_id

                WHERE c.id = %s
                  AND c.empresa_id = %s

                GROUP BY c.id
                """,
                (
                    cliente_id,
                    empresa_id,
                )
            )

            return cursor.fetchone()

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def listar(
        empresa_id,
        busca=None,
        status=None,
        limite=100,
    ):
        if not empresa_id:
            return []

        try:
            limite = int(limite)

        except Exception:
            limite = 100

        limite = max(
            1,
            min(
                limite,
                500
            )
        )

        filtros = [
            "c.empresa_id = %s"
        ]

        parametros = [
            empresa_id
        ]

        if busca:
            busca = str(
                busca
            ).strip()

            if busca:
                filtros.append(
                    """
                    (
                        c.nome ILIKE %s
                        OR c.telefone ILIKE %s
                        OR COALESCE(
                            c.documento,
                            ''
                        ) ILIKE %s
                    )
                    """
                )

                termo = f"%{busca}%"

                parametros.extend([
                    termo,
                    termo,
                    termo,
                ])

        if (
            status
            in EmprestimoClientesService
            .STATUS_VALIDOS
        ):
            filtros.append(
                "c.status = %s"
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

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                f"""
                SELECT
                    c.*,

                    COUNT(
                        DISTINCT e.id
                    ) AS total_emprestimos,

                    COUNT(
                        DISTINCT e.id
                    ) FILTER (
                        WHERE e.status IN (
                            'ativo',
                            'atrasado'
                        )
                    ) AS emprestimos_abertos,

                    COALESCE(
                        SUM(
                            e.valor_total
                            - e.valor_pago
                        ) FILTER (
                            WHERE e.status IN (
                                'ativo',
                                'atrasado'
                            )
                        ),
                        0
                    ) AS saldo_devedor,

                    COUNT(
                        DISTINCT p.id
                    ) FILTER (
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

                FROM emprestimo_clientes c

                LEFT JOIN emprestimos e
                    ON e.cliente_id = c.id
                   AND e.empresa_id =
                       c.empresa_id

                LEFT JOIN emprestimo_parcelas p
                    ON p.emprestimo_id = e.id
                   AND p.empresa_id =
                       e.empresa_id

                WHERE {where_sql}

                GROUP BY c.id

                ORDER BY
                    parcelas_atrasadas DESC,
                    saldo_devedor DESC,
                    c.nome ASC

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

    @staticmethod
    def listar_emprestimos(
        empresa_id,
        cliente_id,
    ):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    e.*,

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

                LEFT JOIN emprestimo_parcelas p
                    ON p.emprestimo_id = e.id
                   AND p.empresa_id =
                       e.empresa_id

                WHERE e.cliente_id = %s
                  AND e.empresa_id = %s

                GROUP BY e.id

                ORDER BY
                    e.data_emprestimo DESC,
                    e.id DESC
                """,
                (
                    cliente_id,
                    empresa_id,
                )
            )

            return (
                cursor.fetchall()
                or []
            )

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def alterar_status(
        empresa_id,
        cliente_id,
        status,
    ):
        if (
            status
            not in EmprestimoClientesService
            .STATUS_VALIDOS
        ):
            raise ValueError(
                "Status inválido."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE emprestimo_clientes
                SET
                    status = %s,
                    data_atualizacao =
                        CURRENT_TIMESTAMP
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    status,
                    cliente_id,
                    empresa_id,
                )
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Cliente não encontrado."
                )

            conn.commit()

            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def excluir(
        empresa_id,
        cliente_id,
    ):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM emprestimos
                WHERE cliente_id = %s
                  AND empresa_id = %s
                """,
                (
                    cliente_id,
                    empresa_id,
                )
            )

            total = (
                cursor.fetchone()["total"]
            )

            if total > 0:
                raise ValueError(
                    "O cliente possui empréstimos "
                    "e não pode ser excluído. "
                    "Altere o status para inativo."
                )

            cursor.execute(
                """
                DELETE FROM emprestimo_clientes
                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    cliente_id,
                    empresa_id,
                )
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Cliente não encontrado."
                )

            conn.commit()

            return True

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()