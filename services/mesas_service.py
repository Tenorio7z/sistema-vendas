from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from uuid import uuid4

from database import conectar, criar_cursor
from psycopg2.extras import execute_values


class MesasErro(Exception):
    pass


class MesasService:

    STATUS_MESA = {
        "livre",
        "ocupada",
        "reservada",
        "inativa",
    }

    STATUS_COMANDA_ABERTA = (
        "aberta",
        "aguardando_pagamento",
    )

    @staticmethod
    def _inteiro(valor, nome, minimo=1):

        try:
            valor = int(valor)

        except (TypeError, ValueError) as erro:
            raise MesasErro(
                f"{nome} inválido."
            ) from erro

        if valor < minimo:
            raise MesasErro(
                f"{nome} deve ser maior ou igual a {minimo}."
            )

        return valor

    @staticmethod
    def _decimal(valor, nome):

        try:
            numero = Decimal(
                str(valor or "0")
                .replace(".", "")
                .replace(",", ".")
            )

        except (InvalidOperation, ValueError) as erro:
            raise MesasErro(
                f"{nome} inválido."
            ) from erro

        if numero < 0:
            raise MesasErro(
                f"{nome} não pode ser negativo."
            )

        return numero.quantize(
            Decimal("0.01")
        )

    @staticmethod
    def _texto(valor, limite):

        texto = str(
            valor or ""
        ).strip()

        return texto[:limite]

    @staticmethod
    def _moeda(valor, nome="Valor"):

        try:
            texto = str(
                valor
                if valor is not None
                else "0"
            ).strip()

            texto = texto.replace(
                "R$",
                "",
            ).replace(
                " ",
                "",
            )

            if "," in texto:
                texto = texto.replace(
                    ".",
                    "",
                ).replace(
                    ",",
                    ".",
                )

            elif (
                texto.count(".") >= 1
                and all(
                    len(parte) == 3
                    for parte in texto.split(".")[1:]
                )
            ):
                texto = texto.replace(
                    ".",
                    "",
                )

            numero = Decimal(
                texto or "0"
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as erro:
            raise MesasErro(
                f"{nome} inválido."
            ) from erro

        if numero < 0:
            raise MesasErro(
                f"{nome} não pode ser negativo."
            )

        return numero

    # =====================================================
    # LISTAR PAINEL DE MESAS
    # =====================================================

    @classmethod
    def listar_mesas(
        cls,
        empresa_id,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    m.id,
                    m.numero,
                    m.nome,
                    m.capacidade,
                    m.status,
                    m.observacoes,
                    m.criado_em,
                    m.atualizado_em,

                    c.id AS comanda_id,
                    c.identificacao,
                    c.quantidade_pessoas,
                    c.status AS comanda_status,
                    c.subtotal,
                    c.desconto_valor,
                    c.total,
                    c.aberta_em,

                    u.usuario AS funcionario_nome,

                    COALESCE(
                        itens.quantidade_itens,
                        0
                    ) AS quantidade_itens,

                    COALESCE(
                        itens.itens_nao_enviados,
                        0
                    ) AS itens_nao_enviados,

                    COALESCE(
                        itens.itens_em_producao,
                        0
                    ) AS itens_em_producao

                FROM mesas m

                LEFT JOIN comandas c
                    ON c.mesa_id = m.id
                    AND c.empresa_id = m.empresa_id
                    AND c.status IN (
                        'aberta',
                        'aguardando_pagamento'
                    )

                LEFT JOIN usuarios u
                    ON u.id = c.funcionario_id
                    AND u.empresa_id = m.empresa_id

                LEFT JOIN LATERAL (
                    SELECT
                        COALESCE(
                            SUM(ci.quantidade)
                                FILTER (
                                    WHERE ci.status != 'cancelado'
                                ),
                            0
                        ) AS quantidade_itens,

                        COUNT(*)
                            FILTER (
                                WHERE ci.status != 'cancelado'
                                  AND ci.pedido_id IS NULL
                            ) AS itens_nao_enviados,

                        COUNT(*)
                            FILTER (
                                WHERE ci.status IN (
                                    'pendente',
                                    'preparando'
                                )
                            ) AS itens_em_producao

                    FROM comanda_itens ci

                    WHERE ci.comanda_id = c.id
                      AND ci.empresa_id = m.empresa_id
                ) itens ON TRUE

                WHERE m.empresa_id = %s

                ORDER BY
                    CASE m.status
                        WHEN 'ocupada' THEN 1
                        WHEN 'reservada' THEN 2
                        WHEN 'livre' THEN 3
                        ELSE 4
                    END,
                    m.numero
                """,
                (empresa_id,),
            )

            return cursor.fetchall()

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # LISTAR PEDIDOS DA PRODUÇÃO
    # =====================================================

    @classmethod
    def listar_pedidos_producao(
        cls,
        *,
        empresa_id,
        setor,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        setor = cls._texto(
            setor,
            30,
        ).lower()

        if setor not in {"cozinha", "bar"}:
            raise MesasErro(
                "Setor de produção inválido."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    cp.id AS pedido_id,
                    cp.numero_sequencial,
                    cp.status AS pedido_status,
                    cp.observacoes AS pedido_observacoes,
                    cp.enviado_em,

                    c.id AS comanda_id,
                    c.identificacao,

                    m.numero AS mesa_numero,
                    m.nome AS mesa_nome,

                    ci.id AS item_id,
                    ci.produto_id,
                    ci.produto_nome,
                    ci.quantidade,
                    ci.observacoes,
                    ci.status,
                    ci.enviado_em AS item_enviado_em,
                    ci.preparo_iniciado_em,
                    ci.pronto_em,
                    ci.entregue_em

                FROM comanda_itens ci

                INNER JOIN comanda_pedidos cp
                    ON cp.id = ci.pedido_id
                    AND cp.empresa_id = ci.empresa_id

                INNER JOIN comandas c
                    ON c.id = ci.comanda_id
                    AND c.empresa_id = ci.empresa_id

                LEFT JOIN mesas m
                    ON m.id = c.mesa_id
                    AND m.empresa_id = c.empresa_id

                WHERE ci.empresa_id = %s
                  AND ci.setor_preparo = %s
                  AND ci.pedido_id IS NOT NULL
                  AND ci.status NOT IN (
                      'entregue',
                      'cancelado'
                  )
                  AND c.status IN (
                      'aberta',
                      'aguardando_pagamento'
                  )

                ORDER BY
                    cp.enviado_em,
                    cp.id,
                    ci.criado_em,
                    ci.id
                """,
                (
                    empresa_id,
                    setor,
                ),
            )

            linhas = cursor.fetchall()
            pedidos = []
            pedidos_por_id = {}

            for linha in linhas:
                pedido_id = int(
                    linha["pedido_id"]
                )

                pedido = pedidos_por_id.get(
                    pedido_id
                )

                if pedido is None:
                    pedido = {
                        "pedido_id": pedido_id,
                        "numero": linha[
                            "numero_sequencial"
                        ],
                        "status": linha[
                            "pedido_status"
                        ],
                        "observacoes": (
                            linha[
                                "pedido_observacoes"
                            ]
                            or ""
                        ),
                        "enviado_em": linha[
                            "enviado_em"
                        ],
                        "comanda_id": linha[
                            "comanda_id"
                        ],
                        "identificacao": (
                            linha["identificacao"]
                            or ""
                        ),
                        "mesa_numero": linha[
                            "mesa_numero"
                        ],
                        "mesa_nome": (
                            linha["mesa_nome"]
                            or ""
                        ),
                        "itens": [],
                    }

                    pedidos_por_id[
                        pedido_id
                    ] = pedido

                    pedidos.append(
                        pedido
                    )

                pedido["itens"].append(
                    {
                        "id": linha["item_id"],
                        "produto_id": linha[
                            "produto_id"
                        ],
                        "nome": linha[
                            "produto_nome"
                        ],
                        "quantidade": linha[
                            "quantidade"
                        ],
                        "observacoes": (
                            linha["observacoes"]
                            or ""
                        ),
                        "status": linha[
                            "status"
                        ],
                        "enviado_em": linha[
                            "item_enviado_em"
                        ],
                        "preparo_iniciado_em": linha[
                            "preparo_iniciado_em"
                        ],
                        "pronto_em": linha[
                            "pronto_em"
                        ],
                        "entregue_em": linha[
                            "entregue_em"
                        ],
                    }
                )

            return pedidos

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # ATUALIZAR ITEM NA PRODUÇÃO
    # =====================================================

    @classmethod
    def atualizar_item_producao(
        cls,
        *,
        empresa_id,
        item_id,
        setor,
        status,
        usuario_id=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        item_id = cls._inteiro(
            item_id,
            "Item",
        )

        setor = cls._texto(
            setor,
            30,
        ).lower()

        status = cls._texto(
            status,
            20,
        ).lower()

        if setor not in {"cozinha", "bar"}:
            raise MesasErro(
                "Setor de produção inválido."
            )

        if status not in {
            "preparando",
            "pronto",
        }:
            raise MesasErro(
                "Status de produção inválido."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    ci.id,
                    ci.comanda_id,
                    ci.pedido_id,
                    ci.produto_nome,
                    ci.status,
                    ci.setor_preparo,
                    c.status AS comanda_status

                FROM comanda_itens ci

                INNER JOIN comandas c
                    ON c.id = ci.comanda_id
                    AND c.empresa_id = ci.empresa_id

                WHERE ci.id = %s
                  AND ci.empresa_id = %s

                FOR UPDATE OF ci, c
                """,
                (
                    item_id,
                    empresa_id,
                ),
            )

            item = cursor.fetchone()

            if not item:
                raise MesasErro(
                    "Item não encontrado."
                )

            if item["setor_preparo"] != setor:
                raise MesasErro(
                    "O item pertence a outro setor."
                )

            if not item["pedido_id"]:
                raise MesasErro(
                    "O item ainda não foi enviado."
                )

            if item["comanda_status"] not in {
                "aberta",
                "aguardando_pagamento",
            }:
                raise MesasErro(
                    "A comanda não está em atendimento."
                )

            transicoes = {
                "pendente": {"preparando", "pronto"},
                "preparando": {"pronto"},
                "pronto": set(),
                "entregue": set(),
                "cancelado": set(),
            }

            if status not in transicoes.get(
                item["status"],
                set(),
            ):
                raise MesasErro(
                    "Essa mudança de status não é permitida."
                )

            cursor.execute(
                """
                UPDATE comanda_itens

                SET
                    status = %s,

                    preparo_iniciado_em = CASE
                        WHEN %s = 'preparando'
                        THEN COALESCE(
                            preparo_iniciado_em,
                            CURRENT_TIMESTAMP
                        )
                        ELSE preparo_iniciado_em
                    END,

                    pronto_em = CASE
                        WHEN %s = 'pronto'
                        THEN COALESCE(
                            pronto_em,
                            CURRENT_TIMESTAMP
                        )
                        ELSE pronto_em
                    END,

                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s

                RETURNING *
                """,
                (
                    status,
                    status,
                    status,
                    item_id,
                    empresa_id,
                ),
            )

            atualizado = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) FILTER (
                        WHERE status = 'pendente'
                    ) AS pendentes,

                    COUNT(*) FILTER (
                        WHERE status = 'preparando'
                    ) AS preparando,

                    COUNT(*) FILTER (
                        WHERE status = 'pronto'
                    ) AS prontos,

                    COUNT(*) FILTER (
                        WHERE status = 'entregue'
                    ) AS entregues,

                    COUNT(*) FILTER (
                        WHERE status != 'cancelado'
                    ) AS total

                FROM comanda_itens

                WHERE pedido_id = %s
                  AND empresa_id = %s
                """,
                (
                    item["pedido_id"],
                    empresa_id,
                ),
            )

            resumo = cursor.fetchone()

            if (
                resumo["total"] > 0
                and (
                    resumo["prontos"]
                    + resumo["entregues"]
                ) == resumo["total"]
            ):
                status_pedido = "pronto"

            elif resumo["preparando"] > 0:
                status_pedido = "preparando"

            else:
                status_pedido = "recebido"

            cursor.execute(
                """
                UPDATE comanda_pedidos

                SET
                    status = %s,

                    iniciado_em = CASE
                        WHEN %s = 'preparando'
                        THEN COALESCE(
                            iniciado_em,
                            CURRENT_TIMESTAMP
                        )
                        ELSE iniciado_em
                    END,

                    pronto_em = CASE
                        WHEN %s = 'pronto'
                        THEN COALESCE(
                            pronto_em,
                            CURRENT_TIMESTAMP
                        )
                        ELSE pronto_em
                    END,

                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    status_pedido,
                    status_pedido,
                    status_pedido,
                    item["pedido_id"],
                    empresa_id,
                ),
            )

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'status_producao',
                    %s
                )
                """,
                (
                    empresa_id,
                    item["comanda_id"],
                    usuario_id,
                    (
                        f"{item['produto_nome']}: "
                        f"{status} no setor {setor}."
                    ),
                ),
            )

            conn.commit()

            return {
                "item_id": atualizado["id"],
                "pedido_id": atualizado[
                    "pedido_id"
                ],
                "comanda_id": atualizado[
                    "comanda_id"
                ],
                "produto_nome": atualizado[
                    "produto_nome"
                ],
                "status": atualizado[
                    "status"
                ],
                "setor": atualizado[
                    "setor_preparo"
                ],
                "pedido_status": status_pedido,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    # =====================================================
    # RESUMO DO PAINEL
    # =====================================================

    @classmethod
    def resumo(
        cls,
        empresa_id,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,

                    COUNT(*) FILTER (
                        WHERE status = 'livre'
                    ) AS livres,

                    COUNT(*) FILTER (
                        WHERE status = 'ocupada'
                    ) AS ocupadas,

                    COUNT(*) FILTER (
                        WHERE status = 'reservada'
                    ) AS reservadas,

                    COUNT(*) FILTER (
                        WHERE status = 'inativa'
                    ) AS inativas

                FROM mesas

                WHERE empresa_id = %s
                """,
                (empresa_id,),
            )

            resumo = cursor.fetchone()

            cursor.execute(
                """
                SELECT
                    COUNT(*) AS comandas_abertas,

                    COALESCE(
                        SUM(total),
                        0
                    ) AS total_em_aberto

                FROM comandas

                WHERE empresa_id = %s
                  AND status IN (
                      'aberta',
                      'aguardando_pagamento'
                  )
                """,
                (empresa_id,),
            )

            comandas = cursor.fetchone()

            resumo.update(comandas)

            return resumo

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # CADASTRAR MESA
    # =====================================================

    @classmethod
    def criar_mesa(
        cls,
        *,
        empresa_id,
        numero,
        nome=None,
        capacidade=4,
        observacoes=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        numero = cls._texto(
            numero,
            20,
        )

        nome = cls._texto(
            nome,
            100,
        ) or None

        capacidade = cls._inteiro(
            capacidade,
            "Capacidade",
        )

        observacoes = cls._texto(
            observacoes,
            1000,
        ) or None

        if not numero:
            raise MesasErro(
                "Informe o número ou código da mesa."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                INSERT INTO mesas (
                    empresa_id,
                    numero,
                    nome,
                    capacidade,
                    status,
                    observacoes
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'livre',
                    %s
                )
                RETURNING *
                """,
                (
                    empresa_id,
                    numero,
                    nome,
                    capacidade,
                    observacoes,
                ),
            )

            mesa = cursor.fetchone()

            conn.commit()

            return mesa

        except Exception as erro:

            conn.rollback()

            if getattr(
                erro,
                "pgcode",
                None,
            ) == "23505":

                raise MesasErro(
                    "Já existe uma mesa com esse número."
                ) from erro

            raise

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # ALTERAR MESA
    # =====================================================

    @classmethod
    def editar_mesa(
        cls,
        *,
        empresa_id,
        mesa_id,
        numero,
        nome=None,
        capacidade=4,
        observacoes=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        mesa_id = cls._inteiro(
            mesa_id,
            "Mesa",
        )

        numero = cls._texto(
            numero,
            20,
        )

        nome = cls._texto(
            nome,
            100,
        ) or None

        capacidade = cls._inteiro(
            capacidade,
            "Capacidade",
        )

        observacoes = cls._texto(
            observacoes,
            1000,
        ) or None

        if not numero:
            raise MesasErro(
                "Informe o número ou código da mesa."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                UPDATE mesas

                SET
                    numero = %s,
                    nome = %s,
                    capacidade = %s,
                    observacoes = %s,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s

                RETURNING *
                """,
                (
                    numero,
                    nome,
                    capacidade,
                    observacoes,
                    mesa_id,
                    empresa_id,
                ),
            )

            mesa = cursor.fetchone()

            if not mesa:
                raise MesasErro(
                    "Mesa não encontrada."
                )

            conn.commit()

            return mesa

        except Exception as erro:

            conn.rollback()

            if isinstance(
                erro,
                MesasErro,
            ):
                raise

            if getattr(
                erro,
                "pgcode",
                None,
            ) == "23505":

                raise MesasErro(
                    "Já existe uma mesa com esse número."
                ) from erro

            raise

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # ALTERAR STATUS DA MESA
    # =====================================================

    @classmethod
    def alterar_status_mesa(
        cls,
        *,
        empresa_id,
        mesa_id,
        status,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        mesa_id = cls._inteiro(
            mesa_id,
            "Mesa",
        )

        status = cls._texto(
            status,
            20,
        ).lower()

        if status not in cls.STATUS_MESA:
            raise MesasErro(
                "Status da mesa inválido."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    m.id,
                    m.status,

                    EXISTS (
                        SELECT 1

                        FROM comandas c

                        WHERE c.mesa_id = m.id
                          AND c.empresa_id = m.empresa_id
                          AND c.status IN (
                              'aberta',
                              'aguardando_pagamento'
                          )
                    ) AS possui_comanda

                FROM mesas m

                WHERE m.id = %s
                  AND m.empresa_id = %s

                FOR UPDATE
                """,
                (
                    mesa_id,
                    empresa_id,
                ),
            )

            mesa = cursor.fetchone()

            if not mesa:
                raise MesasErro(
                    "Mesa não encontrada."
                )

            if (
                mesa["possui_comanda"]
                and status != "ocupada"
            ):
                raise MesasErro(
                    "A mesa possui uma comanda aberta."
                )

            cursor.execute(
                """
                UPDATE mesas

                SET
                    status = %s,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s

                RETURNING *
                """,
                (
                    status,
                    mesa_id,
                    empresa_id,
                ),
            )

            atualizada = cursor.fetchone()

            conn.commit()

            return atualizada

        except Exception:

            conn.rollback()
            raise

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # ABRIR COMANDA
    # =====================================================

    @classmethod
    def abrir_comanda(
        cls,
        *,
        empresa_id,
        mesa_id,
        usuario_id,
        cliente_id=None,
        identificacao=None,
        quantidade_pessoas=1,
        observacoes=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        mesa_id = cls._inteiro(
            mesa_id,
            "Mesa",
        )

        usuario_id = cls._inteiro(
            usuario_id,
            "Usuário",
        )

        quantidade_pessoas = cls._inteiro(
            quantidade_pessoas,
            "Quantidade de pessoas",
        )

        identificacao = cls._texto(
            identificacao,
            120,
        ) or None

        observacoes = cls._texto(
            observacoes,
            1000,
        ) or None

        if cliente_id:

            cliente_id = cls._inteiro(
                cliente_id,
                "Cliente",
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    numero,
                    nome,
                    status

                FROM mesas

                WHERE id = %s
                  AND empresa_id = %s

                FOR UPDATE
                """,
                (
                    mesa_id,
                    empresa_id,
                ),
            )

            mesa = cursor.fetchone()

            if not mesa:
                raise MesasErro(
                    "Mesa não encontrada."
                )

            if mesa["status"] == "inativa":
                raise MesasErro(
                    "Essa mesa está inativa."
                )

            cursor.execute(
                """
                SELECT id

                FROM comandas

                WHERE mesa_id = %s
                  AND empresa_id = %s
                  AND status IN (
                      'aberta',
                      'aguardando_pagamento'
                  )

                LIMIT 1

                FOR UPDATE
                """,
                (
                    mesa_id,
                    empresa_id,
                ),
            )

            if cursor.fetchone():
                raise MesasErro(
                    "Essa mesa já possui uma comanda aberta."
                )

            cursor.execute(
                """
                INSERT INTO comandas (
                    empresa_id,
                    mesa_id,
                    cliente_id,
                    funcionario_id,
                    identificacao,
                    quantidade_pessoas,
                    status,
                    subtotal,
                    desconto_valor,
                    desconto_percentual,
                    total,
                    observacoes
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    'aberta',
                    0,
                    0,
                    0,
                    0,
                    %s
                )
                RETURNING *
                """,
                (
                    empresa_id,
                    mesa_id,
                    cliente_id,
                    usuario_id,
                    identificacao,
                    quantidade_pessoas,
                    observacoes,
                ),
            )

            comanda = cursor.fetchone()

            cursor.execute(
                """
                UPDATE mesas

                SET
                    status = 'ocupada',
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    mesa_id,
                    empresa_id,
                ),
            )

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'comanda_aberta',
                    %s
                )
                """,
                (
                    empresa_id,
                    comanda["id"],
                    usuario_id,
                    (
                        "Comanda aberta na mesa "
                        f"{mesa['numero']}."
                    ),
                ),
            )

            conn.commit()

            return comanda

        except Exception:

            conn.rollback()
            raise

        
        
        finally:

            cursor.close()
            conn.close()
            
        # =====================================================
    # RECALCULAR TOTAL DA COMANDA
    # =====================================================

    @classmethod
    def _recalcular_comanda(
        cls,
        cursor,
        *,
        empresa_id,
        comanda_id,
    ):

        cursor.execute(
            """
            SELECT
                COALESCE(
                    SUM(subtotal) FILTER (
                        WHERE status != 'cancelado'
                    ),
                    0
                ) AS subtotal

            FROM comanda_itens

            WHERE empresa_id = %s
              AND comanda_id = %s
            """,
            (
                empresa_id,
                comanda_id,
            ),
        )

        resultado = cursor.fetchone()

        subtotal = Decimal(
            str(resultado["subtotal"] or 0)
        )

        cursor.execute(
            """
            UPDATE comandas

            SET
                subtotal = %s,

                total = GREATEST(
                    %s - desconto_valor,
                    0
                ),

                atualizado_em = CURRENT_TIMESTAMP

            WHERE id = %s
              AND empresa_id = %s

            RETURNING *
            """,
            (
                subtotal,
                subtotal,
                comanda_id,
                empresa_id,
            ),
        )

        return cursor.fetchone()

    # =====================================================
    # DETALHAR COMANDA
    # =====================================================

    @classmethod
    def detalhar_comanda(
        cls,
        *,
        empresa_id,
        comanda_id,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        comanda_id = cls._inteiro(
            comanda_id,
            "Comanda",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    c.*,

                    m.numero AS mesa_numero,
                    m.nome AS mesa_nome,
                    m.capacidade AS mesa_capacidade,

                    u.usuario AS funcionario_nome,

                    cl.nome AS cliente_nome,
                    cl.telefone AS cliente_telefone

                FROM comandas c

                LEFT JOIN mesas m
                    ON m.id = c.mesa_id
                    AND m.empresa_id = c.empresa_id

                LEFT JOIN usuarios u
                    ON u.id = c.funcionario_id
                    AND u.empresa_id = c.empresa_id

                LEFT JOIN clientes cl
                    ON cl.id = c.cliente_id
                    AND cl.empresa_id = c.empresa_id

                WHERE c.id = %s
                  AND c.empresa_id = %s

                LIMIT 1
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            comanda = cursor.fetchone()

            if not comanda:
                raise MesasErro(
                    "Comanda não encontrada."
                )

            cursor.execute(
                """
                SELECT
                    id,
                    pedido_id,
                    produto_id,
                    produto_nome,
                    quantidade,
                    valor_unitario,
                    subtotal,
                    status,
                    observacoes,
                    setor_preparo,
                    enviado_em,
                    criado_em,
                    atualizado_em

                FROM comanda_itens

                WHERE comanda_id = %s
                  AND empresa_id = %s

                ORDER BY
                    CASE status
                        WHEN 'pendente' THEN 1
                        WHEN 'preparando' THEN 2
                        WHEN 'pronto' THEN 3
                        WHEN 'entregue' THEN 4
                        ELSE 5
                    END,
                    criado_em DESC
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            itens = cursor.fetchall()

            cursor.execute(
                """
                SELECT
                    id,
                    acao,
                    descricao,
                    criado_em

                FROM comanda_historico

                WHERE comanda_id = %s
                  AND empresa_id = %s

                ORDER BY criado_em DESC

                LIMIT 50
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            historico = cursor.fetchall()

            return {
                "comanda": comanda,
                "itens": itens,
                "historico": historico,
            }

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # LISTAR PRODUTOS DISPONÍVEIS
    # =====================================================

    @classmethod
    def listar_produtos(
        cls,
        empresa_id,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    preco,
                    estoque

                FROM produtos

                WHERE empresa_id = %s
                  AND estoque > 0

                ORDER BY nome
                """,
                (empresa_id,),
            )

            return cursor.fetchall()

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # ADICIONAR ITEM
    # =====================================================

    @classmethod
    def adicionar_item(
        cls,
        *,
        empresa_id,
        comanda_id,
        produto_id,
        quantidade=1,
        observacoes=None,
        usuario_id=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        comanda_id = cls._inteiro(
            comanda_id,
            "Comanda",
        )

        produto_id = cls._inteiro(
            produto_id,
            "Produto",
        )

        quantidade = cls._decimal(
            quantidade,
            "Quantidade",
        )

        if quantidade <= 0:
            raise MesasErro(
                "A quantidade deve ser maior que zero."
            )

        observacoes = cls._texto(
            observacoes,
            1000,
        ) or None

        if usuario_id:
            usuario_id = cls._inteiro(
                usuario_id,
                "Usuário",
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    id,
                    status

                FROM comandas

                WHERE id = %s
                  AND empresa_id = %s

                FOR UPDATE
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            comanda = cursor.fetchone()

            if not comanda:
                raise MesasErro(
                    "Comanda não encontrada."
                )

            if comanda["status"] != "aberta":
                raise MesasErro(
                    "Essa comanda não aceita novos itens."
                )

            cursor.execute(
                """
                SELECT
                    id,
                    nome,
                    preco,
                    estoque,
                    setor_preparo

                FROM produtos

                WHERE id = %s
                  AND empresa_id = %s

                FOR UPDATE
                """,
                (
                    produto_id,
                    empresa_id,
                ),
            )

            produto = cursor.fetchone()

            if not produto:
                raise MesasErro(
                    "Produto não encontrado."
                )

            estoque = Decimal(
                str(produto["estoque"] or 0)
            )

            if quantidade > estoque:
                raise MesasErro(
                    (
                        "Estoque insuficiente. "
                        f"Disponível: {estoque}."
                    )
                )

            valor_unitario = Decimal(
                str(produto["preco"] or 0)
            ).quantize(
                Decimal("0.01")
            )

            subtotal = (
                valor_unitario
                * quantidade
            ).quantize(
                Decimal("0.01")
            )

            cursor.execute(
                """
                INSERT INTO comanda_itens (
                    empresa_id,
                    comanda_id,
                    produto_id,
                    produto_nome,
                    quantidade,
                    valor_unitario,
                    subtotal,
                    status,
                    observacoes,
                    setor_preparo
                )
                VALUES (
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
                RETURNING *
                """,
                (
                    empresa_id,
                    comanda_id,
                    produto_id,
                    produto["nome"],
                    quantidade,
                    valor_unitario,
                    subtotal,
                    observacoes,
                    (
                        produto["setor_preparo"]
                        or "cozinha"
                    ),
                ),
            )

            item = cursor.fetchone()

            cls._recalcular_comanda(
                cursor,
                empresa_id=empresa_id,
                comanda_id=comanda_id,
            )

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'item_adicionado',
                    %s
                )
                """,
                (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    (
                        f"{quantidade}x "
                        f"{produto['nome']} adicionado."
                    ),
                ),
            )

            conn.commit()

            return item

        except Exception:

            conn.rollback()
            raise

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # ALTERAR QUANTIDADE
    # =====================================================

    @classmethod
    def alterar_quantidade_item(
        cls,
        *,
        empresa_id,
        comanda_id,
        item_id,
        quantidade,
        usuario_id=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        comanda_id = cls._inteiro(
            comanda_id,
            "Comanda",
        )

        item_id = cls._inteiro(
            item_id,
            "Item",
        )

        quantidade = cls._decimal(
            quantidade,
            "Quantidade",
        )

        if quantidade <= 0:
            raise MesasErro(
                "A quantidade deve ser maior que zero."
            )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                SELECT
                    ci.*,
                    p.estoque

                FROM comanda_itens ci

                LEFT JOIN produtos p
                    ON p.id = ci.produto_id
                    AND p.empresa_id = ci.empresa_id

                WHERE ci.id = %s
                  AND ci.comanda_id = %s
                  AND ci.empresa_id = %s

                FOR UPDATE OF ci
                """,
                (
                    item_id,
                    comanda_id,
                    empresa_id,
                ),
            )

            item = cursor.fetchone()

            if not item:
                raise MesasErro(
                    "Item não encontrado."
                )

            if item["status"] == "cancelado":
                raise MesasErro(
                    "O item está cancelado."
                )

            if item["estoque"] is not None:

                estoque = Decimal(
                    str(item["estoque"])
                )

                if quantidade > estoque:
                    raise MesasErro(
                        (
                            "Estoque insuficiente. "
                            f"Disponível: {estoque}."
                        )
                    )

            valor_unitario = Decimal(
                str(item["valor_unitario"])
            )

            subtotal = (
                valor_unitario
                * quantidade
            ).quantize(
                Decimal("0.01")
            )

            cursor.execute(
                """
                UPDATE comanda_itens

                SET
                    quantidade = %s,
                    subtotal = %s,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND comanda_id = %s
                  AND empresa_id = %s

                RETURNING *
                """,
                (
                    quantidade,
                    subtotal,
                    item_id,
                    comanda_id,
                    empresa_id,
                ),
            )

            atualizado = cursor.fetchone()

            cls._recalcular_comanda(
                cursor,
                empresa_id=empresa_id,
                comanda_id=comanda_id,
            )

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'quantidade_alterada',
                    %s
                )
                """,
                (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    (
                        f"Quantidade de "
                        f"{item['produto_nome']} "
                        f"alterada para {quantidade}."
                    ),
                ),
            )

            conn.commit()

            return atualizado

        except Exception:

            conn.rollback()
            raise

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # ALTERAR STATUS DO ITEM
    # =====================================================

    @classmethod
    def alterar_status_item(
        cls,
        *,
        empresa_id,
        comanda_id,
        item_id,
        status,
        usuario_id=None,
    ):

        status = cls._texto(
            status,
            20,
        ).lower()

        status_validos = {
            "pendente",
            "preparando",
            "pronto",
            "entregue",
            "cancelado",
        }

        if status not in status_validos:
            raise MesasErro(
                "Status do item inválido."
            )

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        comanda_id = cls._inteiro(
            comanda_id,
            "Comanda",
        )

        item_id = cls._inteiro(
            item_id,
            "Item",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            cursor.execute(
                """
                UPDATE comanda_itens

                SET
                    status = %s,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND comanda_id = %s
                  AND empresa_id = %s
                  AND status != 'cancelado'

                RETURNING *
                """,
                (
                    status,
                    item_id,
                    comanda_id,
                    empresa_id,
                ),
            )

            item = cursor.fetchone()

            if not item:
                raise MesasErro(
                    "Item não encontrado ou já cancelado."
                )

            cls._recalcular_comanda(
                cursor,
                empresa_id=empresa_id,
                comanda_id=comanda_id,
            )

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    (
                        "item_cancelado"
                        if status == "cancelado"
                        else "status_item_alterado"
                    ),
                    (
                        f"{item['produto_nome']}: "
                        f"{status}."
                    ),
                ),
            )

            conn.commit()

            return item

        except Exception:

            conn.rollback()
            raise

        finally:

            cursor.close()
            conn.close()
            
        # =====================================================
    # ENVIAR PEDIDO PARA PRODUÇÃO
    # =====================================================

    @classmethod
    def enviar_pedido(
        cls,
        *,
        empresa_id,
        comanda_id,
        usuario_id,
        observacoes=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        comanda_id = cls._inteiro(
            comanda_id,
            "Comanda",
        )

        usuario_id = cls._inteiro(
            usuario_id,
            "Usuário",
        )

        observacoes = cls._texto(
            observacoes,
            1000,
        ) or None

        conn = conectar()
        cursor = criar_cursor(conn)

        try:

            # =============================================
            # BLOQUEAR A COMANDA
            # =============================================

            cursor.execute(
                """
                SELECT
                    c.id,
                    c.status,
                    c.mesa_id,

                    m.numero AS mesa_numero,
                    m.nome AS mesa_nome

                FROM comandas c

                LEFT JOIN mesas m
                    ON m.id = c.mesa_id
                    AND m.empresa_id = c.empresa_id

                WHERE c.id = %s
                  AND c.empresa_id = %s

                FOR UPDATE OF c
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            comanda = cursor.fetchone()

            if not comanda:
                raise MesasErro(
                    "Comanda não encontrada."
                )

            if comanda["status"] != "aberta":
                raise MesasErro(
                    (
                        "Somente comandas abertas "
                        "podem enviar pedidos."
                    )
                )

            # =============================================
            # BUSCAR ITENS AINDA NÃO ENVIADOS
            # =============================================

            cursor.execute(
                """
                SELECT
                    id,
                    produto_id,
                    produto_nome,
                    quantidade,
                    valor_unitario,
                    subtotal,
                    observacoes,
                    setor_preparo,
                    status

                FROM comanda_itens

                WHERE empresa_id = %s
                  AND comanda_id = %s
                  AND pedido_id IS NULL
                  AND status != 'cancelado'

                ORDER BY criado_em

                FOR UPDATE
                """,
                (
                    empresa_id,
                    comanda_id,
                ),
            )

            itens = cursor.fetchall()

            if not itens:
                raise MesasErro(
                    (
                        "Não existem novos itens "
                        "para enviar."
                    )
                )

            # =============================================
            # NÚMERO DA RODADA
            # =============================================

            cursor.execute(
                """
                SELECT
                    COALESCE(
                        MAX(numero_sequencial),
                        0
                    ) + 1 AS proximo_numero

                FROM comanda_pedidos

                WHERE empresa_id = %s
                  AND comanda_id = %s
                """,
                (
                    empresa_id,
                    comanda_id,
                ),
            )

            numero = cursor.fetchone()[
                "proximo_numero"
            ]

            # =============================================
            # CRIAR O LOTE DO PEDIDO
            # =============================================

            cursor.execute(
                """
                INSERT INTO comanda_pedidos (
                    empresa_id,
                    comanda_id,
                    enviado_por,
                    numero_sequencial,
                    origem,
                    status,
                    observacoes
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    'garcom',
                    'recebido',
                    %s
                )
                RETURNING *
                """,
                (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    numero,
                    observacoes,
                ),
            )

            pedido = cursor.fetchone()

            ids_itens = [
                item["id"]
                for item in itens
            ]

            # =============================================
            # MARCAR ITENS COMO ENVIADOS
            # =============================================

            cursor.execute(
                """
                UPDATE comanda_itens

                SET
                    pedido_id = %s,
                    enviado_em = CURRENT_TIMESTAMP,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE empresa_id = %s
                  AND comanda_id = %s
                  AND id = ANY(%s)
                  AND pedido_id IS NULL
                """,
                (
                    pedido["id"],
                    empresa_id,
                    comanda_id,
                    ids_itens,
                ),
            )

            # Itens de entrega direta não dependem da cozinha
            # nem do bar. Eles já ficam disponíveis para entrega
            # assim que o garçom envia a rodada.
            cursor.execute(
                """
                UPDATE comanda_itens

                SET
                    status = 'pronto',
                    pronto_em = COALESCE(
                        pronto_em,
                        CURRENT_TIMESTAMP
                    ),
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE empresa_id = %s
                  AND comanda_id = %s
                  AND pedido_id = %s
                  AND setor_preparo = 'direto'
                  AND status = 'pendente'
                """,
                (
                    empresa_id,
                    comanda_id,
                    pedido["id"],
                ),
            )

            # =============================================
            # REGISTRAR HISTÓRICO
            # =============================================

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'pedido_enviado',
                    %s
                )
                """,
                (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    (
                        f"Pedido #{numero} enviado "
                        f"com {len(itens)} item(ns)."
                    ),
                ),
            )

            conn.commit()

            # =============================================
            # PAYLOAD SEGURO PARA O SOCKET.IO
            # =============================================

            itens_socket = []

            for item in itens:

                itens_socket.append(
                    {
                        "id": item["id"],
                        "produto_id": item[
                            "produto_id"
                        ],
                        "nome": item[
                            "produto_nome"
                        ],
                        "quantidade": float(
                            item["quantidade"]
                        ),
                        "valor_unitario": float(
                            item["valor_unitario"]
                        ),
                        "subtotal": float(
                            item["subtotal"]
                        ),
                        "observacoes": (
                            item["observacoes"]
                            or ""
                        ),
                        "setor": (
                            item["setor_preparo"]
                            or "cozinha"
                        ),
                        "status": item["status"],
                    }
                )

            return {
                "pedido_id": pedido["id"],
                "numero": numero,
                "empresa_id": empresa_id,
                "comanda_id": comanda_id,
                "mesa_id": comanda["mesa_id"],
                "mesa_numero": comanda[
                    "mesa_numero"
                ],
                "mesa_nome": (
                    comanda["mesa_nome"]
                    or ""
                ),
                "observacoes": (
                    observacoes
                    or ""
                ),
                "itens": itens_socket,
            }

        except Exception:

            conn.rollback()
            raise

        finally:

            cursor.close()
            conn.close()

    # =====================================================
    # FINALIZAR E RECEBER COMANDA
    # =====================================================

    @classmethod
    def finalizar_comanda(
        cls,
        *,
        empresa_id,
        comanda_id,
        recebido_por,
        pagamento,
        tipo_desconto="nenhum",
        desconto_informado="0",
        cliente_id=None,
    ):

        empresa_id = cls._inteiro(
            empresa_id,
            "Empresa",
        )

        comanda_id = cls._inteiro(
            comanda_id,
            "Comanda",
        )

        recebido_por = cls._inteiro(
            recebido_por,
            "Usuário",
        )

        pagamentos = {
            "dinheiro": "Dinheiro",
            "pix": "PIX",
            "cartão": "Cartão",
            "cartao": "Cartão",
        }

        pagamento = pagamentos.get(
            cls._texto(
                pagamento,
                30,
            ).lower()
        )

        if not pagamento:
            raise MesasErro(
                "Forma de pagamento inválida."
            )

        if cliente_id in {
            None,
            "",
            "0",
            0,
        }:
            cliente_id = None
        else:
            cliente_id = cls._inteiro(
                cliente_id,
                "Cliente",
            )

        tipo_desconto = cls._texto(
            tipo_desconto,
            20,
        ).lower()

        if tipo_desconto not in {
            "nenhum",
            "percentual",
            "valor",
        }:
            raise MesasErro(
                "Tipo de desconto inválido."
            )

        desconto_informado = cls._moeda(
            desconto_informado,
            "Desconto",
        )

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            # A trava da comanda impede pagamento duplicado
            # quando dois terminais confirmam ao mesmo tempo.
            cursor.execute(
                """
                SELECT
                    c.*,
                    m.numero AS mesa_numero,
                    m.nome AS mesa_nome

                FROM comandas c

                LEFT JOIN mesas m
                    ON m.id = c.mesa_id
                    AND m.empresa_id = c.empresa_id

                WHERE c.id = %s
                  AND c.empresa_id = %s

                FOR UPDATE OF c
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            comanda = cursor.fetchone()

            if not comanda:
                raise MesasErro(
                    "Comanda não encontrada."
                )

            if comanda["status"] not in {
                "aberta",
                "aguardando_pagamento",
            }:
                raise MesasErro(
                    "A comanda já foi finalizada ou cancelada."
                )

            cursor.execute(
                """
                SELECT
                    ci.id,
                    ci.produto_id,
                    ci.produto_nome,
                    ci.quantidade,
                    ci.valor_unitario,
                    ci.subtotal,
                    ci.status,
                    ci.pedido_id,
                    p.estoque

                FROM comanda_itens ci

                INNER JOIN produtos p
                    ON p.id = ci.produto_id
                    AND p.empresa_id = ci.empresa_id

                WHERE ci.comanda_id = %s
                  AND ci.empresa_id = %s
                  AND ci.status != 'cancelado'

                ORDER BY ci.id

                FOR UPDATE OF ci, p
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            itens = cursor.fetchall()

            if not itens:
                raise MesasErro(
                    "A comanda não possui itens válidos."
                )

            nao_enviados = [
                item
                for item in itens
                if not item["pedido_id"]
            ]

            if nao_enviados:
                raise MesasErro(
                    "Envie todos os itens antes de fechar a comanda."
                )

            em_producao = [
                item
                for item in itens
                if item["status"] in {
                    "pendente",
                    "preparando",
                }
            ]

            if em_producao:
                raise MesasErro(
                    "Ainda existem itens em produção."
                )

            cursor.execute(
                """
                SELECT
                    id,
                    valor_final

                FROM caixa

                WHERE empresa_id = %s
                  AND status = 'aberto'

                ORDER BY id DESC
                LIMIT 1

                FOR UPDATE
                """,
                (empresa_id,),
            )

            caixa = cursor.fetchone()

            if not caixa:
                raise MesasErro(
                    "Abra o caixa antes de receber a comanda."
                )

            if cliente_id is None:
                cliente_id = comanda[
                    "cliente_id"
                ]

            cliente = None

            if cliente_id is not None:
                cursor.execute(
                    """
                    SELECT
                        id,
                        nome,
                        telefone,
                        cpf_cnpj

                    FROM clientes

                    WHERE id = %s
                      AND empresa_id = %s
                      AND ativo = TRUE

                    LIMIT 1
                    """,
                    (
                        cliente_id,
                        empresa_id,
                    ),
                )

                cliente = cursor.fetchone()

                if not cliente:
                    raise MesasErro(
                        "O cliente selecionado é inválido."
                    )

            total_bruto = sum(
                (
                    cls._moeda(
                        item["subtotal"],
                        "Subtotal",
                    )
                    for item in itens
                ),
                Decimal("0.00"),
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            if total_bruto <= 0:
                raise MesasErro(
                    "O total da comanda é inválido."
                )

            if tipo_desconto == "percentual":
                if desconto_informado > 100:
                    raise MesasErro(
                        "O desconto não pode ultrapassar 100%."
                    )

                percentual = desconto_informado

                desconto_total = (
                    total_bruto
                    * percentual
                    / Decimal("100")
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

            elif tipo_desconto == "valor":
                desconto_total = desconto_informado

                percentual = (
                    desconto_total
                    * Decimal("100")
                    / total_bruto
                ).quantize(
                    Decimal("0.0001"),
                    rounding=ROUND_HALF_UP,
                )

            else:
                desconto_total = Decimal("0.00")
                percentual = Decimal("0.0000")

            if desconto_total >= total_bruto:
                raise MesasErro(
                    "O desconto deve ser menor que o total."
                )

            total_liquido = (
                total_bruto
                - desconto_total
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            venda_grupo = str(
                uuid4()
            )

            usuario_venda = (
                comanda["funcionario_id"]
                or recebido_por
            )

            linhas_vendas = []
            estoque_por_produto = {}
            cupom = []
            desconto_restante = desconto_total

            for indice, item in enumerate(itens):
                quantidade_decimal = Decimal(
                    str(item["quantidade"])
                )

                if (
                    quantidade_decimal
                    != quantidade_decimal.to_integral_value()
                ):
                    raise MesasErro(
                        "A quantidade de "
                        f"{item['produto_nome']} "
                        "precisa ser inteira para concluir a venda."
                    )

                quantidade = int(
                    quantidade_decimal
                )

                produto_id = int(
                    item["produto_id"]
                )

                acumulado = (
                    estoque_por_produto.get(
                        produto_id,
                        {
                            "quantidade": 0,
                            "estoque": int(
                                item["estoque"]
                                or 0
                            ),
                            "nome": item[
                                "produto_nome"
                            ],
                        },
                    )
                )

                acumulado[
                    "quantidade"
                ] += quantidade

                estoque_por_produto[
                    produto_id
                ] = acumulado

                valor_bruto = cls._moeda(
                    item["subtotal"],
                    "Subtotal",
                )

                ultimo = (
                    indice
                    == len(itens) - 1
                )

                if ultimo:
                    desconto_item = desconto_restante
                else:
                    desconto_item = (
                        desconto_total
                        * valor_bruto
                        / total_bruto
                    ).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP,
                    )

                    desconto_item = min(
                        desconto_item,
                        desconto_restante,
                    )

                desconto_restante -= desconto_item

                valor_liquido = (
                    valor_bruto
                    - desconto_item
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

                linhas_vendas.append(
                    (
                        produto_id,
                        quantidade,
                        valor_liquido,
                        valor_bruto,
                        desconto_item,
                        percentual,
                        venda_grupo,
                        pagamento,
                        empresa_id,
                        caixa["id"],
                        usuario_venda,
                        cliente_id,
                    )
                )

                cupom.append(
                    {
                        "nome": item[
                            "produto_nome"
                        ],
                        "quantidade": quantidade,
                        "preco_unitario": cls._moeda(
                            item["valor_unitario"],
                            "Valor unitário",
                        ),
                        "valor_bruto": valor_bruto,
                        "desconto": desconto_item,
                        "valor": valor_liquido,
                        "pagamento": pagamento,
                        "empresa_id": empresa_id,
                        "venda_grupo": venda_grupo,
                        "cliente_id": cliente_id,
                        "cliente_nome": (
                            cliente["nome"]
                            if cliente
                            else None
                        ),
                        "cliente_telefone": (
                            cliente["telefone"]
                            if cliente
                            else None
                        ),
                        "cliente_cpf_cnpj": (
                            cliente["cpf_cnpj"]
                            if cliente
                            else None
                        ),
                    }
                )

            linhas_estoque = []

            for (
                produto_id,
                controle,
            ) in estoque_por_produto.items():

                if (
                    controle["estoque"]
                    < controle["quantidade"]
                ):
                    raise MesasErro(
                        "Estoque insuficiente para "
                        f"{controle['nome']}. "
                        "Disponível: "
                        f"{controle['estoque']}."
                    )

                linhas_estoque.append(
                    (
                        produto_id,
                        controle["quantidade"],
                        empresa_id,
                    )
                )

            estoques_atualizados = execute_values(
                cursor,
                """
                WITH dados (
                    produto_id,
                    quantidade,
                    empresa_id
                ) AS (
                    VALUES %s
                )

                UPDATE produtos p

                SET estoque = (
                    p.estoque
                    - dados.quantidade
                )

                FROM dados

                WHERE p.id = dados.produto_id
                  AND p.empresa_id = dados.empresa_id
                  AND p.estoque >= dados.quantidade

                RETURNING p.id
                """,
                linhas_estoque,
                template="(%s, %s, %s)",
                page_size=len(
                    linhas_estoque
                ),
                fetch=True,
            )

            if len(
                estoques_atualizados
            ) != len(
                linhas_estoque
            ):
                raise MesasErro(
                    "O estoque mudou durante o pagamento. "
                    "Confira a comanda novamente."
                )

            execute_values(
                cursor,
                """
                INSERT INTO vendas (
                    produto_id,
                    quantidade,
                    valor,
                    valor_bruto,
                    desconto_valor,
                    desconto_percentual,
                    venda_grupo,
                    pagamento,
                    empresa_id,
                    caixa_id,
                    usuario_id,
                    cliente_id,
                    data_venda
                )
                VALUES %s
                """,
                linhas_vendas,
                template=(
                    "("
                    "%s, %s, %s, %s, %s, %s, "
                    "%s, %s, %s, %s, %s, %s, "
                    "CURRENT_TIMESTAMP"
                    ")"
                ),
                page_size=len(
                    linhas_vendas
                ),
            )

            cursor.execute(
                """
                UPDATE caixa

                SET valor_final = (
                    COALESCE(
                        valor_final,
                        0
                    )
                    + %s
                )

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    total_liquido,
                    caixa["id"],
                    empresa_id,
                ),
            )

            if cursor.rowcount != 1:
                raise MesasErro(
                    "Não foi possível atualizar o caixa."
                )

            cursor.execute(
                """
                UPDATE comanda_itens

                SET
                    status = CASE
                        WHEN status = 'cancelado'
                        THEN status
                        ELSE 'entregue'
                    END,

                    entregue_em = CASE
                        WHEN status != 'cancelado'
                        THEN COALESCE(
                            entregue_em,
                            CURRENT_TIMESTAMP
                        )
                        ELSE entregue_em
                    END,

                    atualizado_em = CURRENT_TIMESTAMP

                WHERE comanda_id = %s
                  AND empresa_id = %s
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            cursor.execute(
                """
                UPDATE comanda_pedidos

                SET
                    status = 'entregue',
                    entregue_em = COALESCE(
                        entregue_em,
                        CURRENT_TIMESTAMP
                    ),
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE comanda_id = %s
                  AND empresa_id = %s
                  AND status != 'cancelado'
                """,
                (
                    comanda_id,
                    empresa_id,
                ),
            )

            cursor.execute(
                """
                UPDATE comandas

                SET
                    cliente_id = %s,
                    status = 'fechada',
                    subtotal = %s,
                    desconto_valor = %s,
                    desconto_percentual = %s,
                    total = %s,
                    fechada_em = CURRENT_TIMESTAMP,
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    cliente_id,
                    total_bruto,
                    desconto_total,
                    percentual,
                    total_liquido,
                    comanda_id,
                    empresa_id,
                ),
            )

            cursor.execute(
                """
                UPDATE mesas

                SET
                    status = 'livre',
                    atualizado_em = CURRENT_TIMESTAMP

                WHERE id = %s
                  AND empresa_id = %s
                """,
                (
                    comanda["mesa_id"],
                    empresa_id,
                ),
            )

            cursor.execute(
                """
                INSERT INTO comanda_historico (
                    empresa_id,
                    comanda_id,
                    usuario_id,
                    acao,
                    descricao
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    'comanda_finalizada',
                    %s
                )
                """,
                (
                    empresa_id,
                    comanda_id,
                    recebido_por,
                    (
                        "Comanda recebida em "
                        f"{pagamento}. "
                        f"Total: R$ {total_liquido:.2f}."
                    ),
                ),
            )

            conn.commit()

            return {
                "comanda_id": comanda_id,
                "mesa_id": comanda["mesa_id"],
                "mesa_numero": comanda[
                    "mesa_numero"
                ],
                "venda_grupo": venda_grupo,
                "total_bruto": total_bruto,
                "desconto": desconto_total,
                "total": total_liquido,
                "pagamento": pagamento,
                "usuario_venda": usuario_venda,
                "cupom": cupom,
            }

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()
            
