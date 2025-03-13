import json
import os
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,CallbackContext,
    filters, ContextTypes
)
from tvDatafeed import TvDatafeed, Interval

# Telegram Bot Token (replace with your token or use an environment variable)
BOT_TOKEN = "7722341758:AAGL41u5KZz5_KKccCOM2t5qau_nyXfx4uo"

# Channel IDs to send notifications to (update these with your channel usernames or IDs)
CHANNEL_IDS = ["@your_channel_username", "-1001234567890"]

# Initialize Datafeed
Tv = TvDatafeed()

# -------------------- Group Management --------------------
def load_groups(filename="groups.json"):
    """Loads the group data from a JSON file and ensures proper formatting."""
    default_data = {"groups": {}, "next_serial": 1}
    
    if not os.path.exists(filename):
        return default_data
    
    with open(filename, "r", encoding="utf-8") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return default_data

    if "groups" not in data:
        data["groups"] = {}
    if "next_serial" not in data:
        data["next_serial"] = max([info["serial"] for info in data["groups"].values()], default=0) + 1
    
    return data

def save_groups(data):
    with open("groups.json", "w") as file:
        json.dump(data, file, indent=4)

def add_group(group_id, group_name):
    data = load_groups()
    if str(group_id) not in data["groups"]:
        data["groups"][str(group_id)] = {
            "name": group_name,
            "serial": data["next_serial"]
        }
        data["next_serial"] += 1
        save_groups(data)

async def group_removed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_groups()
    chat_id = str(update.message.chat.id)
    if chat_id in data["groups"]:
        del data["groups"][chat_id]
        save_groups(data)

# -------------------- Price Checking --------------------
def get_price(asset):
    try:
        data = Tv.get_hist(asset, exchange="OANDA", interval=Interval.in_1_minute, n_bars=1)
        return data['close'].iloc[-1]
    except Exception:
        return None

# -------------------- Image Generation --------------------
def gen_img(trade_type, profit, pair_name, leverage, exit_price, entry_price, referral_code, image_number,target_number):
    try:
        templates = {
            1: ("images/templates/img6.jpg", "output_img6.jpg"),
            2: ("images/templates/img8.jpg", "output_img8.jpg"),
            3: ("images/templates/img9.jpg", "output_img9.jpg")
        }
        target1_path = "images/templates/target1.jpg"
        target2_path = "images/templates/target2.jpg"
        Binance = referral_code
        template_path, output_name = templates[image_number]
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)
        target_width = 250  # Adjust to your needs
        target_height = 250  # Adjust to your needs
        
        if target_number == 1:
            target_img = Image.open(target1_path)
            target_img = target_img.resize((target_width, target_height))  # Resize
            img.paste(target_img, (750, 270), target_img)  # Paste at position
            
        elif target_number == 2:
            target_img = Image.open(target2_path)
            target_img = target_img.resize((target_width, target_height))  # Resize
            img.paste(target_img, (750, 270), target_img)  # Same position or adjust
        if image_number not in templates:
            return None
            
        # Use the referral code (e.g., Binance referral code)
        
        # Load fonts (ensure these files exist in your working directory)
        font_large = ImageFont.truetype("dino.ttf", 26)
        font_medium = ImageFont.truetype("dino.ttf", 30)
        font_small = ImageFont.truetype("dino.ttf", 23)
        font_size1 = ImageFont.truetype("dino.ttf", 65)
        dot_font = ImageFont.truetype("ku.otf", 81)

        # Define colors
        text_color = "#FFFFFF"  # White
        short_color = "#EA506C"  # Red for Short
        long_color = "#2DC185"   # Green for Long

        # Determine trade type color
        type_color = short_color if trade_type.lower() == "short" else long_color

        # Function to draw text with special dot font and auto alignment
        def draw_text_with_dot(draw, position, text, main_font, dot_font, fill):
            x, y = position
            main_ascent, main_descent = main_font.getmetrics()
            dot_ascent, dot_descent = dot_font.getmetrics()

            for char in text:
                if char == '.':
                    current_font = dot_font
                    y_offset = (main_ascent - dot_ascent)
                else:
                    current_font = main_font
                    y_offset = 0

                draw.text((x, y + y_offset), char, font=current_font, fill=fill)
                bbox = draw.textbbox((x, y), char, font=current_font)
                width = bbox[2] - bbox[0]
                x += width

        # Draw static texts on the image
        draw.text((280, 125), f"{pair_name} Perpetual", font=font_small, fill=text_color)
        draw.text((104, 123), trade_type, font=ImageFont.truetype("dino.ttf", 25), fill=type_color)
        draw.text((213, 126), f"{leverage}x", font=font_small, fill=text_color)

        # Draw profit with auto-aligned dot
        draw_text_with_dot(draw, (104, 187), f"+ {profit}%", ImageFont.truetype("dino.ttf", 90), dot_font, long_color)

        # Draw entry and exit prices with auto-aligned dot
        entry_font = ImageFont.truetype("dino.ttf", 35)
        dot_entry_font = ImageFont.truetype("ku.otf", 35)
        draw_text_with_dot(draw, (284, 295), f"{entry_price}", entry_font, dot_entry_font, (219, 193, 70))
        draw_text_with_dot(draw, (284, 355), f"{exit_price}", entry_font, dot_entry_font, (229, 193, 70))

        # Draw referral code
        draw.text((200, 438), Binance, font=ImageFont.truetype("dino.ttf", 35), fill=text_color)
        
        if img.mode == "RGBA":
            img = img.convert("RGB")
        output_path = f"images/output/{output_name}"
        img.save(output_path)
        return output_path
    except Exception as e:
        print(f"Image error: {e}")
        return None



# -------------------- Trade Handling --------------------
active_trades = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_type = update.message.chat.type
    if chat_type != "private":
        await update.message.reply_text("Please send /start in private chat.")
        return
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

    if query.data == "new_trade":
        data = load_groups()
        groups = data.get("groups", {})
        
        if not groups:
            await query.edit_message_text("No groups available. Please add groups first.")
            return
            
        group_list = "\n".join([f"{info['serial']}) {info['name']}" for gid, info in groups.items()])
        image_list = "1. Image 1\n2. Image 2\n3. Image 3"
        message = (
            f"Available Groups:\n{group_list}\n\n"
            f"Available Images:\n{image_list}\n\n"
            "Enter trade: `Asset Entry TP1 TP2 Leverage GroupNumber ImageNumber ReferralCode`\n"
            "Example: `EURUSD 1.08 1.09 1.10 20 1 2 ref123`"
        )
        await query.edit_message_text(message, parse_mode="Markdown")
        context.user_data["awaiting_trade"] = True

    elif query.data == "active_trades":
        if not active_trades:
            await query.edit_message_text("No active trades.")
            return
        trades_list = []
        for asset, details in active_trades.items():
            trades_list.append(
                f"{asset} | {details['type']} | Entry: {details['entry']} | "
                f"TP1: {details['tp1']} | TP2: {details['tp2']} | Lev: {details['leverage']}x"
            )
        await query.edit_message_text("Active Trades:\n\n" + "\n".join(trades_list))
    
    elif query.data == "group_list":
        data = load_groups()
        groups = data.get("groups", {})
        
        if not groups:
            await query.edit_message_text("No active groups.")
            return

        group_list = "\n".join([f"{info['serial']}) {info['name']}" for gid, info in groups.items()])
        await query.edit_message_text("Active Groups:\n\n" + group_list)
    
    elif query.data == "exit":
        await query.edit_message_text("Exiting admin panel.")

async def capture_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat  # Get chat object
    chat_type = chat.type  # Get chat type
    chat_id = chat.id
    chat_title = chat.title if chat.title else "Private Chat"

    # Print chat details
    print(f"📢 Chat Type: {chat_type}, Title: {chat_title}, ID: {chat_id}")

    # Store group/channel info if it's not a private chat
    if chat_type in ["channel"]:
        add_group(chat_id, chat_title)
    if context.user_data.get("awaiting_trade"):
        try:
            parts = update.message.text.strip().split()
            if len(parts) != 8:
                raise ValueError("Invalid number of parameters.")
                
            asset, entry, tp1, tp2, leverage, group_serial, image_number, referral_code = parts
            
            entry = float(entry)
            tp1 = float(tp1)
            tp2 = float(tp2)
            leverage = int(leverage)
            group_serial = int(group_serial)
            image_number = int(image_number)

            active_trades[asset.upper()] = {
                'entry': entry,
                'tp1': tp1,
                'tp2': tp2,
                'leverage': leverage,
                'group_serial': group_serial,
                'image_number': image_number,
                'referral': referral_code,
                'notified_tp1': False,
                'notified_tp2': False,
                'type': "Long" if tp1 > entry else "Short"
            }
            
            await send_to_groups(
                context,
                f"📢 New Trade: {asset.upper()}\nEntry: {entry}\nTP1: {tp1}\nTP2: {tp2}\nLeverage: {leverage}x",
                group_serial,
                asset,
                None,
                entry,
                entry,  # For a new trade, the initial price equals the entry price.
                image_number,
                referral_code
            )
            
            context.user_data["awaiting_trade"] = False
            
        except Exception as e:
            await update.message.reply_text(
                "Invalid format! Use:\n"
                "`Asset Entry TP1 TP2 Leverage GroupNumber ImageNumber ReferralCode`\n"
                "Example: `EURUSD 1.08 1.09 1.10 20 1 2 ref123`"
            )

async def send_to_groups(context, message, group_serial, asset, leverage, entry_price, exit_price, image_number=None, referral_code=None):
    data = load_groups()
    groups = data["groups"]
    
    # Find target groups by matching the serial number
    targets = [gid for gid, info in groups.items() if info['serial'] == group_serial]
    
    # Send to Groups
    for chat_id in targets:
        try:
            await context.bot.send_message(chat_id, message, parse_mode="Markdown")
            if leverage is not None:
                profit =  ((exit_price - entry_price) / entry_price) * 100 * leverage
                img_path = gen_img(
                    "Long" if exit_price > entry_price else "Short",
                   abs(round(profit,2)),
                    asset.upper(),
                    leverage,
                    exit_price,
                    entry_price,
                    referral_code,
                    image_number
                )
                if img_path:
                    await context.bot.send_photo(chat_id, open(img_path, 'rb'))
        except Exception as e:
            print(f"Failed to send to group {chat_id}: {e}")
    
    

async def check_price(context: ContextTypes.DEFAULT_TYPE):
    for asset, trade in list(active_trades.items()):
        current_price = get_price(asset)
        if current_price is None:
            continue

        entry = trade['entry']
        tp1 = trade['tp1']
        tp2 = trade['tp2']
        leverage = trade['leverage']
        group_serial = trade['group_serial']
        trade_type = trade['type']
        image_number = trade['image_number']
        referral_code = trade['referral']

        if trade_type == "Long":
            if current_price >= tp1 and not trade['notified_tp1']:
                await send_to_groups(
                    context,
                    f"🎯 TP1 Reached for {asset} at {tp1}",
                    group_serial,
                    asset,
                    leverage,
                    entry,
                    tp1,
                    image_number,
                    referral_code
                )
                active_trades[asset]['notified_tp1'] = True
            
            if current_price >= tp2 and not trade['notified_tp2']:
                await send_to_groups(
                    context,
                    f"🚀 TP2 Reached for {asset} at {tp2}",
                    group_serial,
                    asset,
                    leverage,
                    entry,
                    tp2,
                    image_number,
                    referral_code
                )
                del active_trades[asset]

        else:  # Short trade
            if current_price <= tp1 and not trade['notified_tp1']:
                await send_to_groups(
                    context,
                    f"🎯 TP1 Reached for {asset} at {tp1}",
                    group_serial,
                    asset,
                    leverage,
                    entry,
                    tp1,
                    image_number,
                    referral_code
                )
                active_trades[asset]['notified_tp1'] = True
            
            if current_price <= tp2 and not trade['notified_tp2']:
                await send_to_groups(
                    context,
                    f"🚀 TP2 Reached for {asset} at {tp2}",
                    group_serial,
                    asset,
                    leverage,
                    entry,
                    tp2,
                    image_number,
                    referral_code
                )
                del active_trades[asset]

async def group_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    add_group(chat.id, chat.title)
    await update.message.reply_text(f"🤖 Bot activated in {chat.title}!")






def main():
    os.makedirs("images/output", exist_ok=True)
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.job_queue.run_repeating(check_price, interval=5)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_trade))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, group_removed))



    application.run_polling()

if __name__ == "__main__":
    main()
