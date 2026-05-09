# Daily Guidance Review Local-Time Message-Activity Window

## Summary

Updated the manual daily behavioral guidance review command so operator-facing dates use the system local day while database queries remain UTC. Conversation selection now uses message activity timestamps rather than conversation start time.

## Files Changed

- `tir/behavioral_guidance/review.py`
- `tir/admin.py`
- `tests/test_behavioral_guidance_review.py`
- `tests/test_admin.py`

## Behavior Changed

- `behavioral-guidance-review-day --date YYYY-MM-DD` now means local/system date.
- Default date is the current local/system date.
- Local day windows are converted to UTC before querying SQLite.
- `--since` requires a timezone-aware ISO timestamp or trailing `Z`.
- Daily review selects conversations with at least one message inside the UTC window.
- Conversation results are deduplicated and sorted by first message timestamp inside the window.
- Admin output includes local date, timezone, local offset, and UTC query bounds for date mode.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance_review.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `git diff --check`

## Known Limitations

- Timezone display is best-effort and may be a fixed-offset abbreviation instead of an IANA name.
- `--conversation-id` bypasses date/window metadata by design.
- Timestamp comparisons rely on existing UTC ISO timestamp consistency.

## Follow-Up Work

- Add an explicit `--timezone` option only if operators need to review days for a timezone other than the host system timezone.
- Consider richer reporting for first activity timestamps in admin output.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not assign a fixed personality.
- Keeps review manual and admin-triggered.
- Does not modify `BEHAVIORAL_GUIDANCE.md`, `soul.md`, or runtime prompt loading.
- Preserves raw conversation/message activity as the source boundary.
