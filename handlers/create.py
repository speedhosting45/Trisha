#!/usr/bin/env python3
"""
Create escrow handlers - Fixed version with Premium Custom Emojis (UTF-16 safe)
Logs sent from bot, not session string
"""
from telethon.sessions import StringSession
from telethon.tl import functions, types
from telethon import Button
from telethon.tl.types import (
    ChatAdminRights, 
    MessageEntityCustomEmoji,
    MessageEntityBold,
    MessageEntityBlockquote,
    MessageEntityCode,
    MessageEntityUrl,
    MessageEntityHashtag
)
from telethon.helpers import add_surrogate
from config import STRING_SESSION1, API_ID, API_HASH, set_bot_username, LOG_CHANNEL_ID, BOT_TOKEN
from telethon import TelegramClient
import asyncio
import json
import os
from datetime import datetime
import time

# Image URLs from config
OTC_IMAGE = "https://files.catbox.moe/f6lzpr.png"
P2P_IMAGE = "https://files.catbox.moe/ieiejo.png"

# Define get_next_number locally
def get_next_number(group_type="p2p"):
    """Get next sequential group number"""
    COUNTER_FILE = 'data/counter.json'
    try:
        if os.path.exists(COUNTER_FILE):
            with open(COUNTER_FILE, 'r') as f:
                counter = json.load(f)
        else:
            counter = {"p2p": 1, "other": 1}
        
        number = counter.get(group_type, 1)
        counter[group_type] = number + 1
        
        with open(COUNTER_FILE, 'w') as f:
            json.dump(counter, f, indent=2)
        
        return number
    except Exception as e:
        print(f"[ERROR] get_next_number: {e}")
        return 1

def build_log_entities(text):
    """
    Build custom entities for log message with correct UTF-16 offsets
    
    Args:
        text: Full message string
    
    Returns:
        List of MessageEntity objects with correct offsets
    """
    entities = []
    
    # Add hashtag entity for the first line
    hashtag_text = "#𝖭𝖾𝗐 𝖤𝗌𝖼𝗋𝗈𝗐 𝖦𝗋𝗈𝗎𝗉 𝖢𝗋𝖾𝖺𝗍𝖾𝖽 & 𝖲𝖺𝗏𝖾𝖽."
    index = text.find(hashtag_text)
    if index != -1:
        utf16_offset = len(text[:index].encode('utf-16-le')) // 2
        utf16_length = len(hashtag_text.encode('utf-16-le')) // 2
        entities.append(MessageEntityHashtag(offset=utf16_offset, length=utf16_length))
    
    # Emoji map with their document IDs
    emoji_map = {
        "💸": 6082586710988820084,  # After Deal Type
        "🔗": 5271604874419647061,  # After Name
        "🥂": 5260567255145539253,  # After Chat ID
        "🟢": 6298751564592973547,  # After Created By
        "➖": 6024110293167116639   # After User ID
    }
    
    # Add custom emoji entities
    for emoji, doc_id in emoji_map.items():
        start = 0
        while True:
            try:
                index = text.index(emoji, start)
                
                # Calculate UTF-16 offset
                prefix = text[:index]
                utf16_offset = len(prefix.encode('utf-16-le')) // 2
                utf16_length = len(emoji.encode('utf-16-le')) // 2
                
                entities.append(
                    MessageEntityCustomEmoji(
                        offset=utf16_offset,
                        length=utf16_length,
                        document_id=doc_id
                    )
                )
                
                start = index + len(emoji)
                
            except ValueError:
                break
    
    # Sort entities by offset
    return sorted(entities, key=lambda e: e.offset)

def build_bold_entities(text):
    """
    Build bold entities for animation messages
    
    Args:
        text: Message text
    
    Returns:
        List of MessageEntityBold objects
    """
    entities = []
    
    # Find the part to make bold (everything after "Creating" until newline)
    if "Creating" in text:
        start_idx = text.find("Creating")
        end_idx = text.find("\n", start_idx)
        if end_idx == -1:
            end_idx = len(text)
        
        bold_text = text[start_idx:end_idx]
        
        # Calculate UTF-16 offset
        prefix = text[:start_idx]
        utf16_offset = len(prefix.encode('utf-16-le')) // 2
        utf16_length = len(bold_text.encode('utf-16-le')) // 2
        
        entities.append(MessageEntityBold(offset=utf16_offset, length=utf16_length))
    
    return entities

async def handle_create(event):
    """
    Handle create escrow button click with custom emojis - UTF-16 safe
    """
    try:
        from utils.buttons import get_create_buttons

        text = (
            "𝘊𝘳𝘦𝘢𝘵𝘦 𝘕𝘦𝘸 𝘌𝘴𝘤𝘳𝘰𝘸 🔩\n\n"
            "Select transaction type to proceed\n\n"
            "• P2P Deal 🥂 – Standard buyer/seller transactions\n"
            "• Other Deal ❤️ – Custom or multi-party agreements\n\n"
            "All escrows operate within private, bot-moderated groups🔥."
        )

        emoji_map = {
            "🔩": 5260249805522744465,
            "🥂": 5260567255145539253,
            "❤️": 5285439518130857782,
            "🔥": 5228796381329645973,
        }

        entities = []

        # ---- PREMIUM EMOJIS ----
        for emoji, doc_id in emoji_map.items():
            index = text.index(emoji)
            utf16_offset = len(text[:index].encode("utf-16-le")) // 2
            utf16_length = len(emoji.encode("utf-16-le")) // 2

            entities.append(
                MessageEntityCustomEmoji(
                    offset=utf16_offset,
                    length=utf16_length,
                    document_id=doc_id
                )
            )

        # ---- BOLD ----
        bold_phrases = ["P2P Deal", "Other Deal"]

        for phrase in bold_phrases:
            index = text.index(phrase)
            utf16_offset = len(text[:index].encode("utf-16-le")) // 2
            utf16_length = len(phrase.encode("utf-16-le")) // 2

            entities.append(
                MessageEntityBold(
                    offset=utf16_offset,
                    length=utf16_length
                )
            )

        # ---- BLOCKQUOTE ----
        quote_text = "Select transaction type to proceed"
        index = text.index(quote_text)
        utf16_offset = len(text[:index].encode("utf-16-le")) // 2
        utf16_length = len(quote_text.encode("utf-16-le")) // 2

        entities.append(
            MessageEntityBlockquote(
                offset=utf16_offset,
                length=utf16_length
            )
        )

        await event.edit(
            text,
            buttons=get_create_buttons(),
            formatting_entities=entities
        )

    except Exception as e:
        print(f"[ERROR] create handler: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to regular message without custom emojis
        try:
            from utils.texts import CREATE_MESSAGE
            await event.edit(
                CREATE_MESSAGE,
                buttons=get_create_buttons(),
                parse_mode='html'
            )
        except:
            pass

async def handle_create_p2p(event):
    """
    Handle P2P deal selection with premium custom emojis - Proper Telethon way
    Using html_parse to merge HTML formatting with custom emoji entities
    """
    try:
        # Get user mention
        user = await event.get_sender()
        mention = user.first_name
        if user.username:
            mention = f"@{user.username}"
        
        # Get bot info
        bot = await event.client.get_me()
        bot_username = bot.username
        set_bot_username(bot_username)
        
        # Get group number
        group_number = get_next_number("p2p")
        group_name = f"𝖯2𝖯 𝘌𝘴𝘤𝘳𝘰𝘸 𝘚𝘦𝘴𝘴𝘪𝘰𝘯 • #{group_number:02d}"
        
        # Show animation messages with bold formatting using entities
        animation_messages = [
            f"Creating P2P Escrow\nPlease wait {mention}.",
            f"Creating P2P Escrow\nPlease wait {mention}..",
            f"Creating P2P Escrow\nPlease wait {mention}...",
        ]
        
        # Display animation with bold entities
        for msg in animation_messages:
            entities = build_bold_entities(msg)
            await event.edit(msg, formatting_entities=entities)
            await asyncio.sleep(0.5)
        
        # Create group
        result = await create_escrow_group(group_name, bot_username, "p2p", event.client, user.id, mention, event)
        
        if result and "invite_url" in result:
            from utils.buttons import get_p2p_created_buttons
            from telethon.tl.types import MessageEntityCustomEmoji
            from telethon.extensions.html import parse as html_parse
            
            # Get buttons
            buttons = get_p2p_created_buttons(result["invite_url"])
            
            # HTML formatted text
            html_text = f"""
<b>𝘗2𝘗 𝘌𝘴𝘤𝘳𝘰𝘸 𝘌𝘴𝘵𝘢𝘣𝘭𝘪𝘴𝘩𝘦𝘥</b> 💵

<blockquote>Secure transaction group created 🚀</blockquote>

<b>Group:</b> {group_name}
<b>Type:</b> P2P Transaction 🎈
<b>Status:</b> Ready for configuration

<code>{result["invite_url"]}</code>

Proceed to the group to configure participants and terms ⚖️
"""
            
            # Step 1: Parse HTML to get text and HTML entities
            parsed_text, html_entities = html_parse(html_text)
            
            # Custom emoji IDs
            emoji_map = {
                "💵": 5409048419211682843,
                "🚀": 5258332798409783582,
                "🎈": 5278651867780377852,
                "⚖️": 5400250414929041085,
            }
            
            # Step 2: Build custom emoji entities using parsed_text
            emoji_entities = []
            
            for emoji, doc_id in emoji_map.items():
                try:
                    # Find position in parsed text
                    index = parsed_text.index(emoji)
                    
                    # Calculate UTF-16 offset
                    utf16_offset = len(parsed_text[:index].encode("utf-16-le")) // 2
                    utf16_length = len(emoji.encode("utf-16-le")) // 2
                    
                    emoji_entities.append(
                        MessageEntityCustomEmoji(
                            offset=utf16_offset,
                            length=utf16_length,
                            document_id=doc_id
                        )
                    )
                    
                    print(f"[DEBUG] Emoji {emoji} at offset {utf16_offset}, length {utf16_length}")
                    
                except ValueError:
                    print(f"[WARNING] Emoji {emoji} not found in parsed text")
                    continue
            
            # Step 3: Merge both entity lists
            all_entities = html_entities + emoji_entities
            all_entities.sort(key=lambda e: e.offset)
            
            print(f"[DEBUG] Total entities: {len(all_entities)} (HTML: {len(html_entities)}, Emoji: {len(emoji_entities)})")
            
            # Step 4: Send WITHOUT parse_mode
            await event.edit(
                parsed_text,
                formatting_entities=all_entities,
                buttons=buttons,
                link_preview=True
            )
            
            print(f"[SUCCESS] P2P Escrow created: {group_name}")
            
        else:
            await event.edit(
                "𝘌𝘴𝘤𝘳𝘰𝘸 𝘊𝘳𝘦𝘢𝘵𝘪𝘰𝘯 𝘍𝘢𝘪𝘭𝘦𝘥\n\nPlease try again later",
                buttons=[Button.inline("🔄 Try Again", b"create")]
            )
            
    except Exception as e:
        print(f"[ERROR] P2P handler: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to regular message without custom emojis
        try:
            from utils.texts import P2P_CREATED_MESSAGE
            from utils.buttons import get_p2p_created_buttons
            
            # Create group again if needed
            if 'result' not in locals() or not result:
                result = await create_escrow_group(group_name, bot_username, "p2p", event.client, user.id, mention, event)
            
            if result and "invite_url" in result:
                message = P2P_CREATED_MESSAGE.format(
                    GROUP_NUMBER=group_number,
                    GROUP_INVITE_LINK=result["invite_url"],
                    GROUP_NAME=group_name,
                    P2P_IMAGE=P2P_IMAGE
                )
                await event.edit(
                    message,
                    parse_mode='html',
                    link_preview=True,
                    buttons=get_p2p_created_buttons(result["invite_url"])
                )
            else:
                await event.edit(
                    "𝘌𝘴𝘤𝘳𝘰𝘸 𝘊𝘳𝘦𝘢𝘵𝘪𝘰𝘯 𝘍𝘢𝘪𝘭𝘦𝘥\n\nPlease try again later",
                    buttons=[Button.inline("🔄 Try Again", b"create")]
                )
        except Exception as fallback_error:
            print(f"[ERROR] P2P fallback: {fallback_error}")
            await event.edit(
                "𝘌𝘳𝘳𝘰𝘳 𝘊𝘳𝘦𝘢𝘵𝘪𝘯𝘨 𝘌𝘴𝘤𝘳𝘰𝘸\n\nTechnical issue detected",
                buttons=[Button.inline("🔄 Try Again", b"create")]
            )

async def handle_create_other(event):
    """
    Handle OTC deal selection with premium custom emojis - Proper Telethon way
    Using html_parse to merge HTML formatting with custom emoji entities
    """
    try:
        # Get user mention
        user = await event.get_sender()
        mention = user.first_name
        if user.username:
            mention = f"@{user.username}"
        
        # Get bot info
        bot = await event.client.get_me()
        bot_username = bot.username
        set_bot_username(bot_username)
        
        # Get group number
        group_number = get_next_number("other")
        group_name = f"𝖮𝖳𝖢 𝘌𝘴𝘤𝘳𝘰𝘸 𝘚𝘦𝘴𝘴𝘪𝘰𝘯 • #{group_number:02d}"
        
        # Show animation messages with bold formatting using entities
        animation_messages = [
            f"Creating OTC Escrow\nPlease wait {mention}.",
            f"Creating OTC Escrow\nPlease wait {mention}..",
            f"Creating OTC Escrow\nPlease wait {mention}...",
        ]
        
        # Display animation with bold entities
        for msg in animation_messages:
            entities = build_bold_entities(msg)
            await event.edit(msg, formatting_entities=entities)
            await asyncio.sleep(0.5)
        
        # Create group
        result = await create_escrow_group(group_name, bot_username, "other", event.client, user.id, mention, event)
        
        if result and "invite_url" in result:
            from utils.buttons import get_otc_created_buttons
            from telethon.tl.types import MessageEntityCustomEmoji
            from telethon.extensions.html import parse as html_parse
            
            # Get buttons
            buttons = get_otc_created_buttons(result["invite_url"])
            
            # HTML formatted text with placeholders
            html_text = f"""
<b>𝘊𝘶𝘴𝘵𝘰𝘮 𝘌𝘴𝘤𝘳𝘰𝘸 𝘌𝘴𝘵𝘢𝘣𝘭𝘪𝘴𝘩𝘦𝘥</b> 👍

<blockquote>Multi-party agreement group created</blockquote>

<b>Group:</b> {group_name}
<b>Type:</b> Custom Agreement 🐳
<b>Status:</b> Ready for configuration

<code>{result["invite_url"]}</code>

Proceed to the group to define participants and contract terms 🤝
"""
            
            # Step 1: Parse HTML to get text and HTML entities
            parsed_text, html_entities = html_parse(html_text)
            
            # Custom emoji IDs for OTC message
            emoji_map = {
                "👍": 5337080053119336309,
                "🐳": 5323401020368234707,
                "🤝": 5242409048246071737,
            }
            
            # Step 2: Build custom emoji entities using parsed_text
            emoji_entities = []
            
            for emoji, doc_id in emoji_map.items():
                try:
                    # Find position in parsed text
                    index = parsed_text.index(emoji)
                    
                    # Calculate UTF-16 offset
                    utf16_offset = len(parsed_text[:index].encode("utf-16-le")) // 2
                    utf16_length = len(emoji.encode("utf-16-le")) // 2
                    
                    emoji_entities.append(
                        MessageEntityCustomEmoji(
                            offset=utf16_offset,
                            length=utf16_length,
                            document_id=doc_id
                        )
                    )
                    
                    print(f"[DEBUG] Emoji {emoji} at offset {utf16_offset}, length {utf16_length}")
                    
                except ValueError:
                    print(f"[WARNING] Emoji {emoji} not found in parsed text")
                    continue
            
            # Step 3: Merge both entity lists
            all_entities = html_entities + emoji_entities
            all_entities.sort(key=lambda e: e.offset)
            
            print(f"[DEBUG] Total entities: {len(all_entities)} (HTML: {len(html_entities)}, Emoji: {len(emoji_entities)})")
            
            # Step 4: Send WITHOUT parse_mode
            await event.edit(
                parsed_text,
                formatting_entities=all_entities,
                buttons=buttons,
                link_preview=True
            )
            
            print(f"[SUCCESS] OTC Escrow created: {group_name}")
            
        else:
            await event.edit(
                "𝘌𝘴𝘤𝘳𝘰𝘸 𝘊𝘳𝘦𝘢𝘵𝘪𝘰𝘯 𝘍𝘢𝘪𝘭𝘦𝘥\n\nPlease try again later",
                buttons=[Button.inline("🔄 Try Again", b"create")]
            )
            
    except Exception as e:
        print(f"[ERROR] OTC handler: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to regular message without custom emojis
        try:
            from utils.texts import OTHER_CREATED_MESSAGE
            from utils.buttons import get_otc_created_buttons
            
            # Create group again if needed
            if 'result' not in locals() or not result:
                result = await create_escrow_group(group_name, bot_username, "other", event.client, user.id, mention, event)
            
            if result and "invite_url" in result:
                message = OTHER_CREATED_MESSAGE.format(
                    GROUP_NUMBER=group_number,
                    GROUP_INVITE_LINK=result["invite_url"],
                    GROUP_NAME=group_name,
                    OTC_IMAGE=OTC_IMAGE
                )
                await event.edit(
                    message,
                    parse_mode='html',
                    link_preview=True,
                    buttons=get_otc_created_buttons(result["invite_url"])
                )
            else:
                await event.edit(
                    "𝘌𝘴𝘤𝘳𝘰𝘸 𝘊𝘳𝘦𝘢𝘵𝘪𝘰𝘯 𝘍𝘢𝘪𝘭𝘦𝘥\n\nPlease try again later",
                    buttons=[Button.inline("🔄 Try Again", b"create")]
                )
        except Exception as fallback_error:
            print(f"[ERROR] OTC fallback: {fallback_error}")
            await event.edit(
                "𝘌𝘳𝘳𝘰𝘳 𝘊𝘳𝘦𝘢𝘵𝘪𝘯𝘨 𝘌𝘴𝘤𝘳𝘰𝘸\n\nTechnical issue detected",
                buttons=[Button.inline("🔄 Try Again", b"create")]
            )

async def create_escrow_group(group_name, bot_username, group_type, bot_client, creator_user_id, mention, event):
    """
    Create a supergroup
    """
    if not STRING_SESSION1:
        print("[ERROR] STRING_SESSION1 not configured in .env")
        return None
    
    user_client = None
    try:
        # Start user client
        user_client = TelegramClient(StringSession(STRING_SESSION1), API_ID, API_HASH)
        await user_client.start()
        
        print(f"[INFO] User client started")
        
        # Get bot entity
        bot_entity = await user_client.get_entity(bot_username)
        print(f"[INFO] Bot entity: @{bot_username}")
        
        # Get creator's entity
        creator = await user_client.get_me()
        creator_name = creator.username if creator.username else f"ID:{creator.id}"
        print(f"[INFO] Creator: @{creator_name}")
        
        # Create supergroup
        print("[STEP 1] Creating supergroup...")
        created = await user_client(functions.channels.CreateChannelRequest(
            title=group_name,
            about=f"🔐 Secure {group_type.upper()} Escrow Group\nEscrowed by @{bot_username}",
            megagroup=True,
            broadcast=False
        ))
        
        chat = created.chats[0]
        chat_id = chat.id
        channel = types.InputPeerChannel(channel_id=chat.id, access_hash=chat.access_hash)
        print(f"[SUCCESS] Supergroup created: {chat_id}")
        
        # Promote creator as anonymous admin
        print("[STEP 2] Promoting creator as anonymous admin...")
        try:
            await user_client(functions.channels.EditAdminRequest(
                channel=channel,
                user_id=creator,
                admin_rights=ChatAdminRights(
                    change_info=True,
                    post_messages=True,
                    edit_messages=True,
                    delete_messages=True,
                    ban_users=True,
                    invite_users=True,
                    pin_messages=True,
                    add_admins=True,
                    anonymous=True,
                    manage_call=True,
                    other=True
                ),
                rank="Owner"
            ))
            print("[SUCCESS] Creator promoted")
        except Exception as e:
            print(f"[ERROR] Promote creator: {e}")
            return None
        
        # Add and promote bot
        print("[STEP 3] Adding bot...")
        await user_client(functions.channels.InviteToChannelRequest(
            channel=channel,
            users=[bot_entity]
        ))
        
        await user_client(functions.channels.EditAdminRequest(
            channel=channel,
            user_id=bot_entity,
            admin_rights=ChatAdminRights(
                change_info=True,
                post_messages=True,
                edit_messages=True,
                delete_messages=True,
                ban_users=True,
                invite_users=True,
                pin_messages=True,
                add_admins=False,
                anonymous=False,
                manage_call=True,
                other=True
            ),
            rank="Escrow Bot"
        ))
        print("[SUCCESS] Bot added")
        
        # Send welcome message
        print("[STEP 4] Sending welcome message...")
        from utils.texts import WELCOME_MESSAGE
        welcome_msg = WELCOME_MESSAGE.format(bot_username=bot_username)
        
        sent_message = await user_client.send_message(
            channel,
            welcome_msg,
            parse_mode='html'
        )
        
        # Pin the welcome message
        await user_client.pin_message(channel, sent_message, notify=False)
        print("[SUCCESS] Welcome pinned")
        
        # Create invite link
        print("[STEP 5] Creating invite...")
        invite_link = await user_client(functions.messages.ExportChatInviteRequest(
            peer=channel
        ))
        invite_url = str(invite_link.link)
        
        print("[COMPLETE] Group setup done")
        
        # Store group data
        store_group_data(chat_id, group_name, group_type, creator.id, bot_username, creator_name, creator_user_id)
        
        # Send log to channel using BOT (not session string)
        try:
            await send_log_to_channel_bot(event.client, group_name, group_type, creator, chat_id, invite_url, creator_user_id, mention)
        except Exception as log_error:
            print(f"[WARNING] Bot log failed: {log_error}")
            # Continue even if log fails
        
        return {
            "group_id": chat_id,
            "invite_url": invite_url,
            "group_name": group_name,
            "creator_id": creator.id,
            "creator_user_id": creator_user_id,
            "creator_username": creator_name,
            "bot_username": bot_username,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        print(f"[ERROR] Group creation: {e}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        if user_client and user_client.is_connected():
            await user_client.disconnect()
            print("[INFO] User client disconnected")

async def send_log_to_channel_bot(bot_client, group_name, group_type, creator, chat_id, invite_url, creator_user_id, mention):
    """Send creation log to channel using BOT (not session string) with premium emojis"""
    try:
        # Format the log message exactly as requested
        group_type_display = "#𝗉2𝗉" if group_type == "p2p" else "#𝗈𝗍𝖼"
        clean_chat_id = str(chat_id)
        if clean_chat_id.startswith('-100'):
            clean_chat_id = clean_chat_id[4:]
        
        log_text = f"""#𝖭𝖾𝗐 𝖤𝗌𝖼𝗋𝗈𝗐 𝖦𝗋𝗈𝗎𝗉 𝖢𝗋𝖾𝖺𝗍𝖾𝖽 & 𝖲𝖺𝗏𝖾𝖽.

𝖣𝖾𝖺𝗅 𝖳𝗒𝗉𝖾 : {group_type_display} 💸
𝖭𝖺𝗆𝖾 : {group_name} 🔗
𝖢𝗁𝖺𝗍 𝖨𝖣 : {clean_chat_id} 🥂
Link : {invite_url}

𝖢𝗋𝖾𝖺𝗍𝖾𝖽 𝖡𝗒 : {mention} 🟢
𝖴𝗌𝖾𝗋 𝖨𝖣 : {creator_user_id} ➖"""

        # Build entities for log message
        entities = build_log_entities(log_text)
        
        # Send to log channel using the BOT client
        try:
            await bot_client.send_message(
                LOG_CHANNEL_ID,
                log_text,
                formatting_entities=entities
            )
            print(f"[LOG] Sent to channel using BOT with premium emojis")
            
        except Exception as e:
            print(f"[ERROR] Bot failed to send log: {e}")
            
            # Fallback: try to send without entities
            try:
                await bot_client.send_message(
                    LOG_CHANNEL_ID,
                    log_text
                )
                print(f"[LOG] Sent to channel using BOT (plain text)")
            except Exception as e2:
                print(f"[ERROR] Bot fallback also failed: {e2}")
        
    except Exception as e:
        print(f"[ERROR] Preparing log: {e}")

def store_group_data(group_id, group_name, group_type, creator_id, bot_username, creator_username, creator_user_id):
    """Store group data"""
    try:
        GROUPS_FILE = 'data/active_groups.json'
        groups = {}
        
        if os.path.exists(GROUPS_FILE):
            with open(GROUPS_FILE, 'r') as f:
                groups = json.load(f)
        
        # Clean group ID
        clean_group_id = str(group_id)
        if clean_group_id.startswith('-100'):
            clean_group_id = clean_group_id[4:]
        
        groups[clean_group_id] = {
            "name": group_name,
            "type": group_type,
            "creator_id": creator_id,
            "creator_user_id": creator_user_id,
            "creator_username": creator_username,
            "bot_username": bot_username,
            "original_id": str(group_id),
            "members": [],
            "welcome_pinned": True,
            "session_initiated": False,
            "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "created_timestamp": time.time()
        }
        
        with open(GROUPS_FILE, 'w') as f:
            json.dump(groups, f, indent=2)
            
        print(f"[INFO] Group data stored")
        
    except Exception as e:
        print(f"[ERROR] Storing data: {e}")
