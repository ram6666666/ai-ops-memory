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
- a cross-model/runtime difference affects routing or handoff.

Routine success using an already stable operation card does not merit another prose entry unless useful telemetry is collected automatically.

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

## Learning objective

The system should become progressively less dependent on model memory. Solved recurrent work moves into cards, then wrappers/capabilities; high-capability reasoning returns only for semantic choice, ambiguity, conflict and novel failure.
