# ChatGPT Conversation Archive

status: ACTIVE_PLAYBOOK
first_verified_foreground_mirror: 2026-09-03
scope: preserve ChatGPT conversation provenance without pretending reconstructed history is raw transcript

## Problem

ChatGPT conversation context is not a durable message database for the acting model. Older turns may be summarized, truncated, or absent from the active runtime. A later reconstruction can preserve reasoning but cannot recover quotation-level fidelity that is no longer present.

Therefore conversation provenance is split into two acquisition lanes.

## Lane A — official historical baseline

Use the supported ChatGPT Data Export flow to obtain the account export ZIP. Treat the preserved `conversations.json` / numbered conversation JSON files from that export as source evidence. Do not rewrite them in place.

Ingest route:

`official export ZIP/JSON -> tools/ingest_openai_export.py -> preserved source bytes -> per-conversation raw JSON/revisions -> derived Markdown/index -> validation report`

The source JSON remains authoritative. Markdown and indexes are rebuildable views.

## Lane B — foreground loss prevention

When a conversation is currently active and its user-visible text is directly present to the assistant, an explicitly authorized workflow may mirror that text into user-controlled private external storage as it occurs.

The foreground mirror must:

- preserve the exact user-visible text available in the active runtime;
- preserve observed user timestamps when available;
- never invent provider conversation IDs, message IDs, parent IDs, hidden tool state, or branches;
- label itself `EXACT_FOREGROUND_USER_VISIBLE`, not `PROVIDER_RAW_GRAPH`;
- write only to private user-controlled storage for personal transcript content;
- read back the write before claiming checkpoint success;
- remain separate from summaries, nested argument trees, project specifications, and canonical decisions.

This lane is forward-only. It prevents new provenance loss; it does not retroactively repair old missing turns.

## Fidelity classes

- `PROVIDER_RAW_EXPORT`: exact provider export object/bytes preserved from the supported export flow.
- `EXACT_FOREGROUND_USER_VISIBLE`: exact text directly available in the active conversation runtime; provider graph metadata may be absent.
- `NEAR_VERBATIM_DIRECT_SOURCE`: direct source exists, but formatting/surrounding material was normalized.
- `RECOVERED_NON_VERBATIM`: reconstructed from summaries, memory, selected quotations, or later durable records.
- `POINTER_ONLY`: source known but unavailable to the current runtime.

A filename containing `fulltext`, `raw`, `final`, or similar language never upgrades fidelity by itself.

## Acceptance test for “complete transcript”

A record may be called a complete raw transcript only when the required source boundary is explicit and mechanically supported.

For provider-level completeness, require provider-export/raw-graph evidence sufficient to enumerate the conversation nodes/messages within that source. For foreground text completeness, require a defined capture interval and exact mirrored visible turns for that interval. Otherwise use a weaker fidelity label.

## Historical backfill procedure

1. Obtain a supported official Data Export.
2. Preserve the original ZIP separately.
3. Run `tools/ingest_openai_export.py` into a private archive root.
4. Read `reports/validation.md` and `archive.json`.
5. Reconcile existing discussion archives against provider-export source records.
6. Upgrade only records actually supported by direct source evidence; downgrade misleading `fulltext` labels when the assistant trajectory was reconstructed.
7. Keep structured/nested discussion products as derived provenance, never as substitutes for raw source.

## Unsupported default route

Do not make browser scraping or ChatGPT private web endpoints the normal archive mechanism. These routes are brittle and can conflict with provider terms or change without notice. They may be studied as external implementations, but operational archival authority defaults to the supported export plus explicit foreground mirroring.

## Privacy

Conversation bodies are sensitive user data. Raw/private transcript archives belong in private storage. The public `ai-ops-memory` repository stores only generic tooling, schemas, test fixtures, and operational knowledge.

## Failure status

If a required write/readback fails, classify the mirror `ARCHIVE_UNSYNCED` and do not claim preservation. If an old source is unavailable, classify it `RECOVERED_NON_VERBATIM` or `POINTER_ONLY`; never fill gaps by model reconstruction while calling the result verbatim.
