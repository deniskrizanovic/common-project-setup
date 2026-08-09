# Tasks

## 1. Test harness

- [x] 1.1 Set up the test runner (pytest) and a fixture that builds a throwaway project dir + fake `~/.claude` root for install/check/plugin tests
- [x] 1.2 Add a stub git source ref and a stub `claude` CLI for hermetic tests

## 2. Core: registry, manifest, subcommands

- [x] 2.1 Define the component registry structure (id, class, version, source, tracked files) as one iterable list
- [x] 2.2 Implement `.scaffold/manifest.json` read/write (component, version, source_sha, per-file sha256)
- [x] 2.3 Implement drift classification: MISSING / STALE / MODIFIED / MODIFIED+STALE / OK
- [x] 2.4 Implement `list` subcommand (status only, no prompts)
- [x] 2.5 Implement `check` subcommand (read-only report, writes nothing)
- [x] 2.6 Implement `install` subcommand with per-component prompts and a `diff` option
- [x] 2.7 Implement `update [<component>]`, with `--force` required to overwrite MODIFIED
- [x] 2.8 Tests (scaffold-installer spec): each classification case; `check` writes nothing; `list` no prompts; MODIFIED update refused without `--force`; present component skipped

## 3. File-component sourcing

- [x] 3.1 Fetch the configured source ref (default `main`) at run time
- [x] 3.2 Record installed source SHA in the manifest
- [x] 3.3 Content-hash tracked files on install and re-hash on check
- [x] 3.4 Offline degradation: disk-vs-manifest only, report that STALE was not evaluated
- [x] 3.5 Tests (file-component-sourcing spec): source SHA recorded; disk-hash MODIFIED detection; offline check reports honestly and never claims current

## 4. Plugin management

- [x] 4.1 Define the in-repo base plugin wishlist
- [x] 4.2 Load and compose `.scaffold/plugins.json` per-project override with the base
- [x] 4.3 Reconcile desired set against `~/.claude/plugins/installed_plugins.json` (MISSING / STALE / EXTRA)
- [x] 4.4 Install/update via `claude plugin install`, registering the marketplace first
- [x] 4.5 CLI-absent fallback: print exact commands, do not fail the run
- [x] 4.6 Report EXTRA plugins without ever removing them
- [x] 4.7 Tests (plugin-management spec): base-only vs override composition; MISSING/STALE/EXTRA classification; CLI-absent prints commands; EXTRA never removed

## 5. File components

- [x] 5.1 `config-baseline`: filled `openspec/config.yaml` payload + empty-template detection
- [x] 5.2 `schema-clone`: `spec-driven` clone with provenance header and delta list
- [x] 5.3 `enforcement-hooks`: branch-guard, commit-gate, cost-tracker hooks with idempotent wiring
- [x] 5.4 `cost-tracker`: project-local `tokencost/` scaffold, provenance stamp
- [x] 5.5 `lint-gates`: `lint:specs` and `lint:given` traceability gates
- [x] 5.6 `spec-test-traceability`: schema instruction wording enforcing `> **Tests:**` + `- **GIVEN**`
- [x] 5.7 Tests (config-baseline, enforcement-hooks, cost-tracker, spec-test-traceability specs): empty-template flagged; branch-guard asks on main; commit-gate blocks on failing tests + allows on pass; idempotent re-wire adds no duplicates; cost-tracker installed project-local with provenance stamp; missing Tests:/GIVEN fails lint

## 6. Migration & docs

- [x] 6.1 Retire the global `~/.claude/hooks/cost-tracker.py`; re-point hooks to the project-local copy
- [x] 6.2 Document the four subcommands and the source-ref configuration
- [x] 6.3 Resolve open questions: canonical source ref/URL, `check` output format, lint runtime for non-Node projects
