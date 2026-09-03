# Failure Pattern — GitHub Actions Evidence Push Rejected by Concurrent Main Advance

status: STABLE_PLAYBOOK
class: CONCURRENT_REPOSITORY_WRITE_FAILURE
first_recorded: 2026-09-03

environment: GitHub Actions writing generated evidence back to the same repository while another actor may also update `main`.

## Signature

A workflow successfully generates and commits deterministic evidence locally, but the final `git push` fails with non-fast-forward because `origin/main` advanced after checkout.

Observed incident: AI Executor Radar run #1 successfully fetched 4/6 sources and generated `state.json`, `events.jsonl`, and snapshots, then failed only at the final push because another repository write occurred while the job was running.

## Root cause

The workflow treated checkout HEAD as if it would remain the current remote HEAD until completion. Repository-level workflow concurrency only serializes matching workflow jobs; it does not exclude external connector/user/bot writes to the same branch.

## Reliable repair

After creating the local evidence commit, refresh the remote branch and replay the evidence commit before pushing:

`git commit -> git fetch origin main -> git rebase origin/main -> git push origin HEAD:main`

If rebase conflicts, fail closed and require reconciliation rather than force-pushing.

## Design implication

Any background worker that writes generated state to a shared canonical branch must assume external branch movement. Prefer optimistic concurrency with fetch/rebase or a stronger transactional/PR branch pattern; never use force push merely to make the job succeed.

## Verification

AI Executor Radar run #2 completed successfully after the workflow adopted the fetch/rebase/push sequence, and generated baseline state was read back from the repository.

## Related patterns

- SERIAL-MIRROR-MICRO-WRITES
- TOOL-CALL-SUCCESS-WITHOUT-BUSINESS-COMPLETION
- LOCAL_PATH_LIMIT_IS_NOT_GLOBAL_IMPOSSIBILITY
