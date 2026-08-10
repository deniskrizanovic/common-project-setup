# cost-tracker Specification

## Purpose

Defines how the cost-tracker component is installed and versioned within a scaffolded project.

## Requirements

### Requirement: Project-local installation
The cost-tracker SHALL be installed project-locally under `tokencost/`, with hooks pointing at the project copy and no global copy under `~/.claude/hooks/`.

#### Scenario: tokencost scaffolded in project
- **WHEN** the `cost-tracker` component is installed
- **THEN** the tracker script and a `cost.csv` are created under the project's `tokencost/` directory and the hooks reference that project-local path

### Requirement: Provenance stamp
The installed cost-tracker SHALL carry a provenance stamp identifying its component version so future drift is detectable.

#### Scenario: version stamp present
- **WHEN** the cost-tracker is installed
- **THEN** its files and manifest entry record the component version used to install them
