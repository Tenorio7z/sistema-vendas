import os
import threading
import time

import psycopg2
import psycopg2.extras

from dotenv import load_dotenv
from psycopg2 import extensions
from psycopg2.pool import ThreadedConnectionPool


load_dotenv()


_pool = None
_pool_lock = threading.Lock()

_validacoes = {}
_validacoes_lock = threading.Lock()


def _configuracao_banco():
    return {
        "host": os.getenv("DB_HOST"),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": os.getenv("DB_PORT", "5432"),
        "connect_timeout": int(
            os.getenv(
                "DB_CONNECT_TIMEOUT",
                "8",
            )
        ),
        "application_name": os.getenv(
            "DB_APPLICATION_NAME",
            "nexus-pdv",
        ),
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }


def _obter_pool():
    global _pool

    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is None:
            minimo = max(
                1,
                int(os.getenv("DB_POOL_MIN", "1")),
            )

            maximo = max(
                minimo,
                int(os.getenv("DB_POOL_MAX", "10")),
            )

            _pool = ThreadedConnectionPool(
                minimo,
                maximo,
                **_configuracao_banco(),
            )

    return _pool


def _remover_validacao(conexao):
    if conexao is None:
        return

    with _validacoes_lock:
        _validacoes.pop(
            id(conexao),
            None,
        )


def _precisa_validar(conexao):
    intervalo = max(
        15,
        int(
            os.getenv(
                "DB_VALIDATION_INTERVAL",
                "120",
            )
        ),
    )

    agora = time.monotonic()
    chave = id(conexao)

    with _validacoes_lock:
        ultima = _validacoes.get(
            chave,
            0,
        )

        if agora - ultima < intervalo:
            return False

        _validacoes[chave] = agora

    return True


def _validar_conexao(conexao):
    if not _precisa_validar(conexao):
        return

    cursor = conexao.cursor()

    try:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    finally:
        cursor.close()

    conexao.rollback()


class ConexaoPooled:
    """
    Mantém conn.close() compatível com o restante
    do sistema, devolvendo a conexão ao pool.
    """

    def __init__(self, pool, conexao):
        self._pool = pool
        self._conexao = conexao
        self._devolvida = False

    def __getattr__(self, nome):
        return getattr(
            self._conexao,
            nome,
        )

    def close(self):
        if self._devolvida:
            return

        descartar = bool(
            self._conexao.closed
        )

        if not descartar:
            try:
                status = (
                    self._conexao
                    .get_transaction_status()
                )

                if (
                    status
                    != extensions.TRANSACTION_STATUS_IDLE
                ):
                    self._conexao.rollback()

            except psycopg2.Error:
                descartar = True

        if descartar:
            _remover_validacao(
                self._conexao
            )

        self._pool.putconn(
            self._conexao,
            close=descartar,
        )

        self._devolvida = True

    def __enter__(self):
        return self

    def __exit__(
        self,
        tipo,
        valor,
        traceback,
    ):
        if (
            tipo is not None
            and not self._conexao.closed
        ):
            self._conexao.rollback()

        self.close()

        return False


def conectar():
    pool = _obter_pool()
    ultimo_erro = None

    for _ in range(3):
        conexao = None

        try:
            conexao = pool.getconn()

            if conexao.closed:
                _remover_validacao(
                    conexao
                )

                pool.putconn(
                    conexao,
                    close=True,
                )

                continue

            _validar_conexao(
                conexao
            )

            return ConexaoPooled(
                pool,
                conexao,
            )

        except (
            psycopg2.InterfaceError,
            psycopg2.OperationalError,
        ) as erro:
            ultimo_erro = erro

            if conexao is not None:
                _remover_validacao(
                    conexao
                )

                try:
                    pool.putconn(
                        conexao,
                        close=True,
                    )
                except Exception:
                    pass

        except Exception:
            if conexao is not None:
                _remover_validacao(
                    conexao
                )

                try:
                    pool.putconn(
                        conexao,
                        close=True,
                    )
                except Exception:
                    pass

            raise

    raise ultimo_erro or psycopg2.OperationalError(
        "Não foi possível conectar ao banco de dados."
    )


def criar_cursor(conn):
    return conn.cursor(
        cursor_factory=(
            psycopg2.extras.RealDictCursor
        )
    )


def fechar_pool():
    global _pool

    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None

    with _validacoes_lock:
        _validacoes.clear()