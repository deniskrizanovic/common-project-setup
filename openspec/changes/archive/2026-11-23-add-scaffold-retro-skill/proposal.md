# Proposal

## Why

Child projects evolve the scaffold's components in place — patching `commit_gate.py`, adding gates to `.scaffold/gates.json`, wiring extra hooks, extending the plugin/skill wishlist, tightening `openspec/config.yaml` rules — and those improvements stay stranded in the child. The drift report (`check`) says *that* a file is MODIFIED, but nothing harvests *what* changed or whether it is worth promoting back into `common-project-setup`. A retro skill closes that loop: run it in a provisioned project, get a reviewable list of upstream candidates.

For modified tracked files alone, existing tooling gets most of the way: `install` already shows a diff. That diff is against the *incoming* template, though, so it mixes upstream changes with local edits. The retro skill earns its place mainly on what drift tracking cannot see:

- **Additions the scaffold does not track**, such as local gates, hooks, scripts, wishlist entries, and config rules. `check` never reports these, because only file-component hashes are recorded.
- **A judgement step.** For each finding, the skill decides whether the change is generic enough to promote or specific to this project. A diff cannot do that.
- **A clean baseline.** Modified files are diffed against the pristine template at the recorded `source_sha`, so the diff shows only local edits.

If a run only ever surfaces modified tracked files, the skill adds little over `check` plus `install`. Its value depends on the local-additions categories.

## What Changes

- Add a `scaffold-retro` Claude Code skill (`.claude/skills/scaffold-retro/SKILL.md`), authored in `templates/` and distributed to projects as a new tracked **file component** (`scaffold-retro`), so it gets the same MISSING / STALE / MODIFIED drift tracking as other components.
- When invoked in a project, the skill inspects scaffold-owned and scaffold-adjacent state and identifies upstream candidates in these categories:
  - **Modified scaffold files** — tracked files whose disk hash differs from `.scaffold/manifest.json`, diffed against the pristine template at the recorded `source_sha`.
  - **Local gates** — entries in `.scaffold/gates.json` the scaffold did not register.
  - **Local hooks and scripts** — Claude Code hooks in `.claude/settings.json` and scripts beside the scaffold's `scripts/` that the scaffold does not own.
  - **Wishlist overrides** — `.scaffold/plugins.json` / `.scaffold/skills.yaml` entries extending the base manifest.
  - **Config rules** — `openspec/config.yaml` `rules:` / schema-clone instructions that go beyond the template.
  - **Recurring patterns** — repeated workarounds or conventions visible in the project (e.g. `CLAUDE.md` rules, archived OpenSpec changes that patch the same scaffold area).
- Each candidate in the report lists:
  - its category
  - evidence: paths plus a short diff or excerpt
  - a plain-language summary of what changed
  - benefits of promoting it upstream
  - risks or costs of promoting it
  - a recommendation of `promote`, `adapt`, or `keep-local`
  - a suggested upstream target: a template file, `manifest.yaml`, or a new component
  - a suggested kebab-case change name for `common-project-setup`, except when the recommendation is `keep-local`
- The skill excludes project-specific content (the config `context:` block, domain code) and must not copy secrets into the report.
- The skill is **read-only** except for one report file at `.scaffold/retro/retro-<YYYY-MM-DD>.md`. It does not edit scaffold files, does not write to `common-project-setup`, and takes no outward action (no issues, PRs, or pushes).
- If the scaffold source is unreachable, the skill still reports local-only findings and states that it could not diff against the pristine baseline.
- If the project is not scaffold-provisioned (no `.scaffold/manifest.json`), the skill stops. It explains that it has no baseline for telling scaffold-owned state from local additions, points to `scaffold install`, and writes no report. Normally the skill only reaches provisioned projects, so this case means it was copied in by hand or the manifest was deleted.

## Capabilities

### New Capabilities
- `scaffold-retro`: A distributed skill that inspects a scaffold-provisioned project and reports candidate improvements to promote back into `common-project-setup`, with evidence and suggested change names, without modifying the project or the scaffold.

### Modified Capabilities
<!-- None. The new file component follows the existing file-component-sourcing and scaffold-installer requirements unchanged. -->

## Impact

- `templates/.claude/skills/scaffold-retro/SKILL.md`: new skill template.
- `scaffold.py`: one new `FileComponent` (`scaffold-retro`) in `build_registry()`. No new component class or drift state.
- `tests/`: new tests covering registration/install of the component and the skill's content contract.
- `README.md`: list the new component and document the retro workflow (run in child, review report, propose upstream via `/opsx:propose` in `common-project-setup`).
- Projects consuming the scaffold gain `.claude/skills/scaffold-retro/` (tracked) and, after a run, `.scaffold/retro/` reports.
