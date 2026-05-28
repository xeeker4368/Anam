# Local Runtime / Tooling Hygiene v1

## Summary

Confirmed and tightened local runtime/tooling hygiene so raw project test runs do not recurse into local tool checkouts or runtime output directories now that ComfyUI and generated media artifacts may live inside the working tree.

## Files Changed

- `pytest.ini`
- `changelog/2026-05-27-local-runtime-tooling-hygiene-v1.md`

## Behavior Changed

- Pytest now explicitly excludes `config/comfyui` in addition to the existing exclusions for `ComfyUI`, `.pyanam`, `node_modules`, `frontend/dist`, `backups`, `data/prod`, `workspace`, and `docs/reviews`.
- Existing `.gitignore` rules already ignore local ComfyUI, local workflow config, runtime data, generated workspace artifacts, backups, logs, environment files, and local review notes.

## Tests/Checks Run

- Pending implementation verification.

## Known Limitations

- `data/prod/archive.db`, `data/prod/working.db`, `data/prod/chromadb/chroma.sqlite3`, and `data/prod/tir.log` are already tracked by git. `.gitignore` does not hide modifications to tracked files. Removing them from the index should be a separate explicitly approved patch if desired.

## Follow-Up Work

- Consider a dedicated "untrack runtime data" patch using a careful `git rm --cached` plan for already tracked runtime DB/log files.

## Project Anam Alignment Check

- This patch does not assign the entity a name, avatar, identity, or personality.
- This patch does not alter prompts, guidance, model config, memory architecture, scheduler behavior, research behavior, Moltbook/web behavior, image generation behavior, or runtime semantics.
- This patch preserves local runtime/generated files as uncommitted machine-local state.
