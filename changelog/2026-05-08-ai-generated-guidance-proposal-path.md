# First AI-Generated Behavioral Guidance Proposal Path

## Summary

Added a manual admin-triggered conversation review path that asks the configured local model to generate AI-proposed behavioral guidance candidates from one selected chat conversation.

## Files Changed

- `tir/behavioral_guidance/review.py`
- `tir/engine/ollama.py`
- `tir/admin.py`
- `tests/test_behavioral_guidance_review.py`
- `tests/test_admin.py`

## Behavior Changed

- Added `tir.admin behavioral-guidance-review-conversation CONVERSATION_ID`.
- Default mode is dry-run and writes nothing.
- `--write` persists validated proposals as `status=proposed`.
- Review uses only the selected chat conversation transcript.
- Generated proposals are validated before any writes occur.
- Reviewed/admin decision fields remain empty.
- `BEHAVIORAL_GUIDANCE.md` is not read, loaded, or modified.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance_review.py -v`
- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- Semantic atomicity is enforced by prompt constraints and admin review, not a perfect automatic classifier.
- The command depends on the configured local Ollama model producing valid JSON.
- The path reviews only chat conversations, not iMessage, tool traces, artifacts, or debug logs.

## Follow-Up Work

- Add richer review evidence handling if future review passes include tool traces or artifacts.
- Consider structured-output retry behavior if malformed JSON is common.
- Keep application to `BEHAVIORAL_GUIDANCE.md` as a separate admin-only patch.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not assign a fixed personality.
- Preserves raw conversation experience as the source.
- Creates traceable proposal records linked to source conversation/message context.
- Does not modify runtime guidance files or enable self-modification.
