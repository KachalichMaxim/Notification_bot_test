"""User mapping management for Bitrix24 users to Telegram chat IDs"""
import json
import os
from typing import Optional, Dict, List

MAPPINGS_FILE = os.path.join(
    os.path.dirname(__file__), "user_mappings.json"
)


def _load_mappings() -> Dict:
    """Load mappings from JSON file"""
    if not os.path.exists(MAPPINGS_FILE):
        return {"leaders": [], "telegram_chats": {}}
    
    try:
        with open(MAPPINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading mappings: {e}")
        return {"leaders": [], "telegram_chats": {}}


def _save_mappings(mappings: Dict) -> bool:
    """Save mappings to JSON file"""
    try:
        with open(MAPPINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(mappings, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Error saving mappings: {e}")
        return False


def is_leader(bitrix24_user_id: str) -> bool:
    """Check if user is a leader/top manager"""
    mappings = _load_mappings()
    leaders = mappings.get("leaders", [])
    return str(bitrix24_user_id) in [str(leader) for leader in leaders]


def get_telegram_chat_id(bitrix24_user_id: str) -> Optional[str]:
    """Get Telegram chat ID for a Bitrix24 user"""
    mappings = _load_mappings()
    telegram_chats = mappings.get("telegram_chats", {})
    return telegram_chats.get(str(bitrix24_user_id))


def add_leader(user_id: str) -> bool:
    """Add user to leaders list"""
    mappings = _load_mappings()
    leaders = mappings.get("leaders", [])
    user_id_str = str(user_id)
    
    if user_id_str not in leaders:
        leaders.append(user_id_str)
        mappings["leaders"] = leaders
        return _save_mappings(mappings)
    return True


def remove_leader(user_id: str) -> bool:
    """Remove user from leaders list"""
    mappings = _load_mappings()
    leaders = mappings.get("leaders", [])
    user_id_str = str(user_id)
    
    if user_id_str in leaders:
        leaders.remove(user_id_str)
        mappings["leaders"] = leaders
        return _save_mappings(mappings)
    return True


def add_telegram_mapping(
    bitrix24_user_id: str, telegram_chat_id: str
) -> bool:
    """Add or update Telegram mapping for a Bitrix24 user"""
    mappings = _load_mappings()
    telegram_chats = mappings.get("telegram_chats", {})
    telegram_chats[str(bitrix24_user_id)] = str(telegram_chat_id)
    mappings["telegram_chats"] = telegram_chats
    return _save_mappings(mappings)


def remove_telegram_mapping(bitrix24_user_id: str) -> bool:
    """Remove Telegram mapping for a Bitrix24 user"""
    mappings = _load_mappings()
    telegram_chats = mappings.get("telegram_chats", {})
    user_id_str = str(bitrix24_user_id)
    
    if user_id_str in telegram_chats:
        del telegram_chats[user_id_str]
        mappings["telegram_chats"] = telegram_chats
        return _save_mappings(mappings)
    return True


def list_mappings() -> Dict:
    """List all mappings"""
    return _load_mappings()


def get_all_leaders() -> List[str]:
    """Get list of all leader user IDs"""
    mappings = _load_mappings()
    return [str(leader) for leader in mappings.get("leaders", [])]

