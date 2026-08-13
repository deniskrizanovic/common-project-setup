## Why

`scaffold_base/manifest.yaml` records the wrong marketplace source for two base plugins: `caveman@caveman` points at `dk-krizanovic/caveman` but the plugin actually ships from `JuliusBrussee/caveman`, and `superpowers@claude-plugins-official` points at `anthropics/claude-plugins` but the real marketplace repo is `anthropics/claude-plugins-official`. On a fresh machine `scaffold.py install` would run `claude plugin marketplace add dk-krizanovic/caveman` (a repo that is not the plugin's marketplace), so the install fails or wires the wrong source. The drift guard never catches this because it only checks that the generated `plugins.json` matches the manifest — both are wrong in the same way.

## What Changes

- Correct the `source:` values in `scaffold_base/manifest.yaml`:
  - `caveman@caveman`: `dk-krizanovic/caveman` becomes `JuliusBrussee/caveman`
  - `superpowers@claude-plugins-official`: `anthropics/claude-plugins` becomes `anthropics/claude-plugins-official`
- Regenerate `scaffold_base/plugins.json` from the corrected manifest (`scaffold.py gen`).
- Add a spec requirement that the recorded marketplace source for a plugin MUST resolve to the marketplace the plugin is actually installed from — closing the gap where a wrong-but-self-consistent source passes the drift guard.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `plugin-management`: adds a requirement that each plugin's recorded `marketplaceSource` resolve to the real marketplace the plugin ships from, and that the install command register that correct source.

## Impact

- `scaffold_base/manifest.yaml`: two `source:` value corrections.
- `scaffold_base/plugins.json`: regenerated `marketplaceSource` fields for both plugins.
- No code change to `scaffold.py`; behavior fix is entirely in the data the generator reads.
- Fresh-machine `scaffold.py install` now registers the correct marketplaces for `caveman` and `superpowers`.
