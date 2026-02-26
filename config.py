import os
import json
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
API_ID = int(os.getenv('API_ID', 0))
API_HASH = os.getenv('API_HASH', '')
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

# User session for group creation
STRING_SESSION1 = os.getenv('STRING_SESSION1', '')

# Bot username (will be set dynamically)
BOT_USERNAME = ""
MONGO_URI = "mongodb+srv://kyurebc:VsUsi43gwToAT3cR@cluster0.p50wsey.mongodb.net/?appName=Cluster0"
DB_NAME = "OneEscrowUsers"
LOG_CHANNEL_ID=-1003821511613
OWNER_ID = 7339063037

# Add these to your config.py file

# Image URLs
OTC_IMAGE = ""
P2P_IMAGE = ""

# Ensure data directory exists
os.makedirs('data', exist_ok=True)

# Simple group counter
COUNTER_FILE = 'data/counter.json'

def get_next_number(group_type="p2p"):
    """Get next sequential group number"""
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
        print(f"Error in get_next_number: {e}")
        return 1

def set_bot_username(username):
    """Set bot username globally"""
    global BOT_USERNAME
    BOT_USERNAME = username
