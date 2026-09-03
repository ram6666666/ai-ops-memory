# Efficiency / Reliability Baseline

## 2026-09-03 deterministic-operations audit

Source: recent AI-control audit in `ram6666666/ai-`.

Fixed sample: most recent 100 GitHub commits visible at audit time.

Classification:

- 80 `CLEAR_LOW_ENTROPY_MECHANICAL_OR_CONTROL_WRITE`
- 11 `MIXED_DIAGNOSIS_PLUS_STATE_COORDINATION`
- 9 `CLEAR_SUBSTANTIVE_CONTENT_OR_POLICY_GENERATION`

Interpretation: approximately 80% of durable mutations in that sample were mechanically dominated and therefore strong candidates for deterministic execution/batching. This is **not** a claim that 80% of model tokens or billing were wasted; commit sizes and model costs differ and per-operation quota telemetry is unavailable.

## Metrics to drive down

- high-capability model-mediated primitive calls per completed work unit;
- deterministic state mutations per semantic decision;
- serial commits/writes per one logical transition;
- retries per verified file/checkpoint transaction;
- fraction of routine happy paths requiring frontier/high-reasoning model decisions;
- model context used merely to transport deterministic file/data content;
- recovery operations caused by partial compound transactions.

## Desired normal-state targets

- ordinary verified save/checkpoint after semantic parameters resolve: one compound capability invocation where runtime permits;
- receipt/lease happy path: zero semantic decisions;
- one logical multi-surface state transition: one deterministic transaction/commit where provider semantics permit;
- model diagnosis begins on structured failure/ambiguity, not on every internal substep;
- stable routine success does not generate duplicate prose memory.

## Learning KPI

The repository should show migration over time from:

`model-mediated primitive chain -> stable operation card -> wrapper candidate -> verified capability`.

The goal is not to maximize wrapper count. The goal is to minimize expensive semantic computation spent on already-solved deterministic work while preserving or improving correctness.
