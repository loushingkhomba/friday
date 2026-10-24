"""Explicit, constrained user-taught examples for Friday's intent router."""

import json
import os
import re
import tempfile
from datetime import datetime


INTENT_ALIASES = {
    'chat': 'AI_CHAT', 'conversation': 'AI_CHAT', 'answer normally': 'AI_CHAT',
    'list files': 'FILE_LIST', 'show files': 'FILE_LIST', 'check folder': 'FILE_LIST',
    'delete file': 'FILE_DELETE', 'remove file': 'FILE_DELETE',
    'restore file': 'FILE_RESTORE', 'bring file back': 'FILE_RESTORE',
    'create file': 'FILE_CREATE', 'make file': 'FILE_CREATE',
    'add to file': 'FILE_APPEND', 'append to file': 'FILE_APPEND',
    'read file': 'FILE_READ', 'read a file': 'FILE_READ',
    'stop talking': 'STOP', 'stop': 'STOP',
    'weather': 'WEATHER', 'news': 'NEWS',
}
ALLOWED_INTENTS = frozenset(INTENT_ALIASES.values())
_TEACH = re.compile(
    r"^\s*(?:friday[, ]*)?(?:remember|learn)(?:\s+this)?(?:\s+(?:command|phrase|intent))?\s*:?\s*"
    r"when\s+i\s+say\s+(.+?)\s*,?\s*(?:i\s+mean|it\s+means|route\s+it\s+as|treat\s+it\s+as)\s+(.+?)\s*[.!?]*\s*$",
    re.I,
)
_CORRECTION = re.compile(
    r"^\s*(?:hey\s+)?(?:friday[, ]*)?(?:no[, ]*)?(?:that's not what i meant[, ]*|"
    r"you misunderstood[, ]*|that was wrong[, ]*)?(?:i meant|i wanted|i was asking for|"
    r"i was asking you to|you should have)\s+(.+?)\s*[.!?]*\s*$",
    re.I,
)
_CORRECTION_INTENTS = (
    (re.compile(r"^(?:you to )?(?:list|show|check|scan)\s+(?:(?:my|the|your)\s+)?files?\b", re.I), 'FILE_LIST'),
    (re.compile(r"^(?:you to )?(?:delete|remove|erase|trash|scrap|ditch)\s+(?:(?:the|that)\s+)?(?:file|files|it|them)\b", re.I), 'FILE_DELETE'),
    (re.compile(r"^(?:you to )?(?:restore|recover|bring back)\s+(?:(?:the|that)\s+)?(?:file|files|it|them)\b", re.I), 'FILE_RESTORE'),
    (re.compile(r"^(?:you to )?(?:create|make|write)\s+(?:a\s+)?file\b", re.I), 'FILE_CREATE'),
    (re.compile(r"^(?:you to )?(?:add|append)\s+(?:this\s+)?to\s+(?:the\s+)?file\b", re.I), 'FILE_APPEND'),
    (re.compile(r"^(?:you to )?read\s+(?:(?:the|that)\s+)?file\b", re.I), 'FILE_READ'),
    (re.compile(r"^(?:you to )?(?:stop|pause|quiet|silence)\s+(?:talking|speaking)?\b", re.I), 'STOP'),
    (re.compile(r"^(?:you to )?(?:answer|chat|respond)\b", re.I), 'AI_CHAT'),
    (re.compile(r"^(?:you to )?(?:tell me about|answer about|give me)\s+(?:the\s+)?weather\b", re.I), 'WEATHER'),
    (re.compile(r"^(?:you to )?(?:tell me about|give me|share)\s+(?:the\s+)?news\b", re.I), 'NEWS'),
)


def parse_teaching_request(text):
    match = _TEACH.match(text or '')
    if not match:
        return None
    phrase = match.group(1).strip().strip('"\' ')
    label = re.sub(r'^(?:a|an|the)\s+', '', match.group(2).strip().lower())
    intent = INTENT_ALIASES.get(label)
    if not phrase or len(phrase) > 120 or len(phrase.split()) > 16 or intent not in ALLOWED_INTENTS:
        return {'error': 'Use a short phrase and a supported intent: chat, list files, delete file, restore file, create file, add to file, read file, stop talking, weather, or news.'}
    return {'phrase': re.sub(r'\s+', ' ', phrase), 'intent': intent}


def parse_correction_learning(text, previous_phrase):
    """Turn a clear user correction into a candidate lesson; caller must ask approval."""
    if not isinstance(previous_phrase, str) or not previous_phrase.strip():
        return None
    match = _CORRECTION.match(text or '')
    if not match:
        return None
    corrected = re.sub(r'^(?:to|that)\s+', '', match.group(1).strip(), flags=re.I)
    intent = next((name for pattern, name in _CORRECTION_INTENTS if pattern.search(corrected)), None)
    if intent not in ALLOWED_INTENTS:
        return None
    phrase = re.sub(r'\s+', ' ', previous_phrase).strip().strip(' .!?')
    if not phrase or len(phrase) > 120 or len(phrase.split()) > 16:
        return None
    return {'phrase': phrase, 'intent': intent}


class IntentLearning:
    def __init__(self, path, store=None, profile_provider=None):
        self.path = os.path.abspath(path)
        self.store = store
        self.profile_provider = profile_provider

    def examples(self):
        if self.store is not None:
            profile_id = self.profile_provider() if self.profile_provider else None
            rows = self.store.list_learned_intents(profile_id)
            return [item for item in rows[-30:] if item.get('intent') in ALLOWED_INTENTS
                    and isinstance(item.get('phrase'), str) and 0 < len(item['phrase']) <= 120]
        try:
            with open(self.path, encoding='utf-8') as handle:
                value = json.load(handle)
        except (OSError, ValueError):
            return []
        if not isinstance(value, list):
            return []
        return [item for item in value[-30:] if isinstance(item, dict)
                and item.get('intent') in ALLOWED_INTENTS
                and isinstance(item.get('phrase'), str)
                and 0 < len(item['phrase']) <= 120]

    def remember(self, phrase, intent):
        if intent not in ALLOWED_INTENTS or not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 120:
            return False
        if self.store is not None:
            profile_id = self.profile_provider() if self.profile_provider else None
            if not profile_id:
                return False
            self.store.save_learned_intent(profile_id, phrase.strip(), intent)
            return True
        examples = self.examples()
        normalized = phrase.casefold().strip()
        examples = [item for item in examples
                    if not (item['phrase'].casefold().strip() == normalized and item['intent'] == intent)]
        examples.append({'phrase': phrase.strip(), 'intent': intent,
                         'created': datetime.now().astimezone().isoformat(timespec='seconds')})
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='intent-examples-', suffix='.tmp', dir=os.path.dirname(self.path))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(examples[-30:], handle, ensure_ascii=False, indent=2)
                handle.write('\n')
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
        return True


__all__ = ['IntentLearning', 'parse_teaching_request', 'parse_correction_learning', 'ALLOWED_INTENTS']
