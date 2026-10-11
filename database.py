import atexit
from contextlib import contextmanager
import os
from threading import Lock

from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool

_pool = None
_pool_pid = None
_pool_lock = Lock()


def get_pool():
    global _pool, _pool_pid
    with _pool_lock:
        # Bağlantı import sırasında açılmaz; her Celery alt süreci kendi havuzunu kurar.
        if _pool is None or _pool_pid != os.getpid():
            _pool = ConnectionPool(
                kwargs={
                    "host": os.getenv("DB_HOST", "127.0.0.1"),
                    "port": os.getenv("DB_PORT", "5432"),
                    "dbname": os.environ["POSTGRES_DB"],
                    "user": os.environ["POSTGRES_USER"],
                    "password": os.environ["POSTGRES_PASSWORD"],
                    "connect_timeout": 5,
                    "options": "-c statement_timeout=10000 -c lock_timeout=5000",
                },
                min_size=1,
                max_size=int(os.getenv("DB_POOL_MAX", "8")),
                timeout=5,
                max_waiting=32,
                check=ConnectionPool.check_connection,
                open=True,
            )
            _pool_pid = os.getpid()
        return _pool


@contextmanager
def get_connection():
    with get_pool().connection() as conn:
        # Önceki kullanıcı dict_row seçmiş olabilir; yeni işlem temiz ayarla başlar.
        conn.row_factory = tuple_row
        yield conn
    # Başarıda commit, hatada rollback; bağlantı kapatılmaz, havuza geri döner.


def close_pool():
    global _pool, _pool_pid
    if _pool is not None and _pool_pid == os.getpid():
        _pool.close()
        _pool = None
        _pool_pid = None


atexit.register(close_pool)
