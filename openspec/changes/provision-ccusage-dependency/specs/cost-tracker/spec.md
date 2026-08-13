## ADDED Requirements

### Requirement: ccusage runtime dependency
The cost-tracker component SHALL provision the `ccusage` CLI it depends on to resolve per-session cost, installing it globally via `pnpm` during component install. The component SHALL treat the `pnpm` install runtime as a precondition: when `pnpm` is unavailable it SHALL be classified BLOCKED and SHALL NOT install a tracker that cannot resolve cost.

#### Scenario: ccusage provisioned during install
- **WHEN** the `cost-tracker` component is installed and `pnpm` is available
- **THEN** the scaffold installs the `ccusage` CLI globally via `pnpm` so the tracker's `shutil.which("ccusage")` lookup resolves and cost is recorded in USD rather than `ERROR`

#### Scenario: blocked when runtime absent
- **WHEN** the `cost-tracker` component is evaluated and `pnpm` is not on PATH
- **THEN** the component is classified BLOCKED and `check`/`list`/`install` report the unmet `pnpm` precondition instead of installing a tracker that can only log `ERROR`
