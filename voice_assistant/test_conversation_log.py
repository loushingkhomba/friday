import json
import os
import tempfile
import unittest

from conversation_log import ConversationLog


class ConversationLogTests(unittest.TestCase):
    def test_appends_local_jsonl_turns_with_intent_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            log = ConversationLog(os.path.join(directory, 'conversations'))
            log.append('user', 'delete that file', intent='FILE_DELETE', params='CodexVoiceTest.txt')
            log.append('assistant', 'Say yes, delete it, or cancel.')
            files = os.listdir(log.directory)
            self.assertEqual(len(files), 1)
            with open(os.path.join(log.directory, files[0]), encoding='utf-8') as handle:
                records = [json.loads(line) for line in handle]
            self.assertEqual([entry['role'] for entry in records], ['user', 'assistant'])
            self.assertEqual(records[0]['intent'], 'FILE_DELETE')
            self.assertEqual(records[0]['session_id'], records[1]['session_id'])


if __name__ == '__main__':
    unittest.main()
