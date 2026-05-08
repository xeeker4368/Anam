# Behavioral Guidance Proposal Model v1

## Summary

Added working-db storage, service helpers, and admin CLI commands for AI-proposed behavioral guidance proposals.

## Files Changed

- `BEHAVIORAL_GUIDANCE.md`
- `tir/memory/db.py`
- `tir/behavioral_guidance/__init__.py`
- `tir/behavioral_guidance/service.py`
- `tir/admin.py`
- `tests/test_behavioral_guidance.py`
- `tests/test_admin.py`
- `tests/test_context.py`
- `changelog/2026-05-07-behavioral-guidance-proposals.md`

## Behavior Changed

- Working DB initialization now creates `behavioral_guidance_proposals`.
- Behavioral guidance proposals use `proposal_text` for one atomic proposed addition, removal, or revision.
- Proposal records do not include `created_by` or `proposal_created_by`; proposals are AI-proposed by definition.
- Approval, rejection, application, and archive decisions require `reviewed_by_role=admin`.
- Rejected proposals require `review_decision_reason` and remain visible/listable.
- Application fields are recorded in schema/service, but no file mutation is performed.
- Admin CLI can add, list, and update proposal review status.

## Tests/Checks Run

- `.pyanam/bin/python -m pytest tests/test_behavioral_guidance.py -v`
- `.pyanam/bin/python -m pytest tests/test_admin.py -v`
- `.pyanam/bin/python -m pytest tests/test_context.py -v`
- `git diff --check`

## Known Limitations

- V1 enforces admin decisions using role text only. Future enforcement should verify `reviewed_by_user_id` belongs to an admin user.
- CLI insertion records AI proposals but cannot prove the proposal originated from an AI review pass.
- Atomicity is policy-enforced, not automatically detected from proposal text.
- `BEHAVIORAL_GUIDANCE.md` is not loaded into runtime context and is not automatically modified.

## Follow-up Work

- Add verified admin-user enforcement once auth/role context is consistently available.
- Add an explicit apply command in a later patch if approved.
- Add AI review/dream proposal generation in a later, separately approved patch.

## Project Anam Alignment Check

- Does not assign the entity a name.
- Does not call the entity Anam or Tír.
- Does not assign a fixed personality.
- Does not modify `soul.md`.
- Preserves raw experience as the source of proposals.
- Keeps guidance review/admin application separate from automatic self-modification.
