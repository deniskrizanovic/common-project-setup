## 1. Schema instruction updates

- [x] 1.1 Add a branch-isolation preamble to `proposal.instruction` in `templates/openspec/schemas/spec-driven/schema.yaml`: before writing any artifact, ensure a non-trunk change-scoped branch (suggest `change/<change-name>`) is checked out; hard stop on `main`/`master` (create/switch or ask); confirm-intent when already on a non-trunk branch.
- [x] 1.2 Add a matching branch-isolation preamble to `apply.instruction`: before working the first task, refuse `main`/`master` (switch/create or ask) and ensure a change-scoped branch is checked out. Order it relative to the existing model-downgrade prompt without weakening it.
- [x] 1.3 Keep both additions additive — verify the existing proposal artifact-creation guidance and the existing apply directives (downgrade prompt, read context, work tasks, mark complete, pause on blockers) are preserved verbatim.

## 2. Verification

- [x] 2.1 Run the scaffold's schema-related tests / drift check to confirm the edited `schema.yaml` still parses and no committed artifacts drift.
- [x] 2.2 Manually read back `proposal.instruction` and `apply.instruction` to confirm the trunk hard-stop and confirm-intent wording matches the spec scenarios.
- [x] 2.3 Run `openspec validate branch-per-openspec-change` (or the repo's lint gates) and confirm the change passes.
