## Why

The scaffold's branch protection is a single `PreToolUse` `ask` hook (`branch_guard.py`) that fires only on `Edit/Write/NotebookEdit` and only nags — it never puts you on a branch. In practice that leaves a gap: an OpenSpec change can be proposed on whatever branch happens to be checked out and applied straight onto `main`.

Real example (`restyle-reread-email` in NotionLinkReReader):
- **propose** ran while a stale, unrelated feature branch (`add-notion-link-rereader`) was still checked out, so `branch_guard` was correctly silent and the change was authored off the wrong base — no branch was ever created for it.
- **apply** ran after `main` had been checked out. `branch_guard` fired all 9 edits with `ask`, but each was click-approved, so the implementation landed directly on `main`.

Nothing in the propose/apply workflow ensures a dedicated branch exists for a change. The guard is reactive (nag-at-edit) and trivially bypassed with one approval. Branching is left to the operator's memory, and the failure mode is silent — work ends up on trunk or on an unrelated branch with no signal that anything was wrong.

## What Changes

Bake a branch-isolation step into the project-local `spec-driven` schema clone's `proposal` and `apply` instructions — the same mechanism the model-downgrade prompt uses (`templates/openspec/schemas/spec-driven/schema.yaml`).

- **proposal instruction**: before writing artifacts, ensure work is on a change-scoped branch (a non-trunk branch named for the change, e.g. `change/<change-name>`). If on `main`/`master`, direct the agent to create and switch to that branch first; if already on a non-trunk branch, confirm it is the intended branch for this change before proceeding.
- **apply instruction**: before working the first task, perform the same check — refuse to apply on `main`/`master`, and ensure a change-scoped branch is checked out.
- The step is a **hard stop** on trunk (like the downgrade prompt): the agent creates/switches the branch or asks the user, and does not write artifacts / work tasks on `main`/`master`.
- This is additive to `branch_guard.py`; the hook stays as the edit-time backstop.

## Capabilities

### New Capabilities
- `spec-change-branch-isolation`: The propose and apply instructions in the schema clone ensure an OpenSpec change is authored and implemented on a dedicated, non-trunk branch rather than on `main`/`master` or an unrelated branch.

### Modified Capabilities
<!-- none: apply-workflow-guidance stays scoped to the model-downgrade prompt; branch isolation is a distinct concern spanning both propose and apply instructions -->

## Impact

- `templates/openspec/schemas/spec-driven/schema.yaml` — `proposal.instruction` and `apply.instruction` gain a branch-isolation preamble.
- Any project scaffolded (or updated) after this change picks up the new instructions when its schema clone is regenerated.
- No change to `branch_guard.py`; the hook remains the edit-time backstop and is complementary.
- Tests: instruction text is prose guidance (no executable gate), consistent with the existing model-downgrade prompt requirement.
