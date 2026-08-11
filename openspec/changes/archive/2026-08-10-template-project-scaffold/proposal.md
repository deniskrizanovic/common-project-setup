# Proposal: Interactive scaffold installer with drift detection

## Why

`common-project-setup` is the meta-repo meant to seed new projects, but its own setup is stock boilerplate and the proven patterns are scattered: `collaborativegherkin` evolved a battle-tested scaffold (filled config, provenance-stamped schema clone, three enforcement hooks, layered lint gates), while `tokencost` exists as three drifting copies with no single home and a plugin set (caveman, superpowers) is re-installed by hand per project. This change delivers one interactive script that installs the chosen parts into a project and, on demand, checks what has drifted or fallen behind — so setup is opt-in per component and drift is detectable instead of silent.

## What Changes

- **`scaffold.py` — a single script with subcommands**:
  - `install` — interactive per-component picker: shows each component's status (missing/stale/present/modified), prompts install/update/skip with a `diff` option, never clobbers local edits blindly.
  - `check` — the "does anything need updating" mode: reports MISSING / STALE / MODIFIED / EXTRA per component and writes nothing.
  - `update [<component>]` — applies pending updates (STALE); a MODIFIED component requires `--force` to overwrite.
  - `list` — registry plus current status, no prompts.
- **Two component classes behind one registry**:
  - **File components** — sourced from a **remote git ref** (fetched at run time), installed by copying files, tracked by content hash.
  - **Plugin components** — sourced from a marketplace, installed by shelling out to the `claude plugin install` CLI, reconciled against `~/.claude/plugins/installed_plugins.json`.
- **Manifest-based drift detection** (`.scaffold/manifest.json`): install/update record each component's version, tracked file `sha256`, and the source git SHA installed from. `check` re-hashes on disk and classifies:
  - MISSING (not installed) · STALE (source ref moved past installed SHA) · MODIFIED (local edits since install) · MODIFIED+STALE (both). Offline: falls back to disk-vs-manifest only (catches MODIFIED, cannot judge STALE) and says so — never implies "all current" when it could not reach source.
- **File components shipped**: `config-baseline` (filled `openspec/config.yaml` context + rules, and the rule forbidding the empty template), `schema-clone` (local `spec-driven` clone with provenance header + delta list), `branch-guard` hook (`ask` on edits to main/master), `commit-gate` hook (tests + lint block the commit), `cost-tracker` (**project-local** `tokencost/` — no global copy), `lint-gates` (`lint:specs` / `lint:given` traceability gates).
- **Plugin management**: an in-repo base wishlist, extendable/overridable per project via `.scaffold/plugins.json`. `check` reconciles desired vs installed: MISSING → offer install, STALE (`gitCommitSha` differs) → offer update, EXTRA (installed but not desired) → **report only, never remove**.
- **Spec-to-test traceability** kept as a three-layer convention (schema instruction + lint gate + commit hook); the `schema-clone` drift check is **subsumed** into the manifest hash-check rather than a separate `lint:schema-parity` script.

## Capabilities

### New Capabilities
- `scaffold-installer` — the script itself: `install` / `check` / `update` / `list` subcommands, the component registry, `.scaffold/manifest.json`, and the MISSING/STALE/MODIFIED/EXTRA classification.
- `file-component-sourcing` — fetching file components from a remote git ref, content-hash tracking, and offline degrade behavior.
- `plugin-management` — the desired-plugin wishlist (base + per-project override), reconciliation against `installed_plugins.json`, and EXTRA-safe (non-destructive) behavior.
- `project-config-baseline` — the required non-boilerplate `openspec/config.yaml` shape (context + rules) and the rule forbidding the empty template.
- `enforcement-hooks` — the branch-guard, commit-gate, and cost-tracker hook set and their contract.
- `spec-test-traceability` — the three-layer `> **Tests:**` / `- **GIVEN**` scenario enforcement.
- `cost-tracker` — the project-local session cost-tracker: `tokencost/` scaffold and provenance stamp (resolving the current three-copy drift).

### Modified Capabilities
- None. This repo currently has no specs under `openspec/specs/`.

## Impact

- **Affected code/config**: new `scaffold.py`, in-repo component registry + plugin wishlist, `.scaffold/manifest.json` (written into target projects), plus the file-component payloads (`openspec/config.yaml`, `openspec/schemas/`, `.claude/settings.json`, `tokencost/`, lint scripts).
- **Dependencies**: `git` (fetch source ref), `claude` CLI (plugin install), `ccusage` (optional, cost in USD), Node-based lint scripts. All must degrade gracefully when absent — `check` must never report a false "current".
- **Consumers**: any project that runs `scaffold.py`; the current global `~/.claude/hooks/cost-tracker.py` copy is retired in favor of the project-local component. **BREAKING** for projects still sourcing that global copy.
- **Non-goals**: not migrating existing projects onto the scaffold in this change; not removing EXTRA plugins or MODIFIED files automatically; no TUI/menu dependency (plain per-component prompts).
