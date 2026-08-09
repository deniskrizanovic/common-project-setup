## Context

`common-project-setup` is the meta-repo intended to seed new projects, but its own setup is stock boilerplate. The proven patterns are scattered across `~/projects`: `collaborativegherkin` has the only filled `config.yaml`, a provenance-stamped schema clone, and three enforcement hooks; `tokencost` exists as three drifting copies (the global `~/.claude/hooks/` copy has already diverged from the `dk-skills/tokencost-setup` source); and plugins like caveman and superpowers are re-installed by hand per project.

This design covers a single `scaffold.py` that installs chosen components into a project and, on demand, detects what has drifted or fallen behind. It qualifies for a design doc: cross-cutting, a new architectural pattern (component registry + manifest), new external dependencies (git, the `claude` CLI, ccusage), and a migration concern (retiring the global cost-tracker copy).

## Goals / Non-Goals

**Goals:**
- One script, four subcommands: `install` (interactive per-component picker), `check` (read-only drift report), `update`, `list`.
- A self-describing component registry both modes iterate — adding a component wires both install and check for free.
- Manifest-based drift detection that distinguishes MISSING / STALE / MODIFIED / MODIFIED+STALE / EXTRA — the mechanism none of the current projects have and which would have caught the tokencost drift.
- Non-destructive by default: never clobber local edits or remove content without explicit confirmation.

**Non-Goals:**
- Migrating existing projects onto the scaffold (separate effort).
- Auto-removing EXTRA plugins or overwriting MODIFIED files.
- A TUI/menu dependency — plain per-component prompts only.
- A CLI beyond the four subcommands.

## Decisions

### Two component classes behind one registry
File components (config, schema clone, hooks, cost-tracker, lint gates) and plugin components (caveman, superpowers) share one registry but reconcile differently. File components copy content and track file hashes; plugin components declare a desired set and reconcile against `installed_plugins.json`. Alternative considered: modelling plugins as file components — rejected, plugins are not files and are owned by Claude's own install machinery.

### Source of truth is a remote git ref (fetched), not vendored files
`check` and `install` fetch the configured ref (default `main`) at run time; the manifest pins the installed source SHA. STALE = the ref advanced past the installed SHA. Alternative considered: vendoring canonical files in this repo (option 1) — rejected in favor of always-latest fetch. Trade-off: adds a network dependency, handled by offline degradation below.

### Manifest with content hashes, not version stamps alone
`.scaffold/manifest.json` records `{component, version, source_sha, files:{path: sha256}}`. `check` re-hashes disk files and compares three ways:
- disk == manifest, ref > source_sha → STALE
- disk != manifest → MODIFIED (and MODIFIED+STALE if the ref also moved)
- no entry → MISSING

A version stamp alone (alternative considered) cannot tell a stale copy from a locally edited one; the hash manifest can, so it subsumes collaborativegherkin's `lint:schema-parity` idea into one general mechanism.

### cost-tracker is project-local
Hooks point at `$CLAUDE_PROJECT_DIR/tokencost/cost-tracker.py`; no global copy. This removes the only `global+project` component, so `check` inspects a single root. It also retires the drifted global copy — the migration item below.

### Plugins install via the `claude` CLI
`install`/`update` shell out to `claude plugin install <id>`, registering the marketplace first. Alternative considered: editing `installed_plugins.json` directly — rejected as fragile duplication of Claude's internal state. When the CLI is absent, the script prints the exact commands instead of failing.

### Plugin wishlist: in-repo base + per-project override
A base wishlist lives in the repo; a project's `.scaffold/plugins.json` extends or overrides it to form the effective desired set. No plugin is forced "always"; every entry is opt-in through the picker. EXTRA plugins (installed, not desired) are reported only, never removed.

## Risks / Trade-offs

- [Network dependency for STALE detection] → offline `check` degrades to disk-vs-manifest (MODIFIED only) and states plainly that STALE could not be evaluated; never reports "current" on an unreachable source.
- [Retiring the global cost-tracker breaks projects still sourcing it] → **BREAKING**; the migration plan re-points hooks to the project-local copy.
- [`claude` CLI absent] → plugin actions degrade to report-only with printed commands, without failing the rest of the run.
- [Manifest and disk diverge if files are edited outside the tool] → that is exactly the MODIFIED signal; the tool surfaces it rather than silently overwriting.
- [Hook wiring corrupting existing settings] → wiring is idempotent, dedupes by command string, and preserves unrelated hooks.

## Migration Plan

1. Ship `scaffold.py` with the component registry and the seven components as file/plugin entries.
2. For projects using the global `~/.claude/hooks/cost-tracker.py`: run `install` to lay down the project-local `tokencost/` and re-point SessionStart/SessionEnd hooks; then remove the global copy.
3. Populate the base plugin wishlist; projects add their own via `.scaffold/plugins.json`.
4. Existing projects adopt on demand by running `scaffold.py install`; no forced migration.

## Open Questions

- Which git ref/URL is the canonical source, and how is it configured per project (env var vs `.scaffold/` field)?
- Exact `check` output format (table vs per-component lines) — deferred to implementation.
- Whether `lint:*` gates are Node scripts (mirroring collaborativegherkin) or reimplemented language-agnostically for non-Node projects.
