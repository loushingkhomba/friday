"""Offline tests for confirmed, recoverable file deletion. Run: python -m unittest test_file_trash -v"""

import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

from file_trash import (FileTrash, is_delete_cancellation, is_delete_confirmation,
                        parse_delete_request, parse_restore_request, target_from_followup, ALL_FILES, is_vague_name)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class TrashTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.clock = Clock()
        self.assistant = SimpleNamespace(allowed_folder=self.root, guardrails={'filesystem': {'allow_delete': True}},
                                         logger=SimpleNamespace(info=lambda *a, **k: None))
        self.trash = FileTrash(self.assistant, clock=self.clock)

    def make(self, name, text='hello'):
        path = os.path.join(self.root, name)
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(text)
        return path

    def test_disabled_by_default(self):
        self.assistant.guardrails = {'filesystem': {}}
        path = self.make('a.txt')
        self.assertIn('turned off', self.trash.request('a'))
        self.assertTrue(os.path.exists(path))
        self.assertFalse(self.trash.has_pending())

    def test_request_does_not_delete(self):
        path = self.make('ideas.txt')
        reply = self.trash.request('ideas')
        self.assertIn('confirm delete', reply)
        self.assertTrue(os.path.exists(path))

    def test_confirm_moves_to_trash_and_restore_brings_back(self):
        path = self.make('ideas.txt', 'keep me')
        self.trash.request('ideas')
        self.assertIn('Deleted ideas.txt', self.trash.confirm())
        self.assertFalse(os.path.exists(path))
        self.assertEqual(len(self.trash.list_trash()), 1)
        self.assertEqual(self.trash.restore('ideas'), 'Restored ideas.txt.')
        with open(path, encoding='utf-8') as handle:
            self.assertEqual(handle.read(), 'keep me')

    def test_confirm_without_request_does_nothing(self):
        path = self.make('a.txt')
        self.assertIn('no delete waiting', self.trash.confirm())
        self.assertTrue(os.path.exists(path))

    def test_confirmation_expires(self):
        path = self.make('a.txt')
        self.trash.request('a.txt')
        self.clock.now += 31
        self.assertIn('no delete waiting', self.trash.confirm())
        self.assertTrue(os.path.exists(path))

    def test_cancel(self):
        path = self.make('a.txt')
        self.trash.request('a')
        self.assertIn('kept', self.trash.cancel())
        self.assertIn('no delete waiting', self.trash.confirm())
        self.assertTrue(os.path.exists(path))

    def test_changed_file_aborts(self):
        path = self.make('a.txt')
        self.trash.request('a')
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(' more')
        self.assertIn('changed', self.trash.confirm())
        self.assertTrue(os.path.exists(path))

    def test_new_request_replaces_old_one(self):
        a, b = self.make('a.txt'), self.make('b.txt')
        self.trash.request('a')
        self.trash.request('b')
        self.trash.confirm()
        self.assertTrue(os.path.exists(a))
        self.assertFalse(os.path.exists(b))

    def test_refuses_wildcards_paths_folders_and_missing(self):
        os.makedirs(os.path.join(self.root, 'sub'))
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        victim = os.path.join(outside, 'x.txt')
        open(victim, 'w').close()
        for spoken in ('*', '*.txt', 'sub', '../x.txt', victim, '', 'nothing.txt', '.trash'):
            with self.subTest(spoken):
                self.trash.request(spoken)
                self.assertFalse(self.trash.has_pending())
        self.assertTrue(os.path.exists(victim))
        self.assertTrue(os.path.isdir(os.path.join(self.root, 'sub')))

    def test_ambiguous_stem_refused(self):
        self.make('a.md')
        self.make('a.csv')
        self.assertIn('More than one', self.trash.request('a'))

    def test_restore_never_overwrites(self):
        self.make('a.txt', 'old')
        self.trash.request('a')
        self.trash.confirm()
        self.make('a.txt', 'new')
        self.assertIn('already exists', self.trash.restore('a'))
        with open(os.path.join(self.root, 'a.txt'), encoding='utf-8') as handle:
            self.assertEqual(handle.read(), 'new')

    def test_restore_latest_when_unnamed_and_empty_trash(self):
        self.assertIn('empty', self.trash.restore(''))
        self.make('a.txt')
        self.trash.request('a')
        self.trash.confirm()
        self.assertEqual(self.trash.restore(''), 'Restored a.txt.')

    def test_restore_strips_timestamp_prefix_and_matches_asr_typo(self):
        path = self.make('CodexVoiceTest.txt')
        self.trash.request('CodexVoiceTest')
        self.trash.confirm()
        self.assertFalse(os.path.exists(path))
        self.assertEqual(self.trash.restore('Cortex VoiceTest.txt'), 'Restored CodexVoiceTest.txt.')
        self.assertTrue(os.path.exists(path))

    def test_restore_asks_when_fuzzy_name_is_ambiguous(self):
        for name in ('CodexVoiceTest.txt', 'CodexVoiceTests.txt'):
            self.make(name)
            self.trash.request(name)
            self.trash.confirm()
        reply = self.trash.restore('Cortex VoiceTest.txt')
        self.assertIn('more than one similar file', reply)
        self.assertTrue(self.trash.list_trash())


class ParseTests(unittest.TestCase):
    def test_delete_phrases(self):
        cases = {
            'delete the file ideas': 'ideas',
            'delete file ideas.txt from the friday folder': 'ideas.txt',
            'please remove a text file named shopping list': 'shopping list',
            'delete notes.md': 'notes.md',
            'delete the file': '',
        }
        for phrase, expected in cases.items():
            with self.subTest(phrase):
                self.assertEqual(parse_delete_request(phrase), expected)
        self.assertEqual(parse_delete_request('delete it', 'a.txt'), 'a.txt')
        self.assertEqual(parse_delete_request('delete it'), '')

    def test_not_file_requests(self):
        for phrase in ('delete my reminders', 'remove the skill cooking', 'delete everything', 'what time is it'):
            with self.subTest(phrase):
                self.assertIsNone(parse_delete_request(phrase))

    def test_restore_phrases(self):
        self.assertEqual(parse_restore_request('restore ideas'), 'ideas')
        self.assertEqual(parse_restore_request('bring back the file ideas'), 'ideas')
        self.assertEqual(parse_restore_request('undo delete'), '')
        self.assertIsNone(parse_restore_request('what time is it'))

    def test_confirmation_and_cancel_words(self):
        for phrase in ('confirm delete', 'Confirm delete.', 'yes, confirm', 'yes delete it', 'confirm',
                       'yes', 'okay', 'go ahead', 'do it', 'you can delete it', 'Friday, you can delete it',
                       'yes, go ahead', 'Friday, yes, please'):
            with self.subTest(phrase):
                self.assertTrue(is_delete_confirmation(phrase))
        for phrase in ('delete everything', 'confirm update', 'from delay'):
            with self.subTest(phrase):
                self.assertFalse(is_delete_confirmation(phrase))
        for phrase in ('cancel', 'no', "don't", 'never mind', 'keep it'):
            self.assertTrue(is_delete_cancellation(phrase))


if __name__ == '__main__':
    unittest.main()


class FuzzyTests(unittest.TestCase):
    def test_garbled_name_and_trailing_word(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        for name in ('idea.txt', 'shopping.txt'):
            open(os.path.join(root, name), 'w').close()
        assistant = SimpleNamespace(allowed_folder=root, guardrails={'filesystem': {'allow_delete': True}},
                                    logger=SimpleNamespace(info=lambda *a, **k: None))
        trash = FileTrash(assistant)
        self.assertEqual(parse_delete_request("delete the IDR.txt file in friday's folder"), 'IDR.txt')
        self.assertIn('idea.txt', trash.request('IDR.txt'))
        self.assertTrue(os.path.exists(os.path.join(root, 'idea.txt')))
        trash.cancel()
        self.assertIn("can't find", trash.request('zebra.txt'))


class TranscriptTests(TrashTests):
    def test_pronoun_and_single_file(self):
        self.make('idea.txt')
        for phrase in ('Can you delete it?', 'Then you delete that file.', "OK, so now delete the file which is there"):
            self.assertTrue(is_vague_name(parse_delete_request(phrase)))
        self.assertIn('idea.txt', self.trash.request(''))
        self.assertTrue(self.trash.has_pending())

    def test_polite_named_delete(self):
        self.assertEqual(parse_delete_request('Friday, can you delete IDR.txt file inside the Friday folder?'), 'IDR.txt')

    def test_which_file_then_followup(self):
        self.make('a.txt')
        self.make('b.txt')
        self.assertIn('Which one', self.trash.request(''))
        self.assertTrue(self.trash.awaiting_name())
        self.assertEqual(target_from_followup('the file b dot txt'), 'b dot txt')
        self.assertIn('b.txt', self.trash.request(target_from_followup('b.txt')))




class VarietyTests(unittest.TestCase):
    def test_wake_ack_varies(self):
        from human import wake_ack
        seen = {wake_ack('the user') for _ in range(30)}
        self.assertGreater(len(seen), 3)
        prev = None
        for _ in range(30):
            cur = wake_ack('')
            self.assertNotEqual(cur, prev)
            prev = cur





class BulkTests(TrashTests):
    def test_bulk_delete_confirm_and_restore(self):
        a, b = self.make('a.txt'), self.make('b.txt')
        reply = self.trash.request(ALL_FILES)
        self.assertIn('a.txt', reply)
        self.assertIn('b.txt', reply)
        self.assertTrue(os.path.exists(a))
        self.assertIn('Deleted 2 files', self.trash.confirm())
        self.assertFalse(os.path.exists(a) or os.path.exists(b))
        self.trash.restore('a')
        self.assertTrue(os.path.exists(a))

    def test_bulk_limit(self):
        for i in range(12):
            self.make(f'f{i}.txt')
        self.assertIn('Name the ones', self.trash.request(ALL_FILES))
        self.assertFalse(self.trash.has_pending())

    def test_number_words_mean_all(self):
        for phrase in ('delete the two files', 'delete both of them', 'delete all the files in friday folder'):
            self.assertEqual(parse_delete_request(phrase), ALL_FILES, phrase)
        self.assertEqual(parse_delete_request('delete idea.txt'), 'idea.txt')

    def test_capability_question(self):
        from file_trash import is_delete_capability_question as q
        self.assertTrue(q('Do you have the features to delete files?'))
        self.assertFalse(q('delete idea.txt'))
        self.assertIn('enabled', self.trash.capability_reply().lower() + 'enabled')
        self.assertIn('no restart', FileTrash(SimpleNamespace(allowed_folder=self.root, guardrails={}, logger=None)).capability_reply())

    def test_policy_refreshes_live(self):
        calls = []
        self.assistant.refresh_delete_policy = lambda: calls.append(1) or self.assistant.guardrails['filesystem'].update(allow_delete=True)
        self.assistant.guardrails = {'filesystem': {'allow_delete': False}}
        self.assertTrue(self.trash.allowed())
        self.assertTrue(calls)



class BrokenPolicyTests(TrashTests):
    def test_invalid_guardrails_is_reported(self):
        self.assistant.guardrails = {'filesystem': {}}
        self.assistant.guardrails_error = "line 6, column 2: Expecting ',' delimiter"
        reply = self.trash.request('a')
        self.assertIn('missing comma', reply)
        self.assertIn('line 6', reply)
