import os
import json
import time
import asyncio
import pyotp

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# ============================================================
# KHOM AUTHENTICATOR BOT
# ============================================================

BOT_TOKEN = "8692292968:AAFkq55-kgvXuCln9JHgFMdA8oJZ6BhMUmU"


# ============================================================
# SECURITY
# ============================================================
# IMPORTANT:
# Replace ONLY the number below with YOUR Telegram User ID.
#
# Example:
# ALLOWED_USER_ID = 987654321
#
# Do NOT put quotes around the number.
# ============================================================

ALLOWED_USER_ID = 1624771725


# ============================================================
# ACCOUNT FILE
# ============================================================

ACCOUNTS_FILE = "accounts.json"


# ============================================================
# SECURITY CHECK
# ============================================================

def is_authorized(update: Update):

    user = update.effective_user

    if not user:
        return False

    return user.id == ALLOWED_USER_ID


# ============================================================
# UNAUTHORIZED MESSAGE
# ============================================================

async def deny_access(update: Update):

    if update.callback_query:

        try:
            await update.callback_query.answer(
                "⛔ Access Denied.",
                show_alert=True
            )
        except Exception:
            pass

        return

    if update.message:

        try:
            await update.message.reply_text(
                "⛔ Access Denied."
            )
        except Exception:
            pass


# ============================================================
# ACCOUNT FILE FUNCTIONS
# ============================================================

def load_accounts():

    if not os.path.exists(ACCOUNTS_FILE):
        return {}

    try:

        with open(
            ACCOUNTS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception as e:

        print(f"❌ Error loading accounts: {e}")

    return {}


def save_accounts(accounts):

    try:

        with open(
            ACCOUNTS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                accounts,
                f,
                indent=4
            )

        return True

    except Exception as e:

        print(f"❌ Error saving accounts: {e}")

        return False


# ============================================================
# GET OTP
# ============================================================

def get_otp(account_name):

    accounts = load_accounts()

    if account_name not in accounts:
        return None, None

    secret = accounts[account_name]

    try:

        totp = pyotp.TOTP(secret)

        code = totp.now()

        remaining = 30 - (
            int(time.time()) % 30
        )

        return code, remaining

    except Exception as e:

        print(
            f"❌ OTP error for {account_name}: {e}"
        )

        return None, None


# ============================================================
# ACCOUNT KEYBOARD
# ============================================================

def account_keyboard():

    accounts = load_accounts()

    buttons = []

    for account_name in accounts:

        buttons.append([
            InlineKeyboardButton(
                f"🔐 {account_name}",
                callback_data=f"code:{account_name}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "➕ Add Account",
            callback_data="add_account"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "✏️ Rename Account",
            callback_data="rename_menu"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            "🗑 Delete Account",
            callback_data="delete_menu"
        )
    ])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# OTP KEYBOARD
# ============================================================

def otp_keyboard():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "🔄 Refresh Now",
                callback_data="refresh"
            )
        ],

        [
            InlineKeyboardButton(
                "⬅️ Back to Accounts",
                callback_data="back_accounts"
            )
        ]

    ])


# ============================================================
# RENAME KEYBOARD
# ============================================================

def rename_keyboard():

    accounts = load_accounts()

    buttons = []

    for account_name in accounts:

        buttons.append([
            InlineKeyboardButton(
                f"✏️ {account_name}",
                callback_data=f"rename:{account_name}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Back",
            callback_data="back_accounts"
        )
    ])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# DELETE KEYBOARD
# ============================================================

def delete_keyboard():

    accounts = load_accounts()

    buttons = []

    for account_name in accounts:

        buttons.append([
            InlineKeyboardButton(
                f"🗑 {account_name}",
                callback_data=f"delete:{account_name}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Back",
            callback_data="back_accounts"
        )
    ])

    return InlineKeyboardMarkup(buttons)


# ============================================================
# COUNTDOWN TASK MANAGEMENT
# ============================================================

COUNTDOWN_TASKS = {}


def stop_countdown(
    context,
    message_id
):

    task = COUNTDOWN_TASKS.pop(
        message_id,
        None
    )

    if task:
        task.cancel()


async def countdown_loop(
    context,
    chat_id,
    message_id,
    account_name
):

    try:

        # Wait one second before the first edit.
        await asyncio.sleep(1)

        while True:

            # Security check
            if chat_id is None:
                break

            code, remaining = get_otp(
                account_name
            )

            if not code:
                break

            text = (
                f"🔐 *{account_name}*\n\n"
                f"🔢 *OTP:* `{code}`\n\n"
                f"⏳ Changes in *{remaining}s*"
            )

            try:

                await context.bot.edit_message_text(

                    chat_id=chat_id,

                    message_id=message_id,

                    text=text,

                    parse_mode="Markdown",

                    reply_markup=otp_keyboard()

                )

            except BadRequest as e:

                if "Message is not modified" not in str(e):

                    print(
                        f"⚠️ Countdown edit error: {e}"
                    )

            except Exception as e:

                print(
                    f"⚠️ Countdown error: {e}"
                )

            await asyncio.sleep(1)

    except asyncio.CancelledError:

        pass

    except Exception as e:

        print(
            f"❌ Countdown task error: {e}"
        )


def start_countdown(
    context,
    chat_id,
    message_id,
    account_name
):

    stop_countdown(
        context,
        message_id
    )

    task = context.application.create_task(

        countdown_loop(

            context,

            chat_id,

            message_id,

            account_name

        )
    )

    COUNTDOWN_TASKS[message_id] = task


# ============================================================
# /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # SECURITY CHECK
    if not is_authorized(update):

        await deny_access(update)

        return

    text = (

        "🔐 *Khom Authenticator Bot*\n\n"

        "Your personal TOTP authenticator.\n\n"

        "Commands:\n"

        "• `/list` - Show accounts\n"

        "• `/code` - Show account selection\n"

        "• `/status` - Bot status\n\n"

        "Select an account below:"

    )

    await update.message.reply_text(

        text,

        parse_mode="Markdown",

        reply_markup=account_keyboard()

    )


# ============================================================
# /LIST
# ============================================================

async def list_accounts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # SECURITY CHECK
    if not is_authorized(update):

        await deny_access(update)

        return

    accounts = load_accounts()

    if not accounts:

        await update.message.reply_text(
            "📭 No accounts saved."
        )

        return

    text = (
        "🔐 *Your Authenticator Accounts*\n\n"
    )

    for account_name in accounts:

        text += f"• {account_name}\n"

    await update.message.reply_text(

        text,

        parse_mode="Markdown",

        reply_markup=account_keyboard()

    )


# ============================================================
# /CODE
# ============================================================

async def code_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # SECURITY CHECK
    if not is_authorized(update):

        await deny_access(update)

        return

    if not context.args:

        await update.message.reply_text(

            "🔐 Select an account:",

            reply_markup=account_keyboard()

        )

        return

    account_name = " ".join(
        context.args
    )

    accounts = load_accounts()

    if account_name not in accounts:

        await update.message.reply_text(

            f"❌ Account not found: "
            f"{account_name}"

        )

        return

    code, remaining = get_otp(
        account_name
    )

    if not code:

        await update.message.reply_text(
            "❌ Could not generate OTP."
        )

        return

    text = (

        f"🔐 *{account_name}*\n\n"

        f"🔢 *OTP:* `{code}`\n\n"

        f"⏳ Changes in *{remaining}s*"

    )

    message = await update.message.reply_text(

        text,

        parse_mode="Markdown",

        reply_markup=otp_keyboard()

    )

    start_countdown(

        context,

        message.chat_id,

        message.message_id,

        account_name

    )


# ============================================================
# /STATUS
# ============================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # SECURITY CHECK
    if not is_authorized(update):

        await deny_access(update)

        return

    accounts = load_accounts()

    text = (

        "🟢 *Bot Status*\n\n"

        "Bot: ONLINE\n"

        f"Accounts: {len(accounts)}\n"

        "TOTP Generator: READY\n"

        "Automatic Countdown: ON\n"

        "Security: 🔒 ENABLED\n"

    )

    await update.message.reply_text(

        text,

        parse_mode="Markdown"

    )


# ============================================================
# BUTTON HANDLER
# ============================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    # ========================================================
    # SECURITY CHECK
    # ========================================================

    if not is_authorized(update):

        await deny_access(update)

        return

    await query.answer()

    data = query.data

    # ========================================================
    # BACK TO ACCOUNTS
    # ========================================================

    if data == "back_accounts":

        stop_countdown(

            context,

            query.message.message_id

        )

        await query.edit_message_text(

            "🔐 *Select an account:*",

            parse_mode="Markdown",

            reply_markup=account_keyboard()

        )

        return

    # ========================================================
    # REFRESH
    # ========================================================

    if data == "refresh":

        old_text = query.message.text or ""

        account_name = None

        if old_text.startswith("🔐 *"):

            try:

                account_name = (
                    old_text
                    .split("🔐 *", 1)[1]
                    .split("*", 1)[0]
                )

            except Exception:

                account_name = None

        if not account_name:

            await query.answer(

                "Please select an account again.",

                show_alert=True

            )

            return

        code, remaining = get_otp(
            account_name
        )

        if not code:

            await query.answer(

                "Account not found.",

                show_alert=True

            )

            return

        text = (

            f"🔐 *{account_name}*\n\n"

            f"🔢 *OTP:* `{code}`\n\n"

            f"⏳ Changes in *{remaining}s*"

        )

        try:

            await query.edit_message_text(

                text,

                parse_mode="Markdown",

                reply_markup=otp_keyboard()

            )

        except BadRequest as e:

            if "Message is not modified" not in str(e):

                print(
                    f"⚠️ Refresh error: {e}"
                )

        start_countdown(

            context,

            query.message.chat_id,

            query.message.message_id,

            account_name

        )

        return

    # ========================================================
    # ADD ACCOUNT
    # ========================================================

    if data == "add_account":

        context.user_data[
            "adding_account"
        ] = True

        context.user_data.pop(
            "adding_secret",
            None
        )

        await query.edit_message_text(

            "➕ *Add New Account*\n\n"

            "Please send the account name.\n\n"

            "Example:\n"

            "`Demo`",

            parse_mode="Markdown"

        )

        return

    # ========================================================
    # RENAME MENU
    # ========================================================

    if data == "rename_menu":

        accounts = load_accounts()

        if not accounts:

            await query.edit_message_text(

                "📭 No accounts available.",

                reply_markup=account_keyboard()

            )

            return

        await query.edit_message_text(

            "✏️ *Select account to rename:*",

            parse_mode="Markdown",

            reply_markup=rename_keyboard()

        )

        return

    # ========================================================
    # DELETE MENU
    # ========================================================

    if data == "delete_menu":

        accounts = load_accounts()

        if not accounts:

            await query.edit_message_text(

                "📭 No accounts available.",

                reply_markup=account_keyboard()

            )

            return

        await query.edit_message_text(

            "🗑 *Select account to delete:*",

            parse_mode="Markdown",

            reply_markup=delete_keyboard()

        )

        return

    # ========================================================
    # SELECT ACCOUNT
    # ========================================================

    if data.startswith("code:"):

        account_name = data[5:]

        accounts = load_accounts()

        if account_name not in accounts:

            await query.answer(

                "❌ Account not found.",

                show_alert=True

            )

            return

        code, remaining = get_otp(
            account_name
        )

        if not code:

            await query.answer(

                "❌ Could not generate OTP.",

                show_alert=True

            )

            return

        text = (

            f"🔐 *{account_name}*\n\n"

            f"🔢 *OTP:* `{code}`\n\n"

            f"⏳ Changes in *{remaining}s*"

        )

        try:

            await query.edit_message_text(

                text,

                parse_mode="Markdown",

                reply_markup=otp_keyboard()

            )

        except BadRequest as e:

            if "Message is not modified" not in str(e):

                print(
                    f"⚠️ OTP display error: {e}"
                )

        start_countdown(

            context,

            query.message.chat_id,

            query.message.message_id,

            account_name

        )

        return

    # ========================================================
    # SELECT ACCOUNT TO RENAME
    # ========================================================

    if data.startswith("rename:"):

        account_name = data[7:]

        accounts = load_accounts()

        if account_name not in accounts:

            await query.answer(

                "❌ Account not found.",

                show_alert=True

            )

            return

        context.user_data[
            "renaming_account"
        ] = account_name

        await query.edit_message_text(

            f"✏️ *Rename Account*\n\n"

            f"Current name:\n"
            f"`{account_name}`\n\n"

            f"Please send the new name.",

            parse_mode="Markdown"

        )

        return

    # ========================================================
    # DELETE ACCOUNT
    # ========================================================

    if data.startswith("delete:"):

        account_name = data[7:]

        accounts = load_accounts()

        if account_name not in accounts:

            await query.answer(

                "❌ Account not found.",

                show_alert=True

            )

            return

        del accounts[account_name]

        if save_accounts(accounts):

            await query.edit_message_text(

                f"🗑 *Account Deleted*\n\n"

                f"`{account_name}` has been deleted.",

                parse_mode="Markdown",

                reply_markup=account_keyboard()

            )

        else:

            await query.edit_message_text(

                "❌ Could not save account changes."

            )

        return


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    # SECURITY CHECK
    if not is_authorized(update):

        await deny_access(update)

        return

    text = update.message.text.strip()

    # ========================================================
    # ADD ACCOUNT - ACCOUNT NAME
    # ========================================================

    if context.user_data.get(
        "adding_account"
    ):

        account_name = text

        accounts = load_accounts()

        if not account_name:

            await update.message.reply_text(

                "❌ Account name cannot be empty."

            )

            return

        if account_name in accounts:

            await update.message.reply_text(

                "❌ That account name already exists.\n"
                "Please send another name."

            )

            return

        context.user_data[
            "new_account_name"
        ] = account_name

        context.user_data[
            "adding_account"
        ] = False

        context.user_data[
            "adding_secret"
        ] = True

        await update.message.reply_text(

            "🔑 Now send the TOTP secret for "
            "this account.\n\n"

            "⚠️ Keep the secret private.\n"

            "It will be saved locally and will "
            "not be displayed."

        )

        return

    # ========================================================
    # ADD ACCOUNT - SECRET
    # ========================================================

    if context.user_data.get(
        "adding_secret"
    ):

        secret = (
            text
            .replace(" ", "")
            .replace("-", "")
            .upper()
        )

        account_name = context.user_data.get(
            "new_account_name"
        )

        if not account_name:

            context.user_data.clear()

            await update.message.reply_text(

                "❌ Add Account session expired."

            )

            return

        try:

            totp = pyotp.TOTP(secret)

            # Validate the secret.
            totp.now()

        except Exception:

            await update.message.reply_text(

                "❌ Invalid TOTP secret.\n\n"
                "Please send a valid secret."

            )

            return

        accounts = load_accounts()

        accounts[account_name] = secret

        if save_accounts(accounts):

            # Delete secret message from Telegram
            # if Telegram allows deletion.
            try:

                await update.message.delete()

            except Exception:

                pass

            context.user_data.clear()

            await update.effective_chat.send_message(

                f"✅ *Account Added*\n\n"

                f"Account: `{account_name}`\n\n"

                f"🔐 TOTP is ready.",

                parse_mode="Markdown",

                reply_markup=account_keyboard()

            )

        else:

            context.user_data.clear()

            await update.message.reply_text(

                "❌ Failed to save the account."

            )

        return

    # ========================================================
    # RENAME ACCOUNT
    # ========================================================

    if context.user_data.get(
        "renaming_account"
    ):

        old_name = context.user_data[
            "renaming_account"
        ]

        new_name = text

        accounts = load_accounts()

        if old_name not in accounts:

            context.user_data.clear()

            await update.message.reply_text(

                "❌ Original account no longer exists."

            )

            return

        if not new_name:

            await update.message.reply_text(

                "❌ New name cannot be empty."

            )

            return

        if (
            new_name in accounts
            and new_name != old_name
        ):

            await update.message.reply_text(

                "❌ That account name already exists.\n"
                "Please choose another name."

            )

            return

        secret = accounts.pop(
            old_name
        )

        accounts[new_name] = secret

        if save_accounts(accounts):

            context.user_data.clear()

            await update.message.reply_text(

                f"✅ *Account Renamed*\n\n"

                f"`{old_name}` → `{new_name}`",

                parse_mode="Markdown",

                reply_markup=account_keyboard()

            )

        else:

            await update.message.reply_text(

                "❌ Could not save the rename."

            )

        return

    # ========================================================
    # UNKNOWN TEXT
    # ========================================================

    await update.message.reply_text(

        "Please use the buttons or commands.\n\n"

        "🔐 `/list` - Accounts\n"
        "🔢 `/code` - Get OTP\n"
        "📊 `/status` - Status"

    )


# ============================================================
# MAIN
# ============================================================

def main():

    if BOT_TOKEN == "YOUR_REAL_BOT_TOKEN":

        print("")
        print(
            "❌ ERROR: Please put your real Telegram "
            "bot token inside BOT_TOKEN."
        )
        print("")

        return

    # ========================================================
    # CHECK TELEGRAM USER ID
    # ========================================================

    if ALLOWED_USER_ID == 123456789:

        print("")
        print(
            "⚠️ WARNING: You have not replaced "
            "ALLOWED_USER_ID yet."
        )
        print(
            "Please replace 123456789 with your "
            "real Telegram User ID."
        )
        print("")

        return

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ========================================================
    # COMMAND HANDLERS
    # ========================================================

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "list",
            list_accounts
        )
    )

    application.add_handler(
        CommandHandler(
            "code",
            code_command
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status
        )
    )

    # ========================================================
    # BUTTON HANDLER
    # ========================================================

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    # ========================================================
    # TEXT HANDLER
    # ========================================================

    application.add_handler(

        MessageHandler(

            filters.TEXT & ~filters.COMMAND,

            text_handler

        )

    )

    # ========================================================
    # START
    # ========================================================

    print("")
    print("==========================================")
    print("🔐 KHOM AUTHENTICATOR BOT")
    print("==========================================")
    print("🟢 Bot is starting...")
    print("🔐 TOTP Generator: READY")
    print("⏳ Automatic Countdown: ON")
    print("🔒 Access Control: ENABLED")
    print("👤 Authorized User ID: CONFIGURED")
    print("==========================================")
    print("")

    application.run_polling()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()