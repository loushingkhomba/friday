"""Idempotently copy Friday's existing persistent records into local PostgreSQL.

Legacy files and Chroma directories are read-only inputs and are never removed.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from friday_postgres import FridayPostgres


ROOT = Path(__file__).resolve().parent
LOCAL = Path.home() / 'AppData' / 'Local' / 'Friday' / 'personalization'


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def scope_for(label: Any, profile_ids: set[str]) -> tuple[str, str | None]:
    profile_id = str(label or '').strip().casefold()
    if profile_id and profile_id != 'unknown' and profile_id in profile_ids:
        return 'private', profile_id
    return 'unassigned', None


def migrate() -> dict[str, int]:
    store = FridayPostgres()
    source_counts = {'profiles':0,'preferences':0,'memories':0,'speaker_turns':0,
                     'conversation_logs':0,'legacy_history':0,'learned_intents':0}

    profile_doc = read_json(LOCAL / 'speaker_profiles.json', {})
    profiles = profile_doc.get('profiles', {}) if isinstance(profile_doc, dict) else {}
    profile_ids = set()
    for key, payload in profiles.items():
        if not isinstance(payload, dict):
            continue
        profile_id = str(key).strip().casefold()
        display_name = str(payload.get('name') or key).strip()
        if not profile_id or not display_name:
            continue
        store.register_profile(profile_id, display_name)
        store.save_profile_payload(profile_id, payload)
        profile_ids.add(profile_id)
        source_counts['profiles'] += 1
    store.save_state('speaker_onboarding_complete', bool(profile_doc.get('onboarding_complete')), shared=True)

    legacy_state = read_json(ROOT / 'data.json', {})
    prefs = legacy_state.get('preferences', {}) if isinstance(legacy_state, dict) else {}
    default_profile = 'the user' if 'the user' in profile_ids else (next(iter(profile_ids)) if len(profile_ids) == 1 else None)
    if default_profile:
        # setup_complete belongs to each person, not the whole household.
        store.delete_preference('setup_complete', shared=True)
    for key, value in (prefs.items() if isinstance(prefs, dict) else []):
        if key in {'name','city','response_style','setup_complete'} and default_profile:
            store.save_preference(key, value, profile_id=default_profile, source='legacy_data_json')
        else:
            store.save_preference(key, value, shared=True, source='legacy_data_json')
        source_counts['preferences'] += 1

    # Keep app state split: household notes/ideas remain shared; undo and personal
    # preferences are attached to the user when that is the only enrolled profile.
    if isinstance(legacy_state, dict):
        store.save_assistant_state(legacy_state, profile_id=default_profile)
        for category in ('notes','ideas'):
            for index, item in enumerate(legacy_state.get(category, []) if isinstance(legacy_state.get(category), list) else []):
                if not isinstance(item, dict) or not str(item.get('text') or '').strip():
                    continue
                kind = 'note' if category == 'notes' else 'idea'
                source_id = str(item.get('id', index))
                store.save_memory(
                    str(item['text']), kind, shared=True,
                    metadata={'id':item.get('id'),'timestamp':item.get('timestamp'),
                              'category':item.get('category'),'memory_id':f'legacy-{kind}-{source_id}'},
                    source='legacy_data_json', memory_id=f'legacy-{kind}-{source_id}',
                )
                source_counts['memories'] += 1
        # Preserve the exact historic conversation snapshot for audit/rollback,
        # but do not make the mixed the user/unknown list available as live context.
        for index, item in enumerate(legacy_state.get('conversation_history', []) if isinstance(legacy_state.get('conversation_history'), list) else []):
            visibility, owner = scope_for(item.get('speaker') if isinstance(item, dict) else None, profile_ids)
            store.append_legacy_record('data_json_history', str(index), item,
                                       visibility=visibility, owner_profile_id=owner)
            source_counts['legacy_history'] += 1
        store.append_legacy_record('data_json_snapshot', 'full', legacy_state,
                                   visibility='unassigned')

    # Curated matched-speaker history is the primary history source for continuity.
    memory_doc = read_json(LOCAL / 'conversation_memory.json', {})
    speaker_lists = memory_doc.get('speakers', {}) if isinstance(memory_doc, dict) else {}
    for speaker, history in speaker_lists.items() if isinstance(speaker_lists, dict) else []:
        visibility, owner = scope_for(speaker, profile_ids)
        base = datetime.now(timezone.utc)
        for index, item in enumerate(history if isinstance(history, list) else []):
            if not isinstance(item, dict) or item.get('role') not in {'user','assistant'} or not isinstance(item.get('content'), str):
                continue
            created = base + timedelta(microseconds=index)
            store.append_turn(
                item['role'], item['content'], session_id=f'legacy-memory-{str(speaker).casefold()}',
                profile_id=owner, metadata={'speaker':speaker,'legacy_index':index},
                source='legacy_speaker_history',
                source_key=f'{str(speaker).casefold()}:{index}', created_at=created,
            )
            source_counts['speaker_turns'] += 1

    logs_dir = ROOT / 'logs' / 'conversations'
    for path in sorted(logs_dir.glob('friday_*.jsonl')):
        session_profiles = {}
        with path.open('r', encoding='utf-8') as handle:
            for line_no, line in enumerate(handle, 1):
                try:
                    item = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(item, dict) or item.get('role') not in {'user','assistant','system'}:
                    continue
                content = item.get('content')
                if not isinstance(content, str):
                    continue
                session_id = str(item.get('session_id') or path.stem)
                explicit_scope = scope_for(item.get('speaker'), profile_ids)
                if item['role'] == 'user':
                    visibility, owner = explicit_scope
                    session_profiles[session_id] = (visibility, owner)
                elif explicit_scope[0] == 'private':
                    visibility, owner = explicit_scope
                else:
                    visibility, owner = session_profiles.get(session_id, ('unassigned', None))
                try:
                    created = datetime.fromisoformat(str(item.get('timestamp')))
                except (TypeError, ValueError):
                    created = None
                metadata = {key:value for key,value in item.items()
                            if key not in {'role','content','session_id','timestamp','speaker'}}
                store.append_turn(
                    item['role'], content, session_id=session_id,
                    profile_id=owner, metadata={**metadata,'speaker_label':item.get('speaker')},
                    source='legacy_conversation_log',
                    source_key=f'{path.name}:{line_no}', created_at=created,
                )
                store.set_legacy_turn_scope(f'{path.name}:{line_no}', owner)
                source_counts['conversation_logs'] += 1

    learning_path = logs_dir / 'learned_intents.json'
    lessons = read_json(learning_path, [])
    for index, lesson in enumerate(lessons if isinstance(lessons, list) else []):
        if not isinstance(lesson, dict) or not default_profile:
            continue
        phrase, intent = lesson.get('phrase'), lesson.get('intent')
        if isinstance(phrase, str) and isinstance(intent, str):
            store.save_learned_intent(default_profile, phrase, intent)
            source_counts['learned_intents'] += 1

    # ChromaDB had zero records in all three collections at migration start.
    # No old vectors are present to transfer. New memories go directly to pgvector.
    return source_counts


if __name__ == '__main__':
    counts = migrate()
    store = FridayPostgres()
    print('Legacy copy completed; source files left unchanged.')
    print('Imported this run:', counts)
    print('PostgreSQL row counts:', store.counts())