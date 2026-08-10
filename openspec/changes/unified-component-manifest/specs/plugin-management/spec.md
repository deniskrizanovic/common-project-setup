## MODIFIED Requirements

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
