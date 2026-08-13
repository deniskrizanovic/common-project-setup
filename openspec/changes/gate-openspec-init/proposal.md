## Why

`scaffold.py install` writes `openspec/config.yaml` and the `spec-driven` schema clone without ever checking that OpenSpec is initialized in the target project. On a repo that never ran `openspec init`, `install_file_component` silently `mkdir`s `openspec/` and lays down a partial tree that the `openspec` CLI does not recognize as a root (`openspec list --json` reports `.root: null`). The user ends up with a fabricated, half-initialized directory that is worse than a clean failure.

## What Changes

- Add a precondition check to `scaffold.py`: before installing the OpenSpec-dependent components, verify OpenSpec is initialized by running `openspec list --json` and requiring a non-null `.root`.
- Tag `config-baseline`, `config-interview`, and `schema-clone` as requiring an OpenSpec root. When the root is absent (or the `openspec` CLI is unavailable), these components are classified **BLOCKED** rather than MISSING.
- `install` refuses to install a BLOCKED component and prints the exact remedy (`openspec init . --tools claude`) instead of fabricating a tree; it does **not** auto-run init.
- `check` and `list` report BLOCKED read-only, distinguishing "precondition unmet" from "installable now".
- OpenSpec-independent components (`enforcement-hooks`, `cost-tracker`, `lint-gates`, plugins, skills) are unaffected and still install on a non-OpenSpec repo.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `scaffold-installer`: adds an OpenSpec-root precondition and a BLOCKED status to the drift classification and install/check/list behavior.

## Impact

- `scaffold.py`: new `openspec_initialized()` probe (shells `openspec list --json`, parses `.root`), a `BLOCKED` status constant, per-component "needs OpenSpec root" tagging, and gating in `cmd_install` / `cmd_check` / `cmd_list`.
- Depends on the `openspec` CLI being on `PATH`; absence is treated as not-initialized (block + hint), never a fabricated tree.
- No behavior change for already-initialized repos.
