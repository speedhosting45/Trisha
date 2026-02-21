# Text messages for the bot

START_MESSAGE = """
𝘞𝘦𝘭𝘤𝘰𝘮𝘦 𝘵𝘰 𝘚𝘦𝘤𝘶𝘳𝘦 𝘌𝘴𝘤𝘳𝘰𝘸

A trusted escrow solution for secure, high-value P2P transactions.

<blockquote>Enterprise-grade security • Transparent process • Neutral third-party</blockquote>

Initiate or manage secure escrow agreements through the menu below.
"""
# Add this line to your texts.py file
JOIN_MESSAGE = "👋 Welcome {user_mention}! You've joined an escrow group. Wait for the session to begin."

CREATE_MESSAGE = """
𝘊𝘳𝘦𝘢𝘵𝘦 𝘕𝘦𝘸 𝘌𝘴𝘤𝘳𝘰𝘸

<blockquote>Select transaction type to proceed</blockquote>

• <b>P2P Deal</b> – Standard buyer/seller transactions
• <b>Other Deal</b> – Custom or multi-party agreements

All escrows operate within private, bot-moderated groups.
"""
# Address Handler Messages - Professional Style

BUYER_ADDRESS_PROMPT = """
<b>Settlement Address: Buyer</b>

Please submit the wallet address for settlement.

<b>Command:</b>
<code>/buyer wallet_address</code>

<blockquote><b>Example:</b>
<code>/buyer 0x742d35Cc6634C0532925a3b844Bc9e0E0F14eC73</code></blockquote>
"""

SELLER_ADDRESS_PROMPT = """
<b>Settlement Address: Seller</b>

Please submit the wallet address for settlement.

<b>Command:</b>
<code>/seller wallet_address</code>

<blockquote><b>Example:</b>
<code>/seller TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm</code></blockquote>
"""

ADDRESS_SAVED = """
<b>Configuration Updated</b>

The settlement address has been successfully recorded.

<b>Details:</b>
• Role: {role}
• Network: {chain}
• User: {user_mention}

<code>{address}</code>
"""

ADDRESSES_VIEW = """
<b>Transaction Configuration</b>

<b>Buyer (Purchaser)</b>
User: {buyer_mention}
Network: {buyer_chain}
<code>{buyer_address}</code>

<b>Seller (Provider)</b>
User: {seller_mention}
Network: {seller_chain}
<code>{seller_address}</code>

<blockquote><b>Session ID:</b> {group_name}</blockquote>
"""

INVALID_ADDRESS = """
<b>Validation Error</b>

The address provided does not match the required format.
<code>{address}</code>

<blockquote><b>Required Formats:</b>
• <b>ERC20/BEP20:</b> 42 hexadecimal characters (0x...)
• <b>TRC20:</b> 34 characters starting with 'T'
• <b>BTC:</b> Legacy (1...), SegWit (3...), or Native (bc1...)</blockquote>
"""

NO_ROLE = """
<b>Access Denied</b>

You do not have an active role in this transaction protocol.

<blockquote><b>Action Required:</b>
Please execute <code>/begin</code> to initialize your participant status.</blockquote>
"""

ADDRESS_ALREADY_SET = """
<b>Configuration Locked</b>

A settlement address is already registered for this role.

<b>Current Entry:</b>
<code>{address}</code>

<blockquote>To modify this, please contact support or reset the session.</blockquote>
"""

NO_ADDRESSES_SET = """
<b>Pending Configuration</b>

Settlement addresses have not been established.

<b>Status:</b>
• Buyer: <b>Pending</b>
• Seller: <b>Pending</b>

<blockquote><b>Instructions:</b>
Use <code>/buyer address</code> or <code>/seller address</code> to proceed.</blockquote>
"""

ADDRESS_VERIFICATION_FAILED = """
<b>Network Mismatch</b>

Verification failed for <b>{chain}</b> network.

<code>{address}</code>

<blockquote>Please ensure the address matches the specific blockchain network selected for this transaction.</blockquote>
"""
P2P_CREATED_MESSAGE = """
𝘗2𝘗 𝘌𝘴𝘤𝘳𝘰𝘸 𝘌𝘴𝘵𝘢𝘣𝘭𝘪𝘴𝘩𝘦𝘥 

<blockquote>Secure transaction group created </blockquote>

<b>Group:</b> {GROUP_NAME} 
<b>Type:</b> P2P Transaction 
<b>Status:</b> Ready for configuration 

<code>{GROUP_INVITE_LINK}</code>

Proceed to the group to configure participants and terms <a href="https://files.catbox.moe/ieiejo.png">.</a>
"""

OTHER_CREATED_MESSAGE = """
𝘊𝘶𝘴𝘵𝘰𝘮 𝘌𝘴𝘤𝘳𝘰𝘸 𝘌𝘴𝘵𝘢𝘣𝘭𝘪𝘴𝘩𝘦𝘥

<blockquote>Multi-party agreement group created</blockquote>

<b>Group:</b> {GROUP_NAME}
<b>Type:</b> Custom Agreement
<b>Status:</b> Ready for configuration

<code>{GROUP_INVITE_LINK}</code>

Proceed to the group to define participants and contract terms <a href="https://files.catbox.moe/f6lzpr.png">.</a>
"""

INSUFFICIENT_MEMBERS_MESSAGE = """
𝘗𝘢𝘳𝘵𝘪𝘤𝘪𝘱𝘢𝘯𝘵 𝘙𝘦𝘲𝘶𝘪𝘳𝘦𝘮𝘦𝘯𝘵

<blockquote>Minimum 2 participants required to commence (Current: {current_count}/2)</blockquote>
"""

WAITING_PARTICIPANTS_MESSAGE = """
𝘗𝘢𝘳𝘵𝘪𝘤𝘪𝘱𝘢𝘯𝘵 𝘈𝘸𝘢𝘪𝘵𝘦𝘥

<blockquote>Awaiting counterparty arrival to initiate configuration.</blockquote>
"""

SESSION_ALREADY_INITIATED_MESSAGE = """
𝘗𝘳𝘰𝘵𝘰𝘤𝘰𝘭 𝘈𝘭𝘳𝘦𝘢𝘥𝘺 𝘈𝘤𝘵𝘪𝘷𝘦

<blockquote>Transaction configuration already in progress.</blockquote>
"""

GROUP_NOT_FOUND_MESSAGE = """
𝘌𝘯𝘷𝘪𝘳𝘰𝘯𝘮𝘦𝘯𝘵 𝘜𝘯𝘢𝘷𝘢𝘪𝘭𝘢𝘣𝘭𝘦

<blockquote>Transaction group not found in system registry.</blockquote>
"""

ERROR_MESSAGE = """
𝘚𝘺𝘴𝘵𝘦𝘮 𝘌𝘳𝘳𝘰𝘳

<blockquote>An operational exception occurred. Please retry.</blockquote>
"""

CHANNEL_LOG_CREATION = """
𝘗𝘳𝘰𝘵𝘰𝘤𝘰𝘭 𝘐𝘯𝘪𝘵𝘪𝘢𝘵𝘪𝘰𝘯

<code>\u250c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500</code>
<b>ID:</b> {group_name}
<b>Type:</b> {escrow_type}
<b>Time:</b> {timestamp}
<code>\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500</code>
<b>Initiator:</b> {creator_name}
<b>TG ID:</b> <code>{creator_id}</code>
<code>\u251c\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500</code>
<b>Group ID:</b> <code>{chat_id}</code>
<b>Status:</b> Configuration
<code>\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500</code>

<blockquote>Transaction environment established. Counterparty configuration pending.</blockquote>
"""

WELCOME_MESSAGE = """
𝘚𝘦𝘤𝘶𝘳𝘦 𝘌𝘴𝘤𝘳𝘰𝘸 𝘚𝘦𝘴𝘴𝘪𝘰𝘯

This group facilitates a secure escrow transaction managed by @{bot_username}.

<blockquote>To begin configuration: <code>/begin</code></blockquote>

All communications within this group are logged for dispute resolution.
"""

SESSION_INITIATED_MESSAGE = """
𝘚𝘦𝘴𝘴𝘪𝘰𝘯 𝘊𝘰𝘯𝘧𝘪𝘨𝘶𝘳𝘢𝘵𝘪𝘰𝘯 𝘚𝘵𝘢𝘳𝘵𝘦𝘥

<b>Participants:</b> {participants_display}

Declare your role to proceed:
<code>/buyer</code> or <code>/seller</code>

<blockquote>Role selection is final and binding for this transaction.</blockquote>
"""

ROLE_ANNOUNCEMENT_MESSAGE = """
{mention} designated as {role_emoji} <b>{role_name}</b>

<blockquote>Protocol Status: Buyers: {buyer_count} | Sellers: {seller_count}</blockquote>
"""

BUYER_CONFIRMED_MESSAGE = """
🔵 <a href="tg://user?id={buyer_id}">{buyer_name}</a> designated as <b>Purchasing Party</b>.
"""

SELLER_CONFIRMED_MESSAGE = """
🟢 <a href="tg://user?id={seller_id}">{seller_name}</a> designated as <b>Provisioning Party</b>.
"""

ROLE_ALREADY_CHOSEN_MESSAGE = """
<blockquote>Your contractual position for this protocol has been registered.</blockquote>
"""

ROLE_ALREADY_TAKEN_MESSAGE = """
<blockquote>This contractual position is occupied. Select the available designation.</blockquote>
"""

WALLET_SETUP_MESSAGE = """
𝘗𝘢𝘳𝘵𝘪𝘤𝘪𝘱𝘢𝘯𝘵𝘴 𝘊𝘰𝘯𝘧𝘪𝘳𝘮𝘦𝘥

<blockquote>
<b>Buyer:</b> {buyer_name}
<b>Seller:</b> {seller_name}
</blockquote>

Provide settlement addresses:

<code>/buyer {buyer_wallet_address}</code>
<code>/seller {seller_wallet_address}</code>

<blockquote>Addresses cannot be modified once submitted. Verify carefully before submission.</blockquote>
"""

ESCROW_READY_MESSAGE = """
𝘌𝘴𝘤𝘳𝘰𝘸 𝘊𝘰𝘯𝘵𝘳𝘢𝘤𝘵 𝘙𝘦𝘢𝘥𝘺

<blockquote>All prerequisites satisfied • Transaction ready to execute</blockquote>

<b>Participants</b>
• Buyer: {buyer_name}
• Seller: {seller_name}

<b>Settlement Addresses</b>
• Buyer: <code>{buyer_wallet}</code>
• Seller: <code>{seller_wallet}</code>

<b>Standard Execution Flow</b>
1. Buyer deposits agreed amount to escrow
2. Seller fulfills obligation
3. Buyer confirms satisfactory completion
4. Escrow releases funds to seller

<blockquote>All transaction communications must remain within this group for security and audit purposes.</blockquote>

𝘚𝘦𝘤𝘶𝘳𝘦 𝘛𝘳𝘢𝘯𝘴𝘢𝘤𝘵𝘪𝘰𝘯 𝘈𝘤𝘵𝘪𝘷𝘦
"""

STATS_MESSAGE = """
𝘗𝘦𝘳𝘧𝘰𝘳𝘮𝘢𝘯𝘤𝘦 𝘔𝘦𝘵𝘳𝘪𝘤𝘴

<blockquote>Transaction history and reliability indicators</blockquote>

• Total Escrows: 0
• Successfully Completed: 0
• Dispute Resolutions: 0
• Completion Rate: 0%

Statistics update upon transaction completion.
"""

ABOUT_MESSAGE = """
𝘗𝘭𝘢𝘵𝘧𝘰𝘳𝘮 𝘖𝘷𝘦𝘳𝘷𝘪𝘦𝘸

<blockquote>A neutral escrow solution for secure digital transactions</blockquote>

• P2P and multi-party transaction support
• Transparent, auditable process flow
• Admin-mediated dispute resolution
• Secure communication and documentation

Designed for high-value transactions requiring trusted intermediation.
"""

HELP_MESSAGE = """
𝘖𝘱𝘦𝘳𝘢𝘵𝘪𝘰𝘯𝘢𝘭 𝘗𝘳𝘰𝘵𝘰𝘤𝘰𝘭

<blockquote>Standard escrow execution process</blockquote>

1. Contract Creation – Terms and participants established
2. Role Assignment – Buyer and seller identities confirmed
3. Wallet Configuration – Settlement addresses registered
4. Fund Deposit – Buyer secures payment in escrow
5. Obligation Fulfillment – Seller delivers as agreed
6. Confirmation & Release – Buyer verifies, funds released

<blockquote>For protocol clarification or dispute assistance, contact designated administrators.</blockquote>
"""

# NEW MESSAGES TO ADD:

MERGED_PHOTO_CAPTION = """
𝘚𝘦𝘴𝘴𝘪𝘰𝘯 𝘐𝘯𝘪𝘵𝘪𝘢𝘵𝘦𝘥

<b>Participants:</b>
• {user1_name}
• {user2_name}

<blockquote>Please select your roles to proceed with configuration.</blockquote>
"""

PARTICIPANTS_CONFIRMED_MESSAGE = """
𝘗𝘢𝘳𝘵𝘪𝘤𝘪𝘱𝘢𝘯𝘵𝘴 𝘊𝘰𝘯𝘧𝘪𝘳𝘮𝘦𝘥

<blockquote>
<b>Transaction Type:</b> {group_type_display}
<b>Buyer:</b> {buyer_name}
<b>Seller:</b> {seller_name}
</blockquote>

<code>/buyer wallet_address</code>
<code>/seller wallet_address</code>

Configure settlement addresses to proceed.
"""

# Alternative with ASCII box characters if Unicode is problematic:
CHANNEL_LOG_CREATION_ASCII = """
𝘗𝘳𝘰𝘵𝘰𝘤𝘰𝘭 𝘐𝘯𝘪𝘵𝘪𝘢𝘵𝘪𝘰𝘯

<code>+-----------------------------</code>
<b>ID:</b> {group_name}
<b>Type:</b> {escrow_type}
<b>Time:</b> {timestamp}
<code>|-----------------------------</code>
<b>Initiator:</b> {creator_name}
<b>TG ID:</b> <code>{creator_id}</code>
<code>|-----------------------------</code>
<b>Group ID:</b> <code>{chat_id}</code>
<b>Status:</b> Configuration
<code>+-----------------------------</code>

<blockquote>Transaction environment established. Counterparty configuration pending.</blockquote>
"""
