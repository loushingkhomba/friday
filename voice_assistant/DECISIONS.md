# Friday Decision Log

Purpose: preserve decisions made during development, including what changed, why, alternatives rejected, and resulting trade-offs. This is historical; it is not a feature inventory, current status, or backlog.

## 2026-10-15 — Separate weekday wake references and file-content clearing

- **Context:** User reports weekday references beginning with “Friday” can activate the assistant, requests to clear file contents are interpreted as deletion, and confused replies repeat stock wording.
- **Decision:** Preserve clear weekday phrases such as “Friday morning,” “next Friday,” and “Friday the 13th” instead of treating them as wake calls. Add a distinct `FILE_CLEAR` action for supported text files under Friday's root, with a separate spoken confirmation, a verified backup, and an `undo` path. Remove “clear” from delete routing. Increase only casual chat temperature to 0.78; keep factual/reasoning and JSON intent routing conservative. Vary focused clarification retries and allow four follow-ups before safely pausing.
- **Why:** A file can be emptied without being removed. Clear intent needs its own confirmation and recoverable behavior. Varied clarification should explain what Friday missed without guessing.
- **Trade-off:** Clear-content backups are temporarily stored in hidden `.friday_undo` inside the allowed folder and are removed when their one-action undo slot is replaced. Only UTF-8 text formats directly inside the allowed root are supported. No test or live voice result is claimed yet.
- **Files changed:** `assistant.py`, `intent_router.py`, `file_intents.py`, `file_clear.py`, `reliability.py`, `STEERING.md`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.

When changing or removing behavior, append an entry with date, context/problem, decision, reason, alternatives/trade-offs, and affected files. Do not silently rewrite earlier entries; append a superseding entry when direction changes.

## 2026-10-15 â€” Add speaker identity hysteresis and multi-example matching

- **Context:** Acoustic signature changes and low-scoring turns cleared primary user's active profile after a single sample. This caused identity flapping. Each profile also held only one averaged voice embedding, losing the range of its enrollment samples.
- **Decision:** On a signature change, revoke private-context access for that turn but preserve same-session match evidence as a candidate. Retry uncertain samples on following active turns. Require two consecutive strong matches before switching to another enrolled profile. Store six normalized enrollment embeddings alongside the centroid; score a profile using its two closest examples. Continue reading existing centroid-only profiles.
- **Why:** A noisy utterance should not erase conversational continuity, while private history must stay unavailable until identity is confirmed. Multiple examples represent natural voice variation without retaining recordings.
- **Trade-off:** A genuine speaker change takes two strong utterances to confirm; user must explicitly re-enroll primary user before old profile gains multi-example matching. No match thresholds were lowered. Voice-profile matching remains personalization only, never authentication.
- **Files changed:** `assistant.py`, `speaker_profiles.py`, `STEERING.md`, `README.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.

## 2026-10-06 â€” Voice-only, offline-first product

- **Context:** Friday is intended as a Jarvis-style personal voice assistant.
- **Decision:** Keep interaction voice-only, with no typed-input fallback or UI. Keep internet disabled unless the user explicitly asks for it.
- **Why:** User wants Friday to be a voice assistant and work offline with locally available models and packages.
- **Trade-off:** No text/UI fallback when microphone or speech recognition fails; new features must work locally.

## 2026-10-06 â€” Deterministic tools own actions and facts

- **Context:** The chat model claimed file operations had succeeded when they had not. It also repeated false action claims from conversation history.
- **Decision:** Use application code for supported actions and verifiable facts; filter suspicious assistant history; block unverified action claims; answer folder listings and conversation recall from real data.
- **Why:** A fluent model response is not evidence that an action happened.
- **Trade-off:** Unsupported phrasing can still miss a tool and fall back to chat; never treat chat claims as execution results.
- **Change:** Added `reliability.py`, file-specific intent handling, history filtering, and deterministic file listing/recall.

## 2026-10-06 â€” File deletion is opt-in, confirmed, and recoverable

- **Context:** User requested deletion, while speech recognition can mishear filenames and model replies had falsely claimed deletion.
- **Decision:** Gate deletion behind user-owned `filesystem.allow_delete`; read back target and require spoken confirmation; move files to `.trash` rather than permanently remove them; support restore.
- **Why:** Prevent accidental loss and make mistaken speech recognition recoverable.
- **Trade-off:** Extra confirmation step. Friday must never edit `guardrails.json`.
- **Change:** Added `file_trash.py`, delete/restore intents and tests.

## 2026-10-06 â€” Vary spoken acknowledgements

- **Context:** Repeated identical wake replies made Friday sound scripted.
- **Decision:** Rotate natural acknowledgements and greetings; account for time of day; avoid repeating the same line consecutively.
- **Why:** User asked for more human conversation.
- **Change:** Added `human.py`.

## 2026-10-06 â€” Add local LLM intent classification after rule fast paths

- **Context:** Regex-only intent matching handled only phrases explicitly coded. Unfamiliar phrasing missed actions; user wanted the LLM to identify intent and invoke the corresponding action.
- **Decision:** Keep regex for simple, clear commands; send unmatched speech to local `llama3.2` JSON classifier. Classifier chooses intent and arguments; Python validates and calls the tool.
- **Why:** Improve phrase coverage without granting the model direct execution authority.
- **Trade-off:** Additional local model latency; malformed output falls back to conversation. Risky actions need matching user words and retain deterministic confirmation.
- **Change:** Added `intent_router.py`; removed the generic vague-file catch from the regex path so unmatched phrasing can be classified.

## 2026-10-06 â€” Guard classifier against action confusion

- **Context:** â€œCan you delete part of the files?â€ was classified as append-to-file. The model could also invent note or append text.
- **Decision:** Delete/remove/erase wording blocks create/append execution; append requires user-provided action/content words; don't accept rewritten content that the user did not say. Guard `STOP` against unrelated classifications.
- **Why:** Classifier output is untrusted, especially for destructive or modifying operations.
- **Trade-off:** Some ambiguous speech requires clarification instead of action.

## 2026-10-06 â€” Support confirmed bulk deletion, capped at ten files

- **Context:** User explicitly asked to delete all files in Friday's folder; earlier implementation refused bulk deletion.
- **Decision:** Support two/both/all-file requests, list every target, ask for one spoken confirmation, move files to `.trash`, cap each operation at ten files.
- **Why:** Fulfill explicit user intent while retaining read-back, confirmation, and recovery.
- **Supersedes:** Earlier one-file-at-a-time bulk refusal.
- **Trade-off:** One confirmation covers the listed batch; cap limits blast radius.

## 2026-10-11 â€” Refresh delete permission without restarting

- **Context:** User enabled deletion in `guardrails.json`, but Friday kept reporting deletion disabled because it loaded policy only at startup.
- **Decision:** Re-read only `filesystem.allow_delete` for each delete attempt; keep the policy file user-owned. Invalid JSON continues to fail closed and reports parse location.
- **Why:** Apply an intentional permission edit promptly without letting Friday mutate its own rules.
- **Important:** A missing comma made the user's reported JSON invalid, so safe defaults correctly disabled deletion. A parse failure is not permission to guess or bypass the guardrail.

## Model selection is separate from intent classification

- **Decision:** Keep task-based chat-model choice (`llama3.2`, `qwen3.5:9b`, `gemma4:26b`) separate from `intent_router.py`, which chooses an action/tool.
- **Why:** Selecting a model for an answer and selecting a tool for an action solve different problems.

## 2026-10-11 â€” Use only the Windows default microphone

- **Context:** Silent-input failover switched between the laptop mic and headset, recalibrated repeatedly, and captured background video audio in the user's report.
- **Decision:** Open only the current Windows default input. Friday must not rotate to another microphone when it hears silence; users switch inputs through Windows Sound settings.
- **Why:** Predictable input source matters more than automatic fallback for this setup.
- **Trade-off:** If the selected default mic is unavailable, Friday reports an error and waits for the user to correct the Windows input setting.

## 2026-10-11 â€” Recover files when speech recognition slightly garbles the name

- **Context:** Trash entries carry a sortable timestamp prefix. Restore already stripped this prefix, but only matched the spoken original name exactly; Whisper transcribed `CodexVoiceTest` as `Cortex VoiceTest`.
- **Decision:** Try exact original filename/stem first, then restore one unique close normalized match. Ask for clarification when more than one close match exists.
- **Why:** Prefix was not the bug; exact-only matching failed on a speech-recognition typo. Unique matching helps while avoiding a guess when target is ambiguous.
- **Trade-off:** Similar filename collisions require the user to repeat an exact name.

## 2026-10-14 â€” Keep conversation context through delete confirmation; log and learn locally

- **Context:** User log showed speech-recognition noise cleared a pending delete confirmation, a later contextual approval was treated as a fresh delete request, and a sentence discussing how delete intent should work was misclassified as a delete command.
- **Decision:** Accept clear contextual affirmations only while a delete is pending; retain pending confirmation after unclear speech and ask again. Treat discussion/teaching of a command as conversation, not execution. A clear cancel can be followed by a new request in the same turn.
- **Why:** Use conversation context without weakening the separate read-back, spoken confirmation, path restriction, or guardrail checks.
- **Conversation records:** Append recognized turns, routing result, and assistant replies to daily local JSONL files under `logs/conversations/`.
- **Learning:** Save routing examples only when user explicitly teaches a phrase-to-intent mapping. Feed them to the local classifier as hints; they cannot grant permissions or bypass deterministic guards. Do not silently learn from unverified speech or change guardrails.

## 2026-10-14 â€” Learn from user-approved conversation corrections

- **Context:** User wants Friday to improve command understanding through daily conversations, while keeping learning under the user's control.
- **Decision:** When a clear correction such as "No, I meant list files" follows a prior request, propose mapping that prior phrase to a supported intent and require spoken approval before persisting it. Expire the proposal after 90 seconds; a different command does not approve it.
- **Why:** Corrections provide useful intent examples without treating uncertain transcripts or ordinary conversation as training data.
- **Limits:** Saved examples are local classifier hints only. They do not fine-tune models, change permissions, or bypass Python validation and confirmations.

## 2026-10-14 â€” Consent-based local speaker profiles

- **Context:** User wants Friday to ask who is speaking once, starting with them, then recognize enrolled household speakers on later conversations while Friday stays offline.
- **Decision:** Use the WeSpeaker ResNet34-LM ONNX embedding model locally. First enrollment asks for a profile label and spoken consent, then collects three utterances; persist only an aggregate embedding and label under Windows `%LOCALAPPDATA%`. Ask consent separately for each unknown speaker. Provide spoken profile setup and removal.
- **Why:** ONNX Runtime is already available and avoids this installation's mismatched Torch and torchaudio packages. The model and feature config are local; runtime does not download files or contact a service.
- **Safety/privacy:** Embeddings identify speakers only for conversational personalization. They are not identity proof and never grant permissions. Enrollment audio is not written to disk. Conversation logs, notes, and existing preferences remain shared pending a separate per-speaker memory design.
- **Trade-off:** Matching thresholds need voice testing and may need tuning for room noise and microphone changes. The local profile JSON is not encrypted by Friday; it relies on Windows account file permissions. Model attribution and license details are in `models/speaker_recognition/wespeaker_resnet34_lm/MODEL_NOTICE.md`.

## 2026-10-14 â€” Require explicit skill intent; fail closed on unclear profile consent

- **Context:** Conversation logs showed a question about saving a voice profile was misrouted to skill creation. Speech recognition also produced a long profile label and an unclear consent response; later malformed Unicode caused Kokoro synthesis to fail, and Piper's no-path return crashed cleanup.
- **Decision:** Skill creation requires an explicit add/create request. Profile status answers read the local profile store. Enrollment extracts a short label, retries unclear consent once, and saves nothing unless consent is clear. Sanitize malformed Unicode before local speech synthesis; every speech backend must return an output path before playback/cleanup.
- **Why:** Tool execution must follow explicit user intent, consent must not be inferred from uncertain speech, and a fallback voice engine must preserve the same playback contract.
- **Trade-off:** A badly transcribed skill request may fall back to ordinary chat; the user can repeat it clearly. No permissions or guardrails change.

## 2026-10-14 â€” Require explicit intent cues before note and status actions

- **Context:** Latest voice log routed a name/profile answer, a profile question, and a question about profile benefits as `NOTE`; all three were saved. It also routed an audio-output complaint as `TIME`. â€œLetâ€™s set it upâ€ was handled as model conversation instead of continuing profile enrollment.
- **Decision:** Require spoken action words before note, idea, reminder, time/date, and greeting intents can be accepted from the classifier. Keep a profile setup offer pending for 90 seconds so clear assent starts the deterministic enrollment flow. Handle direct microphone/output checks from observed state.
- **Why:** Natural-language model labels alone should not create persistent data or trigger unrelated tools. Contextual follow-ups should continue the specific pending workflow.
- **Trade-off:** Unusual phrasing that omits the explicit cue falls back to chat; users can clarify. Existing false notes are preserved pending user direction.

## 2026-10-15 â€” Ask consented basics during voice-profile enrollment

- **Context:** primary user wants Friday to learn basic context for each household speaker when explicitly adding a voice profile.
- **Decision:** After explicit `add voice profile` and separate voice-embedding consent, offer optional consent to store basic details. Ask interests/topics, day-to-day help wanted, and reply style one at a time; allow skipping, read answers back, and confirm before saving. Store details beside that person's local voice profile and use only for relevant personalization. Profile removal removes these details.
- **Why:** Personal context should be gathered consistently, separately from biometric consent, and never attributed across household members.
- **Trade-off:** Profile setup takes longer when details are accepted; details remain optional and voice enrollment can continue without them.

## 2026-10-15 â€” Adapt microphone threshold and recover speech output

- **Context:** Friday missed speech when room noise changed; console identified replies as "Assistant". Logs showed noise adaptation disabled after initial calibration. Oct 15 logs recorded playback completion, while an earlier Kokoro failure had used local fallback.
- **Decision:** Keep SpeechRecognition's dynamic energy threshold enabled after calibration, use a more sensitive faster-whisper VAD threshold with shorter silence segmentation, label console replies "Friday", and retry playback once after refreshing the active Windows output when pygame playback fails. Log when a reply produces no playable audio.
- **Why:** Ambient conditions change after startup; a fixed gate can miss quiet commands. Output failure should be visible and get one device-refresh retry.
- **Trade-off:** More sensitive VAD may accept more background speech; a movie with dialogue can still resemble a user. Logs can confirm playback started, not that speakers were audible.

## 2026-10-15 â€” Answer speaker questions from measured local state

- **Context:** The latest conversation sent voice-profile score/status questions to the chat model. A subsequent â€œthat's meâ€ response was replaced by the generic unverified-action disclaimer. Runtime logs showed scores close to the 0.620 threshold, but did not expose runner-up margin or explicit reject reason.
- **Decision:** Answer profile count/status, score, and direct identity follow-ups from the local profile store and latest match metrics. Report cosine similarity as a score, never as a probability; include threshold, runner-up margin when available, numeric audio quality, and whether match was accepted, rejected, or skipped. Log the same numeric diagnostics without storing audio.
- **Why:** Local measured state directly answers these questions and avoids model filler or invented recognition claims.
- **Trade-off:** Similarity values depend on microphone, room, and utterance quality; a score is not a calibrated identity probability. Voice match remains personalization only.

## 2026-10-15 â€” Keep honesty checks, make recovery conversational

- **Context:** The 14:43â€“14:47 voice log showed repeated unknown-speaker replies and low score (0.601); short 1.7â€“2.7 second turns were skipped by the three-second match minimum. â€œWhere am I?â€ matched the outer query but not the location answer condition. The honesty guard replaced a model draft with a fixed refusal phrase.
- **Decision:** Retain action-claim detection. When it catches an unsupported claim, ask the local model once to rewrite the answer to the actual user turn in Friday's conversational voice, then run the same guard again. Permit light dry wit/self-directed sarcasm, never mock the user. Use a short contextual fallback only if rewrite fails. Score speaker samples from two seconds; keep three-second enrollment and the 0.620 threshold. Answer â€œwhere am I?â€ from saved location.
- **Why:** Preserve truthful action reporting while avoiding repetitive disclaimers; obtain scores from more ordinary turns without lowering identity acceptance criteria based on sparse evidence.
- **Trade-off:** Very short-turn embeddings are noisier; fixed threshold remains conservative. The repair retry adds local-model latency only when a draft fails the honesty check.

## 2026-10-15 â€” Ground personal-history answers and use a familiar home tone

- **Context:** In the latest 14:58â€“15:01 log, voice scores for primary user varied from accepted 0.633/0.688/0.641 to rejected 0.592/0.597, with 0.617 accepted only by continuity. Rejected turns were treated as unknown, so the chat model was not given primary user's private profile history; it then incorrectly said it had no name, location, or earlier conversation. `data.json` does contain the saved name and saved location location, and matched primary user history is persisted locally.
- **Decision:** Answer personal-context/history questions directly from current matched-profile state; when unmatched, say Friday has saved profile history but cannot safely tell which speaker owns it. Lower continuity-only floor to 0.58, still requiring two recent strong matches and margin; retain the ordinary 0.62 threshold. Set Friday's style as warm and familiar like a caring household companion, with dry humor where it fits, while never claiming literal family status or leaking unmatched profile history.
- **Why:** Answers should reflect real saved memory, protect household privacy, and sound familiar instead of denying known information or repeating AI disclaimers.
- **Trade-off:** Lower continuity floor can increase false attribution during a speaker handoff; voice matches still personalize only and never authorize actions. Verify with another household speaker before relying on the lower floor.

## 2026-10-15 â€” Keep ordinary replies fast and resolve follow-ups safely

- **Context:** The latest conversation cold-loaded Qwen for a routine suggestion/summary, spent 55.7 seconds synthesizing a long answer, confused the newest book list with an older one, and treated a correction as a file write. Speaker tags also showed the immediately preceding turns as unknown, so they were correctly excluded from primary user's private history; a later file check was blocked as an unverified model claim.
- **Decision:** Route short ordinary questions and summaries to the fast local model unless available RAM meets a configurable high threshold (16 GB default) for factual Qwen use. Route clear information questions directly to chat, avoid joining new questions to pending clarification state, and give summaries one concise sentence per requested item while preferring the newest matching list. Route contextual file checks only to a safe read when the recent known file exists. Keep unknown-speaker turns private and clarify missing references instead of reusing older matched-speaker history.
- **Why:** Cold model and long speech synthesis dominated response time; stale context caused the wrong answer. File content must still come from the validated file tool, not an LLM assertion.
- **Trade-off:** When speaker matching fails, Friday may ask the user to repeat a reference instead of using anonymous turns. Users can lower `FRIDAY_FACT_MODEL_MIN_AVAILABLE_GB` to allow Qwen at lower available RAM, with increased cold-load risk.

## 2026-10-15 â€” Improve voice-profile sample quality and continuity

- **Context:** Speaker scores for primary user varied from confident matches to near-threshold misses. Enrollment averaged only three short prompted samples; match logs lacked audio-level diagnostics, so poor capture could not be distinguished from ordinary variation.
- **Decision:** Keep enrollment opt-in through direct `add voice profile` and separate consent. Collect six varied utterances of at least three seconds; retry very quiet or heavily clipped samples; keep only embeddings. Log numeric duration, RMS, peak, clipping fraction, and input index, never audio. Allow a score down to 0.60 only when the same profile had two strong matches in the prior three minutes and still meets the competing-profile margin. Reset continuity at a new wake session.
- **Why:** More varied clean samples improve the reference; capture metrics guide later threshold calibration. A narrow recent-match fallback can bridge one borderline turn without lowering the general match threshold.
- **Trade-off:** Temporary continuity can misattribute a similar-sounding person after recent matches; verify against other household voices before relying on it. Voice profiles still never grant permissions.

## 2026-10-14 â€” Ground personal facts and isolate chat history by runtime session

- **Context:** The next voice run repeated old profile claims during a greeting, routed identity questions to file/capability tools, and described the saved name preference as â€œthere.â€ Old assistant claims passed history filtering because voice profiles were not tracked as action targets; chat context also reused the previous launch's turns.
- **Decision:** Supply authoritative saved-name, enrollment, and current-speaker-match state to chat. Answer personal identity/location and voice-profile questions from local state. Keep ordinary chat context within the current runtime session; retain persistent history for explicit last-conversation recall only. Exclude unverified profile-action claims from future context and add evidence gates for file-read/capability routes.
- **Why:** A stored name preference does not verify who is speaking; profile creation is an action that must be confirmed by profile-store state. Old model replies must not become facts in a new session.
- **Trade-off:** Friday will not continue ordinary chat context across a restart; it can still answer explicit last-conversation questions from the saved log.

## 2026-10-15 â€” Preserve profile data and conversation history during re-enrollment

- **Context:** primary user wants a fresh voice match and asked that personal information and conversation logs persist. Profile enrollment replaced profile data, detail collection could omit previously saved fields, per-speaker conversation history was capped at 120 turns, and log recovery read only the latest 120 tagged turns.
- **Decision:** Re-enrollment updates only the voice embedding and merges supplied detail fields over existing ones. Keep saved conversation history and daily JSONL logs without automatic caps or deletion. On first matched use after restart, restore older tagged turns from daily logs when they extend saved memory. Continue sending only the latest 30 safe turns to the model prompt.
- **Why:** Refreshing voice match should not erase personalization or conversation records. Prompt size stays bounded for response speed while local archive remains complete.
- **Trade-off:** Local history and transcript files grow over time. Re-enrollment and persistence still need live restart and microphone checks.
## 2026-10-15 â€” Reduce repeated speaker matching and improve noisy speech capture

- **Context:** In the latest session, Friday re-ran speaker-profile matching on every utterance. Scores swung between 0.262 and 0.645. Whisper also transcribed a question about rescoring the voice as â€œlease for again in next week.â€ User reports exhaust noise during microphone conversation.
- **Decision:** Cache the profile result for a wake session. Measure a transient, low-cost spectral signature on later utterances and rerun full profile matching only when similarity falls below 0.78; clear the previous identity before processing that changed-voice turn. Before Whisper, apply an 85 Hz high-pass and mild spectral gate estimated from leading ambient audio; lower VAD threshold to 0.38 and add speaker/profile vocabulary to the prompt. Keep original audio for speaker matching and do not persist recordings.
- **Why:** Avoid repeated unstable score updates while still rechecking a likely voice change. Low-frequency rumble and steady fan noise can mask speech; modest local filtering may improve intelligibility without downloading models.
- **Trade-off:** Signature and noise-gate settings are initial heuristics. A changed speaker with similar acoustics could be missed, and aggressive filtering can distort speech; live testing with the fan and another speaker is required.

## 2026-10-15 â€” Add verified undo, durable avoid preferences, and admin identity context

- **Context:** Playback logs showed Kokoro WAV synthesis succeeding immediately before Friday reported no playable voice; playback used a shared process-global pygame mixer, and logs did not capture why a segment never reached playback. primary user also requested reversible actions, durable dislike preferences, and an administrator designation.
- **Decision:** Serialize speech calls and verify mixer playback starts, retry once, and log queued/played segment counts, mixer state, and available Windows output endpoints. Persist one latest undo record for reminder/note/idea saves, file creates/appends, and recoverable deletes. Validate file hashes before undo; route created-file undo through existing delete confirmation and trash. Store explicit dislikes only on a matched speaker profile and suppress repeat questions/suggestions unless user reopens topic. Record primary user as household administrator in preferences, with explicit rule that title and voice match never bypass guardrails or authenticate actions.
- **Why:** Prevent overlapping reminder/conversation playback, separate synthesis success from actual mixer start, and make rollback fail closed if the target changed. Profile matching keeps preferences separated between household speakers.
- **Trade-off:** Current historical logs cannot identify which listed output endpoint Windows selected. Unmatched speakers cannot save personal dislikes until Friday confirms profile; supported undo is limited to recorded actions and safe state checks. No guardrail permission was widened.
- **Files changed:** `assistant.py`, `agents.py`, `speaker_profiles.py`, `file_trash.py`, `data.json`, `STEERING.md`, `DECISIONS.md`, `STATUS.md`, `modelsessionlog.md`.


## 2026-10-16 — Persist searchable notes and profile-scoped conversation memory

- **Context:** ChromaDB already used `PersistentClient` and did not clear collections at startup; application code did not index saved notes or conversation exchanges, and initialization errors were swallowed.
- **Decision:** Keep `data.json` and per-profile conversation JSON as durable primary records. Index explicit notes/ideas in shared semantic ChromaDB and confirmed user/Friday exchanges in episodic ChromaDB tagged with the matched speaker. Require the same current confirmed profile to retrieve episodic memories; keep unknown turns in daily logs only. Report the database path/counts at startup and log failures.
- **Why:** This makes notes and matched conversational context searchable across restart while preserving the existing speaker privacy boundary and a recoverable primary copy.
- **Trade-off:** ChromaDB is a local search index, not the only copy. Voice-recognition errors can still affect whether an exchange is attributed and indexed. No test or restart/voice result is claimed.
- **Files changed:** `memory.py`, `agents.py`, `assistant.py`, `README.md`, `STEERING.md`, `STATUS.md`, `DECISIONS.md`, `modelsessionlog.md`.


## 2026-10-16 — Bound multi-step planner execution

- **Context:** The local planner model returned arbitrary-length JSON plans. The executor accepted loosely shaped steps and passed arbitrary parameters to registered agents; correction retries could replace parameters without validating them.
- **Decision:** Require a complete 1–5 step plan with exact `agent` and `params` fields, registered agent names, and short string parameters before running any step. Reject the whole plan if a step is malformed, unknown, disallowed by guardrails, or attempts to write notes. Keep correction retries on the same agent and validate revised parameters.
- **Why:** The planner may propose work, while deterministic code constrains what can execute. Bounded plans make review and failure recovery practical.
- **Trade-off:** Some legitimate long requests will need multiple plans; planner-generated note saving must be requested directly. No behavioral test or live run is claimed.
- **Files changed:** `assistant.py`, `agents.py`, `STATUS.md`, `modelsessionlog.md`.


## 2026-10-16 — Centralize Friday-managed data in SQLite

- **Context:** Friday's saved state is split across `data.json`, profile JSON files, per-profile conversation history, JSONL logs/learned intents, ChromaDB, skills, and code proposal/backup artifacts. Family members need private records and shared household information.
- **Decision:** Use one local SQLite database as the source of truth for Friday-managed records, with explicit `private`, `shared`, and `unassigned` scopes. Keep voice matching as a personalization filter only. Keep user-owned guardrails external and user-requested file artifacts as real files. Store embeddings as database BLOBs so the vector index can be rebuilt or searched locally.
- **Why:** One transactional store simplifies migration, backup, and household data scoping while preserving real file behavior and owner control of policy.
- **Trade-off:** Profile filtering prevents accidental cross-person retrieval but does not authenticate a speaker or encrypt the database against anyone with access to the same Windows account. Migration must be staged and verified before old stores are retired.
- **Files changed:** `friday_store.py`, `STATUS.md`, `modelsessionlog.md`, `DECISIONS.md`.

## 2026-10-16 — Project-local SQLite path and scale-up target

- **Decision:** Default the current SQLite store to `voice_assistant/data/friday.sqlite3` under the project. Use SQLite while Friday runs on one host; plan PostgreSQL + pgvector for the always-on home-network service.
- **Reason:** SQLite is a compact single-file store suitable for local application state; PostgreSQL provides a client/server database for several devices, and pgvector keeps vector search with relational records. Avoid opening one SQLite file directly from several network clients.
- **Limit:** Friday’s runtime is not yet connected to this store. This only configures `FridayStore`’s default path; the existing stores are untouched.

## 2026-10-16 — Use local PostgreSQL + pgvector for the database stage

- **Context:** The user chose to set up pgvector locally and move the database to an always-on home server later. The local PostgreSQL container is healthy, vector extension works, and a restricted app role authenticates over TCP.
- **Decision:** Use PostgreSQL + pgvector as Friday’s target store, starting locally via Docker Compose. Keep the DB data in a persistent Docker named volume; bind the port to localhost during local development. Move with `pg_dump`/`pg_restore`, not by copying a live database volume.
- **Supersedes:** The earlier SQLite default-path proposal is no longer the selected database direction. `friday_store.py` remains an unused SQLite foundation until replaced or retired in a reviewed implementation step.
- **Limit:** Friday runtime and legacy persistence are not yet connected/migrated. Existing JSON, JSONL, and ChromaDB data remain authoritative for now.


## 2026-10-16 - Connect Friday runtime to PostgreSQL and migrate existing data

- **Context:** The local PostgreSQL + pgvector service and `friday_app` role were verified. Friday still used JSON, JSONL, AppData profile files, and ChromaDB.
- **Decision:** Use PostgreSQL as runtime source of truth for Friday-managed state. Migrate profile bundles, scoped preferences, notes/ideas, conversation history/log rows, and learned intents idempotently. New conversation turns and memories write to PostgreSQL. Keep source files unchanged as rollback copies. Keep guardrails and user-created files outside the DB.
- **Privacy:** Private reads filter to the currently matched profile plus shared records. Unknown turns remain unassigned. Voice matching is not authentication.
- **Verification:** Migration imported 806 turns, 15 note/idea memories, one profile, five preferences, 206 archived legacy rows, and three state records. No reminders or learned intents existed. ChromaDB collections were empty. Seven Python files passed AST syntax parsing; no test suite or voice session was run.
- **Limit:** Live restart, voice, profile isolation, and reminder behavior remain unverified. Do not remove legacy copies before user review.


## 2026-10-24 - Gate profile details on speaker-match reliability

- **Context:** primary user's latest logged similarity scores ranged from 0.470 to 0.600, below the 0.620 match threshold. Friday previously asked for personal details during enrollment, before recognition reliability was established.
- **Decision:** Voice enrollment captures voice samples only. Do not collect optional personal details until primary user passes three clean sessions with at least 9/10 correct matches and zero false matches among at least 10 other/unknown-speaker samples. Keep current threshold; treat similarity values as scores, not percentages. Do not adapt embeddings from ordinary conversation.
- **Why:** Improve reliable recognition without exposing private profile context to another speaker or weakening the match threshold. Handle pronunciation/transcription corrections separately from speaker identity.
- **Trade-off:** Personal details remain unavailable until live voice validation passes. Existing saved details remain preserved. No tests or voice checks run for this change.


## 2026-10-24 - Same-session speaker hysteresis and retained enrollment templates

- **Context:** A confirmed speaker could lose profile context after one borderline voice score. Re-enrollment also replaced prior microphone examples.
- **Decision:** Keep the 0.62 initial-match threshold. Within 180 seconds of one strong match, allow the same profile to continue at the existing 0.58 continuity threshold if profile margin passes. Different-profile changes still need two consecutive strong matches. Keep up to 24 normalized embeddings across explicit re-enrollments and record microphone names.
- **Why:** Reduce false dropouts and retain examples across mic and natural voice variation without weakening initial identity checks. A score below the continuity bar remains uncertain; private context stays withheld.
- **Trade-off:** A same-session continuity match is less strict than a fresh initial match. This is for personalization, not authentication. Voice checks remain pending.


## 2026-10-24 - Share offline noise reduction and keep the configured speech voice stable

- **Context:** Noise cleanup only reached Whisper, while speaker matching used raw samples. Recent speaker scores fell below threshold. A Kokoro worker error containing a lone Unicode surrogate broke JSON output; runtime fallback then changed the selected voice to Piper for the rest of the run.
- **Decision:** Apply the same transient high-pass and adaptive spectral subtraction to transcription, voice-change checks, speaker matching, and consented enrollment. Keep raw audio only in memory for numeric quality comparison; never persist recordings. Make worker JSON ASCII-safe, retry Kokoro once after restart, and do not silently switch voice engines after a runtime synthesis error.
- **Limit:** Spectral suppression can reduce steady noise and some changing noise but cannot fully remove competing speech/music. Voice matching and audio quality need user testing in the actual noisy room; no threshold changes are made.

## 2026-10-24 — Public Git baseline excludes household data

- **Context:** The supplied GitHub repository is public. The frozen source contains a household-specific profile name, location examples, a personal folder path, and runtime data/configuration that must stay private.
- **Decision:** Keep the requested status, decisions, and session trackers; anonymize personal examples and make the source default folder relative to the current user's home. Exclude user-owned configuration, profiles, memories, recordings, logs, models, and database dumps. Store PostgreSQL and configuration backups outside the repository.
- **Trade-off:** A clean clone uses generic defaults. Restore the backed-up user configuration locally to reproduce this machine's settings.
