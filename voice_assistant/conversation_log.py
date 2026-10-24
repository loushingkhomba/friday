"""Append-only conversation records; PostgreSQL is primary when configured."""
import json
import os
import threading
import uuid
from datetime import datetime


class ConversationLog:
    def __init__(self, directory, store=None, speaker_provider=None):
        self.directory = os.path.abspath(directory)
        self.store = store
        self.speaker_provider = speaker_provider
        if self.store is None:
            os.makedirs(self.directory, exist_ok=True)
        self.session_id = datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:8]
        self._lock = threading.Lock()

    def append(self, role, content, **fields):
        now = datetime.now().astimezone()
        record = {
            'timestamp': now.isoformat(timespec='seconds'),
            'session_id': self.session_id,
            'role': role,
            'content': str(content),
        }
        record.update({key: value for key, value in fields.items() if value is not None})
        if self.store is not None:
            speaker = record.get('speaker')
            if not speaker and self.speaker_provider:
                speaker = self.speaker_provider()
            profile_id = self.store.profile_id(speaker)
            metadata = {key: value for key, value in record.items()
                        if key not in {'timestamp','session_id','role','content','speaker'}}
            self.store.append_turn(
                role, str(content), session_id=self.session_id, profile_id=profile_id,
                metadata=metadata, source='live_log', source_key=uuid.uuid4().hex, created_at=now,
            )
            return
        path = os.path.join(self.directory, f"friday_{now.strftime('%Y-%m-%d')}.jsonl")
        with self._lock, open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')


__all__ = ['ConversationLog']