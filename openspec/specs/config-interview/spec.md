# config-interview Specification

## Purpose
Provide a guided interview during the scaffold `install` flow that fills the
`context:` block of `openspec/config.yaml` from project-specific answers,
rewriting only that block while preserving the rest of the file.

## Requirements

### Requirement: Guided context interview
The scaffold SHALL provide a `config-interview` component that, during the
interactive `install` flow, prompts the user for project-specific context and
rewrites the `context:` block of `openspec/config.yaml` from the answers. The
interview SHALL run only after `config-baseline` has placed the template on
disk, and SHALL read its answers through the same injectable `reader` used by
the per-component picker.

#### Scenario: interview fills the context block
- **GIVEN** a project whose `openspec/config.yaml` holds the generic template `context:` block
- **WHEN** the user selects the `config-interview` step during `install` and answers the prompts
- **THEN** the `context:` block is rewritten from the answers and the template placeholder sentinel no longer appears in the file

#### Scenario: prompts cover the baseline fields
- **GIVEN** the `config-interview` step is running during `install`
- **WHEN** the interview collects answers
- **THEN** it prompts at least for Purpose, Language/runtime, Frameworks/libraries, Data store, and Testing

#### Scenario: a blank field aborts without writing
- **GIVEN** the `config-interview` step is collecting answers
- **WHEN** the user leaves any field blank
- **THEN** the interview writes nothing, reports which fields were blank, and leaves the placeholder sentinel in place so status stays MISSING

### Requirement: In-place rewrite preserves the rest of the file
The interview SHALL rewrite only the `context:` block and SHALL leave the
`rules:` block, the `schema:` line, and existing comments intact.

#### Scenario: rules and comments survive the rewrite
- **GIVEN** a `openspec/config.yaml` containing a `rules:` block and comments alongside the template `context:` block
- **WHEN** the `config-interview` step rewrites the `context:` block
- **THEN** the `rules:` block, the `schema:` line, and the surrounding comments are unchanged

### Requirement: MISSING-or-OK drift model
The scaffold SHALL classify `config-interview` as OK when the `context:` block
no longer contains the template placeholder sentinel, and as MISSING while the
sentinel survives. It SHALL NOT classify `config-interview` as STALE or
MODIFIED, because the block has no tracked source hash.

#### Scenario: customized context reports OK
- **GIVEN** a project whose `context:` block has been filled by the interview
- **WHEN** `check` runs against the project
- **THEN** `config-interview` is classified OK and no changes are made to disk

#### Scenario: placeholder context reports MISSING
- **GIVEN** a project whose `context:` block still contains the template placeholder sentinel
- **WHEN** `check` runs against the project
- **THEN** `config-interview` is classified MISSING and offered for install

#### Scenario: absent or unlocatable context block reports MISSING
- **GIVEN** a project whose `openspec/config.yaml` has no locatable `context:` block scalar (deleted, malformed, or duplicated)
- **WHEN** `check` runs against the project
- **THEN** `config-interview` is classified MISSING rather than a false OK, because the interview cannot rewrite an unlocatable block

### Requirement: Re-run always offers to re-interview
During `install`, the `config-interview` step SHALL always offer an
`[i]nterview / [s]kip` choice, even when the context block is already
customized, so the context can be revised on a later run.

#### Scenario: filled context is still offered
- **GIVEN** a project whose `context:` block has already been filled by a prior interview
- **WHEN** the user runs `install` again and reaches the `config-interview` step
- **THEN** the step offers `[i]nterview / [s]kip` rather than reporting it current and skipping
