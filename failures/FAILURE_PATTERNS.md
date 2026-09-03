# Failure Patterns

## GH-CREATE-EXISTING-PATH-SHA-ERROR

status: `OBSERVED`

environment: current ChatGPT GitHub connector, 2026-09-03.

symptom: `create_file` returned HTTP 422 / `sha wasn't supplied` while initializing a newly created repository.

discriminating probe: `fetch_file` on the intended path.

observed root cause: repository already contained an initial `README.md` commit even though earlier repository metadata reported size zero; the target path was therefore an update, not a create.

repair: fetch the real object/HEAD first; if path exists, use SHA-guarded update or include replacement in a Git Data multi-file transaction.

lesson: object-state mismatch should be tested before escalating to permission/OAuth/provider diagnosis. Repository size metadata is not sufficient path-existence proof during fresh initialization.

promotion: keep OBSERVED until reproduced or connector behavior is documented as stable.

## PARTIAL-COMPOUND-CHECKPOINT

status: `REPEATED / WRAPPER_CANDIDATE`

symptom: primary artifact write/readback succeeds but checkpoint pointer, queue/state transition or terminal receipt is missing because execution stops between primitives.

impact: later controller must diagnose partial state, bind existing artifact, block unsafe rerun and repair multiple control surfaces.

root cause class: one logical transaction exposed as serial model-mediated provider primitives.

repair now: fail closed, reconcile from externally verified artifact/state, do not blindly rerun scientific production.

architectural repair: `DRIVE_CHECKPOINT_COMMIT` / `STATE_TRANSITION_COMMIT` with idempotency/preconditions/readback and structured receipt.

## SERIAL-MIRROR-MICRO-WRITES

status: `REPEATED / WRAPPER_CANDIDATE`

symptom: one accepted result causes serial commits/updates to index, backlog, task, TODO, watch, lease and receipt surfaces.

impact: quota/context cost, larger interruption surface, recovery amplification.

architectural repair: one logical multi-file transaction plus automatically generated derived mirrors/receipts when possible.

## TOOL-CALL-SUCCESS-WITHOUT-BUSINESS-COMPLETION

status: `STABLE_PLAYBOOK`

symptom: provider call succeeds but intended business postcondition is not verified.

repair: define the real postcondition before mutation and perform proportionate readback/integrity verification. Agent self-report is not evidence.
