# Local-First Personal AI Assistant — Main Model + Specialist Routing

## Core idea

Build **one personal AI assistant** with multiple local models and tools behind it.

The user always talks to **Qwen 3.5 9B** as the main assistant. Qwen understands the request, plans the work, decides whether a specialist model or tool is needed, and synthesizes the final answer.

```text
                         USER
                           |
                           v
                +----------------------+
                |     QWEN 3.5 9B     |
                |    MAIN ASSISTANT    |
                | Understand / Plan    |
                | Decide / Coordinate  |
                +----------+-----------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
      TOOLS             LLAMA 3.2       GEMMA 4 26B
   Python, Files,       Fast Worker     Deep Worker
   Web, RAG, DB                         Research/Reasoning/Vision
          |                |                |
          +----------------+----------------+
                           |
                           v
                  MEMORY + RAG
             PostgreSQL + pgvector
```

## Model roles

| Component | Model | Role |
|---|---|---|
| Main Assistant | `qwen3.5:9b-q4_K_M` | Conversation, planning, routing, general assistance |
| Fast Worker | `llama3.2:latest` | Simple, lightweight, speed-sensitive subtasks |
| Deep Worker | `gemma4:26b` | Complex reasoning, research, difficult analysis, vision |

Qwen should be the default model. Gemma should not be loaded for every request because the laptop has an RTX 3050 Laptop GPU with 4 GB VRAM and 16 GB RAM.

## How routing works

The flow is:

```text
User
  |
  v
Qwen
  |
  +--> Answer directly
  |
  +--> Use Llama
  |
  +--> Use Gemma
  |
  +--> Use Python
  |
  +--> Use RAG
  |
  +--> Use database
  |
  +--> Use web
  |
  +--> Combine several
```

The important design principle is:

> **Qwen decides what needs to be done, while the backend controls what can actually be executed.**

This is a hybrid agent architecture rather than a simple keyword-based model router.

## Specialist delegation

Give Qwen controlled capabilities such as:

```text
delegate_to_fast_model()
delegate_to_deep_model()
run_python()
search_web()
search_memory()
search_knowledge()
read_file()
query_database()
```

Conceptually, Qwen could request:

```json
{
  "action": "delegate_to_deep_model",
  "reason": "Complex research analysis requires deeper reasoning",
  "task": "Analyze the EEG source localization methodology"
}
```

The backend validates the request, runs Gemma, sends the result back to Qwen, and Qwen produces the final response.

## Examples

### Simple question

```text
User -> Qwen -> answer -> User
```

### Coding task

```text
User
 -> Qwen
 -> read code / run Python
 -> optionally use Llama
 -> Qwen verifies and synthesizes
 -> User
```

### Complex research

```text
User
 -> Qwen
 -> research planning
 -> web/paper retrieval
 -> Gemma 26B for deep analysis
 -> Qwen synthesizes
 -> User
```

### Large document

```text
Documents
 -> RAG retrieval
 -> relevant chunks
 -> Qwen/Gemma analysis
 -> Qwen synthesis
 -> User
```

## Model tasks vs tool tasks

Do not send every request to an LLM.

### Model tasks

- Explain
- Compare
- Summarize
- Write code
- Analyze papers
- Interpret findings
- Plan complex work

### Tool tasks

- Calculate numbers
- Read files
- Search PostgreSQL
- Run Python
- Find files
- Get current weather
- Search the web
- Retrieve memory

For example, a financial calculation should use Python/calculator rather than Gemma simply because it involves reasoning.

## Recommended project structure

```text
personal_ai/
|
+-- main.py
|
+-- assistant/
|   +-- assistant.py
|   +-- planner.py
|   +-- conversation.py
|
+-- models/
|   +-- ollama_client.py
|   +-- qwen.py
|   +-- llama.py
|   +-- gemma.py
|
+-- agent/
|   +-- router.py
|   +-- tool_registry.py
|   +-- executor.py
|
+-- tools/
|   +-- python_tool.py
|   +-- filesystem_tool.py
|   +-- web_tool.py
|   +-- database_tool.py
|   +-- rag_tool.py
|
+-- memory/
|   +-- conversation.py
|   +-- personal.py
|   +-- semantic.py
|
+-- rag/
|   +-- embeddings.py
|   +-- retriever.py
|   +-- reranker.py
|
+-- config/
|   +-- models.yaml
|
+-- frontend/
```

## Model configuration

```yaml
models:
  main:
    name: qwen3.5:9b-q4_K_M
    role: assistant

  fast:
    name: llama3.2:latest
    role: fast_worker

  deep:
    name: gemma4:26b
    role: deep_worker
```

## Basic delegation functions

```python
def delegate_fast(task):
    return ask_ollama(
        "llama3.2:latest",
        task
    )


def delegate_deep(task):
    return ask_ollama(
        "gemma4:26b",
        task
    )
```

## Future multi-step planning

Qwen can eventually produce a structured plan:

```json
{
  "plan": [
    {
      "type": "tool",
      "name": "read_file"
    },
    {
      "type": "delegate",
      "model": "deep",
      "task": "Analyze the extracted data"
    },
    {
      "type": "self",
      "task": "Summarize the findings"
    }
  ]
}
```

The executor then performs each step and returns the collected results to Qwen.

## Hardware-aware behavior

Current laptop constraints:

- NVIDIA RTX 3050 Laptop GPU
- 4 GB VRAM
- 16 GB RAM

Recommended behavior:

1. Keep Qwen as the normal/default model.
2. Use Llama for lightweight tasks.
3. Use Gemma only when deeper reasoning is justified.
4. Avoid keeping all large models active simultaneously.
5. Implement fallbacks.

Suggested fallback:

```text
Gemma unavailable / memory failure
        |
        v
      Qwen

Qwen unavailable
        |
        v
      Llama
```

## Target architecture

```text
                         YOU
                          |
                          v
                +----------------------+
                |    QWEN 3.5 9B      |
                |    MAIN ASSISTANT    |
                |                      |
                | Understand           |
                | Plan                 |
                | Decide               |
                | Coordinate           |
                +----------+-----------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
       TOOLS          LLAMA 3.2        GEMMA 4 26B
       Python         Fast worker      Deep reasoning
       Files                           Research
       Web                             Vision
       RAG
       DB
          |                |                |
          +----------------+----------------+
                           |
                           v
                  MEMORY + RAG
             PostgreSQL + pgvector
```

## Build order

### Phase 1 — Core agent

```text
Qwen
  -> decision
  -> Llama / Gemma
  -> Qwen
  -> User
```

### Phase 2 — Tools

Add:

- Python
- Filesystem
- Web
- PostgreSQL
- RAG

### Phase 3 — Memory

Separate:

- Conversation memory
- Personal memory
- Semantic knowledge
- RAG documents

### Phase 4 — Frontend

React + Tailwind.

### Phase 5 — Voice

Optional Whisper/STT and TTS.

### Phase 6 — Automation

Add scheduled and recurring workflows with appropriate user controls.

## Final design principle

> **One assistant, multiple specialist models.**

The user should not have to choose which model to use. Qwen is the single conversational interface and manager. Llama is the fast worker. Gemma is the deep specialist. Deterministic tools handle calculations, files, databases, web access and other operations. Memory and RAG provide persistent context and knowledge.
