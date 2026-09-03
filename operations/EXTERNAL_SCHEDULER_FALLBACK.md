# External Scheduler Fallback

maturity: STABLE_PLAYBOOK
scope: recurring monitoring / reminders / deterministic scheduled work

## Trigger

A platform-native scheduled-task quota, UI limit, or scheduler capability prevents creation of another recurring task, while the underlying job can be decomposed into deterministic scheduled work and optional notification.

## Default rule

Do **not** treat the platform task-slot limit as the execution boundary. Re-evaluate the operation against available external primitives before asking the user to manage slots manually.

Preferred decomposition:

`scheduler -> deterministic worker -> durable state/evidence -> notification outlet -> model review only on material event`

## Preferred primitives

1. GitHub Actions / CI cron for repository-centered monitoring, fetching, tests, diffs, hashes and state updates.
2. Provider-native scheduled jobs or system cron for local/server deterministic work.
3. Google Calendar only when the required action is primarily a human reminder or calendar event; Calendar does not substitute for autonomous research/execution.
4. Slack/Teams/Feishu/WeCom or similar IM as notification/command channels, not automatically as durable state or scheduler authority.
5. Scarce ChatGPT scheduled tasks only when recurring execution materially requires the model/runtime itself rather than an external deterministic worker.

## Verification

For an external scheduler deployment, verify at minimum:

- configuration/workflow exists at the authoritative external location;
- schedule and permissions are explicit;
- worker output has a durable state/evidence location;
- first-run baseline is distinguishable from genuine change;
- routine no-change runs do not create unnecessary state churn;
- notification failure does not destroy the underlying evidence;
- the first real scheduled run remains `CONFIGURED_UNVERIFIED` until observable run evidence exists.

## Failure boundary

If autonomous work requires credentials, provider secrets, local UI access, or an AI endpoint not already safely provisioned, do not invent or store credentials. Keep deterministic collection running where possible and escalate only the irreducible authorization step.

## Root lesson

A quota on one orchestration surface is not necessarily a quota on the task. Search for the correct scheduler/message-bus/storage abstraction before degrading to manual user intervention.
