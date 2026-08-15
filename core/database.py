import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.conn: Optional[sqlite3.Connection] = None
        self.lock = asyncio.Lock()

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    async def setup(self) -> None:
        await self.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_stats (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                messages INTEGER NOT NULL DEFAULT 0,
                commands_used INTEGER NOT NULL DEFAULT 0,
                xp INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 0,
                voice_seconds INTEGER NOT NULL DEFAULT 0,
                stars_received INTEGER NOT NULL DEFAULT 0,
                joined_at TEXT,
                last_seen TEXT,
                last_xp_at TEXT,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS starboard_messages (
                guild_id INTEGER NOT NULL,
                source_message_id INTEGER NOT NULL,
                starboard_message_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                stars INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, source_message_id)
            );

            CREATE TABLE IF NOT EXISTS achievements (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                achievement_key TEXT NOT NULL,
                earned_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id, achievement_key)
            );

            CREATE TABLE IF NOT EXISTS temp_rooms (
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL PRIMARY KEY,
                owner_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS voice_sessions (
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                moderator_id INTEGER,
                target_id INTEGER,
                action TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS music_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    async def execute(self, query: str, params: Iterable = ()) -> sqlite3.Cursor:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        async with self.lock:
            cur = self.conn.execute(query, tuple(params))
            self.conn.commit()
            return cur

    async def executemany(self, query: str, params: Iterable[Iterable]) -> None:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        async with self.lock:
            self.conn.executemany(query, params)
            self.conn.commit()

    async def executescript(self, script: str) -> None:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        async with self.lock:
            self.conn.executescript(script)
            self.conn.commit()

    async def fetchone(self, query: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        async with self.lock:
            return self.conn.execute(query, tuple(params)).fetchone()

    async def fetchall(self, query: str, params: Iterable = ()) -> list[sqlite3.Row]:
        if self.conn is None:
            raise RuntimeError("Database is not connected")
        async with self.lock:
            return self.conn.execute(query, tuple(params)).fetchall()

    async def ensure_user(self, guild_id: int, user_id: int, joined_at: Optional[str] = None) -> None:
        await self.execute(
            """
            INSERT OR IGNORE INTO user_stats (guild_id, user_id, joined_at, last_seen)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, user_id, joined_at, utc_now_iso()),
        )

    async def increment_message(self, guild_id: int, user_id: int) -> None:
        await self.ensure_user(guild_id, user_id)
        await self.execute(
            """
            UPDATE user_stats
            SET messages = messages + 1, last_seen = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (utc_now_iso(), guild_id, user_id),
        )

    async def increment_command(self, guild_id: int, user_id: int) -> None:
        await self.ensure_user(guild_id, user_id)
        await self.execute(
            "UPDATE user_stats SET commands_used = commands_used + 1 WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id),
        )

    async def add_xp(self, guild_id: int, user_id: int, amount: int, level: int) -> None:
        await self.ensure_user(guild_id, user_id)
        await self.execute(
            """
            UPDATE user_stats
            SET xp = xp + ?, level = ?, last_xp_at = ?
            WHERE guild_id = ? AND user_id = ?
            """,
            (amount, level, utc_now_iso(), guild_id, user_id),
        )

