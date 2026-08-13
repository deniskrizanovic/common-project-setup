# plugin-management Specification

## Purpose

Defines how the scaffold reconciles a desired plugin wishlist against installed plugins and installs via the claude CLI.

## Requirements

### Requirement: Desired-plugin wishlist
The scaffold SHALL derive the base plugin wishlist from the `plugins:` section of `scaffold_base/manifest.yaml`, and a project MAY extend or override it via `.scaffold/plugins.json`. The committed `scaffold_base/plugins.json` SHALL be a generated artifact produced from the manifest, not a hand-authored file.

#### Scenario: base wishlist applies
- **WHEN** a project has no `.scaffold/plugins.json`
- **THEN** the base wishlist derived from the manifest alone determines the desired plugin set

#### Scenario: per-project override composes
- **WHEN** a project defines `.scaffold/plugins.json`
- **THEN** its entries extend or override the base wishlist to produce the effective desired set

#### Scenario: plugins.json is generated
- **WHEN** the committed `scaffold_base/plugins.json` is read as the base wishlist
- **THEN** its contents equal the generator output for the current `manifest.yaml` (enforced by the drift guard)

### Requirement: Reconciliation against installed plugins
The script SHALL reconcile the desired plugin set against `~/.claude/plugins/installed_plugins.json` and classify each plugin.

#### Scenario: desired plugin missing
- **WHEN** a wishlisted plugin is not present in `installed_plugins.json`
- **THEN** the script classifies it MISSING and offers to install it

#### Scenario: installed plugin behind marketplace
- **WHEN** a wishlisted plugin is installed but its `gitCommitSha` differs from the marketplace head
- **THEN** the script classifies it STALE and offers to update it

### Requirement: Install via the claude CLI
The script SHALL install and update plugins by shelling out to the `claude plugin install` CLI, registering the required marketplace first.

#### Scenario: install shells out
- **WHEN** the user accepts installing a MISSING plugin
- **THEN** the script ensures the plugin's marketplace is registered and runs `claude plugin install <id>`

#### Scenario: claude CLI absent
- **WHEN** the `claude` CLI is not on PATH
- **THEN** the script reports plugin actions as unavailable and prints the exact commands the user would run, without failing the rest of the run

### Requirement: EXTRA plugins are never removed
The script SHALL report installed plugins that are absent from the desired set as EXTRA and SHALL never uninstall them.

#### Scenario: extra plugin reported only
- **WHEN** a plugin is installed but not in the effective desired set
- **THEN** the script reports it EXTRA and takes no removal action

### Requirement: Recorded marketplace source is authoritative
Each plugin's recorded marketplace source in `scaffold_base/manifest.yaml` SHALL identify the marketplace the plugin is actually installed from, and the install command SHALL register that source. A source that is self-consistent between `manifest.yaml` and the generated `plugins.json` but does not resolve to the plugin's real marketplace is a defect, even though the drift guard passes.

#### Scenario: source resolves to the real marketplace
- **WHEN** the scaffold installs a wishlisted plugin whose id is `<name>@<marketplace>`
- **THEN** the marketplace registered by the install command resolves to the repository the plugin actually ships from, not merely a repository named consistently across `manifest.yaml` and `plugins.json`

#### Scenario: caveman and superpowers sources are correct
- **WHEN** the base manifest is read for the `caveman@caveman` and `superpowers@claude-plugins-official` plugins
- **THEN** their sources are `JuliusBrussee/caveman` and `anthropics/claude-plugins-official` respectively
