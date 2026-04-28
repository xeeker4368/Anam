# Root Gitignore Repo Hygiene

## Summary

Added a root-level `.gitignore` to prevent local, runtime, dependency, and generated files from appearing in future git status output.

## Files Changed

- `.gitignore`
- `changelog/2026-04-28-root-gitignore-repo-hygiene.md`

## Behavior Changed

- No application behavior changed.
- Git now ignores common local/generated paths and files:
  - macOS metadata
  - Python caches
  - local virtual environments
  - Node dependencies
  - frontend build output
  - production runtime data
  - SQLite database sidecar files
  - logs
  - environment files

## Tests/Checks Run

- `git check-ignore -v --no-index .DS_Store tests/__pycache__/test_db.cpython-314-pytest-9.0.3.pyc .pytest_cache .pyanam/bin/python frontend/node_modules data/prod/archive.db data/prod/tir.log .env .env.local frontend/dist/index.html`
- `git ls-files -ci --exclude-standard`
- `git diff --check -- .gitignore changelog/2026-04-28-root-gitignore-repo-hygiene.md`

## Known Limitations

- Ignore rules do not remove files that are already tracked by git.
- Already-tracked runtime/generated files will continue to appear in git status until a separate approved cleanup untracks them.

## Follow-up Work

- In a separate approved patch, consider removing tracked generated/runtime files from the git index while preserving local copies.
- Review whether `start.sh` should remain tracked or be documented as a local helper.

## Project Anam Alignment Check

- Did not change application behavior.
- Did not rename `tir/`.
- Did not modify `soul.md`.
- Did not add runtime features.
- Did not touch `data/prod` contents.
