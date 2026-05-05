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
"""

import argparse
import getpass
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
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
