from database import conectar, criar_cursor


class FiliaisService:
    @staticmethod
    def garantir_matriz(empresa_id):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                INSERT INTO filiais (empresa_id, nome, codigo, matriz, ativa)
                SELECT %s, 'Matriz', 'MATRIZ', TRUE, TRUE
                WHERE NOT EXISTS (
                    SELECT 1 FROM filiais
                    WHERE empresa_id = %s AND matriz = TRUE
                )
                RETURNING id
                """,
                (empresa_id, empresa_id),
            )
            criada = cursor.fetchone()
            if criada:
                filial_id = criada["id"]
            else:
                cursor.execute(
                    "SELECT id FROM filiais WHERE empresa_id = %s AND matriz = TRUE LIMIT 1",
                    (empresa_id,),
                )
                filial_id = cursor.fetchone()["id"]
            conn.commit()
            return int(filial_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def listar(empresa_id, somente_ativas=True):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                SELECT f.id, f.nome, f.codigo, f.matriz, f.ativa,
                       COALESCE((SELECT COUNT(*) FROM produto_filial pf
                                 WHERE pf.filial_id = f.id AND pf.ativo = TRUE), 0) AS total_produtos,
                       COALESCE((SELECT SUM(pf.estoque) FROM produto_filial pf
                                 WHERE pf.filial_id = f.id AND pf.ativo = TRUE), 0) AS total_estoque,
                       COALESCE((SELECT COUNT(*) FROM usuarios u
                                 WHERE u.filial_id = f.id AND u.empresa_id = f.empresa_id
                                   AND u.status = 'ativo'), 0) AS total_usuarios
                FROM filiais f
                WHERE f.empresa_id = %s
                  AND (%s = FALSE OR f.ativa = TRUE)
                ORDER BY f.matriz DESC, f.nome
                """,
                (empresa_id, somente_ativas),
            )
            return cursor.fetchall() or []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obter(empresa_id, filial_id):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                "SELECT * FROM filiais WHERE id = %s AND empresa_id = %s LIMIT 1",
                (filial_id, empresa_id),
            )
            return cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def criar(empresa_id, nome, codigo=None, copiar_matriz=True, estoque_zerado=True):
        nome = str(nome or "").strip()
        codigo = str(codigo or "").strip() or None
        if not nome:
            raise ValueError("Informe o nome da filial.")
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                INSERT INTO filiais (empresa_id, nome, codigo, matriz, ativa)
                VALUES (%s, %s, %s, FALSE, TRUE)
                RETURNING id
                """,
                (empresa_id, nome, codigo),
            )
            filial_id = int(cursor.fetchone()["id"])
            if copiar_matriz:
                cursor.execute(
                    """
                    INSERT INTO produto_filial (produto_id, filial_id, estoque, ativo)
                    SELECT p.id, %s,
                           CASE WHEN %s THEN 0 ELSE COALESCE(pf.estoque, 0) END,
                           TRUE
                    FROM produtos p
                    JOIN filiais matriz
                      ON matriz.empresa_id = p.empresa_id AND matriz.matriz = TRUE
                    LEFT JOIN produto_filial pf
                      ON pf.produto_id = p.id AND pf.filial_id = matriz.id
                    WHERE p.empresa_id = %s
                    ON CONFLICT DO NOTHING
                    """,
                    (filial_id, estoque_zerado, empresa_id),
                )
            conn.commit()
            return filial_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def alterar_status(empresa_id, filial_id, ativa):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                UPDATE filiais SET ativa = %s, atualizada_em = CURRENT_TIMESTAMP
                WHERE id = %s AND empresa_id = %s AND matriz = FALSE
                """,
                (bool(ativa), filial_id, empresa_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("A matriz não pode ser desativada ou a filial não existe.")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def copiar_catalogo(empresa_id, filial_id, estoque_zerado=True):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                "SELECT id FROM filiais WHERE id = %s AND empresa_id = %s AND ativa = TRUE",
                (filial_id, empresa_id),
            )
            if not cursor.fetchone():
                raise ValueError("Filial inválida.")
            cursor.execute(
                """
                INSERT INTO produto_filial (produto_id, filial_id, estoque, ativo)
                SELECT p.id, %s,
                       CASE WHEN %s THEN 0 ELSE COALESCE(origem.estoque, 0) END,
                       TRUE
                FROM produtos p
                JOIN filiais matriz ON matriz.empresa_id = p.empresa_id AND matriz.matriz = TRUE
                LEFT JOIN produto_filial origem
                  ON origem.produto_id = p.id AND origem.filial_id = matriz.id
                WHERE p.empresa_id = %s
                ON CONFLICT (produto_id, filial_id)
                DO UPDATE SET ativo = TRUE, atualizado_em = CURRENT_TIMESTAMP
                """,
                (filial_id, estoque_zerado, empresa_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def filial_do_usuario(empresa_id, usuario_id):
        conn = conectar()
        cursor = criar_cursor(conn)
        try:
            cursor.execute(
                """
                SELECT f.id, f.nome, f.matriz
                FROM usuarios u
                JOIN filiais f ON f.id = u.filial_id AND f.empresa_id = u.empresa_id
                WHERE u.id = %s AND u.empresa_id = %s AND f.ativa = TRUE
                LIMIT 1
                """,
                (usuario_id, empresa_id),
            )
            filial = cursor.fetchone()
            if filial:
                return filial
        finally:
            cursor.close()
            conn.close()
        matriz_id = FiliaisService.garantir_matriz(empresa_id)
        return FiliaisService.obter(empresa_id, matriz_id)
