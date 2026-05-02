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
"""

import argparse
import getpass
import sys

from tir.memory.db import (
    init_databases,
    create_user,
    get_all_users,
    get_user_by_name,
    add_channel_identifier,
    upsert_channel_auth,
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Ensure databases exist for all commands except init-db
    if args.command != "init-db":
        init_databases()

    commands = {
        "init-db": cmd_init_db,
        "add-user": cmd_add_user,
        "list-users": cmd_list_users,
        "add-channel": cmd_add_channel,
        "set-password": cmd_set_password,
        "show-user": cmd_show_user,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
