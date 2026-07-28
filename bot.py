import os
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

# --- የቻፓ (Chapa) ትክክለኛ ቁልፎች ---
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPiXJwRXDF6MdgchtNV"
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDlRpfBCqTczyE10snrrK3Zhj"

# --- የሽልማት መጠኖች (ዳይናሚክ የዋጋ ዝርዝር) ---
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
NAME, PHONE, CITY, OTHER_CITY, PICKING = range(5)

LANG_TEXTS = {
    "am": {
        "btn_reg": "🔄 አዲስ ዙር መክፈቻ / ቦቱን ክፈት",
        "choose_num": "ቁጥር ይምረጡ ({start}-{end}):",
        "name_prompt": "እባክዎ ሙሉ ስምዎን ይጻፉ:",
        "phone_prompt": "ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ: 09XXXXXXXX ወይም 07XXXXXXXX):",
        "phone_error": "❌ ስልክ ቁጥርዎ ትክክል አይደለም!\nእባክዎ በ **09** ወይም በ **07** የሚጀምር ትክክለኛ የኢትዮጵያ ስልክ ቁጥር ያስገቡ:",
        "city_prompt": "ከተማዎን ይምረጡ:",
        "other_city_prompt": "እባክዎ የከተማዎን/ቦታዎን ስም በጽሁፍ ይጻፉ:",
        "done_btn": "✅ የተቆረጠ ምርጫ ጨርስ (ወደ ክፍያ ሂድ)",
        "taken": "ይህ ቁጥር ተይዟል!",
        "min_one": "እባክዎ ቢያንስ አንድ ቁጥር ይምረጡ!",
        "success_reg": "ምርጫዎ ተመዝግቧል።\nጠቅላላ ቲኬት: {count}\nየሚከፈል ክፍያ: {total} ብር\n\n👇 ከታች ያለውን አዝራር በመጫን ክፍያዎን በቻፓ (Chapa) በአውቶማቲክ ይፈጽሙ።",
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
        "done_btn": "✅ Finish Selection (Proceed to Pay)",
        "taken": "This number is already taken!",
        "min_one": "Please select at least one number!",
        "success_reg": "Your selection is registered.\nTotal tickets: {count}\nAmount to pay: {total} birr\n\n👇 Click the button below to pay securely via Chapa.",
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
        msg = "❌ ይቅርታ! ከቦቱ ታግደዋል (Blocked)።"
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
        await query.message.edit_text("❌ ይቅርታ! ታግደዋል (Blocked)።")
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
    await query.message.edit_text(f"{welcome_text}\n\n{time_info}", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(kb))

async def set_price(update, context):
    global TICKET_PRICE
    if update.effective_user.id == ADMIN_ID:
        try:
            TICKET_PRICE = int(context.args[0])
            await update.message.reply_text(
                f"✅ የቲኬት ዋጋ ወደ **{TICKET_PRICE:,} ብር** ተቀይሯል።\n"
                f"ሽልማቶችም በዚሁ መሰረት ተስተካክለዋል:\n"
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
            try:
                TARGET_DATETIME = datetime.strptime(f"{context.args[0]} {context.args[1]}", "%Y-%m-%d %H:%M")
                await update.message.reply_text("✅ የካውንት ዳውን ጊዜ በትክክል ተስተካክሏል!")
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
            f"👥 የተመዘገቡ ተጠቃሚዎች: **{len(registered_users)}**",
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
            msg += (
                f"👤 ስም: *{details.get('name', 'አልታወቀም')}*\n"
                f"📱 ስልክ: `{details.get('phone', 'አልታወቀም')}`\n"
                f"🏙️ ከተማ: {details.get('city', 'አልታወቀም')}\n"
                f"🎟️ የተቆረጡ ቲኬቶች ({len(nums)}): {nums}\n"
                f"-----------------------------------\n"
            )
        await update.message.reply_text(msg[:4096], parse_mode='Markdown')

async def draw_logtery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        if not occupied_numbers:
            await update.message.reply_text("❌ እስካሁን የተያዘ/የተሸጠ የሎተሪ ቁጥር የለም።")
            return
        
        confirm_kb = [
            [InlineKeyboardButton(f"🥇 1ኛ ዕጣ ({get_prize_1st()})", callback_data="draw_tier_1")],
            [InlineKeyboardButton(f"🥈 2ኛ ዕጣ ({get_prize_2nd()})", callback_data="draw_tier_2")],
            [InlineKeyboardButton(f"🥉 3ኛ ዕጣ ({get_prize_3rd()})", callback_data="draw_tier_3")],
            [InlineKeyboardButton("❌ ተው/ይቅር", callback_data="confirm_draw_no")]
        ]
        await update.message.reply_text("⚠️ **የትኛውን የዕጣ ደረጃ ማውጣት ይፈልጋሉ?**", reply_markup=InlineKeyboardMarkup(confirm_kb))

async def handle_draw_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        return

    action = query.data
    if action == "confirm_draw_no":
        await query.message.edit_text("❌ የዕጣ ማውጣት ሂደቱ ተሰርዟል።")
        return
        
    if action.startswith("draw_tier_"):
        tier_key = action.split("_")[-1]
        tier_name = "🥇 1ኛ ደረጃ ዕጣ" if tier_key == "1" else ("🥈 2ኛ ደረጃ ዕጣ" if tier_key == "2" else "🥉 3ኛ ደረጃ ዕጣ")
        amount_text = get_prize_1st() if tier_key == "1" else (get_prize_2nd() if tier_key == "2" else get_prize_3rd())
        internal_tier = "1st" if tier_key == "1" else ("2nd" if tier_key == "2" else "3rd")
            
        available_numbers = {num: uid for num, uid in occupied_numbers.items() if num not in drawn_winners.values()}
        if not available_numbers:
            await query.message.edit_text("❌ የሚመረጥ ቁጥር የለም።")
            return
            
        winning_number = random.choice(list(available_numbers.keys()))
        winner_user_id = available_numbers[winning_number]
        winner_info = all_user_details.get(winner_user_id, {"name": "ስም አልተገኘም", "phone": "ስልክ አልተገኘም", "city": "አልታወቀም"})
        
        drawn_winners[internal_tier] = winning_number
        
        admin_final = (
            f"🎉 **{tier_name} አሸናፊ ተመረጠ!** 🎉\n\n"
            f"🏆 አሸናፊ ቁጥር: **{winning_number}**\n"
            f"💰 ሽልማት: **{amount_text}**\n"
            f"👤 ስም: *{winner_info.get('name')}*\n"
            f"🏙️ ከተማ: {winner_info.get('city')}\n"
            f"📱 ስልክ: `{winner_info.get('phone')}`"
        )
        await query.message.edit_text(admin_final, parse_mode='Markdown')
        
        try:
            await context.bot.send_message(winner_user_id, f"🎉🎊 **እንኳን ደስ አለዎት! እርስዎ የ{tier_name} አሸናፊ ሆነዋል!** 🎊🎉\n\n🎟️ ያሸነፉበት ቁጥር: **{winning_number}**\n💰 ሽልማት: **{amount_text}**", parse_mode='Markdown')
        except Exception:
            pass

async def reset_lottery(update, context):
    if update.effective_user.id == ADMIN_ID:
        occupied_numbers.clear()
        user_selections.clear()
        all_user_details.clear()
        drawn_winners["1st"] = None
        drawn_winners["2nd"] = None
        drawn_winners["3rd"] = None
        
        if os.path.exists(DETAILS_FILE):
            os.remove(DETAILS_FILE)
        context.user_data.clear()
        
        await update.message.reply_text("✅ ሎተሪው ሙሉ በሙሉ ሬሴት ተደርጓል እና አዲስ ዙር ተጀምሯል።")

async def ask_name(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
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
    if not re.match(r"^(?:\+251|0)[79]\d{8}$", phone_text):
        await update.message.reply_text(get_text(user_id, "phone_error"), parse_mode='Markdown')
        return PHONE
    context.user_data['phone'] = phone_text
    kb = [[InlineKeyboardButton(c, callback_data=f"city_{c}")] for c in CITIES]
    kb.append([InlineKeyboardButton("Other (ሌላ)", callback_data="city_Other")])
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
    all_user_details[user_id] = {"name": context.user_data.get('name'), "phone": context.user_data.get('phone'), "city": context.user_data.get('city')}
    save_user_details()
    if user_id not in user_selections:
        user_selections[user_id] = []
    return await show_numbers_page(update, context)

async def get_other_city(update, context):
    user_id = update.effective_user.id
    context.user_data['city'] = update.message.text.strip()
    all_user_details[user_id] = {"name": context.user_data.get('name'), "phone": context.user_data.get('phone'), "city": context.user_data.get('city')}
    save_user_details()
    if user_id not in user_selections:
        user_selections[user_id] = []
    return await show_numbers_page_message(update, context)

async def show_numbers_page_message(update, context, page=0):
    start_num = page * 100 + 1
    end_num = min(start_num + 99, 4000)
    keyboard, row = [], []
    user_id = update.effective_user.id
    my_nums = user_selections.get(user_id, [])

    for i in range(start_num, end_num + 2):
        if i > 4000: break
        text = f"✅ {i}" if i in my_nums else ("⭐" if i in occupied_numbers else str(i))
        row.append(InlineKeyboardButton(text, callback_data=f"sel_{i}"))
        if len(row) == 10: 
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"ገጽ {page+1} (1-4000)", callback_data="ignore"))
    if end_num < 4000: nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page+1}"))
    keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(get_text(user_id, "done_btn"), callback_data="done")])
    
    await update.message.reply_text(get_text(user_id, "choose_num", start=start_num, end=end_num), reply_markup=InlineKeyboardMarkup(keyboard))
    return PICKING

async def show_numbers_page(update, context, page=0):
    start_num = page * 100 + 1
    end_num = min(start_num + 99, 4000)
    keyboard, row = [], []
    user_id = update.effective_user.id
    my_nums = user_selections.get(user_id, [])

    for i in range(start_num, end_num + 2):
        if i > 4000: break
        text = f"✅ {i}" if i in my_nums else ("⭐" if i in occupied_numbers else str(i))
        row.append(InlineKeyboardButton(text, callback_data=f"sel_{i}"))
        if len(row) == 10: 
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"page_{page-1}"))
    nav.append(InlineKeyboardButton(f"ገጽ {page+1} (1-4000)", callback_data="ignore"))
    if end_num < 4000: nav.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page+1}"))
    keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(get_text(user_id, "done_btn"), callback_data="done")])
    
    msg = get_text(user_id, "choose_num", start=start_num, end=end_num)
    if update.callback_query: 
        try:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    return PICKING

async def handle_selection(update, context):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if user_id not in user_selections:
        user_selections[user_id] = []

    if query.data.startswith("page_"):
        await show_numbers_page(update, context, int(query.data.split("_")[1]))
    elif query.data.startswith("sel_"):
        num = int(query.data.split("_")[1])
        if num > 4000: return
        
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

        total_amount = len(nums) * TICKET_PRICE
        user_info = all_user_details.get(user_id, {"name": "Gashaye User", "phone": "0911000000"})
        
        # --- Chapa API Integration ---
        chapa_url = "https://api.chapa.co/v1/transaction/initialize"
        # እዚህ ጋር የዘፈቀደ ቁጥር (random int) ተጨምሯል እንዳይደጋገም
        tx_ref = f"lottery-{user_id}-{int(datetime.now().timestamp())}-{random.randint(1000, 9999)}"
        
        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "amount": str(total_amount),
            "currency": "ETB",
            "email": f"user_{user_id}@lottery.com",
            "first_name": user_info.get('name', 'User').split()[0],
            "last_name": "Lottery",
            "phone_number": user_info.get('phone', '0911000000'),
            "tx_ref": tx_ref,
            "return_url": "https://t.me/" + (await context.bot.get_me()).username
        }
        
        checkout_url = None
        try:
            response = requests.post(chapa_url, json=payload, headers=headers)
            res_data = response.json()
            if res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
        except Exception as e:
            logger.error(f"Chapa Connection Error: {e}")
            
        success_msg = get_text(user_id, "success_reg", count=len(nums), total=total_amount)
        pay_keyboard = [[InlineKeyboardButton("💳 በቻፓ (Chapa) ክፍያ ይፈጽሙ", url=checkout_url)]] if checkout_url else [[InlineKeyboardButton("❌ የክፍያ ሊንክ ማመንጨት አልተቻለም", callback_data="ignore")]]
            
        await query.message.reply_text(success_msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(pay_keyboard))
        return ConversationHandler.END

if __name__ == '__main__':
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("^/start$"), start),
            CallbackQueryHandler(ask_name, pattern="start_reg")
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], 
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)], 
            CITY: [CallbackQueryHandler(get_city, pattern="city_")],
            OTHER_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_other_city)],
            PICKING: [CallbackQueryHandler(handle_selection, pattern="^(page_|sel_|done)")]
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    
    telegram_app.add_handlers([
        conv_handler,
        CallbackQueryHandler(set_language, pattern="^lang_"),
        CommandHandler("setprice", set_price),
        CommandHandler("setcountdown", set_date),
        CommandHandler("stats", check_stats),
        CommandHandler("users", list_users),
        CommandHandler("draw", draw_logtery),
        CallbackQueryHandler(handle_draw_confirmation, pattern="^draw_tier_"),
        CommandHandler("reset_lottery", reset_lottery),
    ])
    
    RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL")
    port = int(os.environ.get("PORT", 8080))
    
    if RENDER_URL:
        webhook_url = f"{RENDER_URL.rstrip('/')}/{BOT_TOKEN}"
        telegram_app.run_webhook(listen="0.0.0.0", port=port, url_path=BOT_TOKEN, webhook_url=webhook_url)
    else:
        telegram_app.run_polling()
