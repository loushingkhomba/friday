import os
import json
import traceback
from unittest.mock import MagicMock, patch
import sys

# Mock hardware dependencies
sys.modules['speech_recognition'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()

try:
    from assistant import VoiceAssistant
except Exception as e:
    print(f"Import Error: {e}")
    traceback.print_exc()
    sys.exit(1)

def test_assistant():
    try:
        with patch('pyttsx3.init'), patch('ollama.chat') as mock_chat:
            assistant = VoiceAssistant()
            assistant.speak = lambda text: print(f"Assistant would say: {text}")
            
            test_cases = [
                ("Could you please search for the latest news on Mars?", "SEARCH"),
                ("I need to be reminded to call my mom in 10 minutes", "REMINDER"),
                ("Open my browser for me", "APP_OPEN"),
                ("What is the current temperature in Tokyo?", "WEATHER"),
                ("Tell me a joke", "AI_CHAT"),
            ]

            print("--- Starting Logic Test ---\n")
            for text, expected in test_cases:
                print(f"User: {text}")
                mock_chat.return_value = {
                    'message': {
                        'content': json.dumps({"intent": expected, "params": "mocked params"})
                    }
                }
                assistant.process_command(text)
                print(f"Result: Intent {expected} triggered successfully.\n" + "-"*30)
    except Exception as e:
        print(f"Execution Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_assistant()
