# Research Open-Loop Low-Signal Filter Fix

Fixed research open-loop extraction so generated no-op placeholder text is not
treated as an open-loop candidate.

- Broadened deterministic low-signal filtering for generated phrases such as
  "No open questions were identified." and
  "No suggested follow-ups were identified."
- Added coverage for research-run style no-op notes.
- Confirmed real open questions and follow-up items still produce candidates.
- Confirmed Suggested Review Items remain outside research open-loop extraction.
