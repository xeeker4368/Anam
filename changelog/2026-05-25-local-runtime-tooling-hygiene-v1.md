# Local Runtime / Tooling Hygiene v1

## Summary

Added project-level hygiene so local runtime/tooling directories, including a local ComfyUI checkout and generated workspace artifacts, are not accidentally collected by pytest or staged for git.

## Files Changed

- `.gitignore`
- `pytest.ini`
- `changelog/2026-05-25-local-runtime-tooling-hygiene-v1.md`

## Behavior Changed

- Bare `python -m pytest` now discovers tests from `tests/` instead of recursing through the entire working tree.
- Pytest explicitly avoids local/runtime directories such as `ComfyUI/`, `.pyanam/`, `workspace/`, `data/prod/`, `backups/`, and `docs/reviews/`.
- Git ignore rules now cover local ComfyUI files, generated workspace outputs, local research/journal/upload artifacts, review notes, runtime logs, and backup/restore outputs.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest`
- `.pyanam/bin/python -m pytest tests -v`
- `npm --prefix frontend run build`
- `npm --prefix frontend run lint`
- `git diff --check`

## Known Limitations

- Ignore rules do not untrack files that were already tracked before this patch. Existing tracked runtime files, if dirty locally, still need a separate explicit cleanup decision before they can be removed from version control.
- This patch does not move local ComfyUI or generated artifacts out of the repository working tree.

## Follow-up Work

- Consider a separate repository cleanup patch if tracked runtime database/log files should be removed from git history or untracked going forward.

## Project Anam Alignment Check

- Does not assign the entity a name or visual identity.
- Does not alter prompts, guidance, memory, research, scheduler, Moltbook, web, image generation, or runtime behavior.
- Preserves the workspace/self-modification distinction by making local workspace outputs harder to accidentally collect or commit.
