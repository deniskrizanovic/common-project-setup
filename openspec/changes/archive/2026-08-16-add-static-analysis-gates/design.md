## Context

The scaffold gates `git commit` through `templates/scripts/commit_gate.py`,
which iterates a list of gates from `.scaffold/gates.json` (falling back to
defaults: `pytest`, `lint:specs`, `lint:given`). Each gate is
`{name, cmd, stopReason}`; the first non-zero exit blocks the commit and
surfaces its output. No static analysis runs today.

The scaffold's established install ethos: never auto-install external
toolchains. Components that need an absent prerequisite classify **BLOCKED**
(pnpm/ccusage for `cost-tracker`, an uninitialized OpenSpec root for
`config-baseline`/`schema-clone`, a missing work tree / `origin` for
`github-init`) — the scaffold prints the remedy and writes nothing that could
only fail. Static analysis follows the same rule (Option B in the proposal).

Language is read from the `Language / runtime:` answer in the `context:` block
of `openspec/config.yaml`. This change reuses that existing answer — no new
interview question. (Note: `lint_specs.py` keys off `Testing:` for its own job —
mapping a test framework to test-file globs — which is a different concern;
static analysis selects on language directly.)

## Goals / Non-Goals

**Goals:**
- Register per-language static-analysis gates into `.scaffold/gates.json` so
  `commit_gate.py` runs them with no structural change to its run loop.
- Granular gates: each analyzer is its own gate with its own `stopReason`.
- BLOCKED-not-broken: absent toolchain → BLOCKED + printed remedy, never an
  auto-install, never a registered gate that can only fail.
- Reuse existing language detection.

**Non-Goals:**
- Coverage-percentage enforcement (separate follow-up change).
- Templating tool config files (`ruff.toml`, `biome.json`,
  `code-analyzer.yml`) — tool defaults only for now.
- Type-checking Python (mypy/pyright) — noisy on unannotated code; excluded
  from baseline.
- Auto-installing ruff / biome / tsc / the `sf` CLI.

## Decisions

### D1: Gate sets per language
| Language | Gates |
| --- | --- |
| Python | `lint:ruff` → `ruff check` |
| TypeScript | `lint:biome` → `biome check`; `typecheck:tsc` → `tsc --noEmit` |
| Salesforce | `analyze:sf` → `sf code-analyzer run` |

Rationale:
- **ruff** collapses Python lint + format + import hygiene into one fast,
  zero-config binary. mypy excluded (Non-Goal).
- **Biome over ESLint**: with a dedicated `typecheck:tsc` gate, ESLint's
  type-aware-rules edge is neutralized; Biome is one zero-config binary vs
  ESLint's mandatory flat-config + plugin/Node dependency graph. "Tool
  defaults only" favors Biome, which has a usable default; ESLint does not.
- **Salesforce Code Analyzer v5** (`sf code-analyzer run`) already unifies
  PMD-Apex, ESLint-LWC, RetireJS, and Flow scanning behind one CLI — one gate,
  not four.

**Alternatives considered:** ESLint+Prettier for TS (rejected: config sprawl,
no zero-config default); mypy in Python baseline (rejected: false-failure
noise on untyped code); deprecated `sf scanner run` v4 (rejected: superseded by
Code Analyzer v5) — see Open Questions on version verification.

### D2: BLOCKED detection per gate
Before registering a language's gates, the scaffold probes each required tool
on PATH (`ruff`, `biome`, `tsc`, `sf`). If any is absent, the component is
BLOCKED: the scaffold prints the install remedy and does **not** write that
gate into `.scaffold/gates.json`. This mirrors the pnpm/ccusage and
openspec-init gate mechanisms. `check`/`list` report BLOCKED read-only.

**Alternative:** register the gate anyway and let `commit_gate.py` fail on
`FileNotFoundError`. Rejected — that turns a missing dev tool into a hard
commit block with a cryptic reason, contradicting the scaffold's
"never write a gate that can only fail" rule.

### D3: No structural change to `commit_gate.py`
`load_gates` already reads `.scaffold/gates.json`. The static gates are just
additional entries. The run loop, ordering-by-list, and first-failure
semantics are unchanged. Static gates are appended after the existing
`tests` / `lint:specs` / `lint:given` gates.

### D4: Reuse the existing `Language / runtime:` answer
Language is read from the `Language / runtime:` line in the `context:` block of
`openspec/config.yaml` — the direct answer the config interview already
collects. `Testing:` is deliberately NOT used: it names a test framework, which
maps to a language only by inference and is ambiguous for Salesforce/Apex.
`lint_specs.py` continues to use `Testing:` for its own test-glob discovery —
unchanged. A project with no recognized `Language / runtime:` value registers no
static-analysis gates (and is reported as such), rather than guessing.

**Alternative:** key off `Testing:` (as `lint_specs.py` does). Rejected — the
test-framework answer is the wrong axis for language selection and breaks for
Apex, where the test framework does not name a distinct language.

## Risks / Trade-offs

- **Salesforce CLI version drift** (`sf code-analyzer run` v5 vs deprecated
  `sf scanner run` v4) → Mitigation: verify the current command against
  Salesforce KB / `project knowledge/` before pinning; the SF KB cache is
  currently degraded, so run `/kb-sync` first (see Open Questions).
- **Tool-default strictness surprises** (a default ruff/biome ruleset flags
  code an existing project didn't expect) → Mitigation: gates are only added on
  a fresh scaffold run; config-file templating is a deliberate future change,
  so projects can drop a config file to tune defaults meanwhile.
- **Existing provisioned projects don't get gates until re-run** → Mitigation:
  same as the strengthened `lint_specs.py` — documented as a re-run
  requirement; the gate is inert until installed.
- **Monorepo / multi-language projects** → the single language signal picks one
  set. Multi-language support is out of scope; documented, not silently
  dropped.

## Open Questions

- ~~Confirm the Salesforce Code Analyzer v5 invocation (`sf code-analyzer run`)
  and its plugin prerequisite name against a fresh Salesforce source — KB cache
  degraded at authoring time.~~ **Resolved** (verified against
  developer.salesforce.com Code Analyzer guide): `sf code-analyzer run` is the
  correct v5 command; the prerequisite is the `code-analyzer` CLI plugin
  (`sf plugins install code-analyzer`), a JIT plugin that also auto-installs on
  first `code-analyzer` invocation. The gate command and remedy match.
- Exact PATH-probe for `tsc` (global vs `npx tsc` vs local `node_modules/.bin`)
  — resolve during implementation; probe order should prefer a project-local
  binary before a global one.
