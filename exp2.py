import json
import os
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from tvDatafeed import TvDatafeed, Interval

# Telegram Bot Token
BOT_TOKEN = "7722341758:AAGL41u5KZz5_KKccCOM2t5qau_nyXfx4uo"

# Initialize Datafeed
Tv = TvDatafeed()

# Load group data
def load_groups():
    try:
        with open("groups.json", "r") as file:
            data = json.load(file)
            return data["groups"] if isinstance(data.get("groups"), dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_groups(groups):
    with open("groups.json", "w") as file:
        json.dump({"groups": groups}, file, indent=4)

# Add group with serial number
def add_group(group_id, group_name):
    groups = load_groups()
    serial_no = str(len(groups) + 1)  # Assign the next serial number
    groups[serial_no] = {"id": str(group_id), "name": group_name}
    save_groups(groups)

# Remove group by ID
async def group_removed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat.id)
    groups = load_groups()
    for sn, details in list(groups.items()):
        if details["id"] == chat_id:
            del groups[sn]
            save_groups(groups)
            break

# Price checking
def get_price(asset):
    try:
        data = Tv.get_hist(asset, exchange="OANDA", interval=Interval.in_1_minute, n_bars=1)
        return data['close'].iloc[-1]
    except Exception:
        return None

# Image generation
def gen_img(trade_type, profit, pair_name, leverage, exit_price, entry_price):
    try:
        img = Image.open("images/templates/img6.jpg").convert('RGB')
        draw = ImageDraw.Draw(img)

        # Font setup
        font_small = ImageFont.truetype("dino.ttf", 23)
        font_med = ImageFont.truetype("dino.ttf", 25)
        font_large = ImageFont.truetype("dino.ttf", 90)
        dot_font = ImageFont.truetype("ku.otf", 81)

        # Colors
        text_color = "#FFFFFF"
        type_color = "#EA506C" if trade_type.lower() == "short" else "#2DC185"

        # Draw trade info
        draw.text((104, 123), trade_type, font=font_med, fill=type_color)
        draw.text((213, 126), f"{leverage}x", font=font_small, fill=text_color)
        draw.text((280, 125), f"{pair_name} Perpetual", font=font_small, fill=text_color)

        # Draw profit
        x = 104
        y = 187
        for char in f"+{profit:.2f}%":
            draw.text((x, y), char, font=font_large if char != '.' else dot_font, fill=type_color)
            x += font_large.getsize(char)[0]

        # Draw prices
        def draw_price(price, y_pos):
            x = 284
            for char in f"{price:.5f}":
                draw.text((x, y_pos), char, font=ImageFont.truetype("dino.ttf", 35), fill="#EBCB62")
                x += 20

        draw_price(entry_price, 295)
        draw_price(exit_price, 355)

        output_path = "images/output/output_img6.jpg"
        img.save(output_path)
        return output_path
    except Exception as e:
        print(f"Image error: {e}")
        return None

# Trade handling
active_trades = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_admin_panel(update, context)

async def send_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("New Trade", callback_data="new_trade"),
         InlineKeyboardButton("Active Trades", callback_data="active_trades")],
        [InlineKeyboardButton("Group List", callback_data="group_list"),
         InlineKeyboardButton("Exit", callback_data="exit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome, Admin! Choose an option:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "group_list":
        groups = load_groups()
        if not groups:
            await query.edit_message_text("No active groups.")
            return

        group_list = [f"Serial: {sn} | Name: {details['name']} (ID: {details['id']})" for sn, details in groups.items()]
        await query.edit_message_text("Active Groups:\n\n" + "\n".join(group_list))

async def capture_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        asset, entry, tp1, tp2, leverage, serial_nos = update.message.text.strip().split()
        entry, tp1, tp2, leverage = float(entry), float(tp1), float(tp2), int(leverage)

        active_trades[asset.upper()] = {
            'entry': entry, 'tp1': tp1, 'tp2': tp2,
            'leverage': leverage, 'serial_nos': serial_nos.split(','),
            'notified_tp1': False, 'notified_tp2': False,
            'type': "Long" if tp1 > entry else "Short"
        }

        message = f"📢 **New Trade Alert**\n🟡 {asset.upper()}\n🔹 Entry: {entry}\n🔹 TP1: {tp1}\n🔹 TP2: {tp2}\n🔹 Leverage: {leverage}x"
        await send_to_groups(context, message, serial_nos)

    except Exception:
        await update.message.reply_text("Invalid format! Use:\n`Asset Entry TP1 TP2 Leverage SerialNo`")

async def send_to_groups(context, message, serial_nos):
    groups = load_groups()
    if "all" in serial_nos.lower():
        targets = groups.values()
    else:
        targets = [groups[sn] for sn in serial_nos.split(',') if sn in groups]

    for group in targets:
        try:
            await context.bot.send_message(group["id"], message, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send to {group['id']}: {e}")

async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    add_group(chat.id, chat.title)
    await update.message.reply_text(f"Bot activated in {chat.title}!")

def main():
    os.makedirs("images/output", exist_ok=True)
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_trade))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, group_removed))
    
    application.run_polling()

if __name__ == "__main__":
    main()
