from telethon import events
from telethon.tl.types import MessageEntityCustomEmoji, MessageEntityBold
from config import OWNER_ID, LOG_CHANNEL_ID, BOT_USERNAME, MONGO_URI, DB_NAME
from core.logger import get_logger
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import asyncio
import time
import os

logger = get_logger("Trisha.core.broadcast")

# MongoDB connection
_mongo_client = None
_db = None

async def get_db():
    """Get MongoDB database instance"""
    global _mongo_client, _db
    try:
        if _mongo_client is None:
            _mongo_client = AsyncIOMotorClient(MONGO_URI)
            _db = _mongo_client[DB_NAME]
            # Test connection
            await _db.command('ping')
            logger.success("MongoDB connected successfully")
        return _db
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        return None

async def get_all_users():
    """Get all user IDs from database"""
    try:
        db = await get_db()
        if db is None:
            logger.error("Database connection failed")
            return []
        
        # Using "users" collection to match start.py
        users_collection = db["users"]
        cursor = users_collection.find({}, {"user_id": 1})
        users = await cursor.to_list(length=None)
        user_ids = [user["user_id"] for user in users]
        
        logger.info(f"Loaded {len(user_ids)} users from users collection")
        return user_ids
    except Exception as e:
        logger.error(f"Error getting users from DB: {e}")
        return []

async def send_broadcast_message(client, user_id, message, file=None, file_name=None, buttons=None):
    """Send broadcast message to a single user"""
    try:
        if file:
            # If it's an image, ensure it has .png extension
            if file_name and not file_name.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                file_name = f"{file_name}.png"
            elif not file_name:
                file_name = "broadcast_image.png"
                
            await client.send_file(
                user_id, 
                file, 
                caption=message, 
                parse_mode='html', 
                buttons=buttons,
                file_name=file_name
            )
        else:
            await client.send_message(user_id, message, parse_mode='html', buttons=buttons)
        return True, None
    except Exception as e:
        error_msg = str(e)
        if "USER_IS_BLOCKED" in error_msg:
            return False, "blocked"
        elif "PEER_ID_INVALID" in error_msg:
            return False, "invalid"
        elif "CHAT_WRITE_FORBIDDEN" in error_msg:
            return False, "no_write"
        else:
            return False, "error"

def format_eta(seconds):
    """Format ETA time"""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

def format_time_taken(seconds):
    """Format time taken in readable format"""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

def build_custom_entities(text, emoji_map=None, bold_ranges=None):
    """
    Dynamically build custom emoji and bold entities with correct UTF-16 offsets
    
    Args:
        text: Full message string
        emoji_map: Dictionary mapping emoji characters to document_ids
        bold_ranges: List of tuples (start_idx, length) for bold text (character indices)
    
    Returns:
        List of MessageEntity objects with correct offsets
    """
    entities = []
    
    # Add bold entities
    if bold_ranges:
        for start_char, length_char in bold_ranges:
            # Convert character offsets to UTF-16 offsets
            prefix = text[:start_char]
            utf16_offset = len(prefix.encode('utf-16-le')) // 2
            utf16_length = len(text[start_char:start_char+length_char].encode('utf-16-le')) // 2
            entities.append(MessageEntityBold(offset=utf16_offset, length=utf16_length))
    
    # Add custom emoji entities
    if emoji_map:
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

async def update_broadcast_status(event, broadcast_msg, start_time, total_users, processed, success, failed):
    """Update broadcast status message"""
    elapsed = time.time() - start_time
    if processed > 0:
        avg_time = elapsed / processed
        remaining = avg_time * (total_users - processed)
        eta = format_eta(remaining)
    else:
        eta = "calculating..."
    
    # Status text
    status_text = f"🚀 » Started Broadcasting.... Once Its Done I will let you know about it.\n ➖  ETA : {eta} 🔥"
    
    # Map emojis to their document IDs
    emoji_map = {
        "🚀": 5258332798409783582,
        "🔥": 6026036220927151662
    }
    
    # No bold ranges needed for status
    entities = build_custom_entities(status_text, emoji_map=emoji_map)
    
    try:
        await broadcast_msg.edit(status_text, formatting_entities=entities)
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        # Fallback to plain text
        await broadcast_msg.edit(f"Started Broadcasting... ETA: {eta}")

async def log_broadcast_result_to_channel(client, completion_text, total_users, success_count, failed_count, start_time, file_type=None):
    """Log broadcast results to log channel with the same format as completion message"""
    try:
        elapsed = time.time() - start_time
        elapsed_str = format_time_taken(elapsed)
        
        # Format the log message exactly like the completion message
        log_text = f"Broadcast Completed. ✌️\nSuccessfully Broadcasted To {success_count} users. And Failed To Broadcast {failed_count} users. 📰\nTime Taken : {elapsed_str}"
        
        # Map emojis for log message
        log_emoji_map = {
            "✌️": 5273802055134229167,
            "📰": 5257952710983955418
        }
        
        # Define bold ranges (character indices)
        bold_ranges = [
            (log_text.find(f"Broadcast Completed"), len("Broadcast Completed")),
            (log_text.find(f"Successfully Broadcasted To {success_count}"), len(f"Successfully Broadcasted To {success_count}")),
            (log_text.find(f"Failed To Broadcast {failed_count}"), len(f"Failed To Broadcast {failed_count}")),
            (log_text.find(f"Time Taken"), len("Time Taken"))
        ]
        
        # Build entities
        log_entities = build_custom_entities(
            log_text,
            emoji_map=log_emoji_map,
            bold_ranges=bold_ranges
        )
        
        # Send to log channel
        await client.send_message(
            LOG_CHANNEL_ID,
            log_text,
            formatting_entities=log_entities
        )
        
        logger.info(f"Broadcast result logged to channel")
    except Exception as e:
        logger.error(f"Error logging broadcast result to channel: {e}")

@events.register(events.NewMessage(pattern='/broadcast'))
async def handle_broadcast(event):
    """
    Handle /broadcast command - Only owner can use
    Usage: /broadcast <message> or reply to a message with /broadcast
    """
    try:
        # Owner check at the very top
        if event.sender_id != OWNER_ID:
            await event.respond("❌ This command is only for bot owner.")
            return
        
        # Get all users from database
        logger.info("Fetching users from users collection...")
        users = await get_all_users()
        
        if not users:
            await event.respond("❌ No users found in database.")
            return
        
        total_users = len(users)
        logger.info(f"Starting broadcast to {total_users} users")
        
        # Get broadcast content
        message_text = None
        file = None
        file_name = None
        
        if event.is_reply:
            # If replying to a message, get that message's content
            replied = await event.get_reply_message()
            message_text = replied.text or replied.message or ""
            if replied.media:
                file = await replied.download_media(file=bytes)
                # Set proper filename for image
                if replied.file and replied.file.name:
                    file_name = replied.file.name
                else:
                    # Generate filename based on media type
                    if replied.photo:
                        file_name = f"broadcast_image_{int(time.time())}.png"
                    elif replied.document:
                        file_name = replied.document.attributes[0].file_name if replied.document.attributes else f"broadcast_file_{int(time.time())}"
                    else:
                        file_name = f"broadcast_media_{int(time.time())}"
                logger.info(f"Broadcasting media file as: {file_name}")
        else:
            # Get text from command
            message_text = event.message.text.replace('/broadcast', '', 1).strip()
            if not message_text:
                await event.respond("❌ Please provide a message to broadcast or reply to a message.")
                return
        
        # Initial status text
        start_text = "🚀 » Started Broadcasting.... Once Its Done I will let you know about it.\n ➖  ETA : calculating... 🔥"
        
        # Map emojis for start message
        start_emoji_map = {
            "🚀": 5258332798409783582,
            "🔥": 6026036220927151662
        }
        
        # Build entities for start message
        start_entities = build_custom_entities(start_text, emoji_map=start_emoji_map)
        
        # Send initial status (reply to the original command)
        start_time = time.time()
        broadcast_msg = await event.reply(
            start_text,
            formatting_entities=start_entities
        )
        
        # Statistics
        success_count = 0
        failed_count = 0
        blocked_count = 0
        invalid_count = 0
        processed = 0
        
        # Send broadcast to all users
        logger.info(f"Broadcasting to {total_users} users...")
        for user_id in users:
            try:
                success, reason = await send_broadcast_message(
                    event.client, 
                    user_id, 
                    message_text, 
                    file,
                    file_name
                )
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    if reason == "blocked":
                        blocked_count += 1
                    elif reason == "invalid":
                        invalid_count += 1
                
                processed += 1
                
                # Update status every 10 users
                if processed % 10 == 0:
                    await update_broadcast_status(
                        event, broadcast_msg, start_time,
                        total_users, processed, success_count, failed_count
                    )
                
                # Small delay to avoid flooding
                await asyncio.sleep(0.05)
                
            except Exception as e:
                logger.error(f"Error broadcasting to {user_id}: {e}")
                failed_count += 1
                processed += 1
        
        # Final status update
        await update_broadcast_status(
            event, broadcast_msg, start_time,
            total_users, processed, success_count, failed_count
        )
        
        # Format time taken
        time_taken = format_time_taken(time.time() - start_time)
        
        # Completion message with bold formatting
        completion_text = f"Broadcast Completed. ✌️\nSuccessfully Broadcasted To {success_count} users. And Failed To Broadcast {failed_count} users. 📰\nTime Taken : {time_taken}"
        
        # Map emojis for completion message
        completion_emoji_map = {
            "✌️": 5273802055134229167,
            "📰": 5257952710983955418
        }
        
        # Define bold ranges (character indices)
        bold_ranges = [
            (completion_text.find(f"Broadcast Completed"), len("Broadcast Completed")),
            (completion_text.find(f"Successfully Broadcasted To {success_count}"), len(f"Successfully Broadcasted To {success_count}")),
            (completion_text.find(f"Failed To Broadcast {failed_count}"), len(f"Failed To Broadcast {failed_count}")),
            (completion_text.find(f"Time Taken"), len("Time Taken"))
        ]
        
        # Build completion entities
        completion_entities = build_custom_entities(
            completion_text, 
            emoji_map=completion_emoji_map,
            bold_ranges=bold_ranges
        )
        
        # Send completion message (reply to the original command)
        await event.reply(completion_text, formatting_entities=completion_entities)
        
        # Log the same message to the channel
        await log_broadcast_result_to_channel(
            event.client, completion_text, total_users,
            success_count, failed_count, start_time
        )
        
        logger.info(f"Broadcast completed: {success_count} success, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Error in broadcast handler: {e}")
        await event.reply(f"❌ Error during broadcast: {str(e)[:100]}")
