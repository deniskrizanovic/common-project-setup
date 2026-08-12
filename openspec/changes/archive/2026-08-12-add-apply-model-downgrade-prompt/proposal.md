## Why

Applying an OpenSpec change is largely mechanical work (working a task list, flipping checkboxes) yet is often run on a top-tier model, wasting cost. The apply workflow never prompts the user to consider a cheaper model, so the downgrade decision is easy to forget.

## What Changes

- Extend the `apply` artifact's `instruction` in the project-local `spec-driven` schema clone (`templates/openspec/schemas/spec-driven/schema.yaml`) to prompt the user, once per apply session and before any task work, about downgrading the implementation model (e.g. Opus → Sonnet).
- The prompt is advisory only: the agent cannot switch models itself, so it directs the user to run `/model` (or `/fast`) and waits for their choice; if declined or already asked, it continues without re-prompting.
- Update the schema file's local-customisation header comment (lines 4-7) to record this as an additional local divergence from base OpenSpec, keeping the re-diff-on-upgrade note accurate.

## Capabilities

### New Capabilities
- `apply-workflow-guidance`: Defines project-local behavior baked into the `spec-driven` schema clone's `apply` instruction — starting with the once-per-session model-downgrade prompt.

### Modified Capabilities
<!-- none -->

## Impact

- `templates/openspec/schemas/spec-driven/schema.yaml` — `apply.instruction` text and header comment.
- Affects every consumer that scaffolds from this template clone (the apply instruction is surfaced by `openspec instructions apply --json` and treated as controlling by the `openspec-apply-change` skill).
- No code, API, or dependency changes; prompt-level behavior only.
