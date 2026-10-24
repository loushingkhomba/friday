"""PostgreSQL persistence for Friday-owned state and profile-scoped household memory."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def _load_project_env() -> None:
    """Load only Friday DB settings; never print values or overwrite process settings."""
    env_path = Path(__file__).resolve().parent / '.env'
    try:
        lines = env_path.read_text(encoding='utf-8').splitlines()
    except OSError:
        lines = []
    allowed = {'FRIDAY_DB_HOST', 'FRIDAY_DB_PORT', 'FRIDAY_DB_NAME', 'FRIDAY_DB_USER', 'FRIDAY_DB_PASSWORD'}
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if key in allowed and key not in os.environ:
            os.environ[key] = value.strip('"\'')


class FridayPostgres:
    """Friday database API. Voice identity scopes retrieval but is not authentication."""

    def __init__(self):
        _load_project_env()
        try:
            import psycopg
            from psycopg.rows import dict_row
            from psycopg.types.json import Jsonb
        except ImportError as exc:
            raise RuntimeError('PostgreSQL driver missing; install requirements.txt (psycopg[binary]).') from exc
        self._psycopg = psycopg
        self._dict_row = dict_row
        self._Jsonb = Jsonb
        self.config = {
            'host': os.environ.get('FRIDAY_DB_HOST', '127.0.0.1'),
            'port': int(os.environ.get('FRIDAY_DB_PORT', '5432')),
            'dbname': os.environ.get('FRIDAY_DB_NAME', 'friday'),
            'user': os.environ.get('FRIDAY_DB_USER', 'friday_app'),
            'password': os.environ.get('FRIDAY_DB_PASSWORD', ''),
            'connect_timeout': 5,
            'row_factory': dict_row,
        }
        if not self.config['password']:
            raise RuntimeError('FRIDAY_DB_PASSWORD is missing from the project .env or process environment.')
        self._initialize()

    def _connect(self):
        return self._psycopg.connect(**self.config)

    def _initialize(self):
        schema = """
        CREATE TABLE IF NOT EXISTS friday_schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS friday_profiles (
            profile_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS friday_profile_state (
            profile_id TEXT PRIMARY KEY REFERENCES friday_profiles(profile_id) ON DELETE CASCADE,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS friday_preferences (
            preference_id TEXT PRIMARY KEY,
            preference_key TEXT NOT NULL,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared','private')),
            owner_profile_id TEXT REFERENCES friday_profiles(profile_id) ON DELETE CASCADE,
            value JSONB NOT NULL,
            source TEXT NOT NULL DEFAULT 'user',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((visibility='shared' AND owner_profile_id IS NULL) OR
                   (visibility='private' AND owner_profile_id IS NOT NULL))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS friday_preference_shared_key
            ON friday_preferences(preference_key) WHERE visibility='shared';
        CREATE UNIQUE INDEX IF NOT EXISTS friday_preference_private_key
            ON friday_preferences(owner_profile_id,preference_key) WHERE visibility='private';
        CREATE TABLE IF NOT EXISTS friday_memories (
            memory_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared','private')),
            owner_profile_id TEXT REFERENCES friday_profiles(profile_id) ON DELETE CASCADE,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedding vector,
            source TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((visibility='shared' AND owner_profile_id IS NULL) OR
                   (visibility='private' AND owner_profile_id IS NOT NULL))
        );
        CREATE INDEX IF NOT EXISTS friday_memories_scope_kind
            ON friday_memories(visibility,owner_profile_id,kind,created_at DESC);
        CREATE TABLE IF NOT EXISTS friday_turns (
            turn_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared','private','unassigned')),
            speaker_profile_id TEXT REFERENCES friday_profiles(profile_id) ON DELETE SET NULL,
            role TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
            content TEXT NOT NULL,
            source TEXT NOT NULL,
            source_key TEXT,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((visibility='private' AND speaker_profile_id IS NOT NULL) OR
                   (visibility IN ('shared','unassigned') AND speaker_profile_id IS NULL)),
            UNIQUE(source,source_key)
        );
        CREATE INDEX IF NOT EXISTS friday_turns_scope_time
            ON friday_turns(visibility,speaker_profile_id,created_at,turn_id);
        CREATE TABLE IF NOT EXISTS friday_state (
            state_id TEXT PRIMARY KEY,
            state_key TEXT NOT NULL,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared','private','unassigned')),
            owner_profile_id TEXT REFERENCES friday_profiles(profile_id) ON DELETE CASCADE,
            value JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((visibility='private' AND owner_profile_id IS NOT NULL) OR
                   (visibility IN ('shared','unassigned') AND owner_profile_id IS NULL))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS friday_state_shared_key
            ON friday_state(state_key) WHERE visibility='shared';
        CREATE UNIQUE INDEX IF NOT EXISTS friday_state_private_key
            ON friday_state(owner_profile_id,state_key) WHERE visibility='private';
        CREATE TABLE IF NOT EXISTS friday_reminders (
            reminder_id TEXT PRIMARY KEY,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared','private')),
            owner_profile_id TEXT REFERENCES friday_profiles(profile_id) ON DELETE CASCADE,
            task TEXT NOT NULL,
            due_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','done','cancelled')),
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK ((visibility='shared' AND owner_profile_id IS NULL) OR
                   (visibility='private' AND owner_profile_id IS NOT NULL))
        );
        CREATE TABLE IF NOT EXISTS friday_learned_intents (
            lesson_id TEXT PRIMARY KEY,
            owner_profile_id TEXT NOT NULL REFERENCES friday_profiles(profile_id) ON DELETE CASCADE,
            phrase TEXT NOT NULL,
            intent TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(owner_profile_id,phrase,intent)
        );
        CREATE TABLE IF NOT EXISTS friday_legacy_records (
            record_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            source_key TEXT NOT NULL,
            visibility TEXT NOT NULL CHECK (visibility IN ('shared','private','unassigned')),
            owner_profile_id TEXT REFERENCES friday_profiles(profile_id) ON DELETE SET NULL,
            payload JSONB NOT NULL,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(source,source_key),
            CHECK ((visibility='private' AND owner_profile_id IS NOT NULL) OR
                   (visibility IN ('shared','unassigned') AND owner_profile_id IS NULL))
        );
        """
        with self._connect() as connection:
            connection.execute(schema)
            version = connection.execute('SELECT COALESCE(MAX(version),0) AS version FROM friday_schema_migrations').fetchone()['version']
            if version > SCHEMA_VERSION:
                raise RuntimeError('Friday DB schema is newer than this Friday build.')
            if version < SCHEMA_VERSION:
                connection.execute('INSERT INTO friday_schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING', (SCHEMA_VERSION,))

    @staticmethod
    def profile_id(label: str | None) -> str | None:
        value = str(label or '').strip().casefold()
        return value if value and value != 'unknown' else None

    def register_profile(self, profile_id: str, display_name: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_profiles(profile_id,display_name) VALUES (%s,%s) "
                "ON CONFLICT(profile_id) DO UPDATE SET display_name=EXCLUDED.display_name,updated_at=now()",
                (profile_id, display_name),
            )

    def save_profile_payload(self, profile_id: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_profile_state(profile_id,payload) VALUES (%s,%s) "
                "ON CONFLICT(profile_id) DO UPDATE SET payload=EXCLUDED.payload,updated_at=now()",
                (profile_id, self._Jsonb(payload)),
            )

    def load_profile_payloads(self) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                'SELECT p.profile_id,p.display_name,s.payload FROM friday_profiles p '
                'LEFT JOIN friday_profile_state s USING(profile_id) ORDER BY p.display_name'
            ).fetchall()
        result = {}
        for row in rows:
            payload = dict(row['payload'] or {})
            payload.setdefault('name', row['display_name'])
            result[row['profile_id']] = payload
        return result

    def save_preference(self, key: str, value: Any, *, profile_id: str | None = None,
                        shared: bool = False, source: str = 'user') -> None:
        if shared and profile_id:
            raise ValueError('Shared preference cannot have a private owner.')
        if not shared and not profile_id:
            raise ValueError('Private preference requires a matched profile.')
        visibility = 'shared' if shared else 'private'
        owner = None if shared else profile_id
        ident = f'{visibility}:{owner or "household"}:{key}'
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_preferences(preference_id,preference_key,visibility,owner_profile_id,value,source) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(preference_id) DO UPDATE "
                "SET value=EXCLUDED.value,source=EXCLUDED.source,updated_at=now()",
                (ident, key, visibility, owner, self._Jsonb(value), source),
            )

    def delete_preference(self, key: str, *, shared: bool = False,
                          profile_id: str | None = None) -> None:
        if shared == bool(profile_id):
            raise ValueError('Choose exactly one preference scope.')
        with self._connect() as connection:
            if shared:
                connection.execute("DELETE FROM friday_preferences WHERE preference_key=%s AND visibility='shared'", (key,))
            else:
                connection.execute("DELETE FROM friday_preferences WHERE preference_key=%s AND visibility='private' AND owner_profile_id=%s", (key, profile_id))

    def load_preferences(self, profile_id: str | None = None) -> dict[str, Any]:
        sql = "SELECT preference_key,value FROM friday_preferences WHERE visibility='shared'"
        params: tuple[Any, ...] = ()
        if profile_id:
            sql += " OR (visibility='private' AND owner_profile_id=%s)"
            params = (profile_id,)
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return {row['preference_key']: row['value'] for row in rows}

    def save_memory(self, content: str, kind: str, *, profile_id: str | None = None,
                    shared: bool = False, metadata: dict[str, Any] | None = None,
                    embedding: list[float] | tuple[float, ...] | None = None,
                    source: str = 'user', memory_id: str | None = None) -> str:
        if not str(content).strip() or not kind:
            raise ValueError('Memory content and kind are required.')
        if shared and profile_id:
            raise ValueError('Shared memory cannot have a private owner.')
        if not shared and not profile_id:
            raise ValueError('Private memory requires a matched profile.')
        item_id = memory_id or uuid.uuid4().hex
        vector = None if embedding is None else '[' + ','.join(format(float(x), '.9g') for x in embedding) + ']'
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_memories(memory_id,visibility,owner_profile_id,kind,content,metadata,embedding,source) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s::vector,%s) ON CONFLICT(memory_id) DO UPDATE SET content=EXCLUDED.content,metadata=EXCLUDED.metadata,embedding=EXCLUDED.embedding,source=EXCLUDED.source",
                (item_id, 'shared' if shared else 'private', None if shared else profile_id,
                 kind, str(content), self._Jsonb(metadata or {}), vector, source),
            )
        return item_id

    def search_memories(self, query_embedding: list[float] | tuple[float, ...],
                        profile_id: str | None = None, *, kinds: tuple[str, ...] | None = None,
                        limit: int = 5) -> list[dict[str, Any]]:
        query = '[' + ','.join(format(float(x), '.9g') for x in query_embedding) + ']'
        clauses = ["visibility='shared'"]
        params: list[Any] = [query]
        if profile_id:
            clauses.append("(visibility='private' AND owner_profile_id=%s)")
            params.append(profile_id)
        sql = 'SELECT memory_id,kind,content,metadata,visibility,owner_profile_id,1-(embedding <=> %s::vector) AS score FROM friday_memories WHERE embedding IS NOT NULL AND (' + ' OR '.join(clauses) + ')'
        # The query vector is first in the SQL expression, so keep its parameter first.
        if kinds:
            sql += ' AND kind = ANY(%s)'
            params.append(list(kinds))
        sql += ' ORDER BY score DESC LIMIT %s'
        params.append(max(1, min(int(limit), 100)))
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def search_memories_text(self, query: str, profile_id: str | None = None, *,
                             kinds: tuple[str, ...] | None = None, limit: int = 5) -> list[dict[str, Any]]:
        terms = [term for term in query.casefold().split() if len(term) > 2]
        if not terms:
            return []
        clauses = ["visibility='shared'"]
        params: list[Any] = []
        if profile_id:
            clauses.append("(visibility='private' AND owner_profile_id=%s)")
            params.append(profile_id)
        sql = 'SELECT memory_id,kind,content,metadata,visibility,owner_profile_id FROM friday_memories WHERE (' + ' OR '.join(clauses) + ')'
        if kinds:
            sql += ' AND kind = ANY(%s)'
            params.append(list(kinds))
        sql += ' ORDER BY created_at DESC LIMIT 1000'
        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        scored = []
        for row in rows:
            haystack = row['content'].casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [dict(row) for _, row in scored[:max(1, min(int(limit), 100))]]

    def list_memories(self, profile_id: str | None = None, *, kinds: tuple[str, ...] | None = None,
                      limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["visibility='shared'"]
        params: list[Any] = []
        if profile_id:
            clauses.append("(visibility='private' AND owner_profile_id=%s)")
            params.append(profile_id)
        sql = 'SELECT memory_id,kind,content,metadata,visibility,owner_profile_id,created_at FROM friday_memories WHERE (' + ' OR '.join(clauses) + ')'
        if kinds:
            sql += ' AND kind = ANY(%s)'
            params.append(list(kinds))
        sql += ' ORDER BY created_at DESC LIMIT %s'
        params.append(max(1, min(int(limit), 1000)))
        with self._connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def delete_memory(self, memory_id: str) -> None:
        with self._connect() as connection:
            connection.execute('DELETE FROM friday_memories WHERE memory_id=%s',(memory_id,))

    def update_reminder_status(self, reminder_id: str, status: str) -> None:
        if status not in {'pending','done','cancelled'}:
            raise ValueError('Invalid reminder status.')
        with self._connect() as connection:
            connection.execute('UPDATE friday_reminders SET status=%s WHERE reminder_id=%s',(status,reminder_id))

    def append_turn(self, role: str, content: str, *, session_id: str,
                    profile_id: str | None = None, shared: bool = False,
                    metadata: dict[str, Any] | None = None, source: str = 'live',
                    source_key: str | None = None, created_at: Any = None,
                    turn_id: str | None = None) -> str:
        if role not in {'user','assistant','system'}:
            raise ValueError('Unsupported conversation role.')
        if shared and profile_id:
            raise ValueError('Shared turn cannot have a private owner.')
        visibility = 'shared' if shared else ('private' if profile_id else 'unassigned')
        turn_id = turn_id or uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_turns(turn_id,session_id,visibility,speaker_profile_id,role,content,source,source_key,metadata,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s,now())) ON CONFLICT(source,source_key) DO NOTHING",
                (turn_id, session_id, visibility, profile_id if visibility == 'private' else None,
                 role, str(content), source, source_key, self._Jsonb(metadata or {}), created_at),
            )
        return turn_id

    def set_legacy_turn_scope(self, source_key: str, profile_id: str | None) -> None:
        visibility = 'private' if profile_id else 'unassigned'
        with self._connect() as connection:
            connection.execute(
                'UPDATE friday_turns SET visibility=%s,speaker_profile_id=%s '
                "WHERE source='legacy_conversation_log' AND source_key=%s",
                (visibility, profile_id, source_key),
            )

    def list_turns(self, profile_id: str | None = None, *, limit: int = 100,
                   sources: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        clauses = ["visibility='shared'"]
        params: list[Any] = []
        if profile_id:
            clauses.append("(visibility='private' AND speaker_profile_id=%s)")
            params.append(profile_id)
        sql = 'SELECT turn_id,session_id,role,content,metadata,created_at,source,speaker_profile_id FROM friday_turns WHERE (' + ' OR '.join(clauses) + ')'
        if sources:
            sql += ' AND source = ANY(%s)'
            params.append(list(sources))
        sql += ' ORDER BY created_at DESC,turn_id DESC LIMIT %s'
        params.append(max(1, min(int(limit), 5000)))
        with self._connect() as connection:
            return list(reversed(connection.execute(sql, params).fetchall()))

    def append_legacy_record(self, source: str, source_key: str, payload: Any, *,
                             visibility: str, owner_profile_id: str | None = None) -> None:
        record_id = f'{source}:{source_key}'
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_legacy_records(record_id,source,source_key,visibility,owner_profile_id,payload) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(source,source_key) DO NOTHING",
                (record_id, source, source_key, visibility, owner_profile_id, self._Jsonb(payload)),
            )

    def save_state(self, key: str, value: Any, *, profile_id: str | None = None,
                   shared: bool = False) -> None:
        if shared and profile_id:
            raise ValueError('Shared state cannot have a private owner.')
        if not shared and not profile_id:
            raise ValueError('Private state requires a matched profile.')
        visibility = 'shared' if shared else 'private'
        owner = None if shared else profile_id
        state_id = f'{visibility}:{owner or "household"}:{key}'
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_state(state_id,state_key,visibility,owner_profile_id,value) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT(state_id) DO UPDATE SET value=EXCLUDED.value,updated_at=now()",
                (state_id,key,visibility,owner,self._Jsonb(value)),
            )

    def load_state(self, key: str, profile_id: str | None = None, default: Any = None) -> Any:
        with self._connect() as connection:
            if profile_id:
                private = connection.execute(
                    "SELECT value FROM friday_state WHERE state_key=%s AND visibility='private' AND owner_profile_id=%s",
                    (key,profile_id),
                ).fetchone()
                if private:
                    return private['value']
            shared = connection.execute(
                "SELECT value FROM friday_state WHERE state_key=%s AND visibility='shared'",(key,)
            ).fetchone()
        return shared['value'] if shared else default

    def load_assistant_state(self, profile_id: str | None = None) -> dict[str, Any]:
        shared = self.load_state('assistant_shared',default={}) or {}
        private = self.load_state('assistant_private',profile_id,default={}) or {} if profile_id else {}
        prefs = self.load_preferences(profile_id)
        prefs.update(shared.get('preferences') or {})
        prefs.update(private.get('preferences') or {})
        result = dict(shared)
        result.update({key:value for key,value in private.items() if key != 'preferences'})
        result['preferences'] = prefs
        result.setdefault('notes',[])
        result.setdefault('ideas',[])
        result.setdefault('conversation_history',[])
        result.setdefault('last_undo_action',None)
        return result

    def save_assistant_state(self, data: dict[str, Any], profile_id: str | None = None) -> None:
        prefs = dict(data.get('preferences') or {})
        shared_prefs = {key:prefs[key] for key in ('household_admin',) if key in prefs}
        private_prefs = {key:prefs[key] for key in ('name','city','response_style','setup_complete') if key in prefs}
        shared = {
            'preferences':shared_prefs,
            'notes':data.get('notes') if isinstance(data.get('notes'),list) else [],
            'ideas':data.get('ideas') if isinstance(data.get('ideas'),list) else [],
            'capabilities_seen':data.get('capabilities_seen',[]),
        }
        self.save_state('assistant_shared',shared,shared=True)
        for key,value in shared_prefs.items():
            self.save_preference(key,value,shared=True)
        if profile_id:
            for key,value in private_prefs.items():
                self.save_preference(key,value,profile_id=profile_id)
            private = {'last_undo_action':data.get('last_undo_action')}
            self.save_state('assistant_private',private,profile_id=profile_id)

    def save_learned_intent(self, profile_id: str, phrase: str, intent: str) -> None:
        lesson_id = f'{profile_id}:{phrase.casefold().strip()}:{intent}'
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_learned_intents(lesson_id,owner_profile_id,phrase,intent) VALUES (%s,%s,%s,%s) "
                "ON CONFLICT(owner_profile_id,phrase,intent) DO NOTHING",
                (lesson_id,profile_id,phrase.strip(),intent),
            )

    def list_learned_intents(self, profile_id: str | None) -> list[dict[str, Any]]:
        if not profile_id:
            return []
        with self._connect() as connection:
            return list(connection.execute(
                'SELECT phrase,intent,created_at FROM friday_learned_intents WHERE owner_profile_id=%s ORDER BY created_at',
                (profile_id,),
            ).fetchall())

    def save_reminder(self, reminder_id: str, task: str, due_at: Any, *,
                      profile_id: str | None, shared: bool = False,
                      status: str = 'pending') -> None:
        if not shared and not profile_id:
            raise ValueError('Private reminder requires a matched profile.')
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO friday_reminders(reminder_id,visibility,owner_profile_id,task,due_at,status) "
                "VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT(reminder_id) DO UPDATE "
                "SET task=EXCLUDED.task,due_at=EXCLUDED.due_at,status=EXCLUDED.status",
                (reminder_id,'shared' if shared else 'private',None if shared else profile_id,task,due_at,status),
            )

    def list_reminders(self, profile_id: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT reminder_id AS id,task AS text,due_at AS time,status FROM friday_reminders WHERE status='pending' AND visibility='shared'"
        params: tuple[Any, ...] = ()
        if profile_id:
            sql += " OR (status='pending' AND visibility='private' AND owner_profile_id=%s)"
            params = (profile_id,)
        sql += ' ORDER BY time'
        with self._connect() as connection:
            rows = connection.execute(sql,params).fetchall()
        return [dict(row, triggered=False) for row in rows]

    def save_profile_bundle(self, document: dict[str, Any]) -> None:
        profiles = document.get('profiles', {}) if isinstance(document, dict) else {}
        keep = []
        for key, payload in profiles.items():
            if not isinstance(payload, dict):
                continue
            profile_id = str(key).casefold()
            display_name = str(payload.get('name') or key)
            self.register_profile(profile_id,display_name)
            self.save_profile_payload(profile_id,payload)
            keep.append(profile_id)
        self.save_state('speaker_onboarding_complete',bool(document.get('onboarding_complete')),shared=True)
        if keep:
            with self._connect() as connection:
                connection.execute('DELETE FROM friday_profiles WHERE NOT (profile_id = ANY(%s))',(keep,))

    def load_profile_bundle(self) -> dict[str, Any]:
        profiles = self.load_profile_payloads()
        onboarding = self.load_state('speaker_onboarding_complete',default=False)
        return {'version':1,'profiles':profiles,'onboarding_complete':bool(onboarding)}

    def count_memories(self, kind: str | None = None) -> int:
        with self._connect() as connection:
            if kind:
                row = connection.execute('SELECT count(*) AS n FROM friday_memories WHERE kind=%s',(kind,)).fetchone()
            else:
                row = connection.execute('SELECT count(*) AS n FROM friday_memories').fetchone()
        return int(row['n'])

    def counts(self) -> dict[str, int]:
        tables = ('friday_profiles','friday_profile_state','friday_preferences','friday_memories',
                  'friday_turns','friday_state','friday_reminders','friday_learned_intents','friday_legacy_records')
        with self._connect() as connection:
            return {table: connection.execute(f'SELECT count(*) AS n FROM {table}').fetchone()['n'] for table in tables}


__all__ = ['FridayPostgres', 'SCHEMA_VERSION']