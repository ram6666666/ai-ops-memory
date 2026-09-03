# Failure Pattern — Learning Capture Trigger Missed

status: REPEATED / STABLE_PLAYBOOK
class: META_OPERATIONAL_LEARNING_FAILURE
first_recorded: 2026-09-03

## Signature

A work unit produces a reusable operational lesson, user correction, failure recovery, shorter route, or evidence that an existing rule did not trigger, but the agent only acknowledges it in conversation and does not automatically update the durable experience library.

Anti-pattern:

`novel operational lesson -> conversational acknowledgement -> continue`

Required pattern:

`novel operational lesson -> classify reusable delta -> update operation/failure/learning record -> read back -> continue`

## Trigger incident

During setup of an AI-executor monitoring radar, ChatGPT's native scheduled-task limit was reached. The user pointed out that external scheduling via GitHub Actions, calendar, Slack/message routing, or similar infrastructure should be considered instead of stopping at the platform limit. The alternative-path lesson was then formalized, but the user subsequently had to remind the system that this new experience should itself have been automatically written into the experience library under the already-established WORK_DERIVED_LEARNING requirement.

This exposed a second-order defect: the repository existed and the learning policy existed, but the automatic capture trigger did not fire.

## Root cause

The learning layer was treated as a destination used when explicitly invoked, rather than as a mandatory postcondition of operational execution.

Having an experience repository does not create learning unless work completion includes a capture gate and future execution retrieves relevant cards before repeating the same class of operation.

## Mandatory repair

At each substantive operational-unit boundary, and immediately after a novel failure/recovery/user correction, evaluate whether reusable operational information changed.

High-priority automatic-capture triggers include:

- user corrects a general engineering behavior;
- an existing global rule/playbook should have fired but did not;
- a platform/tool limitation is rerouted through a better path;
- a repeated mechanical chain appears;
- a new provider/tool quirk or schema behavior is discovered;
- a successful repair provides a shorter/safer/cheaper route;
- a failure shows that retrieval, trigger, or learning control itself is incomplete.

If reusable information changed, update the durable experience surface and perform readback before treating the unit as closed.

## Retrieval implication

Capture alone is insufficient. Future operations should retrieve task-similar operation/failure cards when a trigger signature appears. A repeated user correction after a stable card exists is evidence of retrieval/control failure and should increase priority for deterministic triggering or wrapper implementation.

## User-attention implication

Do not make the user serve as the experience-memory daemon. User corrections are expensive evidence that the system's learning/control layer failed. The system should absorb that evidence automatically and reduce recurrence.

## Maturity rationale

This pattern is already repeated: the user has explicitly established proactive and work-derived learning, yet a newly learned operational reroute still required a second reminder to be persisted. Therefore the issue is not a one-off missing note; it is a control-loop defect requiring a stable playbook.
