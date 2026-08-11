## Context

`scaffold.py` walks a registry of components during `install`. Each component is
one of three types — `FileComponent` (copied from `templates/`, tracked by
sha256), `PluginComponent`, or `SkillComponent` — and the install loop is a hard
`if isinstance(FileComponent) / elif Plugin / else Skill` chain (`cmd_install`).

`config-baseline` is already the odd one out: it is a `FileComponent` but
carries a custom `satisfied=_config_is_real` callable instead of relying purely
on hash equality, because a filled config's content is project-specific and can
never match a fixed template hash. This change extends that same "config is
special" pattern to add a guided fill step, `config-interview`.

Constraints: no third-party TUI dependency; prompts must be testable via the
injectable `reader` (see `_prompt` / `cmd_install`, exercised with
`iter([...])` in `tests/test_scaffold_installer.py`); `check` and `list` must
stay prompt-free and write nothing.

## Goals / Non-Goals

**Goals:**
- Turn the manual, easily-skipped edit of `openspec/config.yaml` into a guided
  step in the interactive `install` flow.
- Rewrite only the `context:` block; leave `rules:`, `schema:`, and comments
  untouched.
- Keep the step deterministic and unit-testable (no autodetection, injectable
  reader).

**Non-Goals:**
- No AI-assisted drafting or project autodetection (blank prompts only).
- No change to `config-baseline`'s behavior — it still copies the template
  verbatim.
- No editing of the `rules:` block; those are enforcement infra, not
  project-specific.

## Decisions

### Component type: FileComponent variant with a `filler` callable
`config-interview` reuses `FileComponent` rather than introducing a fourth
component class. It carries an optional `filler` callable (mirroring the
existing `satisfied=` escape hatch) that runs the interview. The install loop's
`FileComponent` branch checks for a `filler` and, when present, runs the
interview instead of copying a template.

*Alternative considered:* a new `InteractiveComponent` class with its own
branch in `cmd_install`. Rejected — more surface area for one component, and
the `satisfied=`/`filler=` callable approach already fits the existing pattern.

### Drift model: MISSING or OK only, via a placeholder sentinel
`config-interview` has no tracked source hash, so STALE and MODIFIED do not
apply. A `_context_is_customized(root)` predicate returns True when the
`context:` block no longer contains a known placeholder sentinel string from
the template (e.g. the `describe what this project does in 1-3 sentences`
line). OK when customized; MISSING while the sentinel survives.

*Alternative considered:* hashing the filled block. Rejected — the content is
intended to vary per project, so a hash gate would perpetually report drift.

### In-place block splice, not YAML round-trip
The rewrite locates the `context: |` block by its key and indentation
boundaries and replaces only that span, preserving `rules:`, `schema:`, and
comments byte-for-byte outside the block. A full YAML load/dump would strip the
comments the template depends on.

*Alternative considered:* parse-and-reserialize with a comment-preserving YAML
library. Rejected — adds a dependency and risks reformatting the untouched
parts of the file.

### Re-run always prompts
Per product decision, the step always offers `[i]nterview / [s]kip` during
`install`, even when already customized, rather than auto-skipping an OK
component. This is intentionally noisier than the standard `OK → skip` path so
the context can be revised.

## Risks / Trade-offs

- **Sentinel drift** → if the template's placeholder text changes, the
  `_context_is_customized` sentinel must be updated in lockstep. Mitigation:
  derive the sentinel from a single constant shared with the template check.
- **Fragile block splice** → an oddly-formatted or hand-edited `context:` block
  could confuse the boundary detection. Mitigation: match on the `context:` key
  plus block indentation; if the block cannot be located unambiguously, abort
  the rewrite with a clear message rather than corrupting the file.
- **Always-prompt noise** → re-offering an OK component departs from the
  installer's `OK → skip` convention and could surprise. Mitigation: label the
  status clearly (e.g. "customized") so the user knows re-interview is optional.

## Migration Plan

Additive. Existing projects gain a new `config-interview` component that reports
MISSING until run; no existing component changes behavior. No manifest-derived
artifacts (`plugins.json`, `skills-lock.json`) are affected.

## Open Questions

- Exact wording and count of interview prompts beyond the five required fields
  (Conventions block: keep template defaults or optionally extend?).
- Where the placeholder sentinel constant lives so both `_config_is_real`
  (config-baseline) and `_context_is_customized` (config-interview) share it.
