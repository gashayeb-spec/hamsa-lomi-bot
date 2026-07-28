Import os
import json
import logging
import random
import re
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ማዋቀሪያ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8848878976:AAESocn6kgb-WJzRdfggiJRyMGHxVIteRaE")
ADMIN_ID = 5351353727 
TICKET_PRICE = 1000
TARGET_DATETIME = None 

# --- የሽልማት መጠኖች (ዳይናሚክ የዋጋ ዝርዝር) ---
# መሠረታዊ ሬሾ፡ 1000 ብር ሲሆን -> 1ኛ 2,000,000 | 2ኛ 200,000 | 3ኛ 50,000
def get_prize_1st():
    ratio = TICKET_PRICE / 1000.0
    val = int(2000000 * ratio)
    return f"{val:,} ብር"

def get_prize_2nd():
    ratio = TICKET_PRICE / 1000.0
    val = int(200000 * ratio)
    return f"{val:,} ብር"

def get_prize_3rd():
    ratio = TICKET_PRICE / 1000.0
    val = int(50000 * ratio)
    return f"{val:,} ብር"

# አውቶማቲክ ማሳወቂያ የሚለቀቅበት የቴሌግራም ቻናል ዩዘርናሜ
CHANNEL_USERNAME = "@Gashaye_Lottery_Channel"

occupied_numbers = {} 
user_selections = {}  
user_languages = {} 
rejected_counts = {}  
blocked_users = set()   

drawn_winners = {
    "1st": None,
    "2nd": None,
    "3rd": None
}

USERS_FILE = "users.json"
DETAILS_FILE = "users_details.json"

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_users():
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(list(registered_users), f)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

def load_user_details():
    if os.path.exists(DETAILS_FILE):
        try:
            with open(DETAILS_FILE, "r") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            return {}
    return {}

def save_user_details():
    try:
        with open(DETAILS_FILE, "w") as f:
            json.dump(all_user_details, f)
    except Exception as e:
        logger.error(f"Error saving user details: {e}")

registered_users = load_users()
all_user_details = load_user_details()

CITIES = ["አዲስ አበባ", "ሀዋሳ", "አዳማ", "ባህር ዳር", "ድሬዳዋ", "ጂማ", "መቀሌ"]
# Conversations States: NAME, PHONE, CITY, OTHER_CITY, PICKING, WAITING_RECEIPT
NAME, PHONE, CITY, OTHER_CITY, PICKING, WAITING_RECEIPT = range(6)

BANK_DETAILS = (
    "የባንክ ዝርዝሮቻችን (ለመቅዳት ይጫኑ):\n\n"
    "`1000070780201` - ንግድ ባንክ (Gashaye Bejigu Herego)\n"
    "`0916039015` - ቴሌብር (Gashaye Bejigu Herego)\n"
    "`54071628` - አቢሲኒያ (Gashaye Bejigu Herego)\n"
    "`7000007057569` - ንብ (Gashaye Bejigu Herego)"
)

LANG_TEXTS = {
    "am": {
        "btn_reg": "🔄 አዲስ ዙር መክፈቻ / ቦቱን ክፈት",
        "choose_num": "ቁጥር ይምረጡ ({start}-{end}):",
        "name_prompt": "እባክዎ ሙሉ ስምዎን ይጻፉ:",
        "phone_prompt": "ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ: 09XXXXXXXX ወይም 07XXXXXXXX):",
        "phone_error": "❌ ስልክ ቁጥርዎ ትክክል አይደለም!\nእባክዎ በ **09** ወይም በ **07** የሚጀምር ትክክለኛ የኢትዮጵያ ስልክ ቁጥር ያስገቡ:",
        "city_prompt": "ከተማዎን ይምረጡ:",
        "other_city_prompt": "እባክዎ የከተማዎን/ቦታዎን ስም በጽሁፍ ይጻፉ:",
        "done_btn": "✅ የተቆረጠ ምርጫ ጨርስ",
        "taken": "ይህ ቁጥር ተይዟል!",
        "min_one": "እባክዎ ቢያንስ አንድ ቁጥር ይምረጡ!",
        "success_reg": "ምርጫዎ ተመዝግቧል።\nጠቅላላ ቲኬት: {count}\nየሚከፈል ክፍያ: {total} ብር\n\n{banks}\n\nክፍያ ከፈጸሙ በኋላ ስክሪንሾቱን ይላኩ።",
        "lang_prompt": "ቋንቋ ይምረጡ / Choose your language:"
    },
    "en": {
        "btn_reg": "🔄 Open New Round Bot",
        "choose_num": "Select numbers ({start}-{end}):",
        "name_prompt": "Please enter your full name:",
        "phone_prompt": "Enter your phone number (e.g., 09XXXXXXXX or 07XXXXXXXX):",
        "phone_error": "❌ Invalid phone number!\nPlease enter a valid Ethiopian phone number starting with **09** or **07**:",
        "city_prompt": "Select your city:",
        "other_city_prompt": "Please type your city/location name:",
        "done_btn": "✅ Finish Selection",
        "taken": "This number is already taken!",
        "min_one": "Please select at least one number!",
        "success_reg": "Your selection is registered.\nTotal tickets: {count}\nAmount to pay: {total} birr\n\n{banks}\n\nSend the screenshot after payment.",
        "lang_prompt": "ቋንቋ ይምረጡ / Choose your language:"
    }
}

def get_text(user_id, key, **kwargs):
    lang = user_languages.get(user_id, "am") 
    text_template = LANG_TEXTS.get(lang, LANG_TEXTS["am"]).get(key, LANG_TEXTS["am"][key])
    return text_template.format(**kwargs)

def get_countdown_text():
    global TARGET_DATETIME
    if not TARGET_DATETIME:
        return "" 
    
    now = datetime.now()
    remaining = TARGET_DATETIME - now
    
    if remaining.total_seconds() <= 0:
        return "⏰ የዕጣው ጊዜ አልቋል! ዕጣው ሊወጣ ነው!\n"
    
    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    
    return f"⏳ ዕጣ ለመውጣት የቀረው ጊዜ:\n👉 **{days} ቀን ከ {hours} ሰዓት ከ {minutes} ደቂቃ**\n"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        msg = "❌ ይቅርታ! በተደጋጋሚ የተሳሳተ የክፍያ ስክሪንሾት በመላክዎ (Rejected) ምክንያት ከቦቱ ታግደዋል (Blocked)።"
        if update.message:
            await update.message.reply_text(msg)
        elif update.callback_query:
            await update.callback_query.message.reply_text(msg)
        return ConversationHandler.END

    if user_id not in registered_users:
        registered_users.add(user_id)
        save_users()
    
    welcome_intro = (
        "🌟🎰 **እንኳን ወደ 'ጋሻዬ ሎተሪ' አዲስ ዙር በደህና መጡ!** 🎰🌟\n\n"
        f"🎟️ **በ {TICKET_PRICE:,} ብር ብቻ አሸናፊ ይሁኑ!**\n\n"
        "🏆 **የሽልማት ዝርዝር፦**\n"
        f"🥇 **1ኛ ዕጣ:** {get_prize_1st()}\n"
        f"🥈 **2ኛ ዕጣ:** {get_prize_2nd()}\n"
        f"🥉 **3ኛ ዕጣ:** {get_prize_3rd()}\n\n"
        "👇 እባክዎ ለመቀጠል የሚፈልጉትን ቋንቋ ይምረጡ / Please choose your language:"
    )
    
    lang_kb = [
        [InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang_am")],
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")]
    ]
    
    if update.message:
        await update.message.reply_text(welcome_intro, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(lang_kb))
    elif update.callback_query:
        await update.callback_query.message.reply_text(welcome_intro, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(lang_kb))
    
    return ConversationHandler.END

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        await query.message.edit_text("❌ ይቅርታ! በተደጋጋሚ የተሳሳተ ስክሪንሾት በመላክዎ ምክንያት ከቦቱ ታግደዋል (Blocked)።")
        return

    lang_code = query.data.split("_")[1]
    user_languages[user_id] = lang_code
    
    context.user_data.clear()
    if user_id in user_selections and user_id not in occupied_numbers.values():
        user_selections[user_id] = []

    welcome_text = (
        "🌟🎰 **እንኳን ወደ 'ጋሻዬ ሎተሪ' ቦት በደህና መጡ!** 🎰🌟\n\n"
        f"🎟️ **በ {TICKET_PRICE:,} ብር ብቻ አሸናፊ ይሁኑ!**\n\n"
        "🏆 **የሽልማት ዝርዝር፦**\n"
        f"🥇 **1ኛ ዕጣ:** {get_prize_1st()}\n"
        f"🥈 **2ኛ ዕጣ:** {get_prize_2nd()}\n"
        f"🥉 **3ኛ ዕጣ:** {get_prize_3rd()}\n\n"
        "👇 ከታች ያለውን አዝራር በመጫን አሁን የሎተሪ ቁጥርዎን ይምረጡ!"
    )
    btn_text = get_text(user_id, "btn_reg")
    
    kb = [
        [InlineKeyboardButton(btn_text, callback_data="start_reg")],
        [InlineKeyboardButton("📢 የሎተሪ ቻናላችንን ይቀላቀሉ", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]
    ]
    time_info = get_countdown_text()
    
    full_message = f"{welcome_text}\n\n{time_info}"
    await query.message.edit_text(full_message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def set_price(update, context):
    global TICKET_PRICE
    if update.effective_user.id == ADMIN_ID:
        try:
            TICKET_PRICE = int(context.args[0])
            await update.message.reply_text(
                f"✅ የቲኬት ዋጋ ወደ **{TICKET_PRICE:,} ብር** ተቀይሯል።\n"
                f"ሽልማቶችም በዚሁ መሰረት አውቶማቲካሊ ተስተካክለዋል:\n"
                f"🥇 1ኛ: {get_prize_1st()}\n"
                f"🥈 2ኛ: {get_prize_2nd()}\n"
                f"🥉 3ኛ: {get_prize_3rd()}",
                parse_mode='Markdown'
            )
        except (IndexError, ValueError):
            await update.message.reply_text("❌ እባክዎ ትክክለኛ ዋጋ ያስገቡ። (ምሳሌ: /setprice 500)")

async def set_date(update, context):
    global TARGET_DATETIME
    if update.effective_user.id == ADMIN_ID:
        if len(context.args) >= 2:
            date_str = context.args[0]
            time_str = context.args[1]
            try:
                TARGET_DATETIME = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                remaining = TARGET_DATETIME - datetime.now()
                days = remaining.days
                hours = remaining.seconds // 3600
                await update.message.reply_text(f"✅ የካውንት ዳውን ጊዜ በትክክል ተስተካክሏል!")
                
                try:
                    bot_username = (await context.bot.get_me()).username
                    countdown_kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✨ አዲስ ዙር ጀምር", url=f"https://t.me/{bot_username}")]
                    ])
                    countdown_announcement = (
                        f"⏳ **የሎተሪ ዕጣ ማውጫ ቀን ተቆርጧል!** 🎟️\n\n"
                        f"📅 ዕጣ የሚወጣበት ቀን: **{date_str} ሰዓት {time_str}**\n"
                        f"⏰ (ቀሪ ጊዜ: **{days} ቀን ከ {hours} ሰዓት**)\n\n"
                        f"🔥 አዲስ ዙር እድልዎን ለመጠቀም አሁኑኑ ቲኬት ይቁረጡ!"
                    )
                    await context.bot.send_message(CHANNEL_USERNAME, countdown_announcement, parse_mode='Markdown', reply_markup=countdown_kb)
                except Exception as e:
                    logger.error(f"Error posting countdown to channel: {e}")
            except ValueError:
                await update.message.reply_text("❌ ስህተት! ትክክለኛ ፎርማት ይጠቀሙ። ምሳሌ: `/setcountdown 2026-08-21 19:19`", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ ትክክለኛ አጠቃቀም (ምሳሌ):\n`/setcountdown 2026-08-21 19:19`", parse_mode='Markdown')

async def check_stats(update, context):
    if update.effective_user.id == ADMIN_ID:
        total_sold = len(occupied_numbers)
        total_remaining = 4000 - total_sold
        total_revenue = total_sold * TICKET_PRICE
        await update.message.reply_text(
            f"📊 **የሎተሪ ሽያጭ መረጃ:**\n\n"
            f"🎫 የተሸጡ/የተያዙ ቲኬቶች: **{total_sold}** (ከ 4000)\n"
            f"ቁጥሮች የቀሩት ብዛት: **{total_remaining}**\n"
            f"💰 ጠቅላላ ገቢ: **{total_revenue:,} ብር**\n"
            f"💵 የአንድ ቲኬት ዋጋ: **{TICKET_PRICE:,} ብር**\n"
            f"👥 የተመዘገቡ ተጠቃሚዎች: **{len(registered_users)}**\n"
            f"🚫 የታገዱ (Blocked) ተጠቃሚዎች: **{len(blocked_users)}**",
            parse_mode='Markdown'
        )

async def list_users(update, context):
    if update.effective_user.id == ADMIN_ID:
        if not all_user_details:
            await update.message.reply_text("📭 እስካሁን የተመዘገበ ተጠቃሚ የለም።")
            return
        
        msg = "📋 **የተመዘገቡ ተጠቃሚዎች ዝርዝር:**\n\n"
        for uid, details in all_user_details.items():
            nums = [num for num, owner_id in occupied_numbers.items() if owner_id == uid]
            status_blocked = " 🔴 [BLOCKED]" if uid in blocked_users else ""
            msg += (
                f"👤 ስም: *{details.get('name', 'አልታወቀም')}*{status_blocked}\n"
                f"📱 ስልክ: `{details.get('phone', 'አልታወቀም')}`\n"
                f"🏙️ ከተማ: {details.get('city', 'አልታወቀም')}\n"
                f"🎟️ የተቆረጡ ቲኬቶች ({len(nums)}): {nums}\n"
                f"-----------------------------------\n"
            )
        
        if len(msg) > 4096:
            for x in range(0, len(msg), 4096):
                await update.message.reply_text(msg[x:x+4096], parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')

async def draw_logtery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not occupied_numbers:
            await update.message.reply_text("❌ እስካሁን የተያዘ/የተሸጠ የሎተሪ ቁጥር የለም። ዕጣ ማውጣት አይቻልም!")
            return
        
        confirm_kb = [
            [InlineKeyboardButton(f"🥇 1ኛ ዕጣ ({get_prize_1st()})", callback_data="draw_tier_1")],
            [InlineKeyboardButton(f"🥈 2ኛ ዕጣ ({get_prize_2nd()})", callback_data="draw_tier_2")],
            [InlineKeyboardButton(f"🥉 3ኛ ዕጣ ({get_prize_3rd()})", callback_data="draw_tier_3")],
            [InlineKeyboardButton("❌ ተው/ይቅር", callback_data="confirm_draw_no")]
        ]
        await update.message.reply_text(
            "⚠️ **የትኛውን የዕጣ ደረጃ ማውጣት ይፈልጋሉ?**\n\nከታች ያሉትን አማራጮች ይምረጡ፦",
            reply_markup=InlineKeyboardMarkup(confirm_kb),
            parse_mode='Markdown'
        )

async def handle_draw_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.answer("ይህንን ትዕዛዝ መጠቀም የሚችለው አድሚኑ ብቻ ነው!", show_alert=True)
        return

    action = query.data
    
    if action == "confirm_draw_no":
        await query.message.edit_text("❌ የዕጣ ማውጣት ሂደቱ ተሰርዟል።")
        return
        
    if action in ["draw_tier_1", "draw_tier_2", "draw_tier_3", "redraw_tier_1", "redraw_tier_2", "redraw_tier_3"]:
        tier_key = action.split("_")[-1]
        
        if tier_key == "1":
            tier_name = "🥇 1ኛ ደረጃ ዕጣ"
            amount_text = get_prize_1st()
            internal_tier = "1st"
        elif tier_key == "2":
            tier_name = "🥈 2ኛ ደረጃ ዕጣ"
            amount_text = get_prize_2nd()
            internal_tier = "2nd"
        else:
            tier_name = "🥉 3ኛ ደረጃ ዕጣ"
            amount_text = get_prize_3rd()
            internal_tier = "3rd"
            
        available_numbers = {num: uid for num, uid in occupied_numbers.items() if num not in drawn_winners.values()}
        
        if not available_numbers:
            await query.message.edit_text("❌ ሁሉም የተያዙ ቲኬቶች ቀድመው አሸናፊ ሆረዋል ወይም የሚመረጥ ቁጥር የለም።")
            return
            
        winning_number = random.choice(list(available_numbers.keys()))
        winner_user_id = available_numbers[winning_number]
        
        winner_info = all_user_details.get(winner_user_id, {"name": "ስም አልተገኘም", "phone": "ስልክ አልተገኘም", "city": "አልታወቀም"})
        winner_name = winner_info.get("name", "ስም አልተገኘም")
        winner_phone = winner_info.get("phone", "ስልክ አልተገኘም")
        winner_city = winner_info.get("city", "አልታወቀም")
        
        context.user_data['pending_draw'] = {
            "tier": internal_tier,
            "tier_name": tier_name,
            "amount_text": amount_text,
            "winning_number": winning_number,
            "winner_user_id": winner_user_id,
            "winner_name": winner_name,
            "winner_phone": winner_phone,
            "winner_city": winner_city
        }
        
        approval_kb = [
            [
                InlineKeyboardButton("✅ አጽድቅ", callback_data=f"approve_draw_{tier_key}"),
                InlineKeyboardButton("🔄 እንደገና ድሮ (Re-draw)", callback_data=f"draw_tier_{tier_key}")
            ],
            [
                InlineKeyboardButton("❌ ሙሉ በሙሉ ተው", callback_data="confirm_draw_no")
            ]
        ]
        
        admin_preview = (
            f"🔍 **የዕጣ ቅድመ-ዕይታ (Pending {tier_name})**\n\n"
            f"🏆 የተመረጠ ቁጥር: **{winning_number}**\n"
            f"💰 ሽልማት: **{amount_text}**\n"
            f"👤 ስም: *{winner_name}*\n"
            f"🏙️ ከተማ: {winner_city}\n"
            f"📱 ስልክ: `{winner_phone}`\n\n"
            f"👇 እባክዎ ይህንን ውጤት **Approve** ያድርጉት ወይም **Cancel (Re-draw)** በማድረግ ሌላ ቁጥር ይምረጡ።"
        )
        await query.message.edit_text(admin_preview, reply_markup=InlineKeyboardMarkup(approval_kb), parse_mode='Markdown')

    elif action.startswith("approve_draw_"):
        tier_key = action.split("_")[-1]
        pending = context.user_data.get('pending_draw')
        
        if not pending:
            await query.message.edit_text("❌ የድሮ መረጃው አልገኘም ወይም ጊዜው አልፎአል። እባክዎ እንደገና `/draw` ይበሉ።", parse_mode='Markdown')
            return
            
        winning_number = pending['winning_number']
        winner_user_id = pending['winner_user_id']
        tier_name = pending['tier_name']
        amount_text = pending['amount_text']
        winner_name = pending['winner_name']
        winner_phone = pending['winner_phone']
        winner_city = pending['winner_city']
        internal_tier = pending['tier']
        
        drawn_winners[internal_tier] = winning_number
        
        admin_final = (
            f"🎉 **{tier_name} በይፋ ጸድቆ ተልኳል!** 🎉\n\n"
            f"🏆 አሸናፊ ቁጥር: **{winning_number}**\n"
            f"💰 ሽልማት: **{amount_text}**\n"
            f"👤 ስም: *{winner_name}*\n"
            f"🏙️ ከተማ: {winner_city}\n"
            f"📱 ስልክ: `{winner_phone}`"
        )
        await query.message.edit_text(admin_final, parse_mode='Markdown')
        
        winner_message = (
            f"🎉🎊 **እንኳን ደስ አለዎት! እርስዎ የ{tier_name} አሸናፊ ሆነዋል!** 🎊🎉\n\n"
            f"🎟️ ያሸነፉበት ቁጥር: **{winning_number}**\n"
            f"💰 ያሸነፉት የገንዘብ ሽልማት: **{amount_text}**\n\n"
            f"ሽልማትዎን ለመረከብ ወዲያውኑ ከቦቱ አስተዳዳሪ ጋር ይነጋገሩ። መልካም ዕድል!"
        )
        try:
            await context.bot.send_message(winner_user_id, winner_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error sending message to winner {winner_user_id}: {e}")

        try:
            bot_username = (await context.bot.get_me()).username
            channel_draw_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 አዲስ ዙር ጀምር", url=f"https://t.me/{bot_username}")]
            ])
            channel_announcement = (
                f"🚨📢 **የ{tier_name} አሸናፊ ይፋ ሆነ!** 📢🚨\n\n"
                f"🏆 የዚህ ዙር ዕድለኛ ቁጥር **{winning_number}** ሆኗል!\n"
                f"👤 ስም: *{winner_name}* ({winner_city})\n"
                f"💰 ያሸነፈው ሽልማት: **{amount_text}**\n\n"
                f"✨ ዕድለኛውን ተሳታፊ ከልብ እናመሰግናለን! ቀጣይ አዲስ ዙር ተጀምሯል!"
            )
            await context.bot.send_message(CHANNEL_USERNAME, channel_announcement, parse_mode='Markdown', reply_markup=channel_draw_kb)
        except Exception as e:
            logger.error(f"Error posting draw result to channel: {e}")

async def reset_lottery(update, context):
    if update.effective_user.id == ADMIN_ID:
        occupied_numbers.clear()
        user_selections.clear()
        all_user_details.clear()
        rejected_counts.clear()
        blocked_users.clear()
        drawn_winners["1st"] = None
        drawn_winners["2nd"] = None
        drawn_winners["3rd"] = None
        
        if os.path.exists(DETAILS_FILE):
            os.remove(DETAILS_FILE)
        context.user_data.clear()
        
        reset_announcement = (
            "✅ **የቀድሞው ዙር ሎተሪ በሰላም ተጠናቋል!**\n\n"
            "🚀 አሁን **አዲስ ዙር (New Round)** የጀመርን መሆኑን በታላቅ ደስታ እንገልጻለን። ሁላችሁም አዲሱን ዙር ለመቀላቀል ከታች ያለውን አዝራር በመጫን ቲኬት መቆረጥ ትችላላችሁ!"
        )
        
        try:
            bot_username = (await context.bot.get_me()).username
            reset_channel_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 አዲስ ዙር ጀምር", url=f"https://t.me/{bot_username}")]
            ])
            await context.bot.send_message(CHANNEL_USERNAME, reset_announcement, parse_mode='Markdown', reply_markup=reset_channel_kb)
        except Exception as e:
            logger.error(f"Error sending reset announcement to channel: {e}")

        admin_kb = [[InlineKeyboardButton("🚀 አዲስ ዙር ጀምር", callback_data="restart_bot")]]
        await update.message.reply_text(
            "✅ ሎተሪው ሙሉ በሙሉ ሬሴት ተደርጓል እና አዲስ ዙር ማስታወቂያ ለቻናሉ ተልኳል።",
            reply_markup=InlineKeyboardMarkup(admin_kb)
        )
        
        start_kb = [[InlineKeyboardButton("🚀 አዲስ ዙር ጀምር", callback_data="restart_bot")]]
        for uid in list(registered_users):
            try:
                await context.bot.send_message(
                    uid, 
                    reset_announcement, 
                    reply_markup=InlineKeyboardMarkup(start_kb),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error notifying user {uid} about reset: {e}")

async def handle_restart_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    welcome_intro = (
        "🌟🎰 **እንኳን ወደ 'ጋሻዬ ሎተሪ' አዲስ ዙር በደህና መጡ!** 🎰🌟\n\n"
        f"🎟️ **በ {TICKET_PRICE:,} ብር ብቻ አሸናፊ ይሁኑ!**\n\n"
        "🏆 **የሽልማት ዝርዝር፦**\n"
        f"🥇 **1ኛ ዕጣ:** {get_prize_1st()}\n"
        f"🥈 **2ኛ ዕጣ:** {get_prize_2nd()}\n"
        f"🥉 **3ኛ ዕጣ:** {get_prize_3rd()}\n\n"
        "👇 እባክዎ ለመቀጠል የሚፈልጉትን ቋንቋ ይምረጡ / Please choose your language:"
    )
    
    lang_kb = [
        [InlineKeyboardButton("አማርኛ 🇪🇹", callback_data="lang_am")],
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en")]
    ]
    await query.message.reply_text(welcome_intro, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(lang_kb))

async def ask_name(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        await query.message.edit_text("❌ ይቅርታ! በተደጋጋሚ የተሳሳተ የክፍያ ስክሪንሾት በመላክዎ (Rejected) ምክንያት ከቦቱ ታግደዋል (Blocked)።")
        return

    await query.message.reply_text(get_text(user_id, "name_prompt"))
    return NAME

async def get_name(update, context):
    context.user_data['name'] = update.message.text
    user_id = update.effective_user.id
    await update.message.reply_text(get_text(user_id, "phone_prompt"))
    return PHONE

async def get_phone(update, context):
    phone_text = update.message.text.strip()
    user_id = update.effective_user.id
    pattern = r"^(?:\+251|0)[79]\d{8}$"
    
    if not re.match(pattern, phone_text):
        await update.message.reply_text(get_text(user_id, "phone_error"), parse_mode='Markdown')
        return PHONE

    context.user_data['phone'] = phone_text
    
    kb = [[InlineKeyboardButton(c, callback_data=f"city_{c}")] for c in CITIES]
    other_btn_text = "ሌላ (Other)" if user_languages.get(user_id, "am") == "am" else "Other (ሌላ)"
    kb.append([InlineKeyboardButton(other_btn_text, callback_data="city_Other")])
    
    await update.message.reply_text(get_text(user_id, "city_prompt"), reply_markup=InlineKeyboardMarkup(kb))
    return CITY

async def get_city(update, context):
    query = update.callback_query
    await query.answer()
    selected_city = query.data.split("_", 1)[1]
    user_id = update.effective_user.id
    
    if selected_city == "Other":
        await query.message.edit_text(get_text(user_id, "other_city_prompt"))
        return OTHER_CITY
    
    context.user_data['city'] = selected_city
    
    all_user_details[user_id] = {
        "name": context.user_data.get('name'),
        "phone": context.user_data.get('phone'),
        "city": context.user_data.get('city')
    }
    save_user_details()

    if user_id not in user_selections:
        user_selections[user_id] = []
    return await show_numbers_page(update, context)

async def get_other_city(update, context):
    user_id = update.effective_user.id
    other_city_name = update.message.text.strip()
    
    context.user_data['city'] = other_city_name
    
    all_user_details[user_id] = {
        "name": context.user_data.get('name'),
        "phone": context.user_data.get('phone'),
        "city": context.user_data.get('city')
    }
    save_user_details()

    if user_id not in user_selections:
        user_selections[user_id] = []
    
    return await show_numbers_page_message(update, context)

async def show_numbers_page_message(update, context, page=0):
    start_num = page * 100 + 1
    end_num = min(start_num + 99, 4000)
    keyboard = []
    row = []
    user_id = update.effective_user.id
    my_nums = user_selections.get(user_id, [])

    for i in range(start_num, end_num + 2):
        if i > 4000:
            break
            
        if i in my_nums:
            text = f"✅ {i}"
        elif i in occupied_numbers:
            text = "⭐"
        else:
            text = str(i)
            
        row.append(InlineKeyboardButton(text, callback_data=f"sel_{i}"))
        if len(row) == 10: 
            keyboard.append(row)
            row = []
    if row: 
        keyboard.append(row)
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"ገጽ {page+1} (1-4000)", callback_data="ignore"))
    if end_num < 4000: nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page+1}"))
    keyboard.append(nav)
    
    done_text = get_text(user_id, "done_btn")
    keyboard.append([InlineKeyboardButton(done_text, callback_data="done")])
    
    msg = get_text(user_id, "choose_num", start=start_num, end=end_num)
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return PICKING

async def show_numbers_page(update, context, page=0):
    start_num = page * 100 + 1
    end_num = min(start_num + 99, 4000)
    keyboard = []
    row = []
    user_id = update.effective_user.id
    my_nums = user_selections.get(user_id, [])

    for i in range(start_num, end_num + 2):
        if i > 4000:
            break
            
        if i in my_nums:
            text = f"✅ {i}"
        elif i in occupied_numbers:
            text = "⭐"
        else:
            text = str(i)
            
        row.append(InlineKeyboardButton(text, callback_data=f"sel_{i}"))
        if len(row) == 10: 
            keyboard.append(row)
            row = []
    if row: 
        keyboard.append(row)
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"ገጽ {page+1} (1-4000)", callback_data="ignore"))
    if end_num < 4000: nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page+1}"))
    keyboard.append(nav)
    
    done_text = get_text(user_id, "done_btn")
    keyboard.append([InlineKeyboardButton(done_text, callback_data="done")])
    
    msg = get_text(user_id, "choose_num", start=start_num, end=end_num)
    if update.callback_query: 
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return PICKING

async def handle_selection(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        await query.message.edit_text("❌ ይቅርታ! በተደጋጋሚ የተሳሳተ ስክሪንሾት በመላክዎ ምክንያት ከቦቱ ታግደዋል (Blocked)።")
        return

    if user_id not in user_selections:
        user_selections[user_id] = []

    if query.data.startswith("page_"):
        await show_numbers_page(update, context, int(query.data.split("_")[1]))
    elif query.data.startswith("sel_"):
        num = int(query.data.split("_")[1])
        if num > 4000:
            await query.answer("ይህ ቦት የሚፈቅደው እስከ 4000 ቲኬት ብቻ ነው!", show_alert=True)
            return
        
        if num in user_selections[user_id]:
            user_selections[user_id].remove(num)
            if num in occupied_numbers and occupied_numbers[num] == user_id:
                del occupied_numbers[num]
            await show_numbers_page(update, context, (num - 1) // 100)
            
        elif num not in occupied_numbers:
            occupied_numbers[num] = user_id
            user_selections[user_id].append(num)
            await show_numbers_page(update, context, (num - 1) // 100)
        else:
            await query.answer(get_text(user_id, "taken"), show_alert=True)
            
    elif query.data == "done":
        nums = user_selections.get(user_id, [])
        if not nums:
            await query.answer(get_text(user_id, "min_one"), show_alert=True)
            return
        
        for num in nums:
            occupied_numbers[num] = user_id

        total = len(nums) * TICKET_PRICE
        success_msg = get_text(user_id, "success_reg", count=len(nums), total=total, banks=BANK_DETAILS)
        await query.message.reply_text(success_msg, parse_mode='Markdown')
        return WAITING_RECEIPT

async def handle_receipt(update, context):
    user_id = update.effective_user.id
    
    if user_id in blocked_users:
        await update.message.reply_text("❌ ይቅርታ! በተደጋጋሚ የተሳሳተ ስክሪንሾት በመላክዎ ምክንያት ከቦቱ ታግደዋል (Blocked)።")
        return

    if not update.message.photo:
        await update.message.reply_text("❌ እባክዎ ትክክለኛ የክፍያ ስክሪንሾት (ፎቶ) ብቻ ይላኩ!")
        return WAITING_RECEIPT
        
    photo = update.message.photo[-1].file_id
    user_info = all_user_details.get(user_id, {"name": "ስም አልተገኘም", "phone": "ስልክ አልተገኘም"})
    nums = user_selections.get(user_id, [])
    
    if not nums:
        nums = [num for num, uid in occupied_numbers.items() if uid == user_id]

    expected_total = len(nums) * TICKET_PRICE
    current_rejects = rejected_counts.get(user_id, 0)
    
    kb = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"app_{user_id}"), 
            InlineKeyboardButton("❌ ውድቅ አድርግ (Reject)", callback_data=f"rej_{user_id}")
        ]
    ] 
    
    caption = (
        f"📥 **አዲስ የክፍያ ስክሪንሾት መጣ!**\n\n"
        f"👤 ስም: *{user_info.get('name')}*\n"
        f"📱 ስልክ: `{user_info.get('phone')}`\n"
        f"🆔 ዩዘር ID: `{user_id}`\n"
        f"🎟️ የተያዙ ቁጥሮች: {nums}\n"
        f"📊 የዕጣ ብዛት: **{len(nums)} ዕጣ**\n"
        f"💰 ትክክለኛው የሚጠበቀው ክፍያ: **{expected_total:,} ብር**\n"
        f"⚠️ ቀድሞ የተሰጠው የተሳሳተ ሪጀክት (Rejected) ብዛት: **{current_rejects}/3**\n\n"
        f"⚠️ *ማስታወሻ፦ እባክዎ በስክሪንሾቱ ላይ ያለው የባንክ ገቢ ከላይ ካለው መጠን ጋር ትክክል መሆኑን አረጋግጠው 'Approve' ወይም 'Reject' ይበሉ!*"
    )
    
    await context.bot.send_photo(ADMIN_ID, photo, caption=caption, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))
    await update.message.reply_text("ክፍያዎ ለምርመራ ወደ አድሚን ተልኳል። ከተረጋገጠ በሰዓታት ውስጥ እናሳውቆታለን።")
    return ConversationHandler.END

async def admin_response(update, context):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    action = data_parts[0]
    user_id_str = data_parts[1]
    user_id = int(user_id_str.replace("s", "").replace("ዎች", ""))
    
    nums = [num for num, uid in occupied_numbers.items() if uid == user_id]
    
    if action == "app":
        if user_id in rejected_counts:
            del rejected_counts[user_id]
            
        await context.bot.send_message(user_id, f"✅ ክፍያዎ ተረጋግጧል!\n\nእርሶ የቆረጧቸው ቁጥሮች፡ {nums}\nብዛት፡ {len(nums)} ዕጣ።\n\nመልካም እድል! ዕጣው ሲወጣ በዚሁ እናሳውቆታለን።")
        
        try:
            user_info = all_user_details.get(user_id, {"name": "ስም አልተገኘም", "phone": "ስልክ አልተገኘም"})
            name = user_info.get("name", "ስም አልተገኘም")
            phone = user_info.get("phone", "ስልክ አልተገኘም")
            
            admin_notification = (
                f"✅ **ክፍያ ጸድቋል (Approved)!**\n\n"
                f"👤 ስም: *{name}*\n"
                f"📱 ስልክ: `{phone}`\n"
                f"🎟️ የተያዙ ቁጥሮች: {nums}\n"
                f"📊 ብዛት: **{len(nums)} ዕጣ**"
            )
            await context.bot.send_message(ADMIN_ID, admin_notification, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error sending approval notification to admin: {e}")

        try:
            user_info = all_user_details.get(user_id, {"name": "ተጠቃሚ"})
            name = user_info.get("name", "ተጠቃሚ")
            bot_username = (await context.bot.get_me()).username
            channel_ticket_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 አዲስ ዙር ጀምር", url=f"https://t.me/{bot_username}")]
            ])
            channel_msg = (
                f"🎉 **አዲስ ቲኬት ተረጋገጠ!** 🎟️\n\n"
                f"👤 ስም: *{name}*\n"
                f"🎟️ የተያዙ ቁጥሮች: {nums}\n"
                f"📊 ብዛት: **{len(nums)} ዕጣ**\n\n"
                f"✨ መልካም ዕድል ለሁላችንም!"
            )
            await context.bot.send_message(CHANNEL_USERNAME, channel_msg, parse_mode='Markdown', reply_markup=channel_ticket_kb)
        except Exception as e:
            logger.error(f"Error posting to channel: {e}")

    else: 
        for num in nums:
            if occupied_numbers.get(num) == user_id:
                del occupied_numbers[num]
        
        if user_id not in rejected_counts:
            rejected_counts[user_id] = 0
        rejected_counts[user_id] += 1
        
        current_rejects = rejected_counts[user_id]
        
        if current_rejects >= 3:
            blocked_users.add(user_id)
            if user_id in user_selections:
                del user_selections[user_id]
                
            await context.bot.send_message(
                user_id, 
                "❌ **ከቦቱ ታግደዋል (Blocked)!**\n\n"
                "ስክሪንሾትዎ 3 ጊዜ ተከታታይነት ባለው መልኩ ውድቅ (Rejected) ተደርጓል። ህጎቹን በመጣስዎ ምክንያት ከዚህ ቦት ውጪ ተደርገዋል!", 
                parse_mode='Markdown'
            )
            
            try:
                await context.bot.send_message(
                    ADMIN_ID, 
                    f"🚫 **ተጠቃሚ ታግዷል (Auto-Blocked)!**\n\nዩዘር ID: `{user_id}` ስክሪንሾት 3 ጊዜ በመሳሳቱ ምክንያት ተብሎክ አድርጓል።",
                    parse_mode='Markdown'
                )
            except Exception:
                pass
        else:
            remaining_chances = 3 - current_rejects
            await context.bot.send_message(
                user_id, 
                f"❌ ክፍያዎ ተቀባይነት አላገኘም (ስክሪንሾቱ ውድቅ / Rejected ተደርጓል)።\n\n"
                f"⚠️ ያስተውሉ! የተሳሳተ ስክሪንሾት የላኩበት ቁጥር: **{current_rejects}/3** ነው።\n"
                f"አሁንም {remaining_chances} ዕድል ብቻ አለዎት፤ 3 ጊዜ ከተሳሳቱ ቦቱ በራስ-ሰር ብሎክ ያደርግዎታል።\n\n"
                f"እባኮትን ትክክለኛው የክፍያ ስክሪንሾት **ብቻ** አሁን እንደገና ፎቶ አንስተው ይላኩ!", 
                parse_mode='Markdown'
            )
            
    await query.message.delete()

async def announce_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        bot_username = (await context.bot.get_me()).username
        announcement_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 አዲስ ዙር ጀምር", url=f"https://t.me/{bot_username}")]
        ])

        if update.message.photo:
            photo_file_id = update.message.photo[-1].file_id
            caption_text = update.message.caption or "📢 **ልዩ ማስታወቂያ** 🎟️"
            
            sent_count = 0
            for uid in registered_users:
                if uid in blocked_users:
                    continue
                try:
                    await context.bot.send_photo(uid, photo_file_id, caption=caption_text, parse_mode='Markdown')
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending photo to {uid}: {e}")
            
            try:
                await context.bot.send_photo(CHANNEL_USERNAME, photo_file_id, caption=caption_text, parse_mode='Markdown', reply_markup=announcement_kb)
            except Exception as e:
                logger.error(f"Error sending photo to channel: {e}")
                
            await update.message.reply_text(f"✅ ምስል ያለው ማስታወቂያ ለ **{sent_count}** ተጠቃሚዎች እና ለቻናሉ ተልኳል!")
            
        elif context.args:
            message_text = " ".join(context.args)
            sent_count = 0
            
            for uid in registered_users:
                if uid in blocked_users:
                    continue
                try:
                    await context.bot.send_message(uid, message_text, parse_mode='Markdown')
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending text to {uid}: {e}")
            
            try:
                await context.bot.send_message(CHANNEL_USERNAME, message_text, parse_mode='Markdown', reply_markup=announcement_kb)
            except Exception as e:
                logger.error(f"Error sending text to channel: {e}")
                
            await update.message.reply_text(f"✅ ማስታወቂያው ለ **{sent_count}** ተጠቃሚዎች እና ለቻናሉ ተልኳል!")
        else:
            await update.message.reply_text("❌ እባክዎ ጽሁፍ ይጻፉ ወይም ፎቶ ከነ ጽሁፉ ጋር ይላኩ።")

if __name__ == '__main__':
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^/start$"), start),
            CallbackQueryHandler(ask_name, pattern="start_reg")
        ],
        states={
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_name),
                CommandHandler("start", start)
            ], 
            PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
                CommandHandler("start", start)
            ], 
            CITY: [
                CallbackQueryHandler(get_city, pattern="city_"),
                CommandHandler("start", start)
            ],
            OTHER_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_other_city),
                CommandHandler("start", start)
            ],
            PICKING: [
                CallbackQueryHandler(handle_selection, pattern="^(page_|sel_|done)"),
                CommandHandler("start", start),
                MessageHandler(filters.Regex("^/start$"), start)
            ],
            WAITING_RECEIPT: [
                MessageHandler(filters.PHOTO, handle_receipt),
                CommandHandler("start", start)
            ]
        },
        fallbacks=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^/start$"), start)
        ],
        allow_reentry=True
    )
    
    telegram_app.add_handlers([
        conv_handler,
        CallbackQueryHandler(set_language, pattern="^lang_"),
        CallbackQueryHandler(handle_restart_button, pattern="^restart_bot$"),
        CommandHandler("setprice", set_price),
        CommandHandler("setcountdown", set_date),
        CommandHandler("stats", check_stats),
        CommandHandler("users", list_users),
        CommandHandler("draw", draw_logtery),
        CallbackQueryHandler(handle_draw_confirmation, pattern="^(draw_tier_|approve_draw_|confirm_draw_)"),
        CommandHandler("reset_lottery", reset_lottery),
        CommandHandler("announce", announce_message),
        CallbackQueryHandler(admin_response, pattern="^(app|rej)_"),
        CallbackQueryHandler(ask_name, pattern="start_reg"),
        MessageHandler(filters.PHOTO, handle_receipt)
    ])
    
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    port = int(os.environ.get("PORT", 8080))
    
    if RENDER_URL:
        webhook_url = f"{RENDER_URL.rstrip('/')}/{BOT_TOKEN}"
        print(f"Starting Webhook at: {webhook_url}")
        telegram_app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )
    else:
        telegram_app.run_polling()
