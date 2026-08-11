## Why

`config-baseline` drops a generic, pre-filled `openspec/config.yaml` that every
scaffolded project must then hand-edit to describe its real purpose, stack, and
conventions. Nothing guides that edit, so the placeholder often survives — the
AI context block stays generic and the config's value is lost. A guided step
that interviews the user and writes a project-specific `context` block turns a
manual, easily-skipped edit into part of the install flow.

## What Changes

- Add a new `config-interview` component to the scaffold registry, installed
  during the interactive `install` flow **after** `config-baseline` has laid
  the template on disk.
- The step runs a plain-prompt interview (Purpose, Language/runtime,
  Frameworks/libraries, Data store, Testing) via the same injectable `reader`
  used by the picker, then rewrites **only** the `context:` block of
  `openspec/config.yaml` in place — preserving the `rules:` block and comments.
- `check`/`list` classify `config-interview` as MISSING or OK only (no STALE /
  MODIFIED): OK once the `context:` block no longer contains the template
  placeholder sentinel; MISSING while the placeholder survives.
- During `install`, the step **always** offers `[i]nterview / [s]kip` — even
  when already customized — so the context can be revised on a later run.
- Prompts are blank (no project autodetection), keeping the step deterministic
  and testable.

## Capabilities

### New Capabilities
- `config-interview`: guided, prompt-driven fill of the `openspec/config.yaml`
  `context:` block during scaffold install, with a MISSING/OK drift model and
  in-place block rewrite that preserves the rest of the file.

### Modified Capabilities
<!-- None. config-baseline still copies the template verbatim; the interview is
     an additive step layered on top and does not change baseline's requirements. -->

## Impact

- `scaffold.py`: new registry entry and install-loop handling for an
  interview-style component (a `FileComponent` variant carrying a `filler`
  callable, mirroring the existing `satisfied=` escape hatch), plus a
  `_context_is_customized` predicate and an in-place `context:` block rewriter.
- `tests/`: new coverage feeding scripted answers through the injected `reader`.
- No new third-party dependencies; no change to `manifest.yaml`-derived
  artifacts (`plugins.json`, `skills-lock.json`).
