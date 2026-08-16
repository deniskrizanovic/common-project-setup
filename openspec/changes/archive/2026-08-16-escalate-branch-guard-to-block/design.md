## Context

`branch_guard.py::decision()` returns `permissionDecision: "ask"` on `main`/`master`. Claude Code's PreToolUse contract treats `ask` as "prompt the user, who may approve or deny" — a single approval clears it. Evidence from the `restyle-reread-email` apply session: 9 edits on `main`, 9 `ask` prompts, 9 approvals, work landed on trunk. `deny` (block) is the stronger decision that the contract also supports; it refuses the tool call and surfaces the reason, with no one-tap approval path.

## Goals / Non-Goals

**Goals:**
- Make edits on `main`/`master` blocked by default, not click-through.
- Preserve a deliberate escape hatch (create a branch, or disable/bypass the hook).
- Keep the change minimal and localized to the hook, its spec, and its tests.

**Non-Goals:**
- Adding the proactive branch-creation step (that is `branch-per-openspec-change`).
- Gating `git commit`/`git push` (that is `commit_gate.py`).
- Changing behavior on non-trunk branches.

## Decisions

**Decision: return `deny` instead of `ask`.**
Rationale: `ask` is reflexively approved during a working session, so it fails as a floor. `deny` forces an explicit, deliberate action to edit trunk. The escape hatch moves from "one tap" to "create a branch or disable the hook" — deliberate, not reflexive. Alternative considered: keep `ask` but reword the reason more sternly. Rejected — wording does not change the one-tap approval mechanic.

**Decision: keep the escape hatch in the reason string.**
The `deny` reason explains how to proceed legitimately (branch, or disable the hook) so the block is not a dead end. This keeps the hook usable for the rare intentional trunk edit without reintroducing reflexive approval.

**Decision: update the existing test in place, keep its name.**
`test_branch_guard_asks_on_trunk` asserts the trunk decision; its assertion flips from `ask` to `deny`. Renaming is cosmetic churn; the docstring/comment can note the block. `test_branch_guard_silent_on_feature` is unchanged.

## Risks / Trade-offs

- [Legitimate quick edits on `main` (e.g. README typo) now blocked] → Reason string tells the user how to branch or disable; trunk edits should be deliberate anyway.
- [A `deny` that surprises users mid-session] → The reason names the branch and the remedy; and the companion `branch-per-openspec-change` step means well-run workflows are already off trunk before any edit.
- [Downstream tooling that expected `ask`] → Only this repo's tests consume the decision shape; updated in the same change.

## Migration Plan

Edit `templates/scripts/branch_guard.py` (`decision()` return), update `tests/test_file_components.py`, the `enforcement-hooks` spec, and the README line. No data migration. Existing scaffolded projects pick up the blocking behavior when their `scripts/branch_guard.py` is next updated by the scaffold.

## Open Questions

- None blocking.
