## 1. Initialization probe

- [x] 1.1 Add `openspec_initialized(project_root) -> bool` to `scaffold.py`: shell `openspec list --json` (with a timeout), parse JSON, return `True` only when `.root` is non-null; return `False` on missing CLI, non-zero exit, or parse failure
- [x] 1.2 Add a `BLOCKED` status constant alongside MISSING/STALE/MODIFIED/OK

## 2. Component tagging

- [x] 2.1 Tag `config-baseline`, `config-interview`, and `schema-clone` as requiring an OpenSpec root (a `needs_openspec` flag on the component or a name set in `build_registry`)
- [x] 2.2 Thread the single `openspec_initialized` result through `compute_status` so blocked components do not each re-invoke the CLI

## 3. Status + install gating

- [x] 3.1 In status computation, classify a `needs_openspec` component BLOCKED when the root is absent, taking precedence over MISSING
- [x] 3.2 In `cmd_install`, refuse a BLOCKED component: print `Run \`openspec init . --tools claude\` first`, skip it, and ensure no file under `openspec/` is written for it (do not auto-run init)
- [x] 3.3 In `cmd_check` / `cmd_list`, report BLOCKED read-only with no writes or prompts
- [x] 3.4 Confirm `enforcement-hooks`, `cost-tracker`, `lint-gates`, plugins, and skills are unaffected and still install with no root

## 4. Tests

- [x] 4.1 Test `openspec_initialized`: non-null `.root` → True; null `.root`, missing CLI, and bad JSON → False (inject a fake CLI/subprocess)
- [x] 4.2 Test `install` blocks the three OpenSpec-dependent components with no root, writes nothing under `openspec/`, and prints the init remedy
- [x] 4.3 Test `install` still installs OpenSpec-independent components with no root
- [x] 4.4 Test `check` / `list` report BLOCKED read-only
- [x] 4.5 Test that with a present root the three components follow their normal MISSING/OK/MODIFIED flow

## 5. Docs

- [x] 5.1 Update `README.md`: document the OpenSpec-root precondition, the BLOCKED status in the drift table, and which components it gates
