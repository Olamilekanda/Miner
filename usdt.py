from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, Application
import logging
import json
from pathlib import Path
import time
import datetime
import os

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration variables
CHANNELS = ["@FREEA2RDR0P", "@LAKEA1DROP", "@PAYMENTOFPROVE"]
NOTIFICATION_ID = 7150558583
BONUS_FILE = Path("user_bonus_status.json")
BALANCE_FILE = Path("user_balances.json")
USER_DATA_FILE = Path("user_data.json")
NOTIFIED_USERS_FILE = Path("notified_users.json")
REFERRAL_BONUS = 0.0002
WELCOME_BONUS_AMOUNT = 0.0005
BONUS_AMOUNT = 0.0001
BOT_CREATION_DATE = datetime.datetime(2024, 10, 10)

# Load or initialize data
def load_json_file(file_path, default_value):
    if file_path.exists():
        with open(file_path, "r") as f:
            return json.load(f)
    return default_value

def save_json_file(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

user_bonus_status = load_json_file(BONUS_FILE, {})
user_balances = load_json_file(BALANCE_FILE, {})
user_data = load_json_file(USER_DATA_FILE, {})
notified_users = set(load_json_file(NOTIFIED_USERS_FILE, []))

# Functions for sending notifications, verifying channels, and updating balances
async def send_notification(context, user_id, username, first_name, last_name):
    notification_message = (
        f"🔔 **New User Started Bot** 🔔\n\n"
        f"**User ID:** {user_id}\n"
        f"**Username:** {username}\n"
        f"**First Name:** {first_name}\n"
        f"**Last Name:** {last_name}"
    )
    await context.bot.send_message(chat_id=NOTIFICATION_ID, text=notification_message)


# Your start function defined here
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "No Username"
    first_name = update.effective_user.first_name or "No First Name"
    last_name = update.effective_user.last_name or "No Last Name"

    # Handle referral logic
    referrer_id = context.args[0] if context.args else None
    if referrer_id:
        if referrer_id == user_id:
            await update.message.reply_text("🚫 You cannot refer yourself!")
            return

        # Ensure the referred user is initialized in the dictionary
        if user_id not in user_referrals:
            user_referrals[user_id] = {"count": 0, "referred_users": [], "username": username}

            # Ensure the referrer is initialized and update their username if needed
            if referrer_id not in user_referrals:
                chat = await context.bot.get_chat(referrer_id)  # Await the get_chat method
                referrer_username = chat.username or "No Username"
                user_referrals[referrer_id] = {"count": 0, "referred_users": [], "username": referrer_username}
            elif user_referrals[referrer_id]["username"] is None:
                chat = await context.bot.get_chat(referrer_id)  # Await the get_chat method
                user_referrals[referrer_id]["username"] = chat.username or "No Username"

            # Increase the referrer's count and update referred users list
            user_referrals[referrer_id]["count"] += 1
            user_referrals[referrer_id]["referred_users"].append(user_id)
            save_referral_data()

            # Add referral bonus (only if the user is referred for the first time)
            user_balances[referrer_id] = user_balances.get(referrer_id, 0) + 0.0002
            save_json_file(BALANCE_FILE, user_balances)

            # Send a message to the referrer
            await context.bot.send_message(
                chat_id=referrer_id,
                text="🎉 You have successfully referred a new user!\n"
                     "💸 A bonus of 0.0002 USDT has been credited to your balance."
            )

            # Send a welcome message to the referred user
            await update.message.reply_text(
                "🌟 Thank you for joining through a referral link!\n"
                "Explore the bot to earn more rewards."
            )
        else:
            # If the user has already been referred, no additional action is taken
            await update.message.reply_text(
                "⚠️ You have already been referred by someone else."
            )
            return

    # Send notification if not already sent
    if user_id not in notified_users:
        await send_notification(context, user_id, username, first_name, last_name)
        notified_users.add(user_id)
        save_json_file(NOTIFIED_USERS_FILE, list(notified_users))

    # Send welcome message with channel join verification
    welcome_message = (
        "🎉 **Welcome to Our Bot!** 🎉\n\n"
        "🚀 To get started and claim your bonus, join our channels:\n"
        "➤ @FREEA2RDR0P\n"
        "➤ @LAKEA1DROP\n"
        "➤ @PAYMENTOFPROVE\n\n"
        "💸 Once joined, you’ll receive a bonus of 0.0005 USDT!\n\n"
        "✅ Tap the button below to verify your subscriptions."
    )

    verify_button = InlineKeyboardButton("✅ Verify", callback_data="verify_channels")
    reply_markup = InlineKeyboardMarkup([[verify_button]])
    await update.message.reply_text(text=welcome_message, reply_markup=reply_markup)


async def verify_channels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if await check_user_channels(user_id, context):
        if str(user_id) not in user_bonus_status:
            user_bonus_status[str(user_id)] = True
            user_balances[str(user_id)] = user_balances.get(str(user_id), 0) + WELCOME_BONUS_AMOUNT
            save_json_file(BONUS_FILE, user_bonus_status)
            save_json_file(BALANCE_FILE, user_balances)
            await query.message.reply_text(text=(
                "🎁 **Congratulations!** 🎁\n\n"
                "You've successfully verified your subscription to our channels! 🎉\n\n"
                "A bonus of 0.0005 USDT has been credited to your account! 💸"
            ))

        # Remove the original join message and retry button after verification
        await query.message.delete()
        # Inline keyboard for setting the wallet
        inline_keyboard = [
            [InlineKeyboardButton("🔧 Set Wallet", callback_data='set_wallet')]
        ]
        inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

        # Regular keyboard layout
        keyboard = [
            [KeyboardButton("💰 Balance"), KeyboardButton("🎁 Bonus"), KeyboardButton("💳 Markets")],
            [KeyboardButton("💵 Deposit"), KeyboardButton("🔗 Referral Link"), KeyboardButton("🏧 Withdraw")],
            [KeyboardButton("🔧 Set Wallet"), KeyboardButton("❓ Help"), KeyboardButton("🔑 Unlock Profit")],
            [KeyboardButton("ℹ️ Airdrop Info"), KeyboardButton("🗒 Update"), KeyboardButton("📊 Statistics")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.message.reply_text(text="🥳 Welcome to our Bot! 🥳\n\nYou can always return to check the airdrop and explore more offers! 🌟\n\n💡 Stay tuned for exciting updates and rewards! 🎁", reply_markup=reply_markup)
    else:
        retry_button = InlineKeyboardButton("🔄 Retry", callback_data="verify_channels")
        retry_markup = InlineKeyboardMarkup([[retry_button]])
        await query.edit_message_text(text=(
            "❗️ **It looks like you haven’t joined the channels yet.**\n\n"
            "Please join the following channels to proceed:\n"
            "➤ @FREEA2RDR0P\n"
            "➤ @LAKEA1DROP\n"
            "➤ @PAYMENTOFPROVE\n\n"
            "Once joined, click the button below to verify your subscriptions."
        ), reply_markup=retry_markup)

async def check_user_channels(user_id: int, context) -> bool:
    try:
        for channel in CHANNELS:
            chat_member = await context.bot.get_chat_member(channel, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking user channels: {e}")
        return False

async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"

    # Get the user's balance and round it to 4 decimal places
    balance = user_balances.get(str(user_id), 0)
    rounded_balance = round(balance, 5)

    balance_message = (
        f"💰 **Your Balance** 💰\n\n"
        f"👤 **Username:** {username}\n\n"
        f"💸 **Balance:** {rounded_balance} USDT\n\n"
        "Keep using the bot to earn more!\n\n"
        "🥇 Upgrade your Account To Earn More USDT"
    )
    await update.message.reply_text(text=balance_message)


async def bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    last_bonus_time = user_bonus_status.get(str(user_id), 0)

    # Check if 24 hours have passed since the last bonus
    if time.time() - last_bonus_time < 24 * 60 * 60:
        remaining_seconds = int(24 * 60 * 60 - (time.time() - last_bonus_time))
        remaining_hours = remaining_seconds // 3600
        remaining_minutes = (remaining_seconds % 3600) // 60
        remaining_seconds = remaining_seconds % 60
        formatted_time = f"{remaining_hours:02}:{remaining_minutes:02}:{remaining_seconds:02}"

        await update.message.reply_text(
            f"⏳ You can claim your next bonus in {formatted_time}!\n"
            f"😊 Stay tuned for more opportunities to earn!"
        )
    else:
        # Update the user's balance with the correct bonus amount
        current_balance = user_balances.get(str(user_id), 0)
        user_balances[str(user_id)] = current_balance + BONUS_AMOUNT

        # Record the time when the bonus was claimed
        user_bonus_status[str(user_id)] = time.time()

        # Save the updated data to the files
        save_json_file(BONUS_FILE, user_bonus_status)
        save_json_file(BALANCE_FILE, user_balances)

        # Send a confirmation message
        await update.message.reply_text(
            f"🥳 You have successfully claimed your bonus of {BONUS_AMOUNT:.4f} USDT! 🥳\n\n"
            f"Come back in 24 hours to claim another one! ⏰"
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🔧 Help Center\n\n"
        "Hello there! 👋 Need help or have questions? You’re at the right place! 🌟\n\n"
        "Here’s how we can assist you:\n\n"
        "📜 General Help: If you have any questions about how to use the bot or need assistance with any features, feel free to ask!\n\n"
        "📈 Updates & Announcements: Stay tuned for updates and announcements. Make sure to join our channels for the latest news!\n\n"
        "💬 Contact Support: If you need personal assistance or have specific inquiries, you can reach out directly to me:\n"
        "   - Username: @Botdeveloperking\n\n"
        "🔄 Feedback: We value your feedback! Let us know how we can improve your experience. Your suggestions are always welcome! 💡\n\n"
        "🚀 Enjoy the Bot! We're here to make your experience amazing. If you have any more questions or need help with anything else, just let me know! 😃"
    )


async def statistics_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the "📊 Statistics" button press."""
    num_users = len(user_balances)  # Count the number of users

    await update.message.reply_text(
        f"📊 **Bot Statistics** 📊\n\n"
        f"👑 **Developer:** 👑 @Botdeveloperking\n\n"
        f"👥 **Active Users:** {num_users} users\n\n"
        f"🗓️ **Bot Created:** {BOT_CREATION_DATE.strftime('%Y-%m-%d')}\n\n"
        f"💬 **We're growing strong! Thank you for being a part of our community.** 💬\n\n"
        f"✨ **Your participation is what makes us thrive.** ✨\n\n"
        f"📈 **Stay tuned for new features and updates coming soon.** 🚀\n\n"
        f"**We appreciate your support! If you have any suggestions or feedback, feel free to share.**"
    )



# Set wallet handler
async def set_wallet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or "user"

    user_info = user_data.get(user_id, {'username': username, 'wallet': None})
    wallet_address = user_info.get('wallet', 'Not set')

    if wallet_address == 'Not set':
        wallet_message = (
            "🔧 **Account Settings**\n\n"
            f"👤 **Username:** @{username}\n"
            "💼 **Wallet Address:** Wallet not set.\n\n"
            "⚠️ You haven't set your wallet address yet! Please provide a valid USDT address to receive payments.\n\n"
            "🔗 Click the button below to set your wallet."
        )
    else:
        wallet_message = (
            "🔧 **Account Settings**\n\n"
            f"👤 **Username:** @{username}\n"
            f"💼 **Wallet Address:** {wallet_address}\n\n"
            "🔄 If you want to change your wallet address, click the button below."
        )

    keyboard = [
        [InlineKeyboardButton("🔧 Set Wallet", callback_data='set_wallet')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(wallet_message, reply_markup=reply_markup, parse_mode='Markdown')

async def set_wallet_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Please enter your USDT wallet address:")
    context.user_data['expecting_wallet'] = True

async def process_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    user_input = update.message.text.strip()

    if context.user_data.get('expecting_wallet'):
        if len(user_input) < 26 or len(user_input) > 42:
            await update.message.reply_text("❌ Invalid USDT wallet address.")
            return

        for uid, data in user_data.items():
            if data.get('wallet') == user_input:
                await update.message.reply_text("⚠️ This wallet address is already used.")
                return

        user_info = user_data.get(user_id, {'username': update.effective_user.username, 'wallet': None})
        user_info['wallet'] = user_input
        user_data[user_id] = user_info
        save_user_data(user_data)

        await update.message.reply_text("✅ Your USDT wallet address has been successfully set!")
        context.user_data['expecting_wallet'] = False




# File to store referral data
REFERRAL_FILE = "user_referrals.json"

# Load referral data
if os.path.exists(REFERRAL_FILE):
    with open(REFERRAL_FILE, "r") as f:
        user_referrals = json.load(f)
else:
    user_referrals = {}

# Save referral data
def save_referral_data():
    with open(REFERRAL_FILE, "w") as f:
        json.dump(user_referrals, f)

async def referral_link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    referral_link = f"https://t.me/USDT_SEASONONE_BOT?start={user_id}"

    # Count the number of referrals
    referrals = user_referrals.get(user_id, {"count": 0, "referred_users": []})
    referral_count = referrals["count"]

    referral_message = (
        f"🔗 **Your Referral Link:**\n\n"
        f"👉 {referral_link}\n\n"
        f"📈 **You have referred {referral_count} users!**\n\n"
        "📈 **Referral Rewards:**\n"
        "Each friend who joins through your link will add 0.0002 USDT to your balance. Keep inviting and watch your balance grow! 💰\n\n"
        "🔄 **Referral System:**\n"
        "Track your referrals and rewards directly in the bot. The more you refer, the higher your chances of earning more USDT! 🎯"
    )

    await update.message.reply_text(referral_message)




async def airdrop_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    info_message = (
        "ℹ️ **Airdrop Information** ℹ️\n\n"
        "Welcome to our **Exclusive Airdrop Bot**! 🚀\n\n"
        "🔗 **Referral System**:\n"
        "Earn rewards by inviting your friends! Share your unique referral link, "
        "and for every person who joins through your link, you'll receive a bonus of 0.00002 USDT. "
        "The more you refer, the more you earn! 💸\n\n"
        "🏆 **Top Referrers**:\n"
        "Compete to be one of the top referrers! Each month, the top 10 referrers will be featured, "
        "and the highest referrer will receive an additional bonus reward. Stay active to climb the leaderboard! 🥇\n\n"
        "🔧 **Bot Features**:\n"
        "- **Balance Check**: See your current earnings and bonuses.\n"
        "- **Set Wallet**: Easily set or update your withdrawal wallet address.\n"
        "- **Bonus**: Claim your daily or special bonuses.\n"
        "- **Statistics**: Keep track of your referral count and performance.\n"
        "- **Help**: Get support and answers to frequently asked questions.\n\n"
        "📅 **Seasonal Break**:\n"
        "To ensure fair play and bot maintenance, our bot will take a break for one month every season. "
        "During this time, referrals and earnings will be paused, giving everyone a chance to reset and prepare for the next season. "
        "The bot will notify you before the break starts. Make sure to claim all your rewards before the break! 🛠️\n\n"
        "👨‍💻 **About the Bot**:\n"
        "This bot is developed to provide users with an easy and fun way to earn rewards through referrals. "
        "It is designed with security and user-friendliness in mind, ensuring a smooth experience for all participants. "
        "Our team is dedicated to continuously improving the bot and adding new features to enhance your experience.\n\n"
        "👨‍💻 **Developer Info**:\n"
        "Developed by a passionate team of crypto enthusiasts and developers. "
        "For any queries or support, feel free to reach out to our support team.\n\n"
        "Thank you for participating in our airdrop and helping grow our community! 🎉"
    )

    await update.message.reply_text(info_message)




from telegram import Bot
import os
import json
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pathlib import Path

# File to store user data including wallet addresses
USER_DATA_FILE = 'user_data.json'
BALANCE_FILE = Path("user_balances.json")

# Load user data
def load_user_data():
    if not os.path.exists(USER_DATA_FILE):
        return {}
    with open(USER_DATA_FILE, 'r') as f:
        return json.load(f)

# Save user data
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Load balances (replace with your balance logic)
def load_balances():
    if BALANCE_FILE.exists():
        with open(BALANCE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_balances(data):
    with open(BALANCE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Initialize user data and balances
user_data = load_user_data()
user_balances = load_balances()

# Track ongoing withdrawals
pending_withdrawals = {}

# Predefined withdrawal amounts
withdrawal_options = ["10", "25", "500", "🚫 Cancel"]
# Define your channel ID
CHANNEL_ID = "@PAYMENTOFPROVE"

async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    wallet_address = None  # Initialize wallet_address

    # Step 1: Display withdrawal options as a reply keyboard
    if update.message.text == "🏧 Withdraw":
        keyboard = [withdrawal_options]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        await update.message.reply_text("💰 Choose Amount You Want to Withdraw:", reply_markup=reply_markup)

    # Step 2: Handle input validation and withdrawal process
    elif update.message.text in withdrawal_options:
        if update.message.text == "🚫 Cancel":
            # Main menu
            main_menu_keyboard = [
                [KeyboardButton("💰 Balance"), KeyboardButton("🎁 Bonus"), KeyboardButton("💳 Markets")],
                [KeyboardButton("💵 Deposit"), KeyboardButton("🔗 Referral Link"), KeyboardButton("🏧 Withdraw")],
                [KeyboardButton("🔧 Set Wallet"), KeyboardButton("❓ Help"), KeyboardButton("🔑 Unlock Profit")],
                [KeyboardButton("ℹ️ Airdrop Info"), KeyboardButton("🗒 Update"), KeyboardButton("📊 Statistics")]
            ]
            reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

            await update.message.reply_text("🥳 Welcome back! 🌟", reply_markup=reply_markup)
        else:
            # Store the selected amount for this user
            amount = int(update.message.text)
            pending_withdrawals[user_id] = amount

            # Step 3: Retrieve the user's wallet address from stored data
            user_info = user_data.get(user_id, {})
            wallet_address = user_info.get('wallet')

            # Check if the wallet address is properly retrieved
            if wallet_address:
                # Step 4: Show confirmation message with "Confirm" and "Cancel" buttons
                confirm_keyboard = [
                    [KeyboardButton("✅ Confirm"), KeyboardButton("🚫 Cancel")]
                ]
                reply_markup = ReplyKeyboardMarkup(confirm_keyboard, one_time_keyboard=True, resize_keyboard=True)

                await update.message.reply_text(
                    f"🚀 *Confirmation* 🚀:\n\n"
                    f"🔢 *Address* :\n`{wallet_address}`\n"
                    f"💰 *Amount* : `{amount}` (fee: 10%) USDT\n\n"
                    "⚡ *Confirm Your Payment by clicking on* `Confirm`",
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "⚠️ You have not set a wallet address yet. Please set your wallet using the '🔧 Set Wallet' option."
                )

    # Step 5: Handle confirmation or cancellation of the withdrawal
    elif update.message.text == "✅ Confirm":
        # Retrieve the pending withdrawal amount
        amount = pending_withdrawals.get(user_id)

        # Retrieve the wallet address again in case it's not set
        user_info = user_data.get(user_id, {})
        wallet_address = user_info.get('wallet')

        if amount is None or wallet_address is None:
            await update.message.reply_text("⚠️ No pending withdrawal or wallet address found.")
            return

        # Perform the withdrawal logic
        if user_balances.get(user_id, 0) >= amount:
            user_balances[user_id] -= amount
            # Round the balance to 5 decimal places
            user_balances[user_id] = round(user_balances[user_id], 5)
            # Update user balance in persistent storage
            save_balances(user_balances)

            # Notify user of successful withdrawal
            await update.message.reply_text(
                "✅ *New Withdrawal Processed!* ⚡\n\n"
                f"📩 *Sent To* :\n`{wallet_address}`\n"
                f"💰 *Amount* : `{amount}` USDT\n\n"
                "🚀 *In Bot* : @USDT_SEASONONE_BOT",
                parse_mode="Markdown"
            )

            # Send notification to the channel
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=(
                    "💵 *New Withdraw Sent* 💵\n\n"
                    f"🔍 *Status* = Confirmed\n"
                    f"👤 *User* = @{update.effective_user.username}\n"
                    f"🆔 *User ID* = `{user_id}`\n"
                    f"💰 *Amount* = `{amount} USDT`\n"
                    f"🏦 *Address* = `{wallet_address}`\n"
                    f"🤖 *Bot* = @USDT_SEASONONE_BOT"
                ),
                parse_mode="Markdown"
            )

            # Return to main menu
            main_menu_keyboard = [
                [KeyboardButton("💰 Balance"), KeyboardButton("🎁 Bonus"), KeyboardButton("💳 Markets")],
                [KeyboardButton("💵 Deposit"), KeyboardButton("🔗 Referral Link"), KeyboardButton("🏧 Withdraw")],
                [KeyboardButton("🔧 Set Wallet"), KeyboardButton("❓ Help"), KeyboardButton("🔑 Unlock Profit")],
                [KeyboardButton("ℹ️ Airdrop Info"), KeyboardButton("🗒 Update"), KeyboardButton("📊 Statistics")]
            ]
            reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

            await update.message.reply_text("🥳 Your withdrawal was successful!\n\n🌟 You will be credited before 24 hours", reply_markup=reply_markup)
            # Clear the pending withdrawal
            del pending_withdrawals[user_id]

        else:
            await update.message.reply_text(
                "⚠️ *Insufficient Balance* ⚠️\n\n"
                f"Your current balance is `{user_balances.get(user_id, 0):.5f}` USDT, which is insufficient for this withdrawal.",
                parse_mode="Markdown"
            )

            # Return to main menu
            main_menu_keyboard = [
                [KeyboardButton("💰 Balance"), KeyboardButton("🎁 Bonus"), KeyboardButton("💳 Markets")],
                [KeyboardButton("💵 Deposit"), KeyboardButton("🔗 Referral Link"), KeyboardButton("🏧 Withdraw")],
                [KeyboardButton("🔧 Set Wallet"), KeyboardButton("❓ Help"), KeyboardButton("🔑 Unlock Profit")],
                [KeyboardButton("ℹ️ Airdrop Info"), KeyboardButton("🗒 Update"), KeyboardButton("📊 Statistics")]
            ]
            reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

            await update.message.reply_text("🔄 Please check your balance and try again.", reply_markup=reply_markup)
            # Clear the pending withdrawal
            del pending_withdrawals[user_id]







# Updated wallet addresses
wallet_addresses = {
    'ETH': '0x9DF83278862d790f820D0b440Aa78e5908461C73',
    'BTC': 'bc1q6twmxc78npdaph930e0nlcccdukrtvpaptzm0m',
    'BNB': 'bnb1t7phrsgas4nrckcpn5cnfs3llff74vvn5hylul',
    'DGB': 'dgb1qejadjp6lytajm303uv8c7y87ekayun2dg2lr96',
    'TRX': 'TJUcRvN9q68bsjDoYCBwnSVmXcktAEEC2D',
    'SOL': 'APwA5kZyC26wmS9t47kPTsjqsx1VdmycqVejzYETGVvq'
}

# Function to generate the keyboard with two rows of three buttons each
def generate_currency_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("♦️ Pay ETH", callback_data='ETH'),
            InlineKeyboardButton("♦️ Pay BTC", callback_data='BTC'),
            InlineKeyboardButton("♦️ Pay BNB", callback_data='BNB')
        ],
        [
            InlineKeyboardButton("♦️ Pay DGB", callback_data='DGB'),
            InlineKeyboardButton("♦️ Pay TRX", callback_data='TRX'),
            InlineKeyboardButton("♦️ Pay SOL", callback_data='SOL')
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# Function to generate the cancel button as a reply keyboard
def generate_cancel_keyboard():
    keyboard = [[KeyboardButton("🚫 Cancel")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Command handler to start the deposit process
async def deposit_handler(update: Update, context):
    await update.message.reply_text(
        "💵 Choose Your Currency For Purchase",
        reply_markup=generate_currency_keyboard()
    )

# CallbackQueryHandler to handle currency selection
async def currency_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    currency = query.data  # This should match one of the keys in wallet_addresses

    if currency in wallet_addresses:
        currency_name = currency.upper()
        message = f"⚠️ If you send less than 0.20 {currency_name}, your deposit will be ignored!\n\n"
        message += f"✅ Send the amount you want to deposit to the following address:\n\n"
        message += f"`{wallet_addresses[currency]}`\n\n"
        message += "📸 Please send a screenshot of your wallet address. Note that if you send a fake proof, your deposit will be rejected!\n\nYour details are safe with us!"

        await query.edit_message_text(text=message)
        await query.message.reply_text(
            "🚫 You can cancel the operation by pressing the Cancel button below.",
            reply_markup=generate_cancel_keyboard()
        )

        # Set state to indicate the bot is awaiting proof
        context.user_data['awaiting_proof'] = True
    else:
        await query.edit_message_text(text="❌ Unknown currency action. Please try again.")

# Handler to process the user's response (specifically for photos)
async def process_user_input(update: Update, context):
    if context.user_data.get('awaiting_proof'):
        if update.message.photo:
            # Send the photo to your Telegram ID
            await context.bot.send_photo(chat_id=7150558583, photo=update.message.photo[-1].file_id)

            # Ask for payment proof
            await update.message.reply_text(
                "📤 Thank you for sending the screenshot. Now, please send the proof of payment (a screenshot of your payment confirmation).",
                reply_markup=generate_cancel_keyboard()
            )

            # Update state to indicate the bot is awaiting payment proof now
            context.user_data['awaiting_proof'] = False
            context.user_data['awaiting_payment_proof'] = True

        else:
            await update.message.reply_text(
                "❌ Only images are allowed! Please send a valid screenshot or press Cancel to stop the process.",
                reply_markup=generate_cancel_keyboard()
            )

    elif context.user_data.get('awaiting_payment_proof'):
        if update.message.photo:
            # Send the payment proof photo to your Telegram ID
            await context.bot.send_photo(chat_id=7150558583, photo=update.message.photo[-1].file_id)

            await update.message.reply_text("✅ Payment proof received!\n\nYou be credited before 24 hours!\n\nFake proof or fake transfer can lead to ban be warned!\n\nReturning to the main menu.")
            await return_to_main_menu(update)

            # Reset state
            context.user_data['awaiting_payment_proof'] = False

        else:
            await update.message.reply_text(
                "❌ Only images are allowed! Please send a valid payment proof screenshot or press Cancel to stop the process.",
                reply_markup=generate_cancel_keyboard()
            )

# Handler for cancel operation
async def cancel_handler(update: Update, context):
    # Reset all states
    context.user_data['awaiting_proof'] = False
    context.user_data['awaiting_payment_proof'] = False
    await return_to_main_menu(update)

# Function to return to the main menu
async def return_to_main_menu(update: Update):
    main_menu_keyboard = [
        [KeyboardButton("💰 Balance"), KeyboardButton("🎁 Bonus"), KeyboardButton("💳 Markets")],
        [KeyboardButton("💵 Deposit"), KeyboardButton("🔗 Referral Link"), KeyboardButton("🏧 Withdraw")],
        [KeyboardButton("🔧 Set Wallet"), KeyboardButton("❓ Help"), KeyboardButton("🔑 Unlock Profit")],
        [KeyboardButton("ℹ️ Airdrop Info"), KeyboardButton("🗒 Update"), KeyboardButton("📊 Statistics")]
    ]
    reply_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True)

    await update.message.reply_text("🔄 Operation completed successfully! Returning to the home menu.", reply_markup=reply_markup)





from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define miners with updated production values
MINERS = [
    {"name": "Solar Panel 1", "speed": "150 GH/s", "produced_per_hour": "0.01375 USDT", "produced_per_day": "0.33 USDT", "produced_per_second": "0.00000382", "price": "0.002 USDT", "days_available": 3, "gain": "1 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 2", "speed": "300 GH/s", "produced_per_hour": "0.0417 USDT", "produced_per_day": "1 USDT", "produced_per_second": "0.0000116", "price": "3 USDT", "days_available": 6, "gain": "6 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 3", "speed": "450 GH/s", "produced_per_hour": "0.0694 USDT", "produced_per_day": "1.67 USDT", "produced_per_second": "0.0000193", "price": "5 USDT", "days_available": 9, "gain": "10 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 4", "speed": "600 GH/s", "produced_per_hour": "0.0972 USDT", "produced_per_day": "2.33 USDT", "produced_per_second": "0.000027", "price": "7 USDT", "days_available": 12, "gain": "14 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 5", "speed": "750 GH/s", "produced_per_hour": "0.125 USDT", "produced_per_day": "3 USDT", "produced_per_second": "0.0000347", "price": "9 USDT", "days_available": 15, "gain": "18 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 6", "speed": "900 GH/s", "produced_per_hour": "0.1528 USDT", "produced_per_day": "3.67 USDT", "produced_per_second": "0.0000424", "price": "11 USDT", "days_available": 18, "gain": "22 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 7", "speed": "1050 GH/s", "produced_per_hour": "0.1806 USDT", "produced_per_day": "4.33 USDT", "produced_per_second": "0.0000502", "price": "13 USDT", "days_available": 21, "gain": "26 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 8", "speed": "1200 GH/s", "produced_per_hour": "0.2083 USDT", "produced_per_day": "5 USDT", "produced_per_second": "0.0000577", "price": "15 USDT", "days_available": 24, "gain": "30 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 9", "speed": "1350 GH/s", "produced_per_hour": "0.2361 USDT", "produced_per_day": "5.67 USDT", "produced_per_second": "0.0000652", "price": "17 USDT", "days_available": 27, "gain": "34 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"},
    {"name": "Solar Panel 10", "speed": "1500 GH/s", "produced_per_hour": "0.2639 USDT", "produced_per_day": "6.33 USDT", "produced_per_second": "0.0000724", "price": "19 USDT", "days_available": 30, "gain": "38 USDT", "image_url": "https://thumbs.dreamstime.com/b/solar-panels-under-sun-cartoon-produces-recyclabel-electric-energy-119958874.jpg"}
]

async def miner_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for miner in MINERS:
        # Send the image
        await update.message.reply_photo(photo=miner['image_url'])

        # Send the miner info with days available and gain in USDT
        miner_info = (
            f"*⛏️ {miner['name']}*\n"
            f"*⚡ Speed:* `{miner['speed']}`\n"
            f"*🌟 USDT Produced Per Second:* `{miner['produced_per_second']}`\n"
            f"*⏱️ USDT Produced Per Hour:* `{miner['produced_per_hour']}`\n"
            f"*🌞 USDT Produced Per Day:* `{miner['produced_per_day']}`\n"
            f"*💲 Price:* `{miner['price']}`\n"
            f"*📅 Days Available:* `{miner['days_available']}`\n"
            f"*🎉 Gain:* `{miner['gain']}`\n"
            "\n*Get your high efficiency miner today and start earning USDT!*"
        )
        button = InlineKeyboardButton("💰 Acquire Miner", callback_data=f"acquire_{miner['name'].replace(' ', '_')}")
        reply_markup = InlineKeyboardMarkup([[button]])
        await update.message.reply_text(miner_info, parse_mode='Markdown', reply_markup=reply_markup)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, CallbackQueryHandler, ContextTypes

from datetime import datetime, timedelta

async def acquire_miner(update: Update, context: CallbackContext, miner_name: str):
    user_id = str(update.effective_user.id)

    selected_miner = next((miner for miner in MINERS if miner['name'].replace(' ', '_') == miner_name), None)
    if selected_miner is None:
        await update.callback_query.answer("Miner not found.")
        return

    balance = user_balances.get(user_id, 0)
    miner_price = float(selected_miner['price'].replace("USDT", "").strip())

    if balance >= miner_price:
        user_balances[user_id] = balance - miner_price
        save_json_file(BALANCE_FILE, user_balances)

        # Add miner to user's purchased list with expiration date
        if user_id not in purchased_miners:
            purchased_miners[user_id] = []

        expiration_date = datetime.now() + timedelta(days=selected_miner['days_available'])
        purchased_miners[user_id].append({
            "name": selected_miner['name'],
            "purchase_date": datetime.now().isoformat(),
            "expiration_date": expiration_date.isoformat(),
            "produced_per_second": selected_miner['produced_per_second']
        })
        save_json_file(PURCHASED_MINERS_FILE, purchased_miners)

        await update.callback_query.answer("Miner acquired successfully! 🎉")
        await update.callback_query.message.reply_text(
            f"✅ You have acquired {selected_miner['name']} for {miner_price} USDT.\n"
            f"💸 Your new balance is {user_balances[user_id]:.4f} USDT."
        )
    else:
        await update.callback_query.answer("Insufficient funds! ❌")
        await update.callback_query.message.reply_text(
            f"🚫 You do not have enough balance to acquire {selected_miner['name']}.\n"
            f"💸 Your current balance is {balance:.5f} USDT.\n"
            f"Please top up your balance or choose a different miner."
        )
# Handle the button press to acquire a miner
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    # Process the callback data
    callback_data = query.data

    if callback_data == 'set_wallet':
        await set_wallet_callback_handler(update, context)
    elif callback_data in ['ETH', 'BTC', 'BNB', 'DGB', 'TRX', 'SOL']:
        await currency_callback_handler(update, context)
    elif callback_data.startswith('acquire_'):
        miner_name = callback_data.replace('acquire_', '')  # Extract miner name from callback data
        await acquire_miner(update, context, miner_name)
    else:
        await query.edit_message_text(text="❌ Unknown action. Please try again.")

PURCHASED_MINERS_FILE = Path("purchased_miners.json")

# Load or initialize purchased miners data
purchased_miners = load_json_file(PURCHASED_MINERS_FILE, {})

from datetime import datetime
import json
import time

async def collect_handler(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)

    if user_id not in purchased_miners or not purchased_miners[user_id]:
        await update.message.reply_text(
            "😕 You haven't purchased any miners yet.\n"
            "⛏️ Go to the miner store and start earning USDT today!"
        )
        return

    miner_message = "🤑 **Your Purchased Miners** 🤑\n\n"
    total_earnings = 0.0
    current_time = datetime.now()

    for miner in purchased_miners[user_id]:
        expiration_date = datetime.fromisoformat(miner['expiration_date'])
        if current_time < expiration_date:
            miner_status = "🟢 Working"
            earnings = float(miner['produced_per_second']) * (current_time - datetime.fromisoformat(miner['purchase_date'])).total_seconds()
            total_earnings += earnings
            miner['purchase_date'] = current_time.isoformat()  # Update purchase date to current time after collecting
        else:
            miner_status = "🔴 Expired"
            earnings = 0.0

        miner_message += (
            f"*⛏️ {miner['name']}*\n"
            f"*⚡ Speed:* {miner['produced_per_second']} USDT/second\n"
            f"*💲 Earnings:* {earnings:.4f} USDT\n"
            f"*📅 Status:* {miner_status}\n\n"
        )

    # Update the user's balance with total earnings
    user_balances[user_id] = user_balances.get(user_id, 0) + total_earnings
    save_json_file(BALANCE_FILE, user_balances)

    # Save updated miner data back to the file
    save_json_file(PURCHASED_MINERS_FILE, purchased_miners)

    # Send the miner status message to the user
    miner_message += f"💸 **Total Earnings:** {total_earnings:.4f} USDT\n"
    await update.message.reply_text(text=miner_message, parse_mode='Markdown')

import json
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# Load or initialize the update.json file
def load_data():
    try:
        with open('update.json', 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {
            "countdown_end_time": (datetime.now() + timedelta(days=30)).isoformat(),
            "messages": []
        }
        save_data(data)
    return data

def save_data(data):
    with open('update.json', 'w') as file:
        json.dump(data, file, indent=4)

# Load the notified users from notified_users.json
def load_notified_users():
    try:
        with open('notified_users.json', 'r') as file:
            user_data = json.load(file)
    except FileNotFoundError:
        user_data = {"notified_users": []}
        save_notified_users(user_data)
    return user_data["notified_users"]

def save_notified_users(user_data):
    with open('notified_users.json', 'w') as file:
        json.dump({"notified_users": user_data}, file, indent=4)

# Adding a new message every 3 days
def add_message():
    data = load_data()
    messages = data["messages"]

    new_messages = [
        "🚀 New feature: Games will be part of Season Two! Expect exciting challenges and rewards.",
        "🔒 Enhanced security: Your mining sessions will be safer than ever in Season Two. Stay protected!",
        "🎉 Big rewards: Get ready for some huge bonuses coming your way next season. Don't miss out!",
        "⚙️ Optimized Performance: Mining efficiency will be significantly improved in Season Two. Faster and better!",
        "💰 Double Earnings: Season Two will bring you opportunities to double your mining earnings. Stay tuned!",
        "🌍 Global Leaderboard: Compete with miners around the world and climb to the top. Show your skills!",
        "📈 Enhanced Analytics: Get detailed insights into your mining activities with our new analytics tools.",
        "🔔 Instant Notifications: Never miss an important update with our new instant notification feature.",
        "🎯 Daily Challenges: Participate in daily mining challenges and win exclusive rewards!",
        "💸 Lower Fees: We've reduced transaction fees in Season Two, making it easier to cash out your earnings.",
        "🎁 Surprise Gifts: Look out for surprise gifts and bonuses throughout Season Two. Keep mining!",
        "🚨 Anti-Fraud Measures: We've implemented stronger anti-fraud measures to protect your earnings.",
        "🛠 Customizable Mining: Tailor your mining experience with our new customization options in Season Two.",
        "🎮 Interactive Games: Enjoy interactive games within the bot that offer real crypto rewards!",
        "🔧 Automated Tools: Season Two introduces automation tools to streamline your mining operations.",
        "🆕 New Miner Types: Discover new miner types with unique abilities and higher profitability.",
        "🌐 Multi-Currency Support: Season Two will allow mining and transactions in multiple cryptocurrencies!",
        "🔄 Instant Withdrawal: Experience faster withdrawals with our improved payment processing system.",
        "💬 Community Features: Engage with other miners and share tips in our new community section.",
        "🏆 Seasonal Competitions: Participate in seasonal competitions and win big! Season Two is going to be epic!"
    ]

    if len(messages) < len(new_messages):
        message_to_add = new_messages[len(messages)]
        messages.append(message_to_add)
        save_data(data)

        # Notify all users
        user_ids = load_notified_users()
        for chat_id in user_ids:
            application.bot.send_message(chat_id=chat_id, text=message_to_add)

# Display the update information
async def update_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    end_time = datetime.fromisoformat(data["countdown_end_time"])
    time_remaining = end_time - datetime.now()

    new_features = "\n\n".join(data["messages"])

    await update.message.reply_text(
        f"⏳ Time Remaining: {time_remaining.days} days, {time_remaining.seconds // 3600} hours\n\n"
        "🆕 New features coming in Season Two:\n"
        f"{new_features}"
    )





def main():
    # Create the Application instance with your bot token
    application = Application.builder().token("7212606267:AAEkQ-ttmBekQDY638HHoW9cUcUMWKsoeZQ").build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^🔗 Referral Link$"), referral_link_handler))
    application.add_handler(CallbackQueryHandler(verify_channels_handler, pattern="verify_channels"))
    application.add_handler(MessageHandler(filters.Regex("^💰 Balance$"), balance_handler))
    application.add_handler(MessageHandler(filters.Regex("^🎁 Bonus$"), bonus_handler))
    application.add_handler(MessageHandler(filters.Regex("^❓ Help$"), help_handler))
    application.add_handler(MessageHandler(filters.Regex("^📊 Statistics$"), statistics_handler))
    application.add_handler(MessageHandler(filters.Regex("^🗒 Update$"), update_command))
    application.add_handler(MessageHandler(filters.Regex("^ℹ️ Airdrop Info$"), airdrop_info_handler))
    application.add_handler(MessageHandler(filters.Regex("^🔑 Unlock Profit$"), collect_handler))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_handler(MessageHandler(filters.Regex("^💳 Markets$"), miner_handler))
    application.add_handler(MessageHandler(filters.Regex("^💵 Deposit$"), deposit_handler))

    # Add the new handlers for the deposit process
    application.add_handler(CallbackQueryHandler(currency_callback_handler, pattern='^deposit_'))
    application.add_handler(MessageHandler(filters.PHOTO, process_user_input))
    application.add_handler(MessageHandler(filters.Regex("^🚫 Cancel$"), cancel_handler))

    # Handle the initial withdrawal command
    # Handle the initial withdrawal command
    application.add_handler(MessageHandler(filters.Regex("^🏧 Withdraw$"), withdraw_handler))

    # Handle the specific withdrawal options (amounts or cancel)
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(10|25|500|🚫 Cancel|✅ Confirm)$"), withdraw_handler))

    # Handle setting the wallet address
    application.add_handler(MessageHandler(filters.Regex("^🔧 Set Wallet$"), set_wallet_handler))
    application.add_handler(CallbackQueryHandler(set_wallet_callback_handler, pattern='^set_wallet$'))

    # Handle processing the wallet address text input
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_wallet_address))

    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
= '__main__':
    main()