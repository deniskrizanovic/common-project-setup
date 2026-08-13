## 1. Correct manifest sources

- [x] 1.1 In `scaffold_base/manifest.yaml`, change `caveman@caveman` source from `dk-krizanovic/caveman` to `JuliusBrussee/caveman`
- [x] 1.2 In `scaffold_base/manifest.yaml`, change `superpowers@claude-plugins-official` source from `anthropics/claude-plugins` to `anthropics/claude-plugins-official`

## 2. Regenerate artifacts

- [x] 2.1 Run `python3 scaffold.py gen` to rewrite `scaffold_base/plugins.json`
- [x] 2.2 Confirm `plugins.json` `marketplaceSource` fields now read `JuliusBrussee/caveman` and `anthropics/claude-plugins-official`

## 3. Verify

- [x] 3.1 Run `python3 scaffold.py drift` and confirm it exits 0 (manifest and generated artifacts in sync)
- [x] 3.2 Run `uv run pytest -q` and confirm the suite passes
- [x] 3.3 Spot-check `plugin_install_commands` output for `caveman@caveman` registers `claude plugin marketplace add JuliusBrussee/caveman`
