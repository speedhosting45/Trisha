"""
Address management handlers for Escrow Bot
Complete full-length version with all fixes and features
"""
import logging
from telethon import events
from telethon.tl import types
from telethon.tl.types import ChannelParticipantCreator, ChannelParticipantAdmin, ChannelParticipant
from telethon.errors import RPCError, FloodWaitError
import json
import os
import time
import re
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

# Import utilities
from utils.texts import (
    BUYER_ADDRESS_PROMPT, SELLER_ADDRESS_PROMPT, ADDRESSES_MENU_TEXT,
    ADDRESS_SAVED_MESSAGE, NO_ADDRESS_MESSAGE, ADDRESSES_RESET_MESSAGE,
    ADDRESS_UPDATED_MESSAGE, ADDRESS_REMOVED_MESSAGE, ADDRESS_EXPIRED_MESSAGE,
    ADDRESS_CONFIRMATION_MESSAGE, ADDRESS_BOTH_SET_MESSAGE, ADDRESS_ERROR_MESSAGE
)
from utils.buttons import (
    get_addresses_menu_buttons, get_back_button, get_address_confirmation_buttons,
    get_address_actions_buttons, get_main_menu_buttons
)
from utils.blacklist import is_blacklisted, add_to_blacklist, load_blacklist
from utils.validators import validate_address, sanitize_input, is_valid_crypto_address
from utils.helpers import format_address_preview, get_time_remaining

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)

# Data files
USER_ADDRESSES_FILE = 'data/user_addresses.json'
USER_ROLES_FILE = 'data/user_roles.json'
ADDRESS_HISTORY_FILE = 'data/address_history.json'
ADDRESS_STATS_FILE = 'data/address_stats.json'
ACTIVE_GROUPS_FILE = 'data/active_groups.json'

# Constants
MAX_ADDRESS_LENGTH = 500
MIN_ADDRESS_LENGTH = 5
ADDRESS_TIMEOUT = 1800  # 30 minutes
MAX_ADDRESS_HISTORY = 10
ADDRESS_CACHE_TTL = 300  # 5 minutes

# Cache for frequently accessed data
_address_cache = {
    'addresses': None,
    'roles': None,
    'last_load': 0,
    'stats': defaultdict(lambda: {'total': 0, 'by_type': defaultdict(int)})
}

def load_json_file(filepath, default=None):
    """Safely load JSON file with error handling"""
    if default is None:
        default = {}
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON decode error in {filepath}: {e}")
        # Try to backup corrupted file
        try:
            backup_path = f"{filepath}.backup.{int(time.time())}"
            os.rename(filepath, backup_path)
            print(f"[INFO] Backed up corrupted file to {backup_path}")
        except:
            pass
        return default
    except Exception as e:
        print(f"[ERROR] Loading {filepath}: {e}")
        return default

def save_json_file(filepath, data):
    """Safely save JSON file with error handling"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Create temporary file first
        temp_path = f"{filepath}.temp"
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Rename temp file to actual file (atomic operation on Unix)
        os.replace(temp_path, filepath)
        return True
    except Exception as e:
        print(f"[ERROR] Saving {filepath}: {e}")
        return False

def load_addresses(use_cache=True):
    """Load user addresses data with caching"""
    global _address_cache
    
    current_time = time.time()
    
    # Return cached data if still valid
    if use_cache and _address_cache['addresses'] is not None:
        if current_time - _address_cache['last_load'] < ADDRESS_CACHE_TTL:
            return _address_cache['addresses']
    
    # Load fresh data
    addresses = load_json_file(USER_ADDRESSES_FILE, {})
    
    # Update cache
    _address_cache['addresses'] = addresses
    _address_cache['last_load'] = current_time
    
    # Update stats
    _address_cache['stats']['total'] = len(addresses)
    _address_cache['stats']['by_type'] = defaultdict(int)
    
    for user_id, user_data in addresses.items():
        if 'buyer_address' in user_data:
            _address_cache['stats']['by_type']['buyer'] += 1
        if 'seller_address' in user_data:
            _address_cache['stats']['by_type']['seller'] += 1
    
    return addresses

def save_addresses(addresses):
    """Save user addresses data and update cache"""
    global _address_cache
    
    success = save_json_file(USER_ADDRESSES_FILE, addresses)
    
    if success:
        # Update cache
        _address_cache['addresses'] = addresses
        _address_cache['last_load'] = time.time()
        
        # Update stats
        _address_cache['stats']['total'] = len(addresses)
        _address_cache['stats']['by_type'] = defaultdict(int)
        
        for user_id, user_data in addresses.items():
            if 'buyer_address' in user_data:
                _address_cache['stats']['by_type']['buyer'] += 1
            if 'seller_address' in user_data:
                _address_cache['stats']['by_type']['seller'] += 1
    
    return success

def load_user_roles(use_cache=True):
    """Load user roles data with caching"""
    global _address_cache
    
    current_time = time.time()
    
    # Return cached data if still valid
    if use_cache and _address_cache['roles'] is not None:
        if current_time - _address_cache['last_load'] < ADDRESS_CACHE_TTL:
            return _address_cache['roles']
    
    # Load fresh data
    roles = load_json_file(USER_ROLES_FILE, {})
    
    # Update cache
    _address_cache['roles'] = roles
    
    return roles

def save_user_roles(roles):
    """Save user roles data and update cache"""
    global _address_cache
    
    success = save_json_file(USER_ROLES_FILE, roles)
    
    if success:
        _address_cache['roles'] = roles
    
    return success

def load_address_history():
    """Load address history data"""
    return load_json_file(ADDRESS_HISTORY_FILE, {})

def save_address_history(history):
    """Save address history data"""
    return save_json_file(ADDRESS_HISTORY_FILE, history)

def load_address_stats():
    """Load address statistics"""
    return load_json_file(ADDRESS_STATS_FILE, {})

def save_address_stats(stats):
    """Save address statistics"""
    return save_json_file(ADDRESS_STATS_FILE, stats)

def load_active_groups():
    """Load active groups data"""
    return load_json_file(ACTIVE_GROUPS_FILE, {})

def save_active_groups(groups):
    """Save active groups data"""
    return save_json_file(ACTIVE_GROUPS_FILE, groups)

def get_user_display(user_obj):
    """Get clean display name for user with multiple fallbacks"""
    try:
        # Try to get username first (preferred)
        if hasattr(user_obj, 'username') and user_obj.username:
            username = user_obj.username.strip()
            if username and len(username) > 0:
                # Validate username format
                if re.match(r'^[a-zA-Z0-9_]{3,}$', username):
                    return f"@{username}"
        
        # Try to get first name
        first_name = getattr(user_obj, 'first_name', '')
        if first_name:
            first_name = sanitize_input(first_name.strip())
        
        # Try to get last name
        last_name = getattr(user_obj, 'last_name', '')
        if last_name:
            last_name = sanitize_input(last_name.strip())
        
        # Combine names intelligently
        if first_name and last_name:
            # Check if last name might be a username in disguise
            if last_name.startswith('@') or re.match(r'^[a-zA-Z0-9_]+$', last_name):
                full_name = f"{first_name} {last_name}"
            else:
                full_name = f"{first_name} {last_name}"
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            # Ultimate fallback: use user ID
            full_name = f"User_{user_obj.id}"
        
        # Clean any remaining problematic characters
        full_name = re.sub(r'[^\w\s@#\-\.\[\]\(\)]', '', full_name)
        full_name = re.sub(r'\s+', ' ', full_name)  # Replace multiple spaces with single
        full_name = full_name.strip()
        
        # Truncate if too long
        if len(full_name) > 50:
            full_name = full_name[:47] + "..."
        
        # Final check for empty string
        if not full_name or full_name.isspace():
            full_name = f"User_{user_obj.id}"
        
        return full_name
        
    except Exception as e:
        print(f"[ERROR] Getting user display for {getattr(user_obj, 'id', 'unknown')}: {e}")
        return f"User_{getattr(user_obj, 'id', 'unknown')}"

def clean_group_id(chat_id):
    """Clean group ID by removing -100 prefix if present"""
    try:
        chat_id = str(chat_id)
        # Remove -100 prefix for supergroups
        if chat_id.startswith("-100"):
            cleaned = chat_id[4:]
            # Verify it's a valid numeric ID
            if cleaned.isdigit():
                return cleaned
        return chat_id
    except Exception as e:
        print(f"[ERROR] Cleaning group ID {chat_id}: {e}")
        return str(chat_id)

def format_address_for_display(address, max_length=50):
    """Format address for display with truncation"""
    if not address:
        return "Not set"
    
    if len(address) <= max_length:
        return address
    
    # Show first and last parts
    prefix = address[:20]
    suffix = address[-20:]
    return f"{prefix}...{suffix}"

def add_to_address_history(user_id, address_type, address):
    """Add address to user's history"""
    try:
        history = load_address_history()
        user_id = str(user_id)
        
        if user_id not in history:
            history[user_id] = []
        
        # Create history entry
        entry = {
            'type': address_type,
            'address': address,
            'timestamp': time.time(),
            'date': datetime.now().isoformat()
        }
        
        # Add to beginning of list
        history[user_id].insert(0, entry)
        
        # Keep only last MAX_ADDRESS_HISTORY entries
        history[user_id] = history[user_id][:MAX_ADDRESS_HISTORY]
        
        save_address_history(history)
        return True
    except Exception as e:
        print(f"[ERROR] Adding to address history: {e}")
        return False

def update_address_stats(action, address_type=None):
    """Update address statistics"""
    try:
        stats = load_address_stats()
        
        # Update general stats
        stats['total_actions'] = stats.get('total_actions', 0) + 1
        stats['last_action'] = time.time()
        
        # Update daily stats
        today = datetime.now().strftime('%Y-%m-%d')
        if 'daily' not in stats:
            stats['daily'] = {}
        if today not in stats['daily']:
            stats['daily'][today] = {'sets': 0, 'updates': 0, 'views': 0}
        
        if action == 'set':
            stats['daily'][today]['sets'] = stats['daily'][today].get('sets', 0) + 1
            if address_type:
                stats[f'{address_type}_sets'] = stats.get(f'{address_type}_sets', 0) + 1
        elif action == 'update':
            stats['daily'][today]['updates'] = stats['daily'][today].get('updates', 0) + 1
        elif action == 'view':
            stats['daily'][today]['views'] = stats['daily'][today].get('views', 0) + 1
        
        # Clean up old daily stats (keep last 30 days)
        cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        stats['daily'] = {k: v for k, v in stats['daily'].items() if k >= cutoff}
        
        save_address_stats(stats)
    except Exception as e:
        print(f"[ERROR] Updating address stats: {e}")

def setup_address_handlers(client):
    """Setup all address-related handlers"""
    
    # Initialize address state if not exists
    if not hasattr(client, 'address_state'):
        client.address_state = {}
    
    if not hasattr(client, 'address_temp_data'):
        client.address_temp_data = {}
    
    @client.on(events.NewMessage(pattern='/buyer'))
    async def buyer_address_handler(event):
        """Handle /buyer command - Set buyer address"""
        try:
            # Start time for performance tracking
            start_time = time.time()
            
            # Get user and chat info
            user = await event.get_sender()
            chat = await event.get_chat()
            
            if not user or not chat:
                await event.reply("❌ Could not identify user or chat.")
                return
            
            # Check if user is blacklisted
            is_blocked, reason = is_blacklisted(user)
            if is_blocked:
                await event.reply(f"❌ You are blacklisted: {reason}")
                return
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            print(f"[ BUYER ] Command from user {user.id} in chat {raw_chat_id}")
            print(f"[ BUYER ] Cleaned group_id: {group_id}")
            print(f"[ BUYER ] User details - Username: {user.username}, First: {user.first_name}")
            
            # Load roles with cache
            roles = load_user_roles(use_cache=True)
            
            # Debug: Print all stored role keys
            print(f"[ BUYER ] Stored role keys: {list(roles.keys())}")
            
            # Check if group exists in roles
            if group_id not in roles:
                print(f"[ BUYER ] Group {group_id} not found in roles")
                
                # Try to find by name as fallback
                found = False
                chat_title = getattr(chat, 'title', '')
                if chat_title:
                    for key, data in roles.items():
                        if data.get('name') == chat_title:
                            group_id = key
                            found = True
                            print(f"[ BUYER ] Found group by name: {key}")
                            break
                
                if not found:
                    await event.reply(
                        "❌ No active escrow session found in this group.\n\n"
                        "Use /begin to start a session first.",
                        parse_mode='html'
                    )
                    return
            
            # Get roles for this group
            group_roles = roles.get(group_id, {})
            
            # Check if user has a role
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                print(f"[ ⚠️ ] User {user.id} has no role in chat {group_id}")
                
                # List all users in this group for debugging
                print(f"[ BUYER ] Users in group {group_id}: {list(group_roles.keys())}")
                
                await event.reply(
                    "❌ You don't have a role in this escrow session.\n\n"
                    "Only the designated buyer or seller can set addresses.\n\n"
                    "If you believe this is an error:\n"
                    "1️⃣ Check that you are one of the two selected participants\n"
                    "2️⃣ The session may have expired\n"
                    "3️⃣ Use /begin to start a new session",
                    parse_mode='html'
                )
                return
            
            user_role = user_data.get("role")
            user_name = user_data.get("name", get_user_display(user))
            
            if user_role != "buyer":
                print(f"[ ⚠️ ] User {user.id} is {user_role}, not buyer")
                await event.reply(
                    f"❌ Only the buyer can set the buyer address.\n\n"
                    f"You are registered as: <b>{user_role.upper()}</b>\n\n"
                    f"Use /seller if you are the seller, or /addresses to view addresses.",
                    parse_mode='html'
                )
                return
            
            # Load addresses
            addresses = load_addresses(use_cache=True)
            user_addresses = addresses.get(str(user.id), {})
            user_address = user_addresses.get("buyer_address")
            
            # Load address history for suggestions
            history = load_address_history()
            user_history = history.get(str(user.id), [])
            buyer_history = [h for h in user_history if h.get('type') == 'buyer']
            
            # Build response message
            if user_address:
                # Show existing address with preview
                preview = format_address_for_display(user_address)
                await event.reply(
                    f"📋 <b>Your Current Buyer Address</b>\n\n"
                    f"<code>{user_address}</code>\n\n"
                    f"<b>Preview:</b> {preview}\n"
                    f"<b>Length:</b> {len(user_address)} characters\n"
                    f"<b>Set on:</b> {user_addresses.get('buyer_updated', 'Unknown')}\n\n"
                    f"Do you want to update it?\n\n"
                    f"Send your new address or type /cancel to keep current.\n\n"
                    f"<i>Note: Previous addresses will be saved in your history.</i>",
                    parse_mode='html'
                )
            else:
                # Ask for address with examples
                example_text = ""
                if buyer_history:
                    recent = buyer_history[0]['address']
                    example_text = f"\n💡 <b>Recent address example:</b>\n<code>{format_address_for_display(recent, 30)}</code>\n"
                
                await event.reply(
                    f"{BUYER_ADDRESS_PROMPT}\n\n"
                    f"<b>Guidelines:</b>\n"
                    f"• Minimum {MIN_ADDRESS_LENGTH} characters\n"
                    f"• Maximum {MAX_ADDRESS_LENGTH} characters\n"
                    f"• Can include letters, numbers, and special characters\n"
                    f"• Will be visible to all participants\n"
                    f"{example_text}",
                    parse_mode='html'
                )
            
            # Set user state to wait for buyer address
            client.address_state[user.id] = {
                "type": "buyer",
                "group_id": group_id,
                "chat_id": event.chat_id,
                "timestamp": time.time(),
                "original_role": user_role,
                "original_name": user_name,
                "message_id": event.id
            }
            
            # Store temp data for potential recovery
            client.address_temp_data[user.id] = {
                "last_command": "buyer",
                "timestamp": time.time(),
                "chat_id": event.chat_id
            }
            
            # Update stats
            update_address_stats('view', 'buyer')
            
            # Performance tracking
            elapsed = time.time() - start_time
            print(f"[ BUYER ] Handler completed in {elapsed:.2f}s")
            
        except FloodWaitError as e:
            print(f"[FLOOD] Rate limited: {e.seconds}s")
            await event.reply(f"⚠️ Too many requests. Please wait {e.seconds} seconds.")
        except Exception as e:
            print(f"[ERROR] /buyer handler: {e}")
            import traceback
            traceback.print_exc()
            await event.reply("❌ An error occurred. Please try again later.")
    
    @client.on(events.NewMessage(pattern='/seller'))
    async def seller_address_handler(event):
        """Handle /seller command - Set seller address"""
        try:
            # Start time for performance tracking
            start_time = time.time()
            
            # Get user and chat info
            user = await event.get_sender()
            chat = await event.get_chat()
            
            if not user or not chat:
                await event.reply("❌ Could not identify user or chat.")
                return
            
            # Check if user is blacklisted
            is_blocked, reason = is_blacklisted(user)
            if is_blocked:
                await event.reply(f"❌ You are blacklisted: {reason}")
                return
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            print(f"[ SELLER ] Command from user {user.id} in chat {raw_chat_id}")
            print(f"[ SELLER ] Cleaned group_id: {group_id}")
            print(f"[ SELLER ] User details - Username: {user.username}, First: {user.first_name}")
            
            # Load roles with cache
            roles = load_user_roles(use_cache=True)
            
            # Debug: Print all stored role keys
            print(f"[ SELLER ] Stored role keys: {list(roles.keys())}")
            
            # Check if group exists in roles
            if group_id not in roles:
                print(f"[ SELLER ] Group {group_id} not found in roles")
                
                # Try to find by name as fallback
                found = False
                chat_title = getattr(chat, 'title', '')
                if chat_title:
                    for key, data in roles.items():
                        if data.get('name') == chat_title:
                            group_id = key
                            found = True
                            print(f"[ SELLER ] Found group by name: {key}")
                            break
                
                if not found:
                    await event.reply(
                        "❌ No active escrow session found in this group.\n\n"
                        "Use /begin to start a session first.",
                        parse_mode='html'
                    )
                    return
            
            # Get roles for this group
            group_roles = roles.get(group_id, {})
            
            # Check if user has a role
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                print(f"[ ⚠️ ] User {user.id} has no role in chat {group_id}")
                
                # List all users in this group for debugging
                print(f"[ SELLER ] Users in group {group_id}: {list(group_roles.keys())}")
                
                await event.reply(
                    "❌ You don't have a role in this escrow session.\n\n"
                    "Only the designated buyer or seller can set addresses.\n\n"
                    "If you believe this is an error:\n"
                    "1️⃣ Check that you are one of the two selected participants\n"
                    "2️⃣ The session may have expired\n"
                    "3️⃣ Use /begin to start a new session",
                    parse_mode='html'
                )
                return
            
            user_role = user_data.get("role")
            user_name = user_data.get("name", get_user_display(user))
            
            if user_role != "seller":
                print(f"[ ⚠️ ] User {user.id} is {user_role}, not seller")
                await event.reply(
                    f"❌ Only the seller can set the seller address.\n\n"
                    f"You are registered as: <b>{user_role.upper()}</b>\n\n"
                    f"Use /buyer if you are the buyer, or /addresses to view addresses.",
                    parse_mode='html'
                )
                return
            
            # Load addresses
            addresses = load_addresses(use_cache=True)
            user_addresses = addresses.get(str(user.id), {})
            user_address = user_addresses.get("seller_address")
            
            # Load address history for suggestions
            history = load_address_history()
            user_history = history.get(str(user.id), [])
            seller_history = [h for h in user_history if h.get('type') == 'seller']
            
            # Build response message
            if user_address:
                # Show existing address with preview
                preview = format_address_for_display(user_address)
                await event.reply(
                    f"📋 <b>Your Current Seller Address</b>\n\n"
                    f"<code>{user_address}</code>\n\n"
                    f"<b>Preview:</b> {preview}\n"
                    f"<b>Length:</b> {len(user_address)} characters\n"
                    f"<b>Set on:</b> {user_addresses.get('seller_updated', 'Unknown')}\n\n"
                    f"Do you want to update it?\n\n"
                    f"Send your new address or type /cancel to keep current.\n\n"
                    f"<i>Note: Previous addresses will be saved in your history.</i>",
                    parse_mode='html'
                )
            else:
                # Ask for address with examples
                example_text = ""
                if seller_history:
                    recent = seller_history[0]['address']
                    example_text = f"\n💡 <b>Recent address example:</b>\n<code>{format_address_for_display(recent, 30)}</code>\n"
                
                await event.reply(
                    f"{SELLER_ADDRESS_PROMPT}\n\n"
                    f"<b>Guidelines:</b>\n"
                    f"• Minimum {MIN_ADDRESS_LENGTH} characters\n"
                    f"• Maximum {MAX_ADDRESS_LENGTH} characters\n"
                    f"• Can include letters, numbers, and special characters\n"
                    f"• Will be visible to all participants\n"
                    f"{example_text}",
                    parse_mode='html'
                )
            
            # Set user state to wait for seller address
            client.address_state[user.id] = {
                "type": "seller",
                "group_id": group_id,
                "chat_id": event.chat_id,
                "timestamp": time.time(),
                "original_role": user_role,
                "original_name": user_name,
                "message_id": event.id
            }
            
            # Store temp data for potential recovery
            client.address_temp_data[user.id] = {
                "last_command": "seller",
                "timestamp": time.time(),
                "chat_id": event.chat_id
            }
            
            # Update stats
            update_address_stats('view', 'seller')
            
            # Performance tracking
            elapsed = time.time() - start_time
            print(f"[ SELLER ] Handler completed in {elapsed:.2f}s")
            
        except FloodWaitError as e:
            print(f"[FLOOD] Rate limited: {e.seconds}s")
            await event.reply(f"⚠️ Too many requests. Please wait {e.seconds} seconds.")
        except Exception as e:
            print(f"[ERROR] /seller handler: {e}")
            import traceback
            traceback.print_exc()
            await event.reply("❌ An error occurred. Please try again later.")
    
    @client.on(events.NewMessage(pattern='/addresses'))
    async def addresses_menu_handler(event):
        """Handle /addresses command - Show addresses menu"""
        try:
            # Start time for performance tracking
            start_time = time.time()
            
            # Get user and chat info
            user = await event.get_sender()
            chat = await event.get_chat()
            
            if not user or not chat:
                await event.reply("❌ Could not identify user or chat.")
                return
            
            # Check if user is blacklisted
            is_blocked, reason = is_blacklisted(user)
            if is_blocked:
                await event.reply(f"❌ You are blacklisted: {reason}")
                return
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            print(f"[ ADDRESSES ] Command from user {user.id} in chat {raw_chat_id}")
            print(f"[ ADDRESSES ] Cleaned group_id: {group_id}")
            
            # Load roles and addresses with cache
            roles = load_user_roles(use_cache=True)
            addresses = load_addresses(use_cache=True)
            
            # Get user's role in this group
            group_roles = roles.get(group_id, {})
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                await event.reply(
                    "❌ You don't have a role in this escrow session.\n\n"
                    "Use /begin to start a session first.",
                    parse_mode='html'
                )
                return
            
            user_role = user_data.get("role")
            user_name = user_data.get("name", get_user_display(user))
            
            # Get addresses for this group
            buyer_id = None
            seller_id = None
            buyer_name = None
            seller_name = None
            
            for uid, data in group_roles.items():
                if data.get("role") == "buyer":
                    buyer_id = uid
                    buyer_name = data.get("name", f"User_{uid}")
                elif data.get("role") == "seller":
                    seller_id = uid
                    seller_name = data.get("name", f"User_{uid}")
            
            # Get addresses from storage with metadata
            buyer_address = None
            seller_address = None
            buyer_updated = None
            seller_updated = None
            
            if buyer_id:
                buyer_data = addresses.get(str(buyer_id), {})
                buyer_address = buyer_data.get("buyer_address")
                buyer_updated = buyer_data.get("buyer_updated")
            
            if seller_id:
                seller_data = addresses.get(str(seller_id), {})
                seller_address = seller_data.get("seller_address")
                seller_updated = seller_data.get("seller_updated")
            
            # Format addresses display with metadata
            if buyer_address:
                buyer_preview = format_address_for_display(buyer_address)
                buyer_display = f"<code>{buyer_address}</code>\n"
                buyer_display += f"<b>Preview:</b> {buyer_preview}\n"
                if buyer_updated:
                    buyer_display += f"<b>Updated:</b> {buyer_updated}"
                else:
                    buyer_display += f"<b>Status:</b> ✅ Set"
            else:
                buyer_display = "❌ <b>Not set</b>"
            
            if seller_address:
                seller_preview = format_address_for_display(seller_address)
                seller_display = f"<code>{seller_address}</code>\n"
                seller_display += f"<b>Preview:</b> {seller_preview}\n"
                if seller_updated:
                    seller_display += f"<b>Updated:</b> {seller_updated}"
                else:
                    seller_display += f"<b>Status:</b> ✅ Set"
            else:
                seller_display = "❌ <b>Not set</b>"
            
            # Create message with participant names
            message = f"<b>📋 ESCROW ADDRESSES</b>\n\n"
            message += f"<b>Group:</b> {getattr(chat, 'title', 'Unknown')}\n"
            message += f"<b>Your role:</b> {user_role.upper()}\n\n"
            
            message += f"<b>👤 BUYER</b> - {buyer_name}\n"
            message += f"{buyer_display}\n\n"
            
            message += f"<b>👤 SELLER</b> - {seller_name}\n"
            message += f"{seller_display}\n\n"
            
            message += f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            
            # Get buttons based on user role
            buttons = get_addresses_menu_buttons(user_role)
            
            await event.reply(message, buttons=buttons, parse_mode='html')
            
            # Update stats
            update_address_stats('view')
            
            # Performance tracking
            elapsed = time.time() - start_time
            print(f"[ ADDRESSES ] Handler completed in {elapsed:.2f}s")
            
        except FloodWaitError as e:
            print(f"[FLOOD] Rate limited: {e.seconds}s")
            await event.reply(f"⚠️ Too many requests. Please wait {e.seconds} seconds.")
        except Exception as e:
            print(f"[ERROR] /addresses handler: {e}")
            import traceback
            traceback.print_exc()
            await event.reply("❌ An error occurred. Please try again later.")
    
    @client.on(events.CallbackQuery(pattern=b'address_my'))
    async def address_my_handler(event):
        """Handle 'My Address' button - Show user's own address"""
        try:
            user = await event.get_sender()
            
            if not user:
                await event.answer("❌ Could not identify user", alert=True)
                return
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            # Load roles
            roles = load_user_roles()
            group_roles = roles.get(group_id, {})
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                await event.answer("❌ You don't have a role in this session", alert=True)
                return
            
            user_role = user_data.get("role")
            user_name = user_data.get("name", get_user_display(user))
            
            # Load addresses
            addresses = load_addresses()
            user_addresses = addresses.get(str(user.id), {})
            
            if user_role == "buyer":
                address = user_addresses.get("buyer_address")
                address_type = "Buyer"
                updated = user_addresses.get("buyer_updated")
            else:
                address = user_addresses.get("seller_address")
                address_type = "Seller"
                updated = user_addresses.get("seller_updated")
            
            if address:
                # Format message with address details
                message = f"<b>Your {address_type} Address</b>\n\n"
                message += f"<code>{address}</code>\n\n"
                message += f"<b>Length:</b> {len(address)} characters\n"
                if updated:
                    message += f"<b>Last updated:</b> {updated}\n"
                message += f"\n<i>This address is visible to all participants.</i>"
                
                await event.edit(message, buttons=get_back_button(), parse_mode='html')
            else:
                await event.answer(
                    f"❌ You haven't set your {address_type} address yet. Use /{user_role} to set it.",
                    alert=True
                )
            
            # Update stats
            update_address_stats('view')
                
        except Exception as e:
            print(f"[ERROR] address_my handler: {e}")
            await event.answer("❌ Error displaying address", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_buyer'))
    async def address_buyer_handler(event):
        """Handle 'Buyer Address' button - Show buyer's address"""
        try:
            user = await event.get_sender()
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            # Load roles
            roles = load_user_roles()
            group_roles = roles.get(group_id, {})
            
            # Find buyer ID and name
            buyer_id = None
            buyer_name = None
            for uid, data in group_roles.items():
                if data.get("role") == "buyer":
                    buyer_id = uid
                    buyer_name = data.get("name", f"User_{uid}")
                    break
            
            if not buyer_id:
                await event.answer("❌ Buyer not found in this session", alert=True)
                return
            
            # Load addresses
            addresses = load_addresses()
            buyer_data = addresses.get(str(buyer_id), {})
            buyer_address = buyer_data.get("buyer_address")
            buyer_updated = buyer_data.get("buyer_updated")
            
            if buyer_address:
                # Format message with address details
                message = f"<b>👤 Buyer: {buyer_name}</b>\n\n"
                message += f"<code>{buyer_address}</code>\n\n"
                message += f"<b>Length:</b> {len(buyer_address)} characters\n"
                if buyer_updated:
                    message += f"<b>Set on:</b> {buyer_updated}\n"
                
                await event.edit(message, buttons=get_back_button(), parse_mode='html')
            else:
                await event.answer(
                    "❌ Buyer hasn't set their address yet",
                    alert=True
                )
            
            # Update stats
            update_address_stats('view')
                
        except Exception as e:
            print(f"[ERROR] address_buyer handler: {e}")
            await event.answer("❌ Error displaying buyer address", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_seller'))
    async def address_seller_handler(event):
        """Handle 'Seller Address' button - Show seller's address"""
        try:
            user = await event.get_sender()
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            # Load roles
            roles = load_user_roles()
            group_roles = roles.get(group_id, {})
            
            # Find seller ID and name
            seller_id = None
            seller_name = None
            for uid, data in group_roles.items():
                if data.get("role") == "seller":
                    seller_id = uid
                    seller_name = data.get("name", f"User_{uid}")
                    break
            
            if not seller_id:
                await event.answer("❌ Seller not found in this session", alert=True)
                return
            
            # Load addresses
            addresses = load_addresses()
            seller_data = addresses.get(str(seller_id), {})
            seller_address = seller_data.get("seller_address")
            seller_updated = seller_data.get("seller_updated")
            
            if seller_address:
                # Format message with address details
                message = f"<b>👤 Seller: {seller_name}</b>\n\n"
                message += f"<code>{seller_address}</code>\n\n"
                message += f"<b>Length:</b> {len(seller_address)} characters\n"
                if seller_updated:
                    message += f"<b>Set on:</b> {seller_updated}\n"
                
                await event.edit(message, buttons=get_back_button(), parse_mode='html')
            else:
                await event.answer(
                    "❌ Seller hasn't set their address yet",
                    alert=True
                )
            
            # Update stats
            update_address_stats('view')
                
        except Exception as e:
            print(f"[ERROR] address_seller handler: {e}")
            await event.answer("❌ Error displaying seller address", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_reset'))
    async def address_reset_handler(event):
        """Handle 'Reset Addresses' button - Reset both addresses"""
        try:
            user = await event.get_sender()
            
            if not user:
                await event.answer("❌ Could not identify user", alert=True)
                return
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            # Load roles
            roles = load_user_roles()
            group_roles = roles.get(group_id, {})
            
            # Check if user is admin or creator
            chat = await event.get_chat()
            is_creator = False
            is_admin = False
            
            try:
                participants = await client.get_participants(chat)
                for participant in participants:
                    if participant.id == user.id:
                        if hasattr(participant, 'participant'):
                            if isinstance(participant.participant, ChannelParticipantCreator):
                                is_creator = True
                                break
                            elif hasattr(participant.participant, 'admin_rights'):
                                if participant.participant.admin_rights:
                                    is_admin = True
                                    break
            except Exception as e:
                print(f"[ERROR] Checking admin status: {e}")
            
            if not (is_creator or is_admin):
                await event.answer("❌ Only group creator or admin can reset addresses", alert=True)
                return
            
            # Load addresses
            addresses = load_addresses()
            
            # Remove addresses for this group's participants
            reset_count = 0
            reset_details = []
            
            for uid in group_roles.keys():
                if uid in addresses:
                    changed = False
                    if "buyer_address" in addresses[uid]:
                        # Save to history before removing
                        if addresses[uid]["buyer_address"]:
                            add_to_address_history(uid, "buyer", addresses[uid]["buyer_address"])
                        del addresses[uid]["buyer_address"]
                        if "buyer_updated" in addresses[uid]:
                            del addresses[uid]["buyer_updated"]
                        changed = True
                        reset_details.append(f"Buyer {uid}")
                    
                    if "seller_address" in addresses[uid]:
                        # Save to history before removing
                        if addresses[uid]["seller_address"]:
                            add_to_address_history(uid, "seller", addresses[uid]["seller_address"])
                        del addresses[uid]["seller_address"]
                        if "seller_updated" in addresses[uid]:
                            del addresses[uid]["seller_updated"]
                        changed = True
                        reset_details.append(f"Seller {uid}")
                    
                    if changed:
                        reset_count += 1
                    
                    # If user has no addresses left, remove them
                    if not addresses[uid]:
                        del addresses[uid]
            
            save_addresses(addresses)
            
            # Format reset details
            details_text = "\n".join(reset_details[:5])
            if len(reset_details) > 5:
                details_text += f"\n... and {len(reset_details) - 5} more"
            
            await event.edit(
                f"✅ <b>Addresses Reset Complete</b>\n\n"
                f"<b>Total resets:</b> {reset_count}\n"
                f"<b>Groups affected:</b> 1\n\n"
                f"<b>Details:</b>\n{details_text if details_text else 'No addresses were reset'}",
                buttons=get_back_button(),
                parse_mode='html'
            )
            
            print(f"[ ADDRESSES ] Reset {reset_count} addresses by {user.id}")
            
            # Update stats
            update_address_stats('reset')
            
        except Exception as e:
            print(f"[ERROR] address_reset handler: {e}")
            import traceback
            traceback.print_exc()
            await event.answer("❌ Error resetting addresses", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_back'))
    async def address_back_handler(event):
        """Handle back button from addresses menu"""
        try:
            user = await event.get_sender()
            
            if not user:
                await event.answer("❌ Could not identify user", alert=True)
                return
            
            # Get and clean group ID
            raw_chat_id = str(event.chat_id)
            group_id = clean_group_id(raw_chat_id)
            
            # Load roles
            roles = load_user_roles()
            group_roles = roles.get(group_id, {})
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                await event.answer("❌ You don't have a role", alert=True)
                return
            
            user_role = user_data.get("role")
            
            # Get addresses
            addresses = load_addresses()
            
            # Find buyer and seller IDs and names
            buyer_id = None
            seller_id = None
            buyer_name = None
            seller_name = None
            
            for uid, data in group_roles.items():
                if data.get("role") == "buyer":
                    buyer_id = uid
                    buyer_name = data.get("name", f"User_{uid}")
                elif data.get("role") == "seller":
                    seller_id = uid
                    seller_name = data.get("name", f"User_{uid}")
            
            # Get addresses
            buyer_address = None
            seller_address = None
            
            if buyer_id:
                buyer_data = addresses.get(str(buyer_id), {})
                buyer_address = buyer_data.get("buyer_address")
            
            if seller_id:
                seller_data = addresses.get(str(seller_id), {})
                seller_address = seller_data.get("seller_address")
            
            # Format display
            buyer_display = f"<code>{buyer_address}</code>" if buyer_address else "❌ Not set"
            seller_display = f"<code>{seller_address}</code>" if seller_address else "❌ Not set"
            
            message = f"<b>📋 ESCROW ADDRESSES</b>\n\n"
            message += f"<b>👤 BUYER</b> - {buyer_name}\n"
            message += f"{buyer_display}\n\n"
            message += f"<b>👤 SELLER</b> - {seller_name}\n"
            message += f"{seller_display}"
            
            buttons = get_addresses_menu_buttons(user_role)
            
            await event.edit(message, buttons=buttons, parse_mode='html')
            
        except Exception as e:
            print(f"[ERROR] address_back handler: {e}")
            await event.answer("❌ Error", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_history'))
    async def address_history_handler(event):
        """Handle 'Address History' button - Show address history"""
        try:
            user = await event.get_sender()
            
            if not user:
                await event.answer("❌ Could not identify user", alert=True)
                return
            
            # Load address history
            history = load_address_history()
            user_history = history.get(str(user.id), [])
            
            if not user_history:
                await event.answer("📭 No address history found", alert=True)
                return
            
            # Format history message
            message = "<b>📋 Your Address History</b>\n\n"
            
            for i, entry in enumerate(user_history[:10], 1):
                addr_type = entry.get('type', 'unknown').upper()
                addr = entry.get('address', '')
                timestamp = entry.get('timestamp', 0)
                
                # Format date
                if timestamp:
                    date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                else:
                    date = 'Unknown date'
                
                # Truncate address for display
                display_addr = format_address_for_display(addr, 30)
                
                message += f"{i}. <b>{addr_type}</b> - {display_addr}\n"
                message += f"   <i>{date}</i>\n\n"
            
            message += f"<i>Showing last {min(10, len(user_history))} of {len(user_history)} entries</i>"
            
            await event.edit(message, buttons=get_back_button(), parse_mode='html')
            
        except Exception as e:
            print(f"[ERROR] address_history handler: {e}")
            await event.answer("❌ Error loading history", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_stats'))
    async def address_stats_handler(event):
        """Handle 'Statistics' button - Show address statistics"""
        try:
            user = await event.get_sender()
            
            if not user:
                await event.answer("❌ Could not identify user", alert=True)
                return
            
            # Load stats
            stats = load_address_stats()
            addresses = load_addresses()
            roles = load_user_roles()
            
            # Calculate statistics
            total_addresses = len(addresses)
            total_users = len(set([uid for uid in addresses.keys()]))
            total_roles = sum(len(g) for g in roles.values())
            
            # Count by type
            buyer_count = sum(1 for u in addresses.values() if 'buyer_address' in u)
            seller_count = sum(1 for u in addresses.values() if 'seller_address' in u)
            
            # Daily stats
            today = datetime.now().strftime('%Y-%m-%d')
            daily = stats.get('daily', {}).get(today, {})
            
            message = "<b>📊 Address Statistics</b>\n\n"
            
            message += f"<b>Overall:</b>\n"
            message += f"• Total addresses: {total_addresses}\n"
            message += f"• Unique users: {total_users}\n"
            message += f"• Active roles: {total_roles}\n"
            message += f"• Buyers: {buyer_count}\n"
            message += f"• Sellers: {seller_count}\n\n"
            
            message += f"<b>Today ({today}):</b>\n"
            message += f"• Addresses set: {daily.get('sets', 0)}\n"
            message += f"• Updates: {daily.get('updates', 0)}\n"
            message += f"• Views: {daily.get('views', 0)}\n\n"
            
            message += f"<b>All time:</b>\n"
            message += f"• Total actions: {stats.get('total_actions', 0)}"
            
            await event.edit(message, buttons=get_back_button(), parse_mode='html')
            
        except Exception as e:
            print(f"[ERROR] address_stats handler: {e}")
            await event.answer("❌ Error loading statistics", alert=True)
    
    # Handle address input messages
    @client.on(events.NewMessage)
    async def handle_address_input(event):
        """Handle user input for addresses"""
        try:
            # Skip commands
            if event.text and event.text.startswith('/'):
                return
            
            # Check if user is in address input state
            if not hasattr(client, 'address_state'):
                return
            
            user_id = event.sender_id
            
            if user_id not in client.address_state:
                return
            
            # Get state
            state = client.address_state[user_id]
            address_type = state.get("type")  # "buyer" or "seller"
            group_id = state.get("group_id")
            chat_id = state.get("chat_id")
            timestamp = state.get("timestamp", 0)
            original_role = state.get("original_role")
            
            # Check if this is the correct chat
            if event.chat_id != chat_id:
                return
            
            # Check if state is expired
            if time.time() - timestamp > ADDRESS_TIMEOUT:
                del client.address_state[user_id]
                await event.reply(ADDRESS_EXPIRED_MESSAGE)
                return
            
            # Get the address text
            address_text = event.text.strip()
            
            # Check for cancel command
            if address_text.lower() == '/cancel':
                del client.address_state[user_id]
                await event.reply("✅ Address input cancelled.")
                return
            
            # Validate address
            is_valid, validation_message = validate_address(address_text)
            if not is_valid:
                await event.reply(
                    f"❌ {validation_message}\n\n"
                    f"Please send a valid address or type /cancel to cancel."
                )
                return
            
            # Check length
            if len(address_text) < MIN_ADDRESS_LENGTH:
                await event.reply(
                    f"❌ Address is too short (minimum {MIN_ADDRESS_LENGTH} characters).\n"
                    f"Please send a valid address or type /cancel to cancel."
                )
                return
            
            if len(address_text) > MAX_ADDRESS_LENGTH:
                await event.reply(
                    f"❌ Address is too long (maximum {MAX_ADDRESS_LENGTH} characters).\n"
                    f"Please send a shorter address or type /cancel to cancel."
                )
                return
            
            # Load roles to verify user still has role
            roles = load_user_roles()
            group_roles = roles.get(group_id, {})
            user_data = group_roles.get(str(user_id))
            
            if not user_data:
                del client.address_state[user_id]
                await event.reply(
                    "❌ Your role has been removed from this session.\n"
                    "Address cannot be saved."
                )
                return
            
            user_role = user_data.get("role")
            
            # Verify role matches address type and hasn't changed
            if (address_type == "buyer" and user_role != "buyer") or \
               (address_type == "seller" and user_role != "seller"):
                del client.address_state[user_id]
                await event.reply(
                    "❌ Your role has changed. Please use the appropriate command again."
                )
                return
            
            # Load existing addresses
            addresses = load_addresses()
            
            # Initialize user data if not exists
            if str(user_id) not in addresses:
                addresses[str(user_id)] = {}
            
            # Check if address already exists and is the same
            existing = addresses[str(user_id)].get(f"{address_type}_address")
            if existing and existing == address_text:
                await event.reply(
                    "⚠️ This is your current address. No changes made.\n\n"
                    "Use /addresses to view all addresses."
                )
                del client.address_state[user_id]
                return
            
            # Save old address to history before updating
            if existing:
                add_to_address_history(user_id, address_type, existing)
                action = "updated"
                update_address_stats('update', address_type)
            else:
                action = "set"
                update_address_stats('set', address_type)
            
            # Save address based on type
            addresses[str(user_id)][f"{address_type}_address"] = address_text
            addresses[str(user_id)][f"{address_type}_updated"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Save to file
            save_addresses(addresses)
            
            # Clear state
            del client.address_state[user_id]
            
            # Send confirmation
            preview = format_address_for_display(address_text)
            await event.reply(
                ADDRESS_SAVED_MESSAGE.format(
                    address_type=address_type.upper(),
                    address=address_text,
                    preview=preview,
                    action=action
                ),
                parse_mode='html'
            )
            
            print(f"[ADDRESS] {address_type.upper()} address {action} for user {user_id}")
            
            # Check if both addresses are now set and notify
            try:
                # Find other participant
                other_id = None
                other_role = None
                
                for uid, data in group_roles.items():
                    if data.get("role") != user_role:
                        other_id = uid
                        other_role = data.get("role")
                        break
                
                if other_id:
                    other_data = addresses.get(str(other_id), {})
                    other_addr = other_data.get(f"{other_role}_address")
                    
                    if other_addr:
                        # Both addresses are set
                        await client.send_message(
                            chat_id,
                            ADDRESS_BOTH_SET_MESSAGE.format(
                                buyer_role="BUYER" if user_role == "buyer" else "SELLER",
                                seller_role="SELLER" if user_role == "buyer" else "BUYER"
                            ),
                            parse_mode='html'
                        )
                        
                        print(f"[ADDRESS] Both addresses set in group {group_id}")
            except Exception as e:
                print(f"[ERROR] Notifying about both addresses: {e}")
            
        except Exception as e:
            print(f"[ERROR] handle_address_input: {e}")
            import traceback
            traceback.print_exc()
            # Clear state on error to prevent getting stuck
            if hasattr(client, 'address_state') and 'user_id' in locals() and user_id in client.address_state:
                del client.address_state[user_id]
            await event.reply("❌ An error occurred while saving your address. Please try again.")
    
    # Periodic cleanup task
    async def cleanup_expired_states():
        """Clean up expired address input states periodically"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                if not hasattr(client, 'address_state'):
                    continue
                
                current_time = time.time()
                expired = []
                
                for user_id, state in client.address_state.items():
                    timestamp = state.get("timestamp", 0)
                    if current_time - timestamp > ADDRESS_TIMEOUT:
                        expired.append(user_id)
                
                for user_id in expired:
                    del client.address_state[user_id]
                    print(f"[CLEANUP] Removed expired address state for user {user_id}")
                    
            except Exception as e:
                print(f"[ERROR] Cleanup task: {e}")
                await asyncio.sleep(60)
    
    # Start cleanup task
    asyncio.create_task(cleanup_expired_states())
    
    print("[HANDLERS] Address handlers setup complete")
    print(f"[HANDLERS] • Buyer/Seller commands registered")
    print(f"[HANDLERS] • Addresses menu registered")
    print(f"[HANDLERS] • Address input handler registered")
    print(f"[HANDLERS] • Cleanup task started")
    
    return client
