# github-init-gate Specification

## Purpose

Detects the absence of a GitHub `origin` remote on the project root and, on `install`, prints (never runs) the `gh`/`git` commands to create the repository and push. Gated BLOCKED when the project is not a git repository. Tracks no files and takes no outward action.

## Requirements

### Requirement: GitHub remote detection

The `github-init` component SHALL determine its status from the git `origin`
remote of the project root and SHALL track no files, record no source hash, and
take no outward action.

#### Scenario: Not a git repository

- **WHEN** `check` or `list` runs and the project root is not a git repository
- **THEN** `github-init` is classified **BLOCKED**
- **AND** BLOCKED takes precedence over MISSING

#### Scenario: No origin remote

- **WHEN** the project root is a git repository with no `origin` remote
- **THEN** `github-init` is classified **MISSING**

#### Scenario: Origin remote present

- **WHEN** the project root has an `origin` remote (on any host)
- **THEN** `github-init` is classified **OK**
- **AND** the remote is reported and never modified or removed

#### Scenario: No STALE or MODIFIED states

- **WHEN** `github-init` is classified for any project state
- **THEN** the only possible statuses are BLOCKED, MISSING, or OK
- **AND** STALE, MODIFIED, and MODIFIED+STALE are never produced for it

### Requirement: Print-only install

On `install`, `github-init` SHALL print the exact commands to create the GitHub
repository and push, and SHALL NOT execute any command that mutates local git
configuration or remote GitHub state.

#### Scenario: Install on a MISSING component prints gh command

- **WHEN** `install` processes `github-init` and it is MISSING
- **THEN** the tool prints `gh repo create <basename> --public --source=. --remote=origin --push`
- **AND** `<basename>` is the project directory basename
- **AND** the tool creates no repository, adds no remote, and pushes nothing

#### Scenario: Install prints a no-gh fallback

- **WHEN** `install` prints instructions for a MISSING `github-init`
- **THEN** it also prints a fallback path for when the `gh` CLI is absent:
  create the repository on github.com, then run `git remote add origin …` and
  `git push -u origin main`

#### Scenario: Install on an OK component writes nothing

- **WHEN** `install` processes `github-init` and it is OK
- **THEN** the tool reports it as satisfied and prints no commands

#### Scenario: Install on a BLOCKED component refuses

- **WHEN** `install` processes `github-init` and the project is not a git repository
- **THEN** the tool reports BLOCKED, prints how to initialize git, and writes nothing
