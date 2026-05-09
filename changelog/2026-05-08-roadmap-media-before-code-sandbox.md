# Roadmap Media Before Code Sandbox

## Summary

Updated the roadmap to make media/generation the current Phase 4 priority and code/sandbox foundations the current Phase 5 priority without renumbering the historical roadmap.

## Files Changed

- `ROADMAP.md`

## Behavior Changed

- No runtime behavior changed.
- Added a current-priority phase reorder section.
- Moved Pepper's Ghost to later optional display/embodiment experiments.
- Updated near-term build order so media/generation comes before code sandbox and self-modification foundations.

## Tests/Checks Run

- `git diff --check`
- `rg -n "Pepper|Ghost|Phase 4|Phase 5|Avatar|Media and Generation|Code and Sandbox" ROADMAP.md PROJECT_STATE.md DESIGN_RATIONALE.md`

## Known Limitations

- The historical roadmap phase numbering remains unchanged, so the new section is an explicit current-priority overlay rather than a global renumbering.

## Follow-Up Work

- Revisit phase numbering only if a full roadmap rewrite is explicitly approved.
- Add implementation plans for image generation artifacts and generated document artifacts.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not assign a fixed personality.
- Keeps avatar exploration screen-first and tied to emergent self-presentation rather than a name requirement.
- Keeps Pepper's Ghost optional rather than primary.
