# Kokoro-82M voice samples

Friday uses Kokoro `af_bella` by default. `af_sarah` and `af_nova` are alternatives. Kokoro runs in the separate `.venv-kokoro-tts` environment through a persistent worker and uses CPU. Model and voice files use `models/tts/kokoro_hf_cache`; Friday runtime works offline. If Kokoro fails, Friday falls back to Piper, then Windows SAPI.

Generate all three samples from `voice_assistant`:

```bat
.venv-kokoro-tts\Scripts\python.exe voice_samples\make_kokoro_sample.py
```

Samples save as `voice_samples\kokoro_af_bella.wav`, `kokoro_af_sarah.wav`, and `kokoro_af_nova.wav`. Generate selected samples with `--voices af_bella af_nova`. Change Friday's active voice in CMD with `set FRIDAY_KOKORO_VOICE=af_sarah` before starting `python assistant.py`; use `af_bella`, `af_sarah`, or `af_nova`. To recreate the environment, create a Python 3.11 venv and install `requirements_kokoro.txt`.
