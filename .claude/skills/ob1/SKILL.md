---
name: ob1
description: |
  Local Open Brain memory. Use whenever the user wants to save, search, list,
  or look up captured thoughts in their personal knowledge base — phrases like
  "remember this", "save this", "what did I note about X", "search my brain",
  "list my recent thoughts", "stats on my notes". Fires only when the local
  `ob1` CLI is available (Postgres + pgvector + Ollama running locally). All
  operations stay on the user's machine — no network calls to Supabase or any
  third-party service.
version: 0.1.0
---

# ob1 — local memory CLI

This repo replaces the cloud OB1 (Supabase + remote MCP) with a fully local
stack. The user runs Postgres+pgvector via Podman/Docker compose and Ollama
for embeddings. You interact with it through the `ob1` CLI via Bash.

## When to fire

- "Save / remember / capture this: …" → `ob1 capture`
- "What did I note about / capture about / save about …" → `ob1 search`
- "Show / list my recent thoughts" → `ob1 list`
- "How many thoughts do I have" / stats questions → `ob1 stats`
- "Open / fetch / read thought <uuid>" → `ob1 fetch`

Do NOT fire for general web search, code search, or anything not stored
in the local brain.

## Preflight

Before the first call in a session, run `ob1 init`. If it fails:

- DB error → tell the user to `cd local && podman compose up -d` (or
  `docker compose up -d`) and confirm `OB1_DB_*` env vars are exported.
- Ollama error → tell the user to `ollama serve` and `ollama pull nomic-embed-text`,
  or pass `--allow-offline` for read-only inspection.

## Commands

```bash
ob1 capture "Sarah said she's thinking about leaving her job to consult"
echo "Decided to ship MVP before March 15" | ob1 capture --source meeting
ob1 capture --file ./notes.txt --source journal
ob1 search "career change" --limit 5
ob1 search "API redesign" --threshold 0.3 --json
ob1 list --days 7 --type idea --limit 20
ob1 list --person Sarah
ob1 fetch <uuid>
ob1 stats
```

Flags worth knowing:

- `--no-metadata` on `capture` skips the optional LLM enrichment step
- `--json` on `search` / `list` / `stats` / `fetch` gives parseable output
  when you need to feed results into another step

## Process

1. Run `ob1 init` if you haven't this session. If the DB ping fails, surface
   the exact compose command — don't try to start containers yourself unless
   the user asked.
2. For capture: prefer one thought per call. Multi-line input is fine via
   `--file` or stdin, one thought per line.
3. For search: start at the default 0.5 threshold; if zero hits, retry once
   at 0.3 and tell the user you widened it.
4. Always echo the captured UUID(s) back so the user can `ob1 fetch` later.
5. After capture, do not re-run search to "verify" unless the user asked —
   the upsert is its own confirmation.

## Output

For interactive replies, summarize in plain prose (e.g. "Captured as
<uuid>. Topics: career, decisions.") and only paste raw CLI output when
the user asks to see it.

## Notes

- Embedding dim is fixed at install time (default 768, nomic-embed-text).
  Mixing models corrupts similarity — if the user wants to switch models,
  the DB volume has to be reset. Warn them before suggesting it.
- The local stack has no auth. Treat the DB and Ollama as trusted localhost
  services; never expose them on the network.
- This skill never makes network calls on its own — the CLI does, only to
  127.0.0.1.
