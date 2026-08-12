## 1. Component wiring

- [x] 1.1 Add a shared placeholder sentinel constant and refactor `_config_is_real` to reference it
- [x] 1.2 Extend `FileComponent` (or its handling) to carry an optional `filler` callable
- [x] 1.3 Register `config-interview` in `build_registry()` after `config-baseline`, with `satisfied=_context_is_customized` and a `filler`

## 2. Interview + rewrite

- [x] 2.1 Implement `_context_is_customized(root)` predicate (True when the sentinel is gone)
- [x] 2.2 Implement the interview `filler` prompting Purpose, Language/runtime, Frameworks/libraries, Data store, Testing via the injectable `reader`
- [x] 2.3 Test the interview fills the block from scripted `reader` answers and clears the sentinel
- [x] 2.4 Implement the in-place `context:` block rewriter that preserves `rules:`, `schema:`, and comments (abort with a clear message if the block can't be located)
- [x] 2.5 Test `rules:`, `schema:`, and comments survive the rewrite

## 3. Install-loop integration

- [x] 3.1 In `cmd_install`, run the `filler` for a `FileComponent` that has one, instead of copying a template
- [x] 3.2 Always offer `[i]nterview / [s]kip` for `config-interview`, even when status is OK/customized
- [x] 3.3 Ensure `check`/`list` classify `config-interview` as MISSING or OK only and write nothing
- [x] 3.4 Test drift: placeholder → MISSING, customized → OK; and re-run offers interview on an OK component

## 4. Docs

- [x] 4.1 Update README Components section to document `config-interview`
