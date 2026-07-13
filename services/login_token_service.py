import hashlib
import secrets

from database import conectar, criar_cursor


class LoginTokenService:

    COOKIE_NAME = "nexus_login_token"
    DURACAO_DIAS = 30

    @staticmethod
    def _gerar_hash(token):
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    @classmethod
    def criar(
        cls,
        usuario_id,
        user_agent=None,
        endereco_ip=None,
    ):
        token = secrets.token_urlsafe(48)
        token_hash = cls._gerar_hash(token)

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            # Limita a quantidade de dispositivos lembrados.
            # Os tokens mais antigos serão removidos.
            cursor.execute(
                """
                DELETE FROM login_tokens
                WHERE usuario_id = %s
                  AND id NOT IN (
                      SELECT id
                      FROM login_tokens
                      WHERE usuario_id = %s
                        AND revogado_em IS NULL
                        AND expira_em > CURRENT_TIMESTAMP
                      ORDER BY criado_em DESC
                      LIMIT 9
                  )
                """,
                (
                    usuario_id,
                    usuario_id,
                )
            )

            cursor.execute(
                """
                INSERT INTO login_tokens (
                    usuario_id,
                    token_hash,
                    expira_em,
                    user_agent,
                    endereco_ip
                )
                VALUES (
                    %s,
                    %s,
                    CURRENT_TIMESTAMP
                        + (%s * INTERVAL '1 day'),
                    %s,
                    %s
                )
                """,
                (
                    usuario_id,
                    token_hash,
                    cls.DURACAO_DIAS,
                    str(user_agent or "")[:500],
                    str(endereco_ip or "")[:100],
                )
            )

            conn.commit()

            return token

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def autenticar(cls, token):
        if not token:
            return None

        token_hash = cls._gerar_hash(token)

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                SELECT
                    lt.id AS login_token_id,

                    u.id,
                    u.usuario,
                    u.nivel,
                    u.empresa_id,
                    u.status,

                    e.nome AS empresa_nome,
                    e.plano,
                    COALESCE(
                        e.emprestimos_ativo,
                        FALSE
                    ) AS emprestimos_ativo

                FROM login_tokens lt

                INNER JOIN usuarios u
                    ON u.id = lt.usuario_id

                LEFT JOIN empresa e
                    ON e.id = u.empresa_id

                WHERE lt.token_hash = %s
                  AND lt.revogado_em IS NULL
                  AND lt.expira_em > CURRENT_TIMESTAMP

                LIMIT 1
                """,
                (
                    token_hash,
                )
            )

            usuario = cursor.fetchone()

            if not usuario:
                return None

            if (
                usuario.get("nivel") != "master"
                and usuario.get("status") == "bloqueado"
            ):
                cursor.execute(
                    """
                    UPDATE login_tokens
                    SET revogado_em = CURRENT_TIMESTAMP
                    WHERE token_hash = %s
                    """,
                    (
                        token_hash,
                    )
                )

                conn.commit()
                return None

            cursor.execute(
                """
                UPDATE login_tokens
                SET ultimo_uso_em = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    usuario["login_token_id"],
                )
            )

            conn.commit()

            return usuario

        except Exception:
            conn.rollback()
            return None

        finally:
            cursor.close()
            conn.close()

    @classmethod
    def revogar(cls, token):
        if not token:
            return

        token_hash = cls._gerar_hash(token)

        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE login_tokens
                SET revogado_em = CURRENT_TIMESTAMP
                WHERE token_hash = %s
                  AND revogado_em IS NULL
                """,
                (
                    token_hash,
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def revogar_usuario(usuario_id):
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                UPDATE login_tokens
                SET revogado_em = CURRENT_TIMESTAMP
                WHERE usuario_id = %s
                  AND revogado_em IS NULL
                """,
                (
                    usuario_id,
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def limpar_expirados():
        conn = conectar()
        cursor = criar_cursor(conn)

        try:
            cursor.execute(
                """
                DELETE FROM login_tokens
                WHERE expira_em <= CURRENT_TIMESTAMP
                   OR (
                       revogado_em IS NOT NULL
                       AND revogado_em
                           < CURRENT_TIMESTAMP
                             - INTERVAL '7 days'
                   )
                """
            )

            conn.commit()

        except Exception:
            conn.rollback()

        finally:
            cursor.close()
            conn.close()