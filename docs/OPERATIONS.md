# Operations Guide

Configuring, running and evaluating the WISP monitoring assistant. For what the project is and why it's built this way, see the main [README](../README.md).

## Contents

- [Building the index](#building-the-index)
- [Switching LLM providers](#switching-llm-providers)
- [Running with Docker](#running-with-docker)
- [Command reference](#command-reference)
- [Evaluation](#evaluation)
- [Troubleshooting](#troubleshooting)

## Building the index

`chroma_db/` and `events.db` are generated and not committed, so a fresh clone must build them before the assistant can answer anything.


python wisp_rag.py ingest \
  --log day1.log@2026-09-14 \
  --log day2.log@2026-09-15 \
  --notes notes \
  --playbooks playbooks
```

### Ingest options

| Option | Purpose |
|---|---|
| `--log FILE` or `FILE@YYYY-MM-DD` | Log file to ingest; repeatable |
| `--date` | Default log date if not given per file |
| `--iface-map` | Map interfaces to towers, e.g. `ether2=A,ether3=B` — only needed if the log has link up/down lines |
| `--window` | Minutes per log chunk window (default 15) |
| `--max-lines` | Maximum log lines per chunk (default 40) |
| `--notes` | Folder of incident notes (`.md`) |
| `--playbooks` | Folder of playbooks (`.md`) |
| `--events-db` | SQLite file for exact counts (default `events.db`) |
| `--model` | Embedding model (default `bge-small`) |
| `--db` | Index folder (default `chroma_db`) |

Re-run the whole command after editing notes, playbooks or logs.

## Switching LLM providers

The assistant calls the model through a single function, `ask_llm()` in `wisp_assistant.py`. The provider is chosen entirely by environment variables — no code changes.

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `ollama`, `kimi`, `gemini`, `openrouter`, `openai` or `anthropic` |
| `<PROVIDER>_MODEL` | e.g. `OLLAMA_MODEL`, `KIMI_MODEL`, `GEMINI_MODEL` |
| `<PROVIDER>_API_KEY` | e.g. `MOONSHOT_API_KEY`, `GEMINI_API_KEY` — not needed for Ollama |
| `OLLAMA_BASE_URL` | Override if Ollama isn't at `http://localhost:11434` |

### Default: local Ollama


# .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=gemma4:e4b
```

Run `ollama pull gemma4:e4b` once and make sure Ollama is running. Nothing leaves the machine with this setup.

### Hosted API

```
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_MODEL=<model id>
ANTHROPIC_API_KEY=<key>
```

The same pattern applies to `kimi`, `gemini`, `openrouter` and `openai`.

### Checking configuration

```bash
python wisp_assistant.py check-keys                   # Which providers have a usable key and model
python wisp_assistant.py models --provider <name>     # List model ids
```

`check-keys` reports whether variables are set; it never prints key values.

## Running with Docker

```bash
docker compose up
```

Then open http://localhost:7860.

The image packages the app only — RAG pipeline, SQLite and Chroma stores, Gradio UI. **The LLM always stays outside the container.**

### Reaching Ollama on the host

`docker-compose.yml` sets:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

`host.docker.internal` resolves automatically on Docker Desktop for Mac and Windows. On Linux, the compose file adds `extra_hosts: host.docker.internal:host-gateway` so the same hostname works there.

`.env` is bind-mounted into the container, so `LLM_PROVIDER`, model names and API keys come from the same file whether you run locally or in Docker. Only `OLLAMA_BASE_URL` differs, which is why it lives in `docker-compose.yml` rather than `.env`.

To point the container at a hosted API instead, just change `.env`. No compose changes are needed — the container reaches the internet directly for those providers.

### About the image

- CPU-only torch, since the container runs embedding inference and never the LLM. The default CUDA wheel would pull roughly 5 GB of unused NVIDIA libraries.
- The embedding model is downloaded at build time and `HF_HUB_OFFLINE=1` is set, so the running container needs no internet.
- The whole project is bind-mounted, so code changes need no rebuild and the Chroma and SQLite stores persist on the host, shared with local runs.
- A healthcheck polls the UI every 30 seconds.

## Command reference

### `wisp_assistant.py`

| Command | Purpose |
|---|---|
| `ask "<question>"` | Answer one question |
| `chat` | Ask several questions in the terminal |
| `ui` | Browser chat window (needs gradio) |
| `check-keys` | Show which providers are configured |
| `models --provider <name>` | List available model ids |
| `compare "<q>" --with <p> --with <p>` | Same question across providers |
| `compare-tests --tests <file> --with <p> --min-pass 0.9` | Run a test file across providers, write a report |

### `wisp_rag.py`

| Command | Purpose |
|---|---|
| `ingest` | Build or rebuild the index |
| `search "<question>" [-k N]` | Show the top chunks |
| `make-tests --key <file>` | Draft retrieval tests from an answer key |
| `eval --tests <file>` | Score retrieval |

`search` options: `--tower`, `--type` (log, incident or playbook), `--incident-type`, `--date`, `--from`, `--to`, `--mode` (hybrid or vector), `--auto` (read filters from the question).

### `wisp_query.py`

Run directly to execute its self-test:

```bash
python wisp_query.py
```

### `wisp_log_tools.py`

| Command | Purpose |
|---|---|
| `validate` | Check a log file and optional answer key |
| `chunks` | Write chunks with metadata as JSONL |

## Evaluation

### Retrieval

```bash
python wisp_rag.py eval --tests retrieval_tests.json
```

| Option | Purpose |
|---|---|
| `-k` | Chunks retrieved per question (default 5) |
| `--mode` | `hybrid` (default) or `vector` |
| `--no-filters` | Ignore the filters in the tests — shows how much they contribute |
| `--auto-filters` | Extract filters from each question with `wisp_query.py` instead |

Comparing a normal run against `--no-filters` is how the value of rule-based filtering is measured.

### Answers

```bash
python wisp_assistant.py compare-tests --tests assistant_tests.json --with ollama --min-pass 0.9
```

Each test can specify `expect_all`, `expect_any` and `forbid` strings. Results are written to a report file. Citation problems are reported alongside each answer.

### Regenerating answer keys

`day1_key.json` and `day2_key.json` are hand-written ground truth derived from the logs: incident timelines, affected customers, routine event counts and expected answers. Edit them by hand when the sample logs change, then regenerate the retrieval tests:

```bash
python wisp_rag.py make-tests --key day1_key.json --out retrieval_tests.json
```

## Troubleshooting

### Answers cite nothing, or the assistant says no data exists

The index probably hasn't been built. Run the ingest command above and check that `chroma_db/` and `events.db` now exist.

### Wrong day's data in the answer

Filter extraction may have missed the date. Check what it found:

```bash
python wisp_query.py
```

Then try the question with an explicit filter:

```bash
python wisp_rag.py search "<question>" --date 2026-09-14
```

### Container can't reach Ollama

The container reaches the host through `host.docker.internal`, not `localhost`. Confirm Ollama is running on the host and listening, and that `OLLAMA_BASE_URL` in `docker-compose.yml` hasn't been overridden by a value in `.env`.

### Provider errors or missing key

```bash
python wisp_assistant.py check-keys
```

Confirms whether the variables for each provider are set and a model is configured.

### Edited notes or playbooks but answers haven't changed

The index is built once and stored. Re-run the ingest command to rebuild it.