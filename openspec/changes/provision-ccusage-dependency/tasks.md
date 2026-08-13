## 1. Generalize the precondition/BLOCKED mechanism

- [ ] 1.1 Add an optional per-component precondition to `FileComponent` (predicate returning satisfied/unmet + a remedy message), keeping `needs_openspec` working as one instance of this shape.
- [ ] 1.2 Update `classify_file_component` (~line 934) so any unmet precondition — not just `needs_openspec` — returns BLOCKED.
- [ ] 1.3 Generalize the BLOCKED reporting in the `install` loop (~line 1383) and in `check`/`list` to print the component-specific remedy instead of the hardcoded OpenSpec string.

## 2. Provision ccusage for cost-tracker

- [ ] 2.1 Add a `pnpm`-on-PATH precondition (`shutil.which("pnpm")`) to the `cost-tracker` component with a remedy message naming `pnpm` (~line 770).
- [ ] 2.2 Add a post-copy install step to the `cost-tracker` install path that runs `pnpm add -g ccusage` via `subprocess`, surfacing a non-zero exit / failure as a warning without aborting the scaffold run.

## 3. Tests & docs

- [ ] 3.1 Add tests in `tests/test_scaffold_installer.py` for: cost-tracker BLOCKED when `pnpm` absent (with correct remedy reported), and the `pnpm add -g ccusage` invocation firing when `pnpm` is present.
- [ ] 3.2 Update README / scaffold docs to note `pnpm` (and Node) as a prerequisite for the `cost-tracker` component and that `ccusage` is provisioned automatically.
- [ ] 3.3 Run the test suite and `openspec validate --change provision-ccusage-dependency --strict`.
