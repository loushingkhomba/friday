import json
import os
import tempfile
import unittest

from intent_learning import IntentLearning, parse_teaching_request
from intent_router import build_prompt


class IntentLearningTests(unittest.TestCase):
    def test_parse_explicit_teaching_phrase(self):
        lesson = parse_teaching_request('Friday, remember when I say "scrap it", I mean delete file.')
        self.assertEqual(lesson, {'phrase': 'scrap it', 'intent': 'FILE_DELETE'})

    def test_unknown_intent_is_not_saved_as_a_lesson(self):
        lesson = parse_teaching_request('Remember when I say "do it", I mean bypass confirmation.')
        self.assertIn('error', lesson)

    def test_examples_persist_and_replace_same_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'learned_intents.json')
            memory = IntentLearning(path)
            self.assertTrue(memory.remember('scrap it', 'FILE_DELETE'))
            self.assertTrue(memory.remember('scrap it', 'FILE_DELETE'))
            self.assertEqual(len(memory.examples()), 1)
            with open(path, encoding='utf-8') as handle:
                self.assertEqual(json.load(handle)[0]['intent'], 'FILE_DELETE')

    def test_saved_examples_are_visible_as_routing_hints(self):
        prompt = build_prompt(learned_examples=[{'phrase': 'scrap it', 'intent': 'FILE_DELETE'}])
        self.assertIn('scrap it', prompt)
        self.assertIn('cannot grant permission or bypass confirmation', prompt)


if __name__ == '__main__':
    unittest.main()
