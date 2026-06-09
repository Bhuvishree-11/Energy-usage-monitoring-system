"""
app/core/database.py  –  MySQL connection pool + typed query helpers
"""
from mysql.connector import pooling, Error as MySQLError
from contextlib import contextmanager
from dotenv import load_dotenv
import logging, os

load_dotenv()

logger = logging.getLogger(__name__)

_pool: pooling.MySQLConnectionPool | None = None


def init_pool():
    global _pool
    _pool = pooling.MySQLConnectionPool(
        pool_name="smartwatt",
        pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
        pool_reset_session=True,
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "smartwatt"),
        charset="utf8mb4",
        autocommit=False,
        time_zone="+05:30",
    )
    logger.info("DB pool ready (size=%s)", os.getenv("DB_POOL_SIZE", 10))


def close_pool():
    global _pool
    _pool = None


@contextmanager
def get_conn():
    if not _pool:
        raise RuntimeError("DB pool not initialised")
    conn = _pool.get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    with get_conn() as conn:
        yield conn


# ── Query helpers ────────────────────────────────────────────────

def fetchall(conn, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def fetchone(conn, sql: str, params: tuple = ()) -> dict | None:
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params)
    row = cur.fetchone()
    cur.close()
    return row


def execute(conn, sql: str, params: tuple = ()) -> int:
    cur = conn.cursor()
    cur.execute(sql, params)
    lid = cur.lastrowid
    cur.close()
    return lid


def executemany(conn, sql: str, rows: list[tuple]) -> int:
    cur = conn.cursor()
    cur.executemany(sql, rows)
    n = cur.rowcount
    cur.close()
    return n