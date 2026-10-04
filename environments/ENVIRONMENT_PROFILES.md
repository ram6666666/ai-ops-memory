# Environment Profiles

## Google Drive / Google Docs

maturity: `REPEATED / STABLE_PLAYBOOK` for listed operations, bound to current connector schema.

### Object grounding

- Exact URL/ID supplied: use it directly.
- Otherwise resolve the real object through search/list/recent/metadata before mutation.
- Filename alone is not identity when duplicates are plausible.

### File lifecycle

- Move: read current metadata/parents -> update parents with destination and only verified source removals -> preserve unrelated parents -> metadata/folder readback.
- Stored/non-native file transfer: prefer raw fetch/file reference/stream and native upload/copy; do not route bytes through model context.
- Native Workspace content uses Docs/Sheets/Slides content APIs, not Drive metadata update.

### Native Docs

- Read document/text to obtain document id, tab id, live indexes and revision.
- Use structured `batchUpdate` requests.
- Use required revision control when concurrent edits should fail fast.
- Re-read after substantive/index-shifting writes.
- For basic new docs: create -> one read for revision/tab/index -> compact batch update -> readback.

### Known abstraction gaps

- Verified create-in-folder and checkpoint commit span multiple primitives in current connector.
- Priority abstractions: `DRIVE_CREATE_IN_FOLDER_VERIFIED`, `DRIVE_CHECKPOINT_COMMIT`.

## GitHub

maturity: `REPEATED / STABLE_PLAYBOOK` for listed operations, bound to current connector schema.

### Discovery/read

- Search is candidate discovery; `fetch_file` is authoritative content read.
- Do not treat search excerpts as complete file state.

### Single text file update

- Fetch current file and retain blob SHA.
- Update complete content using current SHA.
- Read back path/blob/content.
- Do not concurrently update/delete the same path.

### Multi-file logical transition

Prefer one Git Data transaction for related state changes:

`resolve current HEAD/tree -> create blobs -> create tree from current base tree -> create commit with current HEAD parent -> update branch ref non-force -> readback`.

If HEAD changes, do not force. Reacquire, reconcile any semantic conflict, rebuild.

### Known connector observation

A newly created repository may already contain an initial README even when earlier repository metadata reports size zero. A create call against that existing path can return an update-style SHA error. Minimal discriminating action: fetch the candidate path / current HEAD before diagnosing permissions or provider failure.

### Known abstraction gap

Logical multi-file state transitions still expose multiple Git Data calls. Priority abstraction: `GITHUB_MULTI_FILE_STATE_COMMIT`.

## Cross-model/runtime binding

ChatGPT, Work, Claude, Codex and local tools must not be assumed to expose identical schemas, provider file references, permissions or tool families. Reuse the semantic operation card, then bind it to the actual runtime capability. Current schema beats remembered syntax.

Operation card: `operations/CROSS_RUNTIME_HANDOFF.md`.

### Claude web / connector / container split

Observation maturity: `OBSERVED_LIMITATION`, not a universal statement about all Claude sessions. Record the exact surface, session and configuration for every serious dispatch.

- A Drive connector can expose metadata or base64 to model context while the local computation container has no route to those bytes. Local hashing, ZIP extraction or PDF rendering tools do not repair that missing bridge.
- A small text checkpoint write/readback does not demonstrate a multi-megabyte binary transfer or generated-binary upload.
- Browser connection and actual image/page viewing are separate capabilities from extracted text.
- Direct GitHub availability, readable canonical control relay, source text, raw binary, visual pages, text output and binary output each need their own tested route.

The sender must retrieve observed evidence, run a separately bounded probe bootstrap when necessary, and compile all required input/output routes before serious dispatch. Unknown, stale, mismatched or negative required capability means `BLOCKED_PRE_DISPATCH`. A successful sender read is not receiver access evidence.

The executable compiler, relay and dispatch-boundary components live in `ram6666666/ai-`; their current operational status is `IMPLEMENTED_SELF_TESTED_COMPONENT`. Real receiver-provider qualification remains pending until the exact runtime's fresh receipts pass. This profile does not claim an installed platform-wide hook, a deployed remote scheduler or live Claude readiness.

## Future environment profiles

Add dedicated profiles as actual work or proactive curation justifies them:

- Work controller/executor
- additional Claude surfaces after exact runtime characterization
- Codex
- local Windows/Linux research filesystem
- Git CLI/local repositories
- LaTeX build toolchain
- PDF processing/render QA
- Python/numerical environments
- literature/bibliography management
- Office/Google Workspace conversions
