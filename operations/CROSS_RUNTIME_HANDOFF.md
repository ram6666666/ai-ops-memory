# Cross-runtime handoff preparation

status: `IMPLEMENTED_SELF_TESTED_COMPONENT`
maturity: `WRAPPER_CANDIDATE`; exact receiver-provider qualification pending
implementation repository: `ram6666666/ai-`
policy pointer: `global/CROSS_RUNTIME_HANDOFF_PROTOCOL.md`

## Problem and route

A receiver may expose Drive metadata and small text operations while its local computation container cannot receive connector binaries. It may have PDF tooling without access to the PDF, no GitHub route, no browser connection, or no route to upload generated binaries. Model family, sender access and old tiny-checkpoint success cannot establish that environment's full capability.

Prepare a serious handoff as:

`exact task/input/output requirements -> observed profile -> exact runtime binding -> fresh receiver probes -> prepared/read-back carriers -> deterministic SAT -> guarded dispatch`

Bind surface, session and configuration hash for the receiver and any controller fallback. Bind the profile hash, challenge, observation times, task identity and exact carrier targets. Missing, false, stale or mismatched required evidence produces `BLOCKED_PRE_DISPATCH`. Unknown capability is not permission to try substantive work.

If no fresh receiver evidence exists, issue a separately scoped `PROBE_ONLY` bootstrap. It tests synthetic access/write/readback and returns receipts; it does not start the serious audit, expose sealed later-stage conclusions, mutate candidates or claim readiness. Recheck after dispatch for capability drift.

## Carrier decisions

| Need | Route to prepare and test |
|---|---|
| Canonical control without GitHub | Complete readable relay, mechanically bound to repository/commit/path/blob/raw SHA-256 and sender publication/readback |
| Text and source members | Independently addressable complete files, exact source mapping and per-file readback |
| Raw binary | Byte-preserving connector-to-container stream/file bridge or mechanically verified chunk route |
| Visual PDF review | Independently viewable actual pages, bound to exact PDF hash/page index/render parameters/image hashes |
| Receiver text output | Bound namespace, format/size limits and create/readback probe |
| Receiver cannot upload required PDF/ZIP | Prebound controller mechanical terminalization from frozen reviewer text/findings; controller upload/readback tested separately |

ZIP/TAR is archival/convenience packaging, never the sole load-bearing carrier. Page images do not replace separate raw-PDF-byte or reproducible-build obligations. Base64 that reaches only model context is not a mechanical binary bridge; splitting it into model-transcribed chunks does not change that.

Keep first-pass and sealed later-stage payloads separate. Publishing an archive can expose every embedded member even if an index hides it. Receiver findings remain receiver-authored: controller fallback may render/package exact returned sources, but must not add conclusions, change verdicts or repair arguments.

## Executable interfaces

All paths below are in the implementation repository:

- `runtime/control-kernel/cross_runtime_handoff.py`: `compile_handoff(contract, profile, probes, now)` computes `SAT/READY_TO_SEND` or `UNSAT/BLOCKED_PRE_DISPATCH`; CLI accepts contract, profile and probes JSON paths plus `--now`.
- `global/CROSS_RUNTIME_HANDOFF_SCHEMA_V1.json`: contract schema with reusable profile/probe definitions.
- `runtime/control-kernel/cross_chat_handoff_guard.py`: validates serious handoff structure and recomputes the cross-runtime gate; a saved SAT receipt is not an authorization token.
- `runtime/control-kernel/cross_runtime_relay.py`: `RelayBuilder`, `git_control`, `publish_verified` and `terminalize` prepare exact files/control/page relays, verify provider readback through supplied adapters and produce mechanically bound output candidates.
- `runtime/control-kernel/cross_runtime_dispatch.py`: `prepare_dispatch`/`dispatch` bind task/generation/input hash and launcher bytes, embed the exact reviewer-readable contract and frozen carrier manifest, recompile immediately before compare-and-publish, then require exact byte readback. `FileMailboxTransport` is the bundled local staging/regression transport. `GoogleDocsMailboxTransport` supports a dedicated plain-text JSON Google Docs mailbox through `get_document` and revision-guarded `batch_update_document`; `prepare_google_docs_mutation` and `verify_google_docs_readback` support the same boundary through connected-tool calls. A legacy prose mailbox is rejected instead of silently converted.

The publisher adapter provides `publish(bytes, name, mime) -> locator` and `read(locator) -> bytes`. The dispatch transport provides `snapshot`, `publish_if_current` and `readback`; concurrent revision changes must reject the mutation. A production provider adapter must preserve those contracts and be tested in its actual invocation path.

## Evidence and limitations

Synthetic regression must exercise real file creation, archive expansion, page rendering where available, transport/readback/hash checks, mismatched/expired receipts, ZIP-only rejection, full input/output coverage and blocked emission. It proves an implementation component, not a live Claude session.

The compiler checks supplied receipt bindings; it does not authenticate provider signatures or transform model assertions into observations. Sender publication/readback does not set receiver access true. A local mailbox test does not deploy a remote scheduler. No universal `VERIFIED_CAPABILITY`, unavoidable provider hook, fresh Claude qualification or scientific acceptance follows from these components alone.

Output qualification binds the requested format, MIME type, destination and observed file signature. The implemented binary signature set is PDF, ZIP, PNG and JPEG; undeclared formats such as DOCX remain blocked. Literal report rendering requires an explicit font with coverage for non-ASCII characters.

Keep user-specific task IDs, storage IDs, exact private runtime bindings and receipts in the authorized private control surface. Never place secrets or live handshake codes in this public operation card or its fixtures.
