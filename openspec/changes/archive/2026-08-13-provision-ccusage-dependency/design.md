## Context

`cost-tracker.py` resolves per-session cost by shelling out to the `ccusage` CLI (`shutil.which("ccusage")`, then `ccusage session --json --offline`). When `ccusage` is absent the tracker degrades to writing `total_cost_usd = "ERROR"`. The scaffold provisions the tracker's Python files but never provisions `ccusage`, so on a clean machine the tracker's headline feature — cost in USD — never works. `ccusage` is an npm-published Node CLI; the user's package manager is `pnpm`.

The scaffold already models a precondition today: `FileComponent.needs_openspec` classifies a component BLOCKED when the `openspec/` root is missing, and the `install` loop prints a fixed remedy for that case (`scaffold.py` ~1383). That remedy string is hardcoded to the OpenSpec message, so a second precondition needs the reporting path generalized.

## Goals / Non-Goals

**Goals:**
- Provision `ccusage` globally via `pnpm add -g ccusage` when the `cost-tracker` component is installed.
- Classify `cost-tracker` BLOCKED when `pnpm` is not on PATH, and report the unmet precondition in `check`/`list`/`install`.
- Keep the change graceful: a BLOCKED component installs nothing and prints an actionable remedy.

**Non-Goals:**
- Changing `cost-tracker.py`'s runtime behavior (it keeps its `shutil.which` + `ERROR` fallback for defense in depth).
- Pinning a specific `ccusage` version or managing upgrades/drift of the global CLI.
- Provisioning Node/`pnpm` themselves — those remain user-supplied prerequisites.

## Decisions

**Install via `pnpm add -g ccusage`.** The user uses `pnpm`; a global add makes `ccusage` resolvable on PATH so the tracker's existing `shutil.which("ccusage")` lookup succeeds unchanged. Alternative — switch the tracker to `npx ccusage` — was rejected: it adds per-call latency, a network fetch on first run, and still needs a Node runtime, while touching the tracker script that today works when the CLI is present.

**Gate on `pnpm`, not on `ccusage` itself.** The precondition predicate checks `shutil.which("pnpm")` (the install runtime), because that is what the install step needs. Checking for `ccusage` presence instead would make the component permanently BLOCKED on first install (the CLI isn't there yet — that's the point of installing it).

**Generalize the BLOCKED remedy, reusing the `needs_openspec` pattern.** Rather than invent a new mechanism, add an optional per-component precondition (predicate + remedy message) so classification returns BLOCKED and the `install`/`check`/`list` paths print the component-specific remedy instead of the hardcoded OpenSpec string. `needs_openspec` becomes one instance of this shape.

**Run the install as a post-copy step in the component's install path.** The `ccusage` install runs after the tracker files are copied, invoked via `subprocess` with a non-zero exit surfaced as a warning. Because the component is BLOCKED when `pnpm` is missing, the install step only runs when `pnpm` is present.

## Risks / Trade-offs

- `pnpm add -g ccusage` needs network access and can fail (registry down, offline) → surface the failure as a warning; the tracker still degrades to `ERROR`, so a failed install is not fatal to the scaffold run.
- Global install pollutes the user's global pnpm store and is unversioned → acceptable; matches how the tracker already assumes a system-wide `ccusage`, and version pinning is an explicit non-goal.
- A machine with Node/`npm` but not `pnpm` is now BLOCKED even though `ccusage` could be installed another way → acceptable given the user standardized on `pnpm`; the remedy message names `pnpm` so the fix is clear.

## Migration Plan

- Existing scaffolded projects: on the next `install`/`update`, `cost-tracker` re-evaluates; if `pnpm` is present `ccusage` is installed, otherwise the component reports BLOCKED with its remedy.
- Rollback: revert the `scaffold.py` change; the tracker files are unaffected and continue their `ERROR` fallback.

## Open Questions

- None.
