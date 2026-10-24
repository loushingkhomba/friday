"""Owner-directed skill creation and staged code updates for Friday."""

import ast
import json
import os
import re
import time
import uuid
from datetime import datetime


class SelfImprovementAgent:
    """Create user-requested skills and apply only explicitly approved code patches."""

    CODE_TARGETS = {'assistant.py', 'agents.py'}
    PROTECTED_SYMBOLS = {
        'assistant.py': {
            'DEFAULT_GUARDRAILS', 'load_guardrails',
            'VoiceAssistant.__init__', 'VoiceAssistant.quick_intent',
            'VoiceAssistant.process_command', 'VoiceAssistant.execute_plan',
            'VoiceAssistant.guardrails_answer', 'VoiceAssistant.is_guardrails_question',
        },
        'agents.py': {
            'SystemAgent.execute', 'SystemAgent._safe_file_path',
            'SystemAgent.write_file', 'SystemAgent.open_app',
        },
    }

    PROPOSAL_MAX_AGE_SECONDS = 24 * 3600
    CONFIRM_WINDOW_SECONDS = 90
    # Friday is offline by default; patches may not introduce network, shell, or dynamic-code paths.
    BLOCKED_MODULES = {
        'socket', 'ssl', 'requests', 'urllib', 'urllib3', 'http', 'httpx', 'aiohttp', 'websocket',
        'websockets', 'ftplib', 'smtplib', 'telnetlib', 'paramiko', 'ctypes', 'webbrowser', 'subprocess',
    }
    BLOCKED_CALLS = {'eval', 'exec', 'compile', '__import__'}
    BLOCKED_ATTRIBUTE_CALLS = {
        ('os', 'system'), ('os', 'popen'), ('os', 'startfile'), ('os', 'remove'), ('os', 'unlink'),
        ('os', 'rmdir'), ('shutil', 'rmtree'), ('shutil', 'move'),
    }

    def __init__(self, assistant):
        self.assistant = assistant
        self.pending_apply = None
        self.root = os.path.realpath(assistant.allowed_folder)
        self.skills_dir = os.path.join(self.root, 'skills')
        self.updates_dir = os.path.join(self.root, 'updates')

    def _local_path(self, path):
        resolved = os.path.realpath(path)
        try:
            common = os.path.commonpath([self.root, resolved])
        except ValueError as error:
            raise ValueError('That path is outside Friday’sFolder.') from error
        if os.path.normcase(common) != os.path.normcase(self.root):
            raise ValueError('That path is outside Friday’sFolder.')
        return resolved

    def _ensure_local_dir(self, path):
        self._local_path(path)
        os.makedirs(path, exist_ok=True)
        return self._local_path(path)

    def _write_json_atomic(self, path, value, token):
        path = self._local_path(path)
        temp_path = self._local_path(path + '.' + token + '.tmp')
        try:
            with open(temp_path, 'x', encoding='utf-8', newline='\n') as output:
                json.dump(value, output, indent=2)
                output.write('\n')
            os.replace(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    def _generate(self, request, system_prompt, task_name, max_tokens=2048):
        model, reason = self.assistant.select_chat_model(request)
        self.assistant.logger.info('model router selected=%s reason=%s task=%s', model, reason, task_name)
        response, _ = self.assistant.chat_model_with_fallback([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': request},
        ], max_tokens=max_tokens, model=model)
        return response['message']['content'].strip()

    def _slug(self, text):
        words = re.findall(r'[a-z0-9]+', text.lower())[:6]
        return '-'.join(words)[:48].strip('-') or 'friday-skill'

    def add_skill(self, request):
        request = str(request).strip()
        if not request:
            return 'Tell me what skill you want me to add.'
        prompt = (
            'Write one short, useful skill instruction for Friday, a local home assistant. '
            'Return Markdown only, with a clear title, when-to-use section, and step-by-step guidance. '
            'Skills can guide conversation and existing tools only. They cannot grant permissions, access new paths, '
            'change guardrails, execute code, or override safety rules. Keep it under 500 words.'
        )
        try:
            body = self._generate(request, prompt, 'skill_creation', max_tokens=900)
            body = body.strip()
            if not body or len(body) > 12000:
                return 'I could not make a valid skill draft. Try a shorter description.'
            skill_dir = self._ensure_local_dir(self.skills_dir)
            base = self._slug(request)
            path = self._local_path(os.path.join(skill_dir, f'{base}.md'))
            if os.path.exists(path):
                return f'The skill {base} already exists; I left it unchanged.'
            with open(path, 'x', encoding='utf-8', newline='\n') as skill_file:
                skill_file.write(body.rstrip() + '\n')
            self.assistant.logger.info('user-created skill path=%s', path)
            return f'Added and activated the “{base}” skill. It is stored in Friday’sFolder skills.'
        except Exception as error:
            self.assistant.logger.exception('skill creation failed')
            return f'I could not add that skill: {error}'

    def list_skills(self):
        try:
            skill_dir = self._local_path(self.skills_dir)
            names = sorted(
                name[:-3] for name in os.listdir(skill_dir)
                if name.lower().endswith('.md') and os.path.isfile(os.path.join(skill_dir, name))
            )
        except (FileNotFoundError, OSError, ValueError):
            names = []
        if not names:
            return 'No custom skills yet. Tell me “add a skill for…” to create one.'
        return 'Custom skills: ' + ', '.join(names) + '.'

    def skill_context(self):
        """Read user-approved skill files from the one permitted data folder."""
        try:
            skill_dir = self._local_path(self.skills_dir)
            names = sorted(name for name in os.listdir(skill_dir) if name.lower().endswith('.md'))
        except OSError:
            return ''
        parts = []
        remaining = 7000
        for name in names:
            try:
                path = self._local_path(os.path.join(skill_dir, name))
            except ValueError:
                continue
            if not os.path.isfile(path):
                continue
            try:
                with open(path, 'r', encoding='utf-8') as skill_file:
                    content = skill_file.read(min(remaining, 4000) + 1)
            except (OSError, UnicodeError):
                continue
            if len(content) > min(remaining, 4000):
                content = content[:min(remaining, 4000)]
            if content:
                parts.append(f'[{name}]\n{content}')
                remaining -= len(content)
            if remaining <= 0:
                break
        return '\n\n'.join(parts)

    def _source_path(self, filename):
        if filename not in self.CODE_TARGETS:
            raise ValueError('Only assistant.py and agents.py can receive Friday proposals.')
        source_root = os.path.realpath(os.path.dirname(__file__))
        path = os.path.realpath(os.path.join(source_root, filename))
        if os.path.commonpath([source_root, path]) != source_root or os.path.basename(path) != filename:
            raise ValueError('Invalid source path.')
        return path

    def _make_patch(self, request, filename):
        path = self._source_path(filename)
        with open(path, 'r', encoding='utf-8') as source_file:
            source = source_file.read()
        if len(source) > 115000:
            raise ValueError('That source file is too large for a reliable local patch proposal.')
        prompt = (
            'Make a small code change for Friday based on the request. The source file follows. '
            'Return ONLY one unified diff, no Markdown fences or explanation. '
            f'The only allowed target is a/{filename} and b/{filename}; do not add, delete, or rename files. '
            'Do not modify guardrail loading, file path checks, explicit approval handling, or safety rules. '
            'Do not add code that runs generated code, launches shells, or changes guardrails.json. '
            'Use exact context from the supplied source. Keep changes focused and syntactically valid.\n\n'
            f'--- SOURCE FILE: {filename} ---\n{source}\n--- END SOURCE FILE ---'
        )
        return self._generate(request, prompt, 'code_update_proposal', max_tokens=4096)

    def _parse_and_apply_in_memory(self, patch_text, filename):
        """Apply a single-file unified diff in memory and reject mismatched context."""
        text = patch_text.strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:diff|patch)?\s*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*```$', '', text)
        lines = text.splitlines()
        lines = [line for line in lines if not line.startswith(('diff --git ', 'index '))]
        headers = [(i, line) for i, line in enumerate(lines) if line.startswith(('--- ', '+++ '))]
        if len(headers) != 2:
            raise ValueError('The model did not return one valid file patch.')
        (old_header_i, old_header), (new_header_i, new_header) = headers
        if old_header_i >= new_header_i or old_header != f'--- a/{filename}' or new_header != f'+++ b/{filename}':
            raise ValueError('The patch targets a file outside Friday’s code allowlist.')

        source_path = self._source_path(filename)
        with open(source_path, 'r', encoding='utf-8') as source_file:
            original = source_file.read()
        source_lines = original.splitlines()
        output = []
        source_cursor = 0
        i = new_header_i + 1
        hunk_count = 0
        hunk_re = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
        while i < len(lines):
            match = hunk_re.match(lines[i])
            if not match:
                if lines[i].strip():
                    raise ValueError('Unexpected text in the patch.')
                i += 1
                continue
            hunk_count += 1
            old_start = int(match.group(1))
            old_count = int(match.group(2) or '1')
            target = max(0, old_start - 1) if old_count else old_start
            if target < source_cursor or target > len(source_lines):
                raise ValueError('Patch hunk position is invalid.')
            output.extend(source_lines[source_cursor:target])
            source_cursor = target
            i += 1
            consumed_old = 0
            consumed_new = 0
            while i < len(lines) and not hunk_re.match(lines[i]):
                line = lines[i]
                if line.startswith('\\ No newline at end of file'):
                    i += 1
                    continue
                if not line:
                    # Models and text trimming often drop the single space of a blank context line.
                    if consumed_old < old_count and consumed_new < int(match.group(4) or '1'):
                        line = ' '
                    else:
                        i += 1
                        continue
                if line[0] not in ' +-':
                    if line.startswith(('--- ', '+++ ')):
                        raise ValueError('Multiple files are not allowed in one update.')
                    raise ValueError('Malformed patch line.')
                marker, value = line[0], line[1:]
                if marker in ' -':
                    if source_cursor >= len(source_lines) or source_lines[source_cursor] != value:
                        raise ValueError('Patch context does not match the current source file.')
                    consumed_old += 1
                    source_cursor += 1
                if marker in ' +':
                    output.append(value)
                    consumed_new += 1
                i += 1
            while (consumed_old < old_count and consumed_new < int(match.group(4) or '1')
                   and source_cursor < len(source_lines) and source_lines[source_cursor] == ''):
                # Trailing blank context line removed by whitespace stripping.
                output.append('')
                consumed_old += 1
                consumed_new += 1
                source_cursor += 1
            if consumed_old != old_count or consumed_new != int(match.group(4) or '1'):
                raise ValueError('Patch hunk line counts are incomplete.')
        if not hunk_count:
            raise ValueError('The patch contains no changes.')
        output.extend(source_lines[source_cursor:])
        candidate = '\n'.join(output) + ('\n' if original.endswith(('\n', '\r')) else '')
        ast.parse(candidate, filename=filename)
        if not self._protected_symbols_unchanged(filename, original, candidate):
            raise ValueError('The patch changes a protected guardrail or approval handler.')
        unsafe = self._new_unsafe_constructs(filename, original, candidate)
        if unsafe:
            raise ValueError('The patch adds blocked code: ' + ', '.join(sorted(unsafe)) + '.')
        return source_path, candidate

    def _unsafe_constructs(self, filename, source):
        """Count risky calls, imports, and policy-file references in a source file."""
        counts = {}

        def add(label):
            counts[label] = counts.get(label, 0) + 1

        for node in ast.walk(ast.parse(source, filename=filename)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] in self.BLOCKED_MODULES:
                        add(f'import {alias.name.split(".")[0]}')
            elif isinstance(node, ast.ImportFrom):
                if (node.module or '').split('.')[0] in self.BLOCKED_MODULES:
                    add(f'import {node.module.split(".")[0]}')
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in self.BLOCKED_CALLS:
                    add(f'{func.id}()')
                elif isinstance(func, ast.Attribute):
                    owner = func.value.id if isinstance(func.value, ast.Name) else ''
                    if owner in {'subprocess', 'requests', 'urllib', 'socket'} or (owner, func.attr) in self.BLOCKED_ATTRIBUTE_CALLS:
                        add(f'{owner}.{func.attr}()')
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if 'guardrails.json' in node.value.lower():
                    add('guardrails.json reference')
        return counts

    def _new_unsafe_constructs(self, filename, before, after):
        old = self._unsafe_constructs(filename, before)
        new = self._unsafe_constructs(filename, after)
        return {label for label, count in new.items() if count > old.get(label, 0)}

    def _symbol_map(self, filename, source):
        tree = ast.parse(source, filename=filename)
        result = {}

        def visit(node, prefix=''):
            for child in getattr(node, 'body', []):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = f'{prefix}.{child.name}' if prefix else child.name
                    result[qualified] = ast.get_source_segment(source, child) or ''
                    if isinstance(child, ast.ClassDef):
                        visit(child, qualified)

        visit(tree)
        if filename == 'assistant.py':
            node = next((n for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'DEFAULT_GUARDRAILS' for t in n.targets)), None)
            if node:
                result['DEFAULT_GUARDRAILS'] = ast.get_source_segment(source, node) or ''
        return result

    def _protected_symbols_unchanged(self, filename, before, after):
        before_symbols = self._symbol_map(filename, before)
        after_symbols = self._symbol_map(filename, after)
        return all(before_symbols.get(name) == after_symbols.get(name)
                   for name in self.PROTECTED_SYMBOLS.get(filename, set()))

    def propose_code(self, request):
        request = str(request).strip()
        if not request:
            return 'Tell me what code change you want me to propose.'
        terms = request.lower()
        filename = 'agents.py' if re.search(r'\b(?:file|system|app|tool|agent|volume)\b', terms) else 'assistant.py'
        try:
            patch_text = self._make_patch(request, filename)
            source_path, _ = self._parse_and_apply_in_memory(patch_text, filename)
            proposal_id = 'FRI-' + uuid.uuid4().hex[:8].upper()
            updates_dir = self._ensure_local_dir(self.updates_dir)
            proposal_path = self._local_path(os.path.join(updates_dir, proposal_id + '.patch'))
            metadata_path = self._local_path(os.path.join(updates_dir, proposal_id + '.json'))
            patch_bytes = (patch_text.rstrip() + '\n').encode('utf-8')
            with open(proposal_path, 'xb') as patch_file:
                patch_file.write(patch_bytes)
            with open(source_path, 'rb') as source_file:
                source_sha256 = self._sha256(source_file.read())
            metadata = {
                'id': proposal_id, 'file': os.path.basename(source_path), 'status': 'pending',
                'created': datetime.now().isoformat(timespec='seconds'),
                'patch_sha256': self._sha256(patch_bytes), 'source_sha256': source_sha256,
                'request': request[:200],
            }
            with open(metadata_path, 'x', encoding='utf-8', newline='\n') as metadata_file:
                json.dump(metadata, metadata_file, indent=2)
                metadata_file.write('\n')
            self.assistant.logger.info('code proposal created id=%s file=%s', proposal_id, filename)
            print(f'\n--- Friday code proposal {proposal_id} ({filename}) ---\n{patch_text}\n--- End proposal ---\n')
            return (
                f'I drafted update {proposal_id} for {filename}. The diff is printed in the console. '
                f'Review it, then say “apply the latest update” to approve this exact patch.'
            )
        except Exception as error:
            self.assistant.logger.exception('code proposal failed')
            return f'I could not make a safe code proposal: {error}'

    def _proposal_paths(self, proposal_id):
        proposal_id = str(proposal_id).strip().upper()
        if not re.fullmatch(r'FRI-[A-F0-9]{8}', proposal_id):
            raise ValueError('Give me the complete proposal ID, such as FRI-1A2B3C4D.')
        updates_dir = self._local_path(self.updates_dir)
        return (
            self._local_path(os.path.join(updates_dir, proposal_id + '.patch')),
            self._local_path(os.path.join(updates_dir, proposal_id + '.json')),
            proposal_id,
        )

    def _pending_proposals(self):
        """Return pending, unexpired proposal metadata, newest first."""
        proposals = [m for m in self._all_proposals() if m.get('status') == 'pending']
        fresh = []
        for metadata in proposals:
            try:
                age = (datetime.now() - datetime.fromisoformat(metadata['created'])).total_seconds()
            except (ValueError, KeyError, TypeError):
                continue
            if age <= self.PROPOSAL_MAX_AGE_SECONDS:
                fresh.append(metadata)
        return fresh

    def _applied_proposals(self):
        return [m for m in self._all_proposals() if m.get('status') == 'applied']

    def _all_proposals(self):
        try:
            updates_dir = self._local_path(self.updates_dir)
            names = [n for n in os.listdir(updates_dir) if n.endswith('.json')]
        except (OSError, ValueError):
            return []
        proposals = []
        for name in names:
            try:
                with open(self._local_path(os.path.join(updates_dir, name)), 'r', encoding='utf-8') as handle:
                    metadata = json.load(handle)
            except (OSError, ValueError):
                continue
            if isinstance(metadata, dict) and isinstance(metadata.get('created'), str):
                proposals.append(metadata)
        return sorted(proposals, key=lambda item: item['created'], reverse=True)

    @staticmethod
    def spell_id(proposal_id):
        return ' '.join(proposal_id.replace('-', ' ')).replace('   ', ', ')

    def request_apply_latest(self):
        """Voice-friendly approval step: describe the newest pending patch, then wait for 'confirm update'."""
        self.pending_apply = None
        pending = self._pending_proposals()
        if not pending:
            return 'There is no pending code update to apply.'
        latest = pending[0]
        proposal_id = latest.get('id', '')
        try:
            patch_path, _, proposal_id = self._proposal_paths(proposal_id)
            with open(patch_path, 'r', encoding='utf-8') as patch_file:
                patch_lines = patch_file.read().splitlines()
        except Exception as error:
            return f'I could not read the latest update: {error}'
        added = sum(1 for line in patch_lines if line.startswith('+') and not line.startswith('+++'))
        removed = sum(1 for line in patch_lines if line.startswith('-') and not line.startswith('---'))
        self.pending_apply = {
            'id': proposal_id, 'patch_sha256': latest.get('patch_sha256'),
            'expires': time.monotonic() + self.CONFIRM_WINDOW_SECONDS,
        }
        extra = f' There are {len(pending) - 1} older pending updates I will ignore.' if len(pending) > 1 else ''
        return (
            f'Latest update is {self.spell_id(proposal_id)} for {latest.get("file")}: '
            f'{added} lines added and {removed} removed.{extra} '
            'Say “confirm update” to apply it, or “cancel update” to drop it.'
        )

    def confirm_apply(self):
        pending = self.pending_apply
        self.pending_apply = None
        if not pending or time.monotonic() > pending['expires']:
            return 'There is nothing waiting for confirmation.'
        return self.apply_update(pending['id'], expected_patch_sha256=pending.get('patch_sha256'))

    def cancel_apply(self):
        had_pending = self.pending_apply is not None
        self.pending_apply = None
        return 'Okay, I dropped that update request.' if had_pending else 'There is nothing waiting for confirmation.'

    def apply_update(self, proposal_id, expected_patch_sha256=None):
        try:
            if str(proposal_id).strip().lower() in {'latest', 'last', 'newest', 'pending', ''}:
                return self.request_apply_latest()
            patch_path, metadata_path, proposal_id = self._proposal_paths(proposal_id)
            with open(metadata_path, 'r', encoding='utf-8') as metadata_file:
                metadata = json.load(metadata_file)
            if metadata.get('status') != 'pending' or metadata.get('id') != proposal_id:
                return 'That update is not pending approval.'
            filename = metadata.get('file')
            if filename not in self.CODE_TARGETS:
                return 'That update targets a file outside the approved code list.'
            created = datetime.fromisoformat(metadata['created'])
            if (datetime.now() - created).total_seconds() > self.PROPOSAL_MAX_AGE_SECONDS:
                return 'That update has expired. Ask me to propose it again.'
            with open(patch_path, 'rb') as patch_file:
                patch_bytes = patch_file.read()
            patch_sha256 = self._sha256(patch_bytes)
            if (not metadata.get('patch_sha256') or patch_sha256 != metadata['patch_sha256']
                    or (expected_patch_sha256 and patch_sha256 != expected_patch_sha256)):
                return 'That patch changed after it was proposed, so I refused to apply it.'
            patch_text = patch_bytes.decode('utf-8')
            source_path = self._source_path(filename)
            with open(source_path, 'rb') as source_file:
                if self._sha256(source_file.read()) != metadata.get('source_sha256'):
                    return f'{filename} changed since this update was proposed. Ask me to propose it again.'
            source_path, candidate = self._parse_and_apply_in_memory(patch_text, filename)

            backup_dir = self._ensure_local_dir(os.path.join(self.updates_dir, 'backups'))
            backup_path = self._local_path(os.path.join(backup_dir, f'{proposal_id}-{filename}.bak'))
            with open(source_path, 'rb') as source_file:
                original_bytes = source_file.read()
            with open(backup_path, 'xb') as backup_file:
                backup_file.write(original_bytes)
            temp_path = source_path + '.' + proposal_id + '.tmp'
            if os.path.exists(temp_path):
                os.remove(temp_path)
            try:
                with open(temp_path, 'x', encoding='utf-8', newline='\n') as temp_file:
                    temp_file.write(candidate)
                os.replace(temp_path, source_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                os.remove(backup_path)
                raise

            metadata['status'] = 'applied'
            metadata['backup'] = os.path.relpath(backup_path, self.root)
            metadata['applied_sha256'] = self._sha256(candidate.encode('utf-8'))
            try:
                self._write_json_atomic(metadata_path, metadata, proposal_id)
            except Exception:
                restore_path = source_path + '.' + proposal_id + '.restore'
                with open(restore_path, 'xb') as restore_file:
                    restore_file.write(original_bytes)
                os.replace(restore_path, source_path)
                raise
            self.assistant.logger.warning('user approved code update id=%s file=%s', proposal_id, filename)
            return f'Applied update {proposal_id} to {filename}; backup saved. Restart Friday to load the change.'
        except Exception as error:
            self.assistant.logger.exception('approved code update failed')
            return f'I did not apply that update: {error}'

    @staticmethod
    def _sha256(data):
        import hashlib
        return hashlib.sha256(data).hexdigest()

    def rollback_update(self, proposal_id):
        try:
            if str(proposal_id).strip().lower() in {'latest', 'last', 'newest', ''}:
                applied = self._applied_proposals()
                if not applied:
                    return 'There is no applied update to roll back.'
                proposal_id = applied[0]['id']
            _, metadata_path, proposal_id = self._proposal_paths(proposal_id)
            with open(metadata_path, 'r', encoding='utf-8') as metadata_file:
                metadata = json.load(metadata_file)
            if metadata.get('status') != 'applied':
                return 'That update has not been applied.'
            filename = metadata.get('file')
            if filename not in self.CODE_TARGETS:
                return 'That update targets a file outside the approved code list.'
            source_path = self._source_path(filename)
            with open(source_path, 'rb') as source_file:
                current = source_file.read()
            if self._sha256(current) != metadata.get('applied_sha256'):
                return 'That file changed after the update. I left it untouched; restore the backup manually after review.'
            backup_path = self._local_path(os.path.join(self.root, metadata['backup']))
            with open(backup_path, 'rb') as backup_file:
                original = backup_file.read()
            ast.parse(original.decode('utf-8'), filename=filename)
            temp_path = source_path + '.' + proposal_id + '.rollback'
            with open(temp_path, 'xb') as temp_file:
                temp_file.write(original)
            os.replace(temp_path, source_path)
            metadata['status'] = 'rolled_back'
            self._write_json_atomic(metadata_path, metadata, proposal_id + '-rollback')
            self.assistant.logger.warning('user requested rollback id=%s file=%s', proposal_id, filename)
            return f'Rolled back update {proposal_id}. Restart Friday to reload the restored file.'
        except Exception as error:
            self.assistant.logger.exception('code rollback failed')
            return f'I could not roll back that update: {error}'

    def list_updates(self):
        try:
            items = []
            updates_dir = self._local_path(self.updates_dir)
            for name in sorted(os.listdir(updates_dir)):
                if not name.endswith('.json'):
                    continue
                metadata_path = self._local_path(os.path.join(updates_dir, name))
                with open(metadata_path, 'r', encoding='utf-8') as metadata_file:
                    metadata = json.load(metadata_file)
                items.append(f"{metadata.get('id')} ({metadata.get('file')}, {metadata.get('status')})")
        except FileNotFoundError:
            items = []
        except Exception:
            return 'I could not read the update proposal list.'
        return 'Update proposals: ' + '; '.join(items) if items else 'There are no code proposals yet.'
