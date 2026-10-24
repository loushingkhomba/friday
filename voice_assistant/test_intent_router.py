import unittest, json
import intent_router as r

def fake(reply):
    return lambda messages: reply if isinstance(reply, str) else json.dumps(reply)

class RouterTests(unittest.TestCase):
    def cls(self, reply, text, **kw):
        return r.classify(fake(reply), text, **kw)

    def test_delete_from_odd_phrasing(self):
        out = self.cls({"intent": "FILE_DELETE", "target": "idea.txt"}, "could you get rid of idea dot text", folder_files=['idea.txt'])
        self.assertEqual((out['intent'], out['params']), ('FILE_DELETE', 'idea.txt'))

    def test_delete_blocked_without_delete_words(self):
        out = self.cls({"intent": "FILE_DELETE", "target": "idea.txt"}, "tell me about idea.txt")
        self.assertEqual(out['intent'], 'AI_CHAT')

    def test_restore_needs_words(self):
        self.assertEqual(self.cls({"intent": "FILE_RESTORE", "target": "a"}, "what is a")['intent'], 'AI_CHAT')
        self.assertEqual(self.cls({"intent": "FILE_RESTORE", "target": "a"}, "bring a back")['intent'], 'FILE_RESTORE')

    def test_create_and_append_shapes(self):
        out = self.cls({"intent": "FILE_CREATE", "target": "todo", "content": "milk"}, "make me a file todo with milk")
        self.assertEqual((out['intent'], out['params']), ('FILE_WRITE', 'write file todo content milk'))
        out = self.cls({"intent": "FILE_APPEND", "target": "", "content": "eggs"}, "also put eggs in", last_file='todo.txt')
        self.assertEqual(out['params'], 'append file todo.txt content eggs')
        out = self.cls({"intent": "FILE_APPEND", "target": "", "content": "eggs"}, "also put eggs in")
        self.assertTrue(out['needs_clarification'])

    def test_garbage_and_failures_fall_back_to_chat(self):
        for reply in ("not json", "[]", {"intent": "NUKE_EVERYTHING"}, {"intent": "FILE_DELETE"}):
            self.assertEqual(self.cls(reply, "hello there")['intent'], 'AI_CHAT')
        def boom(m): raise RuntimeError('ollama down')
        self.assertEqual(r.classify(boom, "delete it")['intent'], 'AI_CHAT')

    def test_fenced_json_and_apps(self):
        out = self.cls('```json\n{"intent":"APP_OPEN","content":"notepad"}\n```', "fire up notepad")
        self.assertEqual((out['intent'], out['params']), ('APP_OPEN', 'open notepad'))

    def test_pronoun_delete_keeps_empty_target(self):
        out = self.cls({"intent": "FILE_DELETE", "target": ""}, "scrap it, delete it")
        self.assertEqual((out['intent'], out['params']), ('FILE_DELETE', ''))

    def test_prompt_lists_folder_files(self):
        self.assertIn('idea.txt', r.build_prompt('idea.txt', ['idea.txt']))

if __name__ == '__main__':
    unittest.main()


class GuardTests(unittest.TestCase):
    def test_stop_needs_stop_word(self):
        out = r.classify(lambda m: '{"intent":"STOP"}', "delete all the stuff there")
        self.assertEqual(out['intent'], 'AI_CHAT')

    def test_reworded_note_falls_back_to_users_words(self):
        out = r.classify(lambda m: '{"intent":"NOTE","content":"buy milk"}', "jot down that I need oat milk")
        self.assertEqual(out['params'], "jot down that I need oat milk")
        out = r.classify(lambda m: '{"intent":"NOTE","content":"oat milk"}', "jot down that I need oat milk")
        self.assertEqual(out['params'], "oat milk")


class MisrouteTests(unittest.TestCase):
    def test_delete_sentence_never_appends_or_creates(self):
        for intent in ('FILE_APPEND', 'FILE_CREATE'):
            out = r.classify(lambda m, i=intent: '{"intent":"%s","content":"that"}' % i,
                             "Can you delete part of the files?", last_file='idea.txt')
            self.assertEqual(out['intent'], 'AI_CHAT')

    def test_append_needs_own_words(self):
        out = r.classify(lambda m: '{"intent":"FILE_APPEND","content":"banana"}', "add something to it", last_file='a.txt')
        self.assertTrue(out['needs_clarification'])

    def test_discussing_delete_behavior_is_not_a_delete_command(self):
        command = ('So when we delete a file, and I say delete it, you should know the intent carefully. '
                   'Not just relying on the words that confirm delete.')
        out = r.classify(lambda m: '{"intent":"FILE_DELETE","target":"CodexVoiceTest.txt"}', command)
        self.assertEqual(out['intent'], 'AI_CHAT')

    def test_direct_delete_request_is_not_blocked_as_discussion(self):
        out = r.classify(lambda m: '{"intent":"FILE_DELETE","target":"a.txt"}',
                         'I want you to delete a.txt')
        self.assertEqual((out['intent'], out['params']), ('FILE_DELETE', 'a.txt'))
