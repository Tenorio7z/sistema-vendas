import os
import threading

import psycopg2
import psycopg2.extras
from psycopg2 import extensions
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv


load_dotenv()


_pool = None
_pool_lock = threading.Lock()


def _configuracao_banco():
    return {
        "host": os.getenv("DB_HOST"),
        "database": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": os.getenv("DB_PORT", "5432"),
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "8")),
        "application_name": os.getenv("DB_APPLICATION_NAME", "nexus-pdv"),
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
            minimo = max(1, int(os.getenv("DB_POOL_MIN", "1")))
            maximo = max(minimo, int(os.getenv("DB_POOL_MAX", "10")))

            _pool = ThreadedConnectionPool(
                minimo,
                maximo,
                **_configuracao_banco(),
            )

    return _pool


class ConexaoPooled:
    """Mantém conn.close() compatível, devolvendo a conexão ao pool."""

    def __init__(self, pool, conexao):
        self._pool = pool
        self._conexao = conexao
        self._devolvida = False

    def __getattr__(self, nome):
        return getattr(self._conexao, nome)

    def close(self):
        if self._devolvida:
            return

        descartar = bool(self._conexao.closed)

        if not descartar:
            try:
                if (
                    self._conexao.get_transaction_status()
                    != extensions.TRANSACTION_STATUS_IDLE
                ):
                    self._conexao.rollback()
            except psycopg2.Error:
                descartar = True

        self._pool.putconn(self._conexao, close=descartar)
        self._devolvida = True

    def __enter__(self):
        return self

    def __exit__(self, tipo, valor, traceback):
        if tipo is not None and not self._conexao.closed:
            self._conexao.rollback()

        self.close()
        return False


def conectar():
    pool = _obter_pool()
    ultimo_erro = None

    # Tenta obter uma conexão válida até 3 vezes.
    for tentativa in range(3):

        conexao = None

        try:
            conexao = pool.getconn()

            if conexao.closed:
                pool.putconn(
                    conexao,
                    close=True
                )

                conexao = None
                continue

            # Testa se a conexão ainda está viva.
            cursor_teste = conexao.cursor()

            try:
                cursor_teste.execute(
                    "SELECT 1"
                )

                cursor_teste.fetchone()

            finally:
                cursor_teste.close()

            # O SELECT de teste abre uma transação.
            # Voltamos para o estado limpo antes de entregar.
            conexao.rollback()

            return ConexaoPooled(
                pool,
                conexao
            )

        except (
            psycopg2.InterfaceError,
            psycopg2.OperationalError,
        ) as erro:
            ultimo_erro = erro

            if conexao is not None:
                try:
                    pool.putconn(
                        conexao,
                        close=True
                    )
                except Exception:
                    pass

            conexao = None

        except Exception as erro:
            ultimo_erro = erro

            if conexao is not None:
                try:
                    pool.putconn(
                        conexao,
                        close=True
                    )
                except Exception:
                    pass

            raise

    print(
        "Erro ao conectar no banco após 3 tentativas:",
        ultimo_erro
    )

    raise ultimo_erro

def criar_cursor(conn):
    return conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def fechar_pool():
    global _pool

    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None
