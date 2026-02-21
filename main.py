#!/usr/bin/env python3
"""
Main entry point for the Escrow Bot - Fixed version with join notifications
"""
import asyncio
import logging
import sys
from telethon import TelegramClient, events
from telethon.tl import functions, types
from telethon.tl.types import ChannelParticipantCreator, ChannelParticipantAdmin, ChannelParticipant
import json
import os
import time
import re
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Import configuration
from config import API_ID, API_HASH, BOT_TOKEN, BOT_USERNAME

# Import handlers
from handlers.start import handle_start
from handlers.create import handle_create, handle_create_p2p, handle_create_other
from handlers.stats import handle_stats
from handlers.about import handle_about
from handlers.help import handle_help
from handlers.addresses import setup_address_handlers

# Import utilities
from utils.texts import (
    START_MESSAGE, CREATE_MESSAGE, P2P_CREATED_MESSAGE, OTHER_CREATED_MESSAGE,
    WELCOME_MESSAGE, SESSION_INITIATED_MESSAGE, INSUFFICIENT_MEMBERS_MESSAGE,
    SESSION_ALREADY_INITIATED_MESSAGE, GROUP_NOT_FOUND_MESSAGE,
    MERGED_PHOTO_CAPTION, PARTICIPANTS_CONFIRMED_MESSAGE, JOIN_MESSAGE
)
from utils.buttons import get_main_menu_buttons, get_session_buttons
from utils.blacklist import is_blacklisted, add_to_blacklist, load_blacklist

# Setup logging
logging.basicConfig(
    format='[%(asctime)s] %(message)s',
    level=logging.INFO,
    datefmt='%H:%M:%S'
)

# Track groups for invite management
GROUPS_FILE = 'data/active_groups.json'
USER_ROLES_FILE = 'data/user_roles.json'

# Asset paths
BASE_START_IMAGE = "assets/base_start.png"  # For /begin preview
PFP_TEMPLATE = "assets/tg1.png"  # For final group PFP
UNKNOWN_PFP = "assets/unknown.png"
PFP_CONFIG_PATH = "config/pfp_config.json"

def load_groups():
    """Load active groups data"""
    if os.path.exists(GROUPS_FILE):
        with open(GROUPS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_groups(groups):
    """Save active groups data"""
    os.makedirs('data', exist_ok=True)
    with open(GROUPS_FILE, 'w') as f:
        json.dump(groups, f, indent=2)

def load_user_roles():
    """Load user roles data"""
    if os.path.exists(USER_ROLES_FILE):
        with open(USER_ROLES_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_roles(roles):
    """Save user roles data"""
    os.makedirs('data', exist_ok=True)
    with open(USER_ROLES_FILE, 'w') as f:
        json.dump(roles, f, indent=2)

def get_user_display(user_obj):
    """Get clean display name for user - IMPROVED VERSION"""
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
        print(f"[ERROR] Getting user display for {getattr(user_obj, 'id', 'unknown')}: {e}")
        return f"User_{getattr(user_obj, 'id', 'unknown')}"

async def set_group_photo(client, chat, photo_path):
    """Set group/channel photo with fallback methods"""
    try:
        # Upload the photo file
        file = await client.upload_file(photo_path)

        # Try normal group method first
        try:
            await client(
                functions.messages.EditChatPhotoRequest(
                    chat_id=chat.id,
                    photo=types.InputChatUploadedPhoto(file=file)
                )
            )
            print("[SUCCESS] Group photo updated via messages.EditChatPhotoRequest")
            return True
        except Exception as e1:
            print(f"[DEBUG] Normal group photo update failed: {e1}")
            
            # Fallback for supergroups / channels
            try:
                await client(
                    functions.channels.EditPhotoRequest(
                        channel=chat,
                        photo=types.InputChatUploadedPhoto(file=file)
                    )
                )
                print("[SUCCESS] Group photo updated via channels.EditPhotoRequest")
                return True
            except Exception as e2:
                print(f"[DEBUG] Channel photo update failed: {e2}")
                
                # Try the simple edit_photo method as last resort
                try:
                    await client.edit_photo(chat, photo=photo_path)
                    print("[SUCCESS] Group photo updated via edit_photo")
                    return True
                except Exception as e3:
                    print(f"[DEBUG] Simple edit_photo failed: {e3}")
                    raise Exception(f"All photo update methods failed: {e1}, {e2}, {e3}")

    except Exception as e:
        print(f"[ERROR] set_group_photo: {e}")
        raise e

async def download_profile_picture(client, user_id):
    """Download user's profile picture"""
    try:
        print(f"[PHOTO] Downloading profile picture for user_id: {user_id}")
        
        # Get user entity
        user = await client.get_entity(user_id)
        
        # Download profile photo as bytes
        photo_bytes = await client.download_profile_photo(user, file=bytes)
        
        if photo_bytes:
            # Open from BytesIO
            img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
            print(f"[PHOTO] Successfully downloaded profile picture for {user_id}")
            return img
        else:
            # No profile picture, use fallback
            print(f"[PHOTO] No profile picture for {user_id}, using fallback")
            return load_unknown_pfp()
            
    except Exception as e:
        print(f"[ERROR] Downloading profile picture for {user_id}: {e}")
        return load_unknown_pfp()

def load_unknown_pfp():
    """Load the unknown.png fallback image"""
    try:
        if os.path.exists(UNKNOWN_PFP):
            img = Image.open(UNKNOWN_PFP).convert("RGBA")
            print(f"[PHOTO] Loaded unknown.png fallback")
            return img
        else:
            # Create a simple fallback if unknown.png doesn't exist
            print(f"[WARNING] {UNKNOWN_PFP} not found, creating default fallback")
            return create_default_fallback()
    except Exception as e:
        print(f"[ERROR] Loading unknown.png: {e}")
        return create_default_fallback()

def create_default_fallback():
    """Create a default fallback image"""
    try:
        # Create a 400x400 image with question mark
        size = (400, 400)
        image = Image.new('RGBA', size, (100, 100, 100, 255))
        draw = ImageDraw.Draw(image)
        
        # Draw circle
        center_x, center_y = size[0] // 2, size[1] // 2
        radius = min(center_x, center_y) - 20
        
        draw.ellipse(
            [(center_x - radius, center_y - radius),
             (center_x + radius, center_y + radius)],
            fill=(200, 200, 200, 255)
        )
        
        # Add question mark
        try:
            font = ImageFont.truetype("arial.ttf", 120)
        except:
            font = ImageFont.load_default()
        
        draw.text(
            (center_x, center_y),
            "?",
            fill=(100, 100, 100, 255),
            anchor="mm",
            font=font
        )
        
        return image
        
    except Exception as e:
        print(f"[ERROR] Creating default fallback: {e}")
        # Last resort: solid color image
        return Image.new('RGBA', (400, 400), (100, 100, 100, 255))

def create_circular_mask(size, radius):
    """Create a circular mask"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    center_x, center_y = size[0] // 2, size[1] // 2
    draw.ellipse(
        [(center_x - radius, center_y - radius),
         (center_x + radius, center_y + radius)],
        fill=255
    )
    return mask

async def create_merged_photo(client, buyer_id, seller_id):
    """Create merged photo with both profile pictures for /begin preview"""
    try:
        # Load config
        if os.path.exists(PFP_CONFIG_PATH):
            with open(PFP_CONFIG_PATH, 'r') as f:
                config = json.load(f)
        else:
            config = {
                "BUYER_PFP": {"center_x": 470, "center_y": 384, "radius": 177},
                "SELLER_PFP": {"center_x": 920, "center_y": 384, "radius": 177}
            }
        
        # Check base image exists
        if not os.path.exists(BASE_START_IMAGE):
            print(f"[ERROR] Base image not found: {BASE_START_IMAGE}")
            return False, None, "Base image not found"
        
        # Download profile pictures
        buyer_pfp = await download_profile_picture(client, buyer_id)
        seller_pfp = await download_profile_picture(client, seller_id)
        
        # Load base image
        base_img = Image.open(BASE_START_IMAGE).convert('RGBA')
        
        # Get coordinates from config
        buyer_config = config.get("BUYER_PFP", {})
        seller_config = config.get("SELLER_PFP", {})
        
        buyer_x = buyer_config.get("center_x", 470)
        buyer_y = buyer_config.get("center_y", 384)
        buyer_radius = buyer_config.get("radius", 177)
        
        seller_x = seller_config.get("center_x", 920)
        seller_y = seller_config.get("center_y", 384)
        seller_radius = seller_config.get("radius", 177)
        
        # Resize profile pictures to match circle diameters
        buyer_size = (buyer_radius * 2, buyer_radius * 2)
        seller_size = (seller_radius * 2, seller_radius * 2)
        
        buyer_pfp = buyer_pfp.resize(buyer_size, Image.Resampling.LANCZOS)
        seller_pfp = seller_pfp.resize(seller_size, Image.Resampling.LANCZOS)
        
        # Create circular masks
        buyer_mask = create_circular_mask(buyer_size, buyer_radius)
        seller_mask = create_circular_mask(seller_size, seller_radius)
        
        # Calculate positions (center to top-left)
        buyer_pos = (buyer_x - buyer_radius, buyer_y - buyer_radius)
        seller_pos = (seller_x - seller_radius, seller_y - seller_radius)
        
        # Paste buyer PFP
        base_img.paste(buyer_pfp, buyer_pos, buyer_mask)
        
        # Paste seller PFP
        base_img.paste(seller_pfp, seller_pos, seller_mask)
        
        # Convert to bytes
        img_bytes = BytesIO()
        base_img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return True, img_bytes, "✅ Merged photo created"
        
    except Exception as e:
        print(f"[ERROR] Creating merged photo: {e}")
        import traceback
        traceback.print_exc()
        return False, None, f"❌ Error creating merged photo: {e}"

class EscrowBot:
    def __init__(self):
        self.client = TelegramClient('escrow_bot', API_ID, API_HASH)
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all event handlers"""
        
        @self.client.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await handle_start(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'create'))
        async def create_handler(event):
            await handle_create(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'create_p2p'))
        async def create_p2p_handler(event):
            await handle_create_p2p(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'create_other'))
        async def create_other_handler(event):
            await handle_create_other(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'stats'))
        async def stats_handler(event):
            await handle_stats(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'about'))
        async def about_handler(event):
            await handle_about(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'help'))
        async def help_handler(event):
            await handle_help(event)
        
        @self.client.on(events.CallbackQuery(pattern=b'back_to_main'))
        async def back_handler(event):
            try:
                await event.edit(
                    START_MESSAGE,
                    buttons=get_main_menu_buttons(),
                    parse_mode='html'
                )
            except Exception as e:
                await event.answer("❌ An error occurred.", alert=True)
        
        # Handle /begin command
        @self.client.on(events.NewMessage(pattern='/begin'))
        async def begin_handler(event):
            await self.handle_begin_command(event)
        
        # Handle role selection
        @self.client.on(events.CallbackQuery(pattern=rb'role_'))
        async def role_handler(event):
            await self.handle_role_selection(event)
        
        # Setup address handlers
        setup_address_handlers(self.client)
        
        # Handle new users joining - FIXED VERSION
        @self.client.on(events.ChatAction)
        async def handle_chat_action(event):
            await self.handle_new_member(event)
        
        # Delete system messages only
        @self.client.on(events.NewMessage)
        async def handle_all_messages(event):
            """Delete system messages only"""
            try:
                message_text = event.text or ""
                
                # Check if system message
                is_system = False
                if event.sender_id == 777000 or event.sender_id == 1087968824:
                    is_system = True
                elif any(pattern in message_text.lower() for pattern in [
                    "joined the group", "was added", "created the group", 
                    "left the group", "pinned a message"
                ]):
                    is_system = True
                
                if is_system:
                    try:
                        await event.delete()
                    except:
                        pass
                    
            except:
                pass
    
    async def handle_new_member(self, event):
        """Handle new members joining the group - FIXED VERSION"""
        try:
            # Check if this is a user joining event safely
            if hasattr(event, 'user_joined') and event.user_joined:
                # Get the chat
                chat = await event.get_chat()
                
                # Get the new member(s) safely
                if hasattr(event, 'action_message') and event.action_message:
                    if hasattr(event.action_message, 'action') and event.action_message.action:
                        if hasattr(event.action_message.action, 'users'):
                            users = event.action_message.action.users
                            
                            for user_id in users:
                                try:
                                    # Get user info
                                    user = await event.client.get_entity(user_id)
                                    
                                    # Check if it's a bot
                                    if hasattr(user, 'bot') and user.bot:
                                        continue
                                    
                                    # Get user display name
                                    user_display = get_user_display(user)
                                    
                                    # Check blacklist
                                    is_blocked, reason = is_blacklisted(user)
                                    if is_blocked:
                                        # If blacklisted, remove them
                                        try:
                                            await event.client.kick_participant(chat, user_id)
                                            print(f"[BLACKLIST] Removed blacklisted user {user_display} from {chat.title}")
                                        except:
                                            pass
                                        continue
                                    
                                    # Send welcome message
                                    welcome_text = JOIN_MESSAGE.format(
                                        user_mention=f"<a href='tg://user?id={user_id}'>{user_display}</a>"
                                    )
                                    
                                    await event.client.send_message(
                                        chat,
                                        welcome_text,
                                        parse_mode='html'
                                    )
                                    
                                    print(f"[JOIN] New member joined: {user_display} in {chat.title}")
                                    
                                except Exception as e:
                                    print(f"[ERROR] Processing new member: {e}")
                        
        except Exception as e:
            print(f"[ERROR] Handle new member: {e}")
    
    async def get_group_owner_id(self, chat):
        """Get the Telegram user ID of the group owner/creator"""
        try:
            # Method 1: Check admin participants for creator flag
            try:
                participants = await self.client.get_participants(
                    chat, 
                    filter=types.ChannelParticipantsAdmins()
                )
                
                for participant in participants:
                    if hasattr(participant, 'participant'):
                        # Check if this is the creator using proper Telethon types
                        if isinstance(participant.participant, ChannelParticipantCreator):
                            return participant.id
            except:
                pass
            
            # Method 2: Check full chat info
            try:
                if hasattr(chat, 'megagroup') and chat.megagroup:
                    full_chat = await self.client(
                        functions.channels.GetFullChannelRequest(chat)
                    )
                    if hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'creator_id'):
                        return full_chat.full_chat.creator_id
            except:
                pass
            
            print(f"[DEBUG] Could not determine group owner for chat {chat.id}")
            return None
            
        except Exception as e:
            print(f"[ERROR] Getting group owner: {e}")
            return None
    
    async def handle_begin_command(self, event):
        """Handle /begin command - Create merged photo and show role buttons"""
        try:
            # Get chat and user
            chat = await event.get_chat()
            user = await event.get_sender()
            chat_id = str(chat.id)
            chat_title = getattr(chat, 'title', 'Unknown')
            
            # Clean chat ID
            if chat_id.startswith('-100'):
                clean_chat_id = chat_id[4:]
            else:
                clean_chat_id = chat_id
            
            # Load groups
            groups = load_groups()
            group_data = None
            group_key = None
            
            # Find group
            if clean_chat_id in groups:
                group_data = groups[clean_chat_id]
                group_key = clean_chat_id
            elif chat_id in groups:
                group_data = groups[chat_id]
                group_key = chat_id
            else:
                for key, data in groups.items():
                    if data.get("name") == chat_title:
                        group_data = data
                        group_key = key
                        break
            
            if not group_data:
                try:
                    await event.reply(GROUP_NOT_FOUND_MESSAGE, parse_mode='html')
                except:
                    pass
                return
            
            # Check if already initiated
            if group_data.get("session_initiated", False):
                try:
                    await event.reply(SESSION_ALREADY_INITIATED_MESSAGE, parse_mode='html')
                except:
                    pass
                return
            
            # Get participants - EXCLUDE BOT, GROUP CREATOR, AND BLACKLISTED USERS
            try:
                participants = await self.client.get_participants(chat)
                eligible_users = []
                
                bot_id = (await self.client.get_me()).id
                
                print(f"[BEGIN] Total participants: {len(participants)}")
                print(f"[BEGIN] Bot ID: {bot_id}")
                
                for participant in participants:
                    participant_id = participant.id
                    
                    # Skip bot
                    if participant_id == bot_id:
                        print(f"[BEGIN] Skipping bot: {participant_id}")
                        continue
                    
                    # Skip group creator - FIXED: Use proper Telethon type checking
                    if hasattr(participant, 'participant'):
                        if isinstance(participant.participant, ChannelParticipantCreator):
                            print(f"[BEGIN] Skipping group creator: {participant_id}")
                            continue
                    
                    # Check if it's a bot account
                    if hasattr(participant, 'bot') and participant.bot:
                        print(f"[BEGIN] Skipping bot account: {participant_id}")
                        continue
                    
                    # Check if blacklisted
                    is_blocked, reason = is_blacklisted(participant)
                    if is_blocked:
                        print(f"[BEGIN] Skipping blacklisted user: {participant_id} - {reason}")
                        continue
                    
                    # Add user as eligible (not bot, not creator, not blacklisted)
                    eligible_users.append(participant)
                    print(f"[BEGIN] Added eligible user: ID={participant_id}, Name={get_user_display(participant)}")
                
                member_count = len(eligible_users)
                print(f"[BEGIN] Found {member_count} eligible users (excluding bot, creator, blacklisted)")
                
                # Need exactly 2 eligible users (for buyer and seller)
                if member_count != 2:
                    try:
                        message = INSUFFICIENT_MEMBERS_MESSAGE.format(current_count=member_count)
                        await event.reply(message, parse_mode='html')
                    except:
                        pass
                    return
                
                # Update members
                group_data["members"] = [u.id for u in eligible_users]
                groups[group_key] = group_data
                save_groups(groups)
                
                # Get the 2 eligible users for photo
                user1, user2 = eligible_users[0], eligible_users[1]
                
                print(f"[BEGIN] Selected users for roles:")
                print(f"[BEGIN]   User1: ID={user1.id}, Display={get_user_display(user1)}")
                print(f"[BEGIN]   User2: ID={user2.id}, Display={get_user_display(user2)}")
                
                # Create merged photo with their profile pictures
                success, image_bytes, message = await create_merged_photo(
                    self.client, 
                    user1.id, 
                    user2.id
                )
                
                if success:
                    # Send the merged photo as preview
                    temp_file = "temp_merged_preview.png"
                    with open(temp_file, "wb") as f:
                        f.write(image_bytes.getvalue())
                    
                    # Use text from texts.py
                    caption = MERGED_PHOTO_CAPTION.format(
                        user1_name=get_user_display(user1),
                        user2_name=get_user_display(user2)
                    )
                    
                    # Get buttons for role selection
                    buttons = get_session_buttons(group_key)
                    
                    # Send photo with buttons
                    await self.client.send_file(
                        chat,
                        temp_file,
                        caption=caption,
                        parse_mode='html',
                        buttons=buttons
                    )
                    
                    # Clean up temp file
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    
                    print(f"[PHOTO] Merged preview sent for {chat_title}")
                else:
                    print(f"[ERROR] Failed to create merged photo: {message}")
                    # Send text message instead
                    await self.client.send_message(
                        chat,
                        f"❌ Failed to create preview photo. {message}\n\nPlease select your roles:",
                        parse_mode='html',
                        buttons=get_session_buttons(group_key)
                    )
                
                # Update group
                group_data["session_initiated"] = True
                group_data["user1_id"] = user1.id
                group_data["user2_id"] = user2.id
                groups[group_key] = group_data
                save_groups(groups)
                
                print(f"[SUCCESS] Session initiated in {chat_title}")
                
            except Exception as e:
                print(f"[ERROR] /begin: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await event.reply(f"❌ Error: {str(e)[:100]}", parse_mode='html')
                except:
                    pass
            
        except Exception as e:
            print(f"[ERROR] Handling /begin: {e}")
            import traceback
            traceback.print_exc()
    
    async def handle_role_selection(self, event):
        """Handle role selection - Generate final PFP logo and update group photo"""
        try:
            # Get user
            sender = await event.get_sender()
            if not sender:
                await event.answer("❌ Cannot identify user", alert=True)
                return
            
            # Get data
            data = event.data.decode('utf-8')
            
            # Get chat
            chat = await event.get_chat()
            chat_id = str(chat.id)
            chat_title = getattr(chat, 'title', 'Unknown')
            
            # Clean chat ID
            if chat_id.startswith('-100'):
                clean_chat_id = chat_id[4:]
            else:
                clean_chat_id = chat_id
            
            # Parse role
            if data.startswith('role_buyer_'):
                role = "buyer"
                role_name = "Buyer"
                group_id = data.replace('role_buyer_', '')
            elif data.startswith('role_seller_'):
                role = "seller"
                role_name = "Seller"
                group_id = data.replace('role_seller_', '')
            else:
                return
            
            # Load data
            groups = load_groups()
            roles = load_user_roles()
            
            # Find group
            if group_id not in groups:
                for key, data in groups.items():
                    if data.get("name") == chat_title:
                        group_id = key
                        break
            
            if group_id not in groups:
                await event.answer("❌ Group not found", alert=True)
                return
            
            # Check if this user is the bot
            bot_id = (await self.client.get_me()).id
            if sender.id == bot_id:
                await event.answer("❌ Bot cannot select roles", alert=True)
                return
            
            # Check if this user is the group creator - FIXED: Use proper type checking
            try:
                participants = await self.client.get_participants(chat, filter=types.ChannelParticipantsAdmins())
                for participant in participants:
                    if hasattr(participant, 'participant'):
                        if isinstance(participant.participant, ChannelParticipantCreator):
                            if participant.id == sender.id:
                                await event.answer("❌ Group creator cannot select roles", alert=True)
                                return
            except:
                pass
            
            # Check if this user is one of the 2 eligible users
            eligible_user_ids = group_data.get("members", [])
            if sender.id not in eligible_user_ids:
                await event.answer("❌ You are not an eligible participant for this session", alert=True)
                return
            
            # Initialize roles
            if group_id not in roles:
                roles[group_id] = {}
            
            # Check if already chosen - FIXED: Use string comparison
            if str(sender.id) in roles[group_id]:
                await event.answer("⛔ Role Already Chosen", alert=True)
                return
            
            # Check if role taken
            role_taken = any(u.get("role") == role for u in roles[group_id].values())
            if role_taken:
                await event.answer("⚠️ Role Already Taken", alert=True)
                return
            
            # Save role
            roles[group_id][str(sender.id)] = {
                "role": role,
                "name": get_user_display(sender),
                "user_id": sender.id,
                "selected_at": time.time()
            }
            save_user_roles(roles)
            
            # Send success
            await event.answer(f"✅ {role_name} role selected", alert=False)
            
            # Send confirmation
            if role == "buyer":
                confirm_msg = f"✅ <a href='tg://user?id={sender.id}'>{get_user_display(sender)}</a> confirmed as <b>Buyer</b>."
            else:
                confirm_msg = f"✅ <a href='tg://user?id={sender.id}'>{get_user_display(sender)}</a> confirmed as <b>Seller</b>."
            
            await self.client.send_message(
                chat,
                confirm_msg,
                parse_mode='html'
            )
            
            print(f"[ROLE] {get_user_display(sender)} selected as {role_name}")
            
            # Check if both roles selected
            buyer_count = sum(1 for u in roles[group_id].values() if u.get("role") == "buyer")
            seller_count = sum(1 for u in roles[group_id].values() if u.get("role") == "seller")
            
            if buyer_count >= 1 and seller_count >= 1:
                await self.generate_final_pfp_logo(chat, group_id, roles[group_id])
                
        except Exception as e:
            print(f"[ERROR] Role selection: {e}")
            import traceback
            traceback.print_exc()
            await event.answer("❌ Error selecting role", alert=True)
    
    async def generate_final_pfp_logo(self, chat, group_id, user_roles):
        """Generate final PFP logo and update group photo - ONLY CALLED ONCE!"""
        try:
            # Find buyer and seller
            buyer = None
            seller = None
            
            for user_id, data in user_roles.items():
                if data.get("role") == "buyer" and not buyer:
                    buyer = data
                elif data.get("role") == "seller" and not seller:
                    seller = data
            
            if not buyer or not seller:
                return
            
            # Get group type from stored data
            groups = load_groups()
            group_data = groups.get(group_id, {})
            group_type = group_data.get("type", "p2p")
            group_type_display = "P2P" if group_type == "p2p" else "OTC"
            
            print(f"[PFP] Generating final logo for {group_type_display} escrow")
            
            # Use PFPGenerator to create logo
            from utils.pfpgen import PFPGenerator
            
            # Initialize PFP generator
            pfp_gen = PFPGenerator(template_path=PFP_TEMPLATE)
            
            # Generate logo with formatted usernames
            success, image_bytes, message = pfp_gen.generate_logo(
                buyer_username=buyer['name'],
                buyer_user_id=buyer['user_id'],
                seller_username=seller['name'],
                seller_user_id=seller['user_id']
            )
            
            if success:
                try:
                    # Save to temporary file
                    temp_file = f"temp_final_pfp_{group_type}.png"
                    with open(temp_file, "wb") as f:
                        f.write(image_bytes.getvalue())
                    
                    # UPDATE GROUP PHOTO (ONLY THIS ONE TIME!)
                    await set_group_photo(self.client, chat, temp_file)
                    
                    # Clean up
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                    
                    print(f"[PFP] Final {group_type_display} PFP logo updated!")
                    
                except Exception as e:
                    print(f"[ERROR] Could not update final group photo: {e}")
                    # Silently fail - don't send any message to chat
            else:
                print(f"[ERROR] Failed to create final PFP logo: {message}")
            
            # Send final confirmation message
            message_text = PARTICIPANTS_CONFIRMED_MESSAGE.format(
                group_type_display=group_type_display,
                buyer_name=buyer['name'],
                seller_name=seller['name']
            )
            
            await self.client.send_message(
                chat,
                message_text,
                parse_mode='html'
            )
            
            print(f"[SETUP] {group_type_display} escrow finalized: {buyer['name']} ↔ {seller['name']}")
            
        except Exception as e:
            print(f"[ERROR] Generating final PFP logo: {e}")
            import traceback
            traceback.print_exc()

    async def start_bot(self):
        """Start the bot"""
        try:
            print("═"*50)
            print("🔐 SECURE ESCROW BOT")
            print("═"*50)
            
            # Check config
            if not API_ID or not API_HASH or not BOT_TOKEN:
                print("❌ Missing configuration")
                sys.exit(1)
            
            # Check assets
            self.check_assets()
            
            # Start client
            await self.client.start(bot_token=BOT_TOKEN)
            
            # Get bot info
            me = await self.client.get_me()
            
            print(f"✅ Bot: @{me.username}")
            print(f"🆔 ID: {me.id}")
            print("═"*50)
            
            print("\n🚀 FEATURES:")
            print("   • P2P & OTC Escrow Creation")
            print("   • Profile picture preview on /begin")
            print("   • PFP logo generation on role confirmation")
            print("   • Role selection system")
            print("   • Address management (/buyer, /seller, /addresses)")
            print("   • Blacklist system")
            print("   • Works with users without usernames")
            print("   • User ID display for long/no usernames")
            print("   • Welcome message when new members join")
            print("   • Auto-removal of blacklisted users")
            print("\n📡 Bot is ready...")
            print("   Ctrl+C to stop\n")
            
            # Run
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            print("\n👋 Bot stopped")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\n🔴 Shutdown complete")
    
    def check_assets(self):
        """Check if required assets exist"""
        print("\n📁 Checking assets...")
        
        # Create necessary directories
        os.makedirs('assets', exist_ok=True)
        os.makedirs('config', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        # Check required assets
        required_assets = [BASE_START_IMAGE, PFP_TEMPLATE, UNKNOWN_PFP]
        
        for asset in required_assets:
            if not os.path.exists(asset):
                print(f"❌ REQUIRED asset missing: {asset}")
                if asset == UNKNOWN_PFP:
                    print("   Creating unknown.png fallback...")
                    # Create a simple unknown.png
                    img = create_default_fallback()
                    img.save(UNKNOWN_PFP)
                    print(f"   Created {UNKNOWN_PFP}")
                elif asset == BASE_START_IMAGE:
                    print(f"   Please add {BASE_START_IMAGE} for /begin preview")
                elif asset == PFP_TEMPLATE:
                    print(f"   Please add {PFP_TEMPLATE} for final PFP logo")
        
        # Check font
        font_path = "assets/Skynight.otf"
        if not os.path.exists(font_path):
            print(f"⚠️  Font file missing: {font_path}")
            print("   PFP logos will use default font")
        
        print("✅ Asset check complete\n")

async def main_async():
    """Async main function"""
    bot = EscrowBot()
    await bot.start_bot()

def main():
    """Main function"""
    # Run bot
    asyncio.run(main_async())

if __name__ == '__main__':
    main()
