import json
import os
from telegram import Bot
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,CallbackContext,
    filters, ContextTypes
)
from tvDatafeed import TvDatafeed, Interval
import time
from datetime import timedelta

# Telegram Bot Token (replace with your token or use an environment variable)
BOT_TOKEN = "7722341758:AAGL41u5KZz5_KKccCOM2t5qau_nyXfx4uo"

def format_time_difference(seconds):
    delta = timedelta(seconds=int(seconds))
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    if days > 0:
        return f"{days} days {hours} hours {minutes} min"
    elif hours > 0:
        return f"{hours} hours {minutes} min"
    else:
        return f"{minutes} min"

Checking_channel_id = ["-1002262989255"]

# Initialize Datafeed
Tv = TvDatafeed()

# -------------------- Channel Management --------------------
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
        while data is None:
            data = Tv.get_hist(asset, exchange="OANDA", interval=Interval.in_1_minute, n_bars=1)
        return data['close'].iloc[-1]
    except Exception:
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
            
        group_list = "\n1) Absolute Future\n2) Conquered\n3) Bitcoin Cartel"
        image_list = "1. Image 1\n2. Image 2\n3. Image 3"
        message = (
            f"Available Groups:\n{group_list}\n\n"
            f"Available Images:\n{image_list}\n\n"
            "Enter trade: `Asset Entry TP1 TP2 TP3 TP4 TP5 TP6 SL leverage Group Number Image Number Referral Code`\n"
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
    # if chat_type in ["channel"]:
    #     add_group(chat_id, chat_title)
    if chat_type in ["channel"] and context.user_data.get("awaiting_trade"):
        context.user_data["awaiting_trade"] = False
        
    if context.user_data.get("awaiting_trade"):
        
        parts = update.message.text.strip().split()
        
            
        asset, entry, tp1, tp2,tp3,tp4,tp5,tp6,sl,leverage, group_serial, image_number, referral_code = parts
        
        entry = float(entry)
        tp1 = float(tp1)
        tp2 = float(tp2)
        tp3 = float(tp3)
        tp4 = float(tp4)
        tp5 = float(tp5)
        tp6 = float(tp6)
        sl = float(sl)
        leverage = int(leverage)
        group_serial = int(group_serial)
        image_number = int(image_number)
        trade_type = "LONG" if tp1 > entry else "SHORT"
        active_trades[asset.upper()] = {
            'entry': entry,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'tp4': tp4,
            'tp5': tp5,
            'tp6': tp6,
            'sl' : sl,
            'leverage': leverage,
            'group_serial': group_serial,
            'image_number': image_number,
            'referral': referral_code,
            'notified_tp1': False,
            'notified_tp2': False,
            'notified_tp3': False,
            'notified_tp4': False,
            'notified_tp5': False,
            'notified_tp6': False,
            'notified_sl': False,
            'type': "Long" if tp1 > entry else "Short",
            'entry_time': time.time()  # Store timestamp of trade entry
        }
        await send_entery_message(update,context,group_serial,asset,trade_type,entry,[tp1,tp2,tp3,tp4,tp5,tp6],sl,leverage)
        
        
        context.user_data["awaiting_trade"] = False
            
# -------------------- Image Generation --------------------
def gen_img(trade_type, profit, pair_name, leverage, exit_price, entry_price, referral_code, image_number,target_number,group_number):
    try:
        templates = {
            1: ("images/templates/img6.jpg", "output_img6.jpg"),
            2: ("images/templates/img8.jpg", "output_img8.jpg"),
            3: ("images/templates/img9.jpg", "output_img9.jpg")
        }

        target_paths = {
            1:{
                1: "images/templates/target_absolutes.jpg",
                2: "images/templates/target_absolutes.jpg",
                3: "images/templates/target_absolutes.jpg",
                4: "images/templates/target_absolutes.jpg",
                5: "images/templates/target_absolutes.jpg",
                6: "images/templates/target_absolutes.jpg"
            },
            2:{
                1: "images/templates/target1.jpg",
                2: "images/templates/target2.jpg",
                3: "images/templates/target3.jpg",
                4: "images/templates/target4.jpg",
                5: "images/templates/target5.jpg",
                6: "images/templates/target6.jpg"
            }
        }
        target_path = target_paths[group_number][target_number]
        Binance = referral_code
        template_path, output_name = templates[image_number]
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)
        target_width = 250  # Adjust to your needs
        target_height = 250  # Adjust to your needs
        
        
        target_img = Image.open(target_path)
        target_img = target_img.resize((target_width, target_height))  # Resize
        img.paste(target_img, (750, 270), target_img)  # Paste at position
            
        
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


        # Dictionary to store sent messages (You can use a database instead)


sent_messages = {}

async def send_entery_message(update: Update, context: ContextTypes.DEFAULT_TYPE, group_no: int, pair_name: str, trade_type, entery_price, tp_lst, sl, leverage):
    global bot
    bot = Bot(BOT_TOKEN)

    if group_no == 1:
        range_mapping = {
            "LONG": "Buying",
            "SHORT": "Selling"
        }
        message = f"Demo Trade Opportunity\n=========================\n\nMy Coin: ${pair_name}/USDT\nLooking for {trade_type.upper()}\n\n{entery_price} Will Be My {range_mapping[trade_type.upper()]} Range.\n\nExpected Targets: {tp_lst[0]} - {tp_lst[1]} - {tp_lst[2]} - {tp_lst[3]} - {tp_lst[4]} - {tp_lst[5]}\n\nI Will Set: {sl}\n°°°°°°°°°°°°°° As my stoploss"

        with open('absolute.mp4', 'rb') as f:
            sent_message = await bot.send_video(chat_id=Checking_channel_id[0], video=f, caption=message)
        
        # Store message_id with trade details
        sent_messages[sent_message.message_id] = {
            "pair_name": pair_name,
            "trade_type": trade_type.upper(),
            "entry_price": entery_price,
            "stop_loss": sl
        }

    elif group_no == 2:
        tag = "🟢 LONG" if trade_type.upper() == "LONG" else "🔴 SELL"
        message = f"🏆Crypto Conquered Signals©\n〰〰〰〰〰〰〰〰〰〰〰\n\n🔘 Coin : #{pair_name}/USDT 🔘\n\n{tag}\n\n🔺Entry🔻: {entery_price}\n\n⭐️ Target: {tp_lst[0]} - {tp_lst[1]} - {tp_lst[2]} - {tp_lst[3]} - {tp_lst[4]} - {tp_lst[5]}\n\n♦️ StopLoss : {sl}\n\n🔱 Leverage: {leverage}x"

        sent_message = await context.bot.send_message(chat_id=Checking_channel_id[0], text=message)

        # Store message_id with trade details
        sent_messages[sent_message.message_id] = {
            "pair_name": pair_name,
            "trade_type": trade_type.upper(),
            "entry_price": entery_price,
            "stop_loss": sl
        }
    elif group_no == 3:
        tag = "LONG" if trade_type.upper() == "LONG" else "SELL"
        message = f"""
••Bitcoin Cartel Free Signal••

🎖Coin: {pair_name}/USDT

🔸Leverage: {leverage}x🔸

Signal Direction:- {tag}

〽️Entries: {entery_price}

🎯 Targets 🎯
{tp_lst[0]} - {tp_lst[1]} - {tp_lst[2]} - {tp_lst[3]} - {tp_lst[4]} - {tp_lst[5]}

➖Stoploss: {sl} (Mandatory)
"""
        sent_message = await context.bot.send_message(chat_id=Checking_channel_id[0], text=message)

        # Store message_id with trade details
        sent_messages[sent_message.message_id] = {
            "pair_name": pair_name,
            "trade_type": trade_type.upper(),
            "entry_price": entery_price,
            "stop_loss": sl
        }
    print("Stored Messages:", sent_messages)  # Debugging: Print stored messages

async def send_tp_message(update: Update, context: ContextTypes.DEFAULT_TYPE, TP_number: int, asset, exit_price,formated_time):
    global sent_messages  # Access stored message IDs

    # Fetch trade details from active_trades
    trade_type = active_trades[asset]['type']
    leverage = active_trades[asset]['leverage']
    group_serial = active_trades[asset]['group_serial']
    image_number = active_trades[asset]['image_number']
    referral_code = active_trades[asset]['referral']
    entry_price = active_trades[asset]['entry']
    trade_data = active_trades[asset]

    # Calculate profit percentage
    profit = ((exit_price - entry_price) / entry_price) * 100 * leverage
    profit = abs(round(profit, 2))

    # Generate target emoji (e.g., "1️⃣" for TP1, "1️⃣,2️⃣" for TP2, etc.)
    tp_emoji = " ".join([f"{i}️⃣" for i in range(1, TP_number + 1)])
    tp_values = [trade_data[f'tp{i}'] for i in range(1, TP_number + 1) if f'tp{i}' in trade_data]
    target_lines = "\n".join([f"Target: {i} :- {tp_values[i-1]} ✅" for i in range(1, len(tp_values) + 1)])
    # Generate image
    output_path = gen_img(trade_type, profit, asset, leverage, exit_price, entry_price, referral_code, image_number, TP_number, group_serial)

    # Select message format based on group serial
    if group_serial == 1:
        message = f"""••• Demo Trade Updates •••

🎖| ${asset}/USDT 
⭐️| {tp_emoji} Targets Done
🚀| {profit}% of Absolute Profits
💎| Within {formated_time} of holding this

⚜️Absolute VIP✔️: @absovip 😎"""
    
    elif group_serial == 2:
        message = f"""🔥 #{asset}/USDT   #Conquered💪
        
🤑Achieved: {profit}% Profit in {formated_time}

🏹 Targets. {tp_emoji}, Done ✅

🏆VIP: @CryptoCoach9"""
    
    elif group_serial == 3:
        message = f"""
#{asset}/USDT ({trade_type})🚀

{target_lines}

Target Achieved In {formated_time}

📈 {profit}% Profit ({leverage}x) 📈
"""

        # Send **only a message** (no image) for Group 3, with trade message tagging
        await context.bot.send_message(
            chat_id=Checking_channel_id[0],
            text=message,
            reply_to_message_id=reply_to_message_id  # Tag previous trade message
        )
        return  # Exit function to prevent image sending

    # Get previous trade message ID (if available)
    reply_to_message_id = None
    for msg_id, details in sent_messages.items():
        if details["pair_name"] == asset and details["entry_price"] == entry_price:
            reply_to_message_id = msg_id
            break

    # Send image with caption, tagging previous trade if available
    with open(output_path, 'rb') as photo:
        await context.bot.send_photo(
            chat_id=Checking_channel_id[0],
            photo=photo,
            caption=message,
            reply_to_message_id=reply_to_message_id  # Tag previous trade message
        )

async def check_target(context: ContextTypes.DEFAULT_TYPE):
    """
    Active Trade Dictonoary looks like this
    active_trades[asset.upper()] = {
            'entry': entry,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'tp4': tp4,
            'tp5': tp5,
            'tp6': tp6,
            'sl' : sl,
            'leverage': leverage,
            'group_serial': group_serial,
            'image_number': image_number,
            'referral': referral_code,
            'notified_tp1': False,
            'notified_tp2': False,
            'notified_tp3': False,
            'notified_tp4': False,
            'notified_tp5': False,
            'notified_tp6': False,
            'notified_sl': False,
            'type': "Long" if tp1 > entry else "Short"
        }
        And this how you can get the current Price
        price = get_price(asset)
    """
    for asset in list(active_trades.keys()):
        trade = active_trades[asset]
        price = get_price(asset)
        trade_type = trade['type']
        sl = trade['sl']
        
        # Check if SL is hit
        sl_hit = False
        if trade_type == "Long":
            if price <= sl:
                sl_hit = True
        else:  # Short
            if price >= sl:
                sl_hit = True
        
        if sl_hit:
            # Send SL notification and remove the trade
            del active_trades[asset]
            continue  # Proceed to next asset
        
        # Check each TP in order from 1 to 6
        for tp_num in range(1, 7):
            tp_key = f'tp{tp_num}'
            notified_key = f'notified_tp{tp_num}'
            
            tp_value = trade.get(tp_key)
            if tp_value is None:
                continue  # Skip if this TP isn't set
            
            # Check if already notified
            if trade[notified_key]:
                continue
            
            # Check TP condition based on trade type
            condition_met = False
            if trade_type == "Long":
                if price >= tp_value:
                    condition_met = True
            else:  # Short
                if price <= tp_value:
                    condition_met = True
            
            if condition_met:
                holding_time = time.time() - trade['entry_time']  # Time difference in seconds
                formatted_time = format_time_difference(holding_time)
                # Send TP message and update the notified status
                await send_tp_message(Update, context, tp_num, asset, price,formatted_time)
                trade[notified_key] = True
                if tp_num == 6:
                    del active_trades[asset]

def main():
    os.makedirs("images/output", exist_ok=True)
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.job_queue.run_repeating(check_target, interval=5)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, capture_trade))
    # application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, group_welcome))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, group_removed))



    application.run_polling()

if __name__ == "__main__":
    main()



        