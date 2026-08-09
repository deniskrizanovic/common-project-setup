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
| `check`  | Read-only drift report (MISSING / STALE / MODIFIED / MODIFIED+STALE / OK / EXTRA). Writes nothing. |
| `install`| Interactive per-component picker: `[i]nstall/update`, `[d]iff`, `[s]kip`. Wires hooks idempotently at the end. |
| `update [<component>] [--force]` | Applies pending updates. A MODIFIED component is refused unless `--force` is given. |

`--project` defaults to the current directory.

## Components

Two classes behind one registry (`build_registry()` in `scaffold.py`):

**File components** — copied from `templates/`, tracked by `sha256` in
`.scaffold/manifest.json`:

- `config-baseline` — filled `openspec/config.yaml` (real context + traceability
  rules). The empty commented template is treated as **not satisfied**.
- `schema-clone` — local `spec-driven` schema clone with the `> **Tests:**` /
  `- **GIVEN**` instructions and templates.
- `enforcement-hooks` — `branch_guard.py` (asks on edits to `main`/`master`) and
  `commit_gate.py` (blocks `git commit` on failing tests/lint).
- `cost-tracker` — project-local `tokencost/` tracker with a `.provenance` stamp.
- `lint-gates` — `lint_specs.py` and `lint_given.py`, pure-Python (no Node).

**Plugin components** — reconciled against
`~/.claude/plugins/installed_plugins.json`, installed via `claude plugin install`:

- `caveman`, `superpowers` (base wishlist in `scaffold_base/plugins.json`).

A project extends/overrides the wishlist via `.scaffold/plugins.json` (same-id
entries replace the base; new ids extend). EXTRA plugins (installed but not
wishlisted) are **reported only, never removed**. If the `claude` CLI is absent,
the exact commands are printed instead of failing the run.

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
