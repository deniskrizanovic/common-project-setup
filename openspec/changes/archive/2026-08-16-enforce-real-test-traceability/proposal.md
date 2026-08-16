## Why

The `spec-test-traceability` component promises that every spec scenario is traceable to the test(s) that exercise it, but in practice it enforces only that a `> **Tests:**` line is *present* — not that it names a real, passing test. Two holes make the guarantee hollow: the literal word `none` is a blanket exemption that green-lights the gate while delivering zero traceability, and cited names are never checked against the test suite, so a typo or an invented name passes just as readily. Observed in a real downstream project (NotionLinkReReader): 21 of 22 live scenarios cite `none`, 16 real pytest functions sit orphaned, and the single non-`none` citation passes only by luck. The gate rewards typing the ritual line, not wiring a test.

## What Changes

- Extend the `lint:specs` gate so a non-`none` `> **Tests:**` citation MUST resolve to a test that actually exists in the project's test suite; an unresolvable citation fails the gate.
- Make `none` a *tracked* exemption rather than a free pass: the gate reports a count of `none` scenarios and fails when their share exceeds a configurable threshold (default reported, not blocking, at first), so blanket `none` becomes visible instead of invisible.
- Add author-time guidance (schema `specs` rule + gherkin-authoring skill) that directs authors to cite the concrete test name once the test exists, and to replace `none` during apply.
- Add an apply-workflow step that, after implementing tests, backfills real test citations into the scenarios they cover.
- **BREAKING** for specs that currently cite non-existent test names: those will begin failing `lint:specs` until corrected.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `spec-test-traceability`: strengthen from line-presence enforcement to real-test-resolution; add tracked-`none` accounting and threshold.
- `apply-workflow-guidance`: add a step to backfill concrete test citations into scenarios after tests are written.

## Impact

- `templates/openspec/schemas/spec-driven/schema.yaml` — `specs` rule wording (author-time layer).
- Lint gate script `scripts/lint_specs.py` (template + provisioned copies) — test-resolution check and `none` accounting.
- `commit_gate.py` behavior unchanged in wiring; stricter results.
- `gherkin-authoring` skill guidance.
- Downstream provisioned projects inherit on next scaffold sync; existing projects surface previously-hidden gaps.
