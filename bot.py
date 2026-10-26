import os
import json
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configurations
TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not TOKEN:
    logger.error("BOT_TOKEN environment variable is missing!")

# Data persistence files
SETTINGS_FILE = "settings.json"
GROUPS_FILE = "groups.json"

def load_data(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_data(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

def get_group_setting(chat_id):
    settings = load_data(SETTINGS_FILE)
    str_id = str(chat_id)
    if str_id not in settings:
        settings[str_id] = {
            "welcome_enabled": True,
            "welcome_message": "Hello {user}, Welcome to {group}! 🎉\nGlad to have you here.",
            "last_welcome_msg_id": None
        }
        save_data(SETTINGS_FILE, settings)
    return settings[str_id]

def update_group_setting(chat_id, key, value):
    settings = load_data(SETTINGS_FILE)
    str_id = str(chat_id)
    if str_id not in settings:
        get_group_setting(chat_id)
        settings = load_data(SETTINGS_FILE)
    settings[str_id][key] = value
    save_data(SETTINGS_FILE, settings)

def track_group(chat_id):
    groups = load_data(GROUPS_FILE)
    str_id = str(chat_id)
    if str_id not in groups:
        groups[str_id] = True
        save_data(GROUPS_FILE, groups)

# --- Telegram Bot Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I am your advanced Welcome Bot.\n"
        "Add me to your group and make me an Admin to get started!"
    )

async def new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    track_group(chat.id)
    
    settings = get_group_setting(chat.id)
    if not settings.get("welcome_enabled", True):
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue

        user_name = member.first_name
        group_name = chat.title
        
        custom_msg = settings.get("welcome_message", "Welcome {user} to {group}!")
        formatted_msg = custom_msg.replace("{user}", f"@{user_name}" if member.username else user_name).replace("{group}", group_name)

        # Delete previous welcome message to keep group clean
        last_msg_id = settings.get("last_welcome_msg_id")
        if last_msg_id:
            try:
                await context.bot.delete_message(chat_id=chat.id, message_id=last_msg_id)
            except Exception as e:
                logger.warning(f"Could not delete old welcome message: {e}")

        sent_msg = await chat.send_message(formatted_msg)
        update_group_setting(chat.id, "last_welcome_msg_id", sent_msg.message_id)

async def set_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Ye command sirf group me kaam karegi!")
        return

    user_member = await chat.get_member(update.effective_user.id)
    if user_member.status not in ["creator", "administrator"] and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⚠️ Sirf Group Admins hi welcome message change kar sakte hain!")
        return

    new_text = " ".join(context.args)
    if not new_text:
        await update.message.reply_text(
            "❌ Please welcome message saath me likhein!\n"
            "Example: `/setwelcome Hello {user}, Welcome to {group}!`"
        )
        return

    update_group_setting(chat.id, "welcome_message", new_text)
    await update.message.reply_text("✅ Welcome message successfully update ho gaya hai!")

async def toggle_welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("❌ Ye command sirf group me kaam karegi!")
        return

    user_member = await chat.get_member(update.effective_user.id)
    if user_member.status not in ["creator", "administrator"] and update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⚠️ Sirf Group Admins hi ise on/off kar sakte hain!")
        return

    if not context.args:
        await update.message.reply_text("Use: `/welcomebot on` ya `/welcomebot off`")
        return

    action = context.args[0].lower()
    if action == "on":
        update_group_setting(chat.id, "welcome_enabled", True)
        await update.message.reply_text("✅ Welcome messages are now **ENABLED**.")
    elif action == "off":
        update_group_setting(chat.id, "welcome_enabled", False)
        await update.message.reply_text("❌ Welcome messages are now **DISABLED**.")
    else:
        await update.message.reply_text("Invalid argument! Use `on` or `off`.")

async def owner_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⚠️ Ye command sirf bot owner ke liye hai!")
        return

    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_text("Usage: `/broadcast Aapka message yahan likhein`")
        return

    groups = load_data(GROUPS_FILE)
    success_count = 0
    fail_count = 0

    for chat_id_str in groups.keys():
        try:
            await context.bot.send_message(chat_id=int(chat_id_str), text=f"📢 **Broadcast from Owner:**\n\n{msg_text}", parse_mode="Markdown")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to broadcast to {chat_id_str}: {e}")
            fail_count += 1

    await update.message.reply_text(f"✅ Broadcast complete!\nSent: {success_count}\nFailed: {fail_count}")

async def owner_groups_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⚠️ Ye command sirf bot owner ke liye hai!")
        return

    groups = load_data(GROUPS_FILE)
    total_groups = len(groups)
    await update.message.reply_text(f"📊 Total active groups where bot is added: **{total_groups}**")

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_member_handler))
    application.add_handler(CommandHandler("setwelcome", set_welcome_command))
    application.add_handler(CommandHandler("welcomebot", toggle_welcome_command))
    application.add_handler(CommandHandler("broadcast", owner_broadcast))
    application.add_handler(CommandHandler("groups", owner_groups_list))

    PORT = int(os.environ.get("PORT", 10000))
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")

    if RENDER_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{RENDER_URL}/{TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == "__main__":
    main()
