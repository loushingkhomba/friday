"""Offline tests for spoken file creation. Run: python -m unittest test_file_intents -v"""

import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

from agents import SystemAgent
from file_intents import is_folder_location_question, parse_create_file, spoken_folder_location


class ParseTests(unittest.TestCase):
    def test_phrases_from_real_session(self):
        cases = {
            "okay, so now let's create a file in the friday's folder with ideas.": 'ideas.txt',
            'no, discard everything, just create a blank file with ideas as the file name.': 'ideas.txt',
            'OK, now create me a file, a text file, with blank, name is Idea.': 'Idea.txt',
            'create a text file named Shopping List': 'Shopping List.txt',
            'create a file called plan.md in friday folder': 'plan.md',
            'make a new file in Friday folder named Todo': 'Todo.txt',
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase):
                result = parse_create_file(phrase)
                self.assertIsNotNone(result)
                self.assertEqual(result[0], expected)

    def test_content_is_split_out(self):
        name, content = parse_create_file('create a file named hello with content good morning')
        self.assertEqual((name, content), ('hello.txt', 'good morning'))

    def test_missing_name_returns_empty_name(self):
        self.assertEqual(parse_create_file('create a file in the friday folder'), ('', ''))
        self.assertEqual(parse_create_file('create a new blank text file'), ('', ''))

    def test_unrelated_requests_ignored(self):
        for phrase in ('add a skill for creating a file', 'read the file notes.txt', 'what time is it',
                       'propose a code update to create files', 'take a note'):
            with self.subTest(phrase):
                self.assertIsNone(parse_create_file(phrase))

    def test_unsafe_characters_removed(self):
        name = parse_create_file('create a file named a<b>c|d')[0]
        self.assertNotRegex(name, r'[<>|]')

    def test_folder_questions(self):
        for phrase in ("can you tell me where is that friday's folder", 'where is your folder',
                       'what is the path of the folder'):
            with self.subTest(phrase):
                self.assertTrue(is_folder_location_question(phrase))
        self.assertFalse(is_folder_location_question('create a file in the folder'))

    def test_spoken_location_has_full_path(self):
        text = spoken_folder_location(r"C:\Users\x\Desktop\proj\Friday'sFolder")
        self.assertIn("Friday'sFolder", text)
        self.assertIn(r"C:\Users\x\Desktop\proj\Friday'sFolder", text)


class EndToEndTests(unittest.TestCase):
    def test_phrase_creates_real_file_through_system_agent(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        assistant = SimpleNamespace(allowed_folder=root, guardrails={'filesystem': {'allow_overwrite': False}},
                                    logger=SimpleNamespace(info=lambda *a, **k: None))
        agent = SystemAgent(assistant)
        name, content = parse_create_file('create a blank file with ideas as the file name')
        reply = agent.execute(f'write file {name} content {content}')
        self.assertTrue(os.path.isfile(os.path.join(root, 'ideas.txt')), reply)
        self.assertIn('already exists', agent.execute(f'write file {name} content {content}'))


if __name__ == '__main__':
    unittest.main()


class AppendTests(unittest.TestCase):
    def test_append_phrases(self):
        from file_intents import parse_append_file
        cases = [
            ('add buy milk to the file ideas', None, ('ideas.txt', 'buy milk')),
            ('write the content hello world in the file notes.md', None, ('notes.md', 'hello world')),
            ('add this to the file: remember the meeting', 'ideas.txt', ('ideas.txt', 'remember the meeting')),
            ('add call mom to it', 'ideas.txt', ('ideas.txt', 'call mom')),
            ('put test content in the file', 'ideas.txt', ('ideas.txt', 'test content')),
            ('add to the file ideas saying launch plan', None, ('ideas.txt', 'launch plan')),
            ('append hello into notes.txt', None, ('notes.txt', 'hello')),
        ]
        for phrase, last, expected in cases:
            with self.subTest(phrase):
                self.assertEqual(parse_append_file(phrase, last), expected)

    def test_not_hijacked(self):
        from file_intents import parse_append_file
        for phrase in ('add a skill for cooking', 'add milk to my shopping list', 'write a reminder to it',
                       'add call mom to it', 'what time is it'):
            with self.subTest(phrase):
                self.assertIsNone(parse_append_file(phrase, None))

    def test_append_through_agent(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        assistant = SimpleNamespace(allowed_folder=root, guardrails={'filesystem': {}},
                                    logger=SimpleNamespace(info=lambda *a, **k: None))
        agent = SystemAgent(assistant)
        self.assertIn("can't find", agent.execute('append file a.txt content x'))
        agent.execute('write file a.txt content first')
        self.assertEqual(assistant.last_file, 'a.txt')
        agent.execute('append file a.txt content second line')
        with open(os.path.join(root, 'a.txt'), encoding='utf-8') as handle:
            self.assertEqual(handle.read(), 'first\nsecond line\n')
        self.assertIn('What should I add', agent.execute('append file a.txt content'))


class HonestyTests(unittest.TestCase):
    def test_real_session_phrases_route_to_tools(self):
        import logging
        import sys
        from unittest.mock import MagicMock
        for name in ('speech_recognition', 'pyautogui', 'pystray', 'pygame', 'pygame._sdl2', 'pygame._sdl2.audio'):
            sys.modules.setdefault(name, MagicMock())
        try:
            from assistant import VoiceAssistant
        except Exception as error:
            self.skipTest(str(error))
        stub = SimpleNamespace(logger=logging.getLogger('t'), last_file=None)
        cases = {
            "Can you delete the IDR.txt file in Friday's folder?": ('FILE_DELETE', 'IDR.txt'),
            'But I still can see. Can you scan the folder again?': ('FILE_LIST', ''),
            'what files are in the folder': ('FILE_LIST', ''),
            'list the files': ('FILE_LIST', ''),
            'please delete a file for me': ('FILE_DELETE', ''),
        }
        for phrase, (intent, params) in cases.items():
            with self.subTest(phrase):
                result = VoiceAssistant.quick_intent(stub, phrase)
                self.assertEqual(result['intent'], intent)
                self.assertEqual(result['params'], params)
        self.assertIsNone(VoiceAssistant.quick_intent(stub, 'rename the file ideas to plans'))
        for phrase in ('how do I delete files in windows', 'what is a file system', 'tell me a joke'):
            with self.subTest(phrase):
                result = VoiceAssistant.quick_intent(stub, phrase)
                self.assertNotIn(result and result['intent'], ('FILE_HELP', 'FILE_LIST', 'FILE_DELETE'))

    def test_list_reports_real_contents(self):
        from file_intents import list_files_reply
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self.assertIn('empty', list_files_reply(root))
        open(os.path.join(root, 'idea.txt'), 'w').close()
        os.makedirs(os.path.join(root, '.trash'))
        reply = list_files_reply(root)
        self.assertIn('idea.txt', reply)
        self.assertNotIn('trash', reply)

    def test_fake_claims_are_flagged(self):
        from file_intents import claims_unverified_file_action as claim
        self.assertTrue(claim("I've deleted the idea.txt file in Friday's folder."))
        self.assertTrue(claim("I've checked the folder again. IDR.txt is no longer there."))
        self.assertTrue(claim("I've scanned Friday's folder again. I don't see idea.txt."))
        self.assertFalse(claim('Paris is the capital of France.'))
        self.assertFalse(claim("I've checked the weather for you.", 'weather'))

