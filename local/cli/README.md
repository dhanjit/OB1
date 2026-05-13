# `ob1` — local Open Brain CLI

Single binary that captures, searches, lists, and fetches thoughts from a
local Postgres+pgvector instance. Embeddings come from a local Ollama server
(default `nomic-embed-text`, 768-dim). No MCP, no Supabase, no cloud calls.

```
ob1 init                          # verify DB connection and Ollama
ob1 capture "Sarah wants to leave her job to consult"
echo "Ship MVP before March 15"  | ob1 capture
ob1 capture --file notes.txt
ob1 search "career change"
ob1 list --days 7 --type idea
ob1 fetch <uuid>
ob1 stats
```

See `../README.md` for full setup.
