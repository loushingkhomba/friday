# Friday Voice Assistant

Friday is a Windows desktop assistant. It uses local Ollama models for chat, local Whisper for speech recognition, and local Kokoro for speech output.

## Current features

- Wake phrases: **Friday**, **hello Friday**, **hey Friday**, and **wake up Friday**. Clear weekday phrases such as “Friday morning,” “next Friday,” or “Friday the 13th” are treated as weekday references.
- Local wake detection. Idle speech without a leading wake phrase is discarded. After activation, follow-up conversation stays open for 45 seconds.
- Local chat with task-based model routing. Regex is fast path; local JSON intent router handles unfamiliar action phrasing.
- Daily local conversation logs include recognized text, routed intent and parameters when available, and Friday's replies; stored under `logs/conversations/`.
- Opt-in speaker profiles: enroll only when directly asked. Friday obtains a name and spoken consent, collects six varied utterances of at least three seconds, and keeps six voice-example embeddings plus a centroid rather than recordings. A weak match stays uncertain and is retried; switching to another enrolled speaker requires two consecutive strong matches. Private profile context stays gated until a match is confirmed. Re-enrolling the matched user refreshes voice examples while preserving saved details and conversation history.
- Kokoro `af_bella` voice by default; `af_sarah` and `af_nova` are alternatives.
- Piper Amy and Windows SAPI fallback speech.
- Notes, reminders, application controls, and local conversation history.
- Friday's file read, write, and search commands are rooted at the folder configured in `guardrails.json`. The safe default is `Friday'sFolder` under the current user's home directory. Use relative paths; attempts to reach outside the folder are rejected.
- Clear “create a file” requests create `.txt` files there; Friday asks for the filename if missing and leaves existing files unchanged by default.
- Guardrails live in `guardrails.json`: internet is disabled, planned system actions are blocked, and shell/browser/file-explorer launches are blocked by default. `filesystem.allow_delete` is re-read for each delete request; other rule changes need restart. Invalid JSON keeps safe defaults and Friday reports parse location.
- Friday can add user-requested skills under `Friday'sFolder\skills`. Code changes are staged as patches under `Friday'sFolder\updates`, limited to `assistant.py` and `agents.py`, and applied only after the exact proposal ID is spoken. Guardrail config and protected approval/path checks are excluded from patching.
- Live web, news, and weather lookups stay disabled until `network.enabled` is set to `true` in `guardrails.json` and `FRIDAY_OFFLINE=0`.
- Accuracy: tools do actions and facts; the chat model never claims an action. Claim guard blocks past, future and offer wording. Old false replies are filtered from prompts. Factual questions go to `qwen3.5:9b` at low temperature when 5 GB RAM is free.
- File voice commands: create, add to ("add X to it"), list, folder location, clear text-file contents, delete and restore. Clearing names the file and asks separately for `confirm clear`; it leaves the file in place and can be undone with `undo`. Delete needs `"allow_delete": true` under `filesystem` in `guardrails.json` (you edit it; no restart). It reads name(s) back, then accepts a clear confirmation such as "yes", "go ahead" or "confirm delete"; say "cancel" to keep files. An unclear response leaves the pending confirmation active. Deleted files move to `.trash`; say `restore name` to undo. "Delete both/the two/all the files" supports up to 10 files per confirmation.
- LLM intent routing: simple rules are fast path; local `llama3.2` JSON router chooses a tool for other requests. Python, not model, runs tool. Failed or unsafe classification falls back to chat.
- "What was your last conversation?" is answered from real history. "You are wrong" gets an honest apology.
- "Stop" interrupts Friday mid-speech.
- See `STATUS.md` for current state and roadmap, `STEERING.md` for project rules, and `DECISIONS.md` for historical choices and rationale.

These are application-level limits. Windows still grants Friday and any apps it launches the same account permissions as the user running it; use a separate Windows account for OS-level isolation.

## Friday self-improvement

- Say `Friday, add a skill for meal planning` to create and activate a local skill. Say `Friday, list my skills` to see skills.
- Say `Friday, propose a code update to improve ...` to generate a patch. Friday prints the complete diff and gives it an ID.
- Review the diff, then say `Friday, apply the latest update`. Friday reads back the update ID, file, and lines changed; say `confirm update` to apply it or `cancel update` to drop it. Saying `apply update FRI-XXXXXXXX` with the exact ID still applies that patch directly. Friday creates a backup and checks Python syntax before replacing an allowlisted source file. Restart Friday after a code update.
- Each proposal is bound to hashes of its patch and source file. Friday refuses patches edited after proposal, source files that changed since, proposals older than 24 hours, and patches that add network, shell, dynamic-code, or `guardrails.json` references.
- Say `Friday, roll back the latest update` (or `roll back update FRI-XXXXXXXX`) to restore that update's backup, if the file has not changed since.
- Friday cannot edit `guardrails.json`; you must change guardrails yourself. The spoken approval phrase is not speaker authentication, so anyone able to use the microphone can issue commands.

Teach a command phrasing example explicitly: `Friday, remember when I say "scrap it", I mean "delete file".` Supported labels: chat, list files, delete file, restore file, create file, add to file, read file, stop talking, weather, and news. These examples guide intent classification only; they cannot change permissions or bypass delete confirmation. Stored in `logs/conversations/learned_intents.json`.

Friday can also learn from a clear correction in the conversation. After a request is misunderstood, say something like `No, I meant list files` or `No, I meant delete the file`. Friday proposes mapping your previous request to that supported action and asks before saving it. Say `yes` to save the routing hint or `cancel` to discard it. A new command does not approve a proposal. Corrections are not model fine-tuning; ordinary conversation logs are not automatically turned into lessons. Learned hints only help intent routing and never change permissions or skip safety checks.

Wake detection needs microphone audio monitoring. Idle audio is processed locally and discarded unless it starts with a supported wake phrase. Clear-content undo snapshots are stored in the hidden `.friday_undo` folder under Friday's allowed folder; a newer recorded action replaces the one-action undo slot and removes the superseded clear backup.

## Run Friday

Install base dependencies:

```bat
python -m pip install -r requirements.txt
```

Ollama must be installed, running, and have the models listed by `ollama list`. Friday also needs its local Whisper model cache and Kokoro environment/model cache. Kokoro uses the separate `.venv-kokoro-tts` environment; recreate it with `requirements_kokoro.txt` if needed.

Start Friday from this folder:

```bat
python assistant.py
```

Or use `run.bat`. To install bundled Piper and Windows speech dependencies without internet, run `install_offline_tts.bat`.

## Choose a voice

In Command Prompt, set a voice before starting Friday:

```bat
set FRIDAY_KOKORO_VOICE=af_sarah
python assistant.py
```

Supported Kokoro voices: `af_bella` (default), `af_sarah`, `af_nova`. The setting lasts for the current Command Prompt window. Clear it with `set FRIDAY_KOKORO_VOICE=`.

`run_edge_voice.bat` selects optional Edge TTS Ava. Edge TTS needs internet; the standard launch stays local.

## Logs and data

Runtime diagnostics and model-routing comparison logs remain under `logs/`. Friday-managed records now use the local PostgreSQL + pgvector service configured in `.env`; Docker Compose keeps database files in the persistent `friday_pgdata` volume and binds PostgreSQL to `127.0.0.1:5432`. Start it with `docker compose up -d` from this folder. Friday stores profiles, profile-scoped preferences, shared notes/ideas, conversation turns, reminders, learned intent examples, and vector memories in PostgreSQL. Unknown-speaker conversation turns stay unassigned and are excluded from private retrieval. Voice matching is a personalization boundary, not secure authentication. `guardrails.json` stays user-owned and outside the database; user-created files remain ordinary files. Existing `data.json`, daily JSONL logs, AppData profile/history JSON, and ChromaDB data were copied without deletion and remain rollback archives until reviewed. No new daily JSONL conversation files are written after PostgreSQL cutover. Database access uses `FRIDAY_DB_HOST`, `FRIDAY_DB_PORT`, `FRIDAY_DB_NAME`, `FRIDAY_DB_USER`, and `FRIDAY_DB_PASSWORD`; keep `.env` private and never commit it. The current local model cache may provide embeddings; when absent, Friday falls back to local text matching until the model is installed. Re-enrolling updates voice examples only; existing profile details remain if skipped. Voice profiles do not grant permissions.

## Project files

- `assistant.py` — assistant, wake gating, model routing, commands, and speech playback.
- `speaker_profiles.py`, `models/speaker_recognition/wespeaker_resnet34_lm/` — local embeddings, profile storage, and offline ONNX model.
- `reliability.py`, `intent_router.py`, `human.py`, `file_intents.py`, `file_trash.py`, `file_clear.py`, `capabilities.py` — accuracy guard, local intent router, natural phrasing, file parsing, confirmed file clear, recoverable delete, self-knowledge.
- `STATUS.md`, `STEERING.md`, `DECISIONS.md` — current status, durable rules, and historical decision log, respectively.
- Tests: `python -m unittest test_intent_router test_honesty test_reliability test_file_trash test_file_intents test_capabilities test_self_improvement`.
- Conversation and learned-intent tests: `python -m unittest test_conversation_log test_intent_learning -v`.
- `agents.py`, `memory.py` — tools and memory.
- `kokoro_tts_worker.py` — persistent local Kokoro worker.
- `voice_samples/` — supported voice samples and generation scripts.
- `models/tts/` — local speech voices and caches.
- `offline_packages/` — wheels for disconnected installation.
