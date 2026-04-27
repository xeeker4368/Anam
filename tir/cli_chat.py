#!/usr/bin/env python3
"""
Tír CLI Chat

Talk to the entity from the terminal. For testing and development.
Run from project root: python -m tir.cli_chat

Usage:
    python -m tir.cli_chat                  # Uses default admin user
    python -m tir.cli_chat --user Sarah     # Specify user by name
    python -m tir.cli_chat --new            # Force new conversation

Commands during chat:
    /quit or /exit  — end conversation and exit
    /new            — end current conversation, start a new one
    /info           — show current conversation info
"""

import argparse
import sys
import logging

from tir.memory.db import (
    init_databases,
    get_user_by_name,
    get_all_users,
    get_active_conversations,
    end_conversation,
    get_conversation,
)
from tir.engine.conversation import handle_turn
from tir.memory.chunking import chunk_conversation_final


def main():
    parser = argparse.ArgumentParser(description="Tír CLI Chat")
    parser.add_argument("--user", default=None, help="User name (default: first admin)")
    parser.add_argument("--new", action="store_true", help="Start a new conversation")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # --- Logging ---
    log_level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # --- Init ---
    init_databases()

    # --- Resolve user ---
    if args.user:
        user = get_user_by_name(args.user)
        if not user:
            print(f"No user named '{args.user}'. Run: python -m tir.admin list-users")
            sys.exit(1)
    else:
        # Default to first admin, or first user
        users = get_all_users()
        if not users:
            print("No users exist. Run: python -m tir.admin add-user <name> --admin")
            sys.exit(1)
        user = next((u for u in users if u["role"] == "admin"), users[0])

    user_id = user["id"]
    user_name = user["name"]

    # --- Resolve conversation ---
    conversation_id = None
    if not args.new:
        # Resume most recent active conversation if one exists
        active = get_active_conversations(user_id)
        if active:
            conversation_id = active[0]["id"]
            conv = get_conversation(conversation_id)
            print(f"Resuming conversation {conversation_id[:8]}...")

    if conversation_id is None:
        print("Starting new conversation.")

    print(f"Chatting as {user_name}. Type /quit to exit, /new for new conversation.\n")

    # --- Chat loop ---
    while True:
        try:
            user_input = input(f"{user_name}: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n")
            break

        if not user_input:
            continue

        # --- Commands ---
        if user_input.lower() in ("/quit", "/exit"):
            break

        if user_input.lower() == "/new":
            if conversation_id:
                end_conversation(conversation_id)
                conv = get_conversation(conversation_id)
                user_id_for_chunk = conv["user_id"] if conv else user_id
                try:
                    n = chunk_conversation_final(conversation_id, user_id_for_chunk)
                    print(f"Ended conversation {conversation_id[:8]}. {n} chunks saved.")
                except Exception as e:
                    print(f"Ended conversation {conversation_id[:8]}. Chunking failed: {e}")
            conversation_id = None
            print("Starting new conversation.\n")
            continue

        if user_input.lower() == "/info":
            if conversation_id:
                conv = get_conversation(conversation_id)
                if conv:
                    print(f"  Conversation: {conv['id'][:8]}...")
                    print(f"  Started:      {conv['started_at']}")
                    print(f"  Messages:     {conv['message_count']}")
                else:
                    print("  No active conversation.")
            else:
                print("  No active conversation (next message starts one).")
            print()
            continue

        # --- Send to engine ---
        response = handle_turn(
            user_id=user_id,
            text=user_input,
            conversation_id=conversation_id,
        )

        # Update conversation_id (may have been created by handle_turn)
        conversation_id = response.conversation_id

        # --- Print response ---
        print(f"\nAssistant: {response.content}\n")

    # --- Cleanup ---
    if conversation_id:
        end_conversation(conversation_id)
        conv = get_conversation(conversation_id)
        user_id_for_chunk = conv["user_id"] if conv else user_id
        try:
            n = chunk_conversation_final(conversation_id, user_id_for_chunk)
            print(f"Conversation {conversation_id[:8]}... ended. {n} chunks saved.")
        except Exception as e:
            print(f"Conversation {conversation_id[:8]}... ended. Chunking failed: {e}")

    print("Goodbye.")


if __name__ == "__main__":
    main()
