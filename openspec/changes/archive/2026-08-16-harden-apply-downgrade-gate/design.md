## Context

The `spec-driven` schema clone's `apply.instruction` (in `templates/openspec/schemas/spec-driven/schema.yaml`) carries a once-per-session model-downgrade prompt. The prompt fires but does not halt: an observed apply session printed the note and started task work in the same turn, so the user never answered before edits began. The template and scaffolded projects both contain the instruction verbatim — the gap is behavioral (soft wording), not a missing artifact.

## Goals / Non-Goals

**Goals**
- Make the downgrade prompt an unambiguous hard stop within the apply instruction prose.
- Preserve every existing apply semantic (once-per-session, defer switch to user, no re-prompt, read/work/mark/pause).

**Non-Goals**
- No enforcement hook. No CLI change. No change to existing scaffolded projects.
- No new model-selection automation — the agent still cannot switch models itself.

## Decisions

**Decision: Strengthen prose, do not add a PreToolUse hook.**
Rationale: Hooks fire on tool events, not skills. The harness passes tool name + input to a hook; it has no "current skill" signal, so a model-downgrade gate cannot be scoped to the apply skill directly. Scoping would require a marker-file proxy (apply writes a session marker) plus once-per-session ack state, and a PreToolUse gate that blocks all edits until the marker is cleared. That is heavy machinery — and blast radius across every edit in the session — for what is a soft cost preference, not a safety gate like branch-guard. Alternative considered: the marker-file hook (option 3). Rejected as disproportionate.

**Decision: Explicit "halt in the same turn" language.**
The failure mode was acknowledge-and-continue. The fix names that mode and forbids it: no context reads, no task work, no edits in the turn that shows the prompt; end the turn waiting for the answer. This turns a paraphrasable suggestion into a directive an agent is far less likely to compress into a drive-by note.

## Risks / Trade-offs

- [Prose remains advisory — an agent could still ignore it] → Accepted. The requirement is a cost preference; the stronger wording raises compliance without the cost of a hard gate. If non-compliance persists, revisit the hook.
- [Existing scaffolded projects keep the old text] → Out of scope; they update on re-scaffold or manual edit. Called out in the proposal.

## Migration Plan

Text-only edit to one template file. No rollback complexity — revert the block if needed.

## Open Questions

None.
