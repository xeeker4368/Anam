#!/usr/bin/env python3
"""
Tír Admin CLI

Manage users, channel identifiers, and database setup.
Run from the project root: python -m tir.admin <command>

Commands:
    init-db          Create databases and tables
    add-user         Create a new user
    list-users       Show all users
    add-channel      Add a channel identifier (phone, username, etc.)
    set-password     Set web login password for a user
    show-user        Show user details including channel identifiers
    memory-audit     Report memory retrieval integrity status
    memory-repair    Repair ended unchunked conversations
    memory-checkpoint-active
                    Checkpoint active conversations into retrieval
    backup           Back up runtime state
    restore          Restore runtime state from a backup
    behavioral-guidance-proposal-list
                    List behavioral guidance proposals
    behavioral-guidance-proposal-add
                    Record an AI-proposed behavioral guidance change
    behavioral-guidance-proposal-update
                    Update proposal review status
    behavioral-guidance-review-conversation
                    Generate AI-proposed guidance candidates from one chat conversation
    behavioral-guidance-review-day
                    Review a bounded recent/day window for AI-proposed guidance candidates
    behavioral-guidance-proposal-apply
                    Apply an approved addition proposal to BEHAVIORAL_GUIDANCE.md
    reflection-journal-day
                    Generate a manual daily reflection journal
    reflection-journal-register
                    Register and index an existing reflection journal
"""

import argparse
import getpass
import json
import sys
from pathlib import Path

from tir.memory.db import (
    init_databases,
    create_user,
    get_all_users,
    get_user_by_name,
    add_channel_identifier,
    upsert_channel_auth,
)
from tir.memory.audit import (
    audit_memory_integrity,
    checkpoint_active_conversations,
    repair_memory_integrity,
)
from tir.ops.backup import BackupError, create_backup, restore_backup
from tir.review.service import (
    ReviewValidationError,
    create_review_item,
    list_review_items,
    update_review_item_status,
)
from tir.behavioral_guidance.service import (
    BehavioralGuidanceValidationError,
    create_behavioral_guidance_proposal,
    list_behavioral_guidance_proposals,
    update_behavioral_guidance_proposal_status,
)
from tir.behavioral_guidance.review import (
    BehavioralGuidanceReviewError,
    generate_behavioral_guidance_daily_review,
    generate_behavioral_guidance_review,
    write_behavioral_guidance_review_proposals,
)
from tir.behavioral_guidance.apply import (
    BehavioralGuidanceApplyError,
    apply_behavioral_guidance_proposal,
    plan_behavioral_guidance_apply,
)
from tir.reflection.journal import (
    ReflectionJournalError,
    register_reflection_journal_artifact,
    run_reflection_journal_day,
)


def cmd_init_db(args):
    """Initialize databases."""
    init_databases()
    print("Databases initialized.")


def cmd_add_user(args):
    """Create a new user."""
    # Check if user already exists
    existing = get_user_by_name(args.name)
    if existing:
        print(f"Error: user '{args.name}' already exists (id: {existing['id']})")
        sys.exit(1)

    role = "admin" if args.admin else "user"
    user = create_user(args.name, role=role)
    print(f"Created {role}: {user['name']} (id: {user['id']})")


def cmd_list_users(args):
    """List all users."""
    users = get_all_users()
    if not users:
        print("No users.")
        return

    for u in users:
        print(f"  {u['name']:20s}  role={u['role']:6s}  id={u['id']}")


def cmd_add_channel(args):
    """Add a channel identifier for a user."""
    user = get_user_by_name(args.user)
    if not user:
        print(f"Error: no user named '{args.user}'")
        sys.exit(1)

    ci = add_channel_identifier(
        user_id=user["id"],
        channel=args.channel,
        identifier=args.identifier,
        verified=True,
    )
    print(f"Added {args.channel} identifier '{args.identifier}' for {args.user}")


def cmd_set_password(args):
    """Set web login password for a user."""
    try:
        from argon2 import PasswordHasher
    except ImportError:
        print("Error: argon2-cffi not installed. Run: pip install argon2-cffi")
        sys.exit(1)

    user = get_user_by_name(args.user)
    if not user:
        print(f"Error: no user named '{args.user}'")
        sys.exit(1)

    password = getpass.getpass(f"Password for {args.user}: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        print("Passwords don't match.")
        sys.exit(1)

    ph = PasswordHasher()
    hashed = ph.hash(password)

    upsert_channel_auth(
        user_id=user["id"],
        channel="web",
        identifier=args.user.lower(),
        auth_material=hashed,
        verified=True,
    )
    print(f"Password set for {args.user} (web channel)")


def cmd_show_user(args):
    """Show user details."""
    from tir.memory.db import get_connection

    user = get_user_by_name(args.user)
    if not user:
        print(f"Error: no user named '{args.user}'")
        sys.exit(1)

    print(f"Name:       {user['name']}")
    print(f"Role:       {user['role']}")
    print(f"ID:         {user['id']}")
    print(f"Created:    {user['created_at']}")
    print(f"Last seen:  {user.get('last_seen_at', 'never')}")

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM main.channel_identifiers WHERE user_id = ?",
            (user["id"],),
        ).fetchall()

    if rows:
        print(f"Channels:")
        for r in rows:
            verified = "verified" if r["verified"] else "unverified"
            has_auth = "has auth" if r["auth_material"] else "no auth"
            print(f"  {r['channel']:12s} {r['identifier']:30s} [{verified}, {has_auth}]")
    else:
        print("Channels:   none")


def _print_memory_audit(audit: dict):
    """Print a readable memory audit summary."""
    print("Memory audit")
    print(f"Working messages: {audit['working_message_count']}")
    print(f"Archive messages: {audit['archive_message_count']}")
    print(f"Message parity: {'ok' if audit['message_id_parity_ok'] else 'problem'}")
    print(
        "Missing messages: "
        f"from_archive={audit['missing_from_archive_count']} "
        f"from_working={audit['missing_from_working_count']}"
    )
    print(
        "Conversations: "
        f"total={audit['total_conversations']} "
        f"active={audit['active_conversation_count']} "
        f"ended={audit['ended_conversation_count']} "
        f"ended_unchunked={audit['ended_unchunked_count']}"
    )
    print(f"FTS chunks: {audit['fts_chunk_count']}")
    print(f"Chroma chunks: {audit['chroma_chunk_count']}")
    print(f"FTS/Chroma count match: {audit['fts_chroma_count_match']}")
    print(
        "Chunked conversations missing FTS chunks: "
        f"{audit['chunked_conversations_missing_fts_chunks']}"
    )

    if audit["missing_from_archive"]:
        print("Missing from archive IDs:")
        for message_id in audit["missing_from_archive"]:
            print(f"  {message_id}")
    if audit["missing_from_working"]:
        print("Missing from working IDs:")
        for message_id in audit["missing_from_working"]:
            print(f"  {message_id}")
    if audit["ended_unchunked_ids"]:
        print("Ended unchunked conversation IDs:")
        for conversation_id in audit["ended_unchunked_ids"]:
            print(f"  {conversation_id}")
    if audit["chunked_conversations_missing_fts_chunk_ids"]:
        print("Chunked conversations missing FTS chunk IDs:")
        for conversation_id in audit["chunked_conversations_missing_fts_chunk_ids"]:
            print(f"  {conversation_id}")
    if audit["warnings"]:
        print("Warnings:")
        for warning in audit["warnings"]:
            print(f"  - {warning}")


def _print_memory_repair(summary: dict):
    """Print a readable memory repair summary."""
    print("Memory repair")
    print(f"Dry run: {summary['dry_run']}")
    print(f"Active conversations: {summary['active_conversation_count']}")
    print(
        "Repairable ended unchunked conversations: "
        f"{summary['repairable_ended_unchunked_count']}"
    )
    if summary["dry_run"]:
        print(f"Would attempt: {summary['would_attempt']}")
        if summary["conversation_ids"]:
            print("Would repair conversation IDs:")
            for conversation_id in summary["conversation_ids"]:
                print(f"  {conversation_id}")
        return

    print(f"Attempted: {summary['attempted']}")
    print(f"Succeeded: {summary['succeeded']}")
    print(f"Failed: {summary['failed']}")
    print(f"Chunks written: {summary['chunks_written']}")
    if summary["failures"]:
        print("Failures:")
        for failure in summary["failures"]:
            print(f"  {failure['conversation_id']}: {failure['error']}")


def _print_memory_checkpoint_active(summary: dict):
    """Print a readable active conversation checkpoint summary."""
    print("Active conversation checkpoint")
    print(f"Dry run: {summary['dry_run']}")
    print(f"Active conversations: {summary['active_conversation_count']}")
    print(
        "Checkpointable active conversations: "
        f"{summary['checkpointable_active_count']}"
    )
    if summary["dry_run"]:
        print(f"Would attempt: {len(summary['conversation_ids'])}")
        if summary["conversation_ids"]:
            print("Would checkpoint conversation IDs:")
            for conversation_id in summary["conversation_ids"]:
                print(f"  {conversation_id}")
        return

    print(f"Attempted: {summary['attempted']}")
    print(f"Succeeded: {summary['succeeded']}")
    print(f"Failed: {summary['failed']}")
    print(f"Chunks written: {summary['chunks_written']}")
    if summary["failures"]:
        print("Failures:")
        for failure in summary["failures"]:
            print(f"  {failure['conversation_id']}: {failure['error']}")


def _print_backup_summary(summary: dict):
    """Print a readable backup summary."""
    manifest = summary["manifest"]
    print("Backup complete")
    print(f"Backup path: {summary['backup_path']}")
    print(f"Manifest: {summary['manifest_path']}")
    print(f"Project: {manifest['project']}")
    print(f"Created at: {manifest['created_at']}")
    for key, entry in manifest["paths"].items():
        if entry["exists"]:
            size = entry.get("bytes", 0)
            if "file_count" in entry:
                print(f"{key}: copied ({entry['file_count']} files, {size} bytes)")
            else:
                print(f"{key}: copied ({size} bytes)")
        else:
            print(f"{key}: missing")

    governance_files = manifest.get("governance_files", {})
    if governance_files:
        print("Governance files:")
        for name, entry in governance_files.items():
            if entry["exists"]:
                print(f"  {name}: copied ({entry.get('bytes', 0)} bytes)")
            else:
                print(f"  {name}: missing")


def _print_restore_summary(summary: dict):
    """Print a readable restore summary."""
    print("Restore")
    print("Warning: restore should be run with the app stopped.")
    print(f"Backup path: {summary['backup_path']}")
    print(f"Dry run: {summary['dry_run']}")

    if not summary.get("ok"):
        print(f"Refused: {summary['error']}")
        return

    if summary["dry_run"]:
        print("Would replace:")
        for target in summary["would_replace"]:
            if target["backup_entry_exists"]:
                print(f"  {target['key']} -> {target['destination']}")
            else:
                print(f"  {target['key']}: not present in backup")
        return

    print(f"Pre-restore safety backup: {summary['pre_restore_backup']}")
    print("Restored:")
    for target in summary["restored"]:
        print(f"  {target['key']} -> {target['destination']}")


def _print_review_item(item: dict):
    """Print one compact review item row."""
    print(
        f"{item['item_id']}  "
        f"status={item['status']}  "
        f"priority={item['priority']}  "
        f"category={item['category']}  "
        f"created={item['created_at']}  "
        f"title={item['title']}"
    )


def _print_behavioral_guidance_proposal(proposal: dict):
    """Print one compact behavioral guidance proposal row."""
    print(
        f"{proposal['proposal_id']}  "
        f"status={proposal['status']}  "
        f"type={proposal['proposal_type']}  "
        f"channel={proposal['source_channel']}  "
        f"created={proposal['created_at']}  "
        f"text={proposal['proposal_text']}"
    )


def _parse_metadata_json(raw: str | None) -> dict | None:
    """Parse optional CLI metadata JSON."""
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid metadata JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("metadata JSON must be an object")
    return parsed


def cmd_memory_audit(args):
    """Run memory integrity audit."""
    audit = audit_memory_integrity(limit=args.limit)
    _print_memory_audit(audit)


def cmd_memory_repair(args):
    """Repair ended unchunked conversations."""
    summary = repair_memory_integrity(limit=args.limit, dry_run=args.dry_run)
    _print_memory_repair(summary)


def cmd_memory_checkpoint_active(args):
    """Checkpoint active conversations into retrieval."""
    summary = checkpoint_active_conversations(
        limit=args.limit,
        dry_run=args.dry_run,
    )
    _print_memory_checkpoint_active(summary)


def cmd_backup(args):
    """Create a runtime state backup."""
    summary = create_backup(destination_root=args.destination)
    _print_backup_summary(summary)


def cmd_restore(args):
    """Restore runtime state from a backup."""
    try:
        summary = restore_backup(
            Path(args.backup_path),
            force=args.force,
            dry_run=args.dry_run,
        )
    except BackupError as exc:
        print(f"Restore failed: {exc}")
        sys.exit(1)
    _print_restore_summary(summary)
    if not summary.get("ok"):
        sys.exit(1)


def cmd_review_list(args):
    """List review queue items."""
    try:
        items = list_review_items(
            status=args.status,
            category=args.category,
            priority=args.priority,
            limit=args.limit,
        )
    except ReviewValidationError as exc:
        print(f"Review list failed: {exc}")
        sys.exit(1)

    if not items:
        print("No review items.")
        return

    for item in items:
        _print_review_item(item)


def cmd_review_add(args):
    """Create a review queue item."""
    try:
        metadata = _parse_metadata_json(args.metadata_json)
        item = create_review_item(
            title=args.title,
            description=args.description,
            category=args.category,
            priority=args.priority,
            source_type=args.source_type,
            source_conversation_id=args.source_conversation_id,
            source_message_id=args.source_message_id,
            source_artifact_id=args.source_artifact_id,
            source_tool_name=args.source_tool_name,
            created_by=args.created_by,
            metadata=metadata,
        )
    except (ReviewValidationError, ValueError) as exc:
        print(f"Review add failed: {exc}")
        sys.exit(1)

    print("Review item created")
    _print_review_item(item)


def cmd_review_update(args):
    """Update review queue item status."""
    try:
        item = update_review_item_status(args.item_id, args.status)
    except ReviewValidationError as exc:
        print(f"Review update failed: {exc}")
        sys.exit(1)

    if item is None:
        print(f"Review update failed: item not found: {args.item_id}")
        sys.exit(1)

    print("Review item updated")
    _print_review_item(item)


def cmd_behavioral_guidance_proposal_list(args):
    """List behavioral guidance proposals."""
    try:
        proposals = list_behavioral_guidance_proposals(
            status=args.status,
            proposal_type=args.proposal_type,
            limit=args.limit,
        )
    except BehavioralGuidanceValidationError as exc:
        print(f"Behavioral guidance proposal list failed: {exc}")
        sys.exit(1)

    if not proposals:
        print("No behavioral guidance proposals.")
        return

    for proposal in proposals:
        _print_behavioral_guidance_proposal(proposal)


def cmd_behavioral_guidance_proposal_add(args):
    """Record an AI-proposed behavioral guidance change."""
    try:
        metadata = _parse_metadata_json(args.metadata_json)
        proposal = create_behavioral_guidance_proposal(
            proposal_type=args.proposal_type,
            proposal_text=args.proposal_text,
            target_existing_guidance_id=args.target_existing_guidance_id,
            target_text=args.target_text,
            rationale=args.rationale,
            source_experience_summary=args.source_experience_summary,
            source_user_id=args.source_user_id,
            source_conversation_id=args.source_conversation_id,
            source_message_id=args.source_message_id,
            source_channel=args.source_channel,
            risk_if_added=args.risk_if_added,
            risk_if_not_added=args.risk_if_not_added,
            metadata=metadata,
        )
    except (BehavioralGuidanceValidationError, ValueError) as exc:
        print(f"Behavioral guidance proposal add failed: {exc}")
        sys.exit(1)

    print("Behavioral guidance proposal recorded")
    _print_behavioral_guidance_proposal(proposal)


def cmd_behavioral_guidance_proposal_update(args):
    """Update behavioral guidance proposal review status."""
    try:
        proposal = update_behavioral_guidance_proposal_status(
            args.proposal_id,
            args.status,
            reviewed_by_user_id=args.reviewed_by_user_id,
            reviewed_by_role=args.reviewed_by_role,
            review_decision_reason=args.review_decision_reason,
            applied_by_user_id=args.applied_by_user_id,
            apply_note=args.apply_note,
        )
    except BehavioralGuidanceValidationError as exc:
        print(f"Behavioral guidance proposal update failed: {exc}")
        sys.exit(1)

    if proposal is None:
        print(f"Behavioral guidance proposal update failed: item not found: {args.proposal_id}")
        sys.exit(1)

    print("Behavioral guidance proposal updated")
    _print_behavioral_guidance_proposal(proposal)


def cmd_behavioral_guidance_review_conversation(args):
    """Generate behavioral guidance proposals from one selected conversation."""
    try:
        review = generate_behavioral_guidance_review(
            args.conversation_id,
            max_proposals=args.max_proposals,
            model=args.model,
        )
    except BehavioralGuidanceReviewError as exc:
        print(f"Behavioral guidance conversation review failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Behavioral guidance conversation review failed: {exc}")
        sys.exit(1)

    proposals = review["proposals"]
    mode = "write" if args.write else "dry-run"
    print("Behavioral guidance conversation review complete")
    print(f"mode={mode}")
    print(f"conversation_id={review['conversation_id']}")
    print(f"source_user_id={review.get('source_user_id')}")
    print(f"message_count={review['message_count']}")
    print(f"model={review['model']}")
    print(f"proposal_count={len(proposals)}")

    if not proposals:
        reason = review.get("no_proposal_reason") or "No proposal warranted."
        print(f"no_proposal_reason={reason}")
        return

    if not args.write:
        print(json.dumps({"proposals": proposals}, indent=2, sort_keys=True))
        return

    try:
        created = write_behavioral_guidance_review_proposals(review)
    except BehavioralGuidanceValidationError as exc:
        print(f"Behavioral guidance proposal write failed: {exc}")
        sys.exit(1)

    print("Created behavioral guidance proposal IDs:")
    for proposal in created:
        print(f"  {proposal['proposal_id']}")
        _print_behavioral_guidance_proposal(proposal)


def cmd_behavioral_guidance_review_day(args):
    """Review a bounded day/window of conversations for guidance proposals."""
    try:
        review = generate_behavioral_guidance_daily_review(
            date_text=args.date,
            since=args.since,
            conversation_ids=args.conversation_id,
            write=args.write,
            max_conversations=args.max_conversations,
            max_proposals_per_conversation=args.max_proposals_per_conversation,
            max_total_proposals=args.max_total_proposals,
            model=args.model,
            allow_duplicates=args.allow_duplicates,
        )
    except BehavioralGuidanceReviewError as exc:
        print(f"Behavioral guidance daily review failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Behavioral guidance daily review failed: {exc}")
        sys.exit(1)

    print("Behavioral guidance daily review complete")
    print(f"mode={review['mode']}")
    print(f"selected_conversations={review['selected_conversations']}")
    print(f"reviewed_conversations={review['reviewed_conversations']}")
    print(f"skipped_conversations={review['skipped_conversations']}")
    print(f"failed_conversations={review['failed_conversations']}")
    print(f"proposal_count={review['proposal_count']}")
    print(f"created_proposal_count={review['created_proposal_count']}")
    selection = review.get("selection") or {}
    if selection.get("selection_mode") == "date":
        print(f"local_date={selection.get('local_date')}")
        print(f"timezone={selection.get('timezone')}")
        print(f"local_offset={selection.get('local_offset')}")
        print(f"utc_start={selection.get('utc_start')}")
        print(f"utc_end={selection.get('utc_end')}")
    elif selection.get("selection_mode") == "since":
        print(f"since={selection.get('since')}")
        print(f"utc_start={selection.get('utc_start')}")
    if review.get("stopped_reason"):
        print(f"stopped_reason={review['stopped_reason']}")

    for result in review["results"]:
        print(
            "conversation "
            f"id={result['conversation_id']} "
            f"status={result['status']} "
            f"messages={result['message_count']} "
            f"proposals={result['proposal_count']}"
        )
        if result.get("skip_reason"):
            print(f"  skip_reason={result['skip_reason']}")
        if result.get("error"):
            print(f"  error={result['error']}")
        if result.get("no_proposal_reason"):
            print(f"  no_proposal_reason={result['no_proposal_reason']}")
        if result.get("created_proposal_ids"):
            print("  created_proposal_ids=" + ", ".join(result["created_proposal_ids"]))
        if not args.write and result.get("proposals"):
            print(json.dumps({"proposals": result["proposals"]}, indent=2, sort_keys=True))


def cmd_behavioral_guidance_proposal_apply(args):
    """Apply an approved addition proposal to BEHAVIORAL_GUIDANCE.md."""
    try:
        if args.write:
            result = apply_behavioral_guidance_proposal(
                args.proposal_id,
                applied_by_user_id=args.applied_by_user_id,
                apply_note=args.apply_note,
            )
            print("Behavioral guidance proposal applied")
            _print_behavioral_guidance_proposal(result["proposal"])
            return

        plan = plan_behavioral_guidance_apply(args.proposal_id)
    except BehavioralGuidanceApplyError as exc:
        print(f"Behavioral guidance proposal apply failed: {exc}")
        sys.exit(1)

    print("Behavioral guidance proposal apply dry-run")
    print(f"proposal_id={args.proposal_id}")
    print(f"guidance_path={plan['guidance_path']}")
    print("append_block:")
    print(plan["append_block"], end="")


def cmd_reflection_journal_day(args):
    """Generate a manual daily reflection journal."""
    try:
        result = run_reflection_journal_day(
            date_text=args.date,
            since=args.since,
            write=args.write,
            register_artifact=args.register_artifact,
            max_conversations=args.max_conversations,
            model=args.model,
        )
    except ReflectionJournalError as exc:
        print(f"Reflection journal failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Reflection journal failed: {exc}")
        sys.exit(1)

    print("Reflection journal complete")
    print(f"mode={result['mode']}")
    print(f"status={result['status']}")
    print(f"target_path={result['target_path']}")
    print(f"conversations_reviewed={result['conversation_count']}")
    print(f"messages_reviewed={result['message_count']}")
    selection = result.get("selection") or {}
    if selection.get("selection_mode") == "date":
        print(f"local_date={selection.get('local_date')}")
        print(f"timezone={selection.get('timezone')}")
        print(f"local_offset={selection.get('local_offset')}")
        print(f"utc_start={selection.get('utc_start')}")
        print(f"utc_end={selection.get('utc_end')}")
    elif selection.get("selection_mode") == "since":
        print(f"since={selection.get('since')}")
        print(f"utc_start={selection.get('utc_start')}")

    if result.get("reason"):
        print(f"reason={result['reason']}")
    if result.get("write_result"):
        print(f"written_path={result['write_result']['path']}")
        print(f"written_bytes={result['write_result']['bytes']}")
    if result.get("artifact_result"):
        artifact_result = result["artifact_result"]
        artifact = artifact_result["artifact"]
        indexing = artifact_result["indexing"]
        print(f"artifact_id={artifact['artifact_id']}")
        print(f"artifact_path={artifact['path']}")
        print(f"indexing_status={indexing['status']}")
        print(f"indexing_chunks={indexing.get('chunks_written', 0)}")
    if result.get("journal"):
        print("journal:")
        print(result["journal"], end="")


def cmd_reflection_journal_register(args):
    """Register and index an existing reflection journal file."""
    try:
        result = register_reflection_journal_artifact(args.date)
    except ReflectionJournalError as exc:
        print(f"Reflection journal registration failed: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Reflection journal registration failed: {exc}")
        sys.exit(1)

    artifact = result["artifact"]
    indexing = result["indexing"]
    print("Reflection journal registered")
    print(f"journal_date={args.date}")
    print(f"path={result['path']}")
    print(f"artifact_id={artifact['artifact_id']}")
    print(f"indexing_status={indexing['status']}")
    print(f"indexing_chunks={indexing.get('chunks_written', 0)}")


def main():
    parser = argparse.ArgumentParser(
        description="Tír Admin CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # init-db
    sub.add_parser("init-db", help="Create databases and tables")

    # add-user
    p = sub.add_parser("add-user", help="Create a new user")
    p.add_argument("name", help="Display name")
    p.add_argument("--admin", action="store_true", help="Make this user an admin")

    # list-users
    sub.add_parser("list-users", help="Show all users")

    # add-channel
    p = sub.add_parser("add-channel", help="Add channel identifier for a user")
    p.add_argument("user", help="User name")
    p.add_argument("channel", help="Channel type (web, imessage, discord)")
    p.add_argument("identifier", help="Channel-specific ID (phone number, username, etc)")

    # set-password
    p = sub.add_parser("set-password", help="Set web login password")
    p.add_argument("user", help="User name")

    # show-user
    p = sub.add_parser("show-user", help="Show user details")
    p.add_argument("user", help="User name")

    # memory-audit
    p = sub.add_parser("memory-audit", help="Report memory retrieval integrity")
    p.add_argument("--limit", type=int, default=25, help="Max IDs to show")

    # memory-repair
    p = sub.add_parser("memory-repair", help="Repair ended unchunked conversations")
    p.add_argument("--limit", type=int, default=None, help="Max conversations to repair")
    p.add_argument("--dry-run", action="store_true", help="Report repair targets only")

    # memory-checkpoint-active
    p = sub.add_parser(
        "memory-checkpoint-active",
        help="Checkpoint active conversations into retrieval",
    )
    p.add_argument("--limit", type=int, default=None, help="Max conversations to checkpoint")
    p.add_argument("--dry-run", action="store_true", help="Report checkpoint targets only")

    # backup
    p = sub.add_parser("backup", help="Back up runtime state")
    p.add_argument(
        "--destination",
        type=Path,
        default=None,
        help="Root directory for the timestamped backup folder",
    )

    # restore
    p = sub.add_parser("restore", help="Restore runtime state from a backup")
    p.add_argument("backup_path", help="Backup folder containing manifest.json")
    p.add_argument("--dry-run", action="store_true", help="Report restore plan only")
    p.add_argument("--force", action="store_true", help="Required to mutate runtime state")

    # review-list
    p = sub.add_parser("review-list", help="List review queue items")
    p.add_argument("--status", default=None, help="Filter by status")
    p.add_argument("--category", default=None, help="Filter by category")
    p.add_argument("--priority", default=None, help="Filter by priority")
    p.add_argument("--limit", type=int, default=50, help="Max items to show")

    # review-add
    p = sub.add_parser("review-add", help="Create a review queue item")
    p.add_argument("--title", required=True, help="Review item title")
    p.add_argument("--description", default=None, help="Optional description")
    p.add_argument("--category", default="other", help="Review category")
    p.add_argument("--priority", default="normal", help="Review priority")
    p.add_argument("--source-type", default=None, help="Optional source type")
    p.add_argument("--source-conversation-id", default=None, help="Optional source conversation ID")
    p.add_argument("--source-message-id", default=None, help="Optional source message ID")
    p.add_argument("--source-artifact-id", default=None, help="Optional source artifact ID")
    p.add_argument("--source-tool-name", default=None, help="Optional source tool name")
    p.add_argument("--created-by", default="operator", help="Creator label")
    p.add_argument("--metadata-json", default=None, help="Optional metadata JSON object")

    # review-update
    p = sub.add_parser("review-update", help="Update review item status")
    p.add_argument("item_id", help="Review item ID")
    p.add_argument("--status", required=True, help="New status")

    # behavioral-guidance-proposal-list
    p = sub.add_parser(
        "behavioral-guidance-proposal-list",
        help="List behavioral guidance proposals",
    )
    p.add_argument("--status", default=None, help="Filter by status")
    p.add_argument("--proposal-type", default=None, help="Filter by proposal type")
    p.add_argument("--limit", type=int, default=50, help="Max proposals to show")

    # behavioral-guidance-proposal-add
    p = sub.add_parser(
        "behavioral-guidance-proposal-add",
        help="Record an AI-proposed behavioral guidance change",
    )
    p.add_argument("--proposal-type", required=True, help="addition, removal, or revision")
    p.add_argument("--proposal-text", required=True, help="Atomic proposed change text")
    p.add_argument("--target-existing-guidance-id", default=None, help="Optional target ID")
    p.add_argument("--target-text", default=None, help="Optional target guidance text")
    p.add_argument("--rationale", required=True, help="Proposal rationale")
    p.add_argument("--source-experience-summary", default=None, help="Source experience summary")
    p.add_argument("--source-user-id", default=None, help="Source user ID")
    p.add_argument("--source-conversation-id", default=None, help="Source conversation ID")
    p.add_argument("--source-message-id", default=None, help="Source message ID")
    p.add_argument(
        "--source-channel",
        default="unknown",
        help="Source channel: chat, imessage, or unknown",
    )
    p.add_argument("--risk-if-added", default=None, help="Risk if the change is added")
    p.add_argument("--risk-if-not-added", default=None, help="Risk if the change is not added")
    p.add_argument("--metadata-json", default=None, help="Optional metadata JSON object")

    # behavioral-guidance-proposal-update
    p = sub.add_parser(
        "behavioral-guidance-proposal-update",
        help="Update behavioral guidance proposal review status",
    )
    p.add_argument("proposal_id", help="Behavioral guidance proposal ID")
    p.add_argument("--status", required=True, help="New status")
    p.add_argument("--reviewed-by-user-id", default=None, help="Reviewing admin user ID")
    p.add_argument("--reviewed-by-role", default="admin", help="Reviewing role")
    p.add_argument("--review-decision-reason", default=None, help="Review decision reason")
    p.add_argument("--applied-by-user-id", default=None, help="Applying admin user ID")
    p.add_argument("--apply-note", default=None, help="Application note")

    # reflection-journal-day
    p = sub.add_parser(
        "reflection-journal-day",
        help="Generate a manual daily reflection journal",
    )
    p.add_argument("--date", default=None, help="Local/system date to review, YYYY-MM-DD")
    p.add_argument("--since", default=None, help="Timezone-aware ISO timestamp lower bound")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Generate journal without writing")
    mode.add_argument("--write", action="store_true", help="Write journal to workspace/journals")
    p.add_argument("--model", default=None, help="Optional Ollama model override")
    p.add_argument("--max-conversations", type=int, default=10, help="Max conversations to review")
    p.add_argument(
        "--register-artifact",
        action="store_true",
        help="After --write, register and index the journal as journal memory",
    )

    # reflection-journal-register
    p = sub.add_parser(
        "reflection-journal-register",
        help="Register and index an existing reflection journal",
    )
    p.add_argument("date", help="Journal local date, YYYY-MM-DD")

    # behavioral-guidance-review-conversation
    p = sub.add_parser(
        "behavioral-guidance-review-conversation",
        help="Generate AI-proposed guidance candidates from one chat conversation",
    )
    p.add_argument("conversation_id", help="Conversation ID to review")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Generate proposals without writing")
    mode.add_argument("--write", action="store_true", help="Write generated proposals")
    p.add_argument(
        "--max-proposals",
        type=int,
        default=1,
        help="Max proposals to generate, capped at 3",
    )
    p.add_argument("--model", default=None, help="Optional Ollama model override")

    # behavioral-guidance-review-day
    p = sub.add_parser(
        "behavioral-guidance-review-day",
        help="Review a bounded recent/day window for AI-proposed guidance candidates",
    )
    p.add_argument("--date", default=None, help="Local/system date to review, YYYY-MM-DD")
    p.add_argument("--since", default=None, help="Timezone-aware ISO timestamp lower bound")
    p.add_argument(
        "--conversation-id",
        action="append",
        default=None,
        help="Conversation ID to review; repeatable",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Generate proposals without writing")
    mode.add_argument("--write", action="store_true", help="Write generated proposals")
    p.add_argument("--max-conversations", type=int, default=10, help="Max conversations to review")
    p.add_argument(
        "--max-proposals-per-conversation",
        type=int,
        default=1,
        help="Max proposals per conversation, capped at 3",
    )
    p.add_argument("--max-total-proposals", type=int, default=5, help="Max total proposals")
    p.add_argument("--model", default=None, help="Optional Ollama model override")
    p.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Review conversations even if conversation_review_v1 proposals already exist",
    )

    # behavioral-guidance-proposal-apply
    p = sub.add_parser(
        "behavioral-guidance-proposal-apply",
        help="Apply an approved addition proposal to BEHAVIORAL_GUIDANCE.md",
    )
    p.add_argument("proposal_id", help="Behavioral guidance proposal ID")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Show append block without writing")
    mode.add_argument("--write", action="store_true", help="Append guidance and mark applied")
    p.add_argument("--applied-by-user-id", default=None, help="Applying admin user ID")
    p.add_argument("--apply-note", default=None, help="Application note")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure databases exist for DB-facing commands. Backup/restore must not
    # create or mutate runtime state before their own safety checks run.
    if args.command not in {"init-db", "backup", "restore"}:
        init_databases()

    commands = {
        "init-db": cmd_init_db,
        "add-user": cmd_add_user,
        "list-users": cmd_list_users,
        "add-channel": cmd_add_channel,
        "set-password": cmd_set_password,
        "show-user": cmd_show_user,
        "memory-audit": cmd_memory_audit,
        "memory-repair": cmd_memory_repair,
        "memory-checkpoint-active": cmd_memory_checkpoint_active,
        "backup": cmd_backup,
        "restore": cmd_restore,
        "review-list": cmd_review_list,
        "review-add": cmd_review_add,
        "review-update": cmd_review_update,
        "behavioral-guidance-proposal-list": cmd_behavioral_guidance_proposal_list,
        "behavioral-guidance-proposal-add": cmd_behavioral_guidance_proposal_add,
        "behavioral-guidance-proposal-update": cmd_behavioral_guidance_proposal_update,
        "behavioral-guidance-review-conversation": cmd_behavioral_guidance_review_conversation,
        "behavioral-guidance-review-day": cmd_behavioral_guidance_review_day,
        "behavioral-guidance-proposal-apply": cmd_behavioral_guidance_proposal_apply,
        "reflection-journal-day": cmd_reflection_journal_day,
        "reflection-journal-register": cmd_reflection_journal_register,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
