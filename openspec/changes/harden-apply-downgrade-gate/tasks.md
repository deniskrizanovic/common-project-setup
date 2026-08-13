## 1. Strengthen the apply downgrade instruction

- [ ] 1.1 In `templates/openspec/schemas/spec-driven/schema.yaml`, rewrite the `MODEL DOWNGRADE PROMPT` block in `apply.instruction` so it is a hard stop: agent MUST ask, then MUST NOT read context files / work tasks / make edits in the same turn, and MUST end the turn waiting for the user's answer.
- [ ] 1.2 Keep the existing semantics in the same block: once per apply session, agent cannot switch models itself, direct user to `/model` (or `/fast`), no re-prompt after asked or declined.
- [ ] 1.3 Leave the following "Read context files, work through pending tasks, mark complete... Pause on blockers" lines intact and unchanged.

## 2. Verify

- [ ] 2.1 Run the scaffold-installer test suite (`pytest tests/test_scaffold_installer.py`) and confirm it still passes; if a test asserts the downgrade wording, update it to match the new text.
- [ ] 2.2 Scaffold a throwaway project (or inspect the rendered schema) and confirm the new `apply.instruction` block reads as a halt-and-wait gate.
