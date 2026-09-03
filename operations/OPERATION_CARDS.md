# Operation Cards

These are semantic recipes. Tool names are runtime-bound and must be confirmed when schemas may have changed.

## DRIVE_TARGET_GROUNDING

maturity: `STABLE_PLAYBOOK`

Input: exact Drive URL/ID or a sufficiently specific identity description.

Route:
1. Use exact ID/URL when provided.
2. Otherwise search/list/recent to resolve candidates.
3. Read metadata/content as needed to prove identity before write.

Success: one verified target identity.

Failure takeover: multiple plausible matches -> semantic disambiguation; no match -> broaden retrieval; do not guess.

## DRIVE_MOVE_FILE

maturity: `STABLE_PLAYBOOK`

Route:
`read metadata/parents -> add destination parent + remove only verified source parent(s) -> readback metadata or target folder`.

Invariant: preserve unrelated parents.

## DRIVE_NATIVE_DOC_BASIC_EDIT

maturity: `STABLE_PLAYBOOK`

Route:
`read live doc/revision/tab/indexes -> one compact structured batchUpdate -> readback edited region`.

Use revision precondition when collaborator conflict should fail closed.

## DRIVE_BYTE_PRESERVING_TRANSFER

maturity: `STABLE_PLAYBOOK`

Route: raw/file-reference/stream/provider copy -> destination upload/copy -> metadata/readback.

Forbidden normal path: read binary into model context and re-emit/base64/transcribe just to move it.

## DRIVE_CHECKPOINT_COMMIT

maturity: `WRAPPER_CANDIDATE`

Desired contract:
`fixed target/version + payload + checkpoint metadata -> write -> readback -> verify -> checkpoint pointer/state update -> one structured receipt`.

Happy path should require one model-level capability invocation after semantic parameters are resolved.

## GITHUB_TEXT_FILE_UPDATE

maturity: `STABLE_PLAYBOOK`

Route:
`fetch_file -> retain blob SHA -> update complete text with SHA precondition -> fetch_file readback`.

Failure: stale SHA -> refetch, determine whether conflict is mechanical or semantic; never blind overwrite.

## GITHUB_MULTI_FILE_LOGICAL_TRANSITION

maturity: `STABLE_PLAYBOOK / WRAPPER_CANDIDATE`

Route:
`current HEAD/tree -> blobs -> tree(base=current tree) -> commit(parent=current HEAD) -> update ref non-force -> representative readback`.

Use when several mechanically determined file mutations are one logical state transition. Prefer this over N serial contents-API commits.

## PROVIDER_WRITE_COMPLETION

maturity: `STABLE_PLAYBOOK`

Rule: API success is not automatically business-level completion. Verify the postcondition that actually matters: target identity, content/revision/hash/metadata, state pointer or externally readable artifact as appropriate.

## TOOL_FAILURE_MINIMAL_PROBE

maturity: `STABLE_PLAYBOOK`

Route:
1. Verify exact tool identity/schema.
2. Run smallest safe schema-valid discriminating read/probe.
3. Distinguish object-state/schema/content/path failure from permission/OAuth/provider failure.
4. Retry only when the new probe changes the diagnosis.
5. High-capability diagnosis begins after structured evidence, not blind repeated calls.
