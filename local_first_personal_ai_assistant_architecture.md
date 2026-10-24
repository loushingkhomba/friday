# Friday: Local-First Assistant Architecture

**Architecture snapshot:** 2026-10-24  
**Scope:** Current Windows voice assistant, implemented boundaries, and the staged home-network target.  
**Source of truth for implementation status:** `voice_assistant/STATUS.md`. This document describes architecture; it does not claim unverified live behavior.

## 1. Current state at a glance

Friday is a local-first, voice-only Windows assistant. The running product is a Python console application (`voice_assistant/assistant.py`), not the earlier proposed web, desktop UI, or mobile app. Speech recognition, language models, speaker matching, and speech synthesis use local components. Web lookups are disabled by default.

The main architecture is:

```text
Windows default microphone
        |
        v
Capture until speech ends; adaptive mic energy threshold
        |
        v
Offline noise cleanup (transient; no audio recordings saved)
        |                              |
        v                              v
Whisper small.en transcription   WeSpeaker voice embeddings
        |                              |
        +---------------+--------------+
                        v
           Wake/session and conversation state
                        |
                        v
       Intent routing and local model selection
                        |
                        v
       Python validation + user-owned guardrails
               |                     |
               v                     v
 Local tools/files             PostgreSQL + pgvector
               |                     |
               +----------+----------+
                          v
                Friday response text
                          |
                          v
          Kokoro af_bella local speech output
                          |
                          v
             Windows active default speaker
```

Friday uses the Windows current default input and output devices; it does not rotate through microphones. The computer's active default can change while Friday runs. The filter uses the same transient cleaned sample for speech transcription and speaker comparison. This filter has not yet been verified by a live test with the user's exhaust/background media.

## 2. Runtime and local models

### Implemented

- **Runtime:** Python voice assistant launched with `python assistant.py`.
- **Local model service:** Ollama serves local models. Friday must have its local Ollama service available; model files on disk alone do not start the service.
- **Fast conversation and intent model:** `llama3.2:latest`.
- **Reasoning model:** `qwen3.5:9b`.
- **Deep model:** `gemma4:26b`.
- **Model routing:** heuristic task routing is the code default. Model choice and intent classification are separate concerns. Simple deterministic requests use Python fast paths; other requests can use the local JSON intent router and local chat models.
- **Speech recognition:** cached faster-whisper `small.en`, in offline mode.
- **Speaker matching:** local WeSpeaker ResNet34-LM ONNX model.
- **Speech output:** local Kokoro `af_bella` is the configured voice. On synthesis error, Friday restarts the Kokoro worker and retries once. It does not silently change to another voice mid-run; after retry failure the reply is reported as an audio failure. Alternate TTS engines may still be selected by explicit configuration or startup availability rules.
- **Internet:** live web lookup is disabled by default. No cloud model is required by the default configuration.

### Not implemented as an active architecture

The earlier proposal's FastAPI service, React UI, MCP interface, browser research agent, general PDF/document RAG pipeline, and phone client are not part of the current running application.

## 3. Voice input, noise cleanup, and speaker matching

### Capture and transcription

1. Friday waits for a supported wake phrase such as ?Friday,? ?hello Friday,? or ?wake up Friday.?
2. During an active conversation, it records until its end-of-speech silence detector closes the turn; there is no fixed phrase-length cap.
3. The microphone energy threshold adapts to ambient input. Faster-whisper performs local English transcription and uses VAD.
4. An 85 Hz high-pass filter reduces low-frequency rumble. Adaptive spectral subtraction estimates noise from the leading buffer and quiet frames in the utterance; smoothed frequency/time gains reduce artifacts.
5. The cleaned audio is used for transcription, voice-change checks, speaker matching, and consented enrollment. Raw samples are transient and are not saved as recordings.
6. Runtime logs store numeric diagnostics (for example, raw/clean RMS and level change), not waveform data.

This is local signal processing, not neural source separation. It can reduce steady noise and some changing noise; it cannot reliably remove overlapping speech or music. The actual noise reduction and its effect on recognition still need a live room test.

### Speaker profiles and privacy

- Profile setup starts only after a direct ?add voice profile? request and requires separate spoken consent for the voice embedding.
- Enrollment collects six varied utterances of at least three seconds. Friday stores normalized embeddings and a centroid, not the recordings. Re-enrollment can retain up to 24 embeddings and records microphone names.
- Initial profile threshold is 0.62. After one strong same-session match, same-profile continuity can pass at 0.58 for up to 180 seconds when the profile margin is sufficient. Switching to another enrolled speaker requires two consecutive strong matches.
- Uncertain and unknown speakers do not receive another person's private context. A match only personalizes the conversation; it is not authentication and never grants permission.
- Personal details remain gated until the documented speaker-reliability criteria pass. Optional details require a direct request, consent, read-back, and confirmation.

## 4. Conversation and task routing

Friday combines deterministic application logic with local language models:

```text
Wake/session state and pending confirmation
                     |
          deterministic fast paths
                     |
       local intent classification when needed
                     |
 Python validation, path checks, guardrails
                     |
     execute approved local tool or answer
                     |
       verify result and form response
```

- The LLM can classify a request or prepare bounded arguments. Python code validates the target, policy, and operation before execution.
- Destructive file actions require the relevant permission, a filename read-back, and spoken confirmation. Unclear recognition does not approve a pending action.
- Multi-step plans are limited to one through five validated steps. Unknown or disallowed steps reject the plan before execution. Planner-driven note writes are blocked.
- Chat claims about completed actions are checked against runtime outcomes. An LLM statement alone is not proof that an action succeeded.
- Clarification and follow-up state is kept within the active conversation flow. Stop/interruption words can stop speech playback.

## 5. Tools and file operations

Implemented local capabilities include notes and ideas, reminders, time/date, app actions, volume controls, capability/status questions, and supported file operations.

File operations include listing, reading/searching, creating, appending, clearing supported text-file contents, deleting, restoring, and undoing supported recent actions. Access is constrained by the user-owned `guardrails.json`; file access stays within its configured allowed root. Delete moves files to recoverable trash and requires confirmation. Clearing a file is a distinct action from deleting it, uses its own confirmation, preserves the file, and supports undo. User-created files remain physical files; Friday-managed records live in the database.

Friday's self-improvement features are approval-gated. Explicit user corrections can propose bounded intent examples; Friday saves them only after spoken approval. Skills and code changes require explicit requests/approval, integrity checks, backups, validation, and rollback. Learned intent examples influence classification only: they do not fine-tune models, modify guardrails, expand permissions, or execute the command being discussed.

## 6. Memory, PostgreSQL, and family separation

PostgreSQL with pgvector is Friday's configured runtime store. The current Docker Compose service binds to `127.0.0.1:5432` and retains database files in a persistent Docker volume. It is local to this PC at present, not yet a multi-device home-network service.

Friday-managed records include profiles and voice embeddings, profile-scoped preferences, shared notes/ideas and household state, conversation turns, reminders, learned intent examples, and searchable memory vectors where available. The database migration was additive; legacy JSON, JSONL, AppData, and ChromaDB sources remain as rollback copies. New conversation turns are written to PostgreSQL; old daily JSONL logs are archives, not the current source of truth.

Data visibility is separated as:

| Scope | Access behavior |
|---|---|
| Private | Only supplied to the currently matched profile and authorized application flow |
| Shared | Available as common household information |
| Unassigned | Unknown-speaker turns stay unassigned and are not used as another person's private memory |

Voice matching is a personalization boundary, not a secure login. PostgreSQL access is local to the configured service; a future server deployment needs authenticated clients and stronger household access controls before opening network access.

## 7. Guardrails and safety boundary

- `guardrails.json` is user-owned. Friday cannot update it, and model output cannot override it.
- Invalid or unreadable guardrails fail closed; they do not widen access.
- The LLM proposes intent and arguments; deterministic code validates the action, allowed path, confirmation, and result.
- File deletion is recoverable and constrained to the allowed root. Other external actions remain unavailable unless a narrow, reviewed integration is added.
- Speaker recognition does not establish administrator identity or authorize actions.
- Offline mode keeps network lookup disabled. Local package/model installation may be performed separately by the owner.

## 8. Logging and observability

Runtime and model-routing diagnostics are kept under `voice_assistant/logs/`. Current logs can report timing, model/route, microphone capture quality, speaker-match scores, noise cleanup level change, TTS engine/voice, and playback outcomes. Raw voice recordings are not logged or retained. Logs may contain recognized text and should be treated as private household data.

Project progress is tracked in `voice_assistant/STATUS.md`; architectural decisions in `voice_assistant/DECISIONS.md`; the single active shared work session in `voice_assistant/modelsessionlog.md`.

## 9. Implemented versus pending

### Implemented in code

- Wake-word standby and active conversational listening with end-of-speech capture.
- Windows-default microphone/output selection without microphone rotation.
- Offline Whisper transcription, local speaker profiles, Kokoro voice output, and output interruption.
- Heuristic model routing plus local LLM intent classification and deterministic tool validation.
- PostgreSQL + pgvector runtime integration and additive import of legacy records.
- Profile-scoped private data, shared household records, and unknown-speaker isolation.
- Guarded local notes, reminders, app/volume actions, and allowed-root file operations.
- Explicitly approved intent learning, guarded skills/code proposals, bounded planner validation, undo for supported operations, and recoverable delete/restore.
- Adaptive noise cleanup shared between transcription and speaker matching; stable Kokoro runtime voice with a single worker retry.

### Pending or not verified live

- User voice test of the latest noise cleanup in the presence of exhaust and background media.
- Confirm recognition stability across the user's intended microphones and other household speakers.
- Confirm the latest Kokoro fix keeps `af_bella` through actual extended use and that audible playback succeeds on active Windows output.
- Restart/persistence and profile-isolation checks for PostgreSQL-backed records, including reminders.
- Broader offline test coverage and measured transcription, intent, latency, interruption, and tool-success evaluation.

### Future architecture, not current features

- Phone/web client and authenticated home-network API.
- Read-only document research/RAG over user-approved local files with citations.
- Sandboxed coding agent with reviewable patches and explicit apply approval.
- User-directed agent builder and narrowly scoped smart-home integrations.
- Evaluation datasets, operational backups/monitoring, and controlled server deployment.

## 10. Staged home-network target

The present single-PC design can evolve toward a private home server, but the current system is not yet exposed to the network:

```text
Family voice clients (future; authenticated)
                  |
        Home-network API (future)
                  |
       Friday orchestrator on server
          |         |          |
       Ollama   PostgreSQL   Local tools
                  + pgvector
          |
 local STT / speaker profiles / TTS
```

Before enabling network clients, add user authentication independent of voice matching, per-person authorization, encrypted transport, secret management, audit retention, backup/restore, and a narrow API. Keep `guardrails.json` owner-controlled. Add one integration at a time and test permission boundaries before allowing home-device control.

## 11. Architecture principles

1. Local models and data by default; network access only when explicitly enabled.
2. Use deterministic code for permissions, validation, execution, and verifying outcomes.
3. Keep private memory scoped to the matched profile; voice recognition is not authentication.
4. Keep voice consistent during a run; disclose synthesis failures instead of silently changing voices.
5. Treat noise suppression, speaker matching, and speech recognition as related but distinct quality problems; validate them with real microphone tests.
6. Add agent autonomy only behind typed tools, narrow permissions, review, audit, and rollback.
7. Keep implemented behavior separate from plans and unverified behavior.
