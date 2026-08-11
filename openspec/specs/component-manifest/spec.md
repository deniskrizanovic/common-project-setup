# component-manifest Specification

## Purpose

Defines a single hand-edited YAML manifest as the source of truth for scaffold components (plugins and skills), the committed artifacts generated from it, and the drift guard that keeps them in sync.

## Requirements

### Requirement: Single YAML manifest as source of truth
The scaffold SHALL define desired components in a single hand-edited file `scaffold_base/manifest.yaml` with two typed top-level sections: `plugins:` and `skills:`. This manifest SHALL be the only file authored by hand for component selection.

#### Scenario: manifest declares both channels
- **WHEN** `scaffold_base/manifest.yaml` lists entries under `plugins:` and `skills:`
- **THEN** the `plugins:` entries determine the desired marketplace-plugin set and the `skills:` entries determine the desired github-sourced skill set

#### Scenario: plugin entry shape
- **WHEN** a `plugins:` entry provides `id` (`name@marketplace`) and `source` (marketplace `owner/repo`)
- **THEN** the manifest reader accepts it as a desired plugin

#### Scenario: skill entry shape
- **WHEN** a `skills:` entry is a string of the form `owner/repo:skill-path`
- **THEN** the manifest reader accepts it as a desired github-sourced skill

#### Scenario: missing required field rejected
- **WHEN** a `plugins:` entry omits `id`, or a `skills:` entry is not a valid `owner/repo:skill-path` string
- **THEN** the reader fails with an error identifying the offending entry

### Requirement: Generated committed artifacts
The installer SHALL generate `scaffold_base/plugins.json` and `scaffold_base/skills-lock.json` from `manifest.yaml`. Both artifacts SHALL be committed to the repository so their diffs are reviewable, and SHALL NOT be hand-edited.

#### Scenario: plugins.json generated from manifest
- **WHEN** the generator runs against a manifest
- **THEN** `scaffold_base/plugins.json` contains one entry per `plugins:` item, preserving the existing `plugins.json` shape (`id`, `marketplaceSource`)

#### Scenario: skills-lock.json generated from manifest
- **WHEN** the generator runs against a manifest
- **THEN** `scaffold_base/skills-lock.json` contains one entry per `skills:` item with its `source`, `sourceType`, `skillPath`, and `computedHash`

### Requirement: Drift guard between manifest and artifacts
The scaffold SHALL provide a check that fails when the committed `plugins.json` or `skills-lock.json` does not match what the manifest would generate.

#### Scenario: artifacts in sync
- **WHEN** the committed artifacts equal the generator output for the current manifest
- **THEN** the drift check passes

#### Scenario: artifacts drifted
- **WHEN** the manifest has changed but an artifact was not regenerated
- **THEN** the drift check fails and reports which artifact is out of sync
