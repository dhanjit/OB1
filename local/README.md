# Open Brain — Local, No-MCP Edition

A fully local OB1 setup for environments where you can't use MCP and can't
ship data to third parties like Supabase. Everything runs on `localhost`:

- **Postgres + pgvector** in a container (Docker or Podman) — your thoughts table
- **Ollama** on the host — local embeddings (default: `nomic-embed-text`, 768-dim)
- **`ob1` Python CLI** — capture / search / list / fetch / stats
- **Claude Code skill** (`.claude/skills/ob1/`) — so Claude invokes the CLI for
  natural-language requests like "remember this" or "what did I note about X"

No cloud accounts, no API keys required for the default path. Optional LLM
metadata enrichment (Anthropic / OpenAI / Gemini) is off by default and only
activates if you set `OB1_METADATA_PROVIDER` and the matching key.

---

## Prerequisites

- Docker **or** Podman (with `podman compose` / `docker compose`)
- Python 3.10+ and `pip`
- Ollama running on the host: <https://ollama.com>

> Podman users: `podman compose` is a drop-in for the `docker compose` commands
> below. If you prefer `podman-compose`, that works too — the file is plain
> Compose v3.

---

## 1. Start the database

```bash
cd local
cp .env.example .env       # adjust port/credentials if you want
docker compose up -d       # or: podman compose up -d
docker compose logs -f postgres   # wait for "database system is ready"
```

The container exposes Postgres on `127.0.0.1:5433` (override with `OB1_DB_PORT`)
and runs the init scripts in `db/init/` on first boot — pgvector extension,
`thoughts` table, `match_thoughts` and `upsert_thought` functions.

> **Wiping the DB:** `docker compose down -v` drops the volume. The init
> scripts only run on a fresh volume, so this is the only way to change the
> embedding dimension after the fact.

## 2. Start Ollama and pull the model

```bash
ollama serve            # or run the Ollama app
ollama pull nomic-embed-text
```

If you want a different model, pull it and update `OB1_EMBED_MODEL` /
`OB1_EMBED_DIM` in `.env`. The DB schema's `vector(N)` is fixed at first
boot — if dims change you must also edit `db/init/02-schema.sql` and
`db/init/03-functions.sql` and `docker compose down -v` to reapply.

| Model | Dim | Notes |
| ----- | --- | ----- |
| `nomic-embed-text` (default) | 768 | Smallest, fastest |
| `mxbai-embed-large` | 1024 | Best discrimination |
| `rjmalagon/gte-qwen2-1.5b-instruct-embed-f16` | 1536 | Matches cloud-OB1 schema |

## 3. Install the CLI

```bash
cd cli
pip install -e .
# or, if you'd rather not install: PYTHONPATH=src python -m ob.cli ...
```

Export the env (or `source ../.env`):

```bash
set -a; source ../.env; set +a
ob1 init
```

You should see:

```
DB:     openbrain@127.0.0.1:5433/openbrain
Embed:  nomic-embed-text (768-dim) via http://127.0.0.1:11434
Meta:   none
OK      PostgreSQL 16...
OK      Ollama reachable
```

## 4. Capture, search, list, stats

```bash
ob1 capture "Sarah is thinking about leaving her job to start a consultancy"
ob1 capture --file my-notes.txt --source journal
ob1 search "career change"
ob1 list --days 7
ob1 stats
ob1 fetch <uuid>
```

## 5. Use it from Claude Code

The skill at `.claude/skills/ob1/SKILL.md` wires the CLI into Claude Code.
Once the CLI is on your `PATH` and the stack is up, phrases like:

- "Remember this: ..."
- "What did I note about ...?"
- "Show me my recent ideas"

will route through `ob1 capture` / `ob1 search` / `ob1 list` automatically.
No MCP config, no remote connector.

---

## Optional: LLM metadata enrichment

By default, captures store `source`, `embedding_model`, `embedded_at` and
nothing else — embeddings power semantic search regardless. If you want
the same `people / topics / action_items / type` enrichment as cloud OB1,
set in `.env`:

```bash
OB1_METADATA_PROVIDER=anthropic       # or openai, gemini
OB1_METADATA_MODEL=claude-haiku-4-5
ANTHROPIC_API_KEY=...
```

The CLI will call that provider for each capture. Pass `--no-metadata` to
override per-call.

## Compatibility with existing recipes

The schema, table name (`thoughts`), function names (`match_thoughts`,
`upsert_thought`), and column shape mirror the cloud version exactly. Recipes
in `../recipes/` that use the Postgres REST or RPC endpoints can be re-pointed
at this DB by changing their connection string — no schema rewrite. The only
difference is `vector(768)` vs the cloud default `vector(1536)`; pick a matching
embedding model if you want them to interop.

## Security

- DB and Ollama bind to `127.0.0.1` only. Do not publish them on a network.
- The CLI accepts any user that can read `OB1_DB_PASSWORD` — keep `.env`
  out of git (it already is, via `.gitignore`).
- This stack does no outbound HTTP unless you enable the optional metadata
  provider.

## Troubleshooting

**`ob1 init` says "cannot reach Ollama"** — start `ollama serve`. On
macOS the Ollama app starts it automatically. If you're using Podman and
Ollama is in another container, set `OB1_OLLAMA_URL` accordingly.

**`embedding dim X != configured OB1_EMBED_DIM`** — the model you pulled
emits a different dimension than the schema. Either pick a matching model
or `docker compose down -v` and edit `db/init/02-schema.sql` to the right dim.

**`relation "thoughts" does not exist`** — the init scripts only run on a
fresh volume. If you started Postgres before mounting `db/init/`, run
`docker compose down -v && docker compose up -d`.

**`pgvector` extension missing** — the compose file pins the `pgvector/pgvector:pg16`
image which bundles the extension. If you swapped images, `CREATE EXTENSION vector`
will fail; switch back or install the extension manually.
