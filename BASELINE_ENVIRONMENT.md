# Friday frozen baseline environment

**Captured:** 2026-10-24  
**Purpose:** Reproducibility reference for the frozen pre-orchestrator version. This records the installed machine state; it does not claim the project has a complete reproducible installer.

## Runtime and services

- Windows: 10.0.26300.9711 (from the user-provided command output).
- Main runtime: Python 3.11.9 at `%LOCALAPPDATA%\Programs\Python\Python311\python.exe`.
- Kokoro worker: Python 3.11.9 in `voice_assistant/.venv-kokoro-tts/`.
- Ollama service: 0.35.1; Python client: `ollama` 0.6.1.
- Database image: `pgvector/pgvector:pg18-trixie`; PostgreSQL server: 18.6; pgvector extension: 0.8.7.
- PostgreSQL compose service: `voice_assistant/compose.yaml`; persistent named volume `voice_assistant_friday_pgdata`; port bound to `127.0.0.1:5432`.

## Configured Ollama models

| Friday role | Configured tag | Installed Ollama ID |
|---|---|---|
| Fast/chat and intent routing | `llama3.2:latest` | `a80c4f17acd5` |
| Reasoning | `qwen3.5:9b` | `6488c96fa5fa` |
| Deep reasoning | `gemma4:26b` | `001e5dafc3c7` |

`qwen3.5:9b-q4_K_M` is also listed by Ollama with the same model ID as `qwen3.5:9b`. Friday defaults are defined in `assistant.py`; the local `.env` model-key scan showed no overrides. No cloud model is configured for Friday.

## Model file locations

| Component | Current location |
|---|---|
| Ollama model blobs | `%USERPROFILE%\.ollama\models\` |
| faster-whisper `small.en` | `%USERPROFILE%\.cache\friday\whisper-small.en\` (resolved cache directory exists) |
| WeSpeaker ResNet34-LM ONNX | `voice_assistant/models/speaker_recognition/wespeaker_resnet34_lm/model.onnx` |
| Kokoro model and voices | `voice_assistant/models/tts/kokoro_hf_cache/hub/models--hexgrad--Kokoro-82M/` (voice `af_bella`) |
| Piper `en_US-amy-medium` alternate | `voice_assistant/models/tts/en_US-amy-medium.onnx` |

Model weights and caches are local machine assets; do not commit them. Other household voice samples/embeddings, private logs, `.env`, and database dumps are excluded from Git.

## Installed main-runtime direct requirements

Versions below were queried from the Python 3.11.9 interpreter above for the packages declared in `requirements.txt`.

| Package | Installed version |
|---|---|
| `speechrecognition` | `3.14.2` |
| `pyaudio` | `0.2.14` |
| `faster-whisper` | `1.2.1` |
| `huggingface-hub` | `0.36.2` |
| `protobuf` | `6.33.6` |
| `ollama` | `0.6.1` |
| `requests` | `2.32.3` |
| `schedule` | `1.2.2` |
| `beautifulsoup4` | `4.13.4` |
| `pyautogui` | `0.9.54` |
| `chromadb` | `1.5.8` |
| `sentence-transformers` | `2.2.2` |
| `dateparser` | `1.4.2` |
| `pygame` | `2.6.1` |
| `piper-tts` | `1.8.0` |
| `winrt-runtime` | `3.2.1` |
| `winrt-Windows.Foundation` | `3.2.1` |
| `winrt-Windows.Media.SpeechSynthesis` | `3.2.1` |
| `winrt-Windows.Storage.Streams` | `3.2.1` |
| `numpy` | `1.26.4` |
| `scipy` | `1.17.1` |
| `onnxruntime` | `1.22.1` |
| `pystray` | `0.19.5` |
| `Pillow` | `11.1.0` |
| `psutil` | `7.1.3` |
| `psycopg` | `3.3.6` |

## Installed optional runtime requirements

### Edge TTS environment (main Python)

| Package | Installed version |
|---|---|
| `edge-tts` | `7.2.8` |

### Kokoro worker environment

| Package | Installed version |
|---|---|
| `kokoro` | `0.9.4` |
| `soundfile` | `0.14.0` |

## Private baseline backup

Backed up outside the project/repository to a local, user-owned backup directory dated `2026-10-24`:

- `friday-baseline.dump` ? PostgreSQL custom-format dump.
- `configuration/.env` ? private database/runtime settings.
- `configuration/guardrails.json` ? user-owned permissions.

Do not stage or publish this backup. Preserve the `.env` values privately; they are not copied into this document. The exact path remains in local records outside this repository.

## Freeze notes

- This is an environment snapshot, not a claim that every installed package in the global Python environment is Friday-only.
- The project requirements remain range-based; review the version tables before recreating the runtime.
- No source code or database schema was changed to create this record.
