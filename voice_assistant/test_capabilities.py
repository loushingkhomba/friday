"""Offline tests for Friday's self-knowledge. Run: python -m unittest test_capabilities -v"""

import json
import logging
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from capabilities import CapabilityRegistry
from self_improvement import SelfImprovementAgent


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        folder = os.path.join(self.tmp, "Friday'sFolder")
        os.makedirs(folder)
        self.folder = folder
        self.assistant = SimpleNamespace(
            allowed_folder=folder, offline_mode=True, data={}, save_data=lambda: None,
            logger=logging.getLogger('friday.test'),
            guardrails={'system': {'blocked_apps': ['cmd', 'powershell']}, 'planner': {'allow_system_actions': False}},
        )
        self.assistant.self_improvement = SelfImprovementAgent(self.assistant)
        self.registry = CapabilityRegistry(self.assistant)

    def add_skill(self, name, body):
        skills = os.path.join(self.folder, 'skills')
        os.makedirs(skills, exist_ok=True)
        with open(os.path.join(skills, name + '.md'), 'w', encoding='utf-8') as handle:
            handle.write(body)

    def add_update(self, proposal_id, status, request='speak the weather politely'):
        updates = os.path.join(self.folder, 'updates')
        os.makedirs(updates, exist_ok=True)
        with open(os.path.join(updates, proposal_id + '.json'), 'w', encoding='utf-8') as handle:
            json.dump({'id': proposal_id, 'file': 'assistant.py', 'status': status,
                       'created': '2026-10-06T10:00:00', 'request': request}, handle)

    def test_overview_lists_core_features_and_offline_limits(self):
        text = self.registry.spoken_overview()
        for word in ('reminders', 'notes', 'files', "Friday'sFolder", 'skills'):
            self.assertIn(word, text)
        self.assertIn('internet access is off', text)
        self.assertNotIn('look up weather', text)

    def test_online_features_listed_only_when_network_is_on(self):
        self.assistant.offline_mode = False
        text = self.registry.spoken_overview()
        self.assertIn('look up weather', text)
        self.assertNotIn('internet access is off', text)

    def test_new_skill_is_noticed_without_code_changes(self):
        self.registry.ensure_baseline()
        self.assertEqual(self.registry.changes_since_seen(), {})
        self.add_skill('meal-planning', '# Meal Planning\n\nWhen to use: dinner ideas.\n')
        self.assertIn('Meal Planning', self.registry.spoken_overview())
        self.assertIn('Meal Planning', self.registry.prompt_context())
        self.assertEqual(self.registry.changes_since_seen()['new_skills'], ['Meal Planning'])
        reply = self.registry.whats_new()
        self.assertIn('Meal Planning', reply)
        self.assertIn('nothing has changed', self.registry.whats_new().lower())

    def test_edited_and_removed_skills_are_reported(self):
        self.add_skill('study', '# Study Coach\n\nv1\n')
        self.registry.ensure_baseline()
        self.add_skill('study', '# Study Coach\n\nv2\n')
        self.assertEqual(self.registry.changes_since_seen()['changed_skills'], ['Study Coach'])
        self.registry.mark_seen()
        os.remove(os.path.join(self.folder, 'skills', 'study.md'))
        self.assertEqual(self.registry.changes_since_seen()['removed_skills'], ['study'])

    def test_applied_update_becomes_a_known_ability_and_rollback_removes_it(self):
        self.registry.ensure_baseline()
        self.add_update('FRI-AAAAAAAA', 'applied')
        self.assertIn('speak the weather politely', self.registry.spoken_overview())
        self.assertEqual(self.registry.changes_since_seen()['new_updates'], ['speak the weather politely'])
        self.registry.mark_seen()
        self.add_update('FRI-AAAAAAAA', 'rolled_back')
        self.assertNotIn('speak the weather politely', self.registry.spoken_overview())
        self.assertEqual(len(self.registry.changes_since_seen()['rolled_back']), 1)

    def test_pending_updates_are_not_claimed_as_abilities(self):
        self.add_update('FRI-BBBBBBBB', 'pending', request='teleport')
        self.assertNotIn('teleport', self.registry.spoken_overview())
        self.assertNotIn('teleport', self.registry.prompt_context())

    def test_first_run_has_no_false_changes(self):
        self.add_skill('existing', '# Existing\n')
        self.registry.ensure_baseline()
        self.assertEqual(self.registry.changes_since_seen(), {})

    def test_network_change_is_reported(self):
        self.registry.ensure_baseline()
        self.assistant.offline_mode = False
        self.assertIn('online', self.registry.changes_since_seen())


class CapabilityIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ('speech_recognition', 'pyautogui', 'pystray', 'pygame', 'pygame._sdl2', 'pygame._sdl2.audio'):
            sys.modules.setdefault(name, MagicMock())
        try:
            from assistant import VoiceAssistant
        except Exception as error:
            raise unittest.SkipTest(f'assistant import unavailable: {error}')
        cls.VoiceAssistant = VoiceAssistant

    def intent(self, text):
        stub = SimpleNamespace(logger=logging.getLogger('friday.test'))
        data = self.VoiceAssistant.quick_intent(stub, text)
        return data['intent'] if data else None

    def test_feature_questions(self):
        for phrase in ('What can you do?', 'Friday, what are your features?', 'Can you tell me what you can do',
                       'what are you capable of', 'tell me about your capabilities', 'how can you help me', 'help'):
            with self.subTest(phrase):
                self.assertEqual(self.intent(phrase), 'CAPABILITIES')

    def test_whats_new_questions(self):
        for phrase in ("What's new?", 'what has changed about you', 'what did you learn lately', 'what is new with you'):
            with self.subTest(phrase):
                self.assertEqual(self.intent(phrase), 'WHATS_NEW')

    def test_other_requests_are_not_hijacked(self):
        self.assertNotEqual(self.intent('list my skills'), 'CAPABILITIES')
        self.assertNotEqual(self.intent("what's the news in my city"), 'WHATS_NEW')
        self.assertNotEqual(self.intent('propose a code update to improve your features'), 'CAPABILITIES')
        self.assertNotEqual(self.intent('add a skill for explaining what you can do'), 'CAPABILITIES')


if __name__ == '__main__':
    unittest.main()
