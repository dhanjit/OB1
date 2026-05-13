import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Iterable

from . import db, embed, metadata
from .config import Config, load


def _iter_inputs(args: argparse.Namespace) -> Iterable[dict]:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            if args.file.endswith(".jsonl"):
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"skip invalid JSON line: {e}", file=sys.stderr)
                        continue
                    if not obj.get("content"):
                        continue
                    yield obj
            else:
                for line in f:
                    line = line.strip()
                    if line:
                        yield {"content": line}
        return

    if args.text:
        yield {"content": " ".join(args.text)}
        return

    if not sys.stdin.isatty():
        buf = sys.stdin.read().strip()
        if buf:
            yield {"content": buf}
        return


def cmd_init(cfg: Config, args: argparse.Namespace) -> int:
    print(f"DB:     {cfg.db_user}@{cfg.db_host}:{cfg.db_port}/{cfg.db_name}")
    print(f"Embed:  {cfg.embed_model} ({cfg.embed_dim}-dim) via {cfg.ollama_url}")
    print(f"Meta:   {cfg.metadata_provider}")
    try:
        with db.connect(cfg) as conn:
            version = db.ping(conn)
            print(f"OK      {version}")
    except Exception as e:
        print(f"FAIL    DB: {e}", file=sys.stderr)
        return 2
    try:
        embed.ping(cfg)
        print("OK      Ollama reachable")
    except Exception as e:
        print(f"WARN    Ollama: {e}", file=sys.stderr)
        return 0 if args.allow_offline else 3
    return 0


def cmd_capture(cfg: Config, args: argparse.Namespace) -> int:
    inputs = list(_iter_inputs(args))
    if not inputs:
        print("nothing to capture (pass text, --file, or pipe to stdin)", file=sys.stderr)
        return 64

    captured = 0
    errors = 0
    with db.connect(cfg) as conn:
        for i, item in enumerate(inputs, 1):
            content = item["content"]
            preview = content if len(content) <= 80 else content[:77] + "..."
            print(f"[{i}/{len(inputs)}] {preview}")

            try:
                vec = embed.generate(content, cfg)
            except embed.EmbedError as e:
                print(f"   embed failed: {e}", file=sys.stderr)
                errors += 1
                continue

            meta: dict = {
                "source": args.source or item.get("source") or "ob1-cli",
                "embedding_model": cfg.embed_model,
                "embedded_at": datetime.now(timezone.utc).isoformat(),
            }
            if isinstance(item.get("metadata"), dict):
                meta.update(item["metadata"])
            if not args.no_metadata and cfg.metadata_provider != "none":
                meta.update(metadata.extract(content, cfg) or {})

            try:
                result = db.upsert(conn, content, vec, meta)
                print(f"   captured {result['id']}")
                captured += 1
            except Exception as e:
                print(f"   db failed: {e}", file=sys.stderr)
                errors += 1
    print(f"\n{captured} captured, {errors} errors")
    return 0 if errors == 0 else 1


def cmd_search(cfg: Config, args: argparse.Namespace) -> int:
    try:
        vec = embed.generate(args.query, cfg)
    except embed.EmbedError as e:
        print(f"embed failed: {e}", file=sys.stderr)
        return 2

    with db.connect(cfg) as conn:
        results = db.search(conn, vec, args.threshold, args.limit, None)

    if args.json:
        print(json.dumps([_serialize(r) for r in results], default=str, indent=2))
        return 0

    if not results:
        print(f"no matches above threshold {args.threshold} for {args.query!r}")
        return 0

    for i, r in enumerate(results, 1):
        m = r.get("metadata") or {}
        pct = r["similarity"] * 100
        topics = ", ".join(m.get("topics") or [])
        people = ", ".join(m.get("people") or [])
        head = f"--- {i}. {pct:.1f}% match  [{r['id']}]"
        print(head)
        print(f"   {r['created_at']:%Y-%m-%d}  type={m.get('type', '?')}", end="")
        if topics:
            print(f"  topics={topics}", end="")
        if people:
            print(f"  people={people}", end="")
        print()
        print(f"   {r['content']}")
        print()
    return 0


def cmd_fetch(cfg: Config, args: argparse.Namespace) -> int:
    with db.connect(cfg) as conn:
        row = db.fetch(conn, args.id)
    if not row:
        print(f"not found: {args.id}", file=sys.stderr)
        return 1
    print(json.dumps(_serialize(row), default=str, indent=2))
    return 0


def cmd_list(cfg: Config, args: argparse.Namespace) -> int:
    with db.connect(cfg) as conn:
        rows = db.list_recent(conn, args.limit, args.type, args.topic, args.person, args.days)
    if args.json:
        print(json.dumps([_serialize(r) for r in rows], default=str, indent=2))
        return 0
    if not rows:
        print("no thoughts found")
        return 0
    for i, r in enumerate(rows, 1):
        m = r.get("metadata") or {}
        topics = ", ".join(m.get("topics") or [])
        suffix = f" — {topics}" if topics else ""
        print(f"{i:>3}. [{r['created_at']:%Y-%m-%d}] ({m.get('type', '?')}{suffix})")
        print(f"     {r['id']}")
        print(f"     {r['content']}")
    return 0


def cmd_stats(cfg: Config, args: argparse.Namespace) -> int:
    with db.connect(cfg) as conn:
        s = db.stats(conn)
    if args.json:
        print(json.dumps(s, default=str, indent=2))
        return 0
    print(f"total:   {s['total']}")
    if s["first"] and s["last"]:
        print(f"range:   {s['first']:%Y-%m-%d} → {s['last']:%Y-%m-%d}")
    if s["types"]:
        print("\ntypes:")
        for k, v in sorted(s["types"].items(), key=lambda x: -x[1]):
            print(f"  {v:>4}  {k}")
    if s["topics"]:
        print("\ntop topics:")
        for k, v in sorted(s["topics"].items(), key=lambda x: -x[1])[:10]:
            print(f"  {v:>4}  {k}")
    if s["people"]:
        print("\npeople:")
        for k, v in sorted(s["people"].items(), key=lambda x: -x[1])[:10]:
            print(f"  {v:>4}  {k}")
    return 0


def _serialize(row: dict) -> dict:
    return {k: v for k, v in row.items()}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ob1", description="Local Open Brain CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="verify DB + Ollama")
    sp.add_argument("--allow-offline", action="store_true", help="treat missing Ollama as warning, not error")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("capture", help="capture a thought")
    sp.add_argument("text", nargs="*", help="thought text (or use --file or stdin)")
    sp.add_argument("--file", help="read .txt (one per line) or .jsonl")
    sp.add_argument("--source", help="metadata.source label")
    sp.add_argument("--no-metadata", action="store_true", help="skip LLM metadata extraction")
    sp.set_defaults(func=cmd_capture)

    sp = sub.add_parser("search", help="semantic search")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--threshold", type=float, default=0.5)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("fetch", help="fetch one thought by id")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_fetch)

    sp = sub.add_parser("list", help="list recent thoughts")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--type")
    sp.add_argument("--topic")
    sp.add_argument("--person")
    sp.add_argument("--days", type=int)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("stats", help="summary statistics")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load()
    return args.func(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
