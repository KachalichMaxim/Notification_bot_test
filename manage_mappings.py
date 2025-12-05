#!/usr/bin/env python3
"""Helper script to manage user mappings"""
import sys
from user_mapping import (
    add_leader, remove_leader, add_telegram_mapping, remove_telegram_mapping,
    list_mappings, is_leader,     get_telegram_chat_id, get_all_leaders
)


def print_usage():
    """Print usage information"""
    print("""
Usage: python manage_mappings.py <command> [arguments]

Commands:
  list                          - List all mappings
  add-leader <user_id>          - Add user to leaders list
  remove-leader <user_id>       - Remove user from leaders list
  add-telegram <user_id> <chat_id> - Add Telegram mapping
  remove-telegram <user_id>     - Remove Telegram mapping
  check-leader <user_id>        - Check if user is a leader
  get-chat <user_id>            - Get Telegram chat ID for user
  leaders                       - List all leaders
""")

def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        mappings = list_mappings()
        print("\n📋 Current Mappings:")
        print(f"Leaders: {mappings.get('leaders', [])}")
        print(f"Telegram Chats: {mappings.get('telegram_chats', {})}")
    
    elif command == "add-leader":
        if len(sys.argv) < 3:
            print("❌ Error: User ID required")
            print("Usage: python manage_mappings.py add-leader <user_id>")
            return
        user_id = sys.argv[2]
        if add_leader(user_id):
            print(f"✅ Added {user_id} to leaders list")
        else:
            print(f"❌ Failed to add {user_id} to leaders list")
    
    elif command == "remove-leader":
        if len(sys.argv) < 3:
            print("❌ Error: User ID required")
            print("Usage: python manage_mappings.py remove-leader <user_id>")
            return
        user_id = sys.argv[2]
        if remove_leader(user_id):
            print(f"✅ Removed {user_id} from leaders list")
        else:
            print(f"❌ Failed to remove {user_id} from leaders list")
    
    elif command == "add-telegram":
        if len(sys.argv) < 4:
            print("❌ Error: User ID and Chat ID required")
            usage_msg = (
                "Usage: python manage_mappings.py "
                "add-telegram <user_id> <chat_id>"
            )
            print(usage_msg)
            return
        user_id = sys.argv[2]
        chat_id = sys.argv[3]
        if add_telegram_mapping(user_id, chat_id):
            print(f"✅ Added Telegram mapping: {user_id} -> {chat_id}")
        else:
            print("❌ Failed to add Telegram mapping")
    
    elif command == "remove-telegram":
        if len(sys.argv) < 3:
            print("❌ Error: User ID required")
            print("Usage: python manage_mappings.py remove-telegram <user_id>")
            return
        user_id = sys.argv[2]
        if remove_telegram_mapping(user_id):
            print(f"✅ Removed Telegram mapping for {user_id}")
        else:
            print("❌ Failed to remove Telegram mapping")
    
    elif command == "check-leader":
        if len(sys.argv) < 3:
            print("❌ Error: User ID required")
            print("Usage: python manage_mappings.py check-leader <user_id>")
            return
        user_id = sys.argv[2]
        if is_leader(user_id):
            print(f"✅ {user_id} is a leader")
        else:
            print(f"❌ {user_id} is not a leader")
    
    elif command == "get-chat":
        if len(sys.argv) < 3:
            print("❌ Error: User ID required")
            print("Usage: python manage_mappings.py get-chat <user_id>")
            return
        user_id = sys.argv[2]
        chat_id = get_telegram_chat_id(user_id)
        if chat_id:
            print(f"📱 Telegram chat ID for {user_id}: {chat_id}")
        else:
            print(f"❌ No Telegram mapping found for {user_id}")

    elif command == "leaders":
        leaders = get_all_leaders()
        if leaders:
            print(f"\n👔 Leaders ({len(leaders)}):")
            for leader in leaders:
                print(f"  - {leader}")
        else:
            print("❌ No leaders configured")
    
    else:
        print(f"❌ Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()

