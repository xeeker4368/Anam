# Reflection Journal Source Framing

## Summary

Updated retrieved reflection journal memory labels to make journal source framing clearer without discounting journal content.

## Files Changed

- `tir/engine/context.py`
- `tests/test_context.py`
- `docs/PROMPT_INVENTORY.md`
- `changelog/2026-05-09-reflection-journal-source-framing.md`

## Behavior Changed

- Retrieved journal chunks now use the label:
  `[Your reflection journal entry from <date> — personal reflection]`
- Non-journal retrieved memory labels are unchanged.
- Journal writing, indexing, metadata, and retrieval ranking are unchanged.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `.pyanam/bin/python -m pytest tests/test_prompt_inventory.py -v`
- `.pyanam/bin/python scripts/extract_prompt_inventory.py --root tir --output docs/PROMPT_INVENTORY.md`
- `git diff --check`

## Known Limitations

- This is label-only source framing. It does not add additional explanatory prose or epistemic metadata.

## Follow-Up Work

- Observe whether the lighter label is enough to prevent over-literal handling of expressive journal language.
- Add a once-per-section explanatory line only if future behavior shows it is needed.

## Project Anam Alignment Check

- Does not assign the entity a name or personality.
- Preserves journals as experience while clarifying their source type.
- Does not change guidance files, journal generation, indexing, or retrieval ranking.
