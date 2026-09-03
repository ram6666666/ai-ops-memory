# Work-Derived Learning

This lane learns from actual execution with the user.

## Record only new information

Create or update an experience record only when at least one of the following changes:

- a tool/schema/capability differs from the stored profile;
- a previously unknown failure or ambiguity appears;
- a shorter, safer or cheaper route is demonstrated;
- an operation crosses a maturity boundary;
- a repeated deterministic chain becomes a wrapper candidate;
- a wrapper/capability is implemented, tested, regresses or is deprecated;
- telemetry exposes a material reliability/cost pattern;
- a cross-model/runtime difference affects routing or handoff;
- the user has to correct an operational behavior that should have followed an existing rule, playbook, or previously learned lesson;
- a local failure reveals that the learning/retrieval/trigger mechanism itself did not fire when it should have.

Routine success using an already stable operation card does not merit another prose entry unless useful telemetry is collected automatically.

## Mandatory automatic capture gate

Experience capture is part of completing the work unit, not an optional retrospective.

At the end of every substantive operational unit, and immediately after any novel failure, recovery, user correction, unexpected provider behavior, shorter route, or repeated low-entropy sequence, the acting agent must ask internally:

1. Did this unit produce new reusable operational information?
2. Did an existing operation/failure card fail to trigger or prove incomplete?
3. Did the user have to teach or remind the system of a generalizable engineering behavior?
4. Is this likely to recur across conversations, models, projects, or environments?
5. Should the result update an existing card, create a failure/operation record, change maturity, or become a wrapper/capability candidate?

If any answer is yes, perform the experience-library write and readback within the same work unit when authorized tooling is available. Do not wait for the user to request memory capture. Do not report the operational unit as fully closed while material reusable learning remains conversation-only.

User correction is a high-priority trigger because it is evidence that current automatic retrieval/control failed. The correct response is not merely to acknowledge the correction; it is to repair the external learning surface so the same class of correction becomes less likely.

When the learning is already fully represented by an existing stable card, avoid duplicate prose; instead update trigger/retrieval conditions, maturity, telemetry, or related evidence if those changed.

## Experience record template

- date/time
- environment/runtime
- operation/task class
- tool/capability identity and schema/version signal
- maturity before
- observed route
- external result/readback evidence
- failure/friction
- root cause
- reliable repair/shorter route
- cost/redundancy observation
- maturity after
- wrapper/capability action
- supersedes/related entries

## Promotion logic

`OBSERVED`: one execution or failure.

`REPEATED`: reproduced across more than one run/context.

`STABLE_PLAYBOOK`: safe normal route under stated environment conditions.

`WRAPPER_CANDIDATE`: deterministic chain repeats or is expected to recur enough that model orchestration is wasteful.

`VERIFIED_CAPABILITY`: executable abstraction has explicit contract, success/failure semantics and test/readback evidence.

`DEPRECATED`: stale due to schema/provider/environment change or superior route.

## First imported lessons from 2026-09-03 audit

- Recent control-plane audit sampled 100 commits: 80 clear low-entropy mechanical/control writes, 11 mixed diagnosis/state coordination, 9 substantive content/policy generation. This is a mutation-density proxy, not token accounting.
- Repeated archive/control batches wrote index/backlog/task/TODO/watch/lease/receipt mirrors as serial commits. These are candidates for one logical transition capability.
- QFT Work cutoff demonstrated a partial transaction: Drive artifact existed/read back, but checkpoint/queue/terminal receipt did not complete before runtime cutoff. Compound checkpoint capability is P0.
- GitHub exact-SHA / non-force ref handling is materially safer than blind replacement and should remain part of stable write recipes.
- Google Docs native content edit requires document-specific APIs; Drive metadata update is not content editing.
- Current connector discovery can expose a misleading create/update symptom: an existing README in a newly created repo caused create_file to return `sha wasn't supplied`; smallest discriminating read showed README already existed. Resolve object state before diagnosing permissions/provider failure.
- ChatGPT scheduled-task capacity incident: after the native scheduler reached its task-slot limit, the correct recovery was to classify the limit as local, discover an external scheduler, and deploy GitHub Actions instead of escalating the platform limit to the user. The deeper failure was that WORK_DERIVED_LEARNING did not auto-capture and reinforce this lesson until the user explicitly demanded it.

## Learning objective

The system should become progressively less dependent on model memory and user supervision. Solved recurrent work moves into cards, then wrappers/capabilities; high-capability reasoning returns only for semantic choice, ambiguity, conflict and novel failure. A user should not have to repeat a general operational lesson merely because the previous correction lived only in conversation.