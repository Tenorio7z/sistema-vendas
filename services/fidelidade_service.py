from database import criar_cursor


def registrar_checkins_da_venda(cursor, empresa_id, cliente_id, venda_grupo):
    """Registra um check-in, dentro da transação da venda confirmada."""
    if not empresa_id or not cliente_id or not venda_grupo:
        return False

    cursor.execute(
        """
        SELECT id, checkins_meta
        FROM fidelidade_campanhas
        WHERE empresa_id = %s
          AND ativa = TRUE
          AND criado_em + (prazo_dias * INTERVAL '1 day') > CURRENT_TIMESTAMP
        ORDER BY criado_em DESC, id DESC
        LIMIT 1
        FOR UPDATE
        """,
        (empresa_id,),
    )
    campanha = cursor.fetchone()
    if not campanha:
        return False

    campanha_id = campanha['id']
    meta = int(campanha['checkins_meta'])

    cursor.execute(
        """
        INSERT INTO fidelidade_checkins (
            empresa_id, campanha_id, cliente_id, venda_grupo
        )
        SELECT %s, %s, c.id, %s
        FROM clientes c
        WHERE c.id = %s
          AND c.empresa_id = %s
          AND c.ativo = TRUE
        ON CONFLICT (campanha_id, venda_grupo) DO NOTHING
        RETURNING id
        """,
        (empresa_id, campanha_id, str(venda_grupo), cliente_id, empresa_id),
    )
    checkin = cursor.fetchone()
    if not checkin:
        return False

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM fidelidade_checkins
        WHERE empresa_id = %s
          AND campanha_id = %s
          AND cliente_id = %s
          AND valido = TRUE
        """,
        (empresa_id, campanha_id, cliente_id),
    )
    total = int(cursor.fetchone()['total'])

    if total % meta == 0:
        ciclo = total // meta
        cursor.execute(
            """
            INSERT INTO fidelidade_recompensas (
                empresa_id, campanha_id, cliente_id, ciclo, checkin_id, status
            ) VALUES (%s, %s, %s, %s, %s, 'disponivel')
            ON CONFLICT (campanha_id, cliente_id, ciclo)
            DO UPDATE SET
                checkin_id = EXCLUDED.checkin_id,
                status = 'disponivel',
                criada_em = CURRENT_TIMESTAMP,
                resgatada_em = NULL
            WHERE fidelidade_recompensas.status = 'revogada'
            """,
            (empresa_id, campanha_id, cliente_id, ciclo, checkin['id']),
        )

    return True


def invalidar_checkin_se_venda_cancelada(cursor, empresa_id, venda_grupo):
    """Invalida o check-in quando todos os itens daquele grupo foram cancelados."""
    if not empresa_id or not venda_grupo:
        return

    cursor.execute(
        """
        SELECT COUNT(*) AS ativas
        FROM vendas
        WHERE empresa_id = %s
          AND venda_grupo = %s
          AND COALESCE(cancelada, 0) = 0
        """,
        (empresa_id, str(venda_grupo)),
    )
    if int(cursor.fetchone()['ativas']) > 0:
        return

    cursor.execute(
        """
        UPDATE fidelidade_checkins
        SET valido = FALSE, invalidado_em = CURRENT_TIMESTAMP
        WHERE empresa_id = %s
          AND venda_grupo = %s
          AND valido = TRUE
        RETURNING campanha_id, cliente_id
        """,
        (empresa_id, str(venda_grupo)),
    )
    invalidado = cursor.fetchone()
    if not invalidado:
        return

    campanha_id = invalidado['campanha_id']
    cliente_id = invalidado['cliente_id']

    cursor.execute(
        """
        SELECT checkins_meta FROM fidelidade_campanhas
        WHERE id = %s AND empresa_id = %s
        """,
        (campanha_id, empresa_id),
    )
    campanha = cursor.fetchone()
    if not campanha:
        return

    meta = int(campanha['checkins_meta'])
    cursor.execute(
        """
        SELECT COUNT(*) AS total FROM fidelidade_checkins
        WHERE empresa_id = %s AND campanha_id = %s
          AND cliente_id = %s AND valido = TRUE
        """,
        (empresa_id, campanha_id, cliente_id),
    )
    ciclos_validos = int(cursor.fetchone()['total']) // meta

    cursor.execute(
        """
        UPDATE fidelidade_recompensas
        SET status = CASE
                WHEN status = 'disponivel' THEN 'revogada'
                WHEN status = 'resgatada' THEN 'revisar_cancelamento'
                ELSE status
            END
        WHERE empresa_id = %s AND campanha_id = %s AND cliente_id = %s
          AND ciclo > %s
          AND status IN ('disponivel', 'resgatada')
        """,
        (empresa_id, campanha_id, cliente_id, ciclos_validos),
    )


def resgatar_recompensa(cursor, empresa_id, recompensa_id):
    cursor.execute(
        """
        SELECT r.id, r.campanha_id, r.cliente_id, r.ciclo,
               c.checkins_meta, c.premio
        FROM fidelidade_recompensas r
        JOIN fidelidade_campanhas c ON c.id = r.campanha_id
        WHERE r.id = %s AND r.empresa_id = %s
          AND r.status = 'disponivel'
        FOR UPDATE OF r
        """,
        (recompensa_id, empresa_id),
    )
    recompensa = cursor.fetchone()
    if not recompensa:
        return False

    cursor.execute(
        """
        SELECT COUNT(*) AS total FROM fidelidade_checkins
        WHERE empresa_id = %s AND campanha_id = %s
          AND cliente_id = %s AND valido = TRUE
        """,
        (empresa_id, recompensa['campanha_id'], recompensa['cliente_id']),
    )
    total = int(cursor.fetchone()['total'])
    if total < int(recompensa['ciclo']) * int(recompensa['checkins_meta']):
        return False

    cursor.execute(
        """
        UPDATE fidelidade_recompensas
        SET status = 'resgatada', resgatada_em = CURRENT_TIMESTAMP
        WHERE id = %s AND empresa_id = %s AND status = 'disponivel'
        """,
        (recompensa_id, empresa_id),
    )
    return cursor.rowcount == 1
