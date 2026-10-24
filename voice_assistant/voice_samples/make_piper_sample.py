import wave
from pathlib import Path

from piper import PiperVoice


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models' / 'tts' / 'en_US-amy-medium.onnx'
OUTPUT = Path(__file__).resolve().parent / 'piper_amy.wav'
TEXT = "Hello the user. I'm Friday, here and ready to help. What would you like to do today?"

voice = PiperVoice.load(str(MODEL))
with wave.open(str(OUTPUT), 'wb') as audio_file:
    voice.synthesize_wav(TEXT, audio_file)

print(f'Created {OUTPUT}')
