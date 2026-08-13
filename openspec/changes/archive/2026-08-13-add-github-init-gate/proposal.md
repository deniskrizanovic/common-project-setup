## Why

A freshly scaffolded project has local branch guarding (`branch_guard.py`) but
nowhere to push and no server-side branch protection, because it has no GitHub
remote. Nothing in the scaffold surfaces that gap, so it goes unnoticed until a
push fails. We want the scaffold to *nag* — tell the user to create the repo —
and hand them the exact `gh` commands, without taking the outward action itself.

## What Changes

- Add a new print-only registry component, `github-init`, walked by `list`,
  `check`, and `install` like every other component.
- Detection keys on the git `origin` remote:
  - not a git repository → **BLOCKED** (precedence over MISSING, mirrors the
    no-OpenSpec-root gate).
  - no `origin` remote → **MISSING** (the recurring nag).
  - `origin` present (any host) → **OK**, reported and never managed.
- `install` on a MISSING `github-init` **prints the exact commands and runs
  nothing outward** — consistent with the existing refusals to auto-run
  `openspec init`, `claude plugin install`, and `npx skills add`. Printed:
  - primary (gh CLI): `gh repo create <basename> --public --source=. --remote=origin --push`
  - fallback (no gh): create the repo on github.com, then
    `git remote add origin …` and `git push -u origin main`.
- Repo name defaults to the project directory basename; no prompt.
- The component tracks **no files**, records no hash, and takes no side effects,
  so it has no STALE/MODIFIED states — only BLOCKED / MISSING / OK.

## Capabilities

### New Capabilities
- `github-init-gate`: detects the absence of a GitHub `origin` remote and, on
  `install`, prints (never runs) the `gh`/`git` commands to create the repo and
  push, gated BLOCKED when the project is not a git repository.

### Modified Capabilities
<!-- None. github-init is a self-contained new component; existing scaffold-installer
     classification states are reused conceptually but no existing requirement changes. -->

## Impact

- `scaffold.py`: new component in `build_registry()`; a `needs_git` gate
  paralleling the existing `needs_openspec` gate; classification for a
  no-tracked-files, side-effect-free component.
- No `templates/` additions (nothing is copied to disk).
- No changes to remote GitHub state performed by the tool — output is advisory.
- Depends on `git` for detection; `gh` optional (fallback path printed when absent).
