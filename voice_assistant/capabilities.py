"""Friday's live, offline knowledge of its own abilities.

Core abilities are listed once here. Custom skills and applied code updates are read from disk every time,
so anything added later is noticed without editing this file.
"""

import hashlib
import os
import re


class CapabilityRegistry:
    MAX_UPDATES_LISTED = 5

    def __init__(self, assistant):
        self.assistant = assistant

    def _network_on(self):
        return not self.assistant.offline_mode

    def core(self):
        """Return (area, spoken description) pairs that reflect the active policy."""
        assistant = self.assistant
        guardrails = assistant.guardrails
        root = os.path.basename(os.path.normpath(assistant.allowed_folder))
        blocked = guardrails.get('system', {}).get('blocked_apps', [])
        items = [
            ('conversation', 'chat about general topics with local models, follow up for 45 seconds, save daily local conversation logs, and improve command understanding from corrections you approve'),
            ('time', 'tell the time and date'),
            ('reminders', 'set and list reminders by voice'),
            ('notes', 'save notes and ideas, then find or list them later'),
            ('files', f'read, create, add to and search text files, and delete one by name after your spoken confirmation (recoverable from a trash folder; only when guardrails allow it), only inside {root}'),
            ('apps', 'open or close simple apps and change the volume'
                     + (f', except blocked ones like {", ".join(str(a) for a in blocked[:3])}' if blocked else '')),
            ('skills', 'learn new skills when you ask, and propose code updates that need your explicit approval'),
            ('rules', 'explain my guardrails and permissions when asked'),
            ('stop', 'stop speaking when you say stop, wait or cancel'),
        ]
        if self._network_on():
            items.append(('online', 'look up weather, news and web or Wikipedia answers'))
        return items

    def unavailable(self):
        """Things Friday should not claim right now."""
        missing = []
        if not self._network_on():
            missing.append('live weather, news and web lookups, because internet access is off')
        if not self.assistant.guardrails.get('planner', {}).get('allow_system_actions', False):
            missing.append('system actions inside multi-step plans')
        return missing

    def custom_skills(self):
        agent = self.assistant.self_improvement
        skills = []
        try:
            skill_dir = agent._local_path(agent.skills_dir)
            names = sorted(n for n in os.listdir(skill_dir) if n.lower().endswith('.md'))
        except (OSError, ValueError):
            return skills
        for name in names:
            try:
                path = agent._local_path(os.path.join(skill_dir, name))
                with open(path, 'rb') as handle:
                    raw = handle.read(20000)
                text = raw.decode('utf-8', errors='ignore')
            except (OSError, ValueError):
                continue
            heading = re.search(r'^\s*#+\s*(.+?)\s*$', text, flags=re.MULTILINE)
            title = re.sub(r'[*_`]', '', heading.group(1)) if heading else name[:-3].replace('-', ' ')
            skills.append({'name': name[:-3], 'title': title.strip(), 'digest': hashlib.sha256(raw).hexdigest()[:12]})
        return skills

    def applied_updates(self):
        agent = self.assistant.self_improvement
        updates = []
        for metadata in agent._applied_proposals():
            summary = str(metadata.get('request') or '').strip()
            updates.append({
                'id': metadata.get('id', ''), 'file': metadata.get('file', ''),
                'summary': summary or f'update to {metadata.get("file", "my code")}',
            })
        return updates

    def snapshot(self):
        return {
            'skills': {s['name']: s['digest'] for s in self.custom_skills()},
            'updates': sorted(u['id'] for u in self.applied_updates()),
            'online': self._network_on(),
        }

    def mark_seen(self):
        self.assistant.data['capabilities_seen'] = self.snapshot()
        self.assistant.save_data()

    def ensure_baseline(self):
        """First launch: record the current state so nothing is falsely reported as new."""
        if not isinstance(self.assistant.data.get('capabilities_seen'), dict):
            self.mark_seen()

    def changes_since_seen(self):
        seen = self.assistant.data.get('capabilities_seen')
        if not isinstance(seen, dict):
            return {}
        now = self.snapshot()
        old_skills = seen.get('skills', {}) if isinstance(seen.get('skills'), dict) else {}
        old_updates = set(seen.get('updates', [])) if isinstance(seen.get('updates'), list) else set()
        titles = {s['name']: s['title'] for s in self.custom_skills()}
        changes = {
            'new_skills': [titles[n] for n in now['skills'] if n not in old_skills],
            'changed_skills': [titles[n] for n, d in now['skills'].items() if n in old_skills and old_skills[n] != d],
            'removed_skills': [n.replace('-', ' ') for n in old_skills if n not in now['skills']],
            'new_updates': [u['summary'] for u in self.applied_updates() if u['id'] not in old_updates],
            'rolled_back': [i for i in old_updates if i not in now['updates']],
        }
        if seen.get('online') != now['online']:
            changes['online'] = 'internet features are now on' if now['online'] else 'internet features are now off'
        return {key: value for key, value in changes.items() if value}

    def spoken_overview(self):
        parts = [f'I can {description}' for _, description in self.core()]
        text = parts[0] + '. I can also ' + ', '.join(p[len('I can '):] for p in parts[1:-1]) + f', and {parts[-1][len("I can "):]}.'
        skills = self.custom_skills()
        if skills:
            text += ' Custom skills: ' + ', '.join(s['title'] for s in skills) + '.'
        updates = self.applied_updates()[:self.MAX_UPDATES_LISTED]
        if updates:
            text += ' Approved improvements: ' + '; '.join(u['summary'] for u in updates) + '.'
        missing = self.unavailable()
        if missing:
            text += ' Right now I cannot do ' + ' or '.join(missing) + '.'
        return text

    def whats_new(self):
        """Report capability changes since the last time the user asked, then mark them as seen."""
        if not isinstance(self.assistant.data.get('capabilities_seen'), dict):
            self.mark_seen()
            return 'I have no earlier record to compare with, so I will track changes from now on.'
        changes = self.changes_since_seen()
        if not changes:
            return 'Nothing has changed in what I can do since you last asked.'
        parts = []
        if changes.get('new_skills'):
            parts.append('new skills: ' + ', '.join(changes['new_skills']))
        if changes.get('changed_skills'):
            parts.append('updated skills: ' + ', '.join(changes['changed_skills']))
        if changes.get('removed_skills'):
            parts.append('removed skills: ' + ', '.join(changes['removed_skills']))
        if changes.get('new_updates'):
            parts.append('new approved improvements: ' + '; '.join(changes['new_updates']))
        if changes.get('rolled_back'):
            parts.append(f'{len(changes["rolled_back"])} improvement(s) rolled back')
        if changes.get('online'):
            parts.append(changes['online'])
        self.mark_seen()
        return 'Here is what changed: ' + '. '.join(parts) + '.'

    def prompt_context(self):
        """Compact, current capability facts for the chat model so it never invents abilities."""
        lines = ['Your real abilities right now (describe only these when asked about your features):']
        lines.extend(f'- {description}' for _, description in self.core())
        for skill in self.custom_skills():
            lines.append(f'- custom skill: {skill["title"]}')
        for update in self.applied_updates()[:self.MAX_UPDATES_LISTED]:
            lines.append(f'- approved improvement: {update["summary"]}')
        for item in self.unavailable():
            lines.append(f'- unavailable now: {item}')
        return '\n'.join(lines)
