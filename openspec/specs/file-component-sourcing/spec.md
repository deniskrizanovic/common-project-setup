# file-component-sourcing Specification

## Purpose

Defines how file components are sourced from a remote git ref and tracked by content hash for drift detection.

## Requirements

### Requirement: Fetch from a remote git ref
File components SHALL be sourced from a remote git ref fetched at run time, not from files vendored in the target project.

#### Scenario: source fetched on run
- **WHEN** `install` or `check` runs for a file component
- **THEN** the script fetches the configured source ref (default `main`) and reads the canonical file contents from it

#### Scenario: installed source SHA recorded
- **WHEN** a file component is installed or updated
- **THEN** the manifest records the exact git SHA the content was taken from

### Requirement: Content-hash tracking
The script SHALL track each installed file by `sha256` in `.scaffold/manifest.json` and use those hashes to detect local modification.

#### Scenario: manifest records file hashes
- **WHEN** a file component is installed
- **THEN** the manifest stores each tracked file's path and `sha256`, plus the component version and installed source SHA

#### Scenario: disk hash compared on check
- **WHEN** `check` runs
- **THEN** the script re-hashes each tracked file on disk and compares it to the manifest hash to decide MODIFIED

### Requirement: Offline degradation
When the source ref cannot be fetched, the script SHALL fall back to a disk-versus-manifest comparison and SHALL clearly report the offline state.

#### Scenario: offline check reports honestly
- **WHEN** `check` cannot reach the source ref
- **THEN** the script reports MODIFIED status from the manifest comparison, states that STALE could not be evaluated, and never reports a component as current on the basis of an unreachable source
