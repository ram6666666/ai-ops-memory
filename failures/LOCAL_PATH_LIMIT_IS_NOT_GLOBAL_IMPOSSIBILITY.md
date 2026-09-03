# Failure Pattern — Local Path Limit Misclassified as Global Impossibility

status: STABLE_PLAYBOOK
class: OPERATIONAL_CONTROL_FAILURE
first_recorded: 2026-09-03

## Signature

An agent encounters a quota, slot limit, connector limitation, unavailable action, provider restriction, context limit, file-size limit, or failure in the initially selected implementation path and prematurely reports the user's task as blocked or asks the user to perform manual work.

Typical anti-pattern:

`selected tool cannot do X -> stop / ask user`

Correct pattern:

`selected tool cannot do X -> classify exact local constraint -> discover equivalent primitives -> reroute architecture -> verify -> escalate only irreducible user/safety boundary`

## Trigger incident

A recurring monitoring task was initially routed to ChatGPT scheduled tasks. The platform returned the maximum-active-task limit. Treating that as the end of automation would have been incorrect because the scheduling function could be externalized to GitHub Actions while GitHub remained the durable evidence/state layer and Slack/calendar remained optional human-notification surfaces.

## Preferred recovery route

1. Identify what failed and whether the failure is semantic or implementation-specific.
2. Search connected/exposed capability registry before claiming absence.
3. Separate scheduling, deterministic execution, durable state, notification, and semantic reasoning.
4. Substitute the constrained component with a mature external primitive.
5. Run a bounded probe/readback.
6. Record only new reusable evidence.
7. Escalate to the user only when account authorization, material cost/privacy changes, destructive action, or genuine semantic choice remains.

## Architecture pattern

`external scheduler -> deterministic worker -> durable GitHub/Drive state -> event triage -> notification only on material condition -> high-capability model only for semantic analysis`

Candidate scheduler primitives include GitHub Actions, cron/systemd timers, cloud/provider schedulers, webhooks, queue workers, and app-native automations. Calendar is primarily a human-attention scheduler; Slack/email are primarily notification/message-routing surfaces unless their workflow engines are deliberately used.

## Failure classifications

- LOCAL_PATH_FAILED
- ALTERNATIVE_PATH_IN_PROGRESS
- DEGRADED_FALLBACK
- BLOCKED_USER_AUTHORIZATION
- BLOCKED_SAFETY_OR_POLICY
- BLOCKED_NO_AVAILABLE_PATH

Do not emit generic BLOCKED before alternative-path discovery has been performed proportionately.

## Guardrail

Never use this playbook to bypass authentication, authorization, consent, security controls, safety policy, legal restrictions, or frozen project scope. Those are real boundaries, not implementation inconvenience.

## Promotion rationale

This failure has occurred repeatedly enough to be treated as a control-system defect rather than an isolated mistake. Future agents should retrieve this card automatically when a platform quota/tool limitation appears and attempt legal rerouting before consuming user attention.
