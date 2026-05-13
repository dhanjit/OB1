"""Optional LLM metadata extraction.

The default provider is "none" — captures store only the source label and
embedding model, no LLM enrichment. To enable richer metadata (people,
topics, action_items, type), set OB1_METADATA_PROVIDER and the matching
API key. Designed so an air-gapped office can still capture and search
without any third-party call.
"""

import json
import os
from typing import Any

import requests

from .config import Config

SYSTEM_PROMPT = """Extract metadata from the user's captured thought. Return JSON with:
- "people": array of people mentioned (empty if none)
- "action_items": array of implied to-dos (empty if none)
- "dates_mentioned": array of dates YYYY-MM-DD (empty if none)
- "topics": array of 1-3 short topic tags (always at least one)
- "type": one of "observation", "task", "idea", "reference", "person_note"
Only extract what's explicitly there. Return JSON only, no prose."""


def extract(text: str, cfg: Config) -> dict[str, Any]:
    provider = cfg.metadata_provider
    if provider in ("none", "", None):
        return {}
    try:
        if provider == "anthropic":
            return _anthropic(text, cfg)
        if provider == "openai":
            return _openai(text, cfg)
        if provider == "gemini":
            return _gemini(text, cfg)
    except Exception as e:
        return {"_metadata_error": str(e)}
    return {"_metadata_error": f"unknown provider: {provider}"}


def _anthropic(text: str, cfg: Config) -> dict[str, Any]:
    if not cfg.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    model = cfg.metadata_model or "claude-haiku-4-5"
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": cfg.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 512,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": text}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    content = "".join(b.get("text", "") for b in body.get("content", []))
    return _safe_json(content)


def _openai(text: str, cfg: Config) -> dict[str, Any]:
    if not cfg.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    model = cfg.metadata_model or "gpt-4o-mini"
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {cfg.openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _safe_json(resp.json()["choices"][0]["message"]["content"])


def _gemini(text: str, cfg: Config) -> dict[str, Any]:
    if not cfg.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    model = cfg.metadata_model or "gemini-2.5-flash"
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        params={"key": cfg.google_api_key},
        json={
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    parts = body["candidates"][0]["content"]["parts"]
    return _safe_json("".join(p.get("text", "") for p in parts))


def _safe_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {"_metadata_error": "non-JSON response", "_raw": raw[:500]}
