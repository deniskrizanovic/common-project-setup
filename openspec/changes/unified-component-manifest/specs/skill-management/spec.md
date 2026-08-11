## ADDED Requirements

### Requirement: Desired-skill wishlist
The scaffold SHALL derive the desired github-sourced skill set from the `skills:` section of `manifest.yaml`, and a project MAY extend or override it via a per-project skill override.

#### Scenario: base skill wishlist applies
- **WHEN** a project has no per-project skill override
- **THEN** the manifest's `skills:` section alone determines the desired skill set

#### Scenario: per-project skill override composes
- **WHEN** a project defines a per-project skill override
- **THEN** its entries extend or override the base wishlist to produce the effective desired skill set

### Requirement: Reconciliation against skills-lock
The script SHALL reconcile the desired skill set against the project's `skills-lock.json` and classify each skill.

#### Scenario: desired skill missing
- **WHEN** a wishlisted skill is absent from `skills-lock.json`
- **THEN** the script classifies it MISSING and offers to install it

#### Scenario: installed skill stale
- **WHEN** a wishlisted skill is installed but its upstream `computedHash` (re-resolved via the `npx skills` CLI) differs from the hash recorded in `skills-lock.json`
- **THEN** the script classifies it STALE and offers to update it

#### Scenario: installed skill current
- **WHEN** a wishlisted skill is present and up to date
- **THEN** the script classifies it OK and skips it

### Requirement: Install via the skills CLI
The script SHALL install and update github-sourced skills by shelling out to the `npx skills` CLI.

#### Scenario: install shells out
- **WHEN** the user accepts installing a MISSING skill
- **THEN** the script runs `npx skills add <owner/repo:skill-path>` for that skill

#### Scenario: skills CLI absent
- **WHEN** the `npx skills` CLI is not available
- **THEN** the script reports skill actions as unavailable and prints the exact commands the user would run, without failing the rest of the run

### Requirement: Per-item install prompt
The script SHALL prompt for each non-OK skill individually with an install/skip choice, consistent with the plugin install flow. It SHALL NOT offer a batch install.

#### Scenario: one prompt per skill
- **WHEN** the install command processes the desired skill set
- **THEN** each non-OK skill produces its own `[i]nstall/update, [s]kip?` prompt and OK skills are skipped without prompting

### Requirement: EXTRA skills are never removed
The script SHALL report installed skills that are absent from the desired set as EXTRA and SHALL never uninstall them.

#### Scenario: extra skill reported only
- **WHEN** a skill is present in `skills-lock.json` but not in the effective desired set
- **THEN** the script reports it EXTRA and takes no removal action
