# Proactive Common-Operations Library

This lane is built deliberately, not only from accidents encountered in user work.

## Rule

Before a recurring mechanical task becomes expensive, identify whether a mature native tool, provider API, library, CLI, deterministic utility, skill, plugin, or already-tested project helper exists. Encode the shortest reliable route as an operation card. Do not wait for repeated failures before using obvious engineering abstractions.

## Candidate domains

Priority order follows observed frequency/cost in the user's environment:

1. Google Drive / Docs file lifecycle, byte-preserving transfer, native content edit, export/import, revision/readback.
2. GitHub search/fetch/update, multi-file logical commits, branch/ref/PR operations, artifact relay.
3. Work/worker checkpoint lifecycle, receipts, leases, resume state and quota-safe persistence.
4. Claude/Codex/ChatGPT cross-model relay and capability binding.
5. Local research filesystem and Git workflows.
6. LaTeX build, bibliography, PDF render/inspection, deterministic conversion and packaging.
7. Python/numerical execution, environment discovery, dataset/file transforms, hashing and reproducibility capture.
8. Literature/PDF ingestion, metadata, source extraction and project linkage.
9. Spreadsheet/document/slide import-export and provider-native editing.

## Proactive card acceptance

A proactive recipe may enter `STABLE_PLAYBOOK` when the current tool/API contract is explicit and the route has either been executed successfully in the current environment or is a direct native operation with adequate readback semantics. Otherwise keep it `OBSERVED` or `REPEATED` until tested.

A proactive recipe must record:

- environment/runtime binding;
- semantic operation;
- preferred primitive/capability;
- minimal required inputs;
- preconditions/concurrency guards;
- success postcondition;
- minimum sufficient verification;
- structured failure/recovery boundary;
- known cost traps;
- wrapper candidacy.

Do not create wrapper code merely to have code. Native mature provider operations remain preferable when they already provide the correct abstraction.
