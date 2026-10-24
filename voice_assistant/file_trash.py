"""Safe, confirmed, recoverable file deletion for Friday's folder (offline)."""

import difflib
import os
import re
import shutil
import time
from datetime import datetime

from human import pick

CONFIRM_WINDOW_SECONDS = 30
TRASH_DIR = '.trash'

_PREAMBLE = re.compile(
    r"^\s*(?:(?:friday|please|now|then|so|ok|okay|and|well|just|can you|could you|would you|will you|can u|you|"
    r"i want you to|i'd like you to|i would like you to|i need you to|go ahead and|want you to)[,\s]+)+", re.I)
_DELETE = re.compile(r'^\s*(?:delete|remove|erase|trash)\b\s*(.*)$', re.I | re.S)
_NUM = r"(?:two|three|four|five|six|seven|eight|nine|ten|2|3|4|5|6|7|8|9|10|both|these|those|them)"
_ALL = re.compile(r"^(?:(?:all|every|all of|the|these|those)\s+)?(?:" + _NUM + r"\s+)?(?:of\s+)?(?:the\s+)?(?:" + _NUM + r"|files|stuff|things)\b.*$"
                  r"|^(?:all|every)\b.*$|^(?:the\s+)?(?:whole|entire)\b.*\b(?:folder|files?)\b.*$", re.I)
MAX_BULK = 10
ALL_FILES = '*all*'
_VAGUE_WORDS = {'which', 'that', 'is', 'are', 'there', 'here', 'the', 'one', 'file', 'it', 'this', 'only', 'single',
                'existing', 'present', 'available', 'in', 'you', 'see', 'have', 'got', 'i', 'mentioned', 'said', 'just',
                'we', 'talked', 'about', 'listed', 'for', 'me', 'please', 'then', 'now', 'those', 'them', 'text'}
_ANY_LOCATION = re.compile(r"\s*\b(?:in|inside|from|within|out of|of)\s+(?:(?:the|my|your|that|this)\s+)*[\w' ]*?\b(?:folder|directory)\b.*$", re.I)
AWAIT_WINDOW_SECONDS = 30
_LOCATION_TAIL = re.compile(
    r"\s*\b(?:from|in|inside|out of)\s+(?:(?:the|my|your|that|this)\s+)*(?:friday(?:\s*'?s)?\s+)?(?:folder|directory)\b.*$", re.I)
_RESTORE = re.compile(
    r'^\s*(?:restore|recover|undelete|bring back|undo (?:the )?delet(?:e|ion)(?: of)?)\b\s*(.*)$', re.I)
_CONFIRM = re.compile(
    r"^(?:yes[,\s]+)?(?:i\s+)?confirm(?:ed)?(?:\s+(?:the\s+)?(?:file\s+)?delet(?:e|ion))?$"
    r"|^(?:yes[,\s]+)?delete\s+(?:it|that|the file|that file)$|^yes[,\s]+delete$"
    r"|^(?:yes|yeah|yep|sure|okay|ok|alright|please do|go ahead|do it|you can delete it|you can delete that|"
    r"yes please|yes go ahead|yes do it)$", re.I)
_CANCEL = re.compile(r"^(?:no|nope|cancel|never ?mind|don'?t|do not|abort|stop|keep it|leave it)(?:[,\s].*)?$", re.I)
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _clean(raw):
    name = re.sub(r'\s+', ' ', raw or '').strip(' \t\r\n.,!?;:\'"')
    name = re.sub(r'^(?:(?:the|a|an|that|this|my|named|called|file|text file)\s+)+', '', name, flags=re.I).strip()
    name = re.sub(r'\s+(?:text\s+)?file$', '', name, flags=re.I).strip()
    return name


def parse_delete_request(text, last_file=None):
    """Return a spoken file name ('' if missing) for delete requests, None if not one."""
    match = _DELETE.match(_PREAMBLE.sub('', text or ''))
    if not match:
        return None
    body = _ANY_LOCATION.sub('', match.group(1)).strip(' .!?,')
    if _ALL.match(body):
        return ALL_FILES
    mentions_file = re.search(r'\b(?:text\s+)?file\b', body, re.I)
    if mentions_file:
        body = re.sub(r'^(?:(?:the|a|an|that|this|my)\s+)*(?:text\s+)?file\b\s*(?:named\s+|called\s+)?', '', body, flags=re.I)
        body = re.sub(r'^(?:for me|me|please|for me please)$', '', body.strip(), flags=re.I)
        return _clean(body)
    if re.fullmatch(r'(?:it|that|that one|this one)', body.strip(' .!?'), re.I):
        return last_file or ''
    if re.fullmatch(r"[\w][\w .'-]*\.\w{1,5}", body.strip(' .!?')):
        return _clean(body)
    return None


_CAPABILITY_Q = re.compile(
    r"\b(?:do you (?:have|got)|are you (?:able|allowed|capable)|is it possible|can you even|have you got|did (?:it|that) (?:get )?(?:work|enable))\b"
    r".*\b(?:feature|ability|option|capabilit|permission|power|way|able|allowed|enabled?)\w*.*\b(?:delet\w*|remov\w*|trash\w*)\b"
    r"|\b(?:can|could) you (?:even )?(?:delete|remove) files\??$|\bare (?:file )?delet\w* (?:on|enabled|allowed|working|turned on)\b", re.I)


def is_delete_capability_question(text):
    return bool(_CAPABILITY_Q.search(text or ''))


def is_vague_name(spoken):
    """True for 'the file', 'it', 'which is there in the folder': no real name given."""
    words = re.findall(r"[\w']+", _ANY_LOCATION.sub('', spoken or '').lower())
    return all(w in _VAGUE_WORDS for w in words)


def target_from_followup(text, last_file=None):
    """The user answered 'which file?'. Accept a bare name or a full delete sentence."""
    direct = parse_delete_request(text, last_file)
    if direct is not None:
        return direct
    if _ALL.match(re.sub(r'^(?:the\s+)?', '', (text or '').strip(), flags=re.I)):
        return ALL_FILES
    return _clean(_ANY_LOCATION.sub('', text or ''))


def parse_restore_request(text):
    match = _RESTORE.match(text or '')
    if not match:
        return None
    body = _clean(re.sub(r'\b(?:file|from (?:the )?trash|from (?:the )?bin)\b', '', match.group(1), flags=re.I))
    return body


def is_delete_confirmation(text):
    normalized = re.sub(r"[^\w\s,']", '', text or '').strip()
    normalized = re.sub(r'^(?:(?:hey\s+)?friday)[,\s]+', '', normalized, flags=re.I)
    normalized = re.sub(r'\s*,\s*', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    return bool(_CONFIRM.match(normalized))


def is_delete_cancellation(text):
    return bool(_CANCEL.match(re.sub(r"[^\w\s,']", '', text or '').strip()))


class FileTrash:
    """Two-step delete: request -> spoken confirmation -> move into .trash (restorable)."""

    def __init__(self, assistant, clock=time.monotonic):
        self.assistant = assistant
        self.clock = clock
        self.pending = None
        self.awaiting_until = 0.0

    def awaiting_name(self):
        return self.clock() < self.awaiting_until

    def clear_awaiting(self):
        self.awaiting_until = 0.0

    def allowed(self):
        refresh = getattr(self.assistant, 'refresh_delete_policy', None)
        if refresh:
            refresh()
        return bool(self.assistant.guardrails.get('filesystem', {}).get('allow_delete', False))

    @property
    def root(self):
        return os.path.realpath(self.assistant.allowed_folder)

    @property
    def trash_dir(self):
        return os.path.join(self.root, TRASH_DIR)

    def _off_reply(self):
        broken = getattr(self.assistant, 'guardrails_error', '')
        if broken:
            return ("I can't read guardrails dot json because it has a typing mistake near "
                    f"{broken}. Probably a missing comma. Fix that and I'll pick up your delete setting straight away.")
        return ("Deleting files is turned off. To allow it, set allow_delete to true under filesystem "
                "in guardrails dot json. I'll notice right away, no restart needed.")

    def capability_reply(self):
        if self.allowed():
            return pick('delete_cap', [
                "Yes. Deleting is switched on. Tell me which file, I'll read it back, and you say confirm delete. It goes to the trash so you can restore it.",
                "I can. It's enabled now. Name a file and I'll ask you to confirm before moving it to the trash.",
            ])
        return self._off_reply()

    def has_pending(self):
        if self.pending and self.clock() - self.pending['created'] > CONFIRM_WINDOW_SECONDS:
            self.pending = None
        return self.pending is not None

    def _resolve(self, spoken):
        """Find one existing file directly inside the root; returns (path, error)."""
        self.awaiting_until = 0.0
        if spoken == ALL_FILES:
            return None, None
        name = _clean(spoken)
        if name and not is_vague_name(name) and (re.search(r'[*?]', name) or _INVALID.search(name)):
            return None, 'I only delete one file at a time, by its exact name.'
        if name.lower().startswith(TRASH_DIR):
            return None, 'That is my trash folder. I will not delete from it.'
        try:
            entries = os.listdir(self.root)
        except OSError:
            return None, "I can't read Friday's folder right now."
        files = [e for e in entries if os.path.isfile(os.path.join(self.root, e))]
        if not name or is_vague_name(name):
            if len(files) == 1:
                return os.path.realpath(os.path.join(self.root, files[0])), None
            if files:
                return None, self._ask_which()
            return None, "There are no files in Friday's folder to delete."
        low = name.lower()
        for wanted in (low, low + '.txt'):
            hits = [e for e in files if e.lower() == wanted]
            if len(hits) == 1:
                path = os.path.realpath(os.path.join(self.root, hits[0]))
                if os.path.dirname(path) != self.root:
                    return None, 'That file is outside Friday\'s folder.'
                return path, None
        stem_hits = [e for e in files if os.path.splitext(e)[0].lower() == low]
        if len(stem_hits) == 1:
            return os.path.realpath(os.path.join(self.root, stem_hits[0])), None
        if len(stem_hits) > 1:
            return None, f"More than one file is called {name}. Say the full name with its extension."
        # Whisper often garbles names ("IDR.txt" for "idea.txt"). The spoken confirmation
        # reads back the real name, so offering one close match is safe.
        stems = {os.path.splitext(e)[0].lower(): e for e in files}
        close = difflib.get_close_matches(os.path.splitext(low)[0], list(stems), n=2, cutoff=0.5)
        if len(close) == 1:
            return os.path.realpath(os.path.join(self.root, stems[close[0]])), None
        if len(close) > 1:
            return None, f"I'm not sure which file you mean by {name}. Say the full name."
        return None, f"I can't find a file called {name} in Friday's folder."

    def _ask_which(self, lead=''):
        try:
            files = sorted(e for e in os.listdir(self.root)
                           if not e.startswith('.') and os.path.isfile(os.path.join(self.root, e)))
        except OSError:
            files = []
        self.awaiting_until = self.clock() + AWAIT_WINDOW_SECONDS
        listing = ', '.join(files[:6])
        if not files:
            self.awaiting_until = 0.0
            return "There are no files in Friday's folder to delete."
        return f"{lead} Which one? I see {listing}.".strip()

    @staticmethod
    def _stamp(path):
        info = os.stat(path)
        return info.st_size, info.st_mtime_ns

    def request(self, spoken):
        self.pending = None
        self.awaiting_until = 0.0
        if not self.allowed():
            return self._off_reply()
        if spoken == ALL_FILES:
            return self._request_all()
        path, error = self._resolve(spoken)
        if error:
            return error
        self.pending = {'path': path, 'created': self.clock(), 'stamp': self._stamp(path), 'items': [(path, self._stamp(path))]}
        name = os.path.basename(path)
        size = self.pending['stamp'][0]
        return pick('delete_ask', [
            f"Okay, I'll delete {name}. It's {size} bytes and goes to the trash, so you can get it back. Say confirm delete, or cancel.",
            f"Just to be sure: delete {name}? I'll move it to the trash so it's recoverable. Say confirm delete to go ahead.",
            f"Got it, {name}. Say confirm delete and I'll send it to the trash, or cancel to keep it.",
        ])

    def _request_all(self):
        try:
            names = sorted(e for e in os.listdir(self.root)
                           if not e.startswith('.') and os.path.isfile(os.path.join(self.root, e)))
        except OSError:
            return "I can't read Friday's folder right now."
        if not names:
            return "There are no files in Friday's folder to delete."
        if len(names) > MAX_BULK:
            return f"That's {len(names)} files, more than the {MAX_BULK} I'll remove at once. Name the ones you want gone."
        items = []
        for name in names:
            path = os.path.realpath(os.path.join(self.root, name))
            items.append((path, self._stamp(path)))
        self.pending = {'path': items[0][0], 'created': self.clock(), 'stamp': items[0][1], 'items': items}
        listing = ', '.join(names)
        return (f"You want all {len(names)} files gone: {listing}. They all go to the trash, so you can restore them. "
                f"Say confirm delete, or cancel.")

    def confirm(self):
        if not self.has_pending():
            return 'There is no delete waiting for confirmation.'
        pending, self.pending = self.pending, None
        if not self.allowed():
            return 'Deleting files is turned off, so I left it alone.'
        moved, problems = [], []
        os.makedirs(self.trash_dir, exist_ok=True)
        for path, stamp in pending.get('items') or [(pending['path'], pending['stamp'])]:
            name = os.path.basename(path)
            if not os.path.isfile(path) or self._stamp(path) != stamp:
                problems.append(f'{name} changed or disappeared')
                continue
            target = os.path.join(self.trash_dir, f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}__{name}")
            try:
                shutil.move(path, target)
            except OSError as error:
                self._log('file delete failed path=%s error=%s', path, error)
                problems.append(f"{name} failed: {error}")
                continue
            self._log('file moved to trash path=%s trash=%s', path, target)
            moved.append(name)
        if not moved:
            return "I didn't delete anything: " + '; '.join(problems) + '.'
        record_undo = getattr(self.assistant, 'record_undo_action', None)
        if record_undo:
            try:
                record_undo({'kind': 'file_delete', 'names': moved})
            except OSError as error:
                self._log('could not save undo record for trashed files names=%s error=%s', moved, error)
        if len(moved) == 1:
            stem = os.path.splitext(moved[0])[0]
            reply = f"Deleted {moved[0]}. Say restore {stem} if you change your mind."
        else:
            reply = f"Deleted {len(moved)} files: {', '.join(moved)}. Say restore and the name to bring one back."
        return reply + (' But ' + '; '.join(problems) + '.' if problems else '')

    def cancel(self):
        had = self.has_pending()
        self.pending = None
        return 'Okay, I kept the file.' if had else None

    def list_trash(self):
        try:
            names = sorted(os.listdir(self.trash_dir))
        except OSError:
            return []
        return [n for n in names if '__' in n and os.path.isfile(os.path.join(self.trash_dir, n))]

    def restore(self, spoken=''):
        items = self.list_trash()
        if not items:
            return 'The trash is empty.'
        name = _clean(spoken).lower()
        if name:
            wanted = {name, name + '.txt'}
            matches = [i for i in items if i.split('__', 1)[1].lower() in wanted
                       or os.path.splitext(i.split('__', 1)[1])[0].lower() == name]
            if not matches:
                # Speech recognition can slightly garble long filenames. Compare the
                # original names after stripping the timestamp prefix and punctuation.
                spoken_key = re.sub(r'[^a-z0-9]', '', os.path.splitext(name)[0])
                candidates = {}
                for item in items:
                    original = item.split('__', 1)[1]
                    key = re.sub(r'[^a-z0-9]', '', os.path.splitext(original)[0].lower())
                    candidates.setdefault(key, []).append(item)
                close = difflib.get_close_matches(spoken_key, list(candidates), n=2, cutoff=0.72)
                if len(close) == 1:
                    matches = candidates[close[0]]
                elif len(close) > 1:
                    names = ', '.join(candidates[key][0].split('__', 1)[1] for key in close)
                    return f"I found more than one similar file in the trash: {names}. Say the exact filename."
        else:
            matches = items
        if not matches:
            return f"I can't find {name} in the trash."
        chosen = matches[-1]
        original = chosen.split('__', 1)[1]
        destination = os.path.join(self.root, original)
        if os.path.exists(destination):
            return f'{original} already exists in Friday\'s folder, so I did not restore over it.'
        try:
            shutil.move(os.path.join(self.trash_dir, chosen), destination)
        except OSError as error:
            return f"I couldn't restore it: {error}"
        self._log('file restored path=%s', destination)
        return f'Restored {original}.'

    def _log(self, message, *args):
        logger = getattr(self.assistant, 'logger', None)
        if logger:
            logger.info(message, *args)

