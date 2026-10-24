# Friday voice samples

Play the Kokoro samples to compare Friday's supported voices. Each reads the same line:

> Hello the user. I'm Friday, here and ready to help. What would you like to do today?

- `kokoro_af_bella.wav` â€” Friday's default voice.
- `kokoro_af_sarah.wav` â€” selectable alternative.
- `kokoro_af_nova.wav` â€” selectable alternative.
- `piper_amy.wav` â€” offline fallback voice.

Generate Kokoro samples from the project folder:

```bat
.venv-kokoro-tts\Scripts\python.exe voice_samples\make_kokoro_sample.py
```

Select a Kokoro voice in Command Prompt with `set FRIDAY_KOKORO_VOICE=af_sarah` before running Friday. Use `af_bella`, `af_sarah`, or `af_nova`.
