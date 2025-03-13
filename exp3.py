import json
import time
import io
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)
from tvDatafeed import TvDatafeed, Interval

# Telegram Bot Token
BOT_TOKEN = "7722341758:AAGL41u5KZz5_KKccCOM2t5qau_nyXfx4uo"

# Load group chat data from JSON file
def load_groups():
    try:
        with open("groups.json", "r") as file:
            data = json.load(file)
            return data.get("groups", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

# Save group chat data (with serial numbers) to JSON file
def save_groups(groups):
    with open("groups.json", "w") as file:
        json.dump({"groups": groups}, file, indent=4)

# Function to add a new group when the bot joins
def add_group(group_id, group_name):
    groups = load_groups()
    
    # Assign a serial number if the group is new
    if str(group_id) not in groups:
        serial_no = len(groups) + 1  # Assign a new serial number
        groups[str(group_id)] = {"name": group_name, "serial_no": serial_no}
        save_groups(groups)

# Function to remove a group when the bot is removed
async def group_removed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    chat_id = str(chat.id)

    groups = load_groups()
    if chat_id in groups:
        del groups[chat_id]  # Remove group from JSON
        save_groups(groups)  # Save updated data
        print(f"Bot removed from {chat.title}, deleting from JSON.")

# Initialize group storage
group_chat_data = load_groups()

# Function to send a message to a specific group by serial number
async def send_message_to_group_by_serial(context: ContextTypes.DEFAULT_TYPE, serial_no, message):
    groups = load_groups()
    
    for chat_id, details in groups.items():
        if details["serial_no"] == serial_no:
            try:
                await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
                return f"✅ Message sent to {details['name']} (Serial No: {serial_no})"
            except Exception as e:
                return f"⚠️ Failed to send message to {details['name']}: {str(e)}"
    
    return f"❌ No group found with Serial No: {serial_no}"

# Function to handle admin commands (for testing)
async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    
    if len(args) < 2:
        await update.message.reply_text("Usage: /sendto <Serial_No> <Message>")
        return
    
    try:
        serial_no = int(args[1])
        message = " ".join(args[2:])
        response = await send_message_to_group_by_serial(context, serial_no, message)
        await update.message.reply_text(response)
    except ValueError:
        await update.message.reply_text("❌ Invalid Serial Number. Please enter a valid number.")

# Function to list all groups with serial numbers
async def list_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = load_groups()
    
    if not groups:
        await update.message.reply_text("No groups found.")
        return
    
    group_list = "\n".join([f"{details['serial_no']}. {details['name']} (ID: {chat_id})" for chat_id, details in groups.items()])
    await update.message.reply_text(f"📜 **Groups List:**\n\n{group_list}", parse_mode="Markdown")

# Function to welcome bot in group and store group chat ID and name
async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    chat_id = str(chat.id)  # Convert ID to string
    chat_name = chat.title  # Get group name

    add_group(chat_id, chat_name)  # Save group with serial number

    await update.message.reply_text(f"✅ Bot activated in **{chat_name}**! (Serial No: {len(load_groups())})")

# Main function to start the bot
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", list_groups))  # List all groups
    application.add_handler(CommandHandler("sendto", send_to_group))  # Send to a group by serial no

    # Group Events
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    
    application.run_polling()

if __name__ == "__main__":
    main()
