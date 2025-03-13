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

# Save group chat data (ID & name) to JSON file
def save_groups(groups):
    with open("groups.json", "w") as file:
        json.dump({"groups": groups}, file, indent=4)

# Function to add a new group when the bot joins
def add_group(group_id, group_name):
    groups = load_groups()
    groups[str(group_id)] = group_name  # Store group ID as a string and its name
    save_groups(groups)

# Function to remove a group when the bot is kicked
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

# Store active trades
active_trades = {}

Tv = TvDatafeed()

# Function to fetch the current price of an asset
def get_price(asset):
    try:
        price = Tv.get_hist(asset, exchange="OANDA", interval=Interval.in_1_minute, n_bars=1)
        while price is None:
            price = Tv.get_hist(asset, exchange="OANDA", interval=Interval.in_1_minute, n_bars=1)
        return price['close'].iloc[-1]
    except Exception as e:
        return None

# Function to handle /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type
    if chat_type != "private":
        await update.message.reply_text("Please send /start in private chat to set up the bot.")
        return
    await send_admin_panel(update, context)

# Function to send the Admin Menu
async def send_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("New Trade", callback_data="new_trade"),
         InlineKeyboardButton("Active Trades", callback_data="active_trades")],
        [InlineKeyboardButton("Group List", callback_data="group_list"),
         InlineKeyboardButton("Exit", callback_data="exit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome, Admin! Choose an option:", reply_markup=reply_markup)

# Function to handle button clicks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "new_trade":
        await query.edit_message_text("Enter trade details: `Assets Entry Target 1 Target 2`", parse_mode="Markdown")
        context.user_data["awaiting_trade"] = True
    elif query.data == "active_trades":
        active_trades_list = "\n".join([f"{asset} | TP1: {tp1} | TP2: {tp2}" for asset, (_, tp1, tp2) in active_trades.items()])
        await query.edit_message_text(f"Active Trades:\n\n{active_trades_list}" if active_trades else "No active trades.")
    elif query.data == "group_list":
        groups = load_groups()
        group_list_text = "\n".join([f"{name} (ID: {gid})" for gid, name in groups.items()])
        await query.edit_message_text(f"Groups where bot is active:\n\n{group_list_text}" if groups else "Bot is not in any groups.")
    elif query.data == "exit":
        await query.edit_message_text("Exiting admin panel.")

def generate_random_code(length: int, Abc: bool) -> str:
    import random
    import string
    characters = string.digits  # Default to numbers only
    if Abc:
        characters += string.ascii_lowercase # Add uppercase and lowercase letters if Abc is True
    return ''.join(random.choice(characters) for _ in range(length))

def gen_img(trade_type,profit,Pair_name,leverage,exit_price,entry_price,):
    # Load the base template image
        img1 = "images/templates/img6.jpg"  # Path to your template image
        img = Image.open(img1)
        Binance = generate_random_code(9,False)

        # Create a drawing object
        draw = ImageDraw.Draw(img)
        referal_code = generate_random_code(6,True)
        # Load fonts
        font_large = ImageFont.truetype("dino.ttf", 26)  # Adjust size as needed
        font_medium = ImageFont.truetype("dino.ttf", 30)
        font_small = ImageFont.truetype("dino.ttf", 23)
        font_size1 = ImageFont.truetype("dino.ttf", 65)
        dot_font = ImageFont.truetype("ku.otf", 81)  # Font for the dot

        # Define colors
        text_color = "#FFFFFF"  # White
        short_color = "#EA506C"  # Red for Short
        long_color = "#2DC185"  # Green for Long

        # Determine trade type color
        type_color = short_color if trade_type.lower() == "short" else long_color

        # Function to draw text with special font for dot and auto alignment
        def draw_text_with_dot(draw, position, text, main_font, dot_font, fill):
            x, y = position
            main_ascent, main_descent = main_font.getmetrics()
            dot_ascent, dot_descent = dot_font.getmetrics()

            for char in text:
                # Use dot_font for '.' else use main_font
                if char == '.':
                    current_font = dot_font
                    # Align dot with the baseline of main font
                    y_offset = (main_ascent - dot_ascent)
                else:
                    current_font = main_font
                    y_offset = 0

                # Draw the character with aligned Y
                draw.text((x, y + y_offset), char, font=current_font, fill=fill)

                # Get width using textbbox
                bbox = draw.textbbox((x, y), char, font=current_font)
                width = bbox[2] - bbox[0]

                x += width  # Move x for next character

        # Draw static texts
        draw.text((280, 125), f"{Pair_name} Perpetual", font=font_small, fill=text_color)
        draw.text((104, 123), trade_type, font=ImageFont.truetype("dino.ttf", 25), fill=type_color)
        draw.text((213, 126), f"{leverage}x", font=font_small, fill=text_color)

        # Draw profit with auto-aligned dot
        draw_text_with_dot(draw, (104, 187), f"+ {profit}%", ImageFont.truetype("dino.ttf", 90), dot_font, long_color)

        # Draw entry and exit prices with auto-aligned dot
        entry_font = ImageFont.truetype("dino.ttf", 35)
        dot_entry_font = ImageFont.truetype("ku.otf", 35)

        draw_text_with_dot(draw, (284, 295), f"{entry_price}", entry_font, dot_entry_font, (219, 193, 70))
        draw_text_with_dot(draw, (284, 355), f"{exit_price}", entry_font, dot_entry_font, (229, 193, 70))

        # Draw random string
        draw.text((200, 438), Binance, font=ImageFont.truetype("dino.ttf", 35), fill=text_color)
        if img.mode == "RGBA":
            img = img.convert("RGB")
        # Save the modified image
        output_path = "images/output/output_img6.jpg"
        img.save(output_path)


# Function to capture user trade input
async def capture_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_trade"):
        trade_data = update.message.text.strip().split()
        if len(trade_data) != 4:
            await update.message.reply_text("Invalid format! Use: `Assets Price Target 1 Target 2`", parse_mode="Markdown")
            return

        asset, entry_price, take_profit1, take_profit2 = trade_data
        active_trades[asset.upper()] = (float(entry_price), float(take_profit1), float(take_profit2))
        context.user_data["awaiting_trade"] = False

        message = f"📢 **New Trade Alert** 📢\n\n🟡 **Asset:** {asset.upper()}\n🔹 **Entry Price:** {entry_price}\n🔹 **Take Profit 1:** {take_profit1}\n🔹 **Take Profit 2:** {take_profit2}"
        await send_message_to_all_groups(context, message)

# Function to send a message to all groups
async def send_message_to_all_groups(context: ContextTypes.DEFAULT_TYPE, message: str):
    
    for chat_id in group_chat_data:
        try:
            
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            
        except Exception as e:
            pass

# Function to welcome bot in group and store group chat ID and name
async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    chat_id = str(chat.id)  # Convert ID to string
    chat_name = chat.title  # Get group name

    groups = load_groups()  # Load existing groups

    if chat_id not in groups:
        groups[chat_id] = chat_name  # Store group ID and name
        save_groups(groups)  # Save updated group data

    await update.message.reply_text(f"Bot activated in **{chat_name}**! I will send alerts here.")

# Function to check if price reaches target levels
async def check_price(context: ContextTypes.DEFAULT_TYPE):
    for asset, (entry, tp1, tp2) in active_trades.items():
        current_price = get_price(asset)
        if current_price is None:
            continue  # Skip if price data is not available

        message = None
        if current_price >= tp1:
            message = f"🔔 **{asset}** has reached **Take Profit 1** at {tp1}!"
        if current_price >= tp2:
            message = f"🚀 **{asset}** has reached **Take Profit 2** at {tp2}! Trade closed."

        if message:
            await send_message_to_all_groups(context, message)
            for chat_id in group_chat_data:
                gen_img("Long",5,"EURUSD",20,1.03578,1.03689)
                img_path = "images/output/output_img6.jpg"
                await context.bot.send_photo(chat_id=chat_id,photo=open(img_path, 'rb'))
            if current_price >= tp2:  
                del active_trades[asset]  # Remove trade when TP2 is hit

# Main function to start the bot
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.job_queue.run_repeating(check_price, interval=5, first=5)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_trade))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_trade))

    application.run_polling()

if __name__ == "__main__":
    main()
