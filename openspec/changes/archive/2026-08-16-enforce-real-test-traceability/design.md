## Context

The `spec-test-traceability` component installs three enforcement layers — a schema `specs` rule (author-time), the `lint:specs` gate (`scripts/lint_specs.py`), and the `commit_gate.py` PreToolUse hook that runs the gate before `git commit`. The gate today does one thing: for each `#### Scenario:`, it checks that the first non-empty following line matches `^>\s*\*\*Tests:\*\*`. Any match passes — including `> **Tests:** none` and `> **Tests:** test_totally_made_up`. It never opens the test suite.

Downstream evidence (NotionLinkReReader): 22 live scenarios, 21 cite `none`, 16 real pytest functions orphaned. The one non-`none` citation (`test_query_follows_pagination`) resolves only by coincidence — the gate would have passed an invalid name identically. The promised scenario→test mapping is absent even where the tests exist.

This change strengthens the gate from *line-presence* to *real-test-resolution*, and makes `none` a tracked (optionally bounded) exemption instead of a silent free pass. It touches the template gate and its schema wording; provisioned projects inherit on scaffold sync.

## Goals / Non-Goals

**Goals:**
- A non-`none` `> **Tests:**` citation must resolve to a test that actually exists, or `lint:specs` fails.
- `none` usage is counted and reported; optionally bounded by a configurable threshold.
- Author-time and apply-time guidance push authors toward concrete citations and away from leaving `none`.
- Gate stays pure-filesystem and offline — reads test source, never executes the suite.

**Non-Goals:**
- Running the test suite or checking that cited tests *pass* (that is coverage-linked traceability — heavier, out of scope here).
- Verifying that a cited test *semantically* exercises the scenario (impossible to check statically; citation correctness stays an author responsibility).
- Changing `lint:given` or the `commit_gate.py` wiring.
- Retroactively fixing downstream projects' specs (they surface gaps on next run; fixing them is their own work).

## Decisions

### Decision: Resolve citations by scanning test source, not executing
Match cited identifiers against test-function names (`test_*`) and test file paths discovered under the project's test tree. Rationale: keeps the gate offline, fast, and dependency-free — consistent with the existing "language-agnostic reimplementation, no toolchain" design note in `lint_specs.py`. Alternative considered: shell out to `pytest --collect-only`. Rejected — introduces a pytest dependency, network/plugin surprises, and slow collection on every commit; breaks the offline guarantee.

### Decision: Discovery is driven by the existing `Testing` config answer
Do NOT invent a new config key for test technology. The `config-interview` component already prompts for **Testing** and writes the answer into `openspec/config.yaml` (for example `- Testing: pytest`); the interview aborts on a blank field, so the value is always present in a filled project. The resolver reads that answer and maps recognized technologies to discovery patterns:

| `Testing:` answer contains | Discovery patterns |
|---|---|
| `pytest` / `python` | `test_*`/`*_test` functions in `**/test_*.py`, `**/*_test.py` |
| `jest` / `vitest` / `mocha` | `**/*.test.{js,ts,jsx,tsx}`, `**/*.spec.{js,ts}` |
| `go test` / `go` | `func Test*` in `**/*_test.go` |
| unrecognized | fall back to the Python default AND log that test technology was not recognized, so it is not mistaken for enforcement |

Rationale: reuse the seam that already exists instead of a parallel `.scaffold` key the user would have to fill twice and keep in sync. The interview question was *designed* to capture exactly this. Alternatives considered: (a) a dedicated `.scaffold/gates.json` test-tech key — rejected, duplicates the interview answer and drifts from it; (b) filesystem auto-detection (sniff for `pytest.ini`, `package.json`, etc.) — rejected as a first step, ignores the explicit answer the user already gave, though it is a reasonable *fallback* refinement later.

Wrinkle: the `Testing:` value lives inside the `context: |` block scalar — it is prose to YAML, not a structured key. The resolver therefore keyword-matches the answer rather than reading a typed field. Accepted trade-off: the interview guarantees presence, matching is tolerant (substring, case-insensitive), and an unrecognized answer degrades to the logged Python fallback rather than a false pass. Promoting `Testing` to a structured field is out of scope here (would change `config-interview` and every provisioned config); revisit if keyword matching proves too loose.

### Decision: `none` is tracked-then-bounded, phased
Phase 1: count and report `none` scenarios (share of total); do not fail on `none` by default. Phase 2 (opt-in): a configured threshold fails the gate when the `none` share is exceeded. Rationale: flipping `none` to an immediate hard failure would break every existing provisioned project on the next commit — including this repo's own specs, which legitimately carry `none` for instruction-only scenarios. Visibility first, enforcement when a project opts in. Alternative: ban `none` outright. Rejected — some scenarios genuinely have no automatable test (e.g. "schema instruction directs authors"); an escape hatch must remain, just not an invisible one.

### Decision: Citation format stays free-text after the marker
Keep `> **Tests:** <ids>` — comma/space-separated identifiers or `none`. The resolver extracts candidate tokens and resolves each. Rationale: minimal churn to existing specs and the gherkin skill's stub; no new structured syntax to learn. Alternative: a strict machine format (JSON/list). Rejected — friction against author-time use, and the current marker already parses cleanly.

## Risks / Trade-offs

- **False negatives from name collision** (two tests share a base name across files) → resolver treats a name match as resolved; acceptable because the goal is "a real test exists," not disambiguation. Report file path when available to aid authors.
- **Non-Python projects / unrecognized `Testing:` answer** → resolver degrades to the Python-default patterns and logs that the test technology was not recognized, so unconfigured resolution is not mistaken for enforcement. New technologies are added by extending the answer→pattern map, not by asking the user for more config.
- **`Testing:` answer is prose, not a typed field** → keyword matching (substring, case-insensitive) rather than an exact key read. Tolerant by design; falls back on no match. If matching proves too loose, promoting `Testing` to a structured field is a separate follow-up against `config-interview`.
- **Breaking existing invalid citations** → intended. `none`-heavy specs stay green (Phase 1); only *wrong* non-`none` names start failing, which is the bug we want surfaced.
- **Threshold noise** → default no threshold; opt-in only, so no project breaks on `none` share without choosing to.
- **Template vs provisioned drift** → the template gate is the source of truth; provisioned copies update on scaffold sync. Document that existing projects must re-sync to gain the check.

## Migration Plan

1. Update template `scripts/lint_specs.py`: read the `Testing:` answer from `openspec/config.yaml`'s `context:` block, map it to discovery patterns, add per-citation resolution, `none` accounting, and optional threshold read from project config.
2. Update the `spec-driven` schema `specs` rule wording (author-time layer) to direct concrete citations and describe the resolution check.
3. Update `gherkin-authoring` skill stub guidance to cite real identifiers and to replace `none` when a test lands.
4. Update the `apply` instruction (apply-workflow-guidance) to backfill concrete citations after tests are written.
5. Self-test in this repo: run the strengthened gate over `openspec/specs/**` and `openspec/changes/**`; confirm existing `none` scenarios still pass (Phase 1) and no non-`none` citation is unresolved.
6. Rollback: revert the gate script and schema wording; provisioned projects re-sync to the prior version. No data migration.

## Open Questions

- Where does the `none`-threshold config live — reuse `.scaffold/gates.json`, or a dedicated key in `openspec/config.yaml`? Leaning `.scaffold/` to keep enforcement config together. (Note: test *technology* is NOT an open question — it reuses the `Testing:` interview answer.)
- Is keyword-matching the prose `Testing:` answer robust enough, or should `config-interview` promote `Testing` to a structured field? Deferred; start with matching.
- Should resolution also accept a file-path citation (e.g. `tests/test_notion.py`) as sufficient, or require a function name? Leaning accept both, since scenario-to-file granularity is often enough.
