import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .config import Config


@contextmanager
def connect(cfg: Config) -> Iterator[psycopg.Connection]:
    with psycopg.connect(cfg.dsn, row_factory=dict_row) as conn:
        yield conn


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"


def upsert(conn: psycopg.Connection, content: str, embedding: list[float], metadata: dict[str, Any]) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT upsert_thought(%s, %s::jsonb) AS result",
            (content, json.dumps({"metadata": metadata})),
        )
        row = cur.fetchone()
        result = row["result"]
        thought_id = result["id"]
        cur.execute(
            "UPDATE thoughts SET embedding = %s::vector WHERE id = %s",
            (_vec_literal(embedding), thought_id),
        )
    conn.commit()
    return result


def search(conn: psycopg.Connection, embedding: list[float], threshold: float, limit: int, filter_: dict[str, Any] | None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM match_thoughts(%s::vector, %s, %s, %s::jsonb)",
            (_vec_literal(embedding), threshold, limit, json.dumps(filter_ or {})),
        )
        return list(cur.fetchall())


def fetch(conn: psycopg.Connection, thought_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, content, metadata, created_at, updated_at FROM thoughts WHERE id = %s",
            (thought_id,),
        )
        return cur.fetchone()


def list_recent(conn: psycopg.Connection, limit: int, type_: str | None, topic: str | None, person: str | None, days: int | None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if type_:
        clauses.append("metadata @> %s::jsonb")
        params.append(json.dumps({"type": type_}))
    if topic:
        clauses.append("metadata @> %s::jsonb")
        params.append(json.dumps({"topics": [topic]}))
    if person:
        clauses.append("metadata @> %s::jsonb")
        params.append(json.dumps({"people": [person]}))
    if days:
        clauses.append("created_at >= now() - (%s || ' days')::interval")
        params.append(str(days))

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT id, content, metadata, created_at "
        f"FROM thoughts {where} "
        "ORDER BY created_at DESC LIMIT %s"
    )
    params.append(limit)
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def stats(conn: psycopg.Connection) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM thoughts")
        total = cur.fetchone()["n"]
        cur.execute("SELECT min(created_at) AS first, max(created_at) AS last FROM thoughts")
        date_range = cur.fetchone()
        cur.execute("SELECT metadata FROM thoughts")
        rows = cur.fetchall()
    types: dict[str, int] = {}
    topics: dict[str, int] = {}
    people: dict[str, int] = {}
    for r in rows:
        m = r["metadata"] or {}
        t = m.get("type")
        if isinstance(t, str):
            types[t] = types.get(t, 0) + 1
        for tag in m.get("topics", []) or []:
            if isinstance(tag, str):
                topics[tag] = topics.get(tag, 0) + 1
        for p in m.get("people", []) or []:
            if isinstance(p, str):
                people[p] = people.get(p, 0) + 1
    return {"total": total, "first": date_range["first"], "last": date_range["last"], "types": types, "topics": topics, "people": people}


def ping(conn: psycopg.Connection) -> str:
    with conn.cursor() as cur:
        cur.execute("SELECT version() AS v")
        return cur.fetchone()["v"]
