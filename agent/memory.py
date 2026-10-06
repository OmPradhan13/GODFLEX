import json
import os
import sqlite3
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, List, Optional


ENABLE_PERSISTENCE = os.getenv("ENABLE_PERSISTENCE", "true").strip().lower() in {
    "1", "true", "yes", "on"
}
DEFAULT_DB_PATH = os.getenv("GODFLEX_DB_PATH", "data/godflex.db")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GODFLEXMemory:
    """
    Durable SQLite-backed state store for GODFLEX.

    It stores:
      - memories
      - chat history
      - plans
      - task state
      - API quota/rate-limit state
      - Telegram approval state

    SQLite is deliberately used instead of JSON because multiple processes
    (for example GODFLEX + the Telegram bot) need safe shared state.
    """

    def __init__(self, storage_path: str = DEFAULT_DB_PATH):
        self.storage_path = storage_path
        self.lock = RLock()

        if ENABLE_PERSISTENCE:
            directory = os.path.dirname(os.path.abspath(self.storage_path))
            os.makedirs(directory, exist_ok=True)
            self._initialize_db()

    def _connect(self):
        conn = sqlite3.connect(
            self.storage_path,
            timeout=30,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _initialize_db(self):
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    goal TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    requires_approval INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS api_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    day TEXT NOT NULL,
                    call_count INTEGER NOT NULL DEFAULT 0,
                    last_call_at REAL
                );

                CREATE TABLE IF NOT EXISTS approvals (
                    task_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    decided_at TEXT,
                    decided_by TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_memories_category
                    ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_chat_history_created
                    ON chat_history(created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_updated
                    ON tasks(updated_at);
                """
            )

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def remember(
        self,
        category: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        memory = {
            "category": category,
            "content": content,
            "metadata": metadata or {},
            "created_at": utc_now(),
        }

        if not ENABLE_PERSISTENCE:
            memory["id"] = 0
            return memory

        with self.lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO memories
                    (category, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    memory["category"],
                    memory["content"],
                    json.dumps(memory["metadata"], ensure_ascii=False),
                    memory["created_at"],
                ),
            )
            memory["id"] = cursor.lastrowid

        return memory

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not ENABLE_PERSISTENCE:
            return []

        pattern = f"%{query.lower()}%"
        params: list[Any] = [pattern, pattern]
        category_sql = ""

        if category:
            category_sql = "AND category = ?"
            params.append(category)

        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, category, content, metadata_json, created_at
                FROM memories
                WHERE (
                    lower(content) LIKE ?
                    OR lower(metadata_json) LIKE ?
                )
                {category_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._memory_row(row) for row in rows]

    def recent(
        self,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not ENABLE_PERSISTENCE:
            return []

        params: list[Any] = [limit]
        category_sql = ""

        if category:
            category_sql = "WHERE category = ?"
            params.insert(0, category)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, category, content, metadata_json, created_at
                FROM memories
                {category_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [self._memory_row(row) for row in reversed(rows)]

    def delete(self, memory_id: int) -> bool:
        if not ENABLE_PERSISTENCE:
            return False

        with self.lock, self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _memory_row(row: sqlite3.Row) -> Dict[str, Any]:
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, json.JSONDecodeError):
            metadata = {}

        return {
            "id": row["id"],
            "category": row["category"],
            "content": row["content"],
            "metadata": metadata,
            "created_at": row["created_at"],
        }

    # ------------------------------------------------------------------
    # Chat history
    # ------------------------------------------------------------------

    def append_chat(self, role: str, content: str) -> Dict[str, Any]:
        item = {
            "role": role,
            "content": content,
            "created_at": utc_now(),
        }

        if not ENABLE_PERSISTENCE:
            return item

        with self.lock, self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_history(role, content, created_at)
                VALUES (?, ?, ?)
                """,
                (role, content, item["created_at"]),
            )
            item["id"] = cursor.lastrowid

        return item

    def recent_chat(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not ENABLE_PERSISTENCE:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at
                FROM chat_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in reversed(rows)]

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    def save_plan(self, goal: str, plan: Dict[str, Any]) -> None:
        if not ENABLE_PERSISTENCE:
            return

        now = utc_now()
        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO plans(goal, plan_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    goal,
                    json.dumps(plan, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def latest_plan(self) -> Optional[Dict[str, Any]]:
        if not ENABLE_PERSISTENCE:
            return None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT plan_json
                FROM plans
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        if not row:
            return None

        try:
            return json.loads(row["plan_json"])
        except json.JSONDecodeError:
            return None

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def save_task(self, task) -> None:
        if not ENABLE_PERSISTENCE:
            return

        result_json = None
        if task.result is not None:
            try:
                result_json = json.dumps(task.result, ensure_ascii=False)
            except (TypeError, ValueError):
                result_json = json.dumps(str(task.result))

        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, name, description, requires_approval,
                    status, result_json, error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    requires_approval=excluded.requires_approval,
                    status=excluded.status,
                    result_json=excluded.result_json,
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    task.task_id,
                    task.name,
                    task.description,
                    int(task.requires_approval),
                    task.status.value if hasattr(task.status, "value") else str(task.status),
                    result_json,
                    task.error,
                    task.created_at,
                    task.updated_at,
                ),
            )

    def load_tasks(self) -> List[Dict[str, Any]]:
        if not ENABLE_PERSISTENCE:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT task_id, name, description, requires_approval,
                       status, result_json, error, created_at, updated_at
                FROM tasks
                ORDER BY created_at ASC
                """
            ).fetchall()

        tasks = []
        for row in rows:
            result = None
            if row["result_json"]:
                try:
                    result = json.loads(row["result_json"])
                except json.JSONDecodeError:
                    result = row["result_json"]

            tasks.append(
                {
                    "task_id": row["task_id"],
                    "name": row["name"],
                    "description": row["description"],
                    "requires_approval": bool(row["requires_approval"]),
                    "status": row["status"],
                    "result": result,
                    "error": row["error"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )

        return tasks

    # ------------------------------------------------------------------
    # Persistent API quota + rate limiting
    # ------------------------------------------------------------------

    def reserve_api_call(
        self,
        max_daily_calls: int,
        min_interval_seconds: float,
    ) -> tuple[bool, float, int]:
        """
        Atomically reserve one API request.

        Returns:
            (allowed, wait_seconds, current_daily_count)

        The caller must sleep for wait_seconds and retry when allowed=False
        and wait_seconds > 0. Quota exhaustion returns allowed=False,
        wait_seconds=0.
        """
        if not ENABLE_PERSISTENCE:
            return True, 0.0, 0

        today = datetime.now(timezone.utc).date().isoformat()

        with self.lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute(
                "SELECT day, call_count, last_call_at FROM api_state WHERE id = 1"
            ).fetchone()

            if row is None or row["day"] != today:
                count = 0
                last_call_at = None
                conn.execute(
                    """
                    INSERT INTO api_state(id, day, call_count, last_call_at)
                    VALUES (1, ?, 0, NULL)
                    ON CONFLICT(id) DO UPDATE SET
                        day=excluded.day,
                        call_count=excluded.call_count,
                        last_call_at=excluded.last_call_at
                    """,
                    (today,),
                )
            else:
                count = int(row["call_count"])
                last_call_at = row["last_call_at"]

            if count >= max_daily_calls:
                conn.commit()
                return False, 0.0, count

            now = datetime.now(timezone.utc).timestamp()

            if last_call_at is not None:
                wait = min_interval_seconds - (now - float(last_call_at))
                if wait > 0:
                    conn.commit()
                    return False, wait, count

            count += 1
            conn.execute(
                """
                UPDATE api_state
                SET day = ?, call_count = ?, last_call_at = ?
                WHERE id = 1
                """,
                (today, count, now),
            )
            conn.commit()

            return True, 0.0, count

    def api_usage(self) -> Dict[str, Any]:
        if not ENABLE_PERSISTENCE:
            return {"day": None, "call_count": 0, "last_call_at": None}

        with self._connect() as conn:
            row = conn.execute(
                "SELECT day, call_count, last_call_at FROM api_state WHERE id = 1"
            ).fetchone()

        if not row:
            return {"day": None, "call_count": 0, "last_call_at": None}

        return dict(row)

    # ------------------------------------------------------------------
    # Telegram approvals
    # ------------------------------------------------------------------

    def create_approval(self, task_id: str) -> None:
        if not ENABLE_PERSISTENCE:
            return

        with self.lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO approvals(task_id, status, requested_at)
                VALUES (?, 'pending', ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status='pending',
                    requested_at=excluded.requested_at,
                    decided_at=NULL,
                    decided_by=NULL
                """,
                (task_id, utc_now()),
            )

    def set_approval(
        self,
        task_id: str,
        status: str,
        decided_by: Optional[str] = None,
    ) -> bool:
        if not ENABLE_PERSISTENCE:
            return False

        if status not in {"approved", "rejected", "expired"}:
            raise ValueError(f"Invalid approval status: {status}")

        with self.lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE approvals
                SET status = ?, decided_at = ?, decided_by = ?
                WHERE task_id = ? AND status = 'pending'
                """,
                (status, utc_now(), decided_by, task_id),
            )
            return cursor.rowcount > 0

    def get_approval(self, task_id: str) -> Optional[Dict[str, Any]]:
        if not ENABLE_PERSISTENCE:
            return None

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT task_id, status, requested_at, decided_at, decided_by
                FROM approvals
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

        return dict(row) if row else None
