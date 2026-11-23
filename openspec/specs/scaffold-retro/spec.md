# scaffold-retro Specification

## Purpose

Defines the `scaffold-retro` skill: distributed to scaffold-provisioned projects, it inspects the project and reports candidate improvements worth promoting back into `common-project-setup`, without modifying the project or the scaffold.

## Requirements


### Requirement: Retro skill distributed as a file component
The scaffold SHALL register a `scaffold-retro` file component that installs the retro skill at `.claude/skills/scaffold-retro/SKILL.md` in the target project and tracks it by content hash like other file components.

#### Scenario: install lays down the skill
> **Tests:** tests/test_scaffold_retro.py::test_install_writes_retro_skill
- **GIVEN** a project without `.claude/skills/scaffold-retro/SKILL.md`
- **WHEN** the user accepts the `scaffold-retro` component during `install`
- **THEN** the skill file is written and `.scaffold/manifest.json` records its `sha256` and source SHA

#### Scenario: drift reported like other file components
> **Tests:** tests/test_scaffold_retro.py::test_retro_skill_modified_detected
- **GIVEN** an installed `scaffold-retro` component whose skill file was edited locally
- **WHEN** `check` runs
- **THEN** the component is classified MODIFIED

#### Scenario: no OpenSpec root required
> **Tests:** tests/test_scaffold_retro.py::test_retro_installs_without_openspec_root
- **GIVEN** a project with no initialized OpenSpec root
- **WHEN** `check` runs
- **THEN** `scaffold-retro` is classified MISSING (installable), not BLOCKED

### Requirement: Modified scaffold files surfaced as candidates
The skill SHALL identify every scaffold-tracked file whose disk content differs from the hash in `.scaffold/manifest.json`, and SHALL report each as a candidate with a diff against the pristine template at the recorded `source_sha`. For each modified file, the skill SHALL also explain in plain language what the local edit changes in behaviour, and SHALL weigh the edit using the assessment fields defined under "Candidate report structure".

#### Scenario: local patch to a scaffold script
> **Tests:** tests/test_scaffold_retro.py::test_skill_instructs_modified_file_diff
- **GIVEN** a project where `scripts/commit_gate.py` differs from its manifest hash
- **WHEN** the retro skill runs
- **THEN** the report lists `scripts/commit_gate.py` under modified scaffold files with a diff against the template at the recorded `source_sha`
- **AND** the candidate includes a plain-language summary of what the edit changes, at least one benefit, at least one risk or cost, and a recommendation

### Requirement: Local additions surfaced as candidates
The skill SHALL identify project additions in scaffold-adjacent locations: gates in `.scaffold/gates.json` the scaffold did not register, Claude Code hooks and scripts the scaffold does not own, `.scaffold/plugins.json` / `.scaffold/skills.yaml` wishlist entries, and `openspec/config.yaml` rules beyond the template.

#### Scenario: extra gate and wishlist entry
> **Tests:** tests/test_scaffold_retro.py::test_skill_covers_all_candidate_categories
- **GIVEN** a project with a custom gate in `.scaffold/gates.json` and an extra skill in `.scaffold/skills.yaml`
- **WHEN** the retro skill runs
- **THEN** the report lists the gate under local gates and the skill under wishlist overrides

### Requirement: Recurring patterns surfaced as candidates
The skill SHALL look for recurring project conventions or workarounds that touch scaffold-managed areas, such as `CLAUDE.md` rules or archived OpenSpec changes repeatedly patching the same scaffold component, and SHALL report them as pattern candidates.

#### Scenario: repeated fixes to one area
> **Tests:** tests/test_scaffold_retro.py::test_skill_covers_all_candidate_categories
- **GIVEN** a project whose archived OpenSpec changes patch the commit gate more than once
- **WHEN** the retro skill runs
- **THEN** the report lists a pattern candidate citing those changes

### Requirement: Candidate report structure
The skill SHALL write the report to `.scaffold/retro/retro-<YYYY-MM-DD>.md`. Each candidate SHALL state:

- its category
- evidence: paths plus a short diff or excerpt
- a plain-language summary of what changed
- benefits: why promoting it upstream would help
- risks or costs: why promoting it could be a bad idea, such as being project-specific, breaking other consumers, or adding maintenance burden
- a recommendation of `promote`, `adapt` (generalize first), or `keep-local`, with a one-line reason
- a suggested upstream target
- a suggested kebab-case change name. This field is omitted when the recommendation is `keep-local`.

#### Scenario: report written with required fields
> **Tests:** tests/test_scaffold_retro.py::test_skill_defines_report_contract
- **GIVEN** a project with at least one candidate
- **WHEN** the retro skill completes
- **THEN** `.scaffold/retro/retro-<today>.md` exists, and every candidate has a category, evidence, a change summary, benefits, risks, a recommendation, and an upstream target
- **AND** every candidate whose recommendation is not `keep-local` has a suggested change name

#### Scenario: no candidates found
> **Tests:** tests/test_scaffold_retro.py::test_skill_defines_report_contract
- **GIVEN** a project with no divergence or additions
- **WHEN** the retro skill completes
- **THEN** the report states that no candidates were found and lists the categories checked

### Requirement: Project-specific content and secrets excluded
The skill SHALL exclude project-specific content, including the `openspec/config.yaml` `context:` block and domain code, from candidates. It SHALL NOT copy credentials, tokens, or other secret values into the report.

#### Scenario: context block not proposed upstream
> **Tests:** tests/test_scaffold_retro.py::test_skill_excludes_project_specific_and_secrets
- **GIVEN** a project whose `config.yaml` `context:` block is filled
- **WHEN** the retro skill runs
- **THEN** the context block does not appear as a candidate

#### Scenario: secret in a hook command redacted
> **Tests:** tests/test_scaffold_retro.py::test_skill_excludes_project_specific_and_secrets
- **GIVEN** a local hook whose command embeds a token value
- **WHEN** the retro skill reports that hook
- **THEN** the report shows the hook with the secret value redacted

### Requirement: Read-only apart from the report
The skill SHALL write only its report file. It SHALL NOT modify project files, scaffold-tracked files, or the `common-project-setup` source, and SHALL take no outward action such as filing issues, opening PRs, or pushing.

#### Scenario: run leaves the project unchanged
> **Tests:** tests/test_scaffold_retro.py::test_skill_declares_read_only_boundary
- **GIVEN** a provisioned project
- **WHEN** the retro skill runs
- **THEN** the only new or changed path is the report under `.scaffold/retro/`

### Requirement: Degraded run when the source is unreachable
When the scaffold source or the recorded `source_sha` cannot be read, the skill SHALL still report local-addition and pattern candidates, and SHALL state in the report that modified files could not be diffed against the pristine baseline.

#### Scenario: offline run
> **Tests:** tests/test_scaffold_retro.py::test_skill_defines_offline_degradation
- **GIVEN** the scaffold source is unreachable
- **WHEN** the retro skill runs
- **THEN** the report lists modified files by path only, notes the missing baseline, and still includes the other categories
