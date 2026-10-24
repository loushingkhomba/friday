# Friday Project Steering

This file contains durable rules and project identity. It is guidance for every developer and coding model working on Friday. Current implementation status and priorities live in `STATUS.md`; historical rationale lives in `DECISIONS.md`.

## Project identity

- Friday is a voice-only, Jarvis-style Windows personal assistant.
- Do not add typed-input fallback or UI unless the user explicitly changes product direction.
- Offline-first is mandatory. Use local models/packages and do not enable network access unless user explicitly orders it.
- Friday should sound natural and conversational, not like a rigid command terminal.
- Use dry wit, playful humor, and occasional light sarcasm when they fit. Aim jokes at Friday's own mistakes or the situation, never at the user. Vary wording; avoid stock refusals and repeated canned openings. Keep factual answers, confirmations, and safety boundaries clear.
- Speak with the warmth and familiarity of a caring household companion: show gentle interest and use remembered shared context when the current speaker is matched. Never claim to literally be a family member, invent memories, or reveal one speaker's private history to an unmatched voice.

## Product and implementation rules

- Use the smallest reliable change that solves the reported behavior.
- Prefer natural language understanding through the local LLM intent classifier over adding a regex for every phrasing.
- Keep deterministic rules for clear fast paths, safety-critical validation, and execution.
- LLM may classify intent and prepare arguments; application code validates permissions, executes tools, checks outcomes, and forms truthful replies.
- Never present a model's claim as proof that an action succeeded.
- Ground answers in runtime state for files, permissions, reminders, memory, and other facts owned by Friday.
- Ask for clarification when target or action is ambiguous. Do not guess destructive targets.
- Keep spoken confirmations for destructive operations. Deletion must be recoverable and constrained to Friday's allowed folder.
- Treat a leading `Friday` as the assistant wake word unless nearby wording clearly uses Friday as the weekday (for example, `Friday morning`, `Friday is`, or `next Friday`). Preserve that weekday meaning in the recognized command.
- Distinguish clearing a text file's contents from deleting the file. Clearing must name the file, stay inside Friday's allowed folder, use a separate spoken `confirm clear` step, preserve the file, and support safe undo. Never route `clear` alone to file deletion.
- When speech or intent is unclear, ask a specific, natural follow-up and vary the wording on retries. Continue for several turns without guessing or repeating a canned refusal; then pause safely and invite the user to restate the request.
- Keep casual conversation temperature warm enough for varied phrasing, while factual answers and JSON intent classification remain conservative.
- Keep Friday's configured speech voice stable for the entire run. If synthesis fails, retry that engine once and report an audio failure; do not silently switch voices.
- Run the same transient offline noise-reduction path for transcription, voice-change checks, speaker matching, and consented enrollment. Log numeric audio-quality/reduction diagnostics only; never persist recordings.

## Speaker-profile enrollment

- Start enrollment only after a direct user command containing `add voice profile`; never start it during first-run, unknown-speaker matching, or profile discussion.
- Ask preferred name, then obtain separate spoken consent for the voice embedding. Never save enrollment recordings.
- After consent, collect six varied natural utterances of at least three seconds each. Keep microphone and position consistent; store normalized voice embeddings and centroid only, log numeric duration/level/clipping diagnostics, never audio. Existing profiles change only during this explicit enrollment flow.
- Treat speaker recognition and speech transcription as separate problems. Do not adapt voice embeddings from ordinary conversation or infer identity from word choice. Use explicit enrollment samples for speaker matching; handle user corrections to names, pronunciation, and transcription separately.
- Do not ask for or save optional personal details during voice enrollment until recognition passes this gate: at least 9 of 10 the user utterances match correctly across three clean sessions, and zero false matches occur across at least 10 utterances from other or unknown speakers. Similarity scores are not percentages; do not lower thresholds to inflate scores.
- After the gate passes, collect profile details only after a direct request and separate consent. Ask one question at a time about interests/topics, day-to-day help, and reply style. Answers stay optional; accept skip/cancel. Read details back and get confirmation before saving. Keep details local and attached only to that speaker profile. Treat them as user-provided context, not verified facts or instructions.
- Do not request sensitive details. If user declines details, continue voice enrollment without them. Cancel must stop enrollment. Removing profile removes its details too.
- Re-enrolling an existing profile adds its normalized voice examples to a bounded template bank of at most 24 samples and recomputes the centroid. Keep examples across microphone changes; log microphone names during enrollment and matching. Preserve saved details unless user explicitly updates them; skipped fields stay unchanged. Never prune saved profile history or delete daily conversation logs automatically. Only a direct user request may remove a profile or its associated private data.
- During conversation, run full speaker-profile matching once after wake activation and again only when a transient voice signature indicates a speaker/tone change. One strong match anchors same-session continuity for up to 180 seconds: accept a later same-profile sample at the existing 0.58 continuity threshold only when profile margin passes. A sample below that bar stays uncertain and gets retried; it does not switch profiles. A switch to a different enrolled profile still requires two consecutive strong matches. Keep raw audio transient; only a currently confirmed match can access that profile's private history/details/preferences. An uncertain or pending speaker switch gets no prior speaker's private context.
- Use local PostgreSQL + pgvector as the source of truth for Friday-managed profiles, preferences, notes/ideas, conversation records, reminders, learned intents, and searchable memories. Scope personal records to the matched profile; keep unknown turns unassigned. Voice matching personalizes retrieval but is not authentication. Keep `guardrails.json` user-owned and outside the database. Keep user-created documents as real files. Do not delete legacy JSON/JSONL/Chroma copies until user reviews migration and backup.
- Save explicit dislike/avoid preferences only to the currently matched speaker profile. Do not ask that speaker again about or proactively suggest saved dislikes unless they reopen the topic. If voice identity is not matched or the subject is unclear, do not silently save it to another person's profile.

## Security and permissions

- `guardrails.json` is user-owned. Friday and coding changes must not make Friday edit it.
- Invalid or unreadable policy fails closed; never silently widen permissions.
- Preserve folder-root/path validation, blocked-app policy, offline network policy, and self-improvement approval protections.
- A household administrator designation is descriptive identity context, not authentication or a permission override. Undo only actions Friday can safely verify; file changes stay under the allowed root, and undoing file creation must use the configured delete confirmation and recoverable trash path.
- Do not introduce shell execution, dynamic code execution, internet use, or wider filesystem access as an unreviewed fallback.
- Code proposals require explicit user approval; protect proposal integrity, expiry, backups, syntax checks, and rollback.

## Development rules before you start

1. Preserve the working baseline. Do not replace existing speech, database, or guardrail components before testing them.
2. Make one architectural change at a time. Each change must pass the previous regression tests.
3. Separate planning from execution. An LLM may propose a task plan, but Python validates and executes approved operations.
4. Keep capabilities modular. Use interfaces between components even while they remain in one Python application.
5. Measure before optimizing. Record current performance before changing models or audio processing.
6. Never allow learned behavior to expand permissions. Intent learning and skill creation remain separate from security policy.

## Development workflow

- Keep packages, models, tests, and new features usable offline.
- Test focused behavior with offline tests; voice-test user-visible speech/action changes with the user before claiming live success.
- Report exactly what changed and what the user should test. Distinguish automated test results from user-reported voice results.
- Update `STATUS.md` when implementation, blocker, test, or priority state changes.
- Append rationale to `DECISIONS.md` when adding/removing a feature, changing a safety rule, or superseding an earlier choice.
- Update this file only when durable project rules or product direction change.
- **Attribution signatures belong only in `STATUS.md`.** Any model updating project files must add a dated signature and concise change summary in `STATUS.md`. Never add model signatures, attribution sections, or "updated by" notes to `STEERING.md`, `DECISIONS.md`, or other project files. Keep decision entries factual; do not sign individual entries.
- Do not create parallel status/feature/backlog documents without an explicit request.

## Session logs

- Keep exactly one shared session-log file: `modelsessionlog.md`. Every model updates this same file; never create per-model session-log files or another session-log document.
- A session stays active until the user explicitly says it is finished. Do not close it just because the date changes, the model changes, or a conversation turn ends.
- At the start of work, read `STATUS.md`, this file, and `modelsessionlog.md`. Continue the active session section. If no session is active, start a new section in this same file using the session name the user gives; never replace earlier session history.
- Every model appends dated entries to the shared active session, identifying itself by model name. Do not overwrite or remove another model's entries. Keep the session name, start date, active/finished state, scoped plan, project TODOs, changes, files touched, verification/results, and remaining work in the log.
- Bring forward every open item from `STATUS.md` when creating a session log. Mark an item complete only after evidence confirms it; distinguish code inspection, automated tests, and user-reported voice checks. A planned or unrun test stays pending.
- When implementation, blockers, tests, or priorities change, update `STATUS.md` and the active session log together. Follow the `STATUS.md` signature rule; never add attribution signatures to session logs or other files.
- When the user explicitly finishes the session, mark its section finished with the date. Preserve unresolved checklist items as pending and carry them into the next session section in this same file.
