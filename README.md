# common-project-setup

Interactive scaffold installer with drift detection. One script, `scaffold.py`,
seeds a project with proven components (filled OpenSpec config, a provenance-
stamped `spec-driven` schema clone, enforcement hooks, a project-local cost
tracker, traceability lint gates) and the base plugin set (caveman,
superpowers) — and, on demand, reports what has drifted or fallen behind.

## Subcommands

```
python3 scaffold.py --project <dir> <command>
```

| Command | What it does |
| --- | --- |
| `list`   | Prints every registered component and its status. No prompts, no writes. |
| `check`  | Read-only drift report (MISSING / STALE / MODIFIED / MODIFIED+STALE / OK / EXTRA / BLOCKED). Writes nothing. |
| `install`| Interactive per-component picker: `[i]nstall/update`, `[d]iff`, `[s]kip`. Wires hooks idempotently at the end. |
| `update [<component>] [--force]` | Applies pending updates. A MODIFIED component is refused unless `--force` is given. |
| `gen` | Regenerates `scaffold_base/plugins.json` and `skills-lock.json` from `manifest.yaml`. |
| `drift` | Fails (exit 1) when a committed artifact drifts from `manifest.yaml`. |

`--project` defaults to the current directory.

## Components

Two classes behind one registry (`build_registry()` in `scaffold.py`):

**File components** — copied from `templates/`, tracked by `sha256` in
`.scaffold/manifest.json`:

- `config-baseline` — filled `openspec/config.yaml` (real context + traceability
  rules). The empty commented template is treated as **not satisfied**.
- `config-interview` — guided fill of `config.yaml`'s `context:` block. During
  `install` it prompts (Purpose, Language/runtime, Frameworks/libraries, Data
  store, Testing) via the same injectable reader and rewrites **only** the
  `context:` block, preserving `rules:`, `schema:`, and comments. Drift is
  MISSING/OK only (no source hash): **OK** once the template placeholder is gone,
  **MISSING** while it survives. `install` **always** offers `[i]nterview /
  [s]kip` — even when OK — so context can be revised on a later run; `check`/
  `list` classify it MISSING/OK and write nothing.
- `schema-clone` — local `spec-driven` schema clone with the `> **Tests:**` /
  `- **GIVEN**` instructions and templates.

`config-baseline`, `config-interview`, and `schema-clone` write inside
`openspec/` and therefore **require an initialized OpenSpec root**. Before
touching them the scaffold runs `openspec list --json` and requires a non-null
`.root`; a missing `openspec` CLI, a non-zero exit, or unparseable output all
count as not-initialized. When the root is absent these three classify
**BLOCKED** (not MISSING): `install` refuses them, prints
`openspec init . --tools claude`, and writes nothing under `openspec/` — it does
**not** auto-run init (that needs a `--tools` choice the scaffold won't guess);
`check`/`list` report BLOCKED read-only. The other components
(`enforcement-hooks`, `cost-tracker`, `lint-gates`, plugins, skills) do not need
a root and install normally on a non-OpenSpec repo.
- `enforcement-hooks` — `branch_guard.py` (asks on edits to `main`/`master`) and
  `commit_gate.py` (blocks `git commit` on failing tests/lint).
- `cost-tracker` — project-local `tokencost/` tracker with a `.provenance` stamp.
  The tracker resolves per-session cost via the `ccusage` CLI, which the scaffold
  provisions automatically with `pnpm add -g ccusage` on install. **`pnpm` (and
  Node) are a prerequisite**: when `pnpm` is not on PATH the component classifies
  **BLOCKED** — same mechanism as the OpenSpec-root gate above — and `install`
  refuses it with a remedy pointing at https://pnpm.io/installation rather than
  installing a tracker that can only log `total_cost_usd = "ERROR"`. A failed
  `pnpm add -g ccusage` (offline, registry down) is a warning, not fatal.
- `lint-gates` — `lint_specs.py` and `lint_given.py`, pure-Python (no Node).
- `github-init` — **print-only** nag to create a GitHub `origin` remote. Tracks no
  files, records no hash, takes no outward action. Detection keys on the git
  `origin` remote: not a git repository → **BLOCKED** (`git init` remedy; needs a
  work tree — same gate mechanism as the OpenSpec-root and `pnpm` gates); no
  `origin` → **MISSING**; `origin` present (any host) → **OK**, reported and never
  managed. Only BLOCKED/MISSING/OK — never STALE/MODIFIED. On MISSING `install`
  **prints** (never runs) `gh repo create <basename> --public --source=. --remote=origin
  --push` (basename = project dir) plus a no-gh fallback (`git remote add origin …`
  + `git push -u origin main`) — consistent with the openspec-init / plugin / skill
  refusals to auto-run outward actions.

**Plugin components** — reconciled against
`~/.claude/plugins/installed_plugins.json`, installed via `claude plugin install`:

- `caveman`, `superpowers` (from the `plugins:` section of `manifest.yaml`).

A project extends/overrides the wishlist via `.scaffold/plugins.json` (same-id
entries replace the base; new ids extend). EXTRA plugins (installed but not
wishlisted) are **reported only, never removed**. If the `claude` CLI is absent,
the exact commands are printed instead of failing the run.

**Skill components** — github-sourced skills reconciled against the project's
`skills-lock.json`, installed via `npx skills add`:

- `grill-me`, `grill-with-docs`, `improve-codebase-architecture`,
  `diff-org-changes`, `dk-cosmic-counting-coach`, `gherkin-authoring`
  (from the `skills:` section of `manifest.yaml`).

A project extends/overrides via `.scaffold/skills.yaml` (a `skills:`-only
manifest fragment; same-name entries replace the base, new names extend). EXTRA
skills are **reported only, never removed**. If the `npx skills` CLI is absent,
the exact commands are printed instead of failing the run.

## Source of truth: `scaffold_base/manifest.yaml`

`manifest.yaml` is the single **hand-edited** file declaring desired components,
with two typed sections (`plugins:` and `skills:`). `plugins.json` and
`skills-lock.json` are **generated** from it (`scaffold.py gen`) and committed so
their diffs are reviewable — never hand-edit those two. `scaffold.py drift`
fails when a committed artifact falls out of sync with the manifest.

`skillPath`/`computedHash` in `skills-lock.json` depend on the real upstream
repo content, so `gen` resolves them by shelling out to `npx skills`; when the
CLI is absent it keeps the existing committed lock. The drift guard therefore
compares only the manifest-derivable projection (skill name → source repo).

## Source ref configuration

File components are sourced from a git ref, resolved in this order:

1. Env: `SCAFFOLD_SOURCE_URL`, `SCAFFOLD_SOURCE_REF`.
2. `.scaffold/source.json` — `{ "url": "...", "ref": "..." }`.
3. Defaults: this repo, ref `main`.

The installed source SHA is pinned in the manifest. STALE = the ref advanced
past the pinned SHA. **Offline degradation:** when the ref is unreachable,
`check` falls back to disk-vs-manifest (MODIFIED only), states that STALE could
not be evaluated, and never reports a component as current on that basis.

## Drift classification

`.scaffold/manifest.json` records `{component, version, source_sha, files:{path:
sha256}}`. `check` re-hashes disk files and compares three ways:

- OpenSpec-dependent component (`config-baseline`, `config-interview`,
  `schema-clone`) with no initialized root → **BLOCKED** (takes precedence over
  MISSING)
- no manifest entry / files absent / `config-baseline` unsatisfied → **MISSING**
- disk == manifest, ref advanced past `source_sha` → **STALE**
- disk != manifest → **MODIFIED** (+ **MODIFIED+STALE** if the ref also moved)
- otherwise → **OK**

## Migration: retiring the global cost-tracker

The global `~/.claude/hooks/cost-tracker.py` copy is retired in favor of the
project-local `tokencost/` component. Per project:

1. Run `scaffold.py install` and accept `cost-tracker` — lays down
   `tokencost/` and points SessionStart/SessionEnd hooks at
   `$CLAUDE_PROJECT_DIR/tokencost/cost-tracker.py`.
2. Remove the global copy once every project sourcing it has migrated.

**BREAKING** for projects still sourcing the global hook until they migrate.

## Resolved design decisions

- **Canonical source**: this repo; ref/URL overridable via env or
  `.scaffold/source.json` (default ref `main`).
- **`check` output**: per-component lines (no table dependency).
- **Lint runtime**: reimplemented in pure Python so non-Node projects need no
  toolchain. Gate commands are configurable via `.scaffold/gates.json`.

## Tests

```
uv run pytest -q
```
