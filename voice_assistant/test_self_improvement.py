"""Offline tests for Friday's self-improvement approval flow. Run: python -m unittest test_self_improvement -v"""

import difflib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from self_improvement import SelfImprovementAgent

SOURCE = (
    'def greet():\n'
    '    return "hi"\n'
    '\n'
    'class VoiceAssistant:\n'
    '    def process_command(self):\n'
    '        return 1\n'
)


class TempAgent(SelfImprovementAgent):
    """Agent whose editable source lives in a temp folder instead of the real code."""

    source_dir = None

    def _source_path(self, filename):
        if filename not in self.CODE_TARGETS:
            raise ValueError('Only assistant.py and agents.py can receive Friday proposals.')
        return os.path.join(self.source_dir, filename)


def make_patch(old, new, filename='assistant.py'):
    return ''.join(difflib.unified_diff(
        old.splitlines(True), new.splitlines(True), f'a/{filename}', f'b/{filename}', n=2
    ))


class SelfImprovementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.friday_folder = os.path.join(self.tmp, 'folder')
        self.source_dir = os.path.join(self.tmp, 'src')
        os.makedirs(self.friday_folder)
        os.makedirs(self.source_dir)
        self.source_path = os.path.join(self.source_dir, 'assistant.py')
        with open(self.source_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(SOURCE)
        logger = logging.getLogger('friday.test')
        logger.addHandler(logging.NullHandler())
        logger.propagate = False
        assistant = SimpleNamespace(allowed_folder=self.friday_folder, logger=logger)
        TempAgent.source_dir = self.source_dir
        self.agent = TempAgent(assistant)

    def read_source(self):
        with open(self.source_path, 'r', encoding='utf-8') as handle:
            return handle.read()

    def propose(self, new_source, request='improve greeting'):
        patch = make_patch(self.read_source(), new_source)
        self.agent._make_patch = lambda req, filename: patch
        reply = self.agent.propose_code(request)
        match = re.search(r'FRI-[A-F0-9]{8}', reply)
        return (match.group(0) if match else None), reply

    def metadata(self, proposal_id):
        path = os.path.join(self.friday_folder, 'updates', proposal_id + '.json')
        with open(path, 'r', encoding='utf-8') as handle:
            return json.load(handle)

    def test_voice_flow_apply_requires_confirmation_then_rolls_back(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hello"'))
        self.assertIsNotNone(proposal_id)
        prompt = self.agent.apply_update('latest')
        self.assertIn('confirm update', prompt)
        self.assertEqual(self.read_source(), SOURCE)
        self.assertIn('Applied update', self.agent.confirm_apply())
        self.assertIn('"hello"', self.read_source())
        self.assertEqual(self.metadata(proposal_id)['status'], 'applied')
        self.assertIn('Rolled back', self.agent.rollback_update('latest'))
        self.assertEqual(self.read_source(), SOURCE)
        self.assertEqual(self.metadata(proposal_id)['status'], 'rolled_back')

    def test_exact_id_applies_directly_and_cannot_apply_twice(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hey"'))
        self.assertIn('Applied update', self.agent.apply_update(proposal_id))
        self.assertIn('not pending', self.agent.apply_update(proposal_id))

    def test_confirm_without_request_does_nothing(self):
        self.propose(SOURCE.replace('"hi"', '"hey"'))
        self.assertIn('nothing waiting', self.agent.confirm_apply())
        self.assertEqual(self.read_source(), SOURCE)

    def test_cancel_drops_pending_confirmation(self):
        self.propose(SOURCE.replace('"hi"', '"hey"'))
        self.agent.apply_update('latest')
        self.assertIn('dropped', self.agent.cancel_apply())
        self.assertIn('nothing waiting', self.agent.confirm_apply())
        self.assertEqual(self.read_source(), SOURCE)

    def test_confirmation_expires(self):
        self.propose(SOURCE.replace('"hi"', '"hey"'))
        self.agent.apply_update('latest')
        self.agent.pending_apply['expires'] = 0
        self.assertIn('nothing waiting', self.agent.confirm_apply())
        self.assertEqual(self.read_source(), SOURCE)

    def test_latest_ignores_older_pending_proposals(self):
        self.propose(SOURCE.replace('"hi"', '"old"'))
        newer_id, _ = self.propose(SOURCE.replace('"hi"', '"new"'))
        old_meta = [m for m in self.agent._pending_proposals() if m['id'] != newer_id][0]
        old_meta['created'] = '2000-01-01T00:00:00'
        path = os.path.join(self.friday_folder, 'updates', old_meta['id'] + '.json')
        with open(path, 'w', encoding='utf-8') as handle:
            json.dump(old_meta, handle)
        self.assertEqual([m['id'] for m in self.agent._pending_proposals()], [newer_id])
        self.agent.apply_update('latest')
        self.assertIn(newer_id.replace('-', ' ')[:5], self.agent.pending_apply['id'].replace('-', ' '))
        self.assertEqual(self.agent.pending_apply['id'], newer_id)

    def test_tampered_patch_is_refused(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hey"'))
        patch_path = os.path.join(self.friday_folder, 'updates', proposal_id + '.patch')
        with open(patch_path, 'r', encoding='utf-8') as handle:
            text = handle.read()
        with open(patch_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text.replace('hey', 'evil'))
        self.assertIn('changed after it was proposed', self.agent.apply_update(proposal_id))
        self.assertEqual(self.read_source(), SOURCE)

    def test_patch_swapped_after_confirmation_prompt_is_refused(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hey"'))
        self.agent.apply_update('latest')
        patch_path = os.path.join(self.friday_folder, 'updates', proposal_id + '.patch')
        with open(patch_path, 'a', encoding='utf-8', newline='\n') as handle:
            handle.write('\n')
        self.assertIn('changed after it was proposed', self.agent.confirm_apply())
        self.assertEqual(self.read_source(), SOURCE)

    def test_source_changed_since_proposal_is_refused(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hey"'))
        with open(self.source_path, 'a', encoding='utf-8', newline='\n') as handle:
            handle.write('# manual edit\n')
        self.assertIn('changed since', self.agent.apply_update(proposal_id))
        self.assertNotIn('"hey"', self.read_source())

    def test_expired_proposal_is_refused(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hey"'))
        meta = self.metadata(proposal_id)
        meta['created'] = '2000-01-01T00:00:00'
        with open(os.path.join(self.friday_folder, 'updates', proposal_id + '.json'), 'w', encoding='utf-8') as handle:
            json.dump(meta, handle)
        self.assertIn('expired', self.agent.apply_update(proposal_id))

    def test_protected_symbol_change_is_refused_at_proposal(self):
        proposal_id, reply = self.propose(SOURCE.replace('return 1', 'return 2'))
        self.assertIsNone(proposal_id)
        self.assertIn('protected', reply)

    def test_new_blocked_code_is_refused(self):
        cases = {
            'network import': 'import socket\n' + SOURCE,
            'subprocess call': SOURCE.replace('return "hi"', 'import subprocess\n    subprocess.run(["cmd"])\n    return "hi"'),
            'eval': SOURCE.replace('return "hi"', 'return eval("1")'),
            'os.system': SOURCE.replace('return "hi"', 'import os\n    os.system("dir")\n    return "hi"'),
            'guardrail edit': SOURCE.replace('return "hi"', 'open("guardrails.json", "w")\n    return "hi"'),
        }
        for name, new_source in cases.items():
            with self.subTest(name):
                proposal_id, reply = self.propose(new_source)
                self.assertIsNone(proposal_id, reply)
                self.assertIn('blocked code', reply)
        self.assertEqual(self.read_source(), SOURCE)

    def test_existing_blocked_constructs_do_not_block_unrelated_patch(self):
        with open(self.source_path, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write('import subprocess\n' + SOURCE)
        before = self.read_source()
        proposal_id, _ = self.propose(before.replace('"hi"', '"hey"'))
        self.assertIsNotNone(proposal_id)

    def test_syntax_error_patch_is_refused(self):
        proposal_id, reply = self.propose(SOURCE.replace('return "hi"', 'return ('))
        self.assertIsNone(proposal_id)
        self.assertIn('could not make a safe code proposal', reply)

    def test_non_allowlisted_target_is_refused(self):
        patch = make_patch(SOURCE, SOURCE.replace('"hi"', '"hey"'), filename='guardrails.json')
        self.agent._make_patch = lambda req, filename: patch
        proposal_id = re.search(r'FRI-[A-F0-9]{8}', self.agent.propose_code('improve greeting') or '')
        self.assertIsNone(proposal_id)

    def test_invalid_ids_are_refused(self):
        for bad in ['FRI-123', 'FRI-ZZZZZZZZ', '../../x', 'FRI-12345678']:
            with self.subTest(bad):
                self.assertIn('did not apply', self.agent.apply_update(bad))

    def test_no_pending_update_message(self):
        self.assertIn('no pending', self.agent.apply_update('latest'))
        self.assertIn('no applied', self.agent.rollback_update('latest'))

    def test_rollback_refused_when_file_changed_after_update(self):
        proposal_id, _ = self.propose(SOURCE.replace('"hi"', '"hey"'))
        self.agent.apply_update(proposal_id)
        with open(self.source_path, 'a', encoding='utf-8', newline='\n') as handle:
            handle.write('# later edit\n')
        reply = self.agent.rollback_update(proposal_id)
        self.assertIn('changed after the update', reply)
        self.assertIn('later edit', self.read_source())

    def test_spoken_id_is_spelled_out(self):
        self.assertEqual(self.agent.spell_id('FRI-1A2B3C4D'), 'F R I, 1 A 2 B 3 C 4 D')


class SpokenCommandTests(unittest.TestCase):
    """Check voice transcripts map to the right self-improvement intents."""

    @classmethod
    def setUpClass(cls):
        for name in ('speech_recognition', 'pyautogui', 'pystray', 'pygame', 'pygame._sdl2', 'pygame._sdl2.audio'):
            sys.modules.setdefault(name, MagicMock())
        try:
            from assistant import VoiceAssistant
        except Exception as error:  # heavy optional runtime dependencies missing
            raise unittest.SkipTest(f'assistant import unavailable: {error}')
        cls.VoiceAssistant = VoiceAssistant

    def intent(self, text):
        stub = SimpleNamespace(logger=logging.getLogger('friday.test'))
        return self.VoiceAssistant.quick_intent(stub, text)

    def test_apply_latest_and_confirm_phrases(self):
        self.assertEqual(self.intent('Friday, apply the latest update')['intent'], 'CODE_APPLY')
        self.assertEqual(self.intent('apply update')['params'], 'latest')
        self.assertEqual(self.intent('confirm update')['intent'], 'CODE_CONFIRM')
        self.assertEqual(self.intent('yes, confirm update')['intent'], 'CODE_CONFIRM')
        self.assertEqual(self.intent('cancel update')['intent'], 'CODE_CANCEL')
        self.assertEqual(self.intent('roll back the latest update')['params'], 'latest')

    def test_spoken_ids_with_spaces_are_normalised(self):
        for phrase in ('apply update FRI-1A2B3C4D', 'apply update fri 1 a 2 b 3 c 4 d', 'apply update F R I 1A2B3C4D'):
            with self.subTest(phrase):
                data = self.intent(phrase)
                self.assertEqual((data['intent'], data['params']), ('CODE_APPLY', 'FRI-1A2B3C4D'))
        self.assertEqual(self.intent('roll back update fri 1a2b3c4d')['params'], 'FRI-1A2B3C4D')

    def test_plain_bare_confirmation_words_do_not_apply(self):
        for phrase in ('yes', 'okay', 'confirm', 'apply'):
            with self.subTest(phrase):
                self.assertNotIn(self.intent(phrase)['intent'] if self.intent(phrase) else '',
                                 {'CODE_APPLY', 'CODE_CONFIRM'})


if __name__ == '__main__':
    unittest.main()
