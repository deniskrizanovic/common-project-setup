## 1. Hook change

- [x] 1.1 In `templates/scripts/branch_guard.py`, change `decision()` to return `permissionDecision: "deny"` on `main`/`master` (was `"ask"`), and update the reason string to name the branch, direct the user to create/switch to a feature branch, and note that trunk edits require deliberately creating a branch or disabling the hook.
- [x] 1.2 Confirm behavior on non-trunk branches is unchanged (returns `None` = no output = allow).

## 2. Spec and tests

- [x] 2.1 Update `openspec/specs/enforcement-hooks/spec.md` Branch-guard requirement to assert `deny` (handled at archive via the delta spec; verify wording matches).
- [x] 2.2 Update `tests/test_file_components.py::test_branch_guard_asks_on_trunk` to assert the decision is `deny` and the branch name appears in the reason; leave `test_branch_guard_silent_on_feature` unchanged.
- [x] 2.3 Update the `README.md` enforcement-hooks line ("asks on edits to `main`/`master`") to describe blocking.

## 3. Verification

- [x] 3.1 Run `pytest -q` and confirm the branch-guard tests pass.
- [x] 3.2 Run the repo lint gates and `openspec validate escalate-branch-guard-to-block`.
