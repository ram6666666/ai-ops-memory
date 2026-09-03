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

## Future environment profiles

Add dedicated profiles as actual work or proactive curation justifies them:

- Work controller/executor
- Claude
- Codex
- local Windows/Linux research filesystem
- Git CLI/local repositories
- LaTeX build toolchain
- PDF processing/render QA
- Python/numerical environments
- literature/bibliography management
- Office/Google Workspace conversions
