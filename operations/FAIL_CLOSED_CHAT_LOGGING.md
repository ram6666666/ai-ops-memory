# Fail-Closed Chat Logging

status: IMPLEMENTATION_PROTOTYPE_SELF_TEST_PASS
maturity: WRAPPER_CANDIDATE
scope: external API/client/personal-harness interaction boundary
not_scope: OpenAI ChatGPT first-party web/app runtime

## Contract

Critical path:

`user input -> durable commit -> model call -> durable assistant-output commit -> delivery`

The harness must fail closed at both logging gates:

- if the user-input durable commit fails, the model call must not execute;
- if the assistant-output durable commit fails, the generated output must not be delivered/returned.

## Prototype implementation

- `tools/fail_closed_chat_logger.py`
- local durable primary: SQLite WAL
- SQLite `synchronous=FULL`
- transaction uses `BEGIN IMMEDIATE` and commits before boundary crossing
- per-conversation monotonically increasing sequence number
- deterministic event id for retry/idempotency
- SHA-256 hash chain across events
- conflicting replay of an existing event id fails closed

## Self-test coverage

`tools/test_fail_closed_chat_logger.py` covers:

1. write-before-call + write-before-deliver happy path;
2. injected user-write failure prevents model execution;
3. injected assistant-write failure prevents delivery;
4. reopen/restart continuity and idempotent retry;
5. content tampering breaks chain verification.

Initial local prototype execution on 2026-09-03: 5/5 tests PASS.

## Current limits

This proves the critical ordering/fail-closed mechanism is implementable in an external harness. It does NOT mean the current ChatGPT web/app has been intercepted or made deterministic. The first-party ChatGPT runtime remains outside this wrapper's control.

The prototype currently uses local durable SQLite as the mandatory commit surface. A real personal harness should add a separately tested remote/cloud replication path (for example Drive/object storage/database) and decide whether remote acknowledgement is itself on the synchronous critical path or whether local durable commit is authoritative with an outbox/replicator. Cloud durability/failure semantics are not yet accepted here.

Streaming output is also not yet implemented; production streaming requires write-before-render at chunk or bounded-frame granularity plus crash/retry semantics.

## Promotion gate

Do not mark VERIFIED_CAPABILITY until all of the following are satisfied:

- integrated into a real external model/API client;
- real model call proves user commit precedes provider invocation;
- real delivery surface proves assistant commit precedes rendering/return;
- process crash/restart and storage-unavailable failure injection pass;
- concurrency and duplicate-request behavior pass;
- remote/cloud replication policy is frozen and tested;
- independent GDVA behavioral validation and implementation/code audit pass.
