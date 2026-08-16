## Why

The `update` subcommand silently skips every writer component (those that derive local project state instead of copying tracked files), so a writer component newly added to the scaffold — such as `static-analysis` — never reaches child projects through `update`; it only ever runs on `install`. As the scaffold evolves, `update` is the mechanism that propagates new gates into existing projects, so a writer that `update` cannot see is a writer that silently never nags. A child project on Python with `ruff` absent from PATH ran `update` and got no BLOCKED remedy, no gate registration, and no signal at all.

## What Changes

- `update` SHALL evaluate writer components (currently excluded because they have no tracked files to re-copy) instead of skipping them.
- When a writer component's precondition is unmet, `update` SHALL report it BLOCKED with the component-specific remedy (mirroring `install`), so an evolving scaffold can nag existing projects to install a newly-required toolchain.
- When a writer component is not yet satisfied and its precondition is met, `update` SHALL run the writer to derive local project state (e.g. register the static-analysis gates).
- When a writer component is already satisfied, `update` SHALL report it current and write nothing.
- `update` SHALL remain non-interactive: `filler` (interview) and `printer` (advisory) components stay excluded from `update`; only `writer` components are added.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `scaffold-installer`: the `update` subcommand's component-selection behavior changes — writer components are no longer skipped and are classified/handled (BLOCKED / satisfied / run-the-writer) during `update`.

## Impact

- `scaffold.py` — `cmd_update`: writer components enter the target set and get a dedicated BLOCKED/OK/MISSING branch mirroring `cmd_install`'s writer handling.
- `tests/test_static_analysis_gates.py` — new coverage for `update` on writer components (BLOCKED remedy when toolchain absent, gate registration when present, no-op when already registered).
- No change to `install`, `check`, or `list`. No change to `filler`/`printer` handling. Child projects gain the ability to receive newly-added writer components (e.g. static-analysis gates) via `update`.
