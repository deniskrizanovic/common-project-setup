## 1. Retro skill template

- [x] 1.1 Create `templates/.claude/skills/scaffold-retro/SKILL.md` with frontmatter (`name: scaffold-retro`; the description triggers on "retro", "what should go back into common-project-setup", "upstream scaffold improvements"). Add a read-only boundary section stating that the only allowed write is `.scaffold/retro/retro-<YYYY-MM-DD>.md` and that issues, PRs, pushes, and edits to scaffold or project files are not allowed. Verify: file exists and `tests/test_scaffold_retro.py::test_skill_declares_read_only_boundary` passes.
- [x] 1.2 Add the "Scaffold-owned inventory" section: tracked file paths from `build_registry()`, gate names from `BASE_COMMIT_GATES` and `STATIC_ANALYSIS_GATES`, and the hook commands written by `wire_hooks()`, in a fenced, machine-parseable list. Verify: `tests/test_scaffold_retro.py::test_skill_inventory_matches_scaffold` passes and fails when an entry is removed from the list.
- [x] 1.3 Add the baseline-resolution steps (design D3: env var, then `.scaffold/source.json`, then ask the user for a local checkout, then a temp clone of the GitHub URL outside the project, then `git show <source_sha>:templates/<dest>`) and the offline-degradation rule (list paths only, note the missing baseline). Verify: `tests/test_scaffold_retro.py::test_skill_defines_offline_degradation` passes.
- [x] 1.4 Add an ordered checklist for each candidate category (modified scaffold files with a diff, local gates, local hooks and scripts, wishlist overrides, config rules, recurring patterns from `CLAUDE.md` and the OpenSpec archive, with the archive skipped when `openspec/` is absent). Verify: `tests/test_scaffold_retro.py::test_skill_instructs_modified_file_diff` and `tests/test_scaffold_retro.py::test_skill_covers_all_candidate_categories` pass.
- [x] 1.5 Add the generalizability and exclusion rules (design D5: exclude the `context:` block and domain code, redact secret-like values as `<redacted>`). Verify: `tests/test_scaffold_retro.py::test_skill_excludes_project_specific_and_secrets` passes.
- [x] 1.6 Add the report template: sections Summary, Baseline status, one section per category, and Categories checked with none found. Each candidate has category, evidence, change summary, benefits, risks/costs, recommendation (`promote` / `adapt` / `keep-local`), upstream target, and a suggested kebab-case change name (omitted for `keep-local`). Include the no-candidates form. Verify: `tests/test_scaffold_retro.py::test_skill_defines_report_contract` passes.

## 2. Component registration

- [x] 2.1 Register `FileComponent(id="scaffold-retro", ...)` in `build_registry()` with the single tracked file and no precondition, `needs_openspec`, or `needs_git`. Verify: `tests/test_scaffold_retro.py::test_install_writes_retro_skill`, `tests/test_scaffold_retro.py::test_retro_skill_modified_detected`, and `tests/test_scaffold_retro.py::test_retro_installs_without_openspec_root` pass.
- [x] 2.2 Run the full suite and the spec lint against the new spec. Verify: `uv run pytest -q` is green and `python3 templates/scripts/lint_specs.py` resolves every `> **Tests:**` citation in `openspec/changes/add-scaffold-retro-skill/specs/scaffold-retro/spec.md`.

## 3. Documentation

- [x] 3.1 Update `README.md`: add `scaffold-retro` to the file-component list and add a short "Retro workflow" section (run `/scaffold-retro` in a child project, review `.scaffold/retro/retro-<date>.md`, then run `/opsx:propose` in `common-project-setup` with the chosen candidates). Verify: README lists the component and the workflow, and the component ids in README match `python3 scaffold.py list`.

## 4. End-to-end check

- [x] 4.1 In a throwaway provisioned project, install `scaffold-retro`, edit `scripts/commit_gate.py`, add a custom gate to `.scaffold/gates.json`, and invoke the skill. Verify: the report appears at `.scaffold/retro/retro-<today>.md`, lists both candidates with all required fields, and `git status` in that project shows no other changed paths.

## Workflow follow-up

- Archive the change with `/opsx:archive` after merge, which syncs `scaffold-retro` into `openspec/specs/`.
