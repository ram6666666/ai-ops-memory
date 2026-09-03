# Fail-Closed Chat Logging

status: PRODUCTION_CANDIDATE_SELF_TEST_PASS
maturity: WRAPPER_CANDIDATE
scope: external API/client/personal-harness interaction boundary
not_scope: OpenAI ChatGPT first-party web/app runtime

## Contract

Strict critical path:

`user input -> local durable commit -> required replica ACK -> model call -> assistant output/chunk -> local durable commit -> required replica ACK -> delivery/render`

The harness fails closed at every boundary:

- if the user-input local commit fails, the model call does not execute;
- if strict replica ACK for the user event fails, the model call does not execute;
- if assistant output local commit or required replica ACK fails, the output is not delivered;
- in streaming mode, each text delta is committed and ACKed before that delta is yielded/rendered.

A weaker local-authoritative mode is implemented for deployments that deliberately choose asynchronous cloud replication, but it is not the strict default for the strongest completeness claim.

## Production-candidate implementation

Primary candidate:

- `tools/fail_closed_chat_runtime.py`
- tests: `tools/test_fail_closed_chat_runtime.py`
- evidence: `telemetry/2026-09-03_FAIL_CLOSED_CHAT_RUNTIME_CANDIDATE_SELF_TEST.yaml`

Core mechanisms:

- SQLite WAL local primary;
- SQLite `synchronous=FULL`;
- `BEGIN IMMEDIATE` serialized event append;
- monotonically increasing per-conversation sequence;
- deterministic event ids for replay/idempotency;
- SHA-256 hash chain;
- persisted replica ACK receipts keyed by event identity/hash;
- pluggable `ReplicaSink` contract;
- atomic fsync-backed filesystem replica for second-sink testing;
- strict `REMOTE_ACK_REQUIRED` path;
- OpenAI Responses API adapter using `responses.create` and streamed `response.output_text.delta` events;
- non-stream recovery reuses a locally committed assistant result after remote-ACK failure instead of invoking the model again;
- streaming write-before-render at delta granularity.

The original five-case prototype remains at `tools/fail_closed_chat_logger.py` as provenance; the runtime candidate supersedes it for productionization work.

## Current self-test evidence

Local production-candidate run: 12/12 PASS with `ResourceWarning` promoted to test failure. During the first 8-case run, connection lifecycle warnings exposed that Python's SQLite context manager commits/rolls back but does not itself close the connection. The candidate was corrected to explicit closing semantics and the enlarged 12-case suite then passed cleanly.

Coverage now includes:

1. strict local + replica ACK on both user/assistant paths;
2. remote user ACK failure blocks model invocation;
3. remote assistant ACK failure blocks delivery;
4. streaming chunk commit/ACK before yield;
5. streaming remote failure blocks the affected chunk from render;
6. optional local-authoritative/asynchronous-replica policy;
7. controlled OpenAI Responses adapter shape test;
8. idempotent replay without duplicate replica writes/model call when output is already committed;
9. recovery after assistant remote-ACK failure without model reinvocation;
10. atomic/idempotent filesystem replica;
11. 24 concurrent same-conversation commits preserving one valid sequence/hash chain;
12. committed data surviving immediate process `os._exit` and verifying after reopen.

GitHub Actions run `33765340011` on `ubuntu-latest` completed successfully. The CI installs the current `openai` Python package and verifies that `client.responses.create` exists, then runs both the original prototype and production-candidate tests and compiles the candidate. No live provider request is made because no API credential is available to this execution environment.

## Current provider/API grounding

The current OpenAI Responses API supports creating a response with a model and input, exposes `output_text` in SDKs, and supports streaming events including `response.output_text.delta`. The candidate adapter deliberately targets that current Responses surface rather than the deprecated legacy Completions path.

## Residual limits / blocked production gates

The following are still explicit blockers or non-claims:

- **Live OpenAI provider call not yet executed.** The adapter and current SDK surface are tested, but a real request requires an API credential available to the external harness runtime.
- **Real cloud replica not yet implemented/tested.** The `ReplicaSink` contract and strict ACK semantics exist; the concrete secondary sink tested so far is an fsync-backed filesystem replica, not Google Drive/object storage/database over an independent network path.
- **Provider-call exactly-once is not claimed.** If the process dies after the provider has generated output but before that output reaches the local durable assistant commit, a retry may invoke the provider again. If local assistant commit succeeded but remote ACK/delivery failed, the current recovery path does avoid a second model call.
- **Mid-stream crash recovery is incomplete.** Every already rendered delta has been durably recorded first, but resuming a provider stream after a process crash without duplicate/divergent continuation is not yet frozen or accepted.
- **First-party ChatGPT web/app remains outside the boundary.** This candidate can protect an API client/personal harness; it cannot intercept the official ChatGPT application's internal inference boundary.
- **Independent acceptance is pending.** Producer self-tests and GitHub CI do not satisfy GDVA behavioral validation or the independent external implementation/code-audit branch.

## Next production steps

1. bind a real OpenAI Responses API client credential in a secure external runtime and run live write-before-call/write-before-deliver tests;
2. implement at least one genuine cloud `ReplicaSink` with provider-returned durable ACK semantics and inject network/storage failures;
3. define and test mid-stream restart/reconciliation semantics;
4. expose the frozen candidate identity, requirement and telemetry to GDVA without producer-originated VERIFIED promotion;
5. run independent behavioral validation, external architecture/code audit, and only then the mechanical acceptance join.

## Promotion gate

Do not mark `VERIFIED_CAPABILITY` / `ACCEPTED_VERIFIED_LIVE` until the exact frozen candidate has passed the live external-client path, real cloud replication failure envelope, required crash/restart behavior, and both independent GDVA branches. The current ceiling is `PRODUCTION_CANDIDATE_SELF_TEST_PASS`.
