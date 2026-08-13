## 1. Git gate

- [x] 1.1 Add a `needs_git` flag to the component model, mirroring `needs_openspec`
- [x] 1.2 Add a git-repository detector (project root is a git work tree)
- [x] 1.3 Wire BLOCKED classification for `needs_git` components, with precedence over MISSING

## 2. github-init component

- [x] 2.1 Add an `origin`-remote detector (`git remote get-url origin`) returning present/absent
- [x] 2.2 Register `github-init` in `build_registry()` with no tracked files, `needs_git=True`
- [x] 2.3 Classify: not-git → BLOCKED, no origin → MISSING, origin present → OK; never STALE/MODIFIED

## 3. Print-only install

- [x] 3.1 On MISSING, print `gh repo create <basename> --public --source=. --remote=origin --push` using the project dir basename
- [x] 3.2 Print the no-gh fallback (create on github.com, then `git remote add origin …` + `git push -u origin main`)
- [x] 3.3 On OK, report satisfied and print nothing; on BLOCKED, print how to init git; ensure install runs no outward command

## 4. Tests & docs

- [x] 4.1 Test classification: non-git repo → BLOCKED, git w/o origin → MISSING, git w/ origin → OK
- [x] 4.2 Test install prints the exact commands and mutates no git/remote state
- [x] 4.3 Update README Components section to document `github-init` (print-only, needs_git gate)
