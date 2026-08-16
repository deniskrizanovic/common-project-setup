## Context

Branch protection today is one `PreToolUse` hook (`templates/scripts/branch_guard.py`) wired on `Edit|Write|NotebookEdit`. It returns an `ask` decision when the current branch is `main`/`master`. It is reactive and click-through: it never creates a branch, it fires only on the three edit tools (not on `git commit`/`git push` or Bash-driven writes), and a single approval lets the edit through.

The `restyle-reread-email` post-mortem showed both halves of the gap in one change: propose authored the change while an unrelated feature branch was checked out (guard silent, wrong base), and apply landed edits on `main` after 9 click-approved prompts. The workflow never asserts "this change gets its own branch."

The schema clone already carries project-local workflow guidance baked directly into instruction text — the model-downgrade prompt in `apply.instruction`. That is the established seam for behavior that must fire per propose/apply session, because hooks fire on tool events and have no notion of "which OpenSpec workflow is running."

## Goals / Non-Goals

**Goals:**
- Ensure every OpenSpec change is authored (propose) and implemented (apply) on a dedicated non-trunk branch.
- Make trunk a hard stop in both instructions, consistent with the existing downgrade prompt.
- Keep the change additive — no behavior removed from the existing instructions or the hook.

**Non-Goals:**
- Changing `branch_guard.py` (escalation to `block` is a separate proposal, `escalate-branch-guard-to-block`).
- Gating `git commit`/`git push` on branch — that path is `commit_gate.py` and out of scope here.
- Enforcing a rigid branch-name scheme. `change/<change-name>` is the suggested convention, not a validated constraint.

## Decisions

**Decision: bake the branch step into `proposal.instruction` and `apply.instruction`, not into a hook.**
Rationale: the same reasoning that placed the downgrade prompt in the instruction applies — a hook cannot know a propose/apply workflow is running, and the check must fire once per session before artifact/task work, not on every edit. The hook stays as the edit-time backstop. Alternative considered: a new PreToolUse hook that auto-creates a branch. Rejected — hooks can't distinguish workflow context, auto-creating branches on arbitrary edits is surprising, and it duplicates `branch_guard`'s blast radius.

**Decision: hard stop on trunk, confirm-intent on a feature branch.**
On `main`/`master` the agent must create/switch (or ask) before proceeding — mirrors the downgrade prompt's "ask, then end turn" pattern. On an existing non-trunk branch the agent confirms it is the intended branch rather than silently assuming, which is exactly what went wrong when `restyle` was proposed on the stale `add-notion-link-rereader` branch.

**Decision: suggest `change/<change-name>` but do not validate it.**
Keeps the guidance prose (consistent with the downgrade prompt) and avoids a brittle name gate. The important invariant is "not trunk," not a specific prefix.

## Risks / Trade-offs

- [Prose guidance is advisory, like the downgrade prompt — an agent could still skip it] → The edit-time `branch_guard` hook remains as the backstop; escalating it to `block` (separate proposal) hardens the floor.
- [Confirm-intent on a feature branch adds a turn] → Cheap relative to authoring a change on the wrong base; only asks when not already on a clearly change-scoped branch.
- [Existing projects don't pick this up until their schema clone is regenerated] → Same rollout property as the downgrade prompt; documented in Impact.

## Migration Plan

Edit `templates/openspec/schemas/spec-driven/schema.yaml`: add a branch-isolation preamble to `proposal.instruction` and `apply.instruction`. No data migration. Projects adopt it when scaffolded or when the schema clone is next regenerated/updated.

## Open Questions

- None blocking. Whether to later add a lightweight branch-name validation is deferred.
