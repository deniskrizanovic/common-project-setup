## Context

The scaffold seeds proven components and reports drift. `branch_guard.py` guards
`main`/`master` locally, but a fresh project has no GitHub remote — no push
target and no server-side branch protection. Nothing surfaces that gap.

The codebase has an established precedent for outward, hard-to-reverse actions:
it **refuses to run them and prints the commands instead**. Three cases already:
`openspec init` is printed, not run, when the root is absent (needs a `--tools`
choice the scaffold won't guess); `claude plugin install` and `npx skills add`
are printed when their CLIs are absent. Creating a public GitHub repository is
the most outward action of all, so it inherits the same treatment.

## Goals / Non-Goals

**Goals:**
- A registry component that nags (`MISSING`) until the project has an `origin`
  remote, and prints the exact `gh`/`git` commands to fix it.
- Reuse the existing gate pattern (`needs_openspec` → BLOCKED) for git presence.

**Non-Goals:**
- The tool never creates the repo, adds a remote, pushes, or sets branch
  protection. All outward action stays with the user.
- No repo-name prompt (basename is used); no branch-protection configuration.
- No tracked files, so no STALE/MODIFIED drift for this component.

## Decisions

**Decision: Print-only, not action (Design A over Design B).**
Running `gh repo create` would make this the first side-effecting component,
requiring gh auth, network, and name-collision handling, and it is neither
idempotent nor reversible. Printing keeps it consistent with the openspec-init /
plugins / skills refusals. *Alternative considered:* actually shelling out to
`gh` — rejected as contradicting the codebase's own resolved decisions.

**Decision: Detect via the `origin` remote.**
`git remote get-url origin` is the cheapest signal that a push target exists.
Any host counts as OK (reported, not managed) — we only care that a remote is
configured, not that it is github.com. *Alternative:* querying the GitHub API
for the repo — rejected; needs auth/network and answers a question we aren't
asking.

**Decision: `needs_git` gate mirrors `needs_openspec`.**
Not-a-git-repo → BLOCKED with precedence over MISSING, identical shape to the
no-OpenSpec-root gate. Reuses the classification precedence already in
`scaffold-installer`.

**Decision: Repo name = directory basename.**
Matches the `gh repo create --source=.` convention and avoids a prompt. The
printed command is a copy-paste-ready single line.

## Risks / Trade-offs

- [User on a non-GitHub remote sees OK though branch protection isn't GitHub's]
  → Acceptable; the component's job is "has a push target," not "is on GitHub."
- [Printed `gh` command assumes the user is authed / repo name is free]
  → Acceptable; the command is advisory and the user runs it deliberately.
- [A component with no tracked files is a new shape in the registry]
  → Contained: classification short-circuits to BLOCKED/MISSING/OK before any
  hash logic runs.

## Open Questions

- None. Scope, visibility (public), and protection (skipped) are decided.
