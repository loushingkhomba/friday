"""Single-file SQLite persistence foundation for Friday-managed household data.

The application must pass a confirmed profile id for private reads/writes. An absent
profile can see shared records only. Voice matching is a personalization signal,
not cryptographic authentication; this API prevents accidental cross-profile recall.
"""

from __future__ import annotations

import json
import math
import os
import sqlite3
import struct
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


class FridayStore:
    """SQLite source-of-truth store; vectors and records live in the same DB file."""

    def __init__(self, path: str | os.PathLike[str] | None = None):
        if path is None:
            path = Path(__file__).resolve().parent / 'data' / 'friday.sqlite3'
        self.path = str(Path(path).expanduser().resolve())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        connection.execute('PRAGMA busy_timeout = 10000')
        connection.execute('PRAGMA journal_mode = WAL')
        connection.execute('PRAGMA synchronous = FULL')
        return connection

    def _initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS profiles (
            profile_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS voice_profiles (
            profile_id TEXT PRIMARY KEY REFERENCES profiles(profile_id) ON DELETE CASCADE,
            centroid BLOB,
            examples_json TEXT NOT NULL DEFAULT '[]',
            details_json TEXT NOT NULL DEFAULT '{}',
            enrollment_version INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS preferences (
            preference_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE CASCADE,
            preference_key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((visibility = 'shared' AND owner_profile_id IS NULL) OR
                   (visibility = 'private' AND owner_profile_id IS NOT NULL))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS preferences_shared_key
            ON preferences(preference_key) WHERE visibility = 'shared';
        CREATE UNIQUE INDEX IF NOT EXISTS preferences_private_key
            ON preferences(owner_profile_id, preference_key) WHERE visibility = 'private';
        CREATE TABLE IF NOT EXISTS memories (
            memory_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            embedding BLOB,
            embedding_dimensions INTEGER,
            source TEXT NOT NULL DEFAULT 'user',
            consent TEXT NOT NULL DEFAULT 'explicit',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((visibility = 'shared' AND owner_profile_id IS NULL) OR
                   (visibility = 'private' AND owner_profile_id IS NOT NULL)),
            CHECK ((embedding IS NULL AND embedding_dimensions IS NULL) OR
                   (embedding IS NOT NULL AND embedding_dimensions > 0))
        );
        CREATE INDEX IF NOT EXISTS memories_scope_kind_date
            ON memories(visibility, owner_profile_id, kind, created_at);
        CREATE TABLE IF NOT EXISTS conversation_turns (
            turn_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            visibility TEXT NOT NULL CHECK (visibility IN ('private', 'shared', 'unassigned')),
            speaker_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE SET NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((visibility = 'private' AND speaker_profile_id IS NOT NULL) OR
                   (visibility IN ('shared', 'unassigned') AND speaker_profile_id IS NULL))
        );
        CREATE INDEX IF NOT EXISTS turns_scope_date
            ON conversation_turns(visibility, speaker_profile_id, created_at);
        CREATE TABLE IF NOT EXISTS reminders (
            reminder_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE CASCADE,
            task TEXT NOT NULL,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((visibility = 'shared' AND owner_profile_id IS NULL) OR
                   (visibility = 'private' AND owner_profile_id IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS reminders_due_status ON reminders(status, due_at);
        CREATE TABLE IF NOT EXISTS learned_intents (
            lesson_id TEXT PRIMARY KEY,
            owner_profile_id TEXT NOT NULL REFERENCES profiles(profile_id) ON DELETE CASCADE,
            phrase TEXT NOT NULL,
            intent TEXT NOT NULL,
            approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS skills (
            skill_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            body TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'approved', 'disabled')),
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((visibility = 'shared' AND owner_profile_id IS NULL) OR
                   (visibility = 'private' AND owner_profile_id IS NOT NULL)),
            UNIQUE(visibility, owner_profile_id, name, version)
        );
        CREATE TABLE IF NOT EXISTS agent_definitions (
            agent_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared', 'private')),
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            specification_json TEXT NOT NULL,
            tool_grants_json TEXT NOT NULL DEFAULT '[]',
            state TEXT NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'approved', 'disabled')),
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK ((visibility = 'shared' AND owner_profile_id IS NULL) OR
                   (visibility = 'private' AND owner_profile_id IS NOT NULL))
        );
        CREATE TABLE IF NOT EXISTS agent_jobs (
            job_id TEXT PRIMARY KEY,
            agent_id TEXT REFERENCES agent_definitions(agent_id) ON DELETE SET NULL,
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE SET NULL,
            goal TEXT NOT NULL,
            state TEXT NOT NULL,
            checkpoint_json TEXT NOT NULL DEFAULT '{}',
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS code_change_artifacts (
            change_id TEXT PRIMARY KEY,
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE SET NULL,
            target_name TEXT NOT NULL,
            patch BLOB NOT NULL,
            source_hash TEXT NOT NULL,
            proposal_hash TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('draft', 'approved', 'applied', 'rejected', 'rolled_back')),
            backup BLOB,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            owner_profile_id TEXT REFERENCES profiles(profile_id) ON DELETE SET NULL,
            visibility TEXT NOT NULL DEFAULT 'unassigned' CHECK (visibility IN ('private', 'shared', 'unassigned')),
            event_type TEXT NOT NULL,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
        with self._connect() as connection:
            connection.executescript(schema)
            current = connection.execute('PRAGMA user_version').fetchone()[0]
            if current > SCHEMA_VERSION:
                raise RuntimeError(f'Database schema {current} is newer than this Friday build.')
            if current < SCHEMA_VERSION:
                connection.execute(
                    'INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)',
                    (SCHEMA_VERSION,),
                )
                connection.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'))

    @staticmethod
    def _pack_vector(vector: list[float] | tuple[float, ...] | None):
        if vector is None:
            return None, None
        values = tuple(float(value) for value in vector)
        if not values or not all(math.isfinite(value) for value in values):
            raise ValueError('Embedding must contain finite numeric values.')
        return struct.pack(f'<{len(values)}f', *values), len(values)

    def register_profile(self, profile_id: str, display_name: str) -> None:
        profile_id = str(profile_id).strip()
        display_name = str(display_name).strip()
        if not profile_id or not display_name:
            raise ValueError('A profile id and display name are required.')
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO profiles(profile_id, display_name) VALUES (?, ?) "
                "ON CONFLICT(profile_id) DO UPDATE SET display_name=excluded.display_name, "
                "updated_at=CURRENT_TIMESTAMP",
                (profile_id, display_name),
            )

    def save_memory(self, content: str, kind: str, *, profile_id: str | None = None,
                    shared: bool = False, metadata: dict[str, Any] | None = None,
                    embedding: list[float] | tuple[float, ...] | None = None,
                    source: str = 'user', consent: str = 'explicit',
                    memory_id: str | None = None) -> str:
        content = str(content).strip()
        kind = str(kind).strip()
        if not content or not kind:
            raise ValueError('Memory content and kind are required.')
        if shared and profile_id:
            raise ValueError('Shared memory cannot have a private owner.')
        if not shared and not profile_id:
            raise ValueError('Private memory requires a confirmed profile id.')
        vector_blob, dimensions = self._pack_vector(embedding)
        item_id = memory_id or uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO memories(memory_id, visibility, owner_profile_id, kind, content, "
                "metadata_json, embedding, embedding_dimensions, source, consent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (item_id, 'shared' if shared else 'private', None if shared else profile_id,
                 kind, content, self._json(metadata or {}), vector_blob, dimensions,
                 str(source), str(consent)),
            )
        return item_id

    def list_memories(self, profile_id: str | None = None, *, kinds: tuple[str, ...] | None = None,
                      limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError('Limit must be between 1 and 1000.')
        clauses = ["visibility = 'shared'"]
        parameters: list[Any] = []
        if profile_id:
            clauses.append("(visibility = 'private' AND owner_profile_id = ?)")
            parameters.append(profile_id)
        sql = 'SELECT * FROM memories WHERE (' + ' OR '.join(clauses) + ')'
        if kinds:
            safe_kinds = tuple(str(kind) for kind in kinds)
            placeholders = ','.join('?' for _ in safe_kinds)
            sql += f' AND kind IN ({placeholders})'
            parameters.extend(safe_kinds)
        sql += ' ORDER BY created_at DESC LIMIT ?'
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [dict(row) for row in rows]

    def search_memories(self, query_embedding: list[float] | tuple[float, ...],
                        profile_id: str | None = None, *, kinds: tuple[str, ...] | None = None,
                        limit: int = 5) -> list[dict[str, Any]]:
        query = tuple(float(value) for value in query_embedding)
        if not query or not all(math.isfinite(value) for value in query):
            raise ValueError('Query embedding must contain finite numeric values.')
        q_norm = math.sqrt(sum(value * value for value in query))
        if q_norm == 0:
            return []
        candidates = self.list_memories(profile_id, kinds=kinds, limit=1000)
        scored = []
        for record in candidates:
            blob = record.get('embedding')
            dims = record.get('embedding_dimensions')
            if not blob or dims != len(query):
                continue
            vector = struct.unpack(f'<{dims}f', blob)
            norm = math.sqrt(sum(value * value for value in vector))
            if not norm:
                continue
            score = sum(a * b for a, b in zip(query, vector)) / (q_norm * norm)
            record['metadata'] = json.loads(record.pop('metadata_json') or '{}')
            record['score'] = score
            scored.append(record)
        return sorted(scored, key=lambda row: row['score'], reverse=True)[:max(0, limit)]

    def save_turn(self, role: str, content: str, *, conversation_id: str,
                  profile_id: str | None = None, shared: bool = False,
                  metadata: dict[str, Any] | None = None, turn_id: str | None = None) -> str:
        if role not in {'user', 'assistant', 'system'}:
            raise ValueError('Unsupported conversation role.')
        if shared and profile_id:
            raise ValueError('Shared turns cannot have a private owner.')
        visibility = 'shared' if shared else ('private' if profile_id else 'unassigned')
        item_id = turn_id or uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversation_turns(turn_id, conversation_id, visibility, "
                "speaker_profile_id, role, content, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (item_id, conversation_id, visibility, profile_id if visibility == 'private' else None,
                 role, str(content), self._json(metadata or {})),
            )
        return item_id

    def list_turns(self, profile_id: str | None = None, *, conversation_id: str | None = None,
                   limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 5000:
            raise ValueError('Limit must be between 1 and 5000.')
        clauses = ["visibility = 'shared'"]
        parameters: list[Any] = []
        if profile_id:
            clauses.append("(visibility = 'private' AND speaker_profile_id = ?)")
            parameters.append(profile_id)
        sql = 'SELECT * FROM conversation_turns WHERE (' + ' OR '.join(clauses) + ')'
        if conversation_id:
            sql += ' AND conversation_id = ?'
            parameters.append(conversation_id)
        sql += ' ORDER BY created_at DESC, rowid DESC LIMIT ?'
        parameters.append(limit)
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [dict(row) for row in reversed(rows)]

    def integrity_check(self) -> str:
        with self._connect() as connection:
            row = connection.execute('PRAGMA integrity_check').fetchone()
        return str(row[0])

    def counts(self) -> dict[str, int]:
        tables = ('profiles', 'preferences', 'memories', 'conversation_turns', 'reminders',
                  'learned_intents', 'skills', 'agent_definitions', 'agent_jobs', 'code_change_artifacts')
        with self._connect() as connection:
            return {table: int(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
                    for table in tables}
