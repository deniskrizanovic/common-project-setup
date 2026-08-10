## Context

Desired components reach a project through four disconnected channels:

| Channel | Mechanism | Reconcile target | Install command |
| --- | --- | --- | --- |
| Marketplace plugins | `plugins.json` wishlist | `~/.claude/plugins/installed_plugins.json` | `claude plugin install` |
| Github skills | `skills-lock.json` | `skills-lock.json` (+ `npx skills check`) | `npx skills add` |
| In-repo skills | committed files | file-component hashes | file copy |
| Per-project | `.scaffold/plugins.json` | composed with base | — |

The installer (`scaffold.py`) already reconciles plugins and file components with a MISSING/STALE/EXTRA/OK model and a per-item install prompt. Github-sourced skills have no scaffold representation. `scaffold_base/plugins.json` is hand-edited and only covers the plugin channel.

This change makes a single YAML manifest the source of truth and teaches the installer to fan out to both CLI-backed channels, reusing the existing reconciliation architecture.

## Goals / Non-Goals

**Goals:**
- One hand-edited file (`manifest.yaml`) declaring plugins and skills.
- `plugins.json` and `skills-lock.json` generated from it, committed for reviewable diffs.
- Skill reconciler mirrors the plugin reconciler exactly: classify, per-item prompt, EXTRA-never-removed, CLI-absent fallback.
- Drift guard keeps committed artifacts in sync with the manifest.

**Non-Goals:**
- Migrating in-repo committed skills (openspec-*, etc.) into the manifest — they stay on the file-component channel.
- A batch "install all" option — explicitly rejected; per-item prompt retained.
- Auto-removing EXTRA plugins or skills.
- Adding domain skills beyond the agreed baseline set.

## Decisions

**D1: YAML manifest with typed sections (not one flat list).**
Plugins and skills resolve with different identifiers (`id@marketplace`+source vs `owner/repo:path`). Typed `plugins:` / `skills:` sections read cleanly for a hand-editor. Alternative — one flat list with a `kind:` tag — is uniform for the parser but more verbose per line; rejected for readability.

**D2: Artifacts are generated but committed.**
`plugins.json` and `skills-lock.json` are regenerated from the manifest and checked in, so the user reviews diffs before commit. Alternative — pure build artifacts, gitignored — loses reviewability; rejected. A drift check (parallel to existing drift detection) enforces sync.

**D3: Skill channel reuses the plugin reconciler shape.**
`npx skills add` / `npx skills check` map 1:1 onto the existing `claude plugin install` flow, and `skills-lock.json` with `computedHash` is the natural reconcile target. The skill reconciler adopts the same MISSING/STALE/EXTRA/OK classification, the same `_prompt` per-item UX, and the same "print commands when CLI absent" fallback.

**D4: `plugins.json` shape preserved.**
The generator emits the current `{ "plugins": [ { id, marketplaceSource } ] }` structure so existing consumers (`compose_wishlist`, `classify_plugins`) are untouched — only the *source* of that file changes from hand-edited to generated.

**D5: Baseline manifest content (stance = "Denis's toolkit").**
Plugins: `caveman`, `superpowers`. Skills: matt pocock `grill-me`, `grill-with-docs`, `improve-codebase-architecture`; dk-skills `diff-org-changes`, `dk-cosmic-counting-coach`, `gherkin-authoring`. `scopezilla-dev` deliberately excluded (special-purpose). The baseline is the user's personal toolkit, not a neutral minimum.

**D6: `gherkin-authoring` published to dk-skills.**
It currently lives only in `collaborativegherkin/.claude/skills/`. To ride the github-skill channel it must exist at `deniskrizanovic/dk-skills:gherkin-authoring`. This publish is a prerequisite (a push to that repo) before the manifest reference resolves.

## Risks / Trade-offs

- [Manifest ref resolves before `gherkin-authoring` is published] → Sequence the publish task first; drift/install for that skill will fail with a clear "source not found" until pushed.
- [`dk-cosmic-counting-coach` ships multi-MB PDF manuals] → Every project that installs it pulls the PDFs. Accepted; the per-item prompt lets a project skip it.
- [`skills-lock.json` hashing differs from expectation] → Generator must compute the same `computedHash` the `npx skills` CLI writes, or drift will false-positive. Validate against a real `npx skills add` output before finalizing.
- [`npx skills` CLI absent in CI/headless] → Same graceful degradation as the `claude` CLI path: report unavailable, print commands, don't fail the run.
- [Two override paths now exist] → `.scaffold/plugins.json` for plugins plus a new skill override path; keep their composition logic symmetric to avoid divergence.

## Migration Plan

1. Publish `gherkin-authoring` to `deniskrizanovic/dk-skills` (external prerequisite).
2. Author `scaffold_base/manifest.yaml` with the baseline set.
3. Add manifest reader + generator; regenerate `plugins.json` (should equal current content plus no scopezilla) and create `skills-lock.json`.
4. Add skill reconciler + drift guard to `scaffold.py`.
5. Commit generated artifacts; review diffs.

Rollback: revert to hand-edited `plugins.json`; the generator and skill reconciler are additive and can be removed without affecting the plugin flow.

## Open Questions

- Exact `computedHash` algorithm the `npx skills` CLI uses (confirm from an existing `skills-lock.json` entry vs a fresh `npx skills add`).
- Per-project skill override filename/format — mirror `.scaffold/plugins.json` as `.scaffold/skills.yaml`, or fold both into a single `.scaffold/manifest.yaml`.
