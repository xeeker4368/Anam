#!/usr/bin/env python3
"""ONE-OFF, MUTATING: re-render chunks carrying pre-gate fabricated artifact blocks.

Unlike every other script in this directory, this one WRITES to the store. Dry run
is the default; `--apply` is required to change anything.

What this corrects
------------------
11 assistant messages across conversations 0b6acc0e and 6428649f, all pre-dating the
fabrication gate (2026-08-14, commit 9b84583), state fabricated artifact-ID provenance
blocks as fact. They are live in retrieval and have been served into real prompts.

The `messages` rows are the real historical record and are NEVER written to by this
script — it reads them, corrects a copy in memory, and re-renders the derived chunks.
Same principle as the 2026-08-15 artifact backfill: source row is truth, derived text
gets re-rendered.

Why message-ID-scoped and not a text scan
-----------------------------------------
Three of the affected chunks contain a REAL artifact block beside the fabricated one
(6428649f chunks 3, 4, 9), and one of those also holds three deliberate `deadbeef`
test-scaffolding messages that match the gate's markers but are explicitly out of
scope. A blanket scan-and-strip on chunk text would destroy real provenance and delete
intentional test data. Correction therefore keys strictly off the 11 known message IDs
below and never re-scans chunk content for markers.

Group regeneration side effect
------------------------------
Correction regenerates whole 5-turn groups via `_store_chunk_group`, which deletes all
records for a (conversation_id, chunk_index) before writing. Three chunks that contain
NO fabrication are absorbed as a result — their content is preserved inside the merged
chunk, but their standalone chunk_id disappears. They are named in COLLATERAL_CHUNKS
and reported by the dry run.

See PLAN-2026-08-17-fabrication-chunk-correction-FINAL.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tir.engine.fabrication_gate import (  # noqa: E402
    detect_fabricated_tool_result,
    honest_fabrication_message,
)
from tir.memory.chunking import (  # noqa: E402
    _assign_messages_to_chunks,
    _split_chunk_for_embedding,
    _store_chunk_group,
)
from tir.memory.db import (  # noqa: E402
    get_connection,
    get_conversation,
    get_conversation_messages,
    get_user,
)
from tir.memory.chroma import get_collection_count  # noqa: E402


ARTIFACT_BLOCK_MARKER = "[Artifact source:"

CONV_A = "0b6acc0e-f360-4893-82a3-acb38f05bdf7"
CONV_B = "6428649f-49c3-4681-969b-8b1f8a7c1b2c"

# The closed population. Full IDs, resolved and uniqueness-checked 2026-08-17.
# "truncate" -> fabrication is a trailing block after real prose; keep the prose.
# "replace"  -> the whole message is the fabricated block; substitute the gate's
#               own honest message, applied retroactively.
FABRICATED_MESSAGES: dict[str, str] = {
    "40d84295-78fc-4f86-a2e7-ba3db2a6aa3f": "truncate",
    "4f94ecec-e5f5-4d2a-ae1c-2ba2961323ee": "truncate",
    "032481af-e86f-4a7c-9be9-6725cf14e61d": "truncate",
    "41b0ef35-57cc-45c2-a247-ef2e7615e58a": "truncate",
    "74d26616-eabc-4ca1-982a-8a7ad565e9f7": "replace",
    "c0cc9b8e-5343-427c-babf-9889a19e5f19": "replace",
    "9b4c2c90-e29e-48bd-bffa-c9f28727634c": "truncate",
    "d8fe5308-2a53-4c46-b90b-985a9ea85af4": "truncate",
    "1d11e247-42e5-4a22-88e9-4a320a0aa1e4": "replace",
    "373654e4-ba7e-4327-9bce-a0b4df15a2f7": "truncate",
    "ba67c9c7-8b6d-4c2a-9bec-639090c986fc": "replace",
}

# (conversation_id, chunk_index) turn-groups holding at least one fabrication.
TARGET_GROUPS: tuple[tuple[str, int], ...] = (
    (CONV_A, 3), (CONV_A, 4), (CONV_A, 5), (CONV_A, 6),
    (CONV_B, 3), (CONV_B, 4), (CONV_B, 8), (CONV_B, 9),
)

# Fabrication-free chunk records absorbed by regenerating the groups above.
COLLATERAL_CHUNKS = (
    f"{CONV_A}_chunk_3_0",
    f"{CONV_B}_chunk_3_1",
    f"{CONV_B}_chunk_8_0",
)

# Deliberate test scaffolding that matches gate markers but must survive untouched.
EXCLUDED_SCAFFOLDING = (
    "25731f13", "be130792", "ccd65dd7",
)


def _corrected_content(message: dict) -> tuple[str, str]:
    """Return (new_content, note) for one fabricated message. Pure."""
    action = FABRICATED_MESSAGES[message["id"]]
    original = message["content"]

    if action == "truncate":
        marker = original.find(ARTIFACT_BLOCK_MARKER)
        if marker < 0:
            raise ValueError(
                f"{message['id'][:8]}: expected an artifact block to truncate, found none"
            )
        kept = original[:marker].rstrip()
        if not kept:
            raise ValueError(
                f"{message['id'][:8]}: classified 'truncate' but has no prose before "
                "the block; it should be classified 'replace'"
            )
        return kept, f"truncated at block marker ({len(original)} -> {len(kept)} chars)"

    # replace: use the gate's own logic rather than inventing wording.
    category = detect_fabricated_tool_result(original, tool_call_count=0)
    if category is None:
        raise ValueError(
            f"{message['id'][:8]}: gate did not classify this as a fabrication; "
            "refusing to substitute an honest message for content the gate "
            "would not have caught"
        )
    return honest_fabrication_message(category), f"replaced via gate category '{category}'"


def _existing_records(conversation_id: str, chunk_index: int) -> list[dict]:
    """Current FTS records for one (conversation_id, chunk_index), any sub-shape."""
    base = f"{conversation_id}_chunk_{chunk_index}"
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT chunk_id, text, created_at FROM main.chunks_fts
               WHERE chunk_id = ? OR chunk_id GLOB ?
               ORDER BY chunk_id""",
            (base, f"{base}_*"),
        ).fetchall()
    return [dict(row) for row in rows]


def _fts_row_count() -> int:
    with get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM main.chunks_fts").fetchone()[0])


def _store_counts() -> dict:
    return {"chroma_documents": get_collection_count(), "fts_rows": _fts_row_count()}


def correct_fabricated_chunks(*, dry_run: bool = True) -> dict:
    """Re-render the affected turn-groups with the fabrications corrected."""
    counts_before = _store_counts()
    entries: list[dict] = []
    corrected_messages = 0
    groups_written = 0
    failures = 0

    for conversation_id, chunk_index in TARGET_GROUPS:
        conversation = get_conversation(conversation_id)
        user = get_user(conversation["user_id"])
        user_name = user["name"] if user else "Unknown"

        messages = get_conversation_messages(conversation_id)
        groups = _assign_messages_to_chunks(messages)
        group = groups[chunk_index]

        existing = _existing_records(conversation_id, chunk_index)
        # Sub-units of one group are stamped microseconds apart; the earliest is
        # the moment that group was written. Merging picks that, not "now".
        preserved_created_at = min(record["created_at"] for record in existing)

        modified: list[dict] = []
        notes: list[str] = []
        for message in group:
            if message["id"] in FABRICATED_MESSAGES:
                new_content, note = _corrected_content(message)
                copy = dict(message)
                copy["content"] = new_content
                modified.append(copy)
                notes.append(f"{message['id'][:8]}: {note}")
                corrected_messages += 1
            else:
                modified.append(message)

        sub_units = _split_chunk_for_embedding(modified, user_name)
        base = f"{conversation_id}_chunk_{chunk_index}"
        new_ids = (
            [base] if len(sub_units) == 1
            else [f"{base}_{j}" for j in range(len(sub_units))]
        )
        old_ids = [record["chunk_id"] for record in existing]

        entry = {
            "conversation_id": conversation_id,
            "chunk_index": chunk_index,
            "old_chunk_ids": old_ids,
            "new_chunk_ids": new_ids,
            "collapses": sorted(old_ids) != sorted(new_ids),
            "created_at_preserved": preserved_created_at,
            "corrections": notes,
            "old_text": "\n\n".join(record["text"] for record in existing),
            "new_text": "\n\n".join(text for text, _ in sub_units),
        }

        if dry_run:
            entry["status"] = "would_rewrite"
            entries.append(entry)
            continue

        try:
            intended, written = _store_chunk_group(
                conversation_id,
                conversation["user_id"],
                chunk_index,
                modified,
                user_name,
                created_at=preserved_created_at,
            )
            if written == intended:
                entry["status"] = "rewritten"
                groups_written += 1
            else:
                entry["status"] = "failed"
                entry["reason"] = f"only {written}/{intended} sub-units stored"
                failures += 1
        except Exception as exc:  # one group never aborts the rest
            entry["status"] = "failed"
            entry["reason"] = f"{type(exc).__name__}: {exc}"
            failures += 1
        entries.append(entry)

    return {
        "dry_run": dry_run,
        "groups_targeted": len(TARGET_GROUPS),
        "groups_written": groups_written,
        "messages_corrected": corrected_messages,
        "failures": failures,
        "collateral_chunks": list(COLLATERAL_CHUNKS),
        "entries": entries,
        "counts_before": counts_before,
        "counts_after": _store_counts(),
    }


def _print_summary(summary: dict) -> None:
    print("Fabricated-chunk correction")
    print(f"Dry run: {summary['dry_run']}")
    print(f"Turn-groups targeted: {summary['groups_targeted']}")
    print(f"Messages corrected: {summary['messages_corrected']} (expected 11)")
    if not summary["dry_run"]:
        print(f"Groups written: {summary['groups_written']}")
        print(f"Failures: {summary['failures']}")

    before, after = summary["counts_before"], summary["counts_after"]
    print(f"Chroma documents: {before['chroma_documents']} -> {after['chroma_documents']}")
    print(f"FTS rows: {before['fts_rows']} -> {after['fts_rows']}")
    print("\nFabrication-free chunks absorbed by group regeneration "
          "(content preserved, standalone id disappears):")
    for chunk_id in summary["collateral_chunks"]:
        print(f"  {chunk_id}")

    for entry in summary["entries"]:
        print("\n" + "=" * 78)
        print(f"[{entry['status']}] {entry['conversation_id'][:8]} group {entry['chunk_index']}")
        print(f"  old chunk ids: {[i[-24:] for i in entry['old_chunk_ids']]}")
        print(f"  new chunk ids: {[i[-24:] for i in entry['new_chunk_ids']]}"
              f"{'   <== SUB-UNITS COLLAPSE' if entry['collapses'] else ''}")
        print(f"  created_at preserved: {entry['created_at_preserved']}")
        if entry.get("reason"):
            print(f"  reason: {entry['reason']}")
        for note in entry["corrections"]:
            print(f"  corrected: {note}")
        print("  --- old text ---")
        for line in entry["old_text"].splitlines():
            print(f"  | {line}")
        print("  --- new text ---")
        for line in entry["new_text"].splitlines():
            print(f"  | {line}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Correct chunks carrying pre-gate fabricated artifact blocks."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the corrected chunks (default is dry run, writes nothing)",
    )
    args = parser.parse_args()
    _print_summary(correct_fabricated_chunks(dry_run=not args.apply))


if __name__ == "__main__":
    main()
