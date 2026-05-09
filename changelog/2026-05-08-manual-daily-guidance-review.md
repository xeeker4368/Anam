# Manual Daily Behavioral Guidance Review v1

## Summary

Added a manual admin command that reviews a bounded day/window or selected set of chat conversations and generates AI-proposed behavioral guidance candidates for admin review.

## Files Changed

- `tir/behavioral_guidance/review.py`
- `tir/admin.py`
- `tests/test_behavioral_guidance_review.py`
- `tests/test_admin.py`

## Behavior Changed

- Added `tir.admin behavioral-guidance-review-day`.
- The command can select conversations by UTC date, ISO `--since`, or repeated `--conversation-id`.
- The command includes active and ended chat conversations, sorted oldest-first.
- Conversations with fewer than three messages are skipped.
- Dry-run mode writes nothing.
- Write mode inserts validated proposals as `status=proposed`.
- Duplicate conversation reviews are skipped by default when prior `conversation_review_v1` proposals exist.
- `--allow-duplicates` permits deliberate reruns.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance_review.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- Duplicate detection is Python-side and based on proposal metadata, not a database uniqueness constraint.
- The command reviews chat conversations only.
- Semantic duplicate proposals across different conversations are not deduplicated.

## Follow-Up Work

- Consider review summaries or evidence compaction for longer conversations.
- Consider richer admin reporting once review batches become common.
- Keep scheduled/background review as a separate explicitly approved patch.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not assign a fixed personality.
- Preserves raw conversation experience as source material for proposals.
- Keeps proposal generation separate from admin review and file application.
- Does not modify `BEHAVIORAL_GUIDANCE.md`, `soul.md`, or runtime prompt loading.
