## Why

Enabled components live across four disconnected channels (marketplace plugins, github-sourced skills, in-repo committed skills, and per-project overrides), so there is no single place to declare what a new project should get. Today `scaffold_base/plugins.json` is hand-edited and only covers marketplace plugins; github-sourced skills (matt pocock's `grill-me`, `dk-skills` entries) have no scaffold representation at all. One curated manifest should be the source of truth, with the installer fanning out to each real install mechanism.

## What Changes

- Introduce `scaffold_base/manifest.yaml` as the single hand-edited source of truth, with typed `plugins:` and `skills:` sections.
- The installer generates `plugins.json` and `skills-lock.json` from the manifest. Both artifacts are **committed** so their diffs are reviewable; they become generated files, never hand-edited. **BREAKING**: `scaffold_base/plugins.json` is no longer authored directly.
- Add a skill reconciler to `scaffold.py` that classifies github-sourced skills (MISSING / STALE / EXTRA) against `skills-lock.json`, installs via `npx skills add`, checks staleness via `npx skills check`, and never removes EXTRA skills — mirroring the existing plugin reconciler.
- Preserve the per-item install UX: one `[i]nstall/update, [s]kip?` prompt per skill, matching the current plugin flow. No batch install.
- Falls back to printing the exact `npx skills` commands when the CLI is absent, mirroring the `claude` CLI fallback.
- Add a drift guard so committed `plugins.json` / `skills-lock.json` must stay in sync with `manifest.yaml`.
- Publish `gherkin-authoring` (currently only in `collaborativegherkin/.claude/skills/`) to `deniskrizanovic/dk-skills` so the manifest can reference it via the github-skill channel.
- Baseline manifest content: plugins `caveman`, `superpowers`; skills `mattpocock/skills:grill-me`, `grill-with-docs`, `improve-codebase-architecture`, `deniskrizanovic/dk-skills:diff-org-changes`, `dk-cosmic-counting-coach`, `gherkin-authoring`.

## Capabilities

### New Capabilities
- `component-manifest`: The single YAML manifest format (typed `plugins:` / `skills:` sections) that is the source of truth for all desired components, and the rule that `plugins.json` / `skills-lock.json` are generated artifacts derived from it.
- `skill-management`: Reconciliation of github-sourced skills against `skills-lock.json` — classify, install via `npx skills add`, staleness via `npx skills check`, EXTRA-never-removed, per-item prompt, CLI-absent fallback.

### Modified Capabilities
- `plugin-management`: The desired-plugin set is now derived from `manifest.yaml` rather than authored directly in `plugins.json`; `plugins.json` becomes a generated, committed artifact.

## Impact

- **Code**: `scaffold.py` (new manifest reader, skill reconciler, artifact generator, drift check); new `scaffold_base/manifest.yaml`; `scaffold_base/plugins.json` becomes generated; new generated `scaffold_base/skills-lock.json`.
- **Tests**: extend `tests/test_plugin_management.py`; new tests for skill reconciliation, manifest parsing, artifact generation, and drift.
- **External**: publish `gherkin-authoring` to `deniskrizanovic/dk-skills` (a git push to that repo, a prerequisite for the manifest reference to resolve). Depends on the `npx skills` CLI at install time (degrades gracefully when absent).
- **Per-project overrides**: `.scaffold/plugins.json` composition behavior is retained; a parallel skill override path is added.
