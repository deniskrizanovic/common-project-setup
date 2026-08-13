## Why

The `spec-driven` schema clone already carries a once-per-session model-downgrade prompt in its `apply` instruction. In practice the agent treats it as a courtesy note rather than a stop: in an observed apply session it printed "Note: apply is mechanical — you can downgrade via `/model`. Proceeding now; interrupt if you want to switch." and started task work in the same turn. The user never got a chance to answer before edits began, which is exactly the "wait for their choice before proceeding" behavior the requirement calls for.

The instruction text is too soft to reliably produce a halt. A hard enforcement hook was considered but rejected: hooks fire on tool events, not skills, so a model-downgrade gate cannot be scoped to the apply skill without a marker-file proxy and once-per-session state — heavy machinery for what is a soft cost preference, not a safety gate. Tightening the prose so the halt is unmistakable is the proportionate fix.

## What Changes

- Rewrite the `apply.instruction` model-downgrade block in `templates/openspec/schemas/spec-driven/schema.yaml` so the prompt is an explicit hard stop: the agent MUST ask and then wait for the user's answer, and MUST NOT read context files, work tasks, or make any edits in the same turn as the prompt.
- Keep the existing semantics intact: once per apply session, deferral of the switch to the user via `/model` (or `/fast`), no re-prompt after asked or declined, and all pre-existing apply directives (read context, work tasks, mark complete, pause on blockers).

## Capabilities

### Modified Capabilities
- `apply-workflow-guidance`: the model-downgrade prompt requirement is strengthened from "ask before task work" to "ask AND halt in the same turn — no context reads or edits until the user answers."

## Impact

- `templates/openspec/schemas/spec-driven/schema.yaml` — `apply.instruction` text only.
- Newly scaffolded projects inherit the stronger wording. Existing scaffolded projects (e.g. NotionLinkReReader) keep the old text until re-scaffolded or manually updated — out of scope here.
- No code, hooks, or CLI behavior change.
