#!/usr/bin/env python3
"""
Main entry point for the Escrow Bot - Complete working version
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
from datetime import datetime

# Import configuration
from config import API_ID, API_HASH, BOT_TOKEN, BOT_USERNAME

# Import handlers
from handlers.start import handle_start
from handlers.create import handle_create, handle_create_p2p, handle_create_other
from handlers.stats import handle_stats
from handlers.about import handle_about
from handlers.help import handle_help
from handlers.addresses import setup_address_handlers
from handlers.broadcast import handle_broadcast

# Import utilities
from utils.texts import (
    START_MESSAGE, CREATE_MESSAGE, P2P_CREATED_MESSAGE, OTHER_CREATED_MESSAGE,
    WELCOME_MESSAGE, SESSION_INITIATED_MESSAGE, INSUFFICIENT_MEMBERS_MESSAGE,
    SESSION_ALREADY_INITIATED_MESSAGE, GROUP_NOT_FOUND_MESSAGE,
    MERGED_PHOTO_CAPTION, PARTICIPANTS_CONFIRMED_MESSAGE, JOIN_MESSAGE,
    BUYER_CONFIRMED_MESSAGE, SELLER_CONFIRMED_MESSAGE, ROLE_ALREADY_CHOSEN_MESSAGE,
    ROLE_ALREADY_TAKEN_MESSAGE, WALLET_SETUP_MESSAGE, ESCROW_READY_MESSAGE,
    CHANNEL_LOG_CREATION, ERROR_MESSAGE, WAITING_PARTICIPANTS_MESSAGE,
    ROLE_ANNOUNCEMENT_MESSAGE, STATS_MESSAGE, ABOUT_MESSAGE, HELP_MESSAGE
)
from utils.buttons import get_main_menu_buttons, get_session_buttons, get_back_button
from utils.blacklist import is_blacklisted, add_to_blacklist, load_blacklist

# Setup logging
from core.logger import get_logger
logger = get_logger("Trisha.core.main")

# Track groups for invite management
GROUPS_FILE = 'data/active_groups.json'
USER_ROLES_FILE = 'data/user_roles.json'
WALLETS_FILE = 'data/wallets.json'

# Asset paths
BASE_START_IMAGE = "assets/base_start.png"  # For /begin preview
PFP_TEMPLATE = "assets/tg1.png"  # For final group PFP
UNKNOWN_PFP = "assets/unknown.png"
PFP_CONFIG_PATH = "config/pfp_config.json"

def load_groups():
    """Load active groups data"""
    try:
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Loading groups: {e}")
        return {}

def save_groups(groups):
    """Save active groups data"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(GROUPS_FILE, 'w') as f:
            json.dump(groups, f, indent=2)
    except Exception as e:
        logger.error(f"Saving groups: {e}")

def load_user_roles():
    """Load user roles data"""
    try:
        if os.path.exists(USER_ROLES_FILE):
            with open(USER_ROLES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Loading roles: {e}")
        return {}

def save_user_roles(roles):
    """Save user roles data"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(USER_ROLES_FILE, 'w') as f:
            json.dump(roles, f, indent=2)
    except Exception as e:
        logger.error(f"Saving roles: {e}")

def load_wallets():
    """Load wallet addresses data"""
    try:
        if os.path.exists(WALLETS_FILE):
            with open(WALLETS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Loading wallets: {e}")
        return {}

def save_wallets(wallets):
    """Save wallet addresses data"""
    try:
        os.makedirs('data', exist_ok=True)
        with open(WALLETS_FILE, 'w') as f:
            json.dump(wallets, f, indent=2)
    except Exception as e:
        logger.error(f"Saving wallets: {e}")

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
        logger.error(f"Getting user display: {e}")
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
        logger.error(f"Cleaning group ID: {e}")
        return str(chat_id)

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
            logger.success("Group photo updated via messages.EditChatPhotoRequest")
            return True
        except Exception as e1:
            logger.info(f"Normal group photo update failed: {e1}")
            
            # Fallback for supergroups / channels
            try:
                await client(
                    functions.channels.EditPhotoRequest(
                        channel=chat,
                        photo=types.InputChatUploadedPhoto(file=file)
                    )
                )
                logger.success("Group photo updated via channels.EditPhotoRequest")
                return True
            except Exception as e2:
                logger.info(f"Channel photo update failed: {e2}")
                
                # Try the simple edit_photo method as last resort
                try:
                    await client.edit_photo(chat, photo=photo_path)
                    logger.success("Group photo updated via edit_photo")
                    return True
                except Exception as e3:
                    logger.info(f"Simple edit_photo failed: {e3}")
                    raise Exception(f"All photo update methods failed: {e1}, {e2}, {e3}")

    except Exception as e:
        logger.error(f"set_group_photo: {e}")
        raise e

async def download_profile_picture(client, user_id):
    """Download user's profile picture"""
    try:
        logger.info(f"Downloading profile picture for user_id: {user_id}")
        
        # Get user entity
        user = await client.get_entity(user_id)
        
        # Download profile photo as bytes
        photo_bytes = await client.download_profile_photo(user, file=bytes)
        
        if photo_bytes:
            # Open from BytesIO
            img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
            logger.info(f"Successfully downloaded profile picture for {user_id}")
            return img
        else:
            # No profile picture, use fallback
            logger.info(f"No profile picture for {user_id}, using fallback")
            return load_unknown_pfp()
            
    except Exception as e:
        logger.error(f"Downloading profile picture for {user_id}: {e}")
        return load_unknown_pfp()

def load_unknown_pfp():
    """Load the unknown.png fallback image"""
    try:
        if os.path.exists(UNKNOWN_PFP):
            img = Image.open(UNKNOWN_PFP).convert("RGBA")
            logger.info(f"Loaded unknown.png fallback")
            return img
        else:
            # Create a simple fallback if unknown.png doesn't exist
            logger.warning(f"{UNKNOWN_PFP} not found, creating default fallback")
            return create_default_fallback()
    except Exception as e:
        logger.error(f"Loading unknown.png: {e}")
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
        logger.error(f"Creating default fallback: {e}")
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
            logger.error(f"Base image not found: {BASE_START_IMAGE}")
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
        logger.error(f"Creating merged photo: {e}")
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
       
        @self.client.on(events.NewMessage(pattern='/broadcast'))
        async def broadcast_handler(event):
            await handle_broadcast(event)
        
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
        
        # Handle new users joining
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
        """Handle new members joining the group"""
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
                                            logger.info(f"Removed blacklisted user {user_display} from {chat.title}")
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
                                    
                                    logger.info(f"New member joined: {user_display} in {chat.title}")
                                    
                                except Exception as e:
                                    logger.error(f"Processing new member: {e}")
                        
        except Exception as e:
            logger.error(f"Handle new member: {e}")
    
    async def get_group_owner_id(self, chat):
        """Get the Telegram user ID of the group owner/creator"""
        try:
            # Check admin participants for creator flag
            try:
                participants = await self.client.get_participants(
                    chat, 
                    filter=types.ChannelParticipantsAdmins()
                )
                
                for participant in participants:
                    if hasattr(participant, 'participant'):
                        if isinstance(participant.participant, ChannelParticipantCreator):
                            return participant.id
            except:
                pass
            
            # Check full chat info
            try:
                if hasattr(chat, 'megagroup') and chat.megagroup:
                    full_chat = await self.client(
                        functions.channels.GetFullChannelRequest(chat)
                    )
                    if hasattr(full_chat, 'full_chat') and hasattr(full_chat.full_chat, 'creator_id'):
                        return full_chat.full_chat.creator_id
            except:
                pass
            
            return None
            
        except Exception as e:
            logger.error(f"Getting group owner: {e}")
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
            clean_chat_id = clean_group_id(chat_id)
            
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
                
                logger.info(f"Total participants: {len(participants)}")
                logger.info(f"Bot ID: {bot_id}")
                
                for participant in participants:
                    participant_id = participant.id
                    
                    # Skip bot
                    if participant_id == bot_id:
                        logger.info(f"Skipping bot: {participant_id}")
                        continue
                    
                    # Skip group creator
                    if hasattr(participant, 'participant'):
                        if isinstance(participant.participant, ChannelParticipantCreator):
                            logger.info(f"Skipping group creator: {participant_id}")
                            continue
                    
                    # Check if it's a bot account
                    if hasattr(participant, 'bot') and participant.bot:
                        logger.info(f"Skipping bot account: {participant_id}")
                        continue
                    
                    # Check if blacklisted
                    is_blocked, reason = is_blacklisted(participant)
                    if is_blocked:
                        logger.info(f"Skipping blacklisted user: {participant_id} - {reason}")
                        continue
                    
                    # Add user as eligible
                    eligible_users.append(participant)
                    logger.info(f"Added eligible user: ID={participant_id}, Name={get_user_display(participant)}")
                
                member_count = len(eligible_users)
                logger.info(f"Found {member_count} eligible users (excluding bot, creator, blacklisted)")
                
                # Need exactly 2 eligible users
                if member_count != 2:
                    if member_count < 2:
                        try:
                            message = WAITING_PARTICIPANTS_MESSAGE
                            await event.reply(message, parse_mode='html')
                        except:
                            pass
                    else:
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
                
                # Get the 2 eligible users
                user1, user2 = eligible_users[0], eligible_users[1]
                
                logger.info(f"Selected users for roles:")
                logger.info(f"  User1: ID={user1.id}, Display={get_user_display(user1)}")
                logger.info(f"  User2: ID={user2.id}, Display={get_user_display(user2)}")
                
                # Create merged photo
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
                    
                    # Create caption
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
                    
                    logger.info(f"Merged preview sent for {chat_title}")
                else:
                    logger.error(f"Failed to create merged photo: {message}")
                    # Send text message instead
                    await self.client.send_message(
                        chat,
                        f"<b>Session Initiated</b>\n\nParticipants:\n• {get_user_display(user1)}\n• {get_user_display(user2)}\n\nPlease select your roles:",
                        parse_mode='html',
                        buttons=get_session_buttons(group_key)
                    )
                
                # Update group
                group_data["session_initiated"] = True
                group_data["user1_id"] = user1.id
                group_data["user2_id"] = user2.id
                groups[group_key] = group_data
                save_groups(groups)
                
                logger.success(f"Session initiated in {chat_title}")
                
                # Log to channel if needed
                try:
                    creator_name = get_user_display(user)
                    escrow_type = group_data.get("type", "P2P").upper()
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    log_message = CHANNEL_LOG_CREATION.format(
                        group_name=chat_title,
                        escrow_type=escrow_type,
                        timestamp=timestamp,
                        creator_name=creator_name,
                        creator_id=user.id,
                        chat_id=clean_chat_id
                    )
                    
                    # Send to log channel if configured
                    # await self.client.send_message(LOG_CHANNEL_ID, log_message, parse_mode='html')
                except Exception as e:
                    logger.error(f"Logging to channel: {e}")
                
            except Exception as e:
                logger.error(f"/begin: {e}")
                import traceback
                traceback.print_exc()
                try:
                    await event.reply(ERROR_MESSAGE, parse_mode='html')
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Handling /begin: {e}")
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
            clean_chat_id = clean_group_id(chat_id)
            
            # Parse role
            if data.startswith('role_buyer_'):
                role = "buyer"
                role_name = "Buyer"
                role_emoji = "🔵"
                group_id = data.replace('role_buyer_', '')
            elif data.startswith('role_seller_'):
                role = "seller"
                role_name = "Seller"
                role_emoji = "🟢"
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
            
            # Get group data
            group_data = groups.get(group_id, {})
            
            # Check if this user is the bot
            bot_id = (await self.client.get_me()).id
            if sender.id == bot_id:
                await event.answer("❌ Bot cannot select roles", alert=True)
                return
            
            # Check if this user is the group creator
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
            
            # Check if already chosen (using string user ID)
            if str(sender.id) in roles[group_id]:
                await event.answer(ROLE_ALREADY_CHOSEN_MESSAGE, alert=True)
                return
            
            # Check if role taken
            role_taken = any(u.get("role") == role for u in roles[group_id].values())
            if role_taken:
                await event.answer(ROLE_ALREADY_TAKEN_MESSAGE, alert=True)
                return
            
            # Save role (using string user ID)
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
                confirm_msg = BUYER_CONFIRMED_MESSAGE.format(
                    buyer_id=sender.id,
                    buyer_name=get_user_display(sender)
                )
            else:
                confirm_msg = SELLER_CONFIRMED_MESSAGE.format(
                    seller_id=sender.id,
                    seller_name=get_user_display(sender)
                )
            
            await self.client.send_message(
                chat,
                confirm_msg,
                parse_mode='html'
            )
            
            logger.info(f"{get_user_display(sender)} selected as {role_name}")
            
            # Check if both roles selected
            buyer_count = sum(1 for u in roles[group_id].values() if u.get("role") == "buyer")
            seller_count = sum(1 for u in roles[group_id].values() if u.get("role") == "seller")
            
            # Announce current status
            participants_display = []
            for uid, data in roles[group_id].items():
                role_emoji = "🔵" if data.get("role") == "buyer" else "🟢"
                participants_display.append(f"{role_emoji} {data.get('name')}")
            
            status_msg = ROLE_ANNOUNCEMENT_MESSAGE.format(
                mention=f"<a href='tg://user?id={sender.id}'>{get_user_display(sender)}</a>",
                role_emoji=role_emoji,
                role_name=role_name,
                buyer_count=buyer_count,
                seller_count=seller_count
            )
            await self.client.send_message(chat, status_msg, parse_mode='html')
            
            if buyer_count >= 1 and seller_count >= 1:
                await self.finalize_session(chat, group_id, roles[group_id], group_data)
                
        except Exception as e:
            logger.error(f"Role selection: {e}")
            import traceback
            traceback.print_exc()
            await event.answer("❌ Error selecting role", alert=True)
    
    async def finalize_session(self, chat, group_id, user_roles, group_data):
        """Finalize session after both roles selected - FIXED VERSION"""
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
            
            # Get group type
            group_type = group_data.get("type", "p2p")
            group_type_display = "P2P" if group_type == "p2p" else "OTC"
            
            logger.info(f"Finalizing {group_type_display} escrow")
            
            # Load wallet addresses from wallets file
            wallets = load_wallets()
            
            # Get wallet addresses if they exist (using string keys for group_id)
            buyer_wallet_address = "[Not set]"
            seller_wallet_address = "[Not set]"
            
            if group_id in wallets:
                if "buyer_wallet" in wallets[group_id]:
                    buyer_wallet_address = wallets[group_id]["buyer_wallet"]
                if "seller_wallet" in wallets[group_id]:
                    seller_wallet_address = wallets[group_id]["seller_wallet"]
            
            # Also update group data with wallet addresses
            if group_id in wallets:
                group_data["buyer_wallet_address"] = buyer_wallet_address
                group_data["seller_wallet_address"] = seller_wallet_address
                
                # Save updated group data
                groups = load_groups()
                if group_id in groups:
                    groups[group_id]["buyer_wallet_address"] = buyer_wallet_address
                    groups[group_id]["seller_wallet_address"] = seller_wallet_address
                    save_groups(groups)
            
            # Generate final PFP logo
            await self.generate_final_pfp_logo(chat, group_id, user_roles)
            
            # Send wallet setup message - FIXED: Now includes all required placeholders
            wallet_msg = WALLET_SETUP_MESSAGE.format(
                buyer_name=buyer['name'],
                seller_name=seller['name'],
                buyer_wallet_address=buyer_wallet_address,
                seller_wallet_address=seller_wallet_address
            )
            
            await self.client.send_message(
                chat,
                wallet_msg,
                parse_mode='html'
            )
            
            logger.success(f"{group_type_display} escrow finalized: {buyer['name']} ↔ {seller['name']}")
            
        except Exception as e:
            logger.error(f"Finalizing session: {e}")
            import traceback
            traceback.print_exc()
    
    async def generate_final_pfp_logo(self, chat, group_id, user_roles):
        """Generate final PFP logo and update group photo"""
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
            
            logger.info(f"Generating final logo for {group_type_display} escrow")
            
            # Use PFPGenerator to create logo
            try:
                from utils.pfpgen import PFPGenerator
                
                # Initialize PFP generator
                pfp_gen = PFPGenerator(template_path=PFP_TEMPLATE)
                
                # Generate logo
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
                        
                        # Update group photo
                        await set_group_photo(self.client, chat, temp_file)
                        
                        # Clean up
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                        
                        logger.success(f"Final {group_type_display} PFP logo updated!")
                        
                    except Exception as e:
                        logger.error(f"Could not update final group photo: {e}")
                else:
                    logger.error(f"Failed to create final PFP logo: {message}")
            except ImportError:
                logger.warning(f"PFPGenerator not available, skipping logo generation")
            except Exception as e:
                logger.error(f"PFP generation: {e}")
            
            # Send final confirmation
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
            
            # Send escrow ready message
            ready_msg = ESCROW_READY_MESSAGE.format(
                buyer_name=buyer['name'],
                seller_name=seller['name'],
                buyer_wallet="[Not set]",
                seller_wallet="[Not set]"
            )
            
            await self.client.send_message(
                chat,
                ready_msg,
                parse_mode='html'
            )
            
        except Exception as e:
            logger.error(f"Generating final PFP logo: {e}")
            import traceback
            traceback.print_exc()

    async def start_bot(self):
        """Start the bot"""
        try:
            # Check config
            if not API_ID or not API_HASH or not BOT_TOKEN:
                logger.error("Missing configuration")
                sys.exit(1)
            
            # Check assets (silently)
            self.check_assets()
            
            # Start client
            await self.client.start(bot_token=BOT_TOKEN)
            
            # Get bot info
            me = await self.client.get_me()
            
            # Clean, spaced out startup messages
            await asyncio.sleep(0.5)
            logger.success(f"Bot @{me.username} successfully hosted")
            
            await asyncio.sleep(0.3)
            # Get VPS info if available
            try:
                import psutil
                ram = psutil.virtual_memory().total / (1024**3)  # GB
                cpu_count = psutil.cpu_count()
                logger.info(f"VPS found - RAM: {ram:.1f}GB | CPU Cores: {cpu_count}")
            except ImportError:
                pass
            except Exception as e:
                pass
            
            await asyncio.sleep(0.3)
            logger.info("Bot is ready")
            logger.info("Press Ctrl+C to stop")
            
            # Run
            await self.client.run_until_disconnected()
            
        except KeyboardInterrupt:
            logger.info("Bot stopped")
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logger.info("Shutdown complete")
    
    def check_assets(self):
        """Check if required assets exist"""
        # Create necessary directories
        os.makedirs('assets', exist_ok=True)
        os.makedirs('config', exist_ok=True)
        os.makedirs('data', exist_ok=True)
        
        # Check required assets (silent)
        required_assets = [BASE_START_IMAGE, PFP_TEMPLATE, UNKNOWN_PFP]
        
        for asset in required_assets:
            if not os.path.exists(asset):
                if asset == UNKNOWN_PFP:
                    # Create a simple unknown.png
                    img = create_default_fallback()
                    img.save(UNKNOWN_PFP)

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
