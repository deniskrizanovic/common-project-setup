## Context

`scaffold.py install` walks a registry of components. Three of them read or write inside `openspec/`:
- `config-baseline` — copies `openspec/config.yaml`
- `config-interview` — rewrites `config.yaml`'s `context:` block
- `schema-clone` — writes `openspec/schemas/spec-driven/**`

`install_file_component` unconditionally `mkdir`s parent dirs, so on a repo that never ran `openspec init` these components fabricate a partial `openspec/` tree. Empirically the `openspec` CLI resolves a project as a root only when `openspec/changes/` (plus `config.yaml`) exists — the scaffold writes neither `changes/` nor `specs/`, so the fabricated tree reads `openspec list --json → .root: null`. The result is a directory the CLI ignores: a silent, half-broken state.

## Goals / Non-Goals

**Goals:**
- Refuse to install the OpenSpec-dependent components when OpenSpec is not initialized, with a precise remedy.
- Keep the scaffold useful on a non-OpenSpec repo: OpenSpec-independent components still install.
- Never fabricate an unrecognized `openspec/` tree.

**Non-Goals:**
- Auto-running `openspec init` (it requires a `--tools` choice and hard-fails without one; guessing the tool is out of scope).
- Managing OpenSpec's own instruction/tool files (`.claude/commands/opsx/**`, `.claude/skills/openspec-*`) that `init` writes.
- Changing behavior for already-initialized repos.

## Decisions

### Signal: `openspec list --json` `.root != null`
Probed three candidate signals on uninitialized, scaffold-fabricated, and real-init trees:

| tree state            | `openspec context` exit | `list --json .root` |
| --------------------- | ----------------------- | ------------------- |
| uninitialized (empty) | 1                       | null                |
| scaffold-fabricated   | 0 (fooled by bare config.yaml) | null         |
| real `openspec init`  | 0                       | `{path}`            |

`openspec context` returns exit 0 on a bare `config.yaml`, so it cannot tell a fabricated tree from a real root — using it would defeat the gate. `.root` is null on both the empty and fabricated trees and non-null only after real init, so **`list --json .root`** is the discriminator. A bare filesystem check for `openspec/` is rejected for the same reason: the fabricated tree passes it.

### Refuse, do not run
On a missing root the gate prints `Run \`openspec init . --tools claude\` first` and skips the component. Rationale: `openspec init` errors without a `--tools` selection, and picking one for the user is a policy decision the scaffold should not own. This preserves the scaffold's boundary — it copies files, it does not manage OpenSpec's lifecycle.

### Guard scope: only the OpenSpec-dependent components
The three components above are tagged as requiring an OpenSpec root; the rest (`enforcement-hooks`, `cost-tracker`, `lint-gates`, plugins, skills) are untouched and install normally. Chosen over a whole-install hard gate so `install` stays useful on a non-OpenSpec repo. The guard sits directly in front of the exact components whose `install_file_component` would otherwise fabricate the root, so it also closes the fabrication trap.

### New status: BLOCKED
A blocked component is distinct from MISSING: MISSING means "installable now", BLOCKED means "precondition unmet". A new `BLOCKED` status constant keeps `check`/`list` output honest instead of overloading MISSING with a reason string. `install` refuses BLOCKED and prints the remedy; `check`/`list` report it read-only.

### CLI absent → treat as not-initialized
If the `openspec` binary is missing from `PATH` (or `list --json` fails to parse), the root cannot be verified, so the gate blocks and prints the init/install hint rather than proceeding to fabricate.

### Probe once per invocation
`openspec_initialized(project_root)` shells out once; the boolean is threaded into status computation so each blocked component does not re-invoke the CLI.

## Risks / Trade-offs

- [`openspec` CLI resolution semantics could change across versions, moving the `.root` trigger] → Gate on the documented `list --json .root` contract, not on which directories happen to trigger it; a version bump only changes what counts as initialized, not the gate's correctness.
- [Shelling out adds a subprocess to every `install`/`check`/`list`] → One call per invocation, guarded by a timeout, failing closed (block) on error.
- [BLOCKED adds a status the existing drift docs/tests must cover] → Update README drift table and add tests for the blocked path.

## Migration Plan

No data migration. On an already-initialized repo, behavior is unchanged. On a non-OpenSpec repo, previously-fabricated `openspec/` trees are not touched by this change; the user re-runs `openspec init` and then `scaffold.py install`.

## Open Questions

None.
