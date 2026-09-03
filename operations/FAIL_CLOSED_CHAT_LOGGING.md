# Fail-Closed Chat Logging

status: PRODUCTION_CANDIDATE_V2_SELF_TEST_AND_CI_PASS
maturity: WRAPPER_CANDIDATE
scope: external API/client/personal-harness interaction boundary
not_scope: OpenAI ChatGPT first-party web/app runtime

## Required boundary contract

Strict mode:

`user input -> atomic local event+replication-intent commit -> replica ACK -> provider call -> assistant output/chunk -> atomic local event+replication-intent commit -> replica ACK -> delivery/render`

Fail-closed invariants:

- user local commit failure blocks provider invocation;
- user replica ACK failure blocks provider invocation in strict mode;
- assistant local commit or required replica ACK failure blocks delivery;
- each streamed output-text delta is committed and ACKed before that delta is yielded/rendered.

Local-authoritative/asynchronous-cloud mode is also supported, but it must not lose replication intent: when a replica is configured, the event and a `PENDING` replication-outbox record are written in the same local SQLite transaction. A remote failure can therefore be retried after process/runtime restart.

## Current frozen producer candidate

- runtime: `tools/fail_closed_chat_runtime_v2.py`
- runtime blob: `7744e523c20e839b560d4ebe25847357b9e0c9d6`
- tests: `tools/test_fail_closed_chat_runtime_v2.py`
- test blob: `e48ad5c5ddf259bf65038d2a889ff7213c78cbd1`
- evidence: `telemetry/2026-09-03_FAIL_CLOSED_CHAT_RUNTIME_V2_SELF_TEST.yaml`
- GitHub Actions run: `33766147148`
- CI head: `45b9a65b8dd8d767521aca0b06b3e9913a8fa034`
- CI conclusion: `success`

The earlier `tools/fail_closed_chat_runtime.py` candidate and the initial `tools/fail_closed_chat_logger.py` prototype remain provenance only. V2 materially changes durability semantics and supersedes them for any new GDVA campaign.

## V2 mechanisms

- SQLite WAL primary;
- SQLite `synchronous=FULL`;
- `BEGIN IMMEDIATE` serialized append;
- per-conversation monotonically increasing sequence;
- deterministic event IDs with conflicting replay fail-closed;
- SHA-256 event hash chain;
- replica ACK receipts bound to event hash;
- **durable replication outbox** atomically created with each event whenever a replica is configured;
- `PENDING -> ACKED` replication state;
- retry attempt/error persistence;
- restart-safe `pending_replications()` / `retry_pending()`;
- pluggable `ReplicaSink`;
- atomic fsync-backed filesystem replica for second-sink testing;
- strict synchronous replica-ACK mode;
- optional local-authoritative asynchronous-replication mode with durable outbox;
- OpenAI Responses API adapter;
- streaming write-before-render at `response.output_text.delta` granularity;
- non-stream retry after assistant replica-ACK failure reuses already committed assistant output instead of invoking the model again.

## Evidence

Local V2 suite: **11/11 PASS**, with `ResourceWarning` treated as a test error and compile check PASS.

GitHub Actions run `33766147148` on `ubuntu-latest` also completed successfully. The job independently passed current OpenAI SDK installation/surface smoke, original prototype tests, V1 tests, V2 durable-outbox tests, and compile checks.

V2 closes a specific V1 production gap: asynchronous replication failure is no longer a volatile fact that can disappear with process death. The replication intent now exists in the same durable transaction as the source event and was tested across reopen/retry.

## Current official API grounding

As rechecked on 2026-09-03, OpenAI's current Responses API accepts a model/input response creation request, SDKs expose `output_text`, and streamed responses emit `response.output_text.delta`. The response-retrieval API also exposes `starting-after` using streamed event sequence numbers. The latter is a promising primitive for future interrupted-stream reconciliation, but V2 does not yet claim a correct mid-stream recovery protocol.

## Residual production gates / nonclaims

- **Live provider call:** not yet run because this execution runtime does not expose an OpenAI API credential. SDK/API shape tests are not a substitute for a real provider call.
- **Real independent cloud replica:** not implemented yet. The `ReplicaSink` contract, strict ACK behavior and durable outbox are implemented; the currently tested second sink is an fsync-backed filesystem replica, not Drive/object storage/database across an independent network durability domain.
- **Provider exactly-once:** not claimed. A crash after provider generation but before assistant local commit may cause a provider reinvocation on retry. A locally committed assistant output does avoid reinvocation during replica-ACK recovery.
- **Mid-stream crash continuation:** not implemented/accepted. Every delta already rendered was committed first, but resuming the provider stream after a process crash without duplicate or divergent continuation still needs a frozen protocol and tests.
- **Official ChatGPT app interception:** not implemented and cannot be forced from the current ChatGPT runtime. This harness protects interactions that actually pass through the external client/harness.
- **Independent acceptance:** pending. Producer self-tests and GitHub CI do not satisfy GDVA's independent behavioral branch or external implementation/code-audit branch.

## Next production work

1. implement and fault-test a genuine network/cloud `ReplicaSink`;
2. run a credentialed real OpenAI Responses API call through this boundary;
3. define interrupted-stream recovery using provider response IDs/sequence numbers where valid, then fault-test it;
4. submit this exact V2 identity to GDVA as a new campaign generation because V2 materially supersedes V1;
5. run independent behavioral validation and independent external implementation/code audit before any `VERIFIED_CAPABILITY` / `ACCEPTED_VERIFIED_LIVE` claim.

Current producer ceiling: `PRODUCTION_CANDIDATE_V2_SELF_TEST_AND_CI_PASS`.
