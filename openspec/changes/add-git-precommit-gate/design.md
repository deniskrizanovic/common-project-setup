## Context

The commit-gate (tests, `lint:specs`, `lint:given`, and per-language
static-analysis gates) is defined in `.scaffold/gates.json` and executed by
`scripts/commit_gate.py`, which is wired as a Claude Code `PreToolUse` hook on
the `Bash` matcher. It self-filters to `git commit` via `is_git_commit`. Because
Claude Code hooks fire only for tool calls the agent makes, any commit issued
from a terminal or an IDE (IntelliJ, VS Code) never triggers the gate. Observed
in a real project (NotionLinkReReader): a terminal/IDE commit ran neither tests
nor ruff, defeating the point of the static-analysis feature.

`commit_gate.py` already has a clean split: `load_gates(project_dir)` reads
`.scaffold/gates.json` (with a built-in fallback), and `run_gates(project_dir,
gates)` executes them in order, returning `None` on success or a
`{continue: false, stopReason}` block on the first failure. This gate-running
logic is reusable by a native hook.

## Goals / Non-Goals

**Goals:**
- Enforce the gate set on every commit path, not just Claude Code Bash commits.
- Reuse `.scaffold/gates.json` and the existing gate-running logic — no second
  gate definition, no duplicated runner.
- Portable, versioned wiring that survives clone: `core.hooksPath` at a tracked
  hooks directory.
- Idempotent wiring that never clobbers a `core.hooksPath` the scaffold did not
  author.

**Non-Goals:**
- Removing or changing the Claude Code `PreToolUse` commit-gate — it stays for
  fast in-session feedback.
- Installing analyzer toolchains (unchanged: scaffold never auto-installs).
- Supporting the git `pre-commit` framework (`.pre-commit-config.yaml`) — this
  is a plain git hook, no new dependency.
- Server-side / CI enforcement — out of scope; this is a local pre-commit gate.

## Decisions

### Decision: `core.hooksPath` + tracked dir over `.git/hooks/`
Set the project-local `core.hooksPath` to a tracked directory (default
`.githooks/`) holding the `pre-commit` script.

- **Why:** `.git/hooks/` is untracked and local-only — it does not survive a
  clone and must be re-wired per checkout, so a fresh clone silently loses the
  gate. `core.hooksPath` at a committed directory versions the hook with the
  project and applies to every clone after a one-time `git config` (which the
  scaffold performs, and which can be re-applied by re-running the scaffold).
- **Alternative considered — write `.git/hooks/pre-commit` directly:** simpler,
  no git config, but local-only and lost on clone. Rejected for the same reason
  the current Claude-only gate is insufficient: it silently fails to apply.
- **Alternative considered — pre-commit framework:** adds an external dependency
  and a second config file; overkill for shelling one gate runner. Rejected.

### Decision: reuse the gate runner, do not reimplement
The native `pre-commit` hook shells a Python entry point that calls the same
`load_gates`/`run_gates` logic as `commit_gate.py`. Preferred implementation:
extract the gate-running core into a small shared module (or expose a
`run_all_gates(project_dir)` callable in `commit_gate.py`) that both the
`PreToolUse` hook and the native hook import. The native hook translates a
failure block into a non-zero exit and prints the `stopReason` to stderr; the
Claude Code hook keeps emitting its JSON `{continue: false, ...}`.

- **Why:** one gate definition (`.scaffold/gates.json`) and one runner means the
  two paths cannot drift. Tests, lint, and static-analysis behavior stay
  identical across both.
- **Alternative considered — native hook re-parses `gates.json` itself in
  shell:** duplicates the missing-command and ordering logic; drifts. Rejected.

### Decision: new component `git-precommit-gate`, wiring beside `wire_hooks`
Add a registry component mirroring the static-analysis component's shape:
`satisfied()` (hook present + `core.hooksPath` correctly set), a precondition
(inside a git work tree), and a writer that writes the tracked hook and runs
`git config core.hooksPath`. Wiring is invoked from the same idempotent path as
`wire_hooks`.

- **Why:** matches existing component conventions (BLOCKED classification,
  read-only `check`/`list`, idempotent install) so `install`/`update`/`check`
  behave consistently.

### Decision: conflict detection on foreign `core.hooksPath`
Before setting `core.hooksPath`, read the current value. If unset or already the
scaffold's tracked dir, proceed. If set to a directory the scaffold did not
author, report a conflict and do not overwrite.

- **Why:** clobbering a team's existing hooks configuration is destructive and
  hard to reverse. Surfacing the conflict lets the user reconcile.

## Risks / Trade-offs

- **[Existing checkouts must re-run wiring]** — `core.hooksPath` is set per local
  clone, so existing checkouts of a scaffolded project need one `scaffold update`
  (or manual `git config`) to activate the hook. → Mitigation: document in the
  component remedy; the hook file itself is tracked, so only the one config line
  is per-clone.
- **[Bypass with `--no-verify`]** — `git commit --no-verify` skips the hook. →
  Mitigation: accepted; this is a local developer gate, not a security control.
  Server-side/CI enforcement is a separate, out-of-scope layer.
- **[Foreign `core.hooksPath` blocks install]** — a project already using
  `core.hooksPath` for other hooks will hit the conflict path and not get the
  gate. → Mitigation: report clearly; a follow-up could support composing into an
  existing hooks dir.
- **[Windows / shell portability]** — the tracked hook must run on the developer's
  shell. → Mitigation: make the hook a thin `#!/bin/sh` (or `python3`) shim that
  invokes the shared Python runner, keeping shell logic minimal.

## Migration Plan

1. Add the `git-precommit-gate` component and tracked hook template to the
   scaffold; extract/expose the shared gate runner.
2. `scaffold install` / `update` writes `.githooks/pre-commit` and sets
   `core.hooksPath`.
3. For existing scaffolded projects: run `scaffold update git-precommit-gate` in
   each local clone to set `core.hooksPath`.
4. Rollback: `git config --unset core.hooksPath` and remove the tracked hooks
   dir; the Claude Code `PreToolUse` gate continues to function unchanged.

## Open Questions

- Directory name: `.githooks/` (proposed default) vs reusing `scripts/`. Leaning
  `.githooks/` to keep hook artifacts separate from gate scripts.
- Hook shim language: `#!/bin/sh` calling `python3` vs a direct `python3`
  shebang. Leaning `python3` shebang to match `commit_gate.py` and avoid shell
  quoting, matching the existing script style.
