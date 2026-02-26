from telethon import events
from utils.texts import START_MESSAGE
from utils.buttons import get_main_menu_buttons
from datetime import datetime
from config import MONGO_URI, DB_NAME, LOG_CHANNEL_ID, BOT_USERNAME
from core.logger import get_logger
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib

logger = get_logger("Trisha.core.start")

# MongoDB client (will be initialized lazily)
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

def generate_user_hash(user_id):
    """Generate a unique hash for user"""
    try:
        # Create a hash using user_id and a secret salt
        hash_string = f"{user_id}_{BOT_USERNAME}_escrow_secret"
        return hashlib.md5(hash_string.encode()).hexdigest()[:10]
    except Exception as e:
        logger.error(f"Error generating user hash: {e}")
        return "unknown"

async def get_total_users():
    """Get total users count from database"""
    try:
        db = await get_db()
        if db is None:  # Fix: Compare with None instead of truth value
            return 0
        users_collection = db["users"]
        return await users_collection.count_documents({})
    except Exception as e:
        logger.error(f"Error getting total users: {e}")
        return 0

async def save_user_to_db(user):
    """Save or update user in database"""
    try:
        db = await get_db()
        if db is None:  # Fix: Compare with None instead of truth value
            logger.error("Database is None, cannot save user")
            return False, False
            
        users_collection = db["users"]
        
        # Check if user exists
        existing_user = await users_collection.find_one({"user_id": user.id})
        is_new = existing_user is None
        
        # Prepare user data
        user_data = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": getattr(user, 'last_name', ''),
            "language_code": getattr(user, 'lang_code', 'en'),
            "is_bot": getattr(user, 'bot', False),
            "is_premium": getattr(user, 'premium', False),
            "last_active": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        if is_new:
            user_data["first_seen"] = datetime.utcnow()
            await users_collection.insert_one(user_data)
            logger.info(f"New user saved to DB: {user.id}")
        else:
            await users_collection.update_one(
                {"user_id": user.id},
                {"$set": user_data}
            )
            logger.info(f"User updated in DB: {user.id}")
        
        return True, is_new
    except Exception as e:
        logger.error(f"Error saving user to DB: {e}")
        return False, False

async def log_to_channel(event, user, is_new_user):
    """Log user start to log channel with exact format"""
    try:
        client = event.client
        
        # Generate user hash
        user_hash = generate_user_hash(user.id)
        
        # Create mention
        mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
        
        # Get total users count
        total_users = await get_total_users()
        
        # Format username
        username = f"@{user.username}" if user.username else "No username"
        
        # Create log message with exact format
        log_message = f"""{mention} 𝘚𝘵𝘢𝘳𝘵𝘦𝘥 𝘛𝘩𝘦 𝘉𝘰𝘵.
𝘜𝘴𝘦𝘳 𝘏𝘢𝘴𝘩 : <code>{user_hash}</code>
𝘜𝘴𝘦𝘳 𝘐𝘋 : <code>{user.id}</code>
𝘜𝘴𝘦𝘳𝘯𝘢𝘮𝘦 : {username}
𝘛𝘰𝘵𝘢𝘭 𝘜𝘱𝘥𝘢𝘵𝘦𝘥 𝘜𝘴𝘦𝘳𝘴 𝘐𝘯 𝘋𝘣 : <code>{total_users}</code>"""
        
        await client.send_message(
            LOG_CHANNEL_ID,
            log_message,
            parse_mode='html'
        )
        logger.info(f"Logged user start to channel: {user.id}")
    except Exception as e:
        logger.error(f"Error logging to channel: {e}")

async def handle_start(event):
    """
    Handle /start command
    """
    try:
        # Get user who started the bot
        user = await event.get_sender()
        
        # Save user to database
        saved, is_new = await save_user_to_db(user)
        
        if saved:
            # Log to channel
            await log_to_channel(event, user, is_new)
            logger.info(f"User {'new' if is_new else 'returning'}: {user.id} (@{user.username})")
        else:
            logger.warning(f"Failed to save user to DB: {user.id}")
        
        # Send start message
        await event.respond(
            START_MESSAGE,
            buttons=get_main_menu_buttons(),
            parse_mode='html'
        )
        
    except Exception as e:
        logger.error(f"Error in start handler: {e}")
        await event.respond("❌ An error occurred. Please try again.")
