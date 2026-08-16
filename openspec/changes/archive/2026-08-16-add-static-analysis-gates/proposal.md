## Why

The scaffold enforces spec traceability and passing tests before commit, but
performs no static analysis: lint, format, and type errors reach commits
freely. Every provisioned project re-solves "which analyzer, wired how" by
hand. A baseline set of per-language static-analysis gates — wired through the
existing `commit_gate.py` model — closes that gap without changing the
scaffold's install ethos.

## What Changes

- Add per-language static-analysis gate definitions the scaffold registers into
  `.scaffold/gates.json`, so `commit_gate.py` runs them (with the existing
  test/lint gates) and blocks `git commit` on failure.
- Language selection reads the existing `Language / runtime:` answer in
  `openspec/config.yaml`'s `context:` block (already collected by the config
  interview). No new interview question. (`lint_specs.py` keys off `Testing:`
  for test-glob discovery — a separate concern, left unchanged.)
- Gate sets per detected language:
  - **Python** → `lint:ruff` (`ruff check`, lint + format check).
  - **TypeScript** → `lint:biome` (`biome check`) and `typecheck:tsc`
    (`tsc --noEmit`).
  - **Salesforce** → `analyze:sf` (`sf code-analyzer run`).
- Each gate is granular: its own `name` and `stopReason` for a precise block
  message.
- **Option B (wire, don't own):** the scaffold registers gate commands but
  never installs the toolchains. When a required tool is absent on PATH, the
  component classifies **BLOCKED** (same mechanism as the pnpm/ccusage,
  openspec-init, and github-init gates), prints the install remedy, and writes
  no gate that could only fail. It never auto-installs.
- **Tool defaults only:** no `ruff.toml` / `biome.json` / `code-analyzer.yml`
  is templated. Gates run each tool's zero-config default; project-specific
  config is out of scope for this change.

## Capabilities

### New Capabilities
- `static-analysis-gates`: per-language static-analysis gate definitions
  (Python / TypeScript / Salesforce), their language detection, their
  BLOCKED-on-missing-toolchain behavior, and how the scaffold registers them
  into `.scaffold/gates.json`.

### Modified Capabilities
- `enforcement-hooks`: `commit_gate.py` gains the registered static-analysis
  gates in its run sequence; the gate ordering and the missing-command
  behavior are affected.

## Impact

- `scaffold.py` — new gate registration during install; language detection
  reuse; BLOCKED classification for absent toolchains.
- `.scaffold/gates.json` — extended with the per-language static-analysis
  gates.
- `templates/scripts/commit_gate.py` — runs the added gates (no structural
  change to the run loop; it already iterates `load_gates`).
- No new templated config files. No auto-install of ruff / biome / tsc /
  `sf` CLI — install remedies are printed only.
- Toolchain prerequisites are per-language: Python (`ruff`), TypeScript
  (`biome`, `tsc`), Salesforce (`sf` CLI with Code Analyzer plugin).
