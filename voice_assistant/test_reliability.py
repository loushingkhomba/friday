"""Offline tests for accuracy helpers. Run: python -m unittest test_reliability -v"""

import logging
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from reliability import (HONESTY_RULES, TEMPERATURE, claims_unverified_action, classify_task,
                         grounded_context)


class ClassifyTests(unittest.TestCase):
    def test_types(self):
        cases = {
            'thanks': 'casual', 'how are you': 'casual', 'tell me a joke': 'casual', 'okay cool': 'casual',
            'who invented the telephone': 'factual', 'what is the capital of Australia': 'factual',
            'how many moons does Mars have': 'factual', 'explain photosynthesis': 'factual',
            'when did the second world war end': 'factual',
            'compare electric and petrol cars and give pros and cons': 'reasoning',
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase):
                self.assertEqual(classify_task(phrase), expected)

    def test_temperatures_ordered(self):
        self.assertLess(TEMPERATURE['factual'], TEMPERATURE['casual'])

    def test_prompt_rules_present(self):
        self.assertIn('not sure', HONESTY_RULES)
        self.assertIn('offline', HONESTY_RULES)


class ClaimTests(unittest.TestCase):
    def test_false_claims_blocked(self):
        for reply, user in (
            ("I've set a reminder for 5 pm.", 'remind me'),
            ("Done, I've saved your note.", 'take a note'),
            ("I opened Notepad for you.", 'open notepad'),
            ("I've turned the volume up.", 'louder'),
            ("Your reminder is set.", ''),
            ("I've added that skill for you.", 'add a skill'),
            ("Okay, I just muted the volume.", ''),
        ):
            with self.subTest(reply):
                self.assertTrue(claims_unverified_action(reply, user))

    def test_honest_replies_allowed(self):
        for reply, user in (
            ('Paris is the capital of France.', 'capital of france'),
            ("I can't set reminders from here, but you can say: remind me.", ''),
            ('Reminders usually work best with a clear time.', 'reminders tips'),
            ("I've heard that before. The note is about photosynthesis.", ''),
            ('The weather in spring is mild.', ''),
        ):
            with self.subTest(reply):
                self.assertFalse(claims_unverified_action(reply, user))

    def test_grounded_context(self):
        self.assertIn('No saved notes', grounded_context('Sam', 'Pune', ''))
        self.assertIn('buy milk', grounded_context('Sam', 'Pune', "['buy milk']"))


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name in ('speech_recognition', 'pyautogui', 'pystray', 'pygame', 'pygame._sdl2', 'pygame._sdl2.audio'):
            sys.modules.setdefault(name, MagicMock())
        try:
            from assistant import VoiceAssistant
        except Exception as error:
            raise unittest.SkipTest(str(error))
        cls.cls = VoiceAssistant

    def stub(self, ram_gb=16):
        import assistant as module
        self._orig = module.psutil
        module.psutil = SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=ram_gb * 1024 ** 3))
        self.addCleanup(setattr, module, 'psutil', self._orig)
        stub = SimpleNamespace(
            model_override='', routing_mode='heuristic', fast_model_name='fast', reasoning_model_name='mid',
            deep_model_name='deep', last_chat_model=None, last_chat_time=0.0, logger=logging.getLogger('t'))
        stub.select_deep_model = lambda reason: ('deep', reason)
        return stub

    def pick(self, message, ram_gb=16):
        stub = self.stub(ram_gb)
        return self.cls.select_chat_model(stub, message)[0]

    def test_work_is_divided_across_models(self):
        self.assertEqual(self.pick('thanks'), 'fast')
        self.assertEqual(self.pick('how are you'), 'fast')
        self.assertEqual(self.pick('who invented the telephone'), 'mid')
        self.assertEqual(self.pick('what is the capital of Australia'), 'mid')
        self.assertEqual(self.pick('give me a deep research comprehensive analysis of battery chemistry'), 'deep')

    def test_low_ram_keeps_facts_on_fast_model(self):
        self.assertEqual(self.pick('who invented the telephone', ram_gb=2), 'fast')


if __name__ == '__main__':
    unittest.main()
