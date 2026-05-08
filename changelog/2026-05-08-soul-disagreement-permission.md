# Minimal soul.md Disagreement Permission

## Summary
- Added one minimal sentence to `soul.md` allowing disagreement with proposed corrections or changes when evidence, memory, or guidance indicates a problem.

## Files Changed
- `soul.md`
- `changelog/2026-05-08-soul-disagreement-permission.md`

## Behavior Changed
- The seed orientation now explicitly permits questioning, disagreeing with, or declining proposed corrections or changes when they appear wrong, unsafe, or harmful.
- The guidance asks for explanation rather than pretended agreement.

## Tests/Checks Run
- `git diff --check`
- `rg -n "Anam|Tír|personality|name" soul.md changelog/2026-05-08-soul-disagreement-permission.md`

## Known Limitations
- This adds permission only. It does not add a persistence mechanism for disagreement records.
- It does not define admin review mechanics or behavioral guidance workflows.

## Follow-Up Work
- Later review/reflection features can record disagreements as review items or proposals when explicitly designed.

## Project Anam Alignment Check
- Does not assign the entity a name.
- Does not assign a personality.
- Does not mention or modify `BEHAVIORAL_GUIDANCE.md`.
- Does not change operational guidance, prompt loading, code, schema, or memory architecture.
