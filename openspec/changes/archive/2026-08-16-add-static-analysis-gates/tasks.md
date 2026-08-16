## 1. Language detection and gate definitions

- [x] 1.1 Add a helper that reads the `Language / runtime:` answer from the `context:` block of `openspec/config.yaml` and resolves it to one of `python` / `typescript` / `salesforce` / none. Use the same block-scan technique as `lint_specs.py`'s config reader, but key off `Language / runtime:` — do NOT reuse its `Testing:` extractor (test framework is a separate, ambiguous axis).
- [x] 1.2 Define the per-language static-analysis gate table: `python` → `lint:ruff` (`ruff check`); `typescript` → `lint:biome` (`biome check`) + `typecheck:tsc` (`tsc --noEmit`); `salesforce` → `analyze:sf` (`sf code-analyzer run`). Each entry carries a gate-specific `stopReason`.
- [x] 1.3 Define the PATH-probe for each gate's required tool (`ruff`, `biome`, `tsc`, `sf`); for `tsc` prefer a project-local `node_modules/.bin` binary before a global one.

## 2. Scaffold component: static-analysis gates

- [x] 2.1 Register the `static-analysis` component in `build_registry()`.
- [x] 2.2 On install for a supported language with all required tools present, append the language's gates to `.scaffold/gates.json` after the existing `tests` / `lint:specs` / `lint:given` gates, idempotently (no duplicate gate names on re-run).
- [x] 2.3 When a required tool is absent from PATH, classify the component BLOCKED, print the tool's install remedy, and write no gate. Never run an install command.
- [x] 2.4 When the language signal matches no supported language, register no gates and report that none were registered.
- [x] 2.5 Ensure `check` / `list` report BLOCKED read-only and write nothing.
- [x] 2.6 Confirm no analyzer config file (`ruff.toml`, `biome.json`, `code-analyzer.yml`) is templated — gate commands are the analyzers' default invocations only.

## 3. Commit-gate integration

- [x] 3.1 Verify `commit_gate.py` runs the appended static-analysis gates in list order and blocks on the first non-zero exit with that gate's `stopReason` (no structural change to the run loop expected).
- [x] 3.2 Confirm a registered gate whose command is not found on PATH blocks the commit with a gate-specific reason (existing `FileNotFoundError` path).

## 4. Tests

- [x] 4.1 Test language detection: each supported `Language / runtime:` answer resolves to the right language; an unrecognized answer resolves to none.
- [x] 4.2 Test gate registration per language (ruff / biome+tsc / sf) writes the expected gates with distinct `stopReason`s — covers the `static-analysis-gates` registration scenarios.
- [x] 4.3 Test BLOCKED-on-missing-tool: absent tool → BLOCKED, remedy printed, no gate written, no install command run — covers the missing-toolchain scenarios.
- [x] 4.4 Test idempotent re-run adds no duplicate gates.
- [x] 4.5 Add a commit-gate test that a failing static-analysis gate blocks the commit with its `stopReason` — replaces the `> **Tests:** none` citation in the enforcement-hooks delta.
- [x] 4.6 Update the `> **Tests:** none` citations in `specs/static-analysis-gates/spec.md` and `specs/enforcement-hooks/spec.md` to the real test identifiers once written.

## 5. Documentation

- [x] 5.1 Document the `static-analysis` component in `README.md` (Components section): per-language gates, BLOCKED-on-missing-toolchain, tool-defaults-only, and the re-run requirement for existing projects.
- [x] 5.2 Before pinning the Salesforce gate, verify the `sf code-analyzer run` v5 invocation and its plugin prerequisite against a fresh Salesforce source (`/kb-sync` first — KB cache degraded at authoring time).
