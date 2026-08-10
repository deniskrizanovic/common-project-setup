# project-config-baseline Specification

## Purpose

Defines the non-boilerplate `openspec/config.yaml` baseline a scaffolded project must carry.

## Requirements

### Requirement: Non-boilerplate config
A scaffolded project's `openspec/config.yaml` SHALL contain a real `context` block and per-artifact `rules`, and SHALL NOT ship the commented-out template placeholders.

#### Scenario: config installed with real content
- **WHEN** the `config-baseline` component is installed into a project
- **THEN** `openspec/config.yaml` contains a populated `context` block and at least one per-artifact `rules` entry

#### Scenario: empty template flagged
- **WHEN** `check` runs against a project whose `openspec/config.yaml` is the unmodified commented template
- **THEN** the script classifies `config-baseline` as not satisfied and offers to install the baseline
