## 1. Gate: test resolution

- [x] 1.1 Add test-source discovery to `templates/openspec/schemas/spec-driven/scripts/lint_specs.py`: read the `Testing:` answer from `openspec/config.yaml`'s `context:` block, map it (substring, case-insensitive) to discovery patterns, and collect candidate test-function names + file paths accordingly
- [x] 1.2 Parse candidate identifiers from each non-`none` `> **Tests:**` line (comma/space-separated tokens)
- [x] 1.3 Resolve each identifier against discovered test-function names and file paths; accept either a function-name match or a file-path match
- [x] 1.4 Fail the gate on any unresolved identifier, reporting file, line, scenario, and the unresolved token
- [x] 1.5 Skip resolution for the literal `none`

## 2. Gate: none accounting

- [x] 2.1 Count scenarios citing the literal `none` and the total scenarios scanned
- [x] 2.2 Print the `none` count / total in the success output
- [x] 2.3 Read an optional `none`-share threshold from project config (`.scaffold/gates.json`); fail with a clear message when the share exceeds it
- [x] 2.4 When no threshold is configured, report the count without failing on `none` grounds

## 3. Test-technology mapping

- [x] 3.1 Define the `Testing:` answer → discovery-pattern map (pytest, jest/vitest/mocha, go test); document defaults and how to extend it
- [x] 3.2 Ensure an unrecognized `Testing:` answer degrades to the default pattern set and logs that the technology was unrecognized (never a silent pass)
- [x] 3.3 Read the optional `none`-share threshold from `.scaffold/gates.json` (threshold is enforcement config, kept separate from the `Testing:` interview answer)

## 4. Author-time and apply guidance

- [x] 4.1 Update the `spec-driven` schema `specs` rule wording to direct concrete citations and describe the resolution check
- [x] 4.2 Update the `gherkin-authoring` skill stub to cite real test identifiers and to replace `none` once a covering test exists
- [x] 4.3 Update the `apply` instruction (apply-workflow-guidance) to backfill concrete citations after tests are written, leaving `none` only where no test exists

## 5. Tests

- [x] 5.1 Unit tests for resolution: nonexistent identifier fails, real identifier passes, `none` is exempt
- [x] 5.2 Unit tests for `none` accounting: count reported, threshold exceeded fails, no threshold does not fail
- [x] 5.3 Backfill concrete test citations into this change's own spec scenarios where these new tests cover them

## 6. Self-verification and sync

- [x] 6.1 Run the strengthened `lint:specs` over `openspec/specs/**` and `openspec/changes/**`; confirm existing `none` scenarios still pass and no non-`none` citation is unresolved
- [x] 6.2 Document that existing provisioned projects must re-sync the scaffold to gain the check
- [x] 6.3 Run the full gate chain (`pytest`, `lint:specs`, `lint:given`) green before archiving — pytest 132 passed; this change's spec delta is clean on `lint:specs` (0 unresolved) and `lint:given` (0 violations). NOTE: baseline `openspec/specs/**` carries 77 pre-existing missing-`> **Tests:**` and given-clause gaps (identical under the prior gate; this repo does not wire the gates on itself), out of scope for this change.
