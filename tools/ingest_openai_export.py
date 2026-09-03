#!/usr/bin/env python3
"""Ingest an official ChatGPT data export into a provenance-first local archive.

The official export ZIP/JSON remains authoritative source evidence. This tool never
calls ChatGPT or any private endpoint; it only processes files the user obtained
through ChatGPT's supported Data Export flow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "chatgpt-official-export-ingest-v1"
CONVERSATIONS_RE = re.compile(r"^conversations(?:[-_]?\d+)?\.json$", re.I)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_component(value: str, fallback: str = "unknown") -> str:
    value = (value or "").strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = value.strip("._")
    return value[:160] or fallback


def canonical_json_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def extract_conversations(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("conversations", "items", "data"):
            value = obj.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    raise ValueError("unsupported conversations JSON envelope")


def conversation_id(conv: dict[str, Any], fallback_seed: str) -> str:
    for key in ("id", "conversation_id", "conversationId"):
        value = conv.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "derived-" + hashlib.sha256(fallback_seed.encode("utf-8")).hexdigest()[:24]


def message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if isinstance(parts, list):
        out: list[str] = []
        for part in parts:
            if isinstance(part, str):
                out.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str):
                    out.append(text)
        if out:
            return "\n".join(out)
    text = content.get("text")
    return text if isinstance(text, str) else ""


def selected_branch(conv: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = conv.get("mapping")
    if not isinstance(mapping, dict) or not mapping:
        return []
    current = conv.get("current_node") or conv.get("currentNode")
    if not isinstance(current, str) or current not in mapping:
        candidates: list[tuple[float, str]] = []
        for node_id, node in mapping.items():
            if not isinstance(node, dict):
                continue
            children = node.get("children")
            if children:
                continue
            msg = node.get("message")
            ts = 0.0
            if isinstance(msg, dict) and isinstance(msg.get("create_time"), (int, float)):
                ts = float(msg["create_time"])
            candidates.append((ts, str(node_id)))
        if not candidates:
            return []
        current = max(candidates)[1]

    path: list[dict[str, Any]] = []
    seen: set[str] = set()
    while isinstance(current, str) and current in mapping and current not in seen:
        seen.add(current)
        node = mapping[current]
        if not isinstance(node, dict):
            break
        path.append(node)
        parent = node.get("parent")
        current = parent if isinstance(parent, str) else None
    path.reverse()
    return path


def render_markdown(conv: dict[str, Any]) -> str:
    title = conv.get("title") if isinstance(conv.get("title"), str) else "Untitled"
    lines = [f"# {title}", "", "> Derived readable view. The raw official-export JSON is authoritative.", ""]
    for node in selected_branch(conv):
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue
        author = msg.get("author")
        role = author.get("role") if isinstance(author, dict) else None
        if not isinstance(role, str):
            role = "unknown"
        text = message_text(msg)
        if not text and role not in {"user", "assistant", "system", "tool"}:
            continue
        lines += [f"## {role}", "", text, ""]
    return "\n".join(lines).rstrip() + "\n"


@dataclass
class SourceBlob:
    name: str
    data: bytes


def source_blobs(input_path: Path) -> list[SourceBlob]:
    if input_path.is_dir():
        blobs = []
        for p in sorted(input_path.rglob("*.json")):
            if CONVERSATIONS_RE.match(p.name):
                blobs.append(SourceBlob(str(p.relative_to(input_path)).replace(os.sep, "/"), p.read_bytes()))
        return blobs
    if zipfile.is_zipfile(input_path):
        blobs = []
        with zipfile.ZipFile(input_path, "r") as zf:
            for name in sorted(zf.namelist()):
                if CONVERSATIONS_RE.match(Path(name).name):
                    blobs.append(SourceBlob(name, zf.read(name)))
        return blobs
    if input_path.suffix.lower() == ".json":
        return [SourceBlob(input_path.name, input_path.read_bytes())]
    raise ValueError("input must be an official export ZIP, a conversations JSON file, or a directory containing them")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def ingest(input_path: Path, output_dir: Path) -> dict[str, Any]:
    blobs = source_blobs(input_path)
    if not blobs:
        raise ValueError("no conversations*.json files found")

    output_dir.mkdir(parents=True, exist_ok=True)
    source_dir = output_dir / "source" / "official-export"
    conversations_dir = output_dir / "conversations"
    indexes_dir = output_dir / "indexes"
    reports_dir = output_dir / "reports"
    source_dir.mkdir(parents=True, exist_ok=True)
    conversations_dir.mkdir(parents=True, exist_ok=True)
    indexes_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    source_manifest: list[dict[str, Any]] = []
    versions: dict[str, list[dict[str, Any]]] = {}

    for blob in blobs:
        raw_sha = sha256_bytes(blob.data)
        preserved_name = f"{raw_sha}.json"
        atomic_write(source_dir / preserved_name, blob.data)
        obj = json.loads(blob.data.decode("utf-8"))
        convs = extract_conversations(obj)
        source_manifest.append({
            "source_name": blob.name,
            "sha256": raw_sha,
            "bytes": len(blob.data),
            "preserved_path": f"source/official-export/{preserved_name}",
            "conversation_count": len(convs),
        })
        for ordinal, conv in enumerate(convs):
            seed = f"{blob.name}:{ordinal}:{conv.get('title','')}:{conv.get('create_time','')}"
            cid = conversation_id(conv, seed)
            cbytes = canonical_json_bytes(conv)
            csha = sha256_bytes(cbytes)
            versions.setdefault(cid, []).append({
                "sha256": csha,
                "bytes": len(cbytes),
                "object": conv,
                "source_name": blob.name,
                "ordinal": ordinal,
            })

    index_records: list[dict[str, Any]] = []
    conflicts = 0
    for cid in sorted(versions):
        unique: dict[str, dict[str, Any]] = {v["sha256"]: v for v in versions[cid]}
        vals = list(unique.values())
        vals.sort(key=lambda v: (
            float(v["object"].get("update_time") or 0) if isinstance(v["object"].get("update_time"), (int, float)) else 0.0,
            v["sha256"],
        ))
        chosen = vals[-1]
        conv = chosen["object"]
        cdir = conversations_dir / safe_component(cid)
        cdir.mkdir(parents=True, exist_ok=True)
        revisions_dir = cdir / "source-revisions"
        revisions_dir.mkdir(parents=True, exist_ok=True)
        for v in vals:
            atomic_write(revisions_dir / f"{v['sha256']}.json", canonical_json_bytes(v["object"]))
        atomic_write(cdir / "conversation.raw.json", canonical_json_bytes(conv))
        atomic_write(cdir / "conversation.selected.md", render_markdown(conv).encode("utf-8"))
        if len(vals) > 1:
            conflicts += 1
        index_records.append({
            "conversation_id": cid,
            "title": conv.get("title"),
            "create_time": conv.get("create_time"),
            "update_time": conv.get("update_time"),
            "current_node": conv.get("current_node") or conv.get("currentNode"),
            "raw_sha256": chosen["sha256"],
            "revision_count": len(vals),
            "raw_path": f"conversations/{safe_component(cid)}/conversation.raw.json",
            "markdown_path": f"conversations/{safe_component(cid)}/conversation.selected.md",
            "fidelity": "OFFICIAL_EXPORT_SOURCE_AVAILABLE",
        })

    index_bytes = b"".join(canonical_json_bytes(r) for r in index_records)
    atomic_write(indexes_dir / "conversations.jsonl", index_bytes)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_type": "OPENAI_OFFICIAL_CHATGPT_DATA_EXPORT",
        "source_authority": "raw preserved export JSON files",
        "derived_views_authoritative": False,
        "conversation_count": len(index_records),
        "conversation_ids_with_multiple_distinct_versions": conflicts,
        "sources": source_manifest,
        "index_sha256": sha256_bytes(index_bytes),
    }
    atomic_write(output_dir / "archive.json", canonical_json_bytes(manifest))

    report = (
        f"# ChatGPT official export ingest\n\n"
        f"- conversations: {len(index_records)}\n"
        f"- source JSON files: {len(source_manifest)}\n"
        f"- IDs with multiple distinct revisions: {conflicts}\n"
        f"- index sha256: `{manifest['index_sha256']}`\n"
        f"- authority: preserved official-export source JSON\n"
    )
    atomic_write(reports_dir / "validation.md", report.encode("utf-8"))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Official ChatGPT export ZIP, conversations JSON, or containing directory")
    parser.add_argument("output", type=Path, help="Destination archive directory")
    args = parser.parse_args()
    try:
        manifest = ingest(args.input, args.output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
