# Codex-11Oct2026

- **Session ID:** Codex-11Oct2026
- **Session owner/model:** Codex
- **Started:** 2026-10-11
- **State:** ACTIVE â€” close only when the user explicitly says the session is finished.

## Session goal

Track this session's changes and open work. Carry forward the project's current TODOs; mark work complete only after the stated evidence exists. This is the single shared log: every model appends its dated changes and verification here, identifying itself by model name. Preserve earlier entries.

## Plan and project TODOs

- [x] Read current `STATUS.md` and `STEERING.md`; audit listed unfinished work against code and logs.
- [x] Parse current `guardrails.json`; confirm configured root and deletion flag. This verifies config only, not Friday's end-to-end voice behavior.
- [x] Run focused offline tests for file trash, file intents, capabilities, and intent routing: 100 passed.
- [x] Diagnose microphone switching from silent-input failover; revert rotation and restore Windows-default-only capture per user request.
- [ ] Live-test wake detection on the laptop mic and headset; verify Friday reports the selected device and transcribes commands on both.
- [x] User voice-reported file listing, delete read-back, and spoken confirmation for `Friday'sFolder\CodexVoiceTest.txt`.
- [ ] Live voice-verify restore with the new fuzzy filename matching; direct exact-name restore was verified by Codex.
- [ ] Test local intent routing against real speech transcripts; fix misroutes while preserving safety gates.
- [ ] Verify custom skills can be created, listed, loaded into prompts, and cannot override guardrails.
- [ ] Add/complete offline tests for voice actions: wake, intent, reminders, safe paths, and skill approval.
- [ ] Persist reminders; verify due-time handling and spoken alerts across restart.
- [ ] Measure current command-to-first-audio, playback, and interruption/follow-up latency; improve long-response playback and turn-taking.
- [ ] Evaluate wake-word misses, false wakes, and latency; improve detection as needed.
- [ ] Add smart-home/routine features only after narrow permissions and spoken confirmations are designed.
- [ ] Add startup checks for required local model availability.
- [ ] Fix semantic memory persistence: `memory.py` currently clears its collections at startup. Verify memory survives restart after the fix.
- [ ] Add user memory correction/forget flows.
- [ ] Add local document retrieval.
- [x] Create daily local conversation logs with recognized turns and routed-intent metadata.
- [x] Add explicit phrase-to-intent learning that cannot bypass guardrails or confirmations.
- [x] Fix delete-confirmation context loss, contextual yes phrases, and meta-command misrouting.
- [ ] User voice-test ambiguous then clear delete confirmation, natural approval, cancellation plus a new request, daily log output, and one taught phrase.
- [x] Stop unsolicited speaker-profile enrollment; allow setup only after direct `add voice profile` request.
- [ ] Voice-check profile enrollment trigger: conversation about profiles and unknown speaker must not enroll; exact request must enroll; cancellation must stop setup.
- [ ] Add a separate profile-details flow only after speaker-match reliability gate passes; collect no personal details during voice enrollment.
- [ ] Voice-check details onboarding: permission decline stores no details; skips work; readback requires confirmation; details personalize only matched speaker.
- [x] Keep microphone energy threshold adaptive, use more sensitive local VAD, display Friday as speaker, and add output playback recovery/diagnostics.
- [ ] Voice-check speech recognition with changing background noise and confirm audible replies on active Windows output.
- [ ] Voice-test six-sample enrollment, retained templates across intended microphones, same-session continuity at 0.58 after one strong match, two-strong-match profile switching, private-history withholding below continuity, and correct unknown/other-speaker separation. Do not adjust thresholds further until results are logged.

- [ ] Review recent conversation logs with the user and agree on target behaviors for more natural, context-aware conversation.
- [ ] After review, scope contextual intent and clarification, cautious tone adaptation, approved profile-scoped memory retrieval, local-data retrieval, and before/after evaluation; implementation remains deferred.

## Friday Enhancement Program â€” review each step before continuing

- [x] Step 1 â€” Bound and validate existing model-generated plans before tool execution; prohibit planner note writes; constrain correction retries. Implementation done; source and syntax checks only. User review and behavior checks pending.
- [ ] Step 2 â€” Durable task/checkpoint storage and explicit memory review/edit/forget controls; Chroma remains a rebuildable, profile-scoped index.
- [ ] Step 3 â€” Typed agent catalog and supervisor with per-agent tools, data scope, risk tier, budgets, audit, and success criteria.
- [ ] Step 4 â€” Read-only local research agent with citations; online sources stay disabled until explicitly enabled.
- [ ] Step 5 â€” Coding agent operating on copies in a sandbox; reviewable patch, test evidence, authenticated apply approval, rollback.
- [ ] Step 6 â€” User-directed agent builder: draft, validate, test, version, and request approval; never self-grant access or activate without approval.
- [ ] Step 7 â€” Home/routine agents, one narrow device integration at a time.
- [ ] Step 8 â€” Evaluation set, metrics, audit/backup/disable/rollback procedures.

## Change log

### 2026-10-15 â€” Weekday-aware wake, distinct clear-file action, warmer clarification (Codex)

- Added a weekday-context exception for leading â€œFridayâ€ mentions (for example, â€œFriday morningâ€ / â€œnext Fridayâ€), preserving weekday words in active-turn routing. Explicit wake calls remain available.
- Removed `clear` from file-delete routing. Added a separate clear-content intent and handler for UTF-8 text files directly under Friday's allowed root. It reads back the filename, requires its own confirmation, leaves the file in place, validates hashes before mutation, and stores a one-action hidden backup for `undo`. The explicit `confirm clear` and `confirm delete` phrases cannot approve the other action; a plain â€œyesâ€ confirms only the currently pending request.
- Increased casual response temperature from 0.6 to 0.78; factual and reasoning temperatures and JSON intent classification remain conservative. Clarification retries now vary wording and continue for up to four follow-ups before safely pausing.
- **Files changed:** `assistant.py`, `intent_router.py`, `file_intents.py`, `file_clear.py`, `reliability.py`, `STEERING.md`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source/doc inspection only. No tests or live voice/file actions run.
- **Next:** restart and voice-test (1) â€œFriday morningâ€¦â€ versus â€œFriday, â€¦â€, (2) â€œclear contents of Xâ€ and confirm/cancel/undo, (3) â€œdelete Xâ€ still routes to trash confirmation, and (4) unclear requests get specific varied follow-ups without modifying files.

### 2026-10-15 â€” Reduce profile flapping and retain multi-example voice templates (Codex)

- A voice-signature change now clears active private-context authorization but preserves earlier strong same-session match evidence. If the new sample is weak or unusable, Friday keeps speaker state uncertain and retries on the next active turn rather than caching `unknown` for the rest of the conversation.
- A different enrolled profile must match strongly on two consecutive utterances before Friday switches the conversation profile. Until confirmed, private profile details/history/preferences remain unavailable; uncertain turns are logged as unknown.
- Explicit future enrollments now keep six normalized embeddings plus their centroid. Matching compares each voice against its two closest examples; old centroid-only profiles still load. primary user's current profile needs explicit re-enrollment to get these example templates.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source inspection only. No tests or voice run performed.
- **Remaining:** live-test primary user across several turns and a brief noisy sample; explicitly re-enroll primary user; verify second household speaker switches only after two strong matches and cannot access primary user's history before confirmation.

### 2026-10-15 â€” Improve speaker matching samples and diagnostics (Codex)

- Updated explicit, consented `add voice profile` enrollment from three to six varied prompts. Each sample must be at least three seconds. Very quiet or heavily clipped samples retry once; recordings remain transient and only embeddings are retained.
- Added numeric quality logs (duration, RMS, peak, clipping fraction, input device) for enrollment and match attempts. Added a conservative near-threshold continuation path: score >=0.60 can match only after two strong recent matches to the same profile within three minutes and only if the competing-profile margin still passes. New wake session clears recent matches. The standard 0.62 threshold stays unchanged.
- Updated `STEERING.md`, `STATUS.md`, and `DECISIONS.md` to reflect the new enrollment process, privacy boundary, rationale, and live-check requirement.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source inspection only. No tests or live enrollment/recognition run; primary user's saved profile was not changed. Need voice test with primary user and another household speaker before relying on smoothing.

### 2026-10-15 â€” Response latency and conversation continuation (Codex)

- Reviewed `logs/conversations/friday_2026-10-15.jsonl` and matching `logs/friday_heuristic.log` entries for 13:16â€“13:24. Cold Qwen load and prompt took 33.2s for a routine question; Kokoro synthesized a 14-segment long answer over 55.7s. The reply summarized an older book list. A follow-up correction was misrouted as `FILE_WRITE`; a later â€œcheck it outâ€ reply tried to claim a file check and was blocked by the honesty filter.
- Recent book turns were tagged `unknown`, while later turns matched primary user. Per project privacy rules, unmatched turns remain excluded from primary user's profile history. Added prompt guidance to ask about missing references instead of substituting an older topic.
- Updated model routing so ordinary short suggestions and summaries avoid cold Qwen loads unless RAM reaches configurable `FRIDAY_FACT_MODEL_MIN_AVAILABLE_GB` (default 16 GB); concise summaries prefer the newest matching list. Clear information questions use direct chat fast-path. New questions/corrections discard pending clarification context. A contextual book/file check can use `FILE_READ` only when `last_file` resolves safely and exists.
- **Files changed:** `assistant.py`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source and logs inspected only. No tests, syntax checks, or live voice run performed. Voice test pending: ask for a book suggestion, request summaries, correct Friday if needed, then ask it to check the actual file. Also test a new question while Friday awaits clarification.
- **Still open:** current project backlog remains pending as listed above; especially voice routing/follow-up verification, command-to-first-audio measurement, speaker recognition stability, and user-reported audibility.

### 2026-10-11 â€” Session initialized

- Created this session log with the open project backlog.
- Added per-model session-log instructions to `STEERING.md`.
- Consolidated the active session into shared `modelsessionlog.md`; removed the former per-model log file.
- Rechecked `guardrails.json`: it parses and currently sets `allow_delete` to true. Voice execution remains unverified.
- Inspected reminder and memory initialization: reminders reset at launch, and Chroma collections are deleted at memory-module startup.
- Reviewed runtime log dates: latest files are Oct 4â€“6, so latency evidence is historical.
- **Files changed:** `STEERING.md`, `STATUS.md`, `modelsessionlog.md`.
- **Verification:** parsed guardrails JSON with PowerShell `ConvertFrom-Json`; inspected code and log timestamps. No test suite run; no live voice test performed.

## Session completion

Keep this session ACTIVE until the user explicitly says the session is finished. At that point, mark the session finished with the date. Leave unresolved checklist items pending and carry them into the next session section in this same file.

### 2026-10-11 â€” Shared-log change (Codex)

- User requested one session-log file shared by every model.
- Updated `STEERING.md` to require all models append to `modelsessionlog.md`, preserve history, and use model-labeled entries.
- Moved the active session contents here and removed the old `sessions/Codex-11Oct2026.md` file and empty `sessions/` directory.
- Updated `STATUS.md` to point to the shared log.
- **Verification:** confirmed shared file exists and old per-model session path is removed. No tests needed or run.

### 2026-10-11 â€” File-action verification progress (Codex)

- Inspected targeted tests; they use temporary directories for file mutation.
- Ran `python -m unittest test_file_trash test_file_intents test_capabilities test_intent_router -v`: **100 tests passed** in 5.875 seconds.
- Created `Friday'sFolder\CodexVoiceTest.txt` inside the configured allowed root. It contains a harmless test line and is intended for delete-to-trash and restore voice checks.
- **Still pending:** live microphone checks for list, delete read-back, spoken confirmation, restore, and capability response. Automated tests do not verify recognition or speech output.
- **Files changed:** `STATUS.md`, `modelsessionlog.md`; created `Friday'sFolder\CodexVoiceTest.txt`.

### 2026-10-11 â€” Laptop microphone diagnosis and fix (Codex)

- Device enumeration showed Windows default input is Jabra headset index 1; built-in Realtek microphone appears at index 2. Friday selected Jabra because it opened successfully and never tested alternate devices after a silence timeout.
- Updated `assistant.py` to rotate through discovered inputs after 2.5 seconds without speech, remember a mic that transcribed speech, and reset preference when the Windows default changes. Filtered Stereo Mix/loopback and sound-mapper aliases so Friday does not switch to system playback capture.
- Lowered the default minimum energy threshold from 300 to 120 and kept dynamic noise adaptation enabled for quieter laptop mics.
- Added `test_microphone_failover.py`. First test run exposed an invalid mocked device index; corrected the fixture. Final focused run across microphone, file-action, capability, and intent-router tests: **104 passed**.
- **Still pending:** real microphone checks on the laptop mic and headset. Device selection and transcription cannot be proven by unit tests.
- **Files changed:** `assistant.py`, `test_microphone_failover.py`, `STATUS.md`, `modelsessionlog.md`.

### 2026-10-11 â€” Restore Windows-default-only microphone (Codex)

- User reported Friday changed between Realtek and Jabra, captured video audio, and recalibrated to very high noise thresholds. User requested the original system-default approach.
- Reverted device rotation and fallback enumeration. Friday now opens only the current Windows default input each listen cycle. To switch between laptop mic and headset, user changes the Windows default input; Friday does not switch devices on silence.
- Restored minimum ambient threshold to 300 and fixed threshold after calibration. Removed duplicate comment and removed the test module that covered the reverted rotation behavior.
- The user transcript shows file listing worked and a delete confirmation was requested, but no successful confirmation is shown. Deletion remains unverified; the test file may still exist.
- **Verification:** focused file-trash, file-intent, capability, and intent-router tests: **100 passed**. These tests do not exercise microphone selection or live speech. Pasted traceback is truncated, so its cause is unknown.
- **Files changed:** `assistant.py`, `STATUS.md`, `modelsessionlog.md`, `DECISIONS.md`; removed `test_microphone_failover.py`.
- **Remaining:** user should select the desired input as Windows default, restart Friday, and voice-test. Current device enumeration in prior diagnostics showed Jabra as Windows default and Realtek as another available input.

### 2026-10-11 â€” Fix restore after speech-recognition filename error (Codex)

- User confirmed Friday moved `CodexVoiceTest.txt` to trash, then restore request was transcribed as â€œCortex VoiceTest.txt.â€
- Inspected real trash entry: `20261011-224439-586741__CodexVoiceTest.txt`. Numeric prefix is a timestamp used to make entries unique and sortable. Existing code already removed that prefix before matching; the failure came from exact-only filename matching against the misheard name.
- Updated restore lookup to try exact filename/stem first, then one unique close match based on normalized original filename. If multiple close files match, Friday asks for the exact name and restores nothing.
- Added tests for a timestamped file with a Whisper-style typo and for ambiguous fuzzy matches.
- **Verification:** `python -m unittest test_file_trash -v`: **71 passed**. Used exact verified name to restore real `CodexVoiceTest.txt`; confirmed it exists at Friday's allowed root, 80 bytes. New fuzzy path is automated-tested but still needs live voice verification.
- **Files changed:** `file_trash.py`, `test_file_trash.py`, `STATUS.md`, `modelsessionlog.md`, `DECISIONS.md`.

### 2026-10-14 â€” Intent context, conversation logs, and explicit learning (Codex)

- Reviewed pasted voice session. `delete that file` got read-back, but "From delay" was not recognized as confirmation and should not have discarded the pending target. User's later phrase "Friday, you can delete it" should count as contextual approval only while that read-back is pending. The sentence explaining how Friday should interpret delete was itself routed as a delete request. Later request to replace a word in a file was answered with file contents; file replacement is not currently implemented and needs separate design.
- Updated delete handling: clear contextual affirmations accepted only when a pending delete exists; unclear speech leaves the pending target unchanged and asks for yes/cancel; explicit cancellation can continue into a clearly new request. Command discussion/teaching is prevented from entering file-action tools.
- Added daily local JSONL conversation logging under `logs/conversations/`. User records include transcript, classified intent/parameters and routing source when available; assistant replies and session events are also appended. Startup prints the folder path.
- Added explicit phrase-to-intent teaching, stored in `logs/conversations/learned_intents.json`, and included as examples in local intent-router prompt. Supported labels are allowlisted; examples only guide routing and cannot override Python validations, delete confirmation, path limits, or guardrails. Friday does not silently train on ordinary or possibly misrecognized conversation.
- Updated capability descriptions, README, status, and decision log.
- **Verification:** `python -m unittest test_file_trash test_intent_router test_intent_learning test_conversation_log test_file_intents test_capabilities -v`: **115 passed**. `py_compile` passed for runtime, router, logging, learning, and capability modules. Tests do not cover live microphone recognition or Ollama route quality.
- **Files changed:** `assistant.py`, `file_trash.py`, `intent_router.py`, `intent_learning.py`, `conversation_log.py`, `capabilities.py`, `test_file_trash.py`, `test_intent_router.py`, `test_intent_learning.py`, `test_conversation_log.py`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Remaining:** user voice-test. Conversation logging begins on next Friday launch; no live voice or Ollama test performed.

### 2026-10-14 â€” Approval-gated conversation correction learning (Codex)

- Added support for clear corrections such as "No, I meant list files" after a prior user request. Friday proposes associating that previous phrase with a supported intent, then waits for an explicit spoken yes; cancel declines. Proposal expires after 90 seconds, and any new request clears it without approval.
- Approved mappings use existing `learned_intents.json` and local intent-router examples. Learning does not execute the corrected action, alter guardrails, or fine-tune a model. Ordinary conversation logs remain records, not training data.
- Updated capability wording, README, `STATUS.md`, and `DECISIONS.md`.
- **Verification:** No tests or live voice test run; testing was not requested.
- **Files changed:** `assistant.py`, `intent_learning.py`, `capabilities.py`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Remaining:** voice-test list/delete corrections, approval, cancellation, timeout, and replacement by a new command. Current example parser supports clear action labels; broad free-form correction inference is not implemented.

### 2026-10-14 â€” Friday learning roadmap (Codex)

- User asked for a plan to help Friday learn from daily conversations and improve understanding. Recorded phased plan in `STATUS.md`; no implementation changes made in this entry.
- [ ] Voice-test existing correction learning: correction proposal, explicit approval, cancel, 90-second expiry, and new request while approval is pending.
- [ ] Expand correction learning carefully; ask when correction meaning is ambiguous and never auto-save uncertain speech.
- [ ] Repair semantic-memory persistence; make explicit save/review/edit/forget work across restarts, with user approval for personal facts and preferences.
- [ ] Add an opt-in spoken review of candidate lessons from selected local logs; user approves, edits, rejects, or removes each lesson.
- [ ] Build an offline evaluation set from approved corrections and real routing failures; compare before/after behavior while checking safety cases.
- [ ] Only if data and hardware justify it, evaluate Sunday fine-tuning of one model offline; use held-out evaluation, approval before activation, and rollback. Skip training when examples are sparse or results regress.
- **Verification:** Confirmed current tracker still records semantic-memory reset and pending correction voice test. No code or tests changed for this roadmap.
- **Files changed:** `STATUS.md`, `modelsessionlog.md`.

### 2026-10-14 â€” Speaker-aware personalization request (Codex)

- User wants Friday to learn their speaking style and distinguish other household speakers. Code inspection found no speaker identification or per-person profile support; current memory/history and learned intent examples are shared on this installation.
- Added roadmap phase for voluntary local voice enrollment, confidence-based identification, unknown/uncertain handling, profile removal, and per-speaker isolation of approved memories and learned examples.
- Set safety boundary: speaker recognition personalizes conversation only; it never authenticates a person or grants permissions. No voice samples collected and no recognition code added.
- **Verification:** inspected project source for speaker identification; none found. No tests run.
- **Files changed:** `STATUS.md`, `modelsessionlog.md`.
- **Remaining:** after correction-flow voice test, design/choose local speaker-recognition method and enrollment UX before implementing; obtain consent from each person who enrolls.

### 2026-10-14 â€” First speaker enrollment request (Codex)

- User requested one-time onboarding starting with them: ask who is speaking, how to label/store their profile, enroll once, then identify that speaker in later sessions.
- Inspected `assistant.py`, `data.json`, requirements, offline package folder, and local Hugging Face model cache. Existing `data.json` already stores user name `primary user`; `check_setup()` only captures name/city when general setup is incomplete. No speaker-recognition engine/model exists in code or local caches. `torch`, `torchaudio`, `onnxruntime`, and NumPy are present; SpeechBrain/Resemblyzer/pyannote are absent.
- Suitable proposed route: local SpeechBrain ECAPA-TDNN speaker embeddings; consented profile enrollment, discard raw enrollment audio after generating local embedding, unknown/low-confidence voice prompts to identify, and voice matching used only for personalizationâ€”not permissions. Official model card describes ECAPA as speaker verification and lists Apache-2.0: https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb
- Project `STEERING.md` prohibits enabling network access unless the user explicitly orders it. No model/dependency download or implementation performed pending that authorization.
- **Remaining:** receive explicit authorization to fetch the pretrained speaker model and required packages; then implement one-time primary user enrollment and verify local recognition/unknown-speaker behavior. Each additional person must consent before enrollment.
- **Files changed:** `STATUS.md`, `modelsessionlog.md`.

### 2026-10-14 â€” Offline speaker-profile implementation (Codex)

- User authorized internet access for development downloads while requiring Friday runtime to remain offline.
- Downloaded WeSpeaker ResNet34-LM ONNX model (26.5 MB) and preprocessing config into `models/speaker_recognition/wespeaker_resnet34_lm/`; added attribution notice. Chose ONNX because installed `torchaudio 2.6.0+cu124` does not match installed CPU `torch 2.1.2`, and SpeechBrain would pull incompatible Torch dependencies.
- Added local embedding extraction/profile store. First wake asks for profile label and explicit spoken consent, then collects three utterances and saves one averaged embedding. Profile file path: `%LOCALAPPDATA%\Friday\personalization\speaker_profiles.json`, outside OneDrive. No raw enrollment recording is written to disk. Unknown speakers need their own spoken consent. User conversation-log turns record matched profile label when available.
- Added spoken profile setup/re-enrollment and confirmation-gated profile removal. Matching only personalizes conversation; it is not identity proof or action permission. Notes/history remain shared; per-speaker memory isolation stays open.
- Added `onnxruntime` and explicit `scipy` requirements; documented offline runtime, privacy, and limitations. Friday uses packaged local model path and does not download at runtime.
- **Verification:** inspected ONNX interface (`input_features`, shape `[B,T,80]`, output `[B,256]`) and file size. No tests or voice enrollment run; confidence threshold remains uncalibrated.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `requirements.txt`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`, model assets under `models/speaker_recognition/wespeaker_resnet34_lm/`.
- **Remaining:** voice-test first primary user enrollment, spoken consent refusal, recognition after restart, short/unknown utterances, second profile opt-in, and removal. Tune match threshold from observed results. Continue per-speaker memory isolation as separate item.

### 2026-10-14 â€” Diagnose conversation failures and harden routing/audio (Codex)

- Reviewed `logs/conversations/friday_2026-10-14.jsonl`, `friday_heuristic.log`, and `friday_heuristic_comparison.jsonl`. Latest session routed â€œSo, now you are saving the profile, right?â€ as `SKILL_ADD`; Friday generated an unintended skill. Consent recognition failed closed, but later an LLM reply incorrectly claimed the user had consented. A noisy transcript was used as the profile label. Kokoro then rejected malformed surrogate text; Piper fallback returned `None`, and cleanup crashed on `os.remove(None)`.
- Added a user-word gate for `SKILL_ADD`; profile status questions now report actual saved-profile state. Profile labels prefer a name explicitly present in a noisy phrase and reject long unstructured transcripts. Consent accepts clear â€œI said yes to save the profileâ€ / â€œsave my profileâ€ wording, retries one unclear answer, and otherwise saves nothing. A direct correction that consent was given now restarts setup with name and consent confirmation.
- Sanitized malformed Unicode before synthesis, fixed Piper to return the WAV path, and guarded speech output/cleanup against invalid paths.
- The unexpected generated skill file in Friday'sFolder was left untouched. Guardrails and permissions were not changed. Friday's runtime remains offline.
- **Verification:** read logs and inspected control flow; did not run tests, compile checks, or launch Friday. These fixes still need offline test coverage and a user voice retest.
- **Files changed:** `assistant.py`, `intent_router.py`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Remaining:** voice-test first enrollment and noisy name/consent recovery; ask whether Friday saved the profile and confirm it answers from actual state; confirm an ordinary profile question does not create a skill; verify Kokoro/Piper playback and that shutdown cleanup no longer crashes. Separately review or remove the unintended skill only if the user asks.

### 2026-10-14 â€” Review latest misrouted conversation (Codex)

- Inspected the newest session (19:41â€“19:45) in `logs/conversations/friday_2026-10-14.jsonl`, routing traces, and `data.json`. Friday answered â€œI can't hear your voiceâ€ with the clock; interpreted â€œlet's set it upâ€ outside a profile workflow; then saved the user's name and two profile questions as three notes. The bad notes are present in `data.json`; left them untouched.
- Added deterministic gates so model labels cannot save notes/ideas or set reminders without explicit wording, or route ordinary utterances to time/date/greeting, app, volume, skill, or code-proposal tools without a matching request. Added direct audio input/output checks and a grounded voice-profile explanation. A profile setup offer now remains pending for 90 seconds; â€œlet's set it upâ€ starts actual enrollment, and the answer goes through profile naming/consent rather than note creation.
- Updated the intent-router prompt and tracker files. Guardrails and permissions unchanged; Friday runtime remains offline.
- **Verification:** reviewed source and logs only. Did not run tests, compile checks, or launch Friday.
- **Files changed:** `assistant.py`, `intent_router.py`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Remaining:** user voice-test audio checks, profile offer â†’ setup â†’ name â†’ consent, an actual explicit note, and ordinary profile questions. Decide whether to remove the three false notes; no data was deleted.

### 2026-10-14 â€” Trace repeat failures in latest voice run (Codex)

- Inspected the 19:51â€“19:54 session. â€œHow are you doingâ€ triggered a false claim that a voice profile had been saved. Identity questions were labeled `FILE_READ`, `CAPABILITIES`, or `AI_CHAT`; Friday claimed the saved name was â€œthereâ€ despite `data.json` storing preference `primary user`. The question about a saved profile name was answered with another false disclaimer.
- Root causes: persisted old turns were always injected into a new runtime conversation; the claim filter did not treat profile enrollment as a tool action; `get_user_name()` intentionally returns neutral â€œthereâ€ without a verified voice match, but the model received that placeholder as the user's actual name; `FILE_READ` and `CAPABILITIES` had no required-word guards. The spoken name preference and verified speaker identity were conflated.
- Updated chat context to current runtime turns only, supplied separate preference/profile/match state, added deterministic personal-fact/profile answers, expanded false-profile-claim filtering, guarded more tool labels, and avoided duplicate current-user input in the intent-router prompt. Persistent history stays available for explicit last-conversation recall.
- **Verification:** inspected source and logs; no tests, syntax checks, or live run performed. The new routing needs user voice verification.
- **Files changed:** `assistant.py`, `intent_router.py`, `reliability.py`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Remaining:** restart Friday; ask â€œHow are you doing?â€, â€œWho am I?â€, â€œWhat is my name and where am I located?â€, and â€œWhat name is the voice profile saved under?â€ Confirm it says saved preference primary user, reports speaker match separately, never claims a profile unless stored, and leaves false notes untouched unless user asks to remove them.

### 2026-10-15 â€” Review latest conversation availability and routing (Codex)

- Reviewed `logs/conversations/friday_2026-10-15.jsonl` and matching entries in `friday_heuristic.log` / `friday_heuristic_comparison.jsonl`.
- â€œHello Fridayâ€ woke correctly. â€œWho am I?â€ returned saved preference primary user and correctly reported that no active voice-profile match existed. This shows the prior personal-fact fix is active in this live run.
- â€œHow many voice profiles do we have?â€ fell through to `AI_CHAT`; local profile-count status needs a deterministic response. â€œOohâ€ was transcribed as â€œOohâ€ and also sent to chat, so it is a conversational backchannel case rather than evidence of a transcription error.
- Ollama connection failed on all three model-dependent turns (`llama3.2:latest`); Python logged `ConnectionError`, then Friday spoke a generic failure. This explains the missing normal replies in this session. Kokoro output worked; no microphone/transcription exception appeared.
- Updated `STATUS.md` with this current blocker and findings. No source code or user data changed. No tests or live Friday run performed by Codex.
- **Remaining:** verify Ollama is running on user's machine; add a clear offline failure reply/availability check; answer voice-profile count from local profile state; decide whether short backchannels should get brief deterministic acknowledgment. Keep runtime offline and leave saved notes/profile data untouched.

### 2026-10-15 â€” Fix voice-profile setup request routing (Codex)

- Reviewed newer 09:41â€“09:44 turns in `logs/conversations/friday_2026-10-15.jsonl` and `friday_heuristic.log`.
- Friday's reply offered profile setup, but â€œYes, please start saving a voice profileâ€ did not match its short yes/no continuation list. It then missed setup-command patterns and the generic `start` fast path routed it to `APP_OPEN`; no enrollment samples or save attempt occurred.
- Added explicit setup-request recognition before profile status and generic app routing. It covers â€œstart saving,â€ â€œset up,â€ enrollment, and direct save requests. Existing label confirmation, spoken consent, three-sample capture, and local embedding save remain required. Updated the no-profile prompt to give the working â€œset up my voice profileâ€ phrase.
- Updated `STATUS.md`. No user profile data changed; no tests or live enrollment run.
- **Remaining:** user should restart Friday, say â€œset up my voice profileâ€ or â€œstart saving my voice profile,â€ then provide a label, clearly consent, and complete the three prompted samples. Verify success response and profile store afterward. Other blockers remain: latest `AI_CHAT` availability when Ollama is down; profile-count question routing; speaker-match threshold needs voice calibration.

### 2026-10-15 â€” Make profile naming conversational and observable (Codex)

- Reviewed 10:00â€“11:16 enrollment attempts. Setup request reached enrollment, but after asking whether to use saved name primary user, Friday repeatedly ended with â€œI didn't catch a profile name.â€ The transcript captured inside `listen()` was absent from the JSONL conversation log; only timing and the later fallback response were visible.
- Root cause: `_speaker_label_from_answer()` depended on a short list of phrase templates and rejected longer natural responses such as â€œI said to save my voice profile as primary user.â€ Profile flow was scripted; LLM did not interpret the label answer.
- Added local `llama3.2` JSON interpretation for the spoken label answer, with prompt context for saved name and examples of natural phrasing. Python validates the returned label to at most three name-like words; deterministic fallback remains if local Ollama is unavailable. Added one clarification retry and shortened the spoken prompts.
- Logged internal profile-name prompts, captured transcript text, consent prompt, and consent response in daily conversation logs. No enrollment audio is persisted. Kept explicit spoken yes/no consent as a separate gate before sample capture or profile save.
- **Verification:** source/log inspection only; no tests or voice enrollment run. No profile data changed.
- **Remaining:** restart Friday and say â€œSet up my voice profile.â€ Answer naturally, e.g. â€œUse primary userâ€ or â€œI said to save my voice profile as primary userâ€; check logged transcript and that Friday reads back primary user, requests consent, captures all three samples, and confirms save. Verify profile file exists; do not treat enrollment as complete until this live check succeeds.

### 2026-10-15 â€” Fix consent response lost during speech (Codex)

- Reviewed latest 11:24â€“11:25 voice log. Friday correctly resolved and read back primary user. Consent log contained two empty user responses; runtime had no microphone capture/transcription events for them, followed by â€œI still couldn't hear a clear yes.â€ Enrollment never reached sample recording.
- The old consent prompt asked for yes before a long privacy explanation. `speak()`'s interrupt monitor discarded ordinary speech and kept only stop commands; `listen()` began after playback and timed out. A clear â€œyesâ€ spoken as a natural response while the prompt was still speaking could be lost.
- Split the privacy disclosure from a short final consent question; monitor now preserves and stops playback for a clear yes/no during that question. Consent `listen()` waits 15 seconds for speech onset; timeouts are logged. Consent remains explicitly required before any sample capture/save.
- **Verification:** inspected logs and source; no tests or live enrollment run. No profile was saved.
- **Remaining:** restart Friday; enroll as primary user; answer â€œyesâ€ during or after the short consent question; confirm next prompt requests the three voice samples and final response confirms saved profile. Verify stored profile and recognition separately.

### 2026-10-15 â€” Accept natural spoken consent answer (Codex)

- Reviewed the follow-up 11:33â€“11:34 run. First consent turn timed out after 15 seconds with an empty transcript. Retry transcript captured â€œYes, can you hear me?â€; Friday rejected it because the yes matcher required the entire transcript to exactly match a short phrase.
- Updated consent parsing to accept clear affirmative words with harmless conversational text around them, while explicit refusal language takes precedence. â€œYesâ€ does not need a fixed full sentence.
- **Verification:** source and log inspection only. No tests, live recording, or profile save verified.
- **Remaining:** restart Friday and repeat setup. Confirm â€œYes, can you hear me?â€ proceeds to three sample prompts; confirm a refusal still saves nothing. If the first consent turn is empty again, collect the new runtime log to isolate microphone pickup during the prompt.

### 2026-10-15 â€” Use natural consent interpretation and spoken readback (Codex)

- Replaced exact-phrase consent acceptance as the primary path with the offline fast model classifying the answer as consent, decline, or unclear. The prompt supports varied natural approval and treats ambiguity as no consent.
- Consent monitor now captures any transcribed speech during the consent/readback question and stops playback; it no longer requires a recognized yes/no keyword before preserving the answer.
- After an affirmative, Friday repeats its understanding twice and asks whether it got that right. A natural affirmative confirms; refusal, unclear speech, or silence saves no profile. Deterministic phrase checks remain only as an offline fallback if Ollama cannot classify.
- **Verification:** source inspection only. No tests, runtime launch, audio capture, or profile save verified.
- **Remaining:** restart Friday; consent naturally, confirm the doubled readback is clear, and answer naturally. Verify it then asks for three samples and saves the profile; verify a refusal or unclear confirmation saves nothing.

### 2026-10-15 â€” Persist recent conversation context by matched speaker (Codex)

- Reviewed the latest 11:51â€“12:05 conversation. Friday correctly summarized primary user's work and personal details at 12:04, then falsely said the history clears after 45 seconds. That value is only the wake-word idle window.
- Found normal chat sent only the latest 10 messages (five exchanges), discarded runtime history on restart, and Chroma memory deleted its collections at initialization. Daily logs and data.json retained history but it was not supplied to chat.
- Increased the supplied history to 30 messages. Matched-speaker turns now persist in local Windows AppData beside voice profiles (capped at 120 messages per profile); unidentified voices are not supplied to future chats. On first recognized use, prior conversation logs tagged with that matched speaker are migrated. Filtered the false 45-second retention claim from assistant context.
- Switched Chroma memory to PersistentClient and get-or-create collections; startup no longer deletes semantic, episodic, or preference data. System context now explains the 45-second timer accurately.
- Updated STATUS.md. No tests or live restart/voice checks run.
- **Files changed:** assistant.py, memory.py, reliability.py, STATUS.md, modelsessionlog.md.
- **Remaining:** restart Friday and confirm the saved primary user profile restores the earlier work/personal details conversation; check history after more than five exchanges and after a restart; ensure another or unmatched speaker cannot see primary user's history. Verify Chroma notes survive restart. Memory edit/forget controls and reminder persistence remain open.

### 2026-10-15 â€” Require explicit voice-profile enrollment request (Codex)

- Reviewed the 11:24â€“12:40 voice logs. Enrollment questions repeatedly interrupted normal chat; at 11:58 and 12:05 Friday emitted a profile-name prompt without an explicit setup command. At 11:59, primary user explicitly said not to set up a profile, but enrollment flow still treated it as a missing name.
- Found three automatic/broad entry paths: first-run wake onboarding, unmatched-speaker identification, and broad phrases such as "set up" or "save"; a profile-status answer also armed enrollment from a later "yes".
- Removed those paths. Profile creation now starts only from a direct command beginning with `add voice profile` (including polite "can you add..."). Unknown speakers remain unidentified. Profile-status answer no longer arms a yes/no setup flow. Added cancellation while naming or collecting samples.
- **Files changed:** `assistant.py`, `STATUS.md`, `modelsessionlog.md`.
- **Verification:** reviewed source and daily conversation log. No tests run and no live voice check performed.
- **Remaining:** restart Friday; confirm profile discussion and an unknown voice do not trigger enrollment; say `add voice profile` to enroll; say `cancel` during setup to verify it stops.

### 2026-10-15 â€” Add consented basic details to voice-profile onboarding (Codex)

- Defined a fixed onboarding rule in `STEERING.md`: after name and voice consent, separately ask permission to save optional personalization details; ask interests/topics, day-to-day help, and reply style one at a time; allow skip/cancel; read back and confirm; store only under that speaker's profile.
- Added optional `details` storage to the local speaker profile. Matched-speaker chat context receives these user-provided details for relevant personalization; unknown speakers do not receive them. Profile removal already removes the whole profile record and details.
- Added the question sequence to enrollment and logged the decision rationale.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source review only. No tests, restart, or voice enrollment run.
- **Remaining:** live-check consent boundaries, skip/cancel handling, readback, profile persistence, matched-speaker personalization, and detail removal with profile removal.

### 2026-10-15 â€” Improve noise tracking and voice output diagnostics (Codex)

- Logs showed microphone threshold fixed at 300 because dynamic energy tracking was disabled after startup calibration. Re-enabled dynamic tracking and changed faster-whisper VAD to a more sensitive 0.45 threshold with shorter silence segmentation and speech padding.
- Changed visible response label from `Assistant:` to `Friday:`. Added one playback retry after refreshing Windows' active default output; no-playback cases now log and show a concise console message. Existing TTS synthesis fallbacks remain in place.
- Latest available Oct 15 logs show playback completed without logged errors; those records cannot prove audio was audible at the device. No tests or live audio run performed.
- **Files changed:** `assistant.py`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Remaining:** restart Friday; test quiet speech with changing background noise, verify replies are audible, and capture new logs if speech is still missed or silent.

### 2026-10-15 â€” Ground speaker-profile replies and expose match metrics (Codex)

- Inspected `logs/conversations/friday_2026-10-15.jsonl` and runtime log for the latest 14:31â€“14:34 session. Voice-score question fell through to chat; one usable sample scored 0.553, below the 0.620 threshold. Next usable sample scored 0.621 and matched primary user. A later 2.09-second turn was skipped. â€œSo that is meâ€ triggered the stock unverified-action refusal after the model made an unsupported profile/history claim.
- Added local replies for profile count/status, score requests, and direct â€œthat's meâ€ follow-ups. Score explanation distinguishes cosine similarity from probability and reports threshold, runner-up margin, duration, RMS, peak, clipping, and match decision. Match logs now include threshold, runner-up score/margin, rejection reason, and audio-quality numbers; raw audio remains transient.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source and log inspection only. No tests or live voice run performed.
- **Remaining:** restart Friday; ask â€œwhat is my voice score?â€, â€œdo you have any voice profile?â€, then â€œso that is me.â€ Confirm direct answers, metric values agree with `logs/friday_heuristic.log`, and another voice stays unmatched. These scores are similarity measures, not identity probabilities.

### 2026-10-15 â€” Replace stock honesty refusal and improve short-turn matching (Codex)

- Reviewed newest 14:43â€“14:47 conversation/runtime logs. The measured 3.78-second sample scored 0.601 vs 0.620 threshold. Identity questions mostly captured 1.70â€“2.65 seconds and were skipped by the old 3-second recognition floor. â€œWhere am I?â€ was logged as a personal-fact query but had no reply because its `am I` wording did not set the location flag.
- Removed the fixed generic action-claim refusal. Friday now retries the answer once with a context-specific rewrite prompt, checks rewritten text with the existing unverified-action filters, and uses a brief self-directed fallback if the retry fails. General chat style invites fitting dry wit, never sarcasm at the user. Identity answers now explain a short sample or below-threshold score; location query matcher handles â€œwhere am I?â€.
- Speaker matching minimum is now 2 seconds; enrollment remains 3 seconds and acceptance threshold stays 0.620. This should allow short turns to be scored without lowering match acceptance based on sparse data.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `reliability.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source and log inspection only. No tests or live voice run performed.
- **Remaining:** restart Friday; test â€œWho am I?â€, â€œWhere am I?â€, the voice-score query, and ordinary conversation. Check whether 2â€“3 second turns now get scores and whether primary user matches; compare results with another speaker before considering any threshold change. Test whether guarded bad drafts get natural rewrites without action claims.

### 2026-10-15 â€” Ground personal memory and make Friday warmer (Codex)

- Inspected newest 14:58â€“15:01 log. primary user matched at 0.633, 0.688, 0.641; near-threshold turns 0.592 and 0.597 were rejected, while 0.617 matched by continuity. On rejected turns, the model lacked primary user's private history and falsely said Friday did not know the user's name/location or could not access earlier chats. Saved basics exist in `data.json`; matched-profile history is locally persisted.
- Added local replies for â€œwhat do you know about me?â€, â€œany other information?â€, and access/recall of earlier conversations. Matched replies use the current speaker's local profile and history; unmatched replies explain recognition uncertainty and protect other profiles. Updated chat voice to feel familiar, warm, and caring, with gentle humor rather than AI boilerplate. Reduced continuity-only floor from 0.60 to 0.58 after two recent strong matches; normal threshold remains 0.62.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** latest logs/source inspected. No tests or live voice run after changes.
- **Remaining:** restart Friday and repeat personal-memory questions; verify it recognizes primary user consistently and continues earlier conversation. Have another household member speak during the same session to check that relaxed continuity does not leak primary user's history.

### 2026-10-15 â€” Preserve primary user profile details and all conversation history (Codex)

- Updated re-enrollment to refresh only the voice embedding and merge newly confirmed details without dropping skipped fields.
- Removed fixed retention caps from saved conversation history. On first matched use after restart, Friday can recover older tagged turns from its daily conversation archive; chat prompt still receives only 30 recent safe messages.
- Added durable steering rule: no automatic profile-history pruning or conversation-log deletion. Updated README with six-sample re-enrollment phrase and local storage locations.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source inspection only. No tests or live voice enrollment run. Existing daily logs and local profile stores were not altered.
- **Next:** restart Friday; say `add voice profile`; confirm primary user, give spoken consent, complete six samples. Verify score changes and saved name/details/history survive restart. Check daily records remain in `logs/conversations/`.

### 2026-10-15 â€” Fix profile reply syntax error (Codex)

- Fixed unescaped apostrophes in profile-detail labels that prevented `assistant.py` from starting.
- **Verification:** `python -m py_compile assistant.py speaker_profiles.py` passed. No runtime or voice test run.

### 2026-10-15 â€” Cache speaker identity and clean noisy speech (Codex)

- Latest log showed voice scoring on every active phrase (scores 0.262â€“0.645); a voice-score question was mis-transcribed. User reports exhaust noise during speech.
- Added transient spectral-signature check; full profile score now runs at first usable phrase and again only after detected voice change. Clear matched speaker before changed-voice turn is processed.
- Added 85 Hz high-pass and mild adaptive spectral gate before Whisper, adjusted VAD sensitivity, and expanded STT vocabulary for speaker/profile terms. Raw audio remains untouched for profile scoring and is not persisted.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** `python -m py_compile assistant.py speaker_profiles.py` passed. No tests or live audio run. Noise gate and 0.78 change threshold remain uncalibrated.
- **Next:** restart Friday with exhaust running; use several varied commands and check logs show no profile-score result unless voice signature changes. Then have another speaker speak and confirm re-identification/privacy behavior.

### 2026-10-15 â€” Diagnose output playback and add safe undo/preferences (Codex)

- Reviewed `logs/friday_heuristic.log`: Kokoro WAV synthesis succeeded before no-playable errors at 17:00:50, 17:02:57, 17:08:11, and 17:09:45; no pygame exception followed. The prior code shared global pygame music state across possible speak callers and treated `play()` as success without checking mixer state. Added a speech lock, playback-start check with refresh retry, and diagnostic counts/state/device enumeration. SDL currently lists NVIDIA HDMI, Jabra headphones, and Realtek speakers as available; historical logs do not reveal which endpoint was Windows default.
- Added persistent one-action undo metadata for note/idea saves, file creation/append, and confirmed trash deletion. Undo validates exact item identity or current file hashes; file-created undo asks for existing deletion confirmation; delete undo restores without overwriting an existing file.
- Added explicit dislike capture to the matched speaker profile. Future local-model replies receive a rule to avoid repeat questions/suggestions unless the speaker reopens the subject. Unmatched voice is not silently assigned a personal preference.
- Stored primary user as household administrator in `data.json` and added prompt/steering boundaries: designation is descriptive, never authentication or guardrail override. Did not edit `guardrails.json`.
- **Files changed:** `assistant.py`, `agents.py`, `speaker_profiles.py`, `file_trash.py`, `data.json`, `STEERING.md`, `DECISIONS.md`, `STATUS.md`, `modelsessionlog.md`.
- **Verification:** Python syntax compilation passed for changed Python modules; `data.json` parses. No feature tests or live voice/audio checks run.
- **Remaining:** Restart Friday; verify active endpoint in Windows Sound settings; test short and long spoken replies/retry logs. Voice-test `undo` for note, idea, file append, file creation (confirm and cancel), and deletion restore; test that modified files are not rolled back. With a confirmed primary user match, say `I don't like <specific thing>` and check persistence after restart and no repeated suggestion/question. Confirm other speaker preference isolation.

- **Scope update:** Undo also covers a newly set in-memory reminder; reminder persistence across restart remains a separate unfinished project item.


### 2026-10-16 â€” Persistent memory wiring (Codex)

- Inspected ChromaDB implementation and call sites. It already used `PersistentClient` and did not clear collections at startup, but application code never indexed notes or conversation exchanges; assistant initialization silently hid failures.
- Wired explicit notes/ideas into the shared semantic collection after their `data.json` save. Wired user/Friday turns into episodic ChromaDB only when both turns have the same confirmed speaker profile. Episodic queries require that profile; unmatched turns remain in daily logs only. Startup now reports the persistent database path/counts, and failures are logged.
- **Files changed:** `memory.py`, `agents.py`, `assistant.py`, `README.md`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source and tracker inspection only. No tests, restart, or live voice check run.
- **Next:** restart Friday; confirm the printed ChromaDB path and collection counts; save a primary user conversation and recall it; confirm unmatched speaker cannot retrieve it; confirm explicit notes remain searchable after restart.


### 2026-10-16 â€” Friday enhancement program, Step 1 (Codex)

- Added the eight-step enhancement roadmap to `STATUS.md` and this active session log; work pauses for user review at each step.
- Hardened `execute_plan`: accepts 1â€“5 steps only, validates the entire plan and short string parameters before execution, rejects malformed/unknown/disallowed actions before any step runs, blocks planner-triggered note writes, and validates correction parameters without allowing agent changes or note writes. Updated planner instructions to match the enforced contract.
- **Files changed:** `assistant.py`, `agents.py`, `STATUS.md`, `modelsessionlog.md`.
- **Verification:** Python syntax check and code inspection only; no tests or live Friday run. Runtime behavior remains to be verified before step 2.
- **Review gate:** user reviews Step 1 and the roadmap before more implementation.


### 2026-10-16 â€” Unified database scoping, Step 2.1 (Codex)

- User selected SQLite for Friday-managed data, profile-separated private records, and shared household records. Ordinary files Friday creates remain files; user-owned `guardrails.json` stays outside Friday's state store.
- Inventory found mixed data in `data.json`, speaker profile and per-profile history JSON, daily JSONL/learned intent files, ChromaDB, skills, and staged code proposal/backup files. Reminders are currently runtime-only.
- Added `friday_store.py`, a SQLite schema foundation covering profiles/voice templates, scoped preferences and memories (with vector BLOBs), conversation turns, reminders, learned intents, skills, agent definitions/jobs, code change artifacts, and audit events. Private queries require a profile id and filter to that profile plus shared rows; unknown turns are unassigned.
- **No migration/cutover yet:** all legacy data remains intact. Voice matching is only a personalization boundary, not strong authentication or encryption against people with access to the same Windows account/database file.
- **Files changed:** `friday_store.py`, `STATUS.md`, `modelsessionlog.md`.
- **Verification:** Python syntax check and source inspection only; no tests or migration/integration run.
- **Review gate:** inspect Step 2.1 schema and scope rules before importing legacy data.

### Storage path and long-term database choice (Codex, 2026-10-16)

- Set `FridayStore` default path to `voice_assistant/data/friday.sqlite3` under the project. The folder/database is created when the store initializes.
- Recommendation: keep SQLite for the current single-host stage; use PostgreSQL + pgvector on an always-on home server when multiple devices/users connect over the home network. Do not place a live SQLite database on a network share for simultaneous clients.
- This changes the configured default only. Friday runtime has not been cut over; no DB file has been created by this change, and existing JSON/Chroma/log stores remain in use.

### 2026-10-16 — Local PostgreSQL + pgvector provisioned (Codex)

- User started the local Docker Compose PostgreSQL 18 + pgvector 0.8.7 service; health check passes. Persistent Docker volume: `voice_assistant_friday_pgdata`. Port bound to localhost only at `127.0.0.1:5432`.
- Enabled `vector`; user verified extension version 0.8.7 and a vector distance query (1.4142135623730951).
- Created `friday_app`, set its password, granted CONNECT and public-schema USAGE/CREATE, and verified TCP authentication as `friday_app` to database `friday`. No credential stored in project logs.
- **Not cut over:** Friday runtime still writes to existing JSON, JSONL, and ChromaDB stores; SQLite foundation is also not wired. No migration performed.
- **Next:** implement PostgreSQL persistence adapter/schema, then import one data category at a time with row counts and profile-scope checks. Preserve all old stores through review.
- **Files changed by this setup step:** Compose file and `.env` were created by the user; Codex updated `STATUS.md`, `DECISIONS.md`, and this session log. No app code changed.


### 2026-10-16 ? PostgreSQL runtime cutover and legacy data import

- Connected `assistant.py`, conversation logging, profile storage, intent learning, and semantic/episodic memory to `FridayPostgres`. PostgreSQL connection is required at startup; `.env` secrets are not logged.
- Added profile-scoped preference/state loading, durable shared notes/ideas and reminders, private undo state, DB conversation history, and lexical memory fallback when local embedding weights are unavailable.
- Imported legacy voice profile, preferences, notes/ideas, curated profile history, 592 daily conversation records, mixed `data.json` history archive, and learned-intent source. Chroma had zero records; no vectors needed migration. All legacy files remain unchanged.
- **Database counts:** 1 profile, 5 preferences, 15 memories, 806 turns, 3 state rows, 206 legacy archive records; no reminders or learned intents.
- **Files changed:** `assistant.py`, `friday_postgres.py`, `migrate_to_postgres.py`, `memory.py`, `README.md`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** migration command completed and reported row counts; AST syntax parsing passed for 7 Python modules. No unit tests or live Friday session run.
- **Remaining:** verify startup, profile-only context, notes/idea recall, restart persistence, reminders, and household speaker isolation. Keep JSON/JSONL/AppData/Chroma rollback copies until review.

### 2026-10-24 - Conversation-quality refinement plan recorded (Codex)

- User asked to defer the proposed natural-language improvements for later review and identified conversation refinement as upcoming work.
- Plan: inspect recent conversation logs with the user; define expected examples; then consider multi-turn context and clarification, cautious tone adaptation, approved profile-scoped memory retrieval, retrieval over approved local data, and evaluation against approved corrections and misroutes.
- **State:** planned/deferred. No assistant code changed and no tests or voice checks run. Continue the active `Codex-11Oct2026` session.


### 2026-10-24 - Speaker-profile reliability and personal-data gate (Codex)

- Latest `friday_heuristic.log` shows six primary user matches below threshold: scores 0.470 to 0.600 vs 0.620. Three utterances were skipped for 1.35 to 1.83 second duration; usable samples showed no clipping. Logged device index is 1, but historical lines do not identify its friendly name.
- Changed enrollment so Friday asks only for voice samples. Existing profile details remain preserved; no data was removed. Updated steering and decision record: personal details wait until 9/10 correct primary user matches across three clean sessions and zero false matches among at least 10 other/unknown-speaker utterances. Threshold remains unchanged.
- **Files changed:** `assistant.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source/doc edits inspected only. No tests, syntax check, or live voice session run.
- **Next:** re-enroll primary user using the same quiet microphone and position; run the acceptance checks; then separately address ASR pronunciation through explicit transcript corrections.


### 2026-10-24 - Speaker-match stability update (Codex)

- Same-session continuity now uses one prior strong match within 180 seconds; a later same-profile score may pass at the existing 0.58 threshold if the profile margin passes. The initial threshold remains 0.62, and switches to another enrolled profile still need two strong matches. Below 0.58 remains uncertain with private context withheld.
- Explicit re-enrollment now appends voice templates, keeps at most 24 normalized examples, recomputes the centroid, and records microphone names. It preserves saved profile details and never stores raw enrollment audio. Logs include microphone name and index for enrollment and match decisions.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source and tracker inspection only. No tests, syntax check, or live voice run.
- **Next:** re-enroll primary user on each intended mic; test 10 utterances across three sessions, 10 other/unknown utterances, and ensure borderline same-session turns continue without exposing data below 0.58.


### 2026-10-24 - Noise suppression and speech-voice stability (Codex)

- Replaced the weak first-buffer-only gate with adaptive spectral subtraction using the pre-speech lead-in and quiet frames across each utterance, smoothed gains, and raised the attenuation ceiling while preserving a gain floor. A single cleaned transient waveform now feeds Whisper, voice-change detection, speaker matching, and explicit enrollment. Numeric raw/clean RMS and level-change diagnostics are logged; recordings are not stored.
- Made Kokoro worker JSON safe for malformed Unicode. On synthesis failure Friday restarts and retries Kokoro once; if retry fails it reports an audio failure and keeps the configured engine instead of switching to Piper mid-run.
- **Files changed:** `assistant.py`, `kokoro_tts_worker.py`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.
- **Verification:** source edits only; no tests, syntax checks, or live audio checks run.
- **Next:** user test with exhaust and background media running. Check `speech cleanup` raw/clean RMS and `level_change_db`, verify speaker scores across the headset and laptop mic, and confirm `offline_tts_segment_synthesis` remains `engine=kokoro voice=Kokoro af_bella` throughout the run.


### 2026-10-24 - Architecture documentation aligned with current implementation (Codex)

- Replaced the outdated proposal-style architecture with a current-state description of Friday, explicitly separating implemented features, live-unverified behavior, and future plans. Covered local models/routing, offline speech and noise path, speaker privacy, PostgreSQL scopes, guarded tools/learning, logs, current limitations, and the home-network evolution path.
- **Files changed:** `local_first_personal_ai_assistant_architecture.md`, `voice_assistant/STATUS.md`, `voice_assistant/modelsessionlog.md`.
- **Verification:** compared the document against current status and runtime code; no tests or live assistant checks run because runtime code did not change.


### 2026-10-24 - User development rules added to steering (Codex)

- Added the six rules provided by the user to `STEERING.md` under ?Development rules before you start.? Future Friday development should consult and follow this section.
- **Files changed:** `STEERING.md`, `STATUS.md`, `modelsessionlog.md`.
- **Verification:** confirmed the section was inserted once and recorded in the required status/session trackers; no code or tests changed.


### 2026-10-24 - Prepare frozen baseline for Git

- Confirmed `local project folder` and `voice_assistant` are not currently Git repositories. Nearby Git repos are unrelated. Asked for the Friday local clone path or remote URL before initializing/pushing.
- Captured Python 3.11.9, direct dependency versions, Ollama 0.35.1 and configured local model tags, PostgreSQL 18.6, pgvector 0.8.7, and model locations in `BASELINE_ENVIRONMENT.md`.
- Created root `.gitignore` to exclude `.env`, `guardrails.json`, voice recordings, logs, user files, local models/caches, runtime data, wheels, and database dumps.
- Backed up PostgreSQL custom dump and current `.env`/`guardrails.json` to `local user-owned backup directory`, outside the project. Backup created and hashed; no secrets printed.
- **Files changed:** `.gitignore`, `BASELINE_ENVIRONMENT.md`, `voice_assistant/STATUS.md`, `voice_assistant/modelsessionlog.md`.
- **Verification:** local version commands, PostgreSQL version/extension query, backup completion, and project/repo path inspection. No tests run.
- **Remaining:** receive Friday repository path/remote URL; inspect its existing contents/visibility; verify Git ignore coverage; commit and tag this baseline; push; create and push `friday-2-orchestrator`.

### 2026-10-24 — Prepare public-safe Git baseline (Codex)

- Confirmed the supplied GitHub repository is public and currently contains one initial commit on `main`.
- Copied the current project into a working clone. Preserved `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`, source, tests, steering rules, and architecture documents.
- Excluded `.env`, `guardrails.json`, `data.json`, conversation logs, memory stores, voice recordings/embeddings, model weights/caches, virtual environments, private household files, and database dumps. Strengthened `.gitignore` for credential, log, audio, and model artifacts.
- Anonymized profile and location examples in the public copy and replaced the machine-specific default folder path with `Friday'sFolder` under the user's home directory. Original working files and private configuration remain unchanged; user configuration backup remains outside the repository.
- Recorded Python, direct dependency, Ollama, model, PostgreSQL, pgvector, and model-path details in `BASELINE_ENVIRONMENT.md`.
- **Verification:** reviewed candidate files and ignore matches; confirmed the remote is public. No project test suite or assistant runtime checks run. No commit or push completed yet.
- **Next:** review staged file list, commit frozen baseline on `main`, tag and push baseline, create and push `friday-2-orchestrator`, then update this session and status with commit references.
