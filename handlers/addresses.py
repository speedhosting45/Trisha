# handlers/addresses.py
"""
Address handlers for OneEscrow Bot
Upgraded version with real blockchain data fetching
"""

import re
import json
import os
import logging
import time
import aiohttp
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
PENDING_CHANGES_FILE = os.path.join(BASE_DIR, 'data/pending_changes.json')

# API Keys (you should move these to config.py)
BSCSCAN_API_KEY = "YOUR_BSCSCAN_API_KEY"  # Get from https://bscscan.com/myapikey
ETHERSCAN_API_KEY = "YOUR_ETHERSCAN_API_KEY"  # Get from https://etherscan.io/myapikey
POLYGONSCAN_API_KEY = "YOUR_POLYGONSCAN_API_KEY"  # Get from https://polygonscan.com/myapikey

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

# ==================== BLOCKCHAIN DATA FETCHER ====================
class BlockchainDataFetcher:
    """Fetch real blockchain data from various explorers"""
    
    @staticmethod
    async def fetch_bsc_data(address: str) -> Dict:
        """Fetch BSC address data from BSCScan"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get BNB balance
                balance_url = f"https://api.bscscan.com/api?module=account&action=balance&address={address}&apikey={BSCSCAN_API_KEY}"
                async with session.get(balance_url) as response:
                    balance_data = await response.json()
                
                # Get last transaction
                tx_url = f"https://api.bscscan.com/api?module=account&action=txlist&address={address}&sort=desc&offset=1&apikey={BSCSCAN_API_KEY}"
                async with session.get(tx_url) as response:
                    tx_data = await response.json()
                
                # Parse balance
                balance = "0"
                if balance_data.get('status') == '1':
                    balance_wei = int(balance_data.get('result', 0))
                    balance = f"{balance_wei / 1e18:.6f} BNB"
                
                # Parse last transaction
                last_txn = "Unavailable"
                if tx_data.get('status') == '1' and tx_data.get('result'):
                    latest_tx = tx_data['result'][0]
                    timestamp = int(latest_tx.get('timeStamp', 0))
                    tx_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    last_txn = tx_time
                
                return {
                    'balance': balance,
                    'last_txn': last_txn,
                    'explorer': f"https://bscscan.com/address/{address}"
                }
        except Exception as e:
            logger.error(f"Error fetching BSC data: {e}")
            return {
                'balance': 'Unavailable',
                'last_txn': 'Unavailable',
                'explorer': f"https://bscscan.com/address/{address}"
            }
    
    @staticmethod
    async def fetch_eth_data(address: str) -> Dict:
        """Fetch Ethereum address data from EtherScan"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get ETH balance
                balance_url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&apikey={ETHERSCAN_API_KEY}"
                async with session.get(balance_url) as response:
                    balance_data = await response.json()
                
                # Get last transaction
                tx_url = f"https://api.etherscan.io/api?module=account&action=txlist&address={address}&sort=desc&offset=1&apikey={ETHERSCAN_API_KEY}"
                async with session.get(tx_url) as response:
                    tx_data = await response.json()
                
                # Parse balance
                balance = "0"
                if balance_data.get('status') == '1':
                    balance_wei = int(balance_data.get('result', 0))
                    balance = f"{balance_wei / 1e18:.6f} ETH"
                
                # Parse last transaction
                last_txn = "Unavailable"
                if tx_data.get('status') == '1' and tx_data.get('result'):
                    latest_tx = tx_data['result'][0]
                    timestamp = int(latest_tx.get('timeStamp', 0))
                    tx_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    last_txn = tx_time
                
                return {
                    'balance': balance,
                    'last_txn': last_txn,
                    'explorer': f"https://etherscan.io/address/{address}"
                }
        except Exception as e:
            logger.error(f"Error fetching ETH data: {e}")
            return {
                'balance': 'Unavailable',
                'last_txn': 'Unavailable',
                'explorer': f"https://etherscan.io/address/{address}"
            }
    
    @staticmethod
    async def fetch_matic_data(address: str) -> Dict:
        """Fetch Polygon address data from PolygonScan"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get MATIC balance
                balance_url = f"https://api.polygonscan.com/api?module=account&action=balance&address={address}&apikey={POLYGONSCAN_API_KEY}"
                async with session.get(balance_url) as response:
                    balance_data = await response.json()
                
                # Get last transaction
                tx_url = f"https://api.polygonscan.com/api?module=account&action=txlist&address={address}&sort=desc&offset=1&apikey={POLYGONSCAN_API_KEY}"
                async with session.get(tx_url) as response:
                    tx_data = await response.json()
                
                # Parse balance
                balance = "0"
                if balance_data.get('status') == '1':
                    balance_wei = int(balance_data.get('result', 0))
                    balance = f"{balance_wei / 1e18:.6f} MATIC"
                
                # Parse last transaction
                last_txn = "Unavailable"
                if tx_data.get('status') == '1' and tx_data.get('result'):
                    latest_tx = tx_data['result'][0]
                    timestamp = int(latest_tx.get('timeStamp', 0))
                    tx_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    last_txn = tx_time
                
                return {
                    'balance': balance,
                    'last_txn': last_txn,
                    'explorer': f"https://polygonscan.com/address/{address}"
                }
        except Exception as e:
            logger.error(f"Error fetching MATIC data: {e}")
            return {
                'balance': 'Unavailable',
                'last_txn': 'Unavailable',
                'explorer': f"https://polygonscan.com/address/{address}"
            }
    
    @staticmethod
    async def fetch_trx_data(address: str) -> Dict:
        """Fetch Tron address data from Tronscan"""
        try:
            async with aiohttp.ClientSession() as session:
                # Get TRX balance and last transaction
                url = f"https://apilist.tronscan.org/api/account?address={address}"
                async with session.get(url) as response:
                    data = await response.json()
                
                # Parse balance
                balance = "0"
                if data.get('balance'):
                    balance_trx = int(data.get('balance', 0)) / 1e6
                    balance = f"{balance_trx:.6f} TRX"
                
                # Get last transaction
                last_txn = "Unavailable"
                if data.get('transactions'):
                    latest_tx = data['transactions'][0]
                    timestamp = latest_tx.get('timestamp', 0) / 1000
                    tx_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    last_txn = tx_time
                
                return {
                    'balance': balance,
                    'last_txn': last_txn,
                    'explorer': f"https://tronscan.org/#/address/{address}"
                }
        except Exception as e:
            logger.error(f"Error fetching TRX data: {e}")
            return {
                'balance': 'Unavailable',
                'last_txn': 'Unavailable',
                'explorer': f"https://tronscan.org/#/address/{address}"
            }
    
    @staticmethod
    async def fetch_btc_data(address: str) -> Dict:
        """Fetch Bitcoin address data from Blockchain.com"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://blockchain.info/rawaddr/{address}"
                async with session.get(url) as response:
                    data = await response.json()
                
                # Parse balance
                balance_btc = data.get('final_balance', 0) / 1e8
                balance = f"{balance_btc:.8f} BTC"
                
                # Get last transaction
                last_txn = "Unavailable"
                if data.get('txs') and len(data['txs']) > 0:
                    latest_tx = data['txs'][0]
                    timestamp = latest_tx.get('time', 0)
                    tx_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    last_txn = tx_time
                
                return {
                    'balance': balance,
                    'last_txn': last_txn,
                    'explorer': f"https://blockchain.com/explorer/addresses/btc/{address}"
                }
        except Exception as e:
            logger.error(f"Error fetching BTC data: {e}")
            return {
                'balance': 'Unavailable',
                'last_txn': 'Unavailable',
                'explorer': f"https://blockchain.com/explorer/addresses/btc/{address}"
            }

# ==================== BLOCKCHAIN VALIDATOR ====================
class BlockchainValidator:
    """Blockchain address validator with explorer URLs and real data"""
    
    # BSC (BEP20) specific patterns - addresses starting with specific prefixes commonly used in BSC
    BSC_PREFIXES = ['0x', 'bnb', 'bsc']
    
    CHAINS = {
        'BTC': {
            'name': 'Bitcoin',
            'regex': r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59}$',
            'explorer': 'https://blockchain.com/explorer/addresses/btc/{address}',
            'color': '\x1b[38;5;226m',  # Yellow
            'fetcher': BlockchainDataFetcher.fetch_btc_data
        },
        'ETH': {
            'name': 'Ethereum',
            'regex': r'^0x[a-fA-F0-9]{40}$',
            'explorer': 'https://etherscan.io/address/{address}',
            'color': '\x1b[38;5;105m',  # Light blue
            'fetcher': BlockchainDataFetcher.fetch_eth_data
        },
        'BSC': {
            'name': 'BNB Smart Chain (BEP20)',
            'regex': r'^0x[a-fA-F0-9]{40}$',  # Same regex as ETH
            'explorer': 'https://bscscan.com/address/{address}',
            'color': '\x1b[38;5;220m',  # Gold
            'fetcher': BlockchainDataFetcher.fetch_bsc_data
        },
        'TRX': {
            'name': 'Tron',
            'regex': r'^T[a-zA-Z0-9]{33}$',
            'explorer': 'https://tronscan.org/#/address/{address}',
            'color': '\x1b[38;5;197m',  # Red
            'fetcher': BlockchainDataFetcher.fetch_trx_data
        },
        'LTC': {
            'name': 'Litecoin',
            'regex': r'^(ltc1|[LM])[a-zA-HJ-NP-Z0-9]{26,33}$',
            'explorer': 'https://blockchair.com/litecoin/address/{address}',
            'color': '\x1b[38;5;39m',  # Blue
            'fetcher': None  # Add LTC fetcher if needed
        },
        'MATIC': {
            'name': 'Polygon',
            'regex': r'^0x[a-fA-F0-9]{40}$',
            'explorer': 'https://polygonscan.com/address/{address}',
            'color': '\x1b[38;5;129m',  # Purple
            'fetcher': BlockchainDataFetcher.fetch_matic_data
        },
        'SOL': {
            'name': 'Solana',
            'regex': r'^[1-9A-HJ-NP-Za-km-z]{32,44}$',
            'explorer': 'https://solscan.io/account/{address}',
            'color': '\x1b[38;5;141m',  # Purple
            'fetcher': None  # Add SOL fetcher if needed
        },
        'ADA': {
            'name': 'Cardano',
            'regex': r'^addr1[a-zA-Z0-9]{50,}$',
            'explorer': 'https://cardanoscan.io/address/{address}',
            'color': '\x1b[38;5;33m',  # Blue
            'fetcher': None  # Add ADA fetcher if needed
        }
    }
    
    @staticmethod
    def detect_chain(address: str, user_hint: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Detect blockchain from address
        If address matches multiple chains (like ETH and BSC), use user hint if available
        """
        address = address.strip()
        possible_chains = []
        
        for chain_code, config in BlockchainValidator.CHAINS.items():
            if re.match(config['regex'], address):
                possible_chains.append((chain_code, config['name']))
        
        if not possible_chains:
            return None, None
        
        # If only one possible chain, return it
        if len(possible_chains) == 1:
            return possible_chains[0]
        
        # If multiple possible chains (ETH, BSC, MATIC all use 0x format)
        # Use user hint if provided
        if user_hint:
            hint_lower = user_hint.lower()
            for chain_code, chain_name in possible_chains:
                if hint_lower in chain_code.lower() or hint_lower in chain_name.lower():
                    return chain_code, chain_name
        
        # Default to BSC for 0x addresses (most common for USDT BEP20)
        for chain_code, chain_name in possible_chains:
            if chain_code == 'BSC' and address.startswith('0x'):
                return 'BSC', 'BNB Smart Chain (BEP20)'
        
        # Default to Ethereum if no BSC match
        return 'ETH', 'Ethereum'
    
    @staticmethod
    async def verify_address(address: str, user_hint: str = None) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Dict]:
        """
        Verify address and return (is_valid, chain_code, chain_name, explorer_url, blockchain_data)
        """
        chain_code, chain_name = BlockchainValidator.detect_chain(address, user_hint)
        
        if not chain_code:
            return False, None, None, None, {}
        
        # Get explorer URL
        explorer_url = BlockchainValidator.CHAINS[chain_code]['explorer'].format(address=address)
        
        # Fetch blockchain data if fetcher exists
        blockchain_data = {
            'balance': 'Unavailable',
            'last_txn': 'Unavailable'
        }
        
        fetcher = BlockchainValidator.CHAINS[chain_code].get('fetcher')
        if fetcher:
            try:
                blockchain_data = await fetcher(address)
            except Exception as e:
                logger.error(f"Error fetching blockchain data for {chain_code}: {e}")
        
        return True, chain_code, chain_name, explorer_url, blockchain_data

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
• <b>BNB Chain (BSC/BEP20):</b> <code>0x...</code>
• <b>Tron (TRX):</b> <code>T...</code>
• <b>Litecoin (LTC):</b> <code>L...</code> or <code>ltc1q...</code>
• <b>Polygon (MATIC):</b> <code>0x...</code>
• <b>Solana (SOL):</b> <code>base58 string</code>

💡 <b>Tip:</b> For BSC addresses, you can specify: <code>/seller bsc 0x...</code>"""
    
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
    def buyer_success(user_name: str, address: str, chain_name: str, chain_code: str, balance: str, last_txn: str):
        return f"""<b>✅ BUYER ADDRESS SAVED SUCCESSFULLY!</b>

<b>Buyer Wallet Stats</b>
<u>Address :</u>

<blockquote>
Balance : {balance}
Last Txn : {last_txn}
Chain : {chain_name}
Network : {chain_code}
</blockquote>

This wallet has been saved for this deal."""
    
    @staticmethod
    def seller_success(user_name: str, address: str, chain_name: str, chain_code: str, balance: str, last_txn: str):
        return f"""<b>✅ SELLER ADDRESS SAVED SUCCESSFULLY!</b>

<b>Seller Wallet Stats</b>
<u>Address :</u>

<blockquote>
Balance : {balance}
Last Txn : {last_txn}
Chain : {chain_name}
Network : {chain_code}
</blockquote>

This wallet has been saved for this deal."""
    
    @staticmethod
    def verify_success(address: str, chain_name: str, chain_code: str, balance: str, last_txn: str):
        return f"""<b>🔍 WALLET VERIFICATION</b>

<blockquote>
Chain : {chain_name}
Network : {chain_code}
Valid : Yes
Balance : {balance}
Last Txn : {last_txn}
</blockquote>"""
    
    @staticmethod
    def address_summary(chat_title: str, buyer_data: Dict, seller_data: Dict):
        buyer_address = buyer_data.get('address', 'Not Set') if buyer_data else 'Not Set'
        buyer_chain = buyer_data.get('chain_name', '—') if buyer_data else '—'
        buyer_network = buyer_data.get('chain', '—') if buyer_data else '—'
        buyer_balance = buyer_data.get('balance', '—') if buyer_data else '—'
        
        seller_address = seller_data.get('address', 'Not Set') if seller_data else 'Not Set'
        seller_chain = seller_data.get('chain_name', '—') if seller_data else '—'
        seller_network = seller_data.get('chain', '—') if seller_data else '—'
        seller_balance = seller_data.get('balance', '—') if seller_data else '—'
        
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
Balance : {buyer_balance}

<b>SELLER :</b>
Address : {seller_address}
Chain : {seller_chain}
Network : {seller_network}
Balance : {seller_balance}"""
    
    @staticmethod
    def chain_mismatch(buyer_chain: str, seller_chain: str):
        return f"""<b>❌ CHAIN MISMATCH DETECTED</b>

Buyer Chain : {buyer_chain}
Seller Chain : {seller_chain}

<b>Both parties must use the same blockchain.</b>"""
    
    @staticmethod
    def escrow_ready(buyer_chain: str, buyer_balance: str, seller_balance: str):
        return f"""<b>🎉 ESCROW READY</b>

Both wallets verified
Same blockchain detected
Escrow ready for deposit

<b>Buyer Balance:</b> {buyer_balance}
<b>Seller Balance:</b> {seller_balance}"""
    
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
        return f"<b>Usage:</b> <code>/{role} [your_wallet_address]</code>\n\n<b>For BSC:</b> <code>/{role} bsc 0x...</code>"
    
    @staticmethod
    def missing_address_verify():
        return "<b>Usage:</b> <code>/verify [wallet_address]</code>"
    
    @staticmethod
    def change_wallet_prompt(role: str, user_mention: str):
        """Prompt user to send new wallet address"""
        return f"""{user_mention} <b>please send your new {role.upper()} wallet address.</b>

<b>Format:</b> <code>/{role} [address]</code>
<b>Example:</b> <code>/{role} 0x1234567890abcdef...</code>

💡 <b>For BSC addresses:</b> <code>/{role} bsc 0x...</code>

You have 5 minutes to respond."""
    
    @staticmethod
    def change_timeout(role: str):
        return f"<b>⏰ Timeout!</b> {role.upper()} wallet change request expired. Please try again."

# ==================== PENDING CHANGE MANAGER ====================
class PendingChangeManager:
    """Manage pending wallet change requests"""
    
    @staticmethod
    def create_request(user_id: int, group_id: str, role: str, message_id: int):
        """Create a pending change request"""
        pending = load_json(PENDING_CHANGES_FILE, {})
        
        key = f"{group_id}:{user_id}:{role}"
        pending[key] = {
            'user_id': user_id,
            'group_id': group_id,
            'role': role,
            'message_id': message_id,
            'timestamp': time.time(),
            'expires': time.time() + 300  # 5 minutes
        }
        
        save_json(PENDING_CHANGES_FILE, pending)
        return key
    
    @staticmethod
    def get_request(user_id: int, group_id: str, role: str):
        """Get pending change request"""
        pending = load_json(PENDING_CHANGES_FILE, {})
        key = f"{group_id}:{user_id}:{role}"
        
        request = pending.get(key)
        if request and request.get('expires', 0) > time.time():
            return request
        
        if key in pending:
            del pending[key]
            save_json(PENDING_CHANGES_FILE, pending)
        
        return None
    
    @staticmethod
    def remove_request(user_id: int, group_id: str, role: str):
        """Remove pending change request"""
        pending = load_json(PENDING_CHANGES_FILE, {})
        key = f"{group_id}:{user_id}:{role}"
        
        if key in pending:
            del pending[key]
            save_json(PENDING_CHANGES_FILE, pending)
            return True
        return False

# ==================== ADDRESS HANDLER ====================
class AddressHandler:
    """Main address handler for buyer/seller commands"""
    
    def __init__(self, client):
        self.client = client
        self.validator = BlockchainValidator()
        self.pending_manager = PendingChangeManager()
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
            await self.handle_change_wallet_callback(event, 'buyer')
        
        @self.client.on(events.CallbackQuery(pattern=r'change_seller_(.+)'))
        async def change_seller_callback(event):
            await self.handle_change_wallet_callback(event, 'seller')
        
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
            parts = event.text.split()
            if len(parts) < 2:
                await event.reply(MessageTemplates.missing_address_verify(), parse_mode='html')
                return
            
            # Check if user specified a chain hint
            user_hint = None
            address = parts[1]
            
            if len(parts) >= 3 and parts[1].lower() in ['bsc', 'eth', 'matic', 'polygon']:
                user_hint = parts[1].lower()
                address = parts[2]
            
            # Show processing
            processing_msg = await event.reply(MessageTemplates.processing(), parse_mode='html')
            
            # Validate address with hint and get blockchain data
            is_valid, chain_code, chain_name, explorer_url, blockchain_data = await self.validator.verify_address(address, user_hint)
            
            if not is_valid:
                await processing_msg.edit(MessageTemplates.invalid_format(), parse_mode='html')
                return
            
            # Create success message with real data
            success_msg = MessageTemplates.verify_success(
                address, 
                chain_name, 
                chain_code,
                blockchain_data.get('balance', 'Unavailable'),
                blockchain_data.get('last_txn', 'Unavailable')
            )
            
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
            parts = event.text.split()
            if len(parts) < 2:
                await event.reply(MessageTemplates.missing_address(role), parse_mode='html')
                return
            
            # Check if user specified a chain hint
            user_hint = None
            address = parts[1]
            
            if len(parts) >= 3 and parts[1].lower() in ['bsc', 'eth', 'matic', 'polygon']:
                user_hint = parts[1].lower()
                address = parts[2]
            
            # Show processing
            processing_msg = await event.reply(MessageTemplates.processing(), parse_mode='html')
            
            # Validate address with hint and get blockchain data
            is_valid, chain_code, chain_name, explorer_url, blockchain_data = await self.validator.verify_address(address, user_hint)
            
            if not is_valid:
                await processing_msg.edit(MessageTemplates.invalid_format(), parse_mode='html')
                return
            
            # Check if this is a pending change request
            pending = self.pending_manager.get_request(user_id, group_id, role)
            is_change = pending is not None
            
            # Load addresses
            addresses = load_json(USER_ADDRESSES_FILE, {})
            
            # Prepare address data with blockchain info
            address_data = {
                'user_id': user_id,
                'user_name': user.first_name or f"User_{user_id}",
                'address': address,
                'chain': chain_code,
                'chain_name': chain_name,
                'balance': blockchain_data.get('balance', 'Unavailable'),
                'last_txn': blockchain_data.get('last_txn', 'Unavailable'),
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
            
            # Remove pending change if this was a change
            if is_change:
                self.pending_manager.remove_request(user_id, group_id, role)
                # Delete the prompt message
                try:
                    await self.client.delete_messages(chat.id, pending['message_id'])
                except:
                    pass
            
            # Send success message with appropriate template and real data
            if role == 'buyer':
                success_msg = MessageTemplates.buyer_success(
                    user.first_name or f"User_{user_id}",
                    address,
                    chain_name,
                    chain_code,
                    blockchain_data.get('balance', 'Unavailable'),
                    blockchain_data.get('last_txn', 'Unavailable')
                )
            else:
                success_msg = MessageTemplates.seller_success(
                    user.first_name or f"User_{user_id}",
                    address,
                    chain_name,
                    chain_code,
                    blockchain_data.get('balance', 'Unavailable'),
                    blockchain_data.get('last_txn', 'Unavailable')
                )
            
            # Create view button
            buttons = [[Button.url("🔎 View Wallet", explorer_url)]]
            
            await processing_msg.edit(success_msg, buttons=buttons, parse_mode='html')
            
            # Send notification to group (only if not a change)
            if not is_change:
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
    
    async def handle_change_wallet_callback(self, event, role: str):
        """Handle change wallet callback - prompts user to send new address"""
        try:
            user = await event.get_sender()
            chat = await event.get_chat()
            group_id = normalize_group_id(chat.id)
            
            # Check permissions
            user_role = RoleManager.get_user_role(user.id, group_id)
            is_creator = RoleManager.is_group_creator(user.id, group_id)
            
            if user_role != role and not is_creator:
                await event.answer("❌ You don't have permission to change this wallet", alert=True)
                return
            
            # Create user mention
            user_mention = f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"
            
            # Send prompt message
            prompt_msg = await event.reply(
                MessageTemplates.change_wallet_prompt(role, user_mention),
                parse_mode='html'
            )
            
            # Create pending change request
            self.pending_manager.create_request(user.id, group_id, role, prompt_msg.id)
            
            # Answer callback
            await event.answer(f"📝 Please send your new {role} address", alert=False)
            
            # Delete the original message with buttons
            try:
                await event.delete()
            except:
                pass
            
            logger.info(f"[ 🔄 ] {role.upper()} change requested by user {user.id}")
            
        except Exception as e:
            logger.error(f"[ ❌ ] Error in change wallet callback: {e}", exc_info=True)
            await event.answer("❌ Error processing request", alert=True)
    
    async def send_group_notification(self, chat, role: str, address_data: Dict):
        """Send notification to group"""
        try:
            message = f"""<b>📢 NEW {role.upper()} REGISTERED!</b>

<b>User:</b> {address_data['user_name']}
<b>Chain:</b> {address_data['chain_name']}
<b>Address:</b> <code>{address_data['address'][:12]}...{address_data['address'][-6:]}</code>
<b>Balance:</b> {address_data.get('balance', 'Unavailable')}

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
                    MessageTemplates.escrow_ready(
                        buyer['chain_name'],
                        buyer.get('balance', 'Unavailable'),
                        seller.get('balance', 'Unavailable')
                    ),
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
    • Real blockchain data (balance, last transaction)
    • Blockchain address validation with explorer links
    • BSC (BEP20) support with chain hints
    • Role-based access control
    • Chain matching enforcement
    • Change wallet functionality with @mention prompt
    • Consistent group ID handling (str(chat.id))
    """)
