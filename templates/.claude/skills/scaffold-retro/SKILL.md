---
name: scaffold-retro
description: Run a retro on a scaffold-provisioned project and report which local changes should go back into common-project-setup. Use when the user asks for a "retro", a "scaffold retro", "what should go back into common-project-setup", "upstream scaffold improvements", or wants to harvest local edits to scaffold-managed files, gates, hooks, wishlists, or config rules. Read-only apart from one report file.
---

# Scaffold retro

Inspect this project and report the changes worth promoting back into
`common-project-setup` (the scaffold). The output is one markdown report. The
human reviews it and decides what to propose upstream.

## Read-only boundary

This skill is **read-only** except for one file.

- The **only allowed write** is the report at
  `.scaffold/retro/retro-<YYYY-MM-DD>.md` (today's date). Create
  `.scaffold/retro/` if it does not exist. A second run on the same day
  overwrites the report.
- Do **not** edit scaffold-tracked files, project files, `.scaffold/manifest.json`,
  or any other file in the project.
- Do **not** write to the `common-project-setup` source or any checkout of it.
  A temp clone used as a baseline (see "Baseline resolution") lives outside the
  project and is only read.
- Take **no outward action**: do not file issues, open PRs, push, comment, or
  create OpenSpec changes. Suggested change names in the report are suggestions
  only.

If a step seems to need a write, skip it and record that in the report instead.

## Preflight: provisioned project only

Read `.scaffold/manifest.json`. If it does not exist, **stop**:

- Explain that the project is not scaffold-provisioned, so there is no baseline
  for telling scaffold-owned state from local additions.
- Point the user to `python3 scaffold.py --project <dir> install` from a
  `common-project-setup` checkout.
- Write **no report**.

## Scaffold-owned inventory

These items belong to the scaffold. Anything in the same areas that is not
listed here is a local addition. The list is kept in sync with `scaffold.py` by
a test (`tests/test_scaffold_retro.py::test_skill_inventory_matches_scaffold`),
so update both together.

- `tracked-file` — files copied from `templates/<path>` and hash-tracked in
  `.scaffold/manifest.json`.
- `writer-file` — files written by a component writer. They are not
  hash-tracked. The template path is given after ` <- `.
- `gate` — gate names the scaffold registers in `.scaffold/gates.json`: the
  base gates plus every per-language static-analysis gate.
- `hook` — Claude Code hooks the scaffold wires into `.claude/settings.json`,
  as `<event> :: <matcher> :: <command>` (empty matcher means none).

```scaffold-inventory
tracked-file: openspec/config.yaml
tracked-file: openspec/schemas/spec-driven/schema.yaml
tracked-file: openspec/schemas/spec-driven/templates/proposal.md
tracked-file: openspec/schemas/spec-driven/templates/spec.md
tracked-file: openspec/schemas/spec-driven/templates/design.md
tracked-file: openspec/schemas/spec-driven/templates/tasks.md
tracked-file: scripts/branch_guard.py
tracked-file: scripts/commit_gate.py
tracked-file: tokencost/cost-tracker.py
tracked-file: tokencost/sum-cost.py
tracked-file: tokencost/.provenance
tracked-file: scripts/lint_specs.py
tracked-file: scripts/lint_given.py
tracked-file: .claude/skills/scaffold-retro/SKILL.md
writer-file: .githooks/pre-commit <- githooks/pre-commit
gate: tests
gate: lint:specs
gate: lint:given
gate: lint:ruff
gate: lint:biome
gate: typecheck:tsc
gate: analyze:sf
hook: PreToolUse :: Edit|Write|NotebookEdit :: python3 "$CLAUDE_PROJECT_DIR/scripts/branch_guard.py" "$CLAUDE_PROJECT_DIR"
hook: PreToolUse :: Bash :: python3 "$CLAUDE_PROJECT_DIR/scripts/commit_gate.py" "$CLAUDE_PROJECT_DIR"
hook: SessionStart ::  :: python3 "$CLAUDE_PROJECT_DIR/tokencost/cost-tracker.py" backfill
hook: SessionEnd ::  :: python3 "$CLAUDE_PROJECT_DIR/tokencost/cost-tracker.py" finalize
```

The base plugin and skill wishlists live in `scaffold_base/manifest.yaml` in
the scaffold. Every entry in the project's override files
(`.scaffold/plugins.json`, `.scaffold/skills.yaml`) is a local extension or
replacement of that base.

## Baseline resolution

Modified files are diffed against the **pristine template at the recorded
`source_sha`**, not against the current template. That way the diff shows only
local edits. Resolve a scaffold source in this order and stop at the first one
that works:

1. The `SCAFFOLD_SOURCE_URL` environment variable.
2. The `url` field of `.scaffold/source.json`.
3. Ask the user for the path to a local `common-project-setup` checkout.
4. Clone `https://github.com/deniskrizanovic/common-project-setup` into a temp
   directory **outside the project**:
   `git clone --filter=blob:none --no-checkout <url> "$(mktemp -d)/scaffold-src"`.

For each modified file, read the pristine version with
`git -C <source> show <source_sha>:templates/<dest>`, where `<source_sha>` is
the component's `source_sha` in `.scaffold/manifest.json`. For a `writer-file`,
use the template path after ` <- ` instead of `templates/<dest>`.

### Offline degradation

If no source resolves, the clone fails, the `source_sha` is missing, or
`git show` cannot read the commit, the run **degrades** instead of stopping:

- List the modified files **by path only**, without a diff.
- State in the "Baseline status" section that the pristine baseline was
  unavailable and why (no source configured, network failure, unknown SHA).
- Still run every other category in full.

## Checklist

Work through the categories in this order. For every category, record either
its candidates or "none found". Do not skip a category silently.

### 1. Modified scaffold files

1. For each component in `.scaffold/manifest.json` with a `files` map, hash each
   file on disk: `shasum -a 256 <dest>`.
2. A file whose disk hash differs from the recorded hash is **modified**. A
   recorded file that is missing on disk is also reported (as deleted).
3. Diff each modified file against its pristine template (see "Baseline
   resolution"): `diff -u <pristine> <dest>`, or `git diff --no-index`.
4. Read the diff and explain in plain language what the local edit changes in
   behaviour. Do not just restate the diff.
5. Weigh the edit using the candidate fields below: benefits, risks or costs,
   and a recommendation.

### 2. Local gates

1. Read `.scaffold/gates.json` (`gates` array).
2. Every gate whose `name` is not a `gate:` entry in the inventory is a local
   gate. Also report an inventory gate whose `cmd` or `stopReason` was changed.
3. Note what the gate checks and whether it is language-agnostic.

### 3. Local hooks and scripts

1. Read `.claude/settings.json` `hooks`. Every hook command that is not a
   `hook:` entry in the inventory is a local hook.
2. List files in `scripts/`, `.githooks/`, and `tokencost/`. Every file that is
   not a `tracked-file:` or `writer-file:` entry is a local script.
3. For each, read enough of the script to summarize what it does.

### 4. Wishlist overrides

1. Read `.scaffold/plugins.json` (`plugins` array) and `.scaffold/skills.yaml`
   (`skills:` list). Every entry is a candidate.
2. Note whether it replaces a base entry (same id or name) or adds a new one.

### 5. Config rules

1. Read `openspec/config.yaml` `rules:` and compare it with the pristine
   `templates/openspec/config.yaml` at the recorded `source_sha`. Rules that the
   template does not have are candidates.
2. Do the same for instructions in the local schema clone under
   `openspec/schemas/spec-driven/`.
3. Ignore the `context:` block (see "Exclusions").
4. Skip this category, and say so, when `openspec/` is absent.

### 6. Recurring patterns

1. Read `CLAUDE.md` (and `AGENTS.md` if present). Look for rules, conventions,
   or workarounds that touch scaffold-managed areas: gates, hooks, commit flow,
   spec format, plugins, skills.
2. Read the OpenSpec archive (`openspec/changes/archive/*/proposal.md` and
   `tasks.md`). Look for more than one change patching the same scaffold area,
   such as the commit gate. Cite those changes by directory name.
3. **Skip the OpenSpec archive** when `openspec/` is absent, and say so in the
   report.

## Generalizability and exclusions

A candidate is worth proposing upstream only if it would help projects other
than this one. Good signs:

- language-agnostic gate or hook logic
- a bug fix to a scaffold script
- a widely useful plugin or skill
- a config rule that is not domain-specific

Use `adapt` when the idea is generic but the current form is tied to this
project. Use `keep-local` when the change only makes sense here.

### Exclusions

- **Never** propose the `openspec/config.yaml` `context:` block. It is
  project-specific by design.
- Exclude **domain code** and anything that references project domain names or
  paths outside the scaffold's areas.

### Secrets

Do not copy credentials into the report. Replace secret-like values with
`<redacted>`, including:

- tokens and API keys
- `*_TOKEN=`, `*_KEY=`, `*_SECRET=`, and `*_PASSWORD=` assignments
- `Authorization:` headers and bearer tokens
- URLs with embedded credentials (`https://user:pass@host`)

For example, a hook command `curl -H "Authorization: Bearer abc123" ...` is
shown as `curl -H "Authorization: Bearer <redacted>" ...`.

Redaction is heuristic. The report ends with a note that it must be reviewed
before it is shared.

## Report template

Write the report to `.scaffold/retro/retro-<YYYY-MM-DD>.md` with these sections,
in this order:

```markdown
# Scaffold retro — <YYYY-MM-DD>

## Summary
<project name>, <N> candidates (<P> promote, <A> adapt, <K> keep-local).
One line per promote/adapt candidate.

## Baseline status
Source: <url or path>, or "unavailable: <reason>".
Recorded source_sha per component. Whether modified files were diffed against
the pristine template or listed by path only.

## Modified scaffold files
<candidates>

## Local gates
<candidates>

## Local hooks and scripts
<candidates>

## Wishlist overrides
<candidates>

## Config rules
<candidates>

## Recurring patterns
<candidates>

## Categories checked with none found
- <category>: none found
- <category>: skipped (<reason, e.g. no openspec/ directory>)

---
Secret redaction is heuristic. Review this report before sharing it.
```

Omit a category section that has no candidates and list it under "Categories
checked with none found" instead.

### Candidate fields

Every candidate has all of these fields:

```markdown
### <short title>
- **Category:** <one of the six categories>
- **Evidence:** <paths> plus a short diff or excerpt (secrets redacted)
- **Change summary:** what changed, in plain language
- **Benefits:** why promoting it upstream would help
- **Risks/costs:** why promoting it could be a bad idea (project-specific,
  breaks other consumers, maintenance burden)
- **Recommendation:** `promote` | `adapt` | `keep-local` — <one-line reason>
- **Upstream target:** <template file, `scaffold_base/manifest.yaml`, or a new
  component>
- **Suggested change name:** <kebab-case, e.g. `add-commit-gate-timeout`>
```

Omit **Suggested change name** when the recommendation is `keep-local`. Every
`promote` or `adapt` candidate must have one.

### No-candidates form

When nothing diverges and nothing was added, still write the report:

```markdown
# Scaffold retro — <YYYY-MM-DD>

## Summary
No candidates found.

## Baseline status
<as above>

## Categories checked with none found
- Modified scaffold files: none found
- Local gates: none found
- Local hooks and scripts: none found
- Wishlist overrides: none found
- Config rules: none found
- Recurring patterns: none found
```

## After the run

Tell the user where the report is. Suggest the next step: review it, then run
`/opsx:propose` in `common-project-setup` with the chosen candidates. Do not do
that step yourself.
