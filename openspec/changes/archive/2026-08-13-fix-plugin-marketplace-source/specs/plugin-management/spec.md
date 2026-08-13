## ADDED Requirements

### Requirement: Recorded marketplace source is authoritative
Each plugin's recorded marketplace source in `scaffold_base/manifest.yaml` SHALL identify the marketplace the plugin is actually installed from, and the install command SHALL register that source. A source that is self-consistent between `manifest.yaml` and the generated `plugins.json` but does not resolve to the plugin's real marketplace is a defect, even though the drift guard passes.

#### Scenario: source resolves to the real marketplace
- **WHEN** the scaffold installs a wishlisted plugin whose id is `<name>@<marketplace>`
- **THEN** the marketplace registered by the install command resolves to the repository the plugin actually ships from, not merely a repository named consistently across `manifest.yaml` and `plugins.json`

#### Scenario: caveman and superpowers sources are correct
- **WHEN** the base manifest is read for the `caveman@caveman` and `superpowers@claude-plugins-official` plugins
- **THEN** their sources are `JuliusBrussee/caveman` and `anthropics/claude-plugins-official` respectively
