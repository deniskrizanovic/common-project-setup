## Context

The apply phase of the `spec-driven` workflow is largely mechanical — reading context, working a task list, flipping checkboxes — yet is often run on a top-tier model. The project ships a local clone of the `spec-driven` schema (`templates/openspec/schemas/spec-driven/schema.yaml`) whose `apply.instruction` is surfaced by `openspec instructions apply --json` and treated as controlling by the `openspec-apply-change` skill. The clone already carries two local divergences from base OpenSpec 1.4.1 (test-traceability line and GIVEN clause), tracked in the file's header comment.

## Goals / Non-Goals

**Goals**
- Prompt the user, once per apply session, to consider a cheaper implementation model before task work begins.
- Keep the prompt advisory and preserve all existing apply directives.

**Non-Goals**
- Automatic model switching. Out of scope — the agent cannot change its own model.
- Persisting the "already asked" state across separate sessions.

## Decisions

**Placement: template `instruction`, not `config.yaml` `operations.apply.guidance`.**
- Template instruction is *controlling* (the skill obeys it) and applies to every consumer of the clone; config guidance is *advisory* (skill may skip) and project-local.
- Rationale: we want the prompt to reliably fire, not be optionally skipped. Cost: adds local divergence #3 to a file the header warns must be re-diffed on OpenSpec upgrade — so the header comment is updated in the same change.

**Mechanism: prompt-only, user pulls the trigger.**
- The instruction tells the user to run `/model` (or `/fast`) and waits; it does not imply the agent switches models.
- Rationale: matches the actual capability boundary in Claude Code.

**Frequency: once per apply session.**
- Tracked in-conversation by the agent, not persisted.
- Honest limitation: "session" means the current conversation. A fresh session re-prompts. Acceptable — a stray extra prompt is cheap; persistence machinery is not worth it.

## Risks / Trade-offs

- [Prompt fatigue] → Bounded to once per session, before task work only.
- [Schema drift on OpenSpec upgrade] → Header comment updated to list this divergence so the re-diff note stays accurate.
- [Session-scope resets on new conversation] → Accepted; re-prompt cost is negligible.

## Open Questions

None.
