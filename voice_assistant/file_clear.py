"""Safely clear text-file contents after an explicit, separate confirmation."""

import hashlib
import os
import re
import time
import uuid

from human import pick

CONFIRM_WINDOW_SECONDS = 45
TEXT_EXTENSIONS = {'.txt', '.md', '.csv', '.json', '.py', '.log', '.yaml', '.yml', '.ini'}


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


class FileClear:
    def __init__(self, assistant, clock=time.monotonic):
        self.assistant = assistant
        self.clock = clock
        self.pending = None

    def has_pending(self):
        if self.pending and self.clock() - self.pending['created'] > CONFIRM_WINDOW_SECONDS:
            self.pending = None
        return self.pending is not None

    def cancel(self):
        self.pending = None
        return pick('clear_cancel', ["Okay, I left the file as it was.", "No problem. The contents are untouched."])

    def request(self, spoken):
        self.pending = None
        if not spoken:
            return "Which file's contents should I clear? I'll keep the file itself."
        try:
            root = os.path.realpath(self.assistant.allowed_folder)
            if not os.path.splitext(spoken)[1]:
                matches = [name for name in os.listdir(root)
                           if os.path.isfile(os.path.join(root, name))
                           and os.path.splitext(name)[0].casefold() == spoken.casefold()]
                if len(matches) > 1:
                    self.assistant.pending_dialog = {
                        'request': 'clear file', 'attempts': 0,
                        'created': self.clock(),
                    }
                    return f"I found more than one file called {spoken}. Which full filename should I clear?"
                if matches:
                    spoken = matches[0]
            path = self.assistant.agents['SYSTEM']._safe_file_path(spoken)
            if os.path.dirname(path) != root:
                return "I can clear files directly inside Friday's folder. Which file do you mean?"
            if os.path.splitext(path)[1].lower() not in TEXT_EXTENSIONS:
                return "I can clear text files such as TXT, MD, CSV, JSON or PY. I left that file alone."
            with open(path, 'rb') as handle:
                original = handle.read()
            original.decode('utf-8')
            stat = os.stat(path)
        except FileNotFoundError:
            return f"I couldn't find {spoken} in Friday's folder. Nothing changed."
        except (OSError, UnicodeError, ValueError):
            return "I couldn't safely read that text file, so I left it unchanged."

        self.pending = {
            'path': os.path.basename(path), 'created': self.clock(),
            'sha256': _sha256(original), 'size': len(original),
            'mtime_ns': stat.st_mtime_ns,
        }
        return pick('clear_ask', [
            f"I'll empty {os.path.basename(path)} and keep the file. Say 'confirm clear' to go ahead, or 'cancel'.",
            f"Just checking: clear the contents of {os.path.basename(path)}, leaving the file in place? Say 'confirm clear' or 'cancel'.",
        ])

    @staticmethod
    def is_confirmation(text):
        value = re.sub(r'[^\w\s]', '', (text or '').lower()).strip()
        value = re.sub(r'^(?:(?:hello|hey|wake up|wake|okay|ok)\s+)?friday\s+', '', value)
        return bool(re.fullmatch(
            r'(?:yes\s+)?(?:confirm\s+(?:the\s+)?clear|confirm\s+clearing|clear\s+it|yes|yeah|yep|sure|okay|ok|go ahead|do it)',
            value))

    @staticmethod
    def is_cancellation(text):
        value = re.sub(r'^\s*(?:(?:hello|hey|wake up|wake|okay|ok)\s+)?friday[,\s]+', '', text or '', flags=re.I)
        return bool(re.fullmatch(r"\s*(?:no|nope|cancel(?: that)?|never mind|keep it|leave it)\s*[.! ]*", value, re.I))

    def confirm(self):
        pending = self.pending
        self.pending = None
        if not pending:
            return "There's no file clearing waiting for confirmation."
        backup_path = None
        cleared = False
        try:
            path = self.assistant.agents['SYSTEM']._safe_file_path(pending['path'])
            root = os.path.realpath(self.assistant.allowed_folder)
            if os.path.dirname(path) != root:
                raise ValueError('outside allowed root')
            with open(path, 'rb') as handle:
                current = handle.read()
            stat = os.stat(path)
            if (len(current) != pending['size'] or _sha256(current) != pending['sha256']
                    or stat.st_mtime_ns != pending['mtime_ns']):
                return f"{pending['path']} changed while I was waiting, so I left it alone."

            backup_dir = os.path.join(root, '.friday_undo')
            os.makedirs(backup_dir, exist_ok=True)
            backup_name = uuid.uuid4().hex + '.bak'
            backup_path = os.path.join(backup_dir, backup_name)
            with open(backup_path, 'xb') as handle:
                handle.write(current)
                handle.flush()
                os.fsync(handle.fileno())

            with open(path, 'r+b') as handle:
                current_again = handle.read()
                if _sha256(current_again) != pending['sha256']:
                    os.remove(backup_path)
                    backup_path = None
                    return f"{pending['path']} changed while I was waiting, so I left it alone."
                handle.seek(0)
                handle.truncate()
                handle.flush()
                os.fsync(handle.fileno())
            cleared = True

            self.assistant.record_undo_action({
                'kind': 'file_clear', 'path': pending['path'],
                'backup': os.path.relpath(backup_path, root),
                'original_size': len(current), 'original_sha256': _sha256(current),
                'empty_sha256': _sha256(b''),
            })
            backup_path = None  # The undo record now owns this backup.
            self.assistant.last_file = pending['path']
            return f"Cleared {pending['path']}. The file is still there; say 'undo' to restore its contents."
        except (OSError, ValueError):
            restored = not cleared
            if backup_path and os.path.isfile(backup_path):
                try:
                    if cleared:
                        with open(backup_path, 'rb') as handle:
                            original = handle.read()
                        with open(path, 'r+b') as handle:
                            handle.seek(0)
                            handle.write(original)
                            handle.truncate()
                            handle.flush()
                            os.fsync(handle.fileno())
                        restored = True
                    os.remove(backup_path)
                except OSError:
                    self.assistant.logger.exception('failed to roll back interrupted file clear')
            if restored:
                return "I couldn't complete the clear, but the original contents are still in place."
            return "The clear was interrupted. I couldn't restore the file, and its recovery copy remains in Friday's hidden undo folder."


__all__ = ['FileClear']
