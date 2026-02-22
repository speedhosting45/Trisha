# handlers/addresses.py
"""
Address handlers for OneEscrow Bot
Upgraded version with /verify, /buyer, /seller, /addresses commands
"""

import re
import json
import os
import logging
import time
from typing import Dict, Optional, Tuple, List
from datetime import datetime
from telethon import events, Button

# Configure colorful logging
class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    grey = "\x1b[38;21m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[38;5;226m"
    red = "\x1b[38;5;196m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[38;5;40m"
    cyan = "\x1b[38;5;51m"
    magenta = "\x1b[38;5;201m"
    reset = "\x1b[0m"

    def __init__(self, fmt):
        super().__init__()
        self.fmt = fmt
        self.FORMATS = {
            logging.DEBUG: self.grey + self.fmt + self.reset,
            logging.INFO: self.green + self.fmt + self.reset,
            logging.WARNING: self.yellow + self.fmt + self.reset,
            logging.ERROR: self.red + self.fmt + self.reset,
            logging.CRITICAL: self.bold_red + self.fmt + self.reset
        }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%H:%M:%S')
        return formatter.format(record)

# Setup logger
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Data files
USER_ADDRESSES_FILE = os.path.join(BASE_DIR, 'data/user_addresses.json')
USER_ROLES_FILE = os.path.join(BASE_DIR, 'data/user_roles.json')
ACTIVE_GROUPS_FILE = os.path.join(BASE_DIR, 'data/active_groups.json')
WALLETS_FILE = os.path.join(BASE_DIR, 'data/wallets.json')

# ==================== DATA MANAGEMENT ====================
def load_json(filepath: str, default=None):
    """Load JSON with error handling"""
    if default is None:
        default = {}
    
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {filepath}: {e}")
    
    return default

def save_json(filepath: str, data: Dict) -> bool:
    """Save JSON with directory creation"""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save {filepath}: {e}")
        return False

def normalize_group_id(chat_id) -> str:
    """
    Normalize group ID to a consistent format
    ALWAYS use str(chat.id), no cleaning, no -100 removal
    """
    try:
        if isinstance(chat_id, str):
            return chat_id
        return str(chat_id)
    except Exception as e:
        logger.error(f"Error normalizing group ID: {e}")
        return str(chat_id)

# ==================== BLOCKCHAIN VALIDATOR ====================
class BlockchainValidator:
    """Blockchain address validator with explorer URLs"""
    
    CHAINS = {
        'BTC': {
            'name': 'Bitcoin',
            'regex': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59}$',
            'explorer': 'https://blockchain.com/explorer/addresses/btc/{address}',
            'color': '\x1b[38;5;226m'  # Yellow
        },
        'ETH': {
            'name': 'Ethereum',
            'regex': r'^0x[a-fA-F0-9]{40}$',
            'explorer': 'https://etherscan.io/address/{address}',
            'color': '\x1b[38;5;105m'  # Light blue
        },
        'BSC': {
            'name': 'BNB Smart Chain',
            'regex': r'^0x[a-fA-F0-9]{40}$',
            'explorer': 'https://bscscan.com/address/{address}',
            'color': '\x1b[38;5;220m'  # Gold
        },
        'TRX': {
            'name': 'Tron',
            'regex': r'^T[a-zA-Z0-9]{33}$',
            'explorer': 'https://tronscan.org/#/address/{address}',
            'color': '\x1b[38;5;197m'  # Red
        },
        'LTC': {
            'name': 'Litecoin',
            'regex': r'^(ltc1|[LM])[a-zA-HJ-NP-Z0-9]{26,33}$',
            'explorer': 'https://blockchair.com/litecoin/address/{address}',
            'color': '\x1b[38;5;39m'  # Blue
        },
        'MATIC': {
            'name': 'Polygon',
            'regex': r'^0x[a-fA-F0-9]{40}$',
            'explorer': 'https://polygonscan.com/address/{address}',
            'color': '\x1b[38;5;129m'  # Purple
        },
        'SOL': {
            'name': 'Solana',
            'regex': r'^[1-9A-HJ-NP-Za-km-z]{32,44}$',
            'explorer': 'https://solscan.io/account/{address}',
            'color': '\x1b[38;5;141m'  # Purple
        },
        'ADA': {
            'name': 'Cardano',
            'regex': r'^addr1[a-zA-Z0-9]{50,}$',
            'explorer': 'https://cardanoscan.io/address/{address}',
            'color': '\x1b[38;5;33m'  # Blue
        }
    }
    
    @staticmethod
    def detect_chain(address: str) -> Tuple[Optional[str], Optional[str]]:
        """Detect blockchain from address"""
        address = address.strip()
        
        for chain_code, config in BlockchainValidator.CHAINS.items():
            if re.match(config['regex'], address):
                return chain_code, config['name']
        
        return None, None
    
    @staticmethod
    async def verify_address(address: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
        """
        Verify address and return (is_valid, chain_code, chain_name, explorer_url)
        """
        chain_code, chain_name = BlockchainValidator.detect_chain(address)
        
        if not chain_code:
            return False, None, None, None
        
        # Get explorer URL
        explorer_url = BlockchainValidator.CHAINS[chain_code]['explorer'].format(address=address)
        
        return True, chain_code, chain_name, explorer_url

# ==================== ROLE MANAGER ====================
class RoleManager:
    """Check user roles from existing data"""
    
    @staticmethod
    def get_user_role(user_id: int, group_id: str) -> Optional[str]:
        """Get user's role from existing user_roles.json"""
        try:
            roles = load_json(USER_ROLES_FILE, {})
            normalized_group_id = normalize_group_id(group_id)
            
            logger.info(f"[ 🔍 ] Checking role for user {user_id} in group {normalized_group_id}")
            
            group_roles = roles.get(normalized_group_id, {})
            
            for uid, role_data in group_roles.items():
                if str(user_id) == uid:
                    role = role_data.get('role')
                    logger.info(f"[ ✅ ] Found role: {role} for user {user_id}")
                    return role
            
            logger.warning(f"[ ⚠️ ] No role found for user {user_id} in group {normalized_group_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting user role: {e}")
            return None
    
    @staticmethod
    def can_use_command(user_id: int, command_role: str, group_id: str) -> bool:
        """Check if user can use command based on their existing role"""
        user_role = RoleManager.get_user_role(user_id, group_id)
        return user_role == command_role
    
    @staticmethod
    def is_group_creator(user_id: int, group_id: str) -> bool:
        """Check if user is group creator (from stored data)"""
        try:
            groups = load_json(ACTIVE_GROUPS_FILE, {})
            normalized_group_id = normalize_group_id(group_id)
            
            group_data = groups.get(normalized_group_id, {})
            creator_id = group_data.get('created_by')
            
            return creator_id == user_id
        except Exception as e:
            logger.error(f"Error checking group creator: {e}")
            return False

# ==================== MESSAGE TEMPLATES ====================
class MessageTemplates:
    """Message templates for address handler - HTML format"""
    
    @staticmethod
    def processing():
        return "<b>🔍 Processing your address...</b>"
    
    @staticmethod
    def invalid_format():
        return """<b>❌ Invalid Address Format!</b>

Please use a valid address format:
• <b>Bitcoin (BTC):</b> <code>1A1zP1...</code> or <code>bc1q...</code>
• <b>Ethereum (ETH):</b> <code>0x...</code>
• <b>BNB Chain (BSC):</b> <code>0x...</code>
• <b>Tron (TRX):</b> <code>T...</code>
• <b>Litecoin (LTC):</b> <code>L...</code> or <code>ltc1q...</code>
• <b>Polygon (MATIC):</b> <code>0x...</code>
• <b>Solana (SOL):</b> <code>base58 string</code>"""
    
    @staticmethod
    def no_role():
        return """<b>❌ No Role Assigned!</b>

You don't have a role in this escrow session.
Please wait for /begin to assign roles."""
    
    @staticmethod
    def role_mismatch(user_role: str, command_role: str):
        return f"""<b>⚠️ Role Mismatch!</b>

You are registered as <b>{user_role.upper()}</b>, but trying to use <b>{command_role.upper()}</b> command.

Please use <code>/{user_role}</code> instead."""
    
    @staticmethod
    def buyer_success(user_name: str, address: str, chain_name: str, chain_code: str):
        return f"""<b>✅ BUYER ADDRESS SAVED SUCCESSFULLY!</b>

<b>Buyer Wallet Stats</b>
<u>Address :</u>

<blockquote>
Balance : Unavailable
Last Txn : Unavailable
Chain : {chain_name}
Network : {chain_code}
</blockquote>

This wallet has been saved for this deal."""
    
    @staticmethod
    def seller_success(user_name: str, address: str, chain_name: str, chain_code: str):
        return f"""<b>✅ SELLER ADDRESS SAVED SUCCESSFULLY!</b>

<b>Seller Wallet Stats</b>
<u>Address :</u>

<blockquote>
Balance : Unavailable
Last Txn : Unavailable
Chain : {chain_name}
Network : {chain_code}
</blockquote>

This wallet has been saved for this deal."""
    
    @staticmethod
    def verify_success(address: str, chain_name: str, chain_code: str):
        return f"""<b>🔍 WALLET VERIFICATION</b>

<blockquote>
Chain : {chain_name}
Network : {chain_code}
Valid : Yes
</blockquote>"""
    
    @staticmethod
    def address_summary(chat_title: str, buyer_data: Dict, seller_data: Dict):
        buyer_address = buyer_data.get('address', 'Not Set') if buyer_data else 'Not Set'
        buyer_chain = buyer_data.get('chain_name', '—') if buyer_data else '—'
        buyer_network = buyer_data.get('chain', '—') if buyer_data else '—'
        
        seller_address = seller_data.get('address', 'Not Set') if seller_data else 'Not Set'
        seller_chain = seller_data.get('chain_name', '—') if seller_data else '—'
        seller_network = seller_data.get('chain', '—') if seller_data else '—'
        
        if buyer_address != 'Not Set':
            buyer_address = f"<code>{buyer_address[:16]}...{buyer_address[-8:]}</code>"
        
        if seller_address != 'Not Set':
            seller_address = f"<code>{seller_address[:16]}...{seller_address[-8:]}</code>"
        
        return f"""<b>📜 ESCROW ADDRESS SUMMARY</b>

<b>CHAT NAME :</b> {chat_title}

<b>BUYER :</b>
Address : {buyer_address}
Chain : {buyer_chain}
Network : {buyer_network}

<b>SELLER :</b>
Address : {seller_address}
Chain : {seller_chain}
Network : {seller_network}"""
    
    @staticmethod
    def chain_mismatch(buyer_chain: str, seller_chain: str):
        return f"""<b>❌ CHAIN MISMATCH DETECTED</b>

Buyer Chain : {buyer_chain}
Seller Chain : {seller_chain}

<b>Both parties must use the same blockchain.</b>"""
    
    @staticmethod
    def escrow_ready(buyer_chain: str):
        return f"""<b>🎉 ESCROW READY</b>

Both wallets verified
Same blockchain detected
Escrow ready for deposit"""
    
    @staticmethod
    def already_set(role: str, chain_name: str, address: str):
        return f"""<b>⚠️ Address Already Set!</b>

You already have a {role} address saved:
<code>{address[:16]}...{address[-8:]}</code>
<b>Chain:</b> {chain_name}

Contact admin to change address."""
    
    @staticmethod
    def not_in_group():
        return "<b>❌ This command only works in groups!</b>"
    
    @staticmethod
    def missing_address(role: str):
        return f"<b>Usage:</b> <code>/{role} [your_wallet_address]</code>"
    
    @staticmethod
    def missing_address_verify():
        return "<b>Usage:</b> <code>/verify [wallet_address]</code>"

# ==================== ADDRESS HANDLER ====================
class AddressHandler:
    """Main address handler for buyer/seller commands"""
    
    def __init__(self, client):
        self.client = client
        self.validator = BlockchainValidator()
        logger.info("[ 📝 ] " + "="*50)
        logger.info("[ 📝 ] Address Handler initialized")
        logger.info("[ 📝 ] " + "="*50)
    
    def setup_handlers(self):
        """Setup command handlers"""
        
        @self.client.on(events.NewMessage(pattern=r'^/buyer(\s+|$)'))
        async def buyer_handler(event):
            await self.handle_address_command(event, 'buyer')
        
        @self.client.on(events.NewMessage(pattern=r'^/seller(\s+|$)'))
        async def seller_handler(event):
            await self.handle_address_command(event, 'seller')
        
        @self.client.on(events.NewMessage(pattern=r'^/addresses$'))
        async def addresses_handler(event):
            await self.show_addresses(event)
        
        @self.client.on(events.NewMessage(pattern=r'^/verify(\s+|$)'))
        async def verify_handler(event):
            await self.handle_verify_command(event)
        
        # Callback handlers for change buttons
        @self.client.on(events.CallbackQuery(pattern=r'change_buyer_(.+)'))
        async def change_buyer_callback(event):
            await self.handle_change_wallet(event, 'buyer')
        
        @self.client.on(events.CallbackQuery(pattern=r'change_seller_(.+)'))
        async def change_seller_callback(event):
            await self.handle_change_wallet(event, 'seller')
        
        logger.info("[ 📝 ] Address command handlers registered")
    
    async def handle_verify_command(self, event):
        """Handle /verify command - Check any wallet address"""
        try:
            chat = await event.get_chat()
            
            # Check if in group
            if not hasattr(chat, 'title'):
                await event.reply(MessageTemplates.not_in_group(), parse_mode='html')
                return
            
            # Get address from command
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(MessageTemplates.missing_address_verify(), parse_mode='html')
                return
            
            address = parts[1].strip()
            
            # Show processing
            processing_msg = await event.reply(MessageTemplates.processing(), parse_mode='html')
            
            # Validate address
            is_valid, chain_code, chain_name, explorer_url = await self.validator.verify_address(address)
            
            if not is_valid:
                await processing_msg.edit(MessageTemplates.invalid_format(), parse_mode='html')
                return
            
            # Create success message
            success_msg = MessageTemplates.verify_success(address, chain_name, chain_code)
            
            # Create view button
            buttons = [[Button.url("🔎 View Wallet", explorer_url)]]
            
            await processing_msg.edit(success_msg, buttons=buttons, parse_mode='html')
            
            logger.info(f"[ 🔍 ] Verified address in {chat.title}: {chain_code}")
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error in verify command: {e}", exc_info=True)
            try:
                await event.reply("<b>❌ An error occurred. Please try again.</b>", parse_mode='html')
            except:
                pass
    
    async def handle_address_command(self, event, role: str):
        """Handle /buyer or /seller command"""
        try:
            user = await event.get_sender()
            chat = await event.get_chat()
            
            user_id = user.id
            # CRITICAL: Use chat.id, NOT event.chat_id
            group_id = normalize_group_id(chat.id)
            
            role_color = '\x1b[38;5;51m' if role == 'buyer' else '\x1b[38;5;201m'
            logger.info(f"[ {role_color}{role.upper()}\x1b[0m ] Command from user {user_id} in group {group_id}")
            
            # Check if in group
            if not hasattr(chat, 'title'):
                await event.reply(MessageTemplates.not_in_group(), parse_mode='html')
                return
            
            # Check user's role
            user_role = RoleManager.get_user_role(user_id, group_id)
            
            if not user_role:
                await event.reply(MessageTemplates.no_role(), parse_mode='html')
                logger.warning(f"[ ⚠️ ] User {user_id} has no role in group {group_id}")
                return
            
            if user_role != role:
                await event.reply(MessageTemplates.role_mismatch(user_role, role), parse_mode='html')
                logger.warning(f"[ ⚠️ ] Role mismatch: user={user_role}, command={role}")
                return
            
            # Get address from command
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.reply(MessageTemplates.missing_address(role), parse_mode='html')
                return
            
            address = parts[1].strip()
            
            # Show processing
            processing_msg = await event.reply(MessageTemplates.processing(), parse_mode='html')
            
            # Validate address
            is_valid, chain_code, chain_name, explorer_url = await self.validator.verify_address(address)
            
            if not is_valid:
                await processing_msg.edit(MessageTemplates.invalid_format(), parse_mode='html')
                return
            
            # Check if user already has address saved
            addresses = load_json(USER_ADDRESSES_FILE, {})
            chat_addresses = addresses.get(group_id, {})
            
            if role in chat_addresses and chat_addresses[role].get('user_id') == user_id:
                # User already has address saved
                existing = chat_addresses[role]
                await processing_msg.edit(
                    MessageTemplates.already_set(role, existing['chain_name'], existing['address']),
                    parse_mode='html'
                )
                return
            
            # Prepare address data
            address_data = {
                'user_id': user_id,
                'user_name': user.first_name or f"User_{user_id}",
                'address': address,
                'chain': chain_code,
                'chain_name': chain_name,
                'timestamp': time.time(),
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Save to user_addresses.json
            if group_id not in addresses:
                addresses[group_id] = {}
            
            addresses[group_id][role] = address_data
            save_json(USER_ADDRESSES_FILE, addresses)
            
            # ALSO save to wallets.json for main.py compatibility
            wallets = load_json(WALLETS_FILE, {})
            if group_id not in wallets:
                wallets[group_id] = {}
            
            if role == 'buyer':
                wallets[group_id]['buyer_wallet'] = address
                wallets[group_id]['buyer_id'] = user_id
            else:
                wallets[group_id]['seller_wallet'] = address
                wallets[group_id]['seller_id'] = user_id
            
            save_json(WALLETS_FILE, wallets)
            
            # Send success message with appropriate template
            if role == 'buyer':
                success_msg = MessageTemplates.buyer_success(
                    user.first_name or f"User_{user_id}",
                    address,
                    chain_name,
                    chain_code
                )
            else:
                success_msg = MessageTemplates.seller_success(
                    user.first_name or f"User_{user_id}",
                    address,
                    chain_name,
                    chain_code
                )
            
            # Create view button
            buttons = [[Button.url("🔎 View Wallet", explorer_url)]]
            
            await processing_msg.edit(success_msg, buttons=buttons, parse_mode='html')
            
            # Send notification to group
            await self.send_group_notification(chat, role, address_data)
            
            logger.info(f"[ ✅ ] {role.upper()} address saved for user {user_id} on {chain_code}")
            
            # Check chain match
            await self.check_chain_match(chat)
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error in handle_address_command: {e}", exc_info=True)
            try:
                await event.reply("<b>❌ An error occurred. Please try again.</b>", parse_mode='html')
            except:
                pass
    
    async def handle_change_wallet(self, event, role: str):
        """Handle change wallet callback"""
        try:
            user = await event.get_sender()
            chat = await event.get_chat()
            group_id = normalize_group_id(chat.id)
            
            # Extract address from callback data
            data = event.data.decode('utf-8')
            address = data.replace(f'change_{role}_', '')
            
            # Check permissions
            user_role = RoleManager.get_user_role(user.id, group_id)
            is_creator = RoleManager.is_group_creator(user.id, group_id)
            
            if user_role != role and not is_creator:
                await event.answer("❌ You don't have permission to change this wallet", alert=True)
                return
            
            # Show processing
            await event.answer("Processing...", alert=False)
            
            # Validate address
            is_valid, chain_code, chain_name, explorer_url = await self.validator.verify_address(address)
            
            if not is_valid:
                await event.answer("❌ Invalid address format!", alert=True)
                return
            
            # Update address
            addresses = load_json(USER_ADDRESSES_FILE, {})
            if group_id not in addresses:
                addresses[group_id] = {}
            
            address_data = {
                'user_id': user.id,
                'user_name': user.first_name or f"User_{user.id}",
                'address': address,
                'chain': chain_code,
                'chain_name': chain_name,
                'timestamp': time.time(),
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated': True
            }
            
            addresses[group_id][role] = address_data
            save_json(USER_ADDRESSES_FILE, addresses)
            
            # Update wallets.json
            wallets = load_json(WALLETS_FILE, {})
            if group_id not in wallets:
                wallets[group_id] = {}
            
            if role == 'buyer':
                wallets[group_id]['buyer_wallet'] = address
                wallets[group_id]['buyer_id'] = user.id
            else:
                wallets[group_id]['seller_wallet'] = address
                wallets[group_id]['seller_id'] = user.id
            
            save_json(WALLETS_FILE, wallets)
            
            # Send confirmation
            if role == 'buyer':
                msg = MessageTemplates.buyer_success(
                    user.first_name or f"User_{user.id}",
                    address,
                    chain_name,
                    chain_code
                )
            else:
                msg = MessageTemplates.seller_success(
                    user.first_name or f"User_{user.id}",
                    address,
                    chain_name,
                    chain_code
                )
            
            buttons = [[Button.url("🔎 View Wallet", explorer_url)]]
            
            await event.edit(msg, buttons=buttons, parse_mode='html')
            
            logger.info(f"[ 🔄 ] {role.upper()} wallet changed for user {user.id}")
            
            # Check chain match
            await self.check_chain_match(chat)
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error in change wallet: {e}", exc_info=True)
            await event.answer("❌ Error updating wallet", alert=True)
    
    async def send_group_notification(self, chat, role: str, address_data: Dict):
        """Send notification to group"""
        try:
            message = f"""<b>📢 NEW {role.upper()} REGISTERED!</b>

<b>User:</b> {address_data['user_name']}
<b>Chain:</b> {address_data['chain_name']}
<b>Address:</b> <code>{address_data['address'][:12]}...{address_data['address'][-6:]}</code>

✅ Address verified and saved!"""
            
            await self.client.send_message(chat.id, message, parse_mode='html')
            
            logger.info(f"[ 📢 ] Group notification sent for {role}")
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error sending group notification: {e}")
    
    async def show_addresses(self, event):
        """Show all addresses in the current chat with change buttons"""
        try:
            chat = await event.get_chat()
            group_id = normalize_group_id(chat.id)
            user = await event.get_sender()
            
            addresses = load_json(USER_ADDRESSES_FILE, {})
            chat_addresses = addresses.get(group_id, {})
            
            if not chat_addresses:
                await event.reply("<b>📭 No addresses saved in this group yet.</b>", parse_mode='html')
                return
            
            # Get buyer and seller data
            buyer_data = chat_addresses.get('buyer', {})
            seller_data = chat_addresses.get('seller', {})
            
            # Create summary message
            summary = MessageTemplates.address_summary(chat.title, buyer_data, seller_data)
            
            # Create change buttons
            buttons = []
            
            user_role = RoleManager.get_user_role(user.id, group_id)
            is_creator = RoleManager.is_group_creator(user.id, group_id)
            
            if buyer_data and (user_role == 'buyer' or is_creator):
                buttons.append([Button.inline(
                    "🔄 Change Buyer Wallet", 
                    data=f"change_buyer_{buyer_data['address']}"
                )])
            
            if seller_data and (user_role == 'seller' or is_creator):
                buttons.append([Button.inline(
                    "🔄 Change Seller Wallet", 
                    data=f"change_seller_{seller_data['address']}"
                )])
            
            await event.reply(summary, buttons=buttons if buttons else None, parse_mode='html')
            
            logger.info(f"[ 📋 ] Address summary shown in {chat.title}")
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error showing addresses: {e}")
            await event.reply("<b>❌ Error loading addresses.</b>", parse_mode='html')
    
    async def check_chain_match(self, chat):
        """Check if both chains match and send appropriate message"""
        try:
            group_id = normalize_group_id(chat.id)
            addresses = load_json(USER_ADDRESSES_FILE, {})
            chat_addresses = addresses.get(group_id, {})
            
            # Check if both addresses exist
            if 'buyer' not in chat_addresses or 'seller' not in chat_addresses:
                return
            
            buyer = chat_addresses['buyer']
            seller = chat_addresses['seller']
            
            logger.info(f"[ 🔍 ] Checking chain match: buyer={buyer['chain']}, seller={seller['chain']}")
            
            if buyer['chain'] != seller['chain']:
                # Chain mismatch
                await self.client.send_message(
                    chat.id,
                    MessageTemplates.chain_mismatch(buyer['chain_name'], seller['chain_name']),
                    parse_mode='html'
                )
                logger.warning(f"[ ⚠️ ] Chain mismatch in {chat.title}")
            else:
                # Chains match - escrow ready
                await self.client.send_message(
                    chat.id,
                    MessageTemplates.escrow_ready(buyer['chain_name']),
                    parse_mode='html'
                )
                logger.info(f"[ 🎉 ] Escrow ready in {chat.title}")
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error checking chain match: {e}")

# ==================== MAIN EXPORT FUNCTION ====================
def setup_address_handlers(client):
    """
    Main function to setup address handlers
    This is what main.py imports and calls
    """
    try:
        # Create handler instance
        handler = AddressHandler(client)
        
        # Setup the handlers
        handler.setup_handlers()
        
        logger.info("[ ✅ ] " + "="*50)
        logger.info("[ ✅ ] Address handlers setup complete!")
        logger.info("[ ✅ ] Commands: /buyer, /seller, /addresses, /verify")
        logger.info("[ ✅ ] " + "="*50)
        
        return handler
        
    except Exception as e:
        logger.error(f"[ ❌ ] Failed to setup address handlers: {e}")
        raise

# For testing
if __name__ == "__main__":
    print("""
    📝 Address Handlers Module for OneEscrow Bot
    ==============================================
    
    This module exports:
    • setup_address_handlers(client) - Main function to setup handlers
    
    Commands added:
    • /buyer [address] - For buyers to set their wallet
    • /seller [address] - For sellers to set their wallet
    • /addresses - Show all addresses with change buttons
    • /verify [address] - Verify any wallet address
    
    Features:
    • HTML parse_mode for all messages
    • Blockchain address validation with explorer links
    • Role-based access control
    • Chain matching enforcement
    • Change wallet functionality for owners/creators
    • Consistent group ID handling (str(chat.id))
    """)
