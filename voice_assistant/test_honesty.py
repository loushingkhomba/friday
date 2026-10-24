import sys, unittest
from unittest.mock import MagicMock
from types import SimpleNamespace
import logging
for m in ("speech_recognition","pyautogui","pystray","pygame","pygame._sdl2","pygame._sdl2.audio"):
    sys.modules.setdefault(m, MagicMock())
import reliability as r
from assistant import VoiceAssistant

def qi(phrase):
    return VoiceAssistant.quick_intent(SimpleNamespace(logger=logging.getLogger("t"), last_file=None), phrase)

class HonestyTests(unittest.TestCase):
    def test_future_claims_blocked(self):
        for s in ("I'll delete it now. Are you sure you want to delete it?", "Let me delete that file for you.",
                  "You had already confirmed that you wanted me to delete the IDR.txt file."):
            self.assertTrue(r.claims_unverified_action(s, "delete file"), s)

    def test_history_filtered(self):
        h = [{"role": "user", "content": "delete idea.txt file"},
             {"role": "assistant", "content": "I've deleted the idea.txt file in Friday's folder."},
             {"role": "assistant", "content": "The sky is blue."}]
        self.assertEqual([m["content"] for m in r.trustworthy_history(h)], ["delete idea.txt file", "The sky is blue."])

    def test_correction_and_recall(self):
        self.assertTrue(r.is_correction("Okay, so what you have been saying is incorrect, right?"))
        self.assertFalse(r.is_correction("What is the capital of France?"))
        self.assertTrue(r.is_last_conversation_query("What was your last conversation?"))
        self.assertEqual(qi("What was your last conversation?")["intent"], "LAST_CONVERSATION")
        self.assertEqual(qi("Okay, so what you have been saying is incorrect, right?")["intent"], "HONESTY_FIX")

    def test_recall_uses_real_history(self):
        h = [{"role": "user", "content": "what is the time now"}, {"role": "assistant", "content": "It is 5 PM."},
             {"role": "user", "content": "What was your last conversation?"}]
        out = r.last_conversation_reply(h, "What was your last conversation?")
        self.assertIn("what is the time now", out)

    def test_ok_so_now_delete(self):
        self.assertEqual(qi("OK, so now delete the file which is there in Friday's folder.")["intent"], "FILE_DELETE")

if __name__ == "__main__":
    unittest.main()

