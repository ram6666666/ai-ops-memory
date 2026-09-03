# AI Executor Radar

Status: `AUTOMATED_MONITORING / OBSERVATION_ONLY`

Purpose: automatically watch AI executor / work-agent products for operational capabilities that matter to the user's control-plane workflow, without consuming scarce ChatGPT scheduled-task slots or requiring the user to manually test routine product changes.

## Architecture

`GitHub Actions cron -> official source fetch -> deterministic normalization -> SHA-256 comparison -> bounded diff -> capability-keyword triage -> versioned evidence`

The initial collector is deliberately deterministic and low-cost. It does **not** use an LLM and therefore does not claim semantic verification. Its job is to detect and preserve candidate changes so a model or human only spends attention on genuinely new evidence.

## Evidence classes

- `BASELINE`: first successful capture of a source. Never treated as a new product event.
- `CHANGED`: normalized source content changed since the prior successful run.
- `HIGH_PRIORITY_CANDIDATE`: changed text contains one or more control-plane capability terms worth later inspection.
- `FETCH_FAILED`: source could not be retrieved; retained as telemetry, not silently interpreted as product change.

Vendor documentation/release notes are evidence of **claimed/configured capability**, not proof that the behavior is reliable in production. Promotion to `VERIFIED_CAPABILITY` requires a separate executable acceptance test with readback evidence.

## Primary evaluation dimensions

- real filesystem access and in-place edits;
- diff / rollback;
- workspace or project-root isolation;
- checkpoint, resume, recovery and persisted state;
- long-running/background execution;
- scheduled execution;
- permissions and destructive-action gates;
- Skills/plugins/MCP/API/CLI extensibility;
- browser/computer use;
- concurrency / queues / worktrees;
- write-readback/integrity/provenance surfaces;
- cross-session recovery and durable external state.

## Notification policy

Routine runs are silent. High-priority candidates are persisted under this directory and may generate a GitHub issue when the workflow has issue-write permission. Slack/other IM should be treated as an optional notification outlet, not as the scheduler or source of truth.

## Authority boundary

This radar is an operational-learning sensor. It cannot authorize project execution, alter scientific scope, or promote vendor claims to verified capability. It stores no secrets, cookies, credentials, or private authorization material.
