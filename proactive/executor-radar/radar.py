#!/usr/bin/env python3
"""Deterministic change detector for AI executor/work-agent release sources.

No LLM is used here. Vendor changes are stored as observations/candidates only.
"""

from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "sources.json"
STATE_PATH = ROOT / "state.json"
SNAPSHOT_DIR = ROOT / "snapshots"
EVENTS_PATH = ROOT / "events.jsonl"
PENDING_ALERT_PATH = ROOT / "pending_alert.md"
MAX_NORMALIZED_CHARS = 400_000
MAX_DIFF_CHARS = 12_000


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = re.sub(r"\s+", " ", html.unescape(data)).strip()
        if text:
            self.parts.append(text)


def normalize(raw: bytes, content_type: str) -> str:
    text = raw.decode("utf-8", errors="replace")
    if "html" in content_type.lower() or "xml" in content_type.lower() or "<html" in text[:1000].lower() or "<?xml" in text[:200].lower():
        parser = TextExtractor()
        parser.feed(text)
        lines = parser.parts
    else:
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
    normalized = "\n".join(lines)
    return normalized[:MAX_NORMALIZED_CHARS] + "\n"


def fetch(url: str) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ai-ops-memory-executor-radar/1.0 (+GitHub Actions; deterministic monitoring)",
            "Accept": "text/html,application/xml,text/xml,text/plain,application/json;q=0.9,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        raw = resp.read(5_000_000)
        content_type = resp.headers.get("Content-Type", "")
    return normalize(raw, content_type), content_type


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def append_event(event: dict) -> None:
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def diff_added(old: str, new: str) -> tuple[str, str]:
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile="previous",
            tofile="current",
            lineterm="",
            n=2,
        )
    )
    diff_text = "\n".join(diff_lines)
    added = "\n".join(
        line[1:] for line in diff_lines if line.startswith("+") and not line.startswith("+++")
    )
    return diff_text[:MAX_DIFF_CHARS], added


def matched_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    return sorted({term for term in terms if term.lower() in lowered})


def main() -> int:
    config = load_json(CONFIG_PATH, {})
    sources = config.get("sources", [])
    terms = config.get("high_priority_terms", [])
    state = load_json(STATE_PATH, {"schema_version": "1.0", "sources": {}})
    source_state = state.setdefault("sources", {})
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    material_change = False
    alert_sections: list[str] = []
    successes = 0

    if PENDING_ALERT_PATH.exists():
        PENDING_ALERT_PATH.unlink()

    for source in sources:
        slug = source["slug"]
        url = source["url"]
        snapshot_path = SNAPSHOT_DIR / f"{slug}.txt"
        previous = source_state.get(slug, {})
        previous_sha = previous.get("sha256")

        try:
            normalized, content_type = fetch(url)
            successes += 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            material_change = True
            append_event(
                {
                    "timestamp": now,
                    "status": "FETCH_FAILED",
                    "slug": slug,
                    "name": source["name"],
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}"[:1000],
                }
            )
            continue

        current_sha = sha256(normalized)
        if not previous_sha or not snapshot_path.exists():
            snapshot_path.write_text(normalized, encoding="utf-8")
            source_state[slug] = {
                "sha256": current_sha,
                "baseline_at": now,
                "last_changed_at": now,
                "url": url,
                "content_type": content_type,
            }
            append_event(
                {
                    "timestamp": now,
                    "status": "BASELINE",
                    "slug": slug,
                    "name": source["name"],
                    "url": url,
                    "sha256": current_sha,
                }
            )
            material_change = True
            continue

        if current_sha == previous_sha:
            continue

        old_text = snapshot_path.read_text(encoding="utf-8")
        diff_text, added = diff_added(old_text, normalized)
        hits = matched_terms(added or normalized, terms)
        status = "HIGH_PRIORITY_CANDIDATE" if hits else "CHANGED"
        event = {
            "timestamp": now,
            "status": status,
            "slug": slug,
            "name": source["name"],
            "vendor": source.get("vendor"),
            "url": url,
            "previous_sha256": previous_sha,
            "sha256": current_sha,
            "matched_terms": hits,
            "diff_excerpt": diff_text,
        }
        append_event(event)
        material_change = True

        if hits:
            alert_sections.append(
                f"## {source['name']}\n\n"
                f"Source: {url}\n\n"
                f"Matched terms: {', '.join(hits)}\n\n"
                f"```diff\n{diff_text[:6000]}\n```\n"
            )

        snapshot_path.write_text(normalized, encoding="utf-8")
        source_state[slug] = {
            "sha256": current_sha,
            "baseline_at": previous.get("baseline_at", now),
            "last_changed_at": now,
            "url": url,
            "content_type": content_type,
        }

    if successes == 0 and sources:
        print("All configured sources failed to fetch", file=sys.stderr)
        return 2

    if material_change:
        STATE_PATH.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if alert_sections:
        PENDING_ALERT_PATH.write_text(
            "# AI Executor Radar — high-priority candidate changes\n\n"
            "These are deterministic keyword-triage candidates, not verified capability claims.\n\n"
            + "\n".join(alert_sections),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "sources": len(sources),
                "successful_fetches": successes,
                "material_repository_change": material_change,
                "high_priority_candidates": len(alert_sections),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
