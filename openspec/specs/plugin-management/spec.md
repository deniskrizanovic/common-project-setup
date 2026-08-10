# plugin-management Specification

## Purpose

Defines how the scaffold reconciles a desired plugin wishlist against installed plugins and installs via the claude CLI.

## Requirements

### Requirement: Desired-plugin wishlist
The scaffold SHALL define a base plugin wishlist in the repo, and a project MAY extend or override it via `.scaffold/plugins.json`.

#### Scenario: base wishlist applies
- **WHEN** a project has no `.scaffold/plugins.json`
- **THEN** the base wishlist alone determines the desired plugin set

#### Scenario: per-project override composes
- **WHEN** a project defines `.scaffold/plugins.json`
- **THEN** its entries extend or override the base wishlist to produce the effective desired set

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
