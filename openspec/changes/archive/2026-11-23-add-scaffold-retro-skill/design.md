# Design

## Context

- File components copy `templates/<src>` to `<dest>` in the child and record `{version, source_sha, files:{dest: sha256}}` in `.scaffold/manifest.json`. Every existing tracked `dest` mirrors its `src` path, so a template path can be derived from any manifest entry.
- The manifest stores `source_sha` but not the source URL. The URL comes from `SCAFFOLD_SOURCE_URL`, then `.scaffold/source.json`, then this checkout's path (`REPO_ROOT`). In a child project, the last fallback usually cannot be resolved.
- The scaffold-owned inventory exists only in `scaffold.py`: `build_registry()` tracked files, `BASE_COMMIT_GATES` (`tests`, `lint:specs`, `lint:given`), `STATIC_ANALYSIS_GATES` names, and the hooks `wire_hooks()` writes. A retro has to know this inventory to tell a local addition from a scaffold-owned one.
- Skills are plain markdown instructions, so the retro's "behavior" is what the agent does after reading `SKILL.md`. Tests can only check the file's content contract and its install path.

## Goals / Non-Goals

**Goals:**
- Ship the skill through the existing file-component path with no new component class or drift state.
- Make the skill's inventory of scaffold-owned items checkable against `scaffold.py`, so the two cannot drift silently.
- Keep evidence gathering mechanical (hash compare, `git show`, JSON reads) and keep judgment (is this generalizable?) in the agent.

**Non-Goals:**
- No `scaffold.py retro` subcommand or machine-readable facts output in this change.
- No cross-project aggregation. One run covers one project.
- No automated upstream action: no OpenSpec change created in `common-project-setup`, no issues or PRs.

## Decisions

**D1. Skill-only, no Python helper.** The skill tells the agent to read `.scaffold/manifest.json`, re-hash tracked files (`shasum -a 256`), read `.scaffold/gates.json`, `.claude/settings.json`, and the override files, and run `git show` for baselines.
*Alternative*: a `scaffold.py retro --json` subcommand that emits the facts deterministically. That is more testable, but the child would need a resolvable scaffold checkout just to start a run, and it is a second feature. If the skill's mechanical steps prove flaky, this can be added later behind the same report contract.

**D2. Embedded inventory plus a sync test.** `SKILL.md` carries a "Scaffold-owned inventory" section listing the tracked file paths, base and static gate names, and scaffold-wired hook commands. A pytest compares that section against `build_registry()`, `BASE_COMMIT_GATES`, `STATIC_ANALYSIS_GATES`, and the `wire_hooks` hook set, and fails on any mismatch. This follows the same idea as the `drift` guard for `manifest.yaml`.
*Alternative*: have the agent parse `scaffold.py` at `source_sha` at runtime. That is fragile, because the agent would be reading Python by eye, and it fails offline.

**D3. Baseline resolution order.** First `SCAFFOLD_SOURCE_URL`, then `.scaffold/source.json` `url`. If neither is set, the agent asks the user for a local `common-project-setup` checkout path. The last fallback is `https://github.com/deniskrizanovic/common-project-setup`, cloned into a temp dir outside the project with `--filter=blob:none`. The pristine file is read with `git show <source_sha>:templates/<dest>`. If any step fails, the run degrades as the spec requires: modified files are listed by path only.

**D4. Report location `.scaffold/retro/retro-<YYYY-MM-DD>.md`.** It sits beside the other scaffold state and is easy to `.gitignore` or commit by choice. A second run on the same day overwrites the file, which is acceptable for a point-in-time snapshot. Report sections, in order:
1. Summary
2. Baseline status
3. One section per category, each with candidates
4. Categories checked with none found

Candidate fields: category, evidence, change summary, benefits, risks/costs, recommendation (`promote` / `adapt` / `keep-local`), upstream target, suggested change name (omitted for `keep-local`).

**D5. Generalizability heuristics, stated in the skill.** A candidate is worth proposing only if it would help projects other than this one:
- language-agnostic gate or hook logic
- a bug fix to a scaffold script
- a widely useful plugin or skill
- a config rule that is not domain-specific

Anything that references project domain names, paths outside the scaffold's areas, or the `context:` block is excluded. Values that look like secrets (tokens, keys, `*_TOKEN=`/`*_KEY=` assignments, URLs with credentials) are shown as `<redacted>`.

**D6. Component definition.** `FileComponent(id="scaffold-retro", files=[(".claude/skills/scaffold-retro/SKILL.md", ".claude/skills/scaffold-retro/SKILL.md")])`, with no precondition, no `needs_openspec`, and no `needs_git`. The pattern-mining step skips the OpenSpec archive when no `openspec/` directory exists.

## Risks / Trade-offs

- [Agent skips steps or reports noise] → The skill gives an ordered checklist per category and a fixed report template. The "categories checked" section makes skipped steps visible.
- [Inventory goes stale when scaffold adds a component] → The D2 sync test fails in CI and pre-commit until `SKILL.md` is updated.
- [Child edits its own copy of the retro skill] → Normal MODIFIED drift. The retro reports its own diff like any other modified file.
- [Temp clone needs network] → It is the last fallback only, and the offline path is spec'd.
- [Secret redaction is heuristic] → The skill says that output must be reviewed before it is shared. The report stays local, since the skill takes no outward action.

## Migration Plan

Additive. Existing projects see `scaffold-retro` as MISSING and receive it on their next `scaffold install` or `scaffold update`. `update` installs MISSING file components. Rollback: delete `.claude/skills/scaffold-retro/` and its manifest entry.
