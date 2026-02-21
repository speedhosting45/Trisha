"""
Address management handlers for Escrow Bot
Complete working version with group ID cleaning fix
"""
import logging
from telethon import events
from telethon.tl import types
from telethon.tl.types import ChannelParticipantCreator
import json
import os
import time
import re

# Import utilities
from utils.texts import (
    BUYER_ADDRESS_PROMPT, SELLER_ADDRESS_PROMPT, ADDRESSES_MENU_TEXT,
    ADDRESS_SAVED_MESSAGE, NO_ADDRESS_MESSAGE, ADDRESSES_RESET_MESSAGE
)
from utils.buttons import get_addresses_menu_buttons, get_back_button
from utils.blacklist import is_blacklisted

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)

# Data files
USER_ADDRESSES_FILE = 'data/user_addresses.json'
USER_ROLES_FILE = 'data/user_roles.json'

def load_addresses():
    """Load user addresses data"""
    try:
        if os.path.exists(USER_ADDRESSES_FILE):
            with open(USER_ADDRESSES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"[ERROR] Loading addresses: {e}")
        return {}

def save_addresses(addresses):
    """Save user addresses data"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(USER_ADDRESSES_FILE, 'w') as f:
            json.dump(addresses, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Saving addresses: {e}")

def load_user_roles():
    """Load user roles data"""
    try:
        if os.path.exists(USER_ROLES_FILE):
            with open(USER_ROLES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"[ERROR] Loading roles: {e}")
        return {}

def save_user_roles(roles):
    """Save user roles data"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(USER_ROLES_FILE, 'w') as f:
            json.dump(roles, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Saving roles: {e}")

def get_user_display(user_obj):
    """Get clean display name for user"""
    try:
        # Get username if exists
        if hasattr(user_obj, 'username') and user_obj.username:
            username = user_obj.username.strip()
            if username:
                return f"@{username}"
        
        # Get first name
        first_name = getattr(user_obj, 'first_name', '')
        if first_name:
            first_name = first_name.strip()
        
        # Get last name
        last_name = getattr(user_obj, 'last_name', '')
        if last_name:
            last_name = last_name.strip()
        
        # Combine names
        if first_name and last_name:
            full_name = f"{first_name} {last_name}"
        elif first_name:
            full_name = first_name
        elif last_name:
            full_name = last_name
        else:
            full_name = f"User_{user_obj.id}"
        
        # Clean special characters
        full_name = re.sub(r'[^\w\s@#\-\.]', '', full_name)
        full_name = full_name.strip()
        
        # If still empty, use user ID
        if not full_name:
            full_name = f"User_{user_obj.id}"
            
        return full_name
        
    except Exception as e:
        print(f"[ERROR] Getting user display: {e}")
        return f"User_{getattr(user_obj, 'id', 'unknown')}"

def clean_group_id(chat_id):
    """Clean group ID by removing -100 prefix if present"""
    try:
        chat_id = str(chat_id)
        # Remove -100 prefix for supergroups
        if chat_id.startswith("-100"):
            return chat_id[4:]
        return chat_id
    except Exception as e:
        print(f"[ERROR] Cleaning group ID: {e}")
        return str(chat_id)

def setup_address_handlers(client):
    """Setup all address-related handlers"""
    
    # Initialize address state if not exists
    if not hasattr(client, 'address_state'):
        client.address_state = {}
    
    @client.on(events.NewMessage(pattern='/buyer'))
    async def buyer_address_handler(event):
        """Handle /buyer command - Set buyer address"""
        try:
            user = await event.get_sender()
            chat = await event.get_chat()
            
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
            
            # Load roles
            roles = load_user_roles()
            
            # Debug: Print all stored role keys
            print(f"[ BUYER ] Stored role keys: {list(roles.keys())}")
            
            # Get roles for this group
            group_roles = roles.get(group_id, {})
            
            # Check if user has a role
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                print(f"[ ⚠️ ] User {user.id} has no role in chat {group_id}")
                await event.reply(
                    "❌ You don't have a role in this escrow session.\n\n"
                    "Only the designated buyer or seller can set addresses.\n\n"
                    "If you believe this is an error, please use /begin to start a new session.",
                    parse_mode='html'
                )
                return
            
            user_role = user_data.get("role")
            
            if user_role != "buyer":
                print(f"[ ⚠️ ] User {user.id} is {user_role}, not buyer")
                await event.reply(
                    "❌ Only the buyer can set the buyer address.\n\n"
                    "Use /seller if you are the seller, or /addresses to view addresses.",
                    parse_mode='html'
                )
                return
            
            # Check if address already exists
            addresses = load_addresses()
            user_addresses = addresses.get(str(user.id), {})
            user_address = user_addresses.get("buyer_address")
            
            if user_address:
                # Show existing address and ask if they want to change it
                await event.reply(
                    f"📋 Your current buyer address is:\n<code>{user_address}</code>\n\n"
                    f"Do you want to update it?\n\n"
                    f"Send your new address or type /cancel to keep current.",
                    parse_mode='html'
                )
            else:
                # Ask for address
                await event.reply(
                    BUYER_ADDRESS_PROMPT,
                    parse_mode='html'
                )
            
            # Set user state to wait for buyer address
            client.address_state[user.id] = {
                "type": "buyer",
                "group_id": group_id,
                "chat_id": event.chat_id,
                "timestamp": time.time()
            }
            
            print(f"[ BUYER ] Waiting for address from user {user.id}")
            
        except Exception as e:
            print(f"[ERROR] /buyer handler: {e}")
            import traceback
            traceback.print_exc()
            await event.reply("❌ An error occurred. Please try again.")
    
    @client.on(events.NewMessage(pattern='/seller'))
    async def seller_address_handler(event):
        """Handle /seller command - Set seller address"""
        try:
            user = await event.get_sender()
            chat = await event.get_chat()
            
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
            
            # Load roles
            roles = load_user_roles()
            
            # Debug: Print all stored role keys
            print(f"[ SELLER ] Stored role keys: {list(roles.keys())}")
            
            # Get roles for this group
            group_roles = roles.get(group_id, {})
            
            # Check if user has a role
            user_data = group_roles.get(str(user.id))
            
            if not user_data:
                print(f"[ ⚠️ ] User {user.id} has no role in chat {group_id}")
                await event.reply(
                    "❌ You don't have a role in this escrow session.\n\n"
                    "Only the designated buyer or seller can set addresses.\n\n"
                    "If you believe this is an error, please use /begin to start a new session.",
                    parse_mode='html'
                )
                return
            
            user_role = user_data.get("role")
            
            if user_role != "seller":
                print(f"[ ⚠️ ] User {user.id} is {user_role}, not seller")
                await event.reply(
                    "❌ Only the seller can set the seller address.\n\n"
                    "Use /buyer if you are the buyer, or /addresses to view addresses.",
                    parse_mode='html'
                )
                return
            
            # Check if address already exists
            addresses = load_addresses()
            user_addresses = addresses.get(str(user.id), {})
            user_address = user_addresses.get("seller_address")
            
            if user_address:
                # Show existing address and ask if they want to change it
                await event.reply(
                    f"📋 Your current seller address is:\n<code>{user_address}</code>\n\n"
                    f"Do you want to update it?\n\n"
                    f"Send your new address or type /cancel to keep current.",
                    parse_mode='html'
                )
            else:
                # Ask for address
                await event.reply(
                    SELLER_ADDRESS_PROMPT,
                    parse_mode='html'
                )
            
            # Set user state to wait for seller address
            client.address_state[user.id] = {
                "type": "seller",
                "group_id": group_id,
                "chat_id": event.chat_id,
                "timestamp": time.time()
            }
            
            print(f"[ SELLER ] Waiting for address from user {user.id}")
            
        except Exception as e:
            print(f"[ERROR] /seller handler: {e}")
            import traceback
            traceback.print_exc()
            await event.reply("❌ An error occurred. Please try again.")
    
    @client.on(events.NewMessage(pattern='/addresses'))
    async def addresses_menu_handler(event):
        """Handle /addresses command - Show addresses menu"""
        try:
            user = await event.get_sender()
            chat = await event.get_chat()
            
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
            
            # Load roles and addresses
            roles = load_user_roles()
            addresses = load_addresses()
            
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
            
            for uid, data in group_roles.items():
                if data.get("role") == "buyer":
                    buyer_id = uid
                elif data.get("role") == "seller":
                    seller_id = uid
            
            # Get addresses from storage
            buyer_address = None
            seller_address = None
            
            if buyer_id:
                buyer_data = addresses.get(str(buyer_id), {})
                buyer_address = buyer_data.get("buyer_address")
            
            if seller_id:
                seller_data = addresses.get(str(seller_id), {})
                seller_address = seller_data.get("seller_address")
            
            # Format addresses display
            buyer_display = f"<code>{buyer_address}</code>" if buyer_address else "❌ Not set"
            seller_display = f"<code>{seller_address}</code>" if seller_address else "❌ Not set"
            
            # Create message
            message = ADDRESSES_MENU_TEXT.format(
                buyer_display=buyer_display,
                seller_display=seller_display
            )
            
            # Get buttons based on user role
            buttons = get_addresses_menu_buttons(user_role)
            
            await event.reply(message, buttons=buttons, parse_mode='html')
            
            print(f"[ ADDRESSES ] Menu shown to {user_role} {user.id}")
            
        except Exception as e:
            print(f"[ERROR] /addresses handler: {e}")
            import traceback
            traceback.print_exc()
            await event.reply("❌ An error occurred.")
    
    @client.on(events.CallbackQuery(pattern=b'address_my'))
    async def address_my_handler(event):
        """Handle 'My Address' button - Show user's own address"""
        try:
            user = await event.get_sender()
            
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
            
            # Load addresses
            addresses = load_addresses()
            user_addresses = addresses.get(str(user.id), {})
            
            if user_role == "buyer":
                address = user_addresses.get("buyer_address")
                address_type = "Buyer"
            else:
                address = user_addresses.get("seller_address")
                address_type = "Seller"
            
            if address:
                await event.answer(
                    f"Your {address_type} Address: {address}",
                    alert=True
                )
            else:
                await event.answer(
                    f"❌ You haven't set your {address_type} address yet. Use /{user_role} to set it.",
                    alert=True
                )
                
        except Exception as e:
            print(f"[ERROR] address_my handler: {e}")
            await event.answer("❌ Error", alert=True)
    
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
            
            # Find buyer ID
            buyer_id = None
            for uid, data in group_roles.items():
                if data.get("role") == "buyer":
                    buyer_id = uid
                    break
            
            if not buyer_id:
                await event.answer("❌ Buyer not found in this session", alert=True)
                return
            
            # Load addresses
            addresses = load_addresses()
            buyer_data = addresses.get(str(buyer_id), {})
            buyer_address = buyer_data.get("buyer_address")
            
            if buyer_address:
                await event.answer(
                    f"Buyer Address: {buyer_address}",
                    alert=True
                )
            else:
                await event.answer(
                    "❌ Buyer hasn't set their address yet",
                    alert=True
                )
                
        except Exception as e:
            print(f"[ERROR] address_buyer handler: {e}")
            await event.answer("❌ Error", alert=True)
    
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
            
            # Find seller ID
            seller_id = None
            for uid, data in group_roles.items():
                if data.get("role") == "seller":
                    seller_id = uid
                    break
            
            if not seller_id:
                await event.answer("❌ Seller not found in this session", alert=True)
                return
            
            # Load addresses
            addresses = load_addresses()
            seller_data = addresses.get(str(seller_id), {})
            seller_address = seller_data.get("seller_address")
            
            if seller_address:
                await event.answer(
                    f"Seller Address: {seller_address}",
                    alert=True
                )
            else:
                await event.answer(
                    "❌ Seller hasn't set their address yet",
                    alert=True
                )
                
        except Exception as e:
            print(f"[ERROR] address_seller handler: {e}")
            await event.answer("❌ Error", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_reset'))
    async def address_reset_handler(event):
        """Handle 'Reset Addresses' button - Reset both addresses"""
        try:
            user = await event.get_sender()
            
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
            except Exception as e:
                print(f"[ERROR] Checking admin status: {e}")
            
            if not (is_creator or is_admin):
                await event.answer("❌ Only group creator or admin can reset addresses", alert=True)
                return
            
            # Load addresses
            addresses = load_addresses()
            
            # Remove addresses for this group's participants
            reset_count = 0
            for uid in group_roles.keys():
                if uid in addresses:
                    changed = False
                    if "buyer_address" in addresses[uid]:
                        del addresses[uid]["buyer_address"]
                        changed = True
                    if "seller_address" in addresses[uid]:
                        del addresses[uid]["seller_address"]
                        changed = True
                    
                    if changed:
                        reset_count += 1
                    
                    # If user has no addresses left, remove them
                    if not addresses[uid]:
                        del addresses[uid]
            
            save_addresses(addresses)
            
            await event.edit(
                ADDRESSES_RESET_MESSAGE.format(count=reset_count),
                buttons=get_back_button(),
                parse_mode='html'
            )
            
            print(f"[ ADDRESSES ] Reset {reset_count} addresses by {user.id}")
            
        except Exception as e:
            print(f"[ERROR] address_reset handler: {e}")
            import traceback
            traceback.print_exc()
            await event.answer("❌ Error", alert=True)
    
    @client.on(events.CallbackQuery(pattern=b'address_back'))
    async def address_back_handler(event):
        """Handle back button from addresses menu"""
        try:
            user = await event.get_sender()
            
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
            
            # Find buyer and seller IDs
            buyer_id = None
            seller_id = None
            
            for uid, data in group_roles.items():
                if data.get("role") == "buyer":
                    buyer_id = uid
                elif data.get("role") == "seller":
                    seller_id = uid
            
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
            
            message = ADDRESSES_MENU_TEXT.format(
                buyer_display=buyer_display,
                seller_display=seller_display
            )
            
            buttons = get_addresses_menu_buttons(user_role)
            
            await event.edit(message, buttons=buttons, parse_mode='html')
            
        except Exception as e:
            print(f"[ERROR] address_back handler: {e}")
            await event.answer("❌ Error", alert=True)
    
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
            
            # Check if this is the correct chat
            if event.chat_id != chat_id:
                return
            
            # Check if state is expired (30 minutes)
            if time.time() - timestamp > 1800:
                del client.address_state[user_id]
                await event.reply("⏰ Address input timed out. Please use /buyer or /seller again.")
                return
            
            # Get the address text
            address_text = event.text.strip()
            
            # Check for cancel command
            if address_text.lower() == '/cancel':
                del client.address_state[user_id]
                await event.reply("✅ Address update cancelled.")
                return
            
            # Basic validation
            if not address_text:
                await event.reply(
                    "❌ Address cannot be empty.\n"
                    "Please send a valid address or type /cancel to cancel."
                )
                return
            
            if len(address_text) < 5:
                await event.reply(
                    "❌ Address is too short (minimum 5 characters).\n"
                    "Please send a valid address or type /cancel to cancel."
                )
                return
            
            if len(address_text) > 500:
                await event.reply(
                    "❌ Address is too long (maximum 500 characters).\n"
                    "Please send a shorter address or type /cancel to cancel."
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
            
            # Verify role matches address type
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
            
            # Save address based on type
            if address_type == "buyer":
                addresses[str(user_id)]["buyer_address"] = address_text
                address_label = "Buyer"
            else:  # seller
                addresses[str(user_id)]["seller_address"] = address_text
                address_label = "Seller"
            
            # Save to file
            save_addresses(addresses)
            
            # Clear state
            del client.address_state[user_id]
            
            # Send confirmation
            await event.reply(
                ADDRESS_SAVED_MESSAGE.format(
                    address_type=address_label,
                    address=address_text
                ),
                parse_mode='html'
            )
            
            print(f"[ADDRESS] {address_label} address saved for user {user_id}")
            
            # Notify the other party if both addresses are set
            try:
                # Check if both addresses are now set
                buyer_id = None
                seller_id = None
                
                for uid, data in group_roles.items():
                    if data.get("role") == "buyer":
                        buyer_id = uid
                    elif data.get("role") == "seller":
                        seller_id = uid
                
                if buyer_id and seller_id:
                    buyer_addr = addresses.get(str(buyer_id), {}).get("buyer_address")
                    seller_addr = addresses.get(str(seller_id), {}).get("seller_address")
                    
                    if buyer_addr and seller_addr:
                        # Both addresses are set, notify the group
                        await client.send_message(
                            chat_id,
                            "✅ Both buyer and seller addresses have been set!\n\n"
                            "Use /addresses to view them.",
                            parse_mode='html'
                        )
            except Exception as e:
                print(f"[ERROR] Notifying about both addresses: {e}")
            
        except Exception as e:
            print(f"[ERROR] handle_address_input: {e}")
            import traceback
            traceback.print_exc()
            # Clear state on error to prevent getting stuck
            if hasattr(client, 'address_state') and user_id in client.address_state:
                del client.address_state[user_id]
            await event.reply("❌ An error occurred while saving your address. Please try again.")
    
    # Cleanup expired states periodically
    @client.on(events.NewMessage)
    async def cleanup_expired_states(event):
        """Clean up expired address input states"""
        try:
            if not hasattr(client, 'address_state'):
                return
            
            current_time = time.time()
            expired = []
            
            for user_id, state in client.address_state.items():
                timestamp = state.get("timestamp", 0)
                if current_time - timestamp > 1800:  # 30 minutes
                    expired.append(user_id)
            
            for user_id in expired:
                del client.address_state[user_id]
                print(f"[CLEANUP] Removed expired address state for user {user_id}")
                
        except Exception as e:
            print(f"[ERROR] Cleanup expired states: {e}")
    
    print("[HANDLERS] Address handlers setup complete")
    return client
