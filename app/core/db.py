import os
import json
import time
import threading
from urllib.parse import urlsplit, urlunsplit
from contextlib import contextmanager
from typing import Any, Dict, Optional, List

import psycopg


class Database:
    """Простой синхронный слой работы с Postgres (psycopg3)."""

    _instance_lock = threading.Lock()
    _instance: "Database" = None

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/orderdb")
        self._ensure_database_exists()
        self._ensure_schema()

    @classmethod
    def get_instance(cls) -> "Database":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = Database()
        return cls._instance

    @contextmanager
    def connection(self):
        with self._connect_with_retry() as conn:
            yield conn

    def _ensure_schema(self):
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS admins (
                        user_id BIGINT PRIMARY KEY
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS suppliers (
                        name TEXT PRIMARY KEY,
                        config JSONB NOT NULL DEFAULT '{}'::jsonb
                    );
                    """
                )

    def users_add(self, user_id: int) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
        return True

    def users_is_registered(self, user_id: int) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM users WHERE user_id = %s", (user_id,))
                return cur.fetchone() is not None

    def users_get_all(self) -> List[int]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM users")
                return [row[0] for row in cur.fetchall()]

    def users_remove(self, user_id: int) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
        return True

    def suppliers_list(self) -> List[str]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM suppliers ORDER BY name")
                return [row[0] for row in cur.fetchall()]

    def suppliers_get_config(self, name: str) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT config FROM suppliers WHERE name = %s", (name,))
                row = cur.fetchone()
                return row[0] if row else None

    def suppliers_set_config(self, name: str, config: Dict[str, Any]) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO suppliers (name, config)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (name) DO UPDATE SET config = EXCLUDED.config
                    """,
                    (name, json.dumps(config)),
                )

    def suppliers_delete(self, name: str) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM suppliers WHERE name = %s", (name,))
                return cur.rowcount > 0

    def _with_dbname(self, dsn: str, dbname: str) -> str:
        parts = urlsplit(dsn)
        new_path = '/' + dbname
        return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))

    def _extract_dbname(self, dsn: str) -> str:
        parts = urlsplit(dsn)
        return parts.path.lstrip('/') or 'postgres'

    def _ensure_database_exists(self):
        target_db = self._extract_dbname(self.dsn)
        try:
            with psycopg.connect(self.dsn, autocommit=True) as _:
                return
        except Exception:
            pass
        admin_dsn = self._with_dbname(self.dsn, 'postgres')
        with self._connect_with_retry() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(f"CREATE DATABASE {psycopg.sql.Identifier(target_db).string}")

    @contextmanager
    def _connect_with_retry(self, timeout_seconds: int = 60):
        deadline = time.time() + timeout_seconds
        last_err = None
        while time.time() < deadline:
            try:
                with psycopg.connect(self.dsn, autocommit=True) as conn:
                    yield conn
                    return
            except Exception as e:
                last_err = e
                time.sleep(1.5)
        raise last_err


