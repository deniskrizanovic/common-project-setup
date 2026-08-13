## Why

The `cost-tracker` component shells out to the `ccusage` CLI to resolve per-session cost in USD (`cost-tracker.py` calls `shutil.which("ccusage")`). The scaffold never provisions `ccusage`, so on a fresh machine every session row is written with `total_cost_usd = "ERROR"` and the tracker's headline feature is silently broken. The scaffold should install `ccusage` and refuse to install a tracker that cannot function.

## What Changes

- Add a `ccusage` global install step to the scaffold, run via `pnpm add -g ccusage`, wired into the `cost-tracker` component's provisioning.
- Gate the `cost-tracker` component on its runtime precondition: when `pnpm` (its install runtime) is absent, classify the component **BLOCKED** rather than installing a tracker that can only log `ERROR`, mirroring the existing `needs_openspec` precondition pattern.
- Report the unmet precondition in `check`/`list`/`install` output so the user sees why the tracker is blocked and how to satisfy it.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `cost-tracker`: add a runtime-dependency requirement — the component provisions the `ccusage` CLI via `pnpm` and is BLOCKED when that runtime is unavailable, instead of installing a tracker that logs `ERROR`.

## Impact

- **Code**: `scaffold.py` — `cost-tracker` component definition (precondition predicate + install step), the BLOCKED classification path, and `check`/`list`/`install` reporting.
- **Dependencies**: adds `pnpm` (and Node) as a precondition for the `cost-tracker` component; `ccusage` becomes a provisioned global CLI rather than an assumed-present one.
- **Specs**: `openspec/specs/cost-tracker/spec.md` gains a dependency-provisioning requirement.
- **Tests**: `tests/test_scaffold_installer.py` — coverage for the BLOCKED-when-runtime-absent path and the install invocation.
