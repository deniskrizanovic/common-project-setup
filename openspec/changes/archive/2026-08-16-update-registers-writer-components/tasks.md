## 1. Tests (TDD — write first, watch fail)

- [x] 1.1 Remove `test_update_static_analysis_reports_install_only` (asserts the old install-only behavior that this change replaces)
- [x] 1.2 Add `test_update_writer_blocked_prints_remedy`: Python project, `ruff` absent from PATH → `cmd_update` reports the static-analysis component BLOCKED with its remedy and writes no `.scaffold/gates.json` gate
- [x] 1.3 Add `test_update_writer_registers_gates_when_ready`: Python project, `ruff` present on PATH, gates not yet registered → `cmd_update` runs the writer and registers `lint:ruff` in `.scaffold/gates.json`
- [x] 1.4 Add `test_update_writer_already_registered_noop`: gates already registered → `cmd_update` reports current and writes nothing further
- [x] 1.5 Add `test_update_still_excludes_filler_and_printer`: `cmd_update` does not evaluate filler/printer components and issues no interactive prompt

## 2. Implementation

- [x] 2.1 In `cmd_update` (scaffold.py), drop `c.writer is None` from the target filter so writer components enter the evaluated set (keep `filler is None` and `printer is None` exclusions)
- [x] 2.2 Add a writer branch in `cmd_update`'s per-component loop, before the tracked-file copy path, mirroring `cmd_install`'s writer handling: BLOCKED → print `{id}: BLOCKED — {remedy}` via `unmet_precondition`; OK → report current, no-op; MISSING → run `comp.writer`. Writers carry no tracked hash, so MODIFIED/STALE never apply to them
- [x] 2.3 Confirm the `component is not None and not targets` install-only messaging still behaves correctly for filler/printer named targets (writer named targets now resolve instead of hitting that branch)

## 3. Verify

- [x] 3.1 Run `pytest -q` — full suite green, new tests pass
- [x] 3.2 Run `scaffold.py update` against NotionLinkReReader (Python, ruff absent) and confirm it now reports static-analysis BLOCKED with the ruff install remedy
