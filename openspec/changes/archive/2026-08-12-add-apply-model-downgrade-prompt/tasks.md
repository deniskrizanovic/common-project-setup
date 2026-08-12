## 1. Update the schema clone

- [x] 1.1 Prepend a model-downgrade prompt paragraph to `apply.instruction` in `templates/openspec/schemas/spec-driven/schema.yaml`: once per apply session, before any task work, ask the user whether to downgrade the model (Opus → Sonnet); state the agent cannot switch models and direct the user to run `/model` (or `/fast`), then wait; do not re-prompt if already asked or declined.
- [x] 1.2 Keep the existing `apply.instruction` directives (read context files, work pending tasks, mark complete, pause on blockers) intact below the new paragraph.
- [x] 1.3 Extend the local-customisation header comment (lines 4-7) to record the apply model-downgrade prompt as an additional divergence from base OpenSpec, so the re-diff-on-upgrade note stays accurate.

## 2. Verify

- [x] 2.1 Confirm `openspec instructions apply --change "<any-change>" --json` surfaces the new prompt text in the returned `instruction`.
- [x] 2.2 Run the repo's spec lint/validation gates and confirm no regressions from the schema edit.
