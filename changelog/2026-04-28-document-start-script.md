# Document Start Script

## Summary

Documented the manually-created `start.sh` script in the project changelog.

## Files Changed

- `changelog/2026-04-28-document-start-script.md`

## Behavior Changed

- No application behavior changed.
- `start.sh` was inspected but not modified.

## Tests/Checks Run

- Inspected `start.sh` for obvious syntax issues.

## Known Limitations

- `start.sh` currently activates `.venv` only if present and otherwise relies on `python` and `npm` being available on `PATH`.
- The script installs frontend dependencies if `frontend/node_modules` is missing.
- The script starts the backend and Vite frontend as child processes and stops both on exit.

## Follow-up Work

- Consider a separate approved patch if the script should support `.pyanam` explicitly.
- Consider documenting expected local startup commands in a README or operator note.

## Project Anam Alignment Check

- Did not modify application behavior.
- Did not rename `tir/`.
- Did not modify `soul.md`.
- Did not touch `data/prod` files.
- Did not touch `.DS_Store`.
