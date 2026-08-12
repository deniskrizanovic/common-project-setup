## 1. Publish gherkin-authoring (external prerequisite)

- [x] 1.1 Copy `gherkin-authoring/` from `collaborativegherkin/.claude/skills/` into the `deniskrizanovic/dk-skills` repo
- [x] 1.2 Commit and push to `deniskrizanovic/dk-skills`; verify `owner/repo:gherkin-authoring` resolves via `npx skills add --dry-run` (or equivalent)

## 2. Manifest format

- [x] 2.1 Author `scaffold_base/manifest.yaml` with typed `plugins:` and `skills:` sections and the baseline set (caveman, superpowers; grill-me, grill-with-docs, improve-codebase-architecture, diff-org-changes, dk-cosmic-counting-coach, gherkin-authoring)
- [x] 2.2 Implement a manifest reader in `scaffold.py` that parses both sections and validates required fields (plugin `id`, skill `owner/repo:path`), erroring on malformed entries
- [x] 2.3 TEST: manifest parsing — valid sections parse, malformed plugin/skill entries rejected with a clear error; run and confirm green

## 3. Artifact generation

- [x] 3.1 Implement generator: `manifest.yaml` → `scaffold_base/plugins.json` in the existing `{ plugins: [{ id, marketplaceSource }] }` shape
- [x] 3.2 Implement generator: `manifest.yaml` → `scaffold_base/skills-lock.json` with `source`, `sourceType`, `skillPath`, `computedHash` (matching the `npx skills` CLI hash format)
- [x] 3.3 TEST: generator output for plugins.json and skills-lock.json matches expected fixtures; run and confirm green
- [x] 3.4 Regenerate and commit both artifacts; confirm `plugins.json` matches prior content minus scopezilla
- [x] 3.5 Implement drift-guard check that fails when committed artifacts differ from generator output
- [x] 3.6 TEST: drift guard — in-sync passes, drifted fails and names the artifact; run and confirm green

## 4. Skill reconciler

- [x] 4.1 Add `SkillComponent` and a `_skill_components()` builder reading from the manifest (mirrors `_plugin_components`)
- [x] 4.2 Implement `read_skills_lock()` and `classify_skills(desired, lock)` producing MISSING/STALE/EXTRA/OK (STALE via `npx skills check`)
- [x] 4.3 TEST: skill classification — MISSING/STALE/EXTRA/OK correct, EXTRA never removed; run and confirm green
- [x] 4.4 Implement `skill_install_commands()` and `install_skill()` shelling out to `npx skills add`, with CLI-absent fallback that prints commands
- [x] 4.5 TEST: CLI-absent fallback — skill actions reported unavailable, commands printed, run does not fail; run and confirm green
- [x] 4.6 Wire skills into `compute_status`, `cmd_list`, `cmd_check`, and the per-item `cmd_install` prompt loop (`[i]nstall/update, [s]kip?`)
- [x] 4.7 TEST: per-item prompt — one prompt per non-OK skill, OK skills skipped, no batch install; run and confirm green
- [x] 4.8 Add per-project skill override composition (parallel to `.scaffold/plugins.json`)
- [x] 4.9 TEST: per-project skill override composes/extends base wishlist; run and confirm green

## 5. Regression

- [x] 5.1 Extend `tests/test_plugin_management.py` for the generated-plugins.json path; run and confirm green

## 6. Validation

- [x] 6.1 Run `openspec validate unified-component-manifest`
- [x] 6.2 Run full test suite and the drift guard; confirm all green
