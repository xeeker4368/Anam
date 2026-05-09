# Reflection Journal Voice + Entity Context Tuning v1

## Summary

Tuned the manual reflection journal prompt so generated journals read more like
the AI's own journal space and less like an external audit report.

## Files Changed

- `tir/engine/context.py`
- `tir/reflection/journal.py`
- `tests/test_reflection_journal.py`
- `changelog/2026-05-08-reflection-journal-voice-context-tuning.md`

## Behavior Changed

- Reflection journal generation now uses a short journal-space system prompt.
- Journal model input includes `soul.md` as current seed context.
- Journal model input includes active reviewed behavioral guidance using the
  same runtime extraction behavior.
- The journal prompt no longer repeats compliance-heavy identity/personality
  guardrail wording.
- Dry-run, write, path, overwrite, and file-only storage behavior are unchanged.

## Tests/Checks Run

- Pending in this patch.

## Known Limitations

- Relevant memory retrieval is still deferred.
- Today's material still includes conversations/messages and behavioral guidance
  activity only.
- Tool traces, artifacts, review queue activity, open-loop activity, generated
  files, and other actions are not included yet.

## Follow-Up Work

- Design bounded relevant memory retrieval for reflection journals.
- Build a daily activity packet that includes tool calls, artifacts, review
  queue activity, open loops, uploads, generated files, and other actions.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not add fixed personality.
- Uses existing seed and reviewed guidance context rather than adding a new
  identity layer.
- Does not mutate `BEHAVIORAL_GUIDANCE.md`, `OPERATIONAL_GUIDANCE.md`, or
  `soul.md`.
- Keeps reflection separate from behavioral guidance proposal creation.
