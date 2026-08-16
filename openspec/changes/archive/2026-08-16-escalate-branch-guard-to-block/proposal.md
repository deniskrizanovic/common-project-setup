## Why

`branch_guard.py` returns an `ask` permission decision when an edit is attempted on `main`/`master`. `ask` is trivially click-through: in the `restyle-reread-email` apply session the guard fired on all 9 edits and all 9 were approved, so the implementation landed directly on `main`. A soft prompt that is dismissed with a single Enter is not a floor — it is a speed bump, and under a working session it reads as noise to be cleared.

Editing on trunk is the exact mistake the guard exists to prevent. For that specific action, the safer default is to block outright and force an explicit branch, rather than offer one-tap approval. The workflow-level branch step (proposed separately in `branch-per-openspec-change`) makes branching proactive; this change hardens the reactive backstop so that even when the workflow step is skipped, edits on trunk cannot be waved through by reflex.

## What Changes

Escalate `branch_guard.py`'s decision on `main`/`master` from an `ask` permission decision to a `deny` (block) decision.

- On `main`/`master`, the hook returns a `deny` permission decision whose reason names the branch and directs the user to create/switch to a feature branch.
- The decision reason keeps an explicit escape hatch in prose: the user can create a branch, or (if they truly intend to edit trunk) temporarily disable/bypass the hook — a deliberate act, not a reflexive approval.
- Behavior on non-trunk branches is unchanged (no output = allow).
- Update the `enforcement-hooks` spec's Branch-guard requirement and the branch-guard tests to assert `deny` instead of `ask`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `enforcement-hooks`: the Branch-guard requirement changes the emitted permission decision on `main`/`master` from `ask` to `deny`.

## Impact

- `templates/scripts/branch_guard.py` — `decision()` returns `permissionDecision: "deny"` (was `"ask"`), with an updated reason string.
- `tests/test_file_components.py` — `test_branch_guard_asks_on_trunk` updated (assert `deny`); `test_branch_guard_silent_on_feature` unchanged.
- `openspec/specs/enforcement-hooks/spec.md` — Branch-guard requirement and scenario updated to `deny`.
- `README.md` — the enforcement-hooks description ("asks on edits to `main`/`master`") updated to reflect blocking.
- Trade-off: legitimate trunk edits (e.g. a quick README fix on `main`) now require creating a branch or disabling the hook. Acceptable — trunk edits should be deliberate.
