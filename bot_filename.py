import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, PhotoSize
import aiohttp
from aiohttp import web

# ----------------- CONFIGURATIONS -----------------
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5351353727"))
CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY", "").strip()
CHAPA_PUBLIC_KEY = os.getenv("CHAPA_PUBLIC_KEY", "").strip()

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

CHANNEL_USERNAME = "@Hamisalomi_bot_official" 
CHANNEL_ID = -1002345678901 
TUTORIAL_VIDEO_URL = "https://t.me/Hamisalomi_bot_official"

# የሳክሰስ ፎቶ ሊንክ (የእርስዎ ፎቶ)
WELCOME_PHOTO_URL = "https://i.ibb.co/3m3v331/success-image.jpg"

# ----------------- BANK & PAYMENT DETAILS -----------------
ACCOUNT_HOLDER = "ጋሻዬ በጅጉ ሄሬጎ (Gashaye Bejigu Herego)"
BANK_DETAILS_TEXT = (
    f"🏦 <b>━━━━━━━━━━━━━━━━━━━</b>\n"
    f"🌟 <b>የባንክ እና የሞባይል ቦርሳ መረጃዎች / Bank Details</b>\n"
    f"🏦 <b>━━━━━━━━━━━━━━━━━━━</b>\n"
    f"👤 <b>የሂሳብ ባለቤት / Account Holder:</b> {ACCOUNT_HOLDER}\n\n"
    f"• <b>የኢትዮጵያ ንግድ ባንክ (CBE):</b> <code>1000070780201</code>\n"
    f"• <b>ቴሌብር (Telebirr):</b> <code>0916039015</code>\n"
    f"• <b>ሲቢኢ ብር (CBE Birr):</b> <code>0916039015</code>\n"
    f"• <b>አቢሲኒያ ባንክ (Bank of Abyssinia):</b> <code>54071628</code>\n"
    f"• <b>ንብ ባንክ (Nib Bank):</b> <code>7000007057569</code>\n"
    f"• <b>አዋሽ ባንክ (Awash Bank):</b> <code>01325229622800</code>\n"
    f"• <b>ዳሽን ባንክ (Dashen Bank):</b> <code>5121355033201</code>\n\n"
    f"⚠️ <i>ገንዘብ ካስተላለፉ በኋላ የክፍያ መግለጫውን ወይም የደረሰኝ ፎቶ (Screenshot) በዚህ ቦት ይላኩ!</i>"
)

logging.basicConfig(level=logging.INFO)
router = Router()

# ----------------- STATES -----------------
class AdminConfig(StatesGroup):
    waiting_for_price = State()
    waiting_for_commission = State()
    waiting_for_coin_price = State()
    waiting_for_support_phone = State()

class UserProfileSetup(StatesGroup):
    waiting_for_phone = State()
    waiting_for_payment_info = State()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

class DepositStates(StatesGroup):
    waiting_for_amount = State()

class ManualPaymentStates(StatesGroup):
    waiting_for_receipt = State()

class P2PTransferStates(StatesGroup):
    waiting_for_recipient = State()
    waiting_for_amount = State()

class ServiceOrderStates(StatesGroup):
    waiting_for_detail = State()

class CoinTradeStates(StatesGroup):
    waiting_for_buy_amount = State()
    waiting_for_sell_amount = State()

# ----------------- DATABASE SETUP -----------------
def init_db():
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        default_settings = [
            ('package_price', '500.0'),
            ('commission_percent', '10.0'),
            ('lomi_coin_price', '10.0'),
            ('tutorial_link', TUTORIAL_VIDEO_URL),
            ('transfer_fee_percent', '2.0'),
            ('withdraw_fee_percent', '5.0'),
            ('support_phone', '0916039015')
        ]
        for k, v in default_settings:
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                fullname TEXT,
                referrer_id INTEGER,
                parent_id INTEGER,
                position TEXT,
                is_active INTEGER DEFAULT 0,
                balance REAL DEFAULT 0.0,
                coin_balance REAL DEFAULT 0.0,
                phone_number TEXT,
                payment_account TEXT,
                wallet_id TEXT UNIQUE,
                is_blocked INTEGER DEFAULT 0,
                lang TEXT DEFAULT 'am'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_ref TEXT PRIMARY KEY,
                user_id INTEGER,
                amount REAL,
                status TEXT DEFAULT 'PENDING',
                type TEXT DEFAULT 'PACKAGE'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                photo_id TEXT,
                payment_type TEXT DEFAULT 'PACKAGE',
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                fee REAL,
                net_amount REAL,
                account_info TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service_type TEXT,
                detail TEXT,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

init_db()

def get_setting(key, default_type=float):
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
    if row:
        if default_type == int:
            return int(float(row[0]))
        elif default_type == str:
            return str(row[0])
        return default_type(row[0])
    return "" if default_type == str else default_type(0)

def set_setting(key, value):
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()

def get_user(user_id):
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    return user

def get_user_by_wallet(wallet_id):
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE wallet_id = ?", (wallet_id.strip(),))
        user = cursor.fetchone()
    return user

def register_pending_user(user_id, username, fullname, referrer_id):
    wallet_id = f"W{user_id}"
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, fullname, referrer_id, is_active, wallet_id, is_blocked, lang) 
            VALUES (?, ?, ?, ?, 0, ?, 0, 'am')
        """, (user_id, username, fullname, referrer_id, wallet_id))
        conn.commit()

# ----------------- TRANSLATIONS DICTIONARY -----------------
TEXTS = {
    'am': {
        'welcome': "ሰላም <b>{}</b>!\n\nእንኳን ወደ 50 ሎሚ በደህና መጡ፤ <b>በጋራ እንበለጽጋለን!</b> 🤝🍋\n\nየአሁኑ የፓኬጅ ዋጋ: <b>{} ETB</b>\nየስራ ኮሚሽን: <b>{}%</b>\n🪙 <b>የ 1 ሎሚ ኮይን ገበያ ዋጋ: {} ETB</b>\n\nከታች ካሉት አማራጮች ውስጥ የሚፈልጉትን መምረጥ ይችላሉ።",
        'lomi_market': "🪙 ሎሚ ኮይን ግይድ/ሽያጭ (Lomi Market)",
        'payment_options': "💳 ፓኬጅ ይግዙ (Chapa & Manual)",
        'wallet_deposit': "📥 ገንዘብ ወደ ዋሌት ጫን (Deposit)",
        'my_account': "📊 የኔ ዋሌት እና አካውንት (Wallet)",
        'digital_services': "🛒 የዲጂታል አገልግሎቶች (Mobile & Ads)",
        'customer_support': "📞 Customer Support & Banks",
        'bot_about': "ℹ️ ስለ 50 ሎሚ እና አሰራር (About)",
        'tutorial_video': "🎬 አጠቃቀም ቪዲዮ መመሪያ (Tutorial)",
        'admin_panel': "⚙️ አድሚን ፓነል (Admin Settings)",
        'change_lang': "🌐 Change Language / ቋንቋ ቀይር",
        'back': "⬅️ ወደ ዋናው ምናሌ",
        'bot_link': "🤖 ቦት ሊንክ",
        'channel': "📢 50 ሎሚ ቻናል"
    },
    'en': {
        'welcome': "Hello <b>{}</b>!\n\nWelcome to 50 Lomi; <b>Together We Prosper!</b> 🤝🍋\n\nPackage Price: <b>{} ETB</b>\nCommission: <b>{}%</b>\n🪙 <b>1 Lomi Coin Price: {} ETB</b>\n\nChoose an option below to get started.",
        'lomi_market': "🪙 Lomi Coin Market",
        'payment_options': "💳 Buy Package (Chapa & Manual)",
        'wallet_deposit': "📥 Wallet Deposit",
        'my_account': "📊 My Wallet & Account",
        'digital_services': "🛒 Digital Services (Mobile & Ads)",
        'customer_support': "📞 Customer Support & Banks",
        'bot_about': "ℹ️ About 50 Lomi",
        'tutorial_video': "🎬 Tutorial Video",
        'admin_panel': "⚙️ Admin Panel",
        'change_lang': "🌐 ቋንቋ መቀየሪያ (Amharic)",
        'back': "⬅️ Main Menu",
        'bot_link': "🤖 Bot Link",
        'channel': "📢 Official Channel"
    }
}

def get_user_lang(user_id):
    user = get_user(user_id)
    if user and len(user) > 13 and user[13]:
        return user[13]
    return 'am'

# ----------------- MATRIX & REFERRAL LOGIC -----------------
async def activate_user_in_matrix(user_id, bot: Bot):
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT is_active, referrer_id, fullname FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        if not res or res[0] == 1:
            return False
        
        raw_referrer_id = res[1]
        user_fullname = res[2]
        
        target_commission_user = ADMIN_ID
        if raw_referrer_id and raw_referrer_id != ADMIN_ID:
            cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ? AND is_active = 1", (raw_referrer_id,))
            direct_count = cursor.fetchone()[0]
            
            if direct_count < 10:
                target_commission_user = raw_referrer_id
            else:
                target_commission_user = ADMIN_ID
        
        effective_parent_id = get_effective_parent_for_matrix(raw_referrer_id if raw_referrer_id else ADMIN_ID)
        parent_id, position = find_available_position_under(effective_parent_id)
        
        package_price = get_setting('package_price', float)
        commission_percent = get_setting('commission_percent', float)
        commission_amount = package_price * (commission_percent / 100.0)
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (commission_amount, target_commission_user))
        cursor.execute("""
            UPDATE users SET parent_id = ?, position = ?, is_active = 1 WHERE user_id = ?
        """, (parent_id, position, user_id))
        conn.commit()

    try:
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        channel_text = (
            f"🌐 <b>የ 50 ሎሚ ኦፊሻል ማህበረሰብ ዜና</b>\n\n"
            f"🎉 <b>አዲስ ንቁ አባል በጋራ ብልጽግና መድረክ ተመዝግቧል!</b>\n\n"
            f"👤 ስም: <b>{user_fullname}</b>\n"
            f"🚀 50 ሎሚ ቦት - በጋራ እናድጋለን፣ በጋራ እንበለጽጋለን!\n\n"
            f"እርስዎም አሁኑኑ በመግባት የራስዎን ገቢ መገንባት ይጀምሩ፦\n"
            f"👉 ቦት ሊንክ: https://t.me/{bot_username}\n"
            f"📢 ቻናል: https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
        )
        channel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🤖 ቦቱን ለመቀላቀል እዚህ ይጫኑ", url=f"https://t.me/{bot_username}")],
            [InlineKeyboardButton(text="📢 50 ሎሚ ኦፊሻል ቻናል", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]
        ])
        await bot.send_message(CHANNEL_ID, channel_text, reply_markup=channel_keyboard, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send channel notification: {e}")

    return True

def get_effective_parent_for_matrix(referrer_id):
    if not referrer_id:
        return ADMIN_ID
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE parent_id = ? AND is_active = 1", (referrer_id,))
        count = cursor.fetchone()[0]
    
    if count >= 10:
        return find_available_matrix_parent()
    return referrer_id

def find_available_matrix_parent():
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        queue = [ADMIN_ID]
        while queue:
            current_id = queue.pop(0)
            cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'LEFT' AND is_active = 1", (current_id,))
            left_child = cursor.fetchone()
            if not left_child:
                return current_id
            else:
                queue.append(left_child[0])
                
            cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'RIGHT' AND is_active = 1", (current_id,))
            right_child = cursor.fetchone()
            if not right_child:
                return current_id
            else:
                queue.append(right_child[0])
    return ADMIN_ID

def find_available_position_under(start_user_id):
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        queue = [start_user_id]
        while queue:
            current_id = queue.pop(0)
            cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'LEFT'", (current_id,))
            if not cursor.fetchone():
                return current_id, 'LEFT'
            
            cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'RIGHT'", (current_id,))
            if not cursor.fetchone():
                return current_id, 'RIGHT'
                
            cursor.execute("SELECT user_id FROM users WHERE parent_id = ? ORDER BY position", (current_id,))
            for child in cursor.fetchall():
                queue.append(child[0])
    return start_user_id, 'LEFT'

# ----------------- BOT HANDLERS -----------------
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        await state.clear()
    except Exception:
        pass

    user = get_user(message.from_user.id)
    if user and user[12] == 1:
        await message.answer("❌ አካውንትዎ በአድሚን ታግዷል። (Account Blocked)")
        return

    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    if not user:
        register_pending_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.full_name or "User",
            referrer_id
        )
        user = get_user(message.from_user.id)

    lang_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="አማርኛ 🇪🇹", callback_data="lang_am"),
            InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en")
        ]
    ])
    
    caption_text = (
        f"ሰላም <b>{message.from_user.full_name}</b>!\n\n"
        f"እንኳን ወደ 50 ሎሚ በደህና መጡ! (በጋራ እንበለጽጋለን! 🤝🍋)\n\n"
        f"እባክዎ የሚፈልጉትን ቋንቋ ይምረጡ:\n"
        f"Please choose your preferred language:"
    )

    # ቴሌግራም የማይፈቅደውን answer_photo አስወግደን በጽሁፍ ብቻ (answer) ላክን
    await message.answer(
        text=caption_text,
        reply_markup=lang_keyboard,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("lang_"))
async def language_selection_callback(callback: types.CallbackQuery, state: FSMContext):
    selected_lang = "am" if callback.data == "lang_am" else "en"
    
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (selected_lang, callback.from_user.id))
        conn.commit()

    user = get_user(callback.from_user.id)
    
    if not user[9] or not user[10]:
        await state.set_state(UserProfileSetup.waiting_for_phone)
        welcome_start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ቀጥል / Continue", callback_data="ask_phone_prompt")]
        ])
        await callback.message.edit_text(
            text="ስልክ ቁጥርዎን እና የክፍያ አካውንትዎን ለመመዝገብ እባክዎ ቀጥል የሚለውን ይጫኑ ወይም ስልክ ቁጥርዎን ይጻፉልኝ፦\n<i>(ምሳሌ: 0911223344)</i>",
            reply_markup=welcome_start_keyboard,
            parse_mode="HTML"
        )
        return

    await show_main_menu(callback, user)

@router.callback_query(F.data == "main_menu")
async def main_menu_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
    except Exception:
        pass
    user = get_user(callback.from_user.id)
    if user and user[12] == 1:
        await callback.answer("❌ አካውንትዎ በአድሚን ታግዷል።", show_alert=True)
        return

    if not user:
        register_pending_user(
            callback.from_user.id,
            callback.from_user.username or "",
            callback.from_user.full_name or "User",
            None
        )
        user = get_user(callback.from_user.id)
    await show_main_menu(callback, user)

@router.callback_query(F.data == "toggle_lang")
async def toggle_language_handler(callback: types.CallbackQuery):
    current_lang = get_user_lang(callback.from_user.id)
    new_lang = 'en' if current_lang == 'am' else 'am'
    
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (new_lang, callback.from_user.id))
        conn.commit()
    
    user = get_user(callback.from_user.id)
    await show_main_menu(callback, user)
    await callback.answer("Language Updated Successfully!")

@router.message(UserProfileSetup.waiting_for_phone)
async def process_user_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    await state.set_state(UserProfileSetup.waiting_for_payment_info)
    
    await message.answer(
        "አሪፍ! አሁን ደግሞ የገንዘብ መቀበያ አካውንትዎን (ለምሳሌ፦ <b>የቴሌብር፣ የሲቢኢ (CBE) ወይም የባንክ አካውንት ቁጥር ስምዎ ጋር</b>) በግልጽ ይጻፉልኝ፦",
        parse_mode="HTML"
    )

@router.message(UserProfileSetup.waiting_for_payment_info)
async def process_user_payment_info(message: types.Message, state: FSMContext):
    payment_info = message.text.strip()
    data = await state.get_data()
    phone = data.get("phone")
    
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET phone_number = ?, payment_account = ? WHERE user_id = ?", 
                       (phone, payment_info, message.from_user.id))
        conn.commit()
    
    await state.clear()
    user = get_user(message.from_user.id)
    await message.answer("✅ መረጃዎ በትክክል ተመዝግቧል! አሁን ወደ ዋናው ገጽ ገብተዋል፦")
    await show_main_menu(message, user)

async def show_main_menu(message_or_callback, user):
    is_admin = (message_or_callback.from_user.id == ADMIN_ID)
    lang = get_user_lang(message_or_callback.from_user.id)
    t = TEXTS[lang]
    
    bot_info = await message_or_callback.bot.get_me() if hasattr(message_or_callback, "bot") else await (message_or_callback.message.bot.get_me() if isinstance(message_or_callback, types.CallbackQuery) else None)
    bot_username = bot_info.username if bot_info else "Hamisalomi_bot"

    keyboard_buttons = [
        [InlineKeyboardButton(text=t['lomi_market'], callback_data="lomi_market")],
        [InlineKeyboardButton(text=t['payment_options'], callback_data="payment_options")],
        [InlineKeyboardButton(text=t['wallet_deposit'], callback_data="wallet_deposit")],
        [InlineKeyboardButton(text=t['my_account'], callback_data="my_account")],
        [InlineKeyboardButton(text=t['digital_services'], callback_data="digital_services")],
        [InlineKeyboardButton(text=t['customer_support'], callback_data="customer_support")],
        [InlineKeyboardButton(text=t['bot_about'], callback_data="bot_about")],
        [InlineKeyboardButton(text=t['tutorial_video'], callback_data="tutorial_video")],
        [InlineKeyboardButton(text=t['change_lang'], callback_data="toggle_lang")],
        [
            InlineKeyboardButton(text=t['bot_link'], url=f"https://t.me/{bot_username}"),
            InlineKeyboardButton(text=t['channel'], url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
        ]
    ]
    
    if is_admin:
        keyboard_buttons.append([InlineKeyboardButton(text=t['admin_panel'], callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    current_price = get_setting('package_price', float)
    current_commission = get_setting('commission_percent', float)
    coin_price = get_setting('lomi_coin_price', float)
    
    welcome_text = t['welcome'].format(message_or_callback.from_user.full_name, current_price, current_commission, coin_price)
    
    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_text(welcome_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await message_or_callback.message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")
        try:
            await message_or_callback.answer()
        except Exception:
            pass
    else:
        await message_or_callback.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

# ----------------- PAYMENT OPTIONS -----------------
@router.callback_query(F.data == "payment_options")
async def payment_options_menu(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 በቻፓ (Chapa) በኦንላይን ይክፈሉ", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="🏦 በባንክ / በሞባይል ቦርሳ (Manual Payment)", callback_data="manual_payment_start")],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
    ])
    text = (
        f"💳 <b>━━━━━━━━━━━━━━━━━━━</b>\n"
        f"🌟 <b>የክፍያ አማራጮች / Payment Options</b>\n"
        f"💳 <b>━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"ፓኬጅዎን ለማግበር ከታሉት ሁለት መንገዶች አንዱን መምረጥ ይችላሉ፦\n\n"
        f"1. <b>በቻፓ (Chapa):</b> በካርድ ወይም በባንክ በኦንላይን ወዲያውኑ ይክፈሉና በራስ-ሰር ይ aktivate ይሆናል።\n"
        f"2. <b>በማኑዋል (Manual):</b> ከታች ባሉት የባንክ ቁጥሮች ገንዘብ አስተላልፈው ደረሰኝ (Screenshot) በመላክ በአድሚን ያስረግጣሉ።"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ----------------- MANUAL PAYMENT & RECEIPT -----------------
@router.callback_query(F.data == "manual_payment_start")
async def manual_payment_start(callback: types.CallbackQuery, state: FSMContext):
    package_price = get_setting('package_price', float)
    await state.set_state(ManualPaymentStates.waiting_for_receipt)
    await state.update_data(payment_type="PACKAGE", amount=package_price)
    
    text = (
        f"{BANK_DETAILS_TEXT}\n\n"
        f"📌 <b>የሚከፈለው መጠን / Amount:</b> <b>{package_price} ETB (ፓኬጅ ማግበር)</b>\n\n"
        f"እባክዎ ከላይ በተዘረዘሩት የባንክ አካውንቶች ገንዘቡን ካስተላለፉ በኋላ **የክፍያውን ደረሰኝ ፎቶ (Screenshot)** በዚህ ቦት ላይ ይላኩላቸው፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ ተመለስ / Back", callback_data="payment_options")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(ManualPaymentStates.waiting_for_receipt, F.photo)
async def process_manual_receipt(message: types.Message, state: FSMContext):
    photo: PhotoSize = message.photo[-1]
    photo_id = photo.file_id
    user_id = message.from_user.id
    
    data = await state.get_data()
    amount = data.get("amount", get_setting('package_price', float))
    pay_type = data.get("payment_type", "PACKAGE")

    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO manual_payments (user_id, amount, photo_id, payment_type, status) VALUES (?, ?, ?, ?, 'PENDING')",
                       (user_id, amount, photo_id, pay_type))
        mp_id = cursor.lastrowid
        conn.commit()

    await state.clear()

    try:
        admin_text = (
            f"🔔 <b>አዲስ የማኑዋል ክፍያ ማረጋገጫ ደረሰኝ!</b>\n\n"
            f"👤 ተጠቃሚ: {message.from_user.full_name} (ID: <code>{user_id}</code>)\n"
            f"💰 መጠን: <b>{amount} ETB</b>\n"
            f"🏷️ ዓይነት: <b>{pay_type}</b>"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ አጽድቅ (Approve)", callback_data=f"app_mp_{mp_id}"),
                InlineKeyboardButton(text="❌ ሰርዝ (Cancel)", callback_data=f"canc_mp_{mp_id}")
            ],
            [
                InlineKeyboardButton(text="🚫 ተጠቃሚውን አግድ (Block)", callback_data=f"block_usr_{user_id}_{mp_id}")
            ]
        ])
        await message.bot.send_photo(ADMIN_ID, photo=photo_id, caption=admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send manual payment to admin: {e}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 ዋና ገጽ / Main Menu", callback_data="main_menu")]])
    await message.answer(
        "✅ <b>ደረሰኝዎ በትክክል ተልኳል!</b>\n\n"
        "አድሚኑ ደረሰኙን አረጋግጦ ጥያቄዎን በቅርቡ ያቀናብርልዎታል። እናመሰግናለን!",
        reply_markup=keyboard, parse_mode="HTML"
    )

@router.message(ManualPaymentStates.waiting_for_receipt)
async def process_manual_receipt_wrong_format(message: types.Message):
    await message.answer("❌ እባክዎ የክፍያውን ደረሰኝ **ፎቶ (Screenshot)** ብቻ ይላኩላት።")

@router.callback_query(F.data.startswith("app_mp_"))
async def approve_manual_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    mp_id = int(callback.data.split("_")[2])
    
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount, payment_type, status FROM manual_payments WHERE id = ?", (mp_id,))
        row = cursor.fetchone()
        
        if not row or row[3] == 'APPROVED':
            await callback.answer("❌ ይህ ክፍያ ቀድሞውኑ ጸድቋል ወይም አልተገኘም!", show_alert=True)
            return

        user_id, amount, pay_type = row[0], row[1], row[2]
        cursor.execute("UPDATE manual_payments SET status = 'APPROVED' WHERE id = ?", (mp_id,))
        
        if pay_type == 'DEPOSIT':
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

    if pay_type == 'PACKAGE':
        await activate_user_in_matrix(user_id, callback.bot)
    
    try:
        msg_text = f"🎉 <b>እንኳን ደስ አለዎት! የማኑዋል ክፍያዎ ({amount} ETB) በአድሚን ጸድቋል።</b>"
        if pay_type == 'DEPOSIT':
            msg_text += f"\n💰 {amount} ETB ወደ ዋሌትዎ ገብቷል!"
        else:
            msg_text += "\n🚀 አካውንትዎ ንቁ (Active) ሆኗል!"
            
        await callback.bot.send_message(user_id, msg_text, parse_mode="HTML")
    except Exception:
        pass

    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption or ''}\n\n✅ <b> በአድሚን ጸድቋል!</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("ክፍያው ጸድቋል!")

@router.callback_query(F.data.startswith("canc_mp_"))
async def cancel_manual_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    mp_id = int(callback.data.split("_")[2])
    
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, amount, status FROM manual_payments WHERE id = ?", (mp_id,))
        row = cursor.fetchone()
        
        if not row or row[2] == 'CANCELLED':
            await callback.answer("❌ ቀድሞውኑ ተሰርዟል!", show_alert=True)
            return

        user_id, amount = row[0], row[1]
        cursor.execute("UPDATE manual_payments SET status = 'CANCELLED' WHERE id = ?", (mp_id,))
        conn.commit()

    try:
        await callback.bot.send_message(user_id, f"❌ <b>የላኩት የማኑዋል ክፍያ ደረሰኝ ({amount} ETB) በአድሚን ውድቅ ተደርጓል (ተሰርዟል)።</b>", parse_mode="HTML")
    except Exception:
        pass

    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption or ''}\n\n❌ <b> ተሰርዟል (Cancelled)!</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("ክፍያው ተሰርዟል!")

@router.callback_query(F.data.startswith("block_usr_"))
async def block_user_action(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    parts = callback.data.split("_")
    user_id = int(parts[2])
    mp_id = int(parts[3])

    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
        cursor.execute("UPDATE manual_payments SET status = 'BLOCKED' WHERE id = ?", (mp_id,))
        conn.commit()

    try:
        await callback.bot.send_message(user_id, "🚫 <b>አካውንትዎ በአድሚን ታግዷል። (Account Blocked)</b>", parse_mode="HTML")
    except Exception:
        pass

    try:
        await callback.message.edit_caption(
            caption=f"{callback.message.caption or ''}\n\n🚫 <b>ተጠቃሚው በአድሚን ታግዷል (Blocked)!</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("ተጠቃሚው ታግዷል!")

# ----------------- LOMI COIN MARKET -----------------
@router.callback_query(F.data == "lomi_market")
async def lomi_market_menu(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[12] == 1:
        await callback.answer("❌ አካውንትዎ ታግዷል።", show_alert=True)
        return

    coin_price = get_setting('lomi_coin_price', float)
    balance = user[7] if user else 0.0
    coin_balance = user[8] if user else 0.0

    text = (
        f"🪙 <b>━━━━━━━━━━━━━━━━━━━</b>\n"
        f"🌟 <b>የሎሚ ኮይን ገበያ / Lomi Coin Market</b>\n"
        f"🪙 <b>━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"• የ 1 ሎሚ ኮይን ወቅታዊ ዋጋ: <b>{coin_price} ETB</b>\n"
        f"• የእርስዎ የብር ቀሪ ሂሳብ: <b>{balance} ETB</b>\n"
        f"• የእርስዎ የሎሚ ኮይን ብዛት: <b>{coin_balance} ሎሚ ኮይን</b>\n\n"
        f"ሎሚ ኮይን በመግዛት ዋጋው ሲጨምር ማትረፍ ወይም ኮይኖቹን ሸጠው ወደ ብር መቀየር ይችላሉ። ምን ማድረግ ይፈልጋሉ?"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📥 ሎሚ ኮይን ይግዙ (Buy)", callback_data="buy_coin_start"),
            InlineKeyboardButton(text="📤 ሎሚ ኮይን ይሽጡ (Sell)", callback_data="sell_coin_start")
        ],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "buy_coin_start")
async def buy_coin_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    coin_price = get_setting('lomi_coin_price', float)
    
    await state.set_state(CoinTradeStates.waiting_for_buy_amount)
    text = (
        f"📥 <b>ሎሚ ኮይን መግዛት (Buy Lomi Coin)</b>\n\n"
        f"• የ 1 ሎሚ ኮይን ዋጋ: <b>{coin_price} ETB</b>\n"
        f"• የዋሌት ቀሪ ሂሳብዎ: <b>{user[7]} ETB</b>\n\n"
        f"መግዛት የሚፈልጉትን የ **ሎሚ ኮይን ብዛት** ጻፉልኝ፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lomi_market")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(CoinTradeStates.waiting_for_buy_amount)
async def process_buy_coin(message: types.Message, state: FSMContext):
    try:
        coins_to_buy = float(message.text.strip())
        if coins_to_buy <= 0: raise ValueError()
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")
        return

    user = get_user(message.from_user.id)
    coin_price = get_setting('lomi_coin_price', float)
    total_cost = coins_to_buy * coin_price

    if total_cost > user[7]:
        await message.answer(
            f"❌ በዋሌትዎ ውስጥ በቂ ብር የለም።\n"
            f"• የሚያስፈልገው: <b>{total_cost} ETB</b>\n"
            f"• ያለዎት: <b>{user[7]} ETB</b>",
            parse_mode="HTML"
        )
        return

    await state.clear()
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - ?, coin_balance = coin_balance + ? WHERE user_id = ?",
                       (total_cost, coins_to_buy, message.from_user.id))
        conn.commit()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 ወደ ሎሚ ገበያ ተመለስ", callback_data="lomi_market")]
    ])
    await message.answer(
        f"🎉 <b>ግዢው ተሳክቷል!</b>\n\n"
        f"• የገዙት ኮይን: <b>{coins_to_buy} ሎሚ ኮይን</b>\n"
        f"• የተቆረጠብዎት ብር: <b>{total_cost} ETB</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )

@router.callback_query(F.data == "sell_coin_start")
async def sell_coin_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    coin_price = get_setting('lomi_coin_price', float)
    
    await state.set_state(CoinTradeStates.waiting_for_sell_amount)
    text = (
        f"📤 <b>ሎሚ ኮይን መሸጥ (Sell Lomi Coin)</b>\n\n"
        f"• የ 1 ሎሚ ኮይን ወቅታዊ ዋጋ: <b>{coin_price} ETB</b>\n"
        f"• የእርስዎ የኮይን ቀሪ ሂሳብ: <b>{user[8]} ሎሚ ኮይን</b>\n\n"
        f"መሸጥ የሚፈልጉትን የ **ኮይን ብዛት** ጻፉልኝ፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data="lomi_market")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(CoinTradeStates.waiting_for_sell_amount)
async def process_sell_coin(message: types.Message, state: FSMContext):
    try:
        coins_to_sell = float(message.text.strip())
        if coins_to_sell <= 0: raise ValueError()
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ያስገቡ።")
        return

    user = get_user(message.from_user.id)
    coin_balance = user[8]
    coin_price = get_setting('lomi_coin_price', float)

    if coins_to_sell > coin_balance:
        await message.answer(f"❌ በቂ ኮይን የለዎትም (ያለዎት: {coin_balance})።")
        return

    await state.clear()
    earned_birr = coins_to_sell * coin_price

    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET coin_balance = coin_balance - ?, balance = balance + ? WHERE user_id = ?",
                       (coins_to_sell, earned_birr, message.from_user.id))
        conn.commit()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪙 ወደ ሎሚ ገበያ ተመለስ", callback_data="lomi_market")]
    ])
    await message.answer(
        f"🎉 <b>ሽያጩ ተሳክቷል!</b>\n\n"
        f"• የተሸጠው ኮይን: <b>{coins_to_sell} ሎሚ ኮይን</b>\n"
        f"• ያገኙት ገንዘብ: <b>{earned_birr} ETB</b>",
        reply_markup=keyboard, parse_mode="HTML"
    )

# ----------------- CHAPA & WEBHOOK -----------------
@router.callback_query(F.data == "pay_chapa")
async def pay_chapa_package(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    if not user:
        await callback.answer("እባክዎ መጀመሪያ /start ይጫኑ።", show_alert=True)
        return

    if user[6] == 1:
        await callback.answer("✅ አካውንትዎ ቀድሞውኑ ገብቷል (Active ነው)!", show_alert=True)
        return

    package_price = get_setting('package_price', float)
    tx_ref = f"pkg-{user_id}-{int(asyncio.get_event_loop().time())}"

    base_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://your-app.onrender.com"
    callback_url = f"{base_url}/chapa-webhook"

    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}", "Content-Type": "application/json"}
    payload = {
        "amount": str(package_price), "currency": "ETB", "email": f"user{user_id}@gmail.com",
        "first_name": callback.from_user.first_name or "User", "last_name": "Lomi",
        "tx_ref": tx_ref, "callback_url": callback_url,
        "return_url": f"https://t.me/{(await callback.bot.get_me()).username}",
        "customization[title]": "50 Lomi Package Activation"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                
                with sqlite3.connect("binary_mlm.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR REPLACE INTO transactions (tx_ref, user_id, amount, status, type) VALUES (?, ?, ?, 'PENDING', 'PACKAGE')",
                                   (tx_ref, user_id, package_price))
                    conn.commit()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 በቻፓ (Chapa) ክፍያ ይፈጽሙ", url=checkout_url)],
                    [InlineKeyboardButton(text="🔄 ክፍያ ከፈጸሙ በኋላ ያረጋግጡ", callback_data=f"verify_pkg_{tx_ref}")],
                    [InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
                ])
                try:
                    await callback.message.edit_text(
                        text=f"💳 <b>የፓኬጅ ክፍያ ማገናኛ ተዘጋጅቷል! (መጠን: {package_price} ETB)</b>",
                        reply_markup=keyboard, parse_mode="HTML"
                    )
                except Exception:
                    await callback.message.answer(f"💳 <b>የፓኬጅ ክፍያ ማገናኛ ተዘጋጅቷል!</b>", reply_markup=keyboard, parse_mode="HTML")
            else:
                await callback.answer("❌ የክፍያ ሊንክ መፍጠር አልተቻለም።", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("verify_pkg_"))
async def verify_package_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_", 2)[2]
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, user_id FROM transactions WHERE tx_ref = ?", (tx_ref,))
        tx_row = cursor.fetchone()

    if not tx_row:
        await callback.answer("❌ የግብይት መረጃ አልተገኘም።", show_alert=True)
        return
    db_status, user_id = tx_row

    if db_status == 'SUCCESS':
        await callback.answer("✅ ክፍያዎ ቀድሞውኑ ተረጋግጧል!", show_alert=True)
        return

    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success" and res_data.get("data", {}).get("status") == "success":
                with sqlite3.connect("binary_mlm.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                    conn.commit()

                await activate_user_in_matrix(user_id, callback.bot)
                await callback.answer("✅ ክፍያዎ ተረጋግጧል እና አካውንትዎ ገብቷል!", show_alert=True)
            else:
                await callback.answer("❌ ክፍያዎ ገና በባንክ አልተረጋገጠም።", show_alert=True)
    await callback.answer()

# ----------------- CUSTOMER SUPPORT & BANKS -----------------
@router.callback_query(F.data == "customer_support")
async def customer_support_handler(callback: types.CallbackQuery):
    support_phone = get_setting('support_phone', str) or "0916039015"
    text = (
        f"📞 <b>የደንበኞች ድጋፍ እና የባንክ መረጃዎች</b>\n\n"
        f"• የድጋፍ ስልክ ቁጥር: <code>{support_phone}</code>\n"
        f"• ቻናል: https://t.me/{CHANNEL_USERNAME.replace('@', '')}\n\n"
        f"{BANK_DETAILS_TEXT}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ----------------- DIGITAL SERVICES -----------------
@router.callback_query(F.data == "digital_services")
async def digital_services_menu(callback: types.CallbackQuery):
    support_phone = get_setting('support_phone', str) or "0916039015"
    text = (
        f"🛒 <b>የዲጂታል አገልግሎቶች ማዕከል</b> (50 ሎሚ)\n\n"
        f"1️⃣ <b>Cell Phone Airtime</b>\n"
        f"2️⃣ <b>የቴሌግራም ፕሪሚየም (Telegram Premium)</b>\n"
        f"3️⃣ <b>የቲክቶክ እና ቴሌግራም ማስታወቂያዎች (Ads)</b>\n\n"
        f"አገልግሎቱን ለማግኘት የገንዘብ ማስተላለፊያ ቁጥር: <b>{support_phone}</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Airtime", callback_data="srv_airtime"), InlineKeyboardButton(text="⭐ Telegram Premium", callback_data="srv_tg_prem")],
        [InlineKeyboardButton(text="📢 Ads", callback_data="srv_ads")],
        [InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.in_({"srv_airtime", "srv_tg_prem", "srv_ads"}))
async def service_order_prompt(callback: types.CallbackQuery, state: FSMContext):
    service_names = {
        "srv_airtime": "Cell Phone Airtime",
        "srv_tg_prem": "የቴሌግራም ፕሪሚየም",
        "srv_ads": "የማስታወቂያ (Ads) አገልግሎት"
    }
    s_title = service_names.get(callback.data, "ዲጂታል አገልግሎት")
    await state.update_data(service_type=s_title)
    await state.set_state(ServiceOrderStates.waiting_for_detail)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="digital_services")]])
    await callback.message.edit_text(
        text=f"🛒 <b>{s_title}</b>\n\nእባክዎ ለዚህ አገልግሎት የሚፈልጉትን ዝርዝር (ስልክ ቁጥር ወይም ሊንክ) ጻፉልኝ፦",
        reply_markup=keyboard, parse_mode="HTML"
    )
    await callback.answer()

@router.message(ServiceOrderStates.waiting_for_detail)
async def process_service_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    s_type = data.get("service_type")
    detail = message.text.strip()
    user_id = message.from_user.id
    await state.clear()

    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO service_orders (user_id, service_type, detail, status) VALUES (?, ?, ?, 'PENDING')",
                       (user_id, s_type, detail))
        order_id = cursor.lastrowid
        conn.commit()

    try:
        admin_text = f"🔔 <b>አዲስ የዲጂታል አገልግሎት ትዕዛዝ!</b>\n👤 ተጠቃሚ: {message.from_user.full_name}\n📦 አገልግሎት: {s_type}\n📝 ዝርዝር:\n{detail}"
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ አጽድቅ", callback_data=f"app_srv_{order_id}")]])
        await message.bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")]])
    await message.answer("✅ ትዕዛዝዎ ተቀባይነት አግኝቷል! አድሚኑ አረጋግጦ ይፈጽምልዎታል።", reply_markup=keyboard)

@router.callback_query(F.data.startswith("app_srv_"))
async def approve_service_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    order_id = int(callback.data.split("_")[2])
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, service_type FROM service_orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE service_orders SET status = 'APPROVED' WHERE id = ?", (order_id,))
            conn.commit()
            try:
                await callback.bot.send_message(row[0], f"🎉 <b>የጠየቁት አገልግሎት ({row[1]}) ጸድቆ ተፈጽሟል!</b>", parse_mode="HTML")
            except Exception:
                pass
    await callback.answer("ጸድቋል!")

# ----------------- WALLET DEPOSIT -----------------
@router.callback_query(F.data == "wallet_deposit")
async def wallet_deposit_start(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 በቻፓ (Chapa) በኦንላይን ጫን", callback_data="deposit_chapa")],
        [InlineKeyboardButton(text="🏦 በባንክ ደረሰኝ (Manual Deposit)", callback_data="deposit_manual")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text="📥 <b>ገንዘብ ወደ ዋሌት ጫን (Deposit Options)</b>\n\nገንዘብ መሙላት የሚፈልጉበትን መንገድ ይምረጡ፦", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "deposit_chapa")
async def deposit_chapa_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_amount)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="wallet_deposit")]])
    await callback.message.edit_text(text="📥 <b>በቻፓ ገንዘብ ማከማቸት</b>\n\nማስገባት የሚፈልጉትን የብር መጠን (ETB) ጻፉልኝ፦", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "deposit_manual")
async def deposit_manual_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_amount)
    await state.update_data(is_manual_deposit=True)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="wallet_deposit")]])
    await callback.message.edit_text(text="📥 <b>በባንክ ዴፖዚት ማድረግ</b>\n\nወደ ባንክ አካውንታችን ያስተላለፉትን **የብር መጠን (ETB)** ጻፉልኝ፦", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(DepositStates.waiting_for_amount)
async def process_wallet_deposit(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError()
    except ValueError:
        await message.answer("❌ ትክክለኛ የብር መጠን ያስገቡ።")
        return

    data = await state.get_data()
    is_manual = data.get("is_manual_deposit", False)
    await state.clear()

    if is_manual:
        await state.set_state(ManualPaymentStates.waiting_for_receipt)
        await state.update_data(payment_type="DEPOSIT", amount=amount)
        await message.answer(
            f"{BANK_DETAILS_TEXT}\n\n"
            f"📌 <b>የጠየቁት የዲፖዚት መጠን:</b> <b>{amount} ETB</b>\n\n"
            f"እባክዎ ገንዘቡን ከላኩ በኋላ **የባንኩን የክፍያ ደረሰኝ ፎቶ (Screenshot)** በዚህ ቦት ላይ ይላኩላቸው፦"
        )
        return

    tx_ref = f"dep-{message.from_user.id}-{int(asyncio.get_event_loop().time())}"
    base_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://your-app.onrender.com"
    
    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}", "Content-Type": "application/json"}
    payload = {
        "amount": str(amount), "currency": "ETB", "email": f"user{message.from_user.id}@gmail.com",
        "first_name": message.from_user.first_name or "User", "tx_ref": tx_ref,
        "callback_url": f"{base_url}/chapa-webhook",
        "return_url": f"https://t.me/{(await message.bot.get_me()).username}",
        "customization[title]": "Wallet Deposit"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                with sqlite3.connect("binary_mlm.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR REPLACE INTO transactions (tx_ref, user_id, amount, status, type) VALUES (?, ?, ?, 'PENDING', 'DEPOSIT')",
                                   (tx_ref, message.from_user.id, amount))
                    conn.commit()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 በቻፓ ለመክፈል እዚህ ይጫኑ", url=checkout_url)],
                    [InlineKeyboardButton(text="🔄 ክፍያ ከፈጸሙ በኋላ ያረጋግጡ", callback_data=f"verify_dep_{tx_ref}")]
                ])
                await message.answer(f"💳 <b>የክፍያ ማገናኛ ተዘጋጅቷል! (መጠን: {amount} ETB)</b>", reply_markup=keyboard, parse_mode="HTML")
            else:
                await message.answer("❌ የክፍያ ሊንክ መፍጠር አልተቻለም።")

@router.callback_query(F.data.startswith("verify_dep_"))
async def verify_deposit_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_", 2)[2]
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status, user_id, amount FROM transactions WHERE tx_ref = ?", (tx_ref,))
        row = cursor.fetchone()

    if not row or row[0] == 'SUCCESS':
        await callback.answer("✅ ቀድሞውኑ ተረጋግጧል!", show_alert=True)
        return

    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success" and res_data.get("data", {}).get("status") == "success":
                with sqlite3.connect("binary_mlm.db") as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (row[2], row[1]))
                    conn.commit()
                await callback.answer(f"🎉 ክፍያዎ ተረጋግጧል! {row[2]} ETB ወደ ዋሌትዎ ገብቷል።", show_alert=True)
            else:
                await callback.answer("❌ ክፍያዎ ገና በባንክ አልተረጋገጠም።", show_alert=True)
    await callback.answer()

# ----------------- P2P TRANSFER -----------------
@router.callback_query(F.data == "p2p_transfer")
async def p2p_transfer_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user[7] <= 0:
        await callback.answer("❌ በዋሌትዎ ውስጥ ማስተላለፍ የሚችሉት ቀሪ ሂሳብ የለም!", show_alert=True)
        return
    await state.set_state(P2PTransferStates.waiting_for_recipient)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="my_account")]])
    await callback.message.edit_text(text="💸 <b>ገንዘብ ለሌላ ተጠቃሚ ማስተላለፍ (P2P)</b>\n\nየተቀባዩን **ዋሌት ID** (ምሳሌ: `W12345`) ጻፉልኝ፦", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(P2PTransferStates.waiting_for_recipient)
async def process_p2p_recipient(message: types.Message, state: FSMContext):
    recipient = get_user_by_wallet(message.text.strip())
    if not recipient:
        await message.answer("❌ ዋሌት ID አልተገኘም። እንደገና ይጻፉ:")
        return
    if recipient[0] == message.from_user.id:
        await message.answer("❌ ለራስዎ ማስተላለፍ አይችሉም:")
        return

    await state.update_data(recipient_id=recipient[0], recipient_name=recipient[2])
    await state.set_state(P2PTransferStates.waiting_for_amount)
    await message.answer(f"✅ ተቀባይ: <b>{recipient[2]}</b>\nማስተላለፍ የሚፈልጉትን የብር መጠን ጻፉልኝ፦", parse_mode="HTML")

@router.message(P2PTransferStates.waiting_for_amount)
async def process_p2p_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError()
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ያስገቡ።")
        return

    data = await state.get_data()
    user = get_user(message.from_user.id)
    fee = amount * (get_setting('transfer_fee_percent', float) / 100.0)
    
    if (amount + fee) > user[7]:
        await message.answer("❌ በቂ ሂሳብ የለም።")
        return

    await state.clear()
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount + fee, message.from_user.id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, data.get("recipient_id")))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (fee, ADMIN_ID))
        conn.commit()

    await message.answer(f"✅ ገንዘቡ ለ<b>{data.get('recipient_name')}</b> ተላልፏል!", parse_mode="HTML")

# ----------------- WITHDRAWAL HANDLERS -----------------
@router.callback_query(F.data == "request_withdraw")
async def request_withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user[7] <= 0:
        await callback.answer("❌ ማውጣት የሚችሉት ቀሪ ሂሳብ የለም!", show_alert=True)
        return
    await state.set_state(WithdrawStates.waiting_for_amount)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data="my_account")]])
    await callback.message.edit_text(text=f"💸 <b>ገንዘብ ማውጣት</b>\nያለዎት: {user[7]} ETB\nማውጣት የሚፈልጉትን መጠን ጻፉልኝ፦", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0: raise ValueError()
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ያስገቡ።")
        return

    user = get_user(message.from_user.id)
    if amount > user[7]:
        await message.answer("❌ በቂ ሂሳብ የለም።")
        return

    await state.clear()
    fee = amount * (get_setting('withdraw_fee_percent', float) / 100.0)
    net = amount - fee
    acc = user[10] or user[9] or "አልታወቀም"

    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, message.from_user.id))
        cursor.execute("INSERT INTO withdrawals (user_id, amount, fee, net_amount, account_info, status) VALUES (?, ?, ?, ?, ?, 'PENDING')",
                       (message.from_user.id, amount, fee, net, acc))
        wd_id = cursor.lastrowid
        conn.commit()

    try:
        await message.bot.send_message(
            ADMIN_ID,
            f"🔔 <b>አዲስ የዊዝድሮ ጥያቄ!</b>\n👤 ተጠቃሚ: {message.from_user.full_name}\n💰 መጠን: {amount} ETB\n💵 የሚላክ: {net} ETB\n🏦 አካውንት: <code>{acc}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ አጽድቅ", callback_data=f"app_wd_{wd_id}")]]),
            parse_mode="HTML"
        )
    except Exception:
        pass

    await message.answer("✅ የገንዘብ ማውጣት ጥያቄዎ ተላልፏል!")

@router.callback_query(F.data.startswith("app_wd_"))
async def approve_withdrawal(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    wd_id = int(callback.data.split("_")[2])
    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, net_amount FROM withdrawals WHERE id = ?", (wd_id,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (wd_id,))
            conn.commit()
            try:
                await callback.bot.send_message(row[0], f"🎉 <b>የጠየቁት ዊዝድሮ ጸድቆ ተፈጽሟል!</b>\n💵 {row[1]} ETB ተልኳል።", parse_mode="HTML")
            except Exception:
                pass
    await callback.answer("ጸድቋል!")

# ----------------- ABOUT & TUTORIAL -----------------
@router.callback_query(F.data == "bot_about")
async def bot_about_callback(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")]])
    await callback.message.edit_text(text="ℹ️ <b>ስለ 50 ሎሚ</b>\nበጋራ እንበለጽጋለን! ባይነሪ ማትሪክስ እና ሎሚ ኮይን ግብይት መድረክ።", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "tutorial_video")
async def tutorial_video_callback(callback: types.CallbackQuery):
    t_link = get_setting('tutorial_link', str) or TUTORIAL_VIDEO_URL
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")]])
    await callback.message.edit_text(text=f"🎬 <b>መመሪያ</b>\n<a href='{t_link}'>ቪዲዮውን ለማየት እዚህ ይጫኑ</a>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ----------------- WALLET & ACCOUNT -----------------
@router.callback_query(F.data == "my_account")
async def my_account_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user: return
    
    is_active = user[6] == 1
    balance = user[7]
    coin_balance = user[8]
    phone = user[9] or 'አልገባም'
    pay_acc = user[10] or 'አልገባም'
    wallet_id = user[11] or f"W{callback.from_user.id}"
    
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    with sqlite3.connect("binary_mlm.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (callback.from_user.id,))
        total_refs = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ? AND is_active = 1", (callback.from_user.id,))
        active_refs = cursor.fetchone()[0]

    keyboard_buttons = [
        [InlineKeyboardButton(text="💸 Withdraw", callback_data="request_withdraw"), InlineKeyboardButton(text="🔄 P2P Transfer", callback_data="p2p_transfer")],
        [InlineKeyboardButton(text="🪙 ሎሚ ኮይን ገበያ", callback_data="lomi_market")]
    ]

    if not is_active:
        keyboard_buttons.insert(0, [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate)", callback_data="payment_options")])

    keyboard_buttons.append([InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    status_text = "🟢 ንቁ (Active)" if is_active else "🔴 ስራ አልጀመረም (Pending)"
    text = (
        f"💳 <b>የእርስዎ ዋሌት እና አካውንት</b> (50 ሎሚ)\n\n"
        f"👤 ስም: {callback.from_user.full_name}\n"
        f"🆔 ዋሌት ID: <code>{wallet_id}</code>\n"
        f"📞 ስልክ: {phone}\n"
        f"🏦 የክፍያ አካውንት: {pay_acc}\n"
        f"📌 ሁኔታ: {status_text}\n"
        f"💰 የብር ቀሪ ሂሳብ: <b>{balance} ETB</b>\n"
        f"🪙 የሎሚ ኮይን ቀሪ ሂሳብ: <b>{coin_balance} ሎሚ ኮይን</b>\n\n"
        f"👥 ሪፈራል: ጠቅላላ {total_refs} | ንቁ: {active_refs}\n\n"
        f"🔗 <b>የእርስዎ ሪፈራል ሊንክ:</b>\n<code>{ref_link}</code>"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ----------------- ADMIN PANEL -----------------
@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return

    price = get_setting('package_price', float)
    comm = get_setting('commission_percent', float)
    coin_price = get_setting('lomi_coin_price', float)
    sup = get_setting('support_phone', str)

    text = (
        f"⚙️ <b>የአድሚን መቆጣጠሪያ ፓነል</b>\n\n"
        f"• የፓኬጅ ዋጋ: <b>{price} ETB</b>\n"
        f"• የኮሚሽን መቶኛ: <b>{comm}%</b>\n"
        f"• 🪙 <b>የ 1 ሎሚ ኮይን ዋጋ: {coin_price} ETB</b>\n"
        f"• የድጋፍ ስልክ: <code>{sup}</code>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ፓኬጅ ዋጋ ቀይር", callback_data="adm_set_price"), InlineKeyboardButton(text="🪙 ኮይን ዋጋ ቀይር", callback_data="adm_set_coin_price")],
        [InlineKeyboardButton(text="📊 ኮሚሽን ቀይር", callback_data="adm_set_comm"), InlineKeyboardButton(text="📞 ድጋፍ ስልክ ቀይር", callback_data="adm_set_phone")],
        [InlineKeyboardButton(text="🏠 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text=text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "adm_set_price")
async def admin_set_price_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminConfig.waiting_for_price)
    await callback.message.answer("አዲሱን የፓኬጅ ዋጋ በቁጥር (ETB) ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_price)
async def admin_save_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        val = float(message.text.strip())
        set_setting('package_price', val)
        await state.clear()
        await message.answer(f"✅ የፓኬጅ ዋጋ ወደ {val} ETB ተቀይሯል!")
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ያስገቡ:")

@router.callback_query(F.data == "adm_set_coin_price")
async def admin_set_coin_price_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminConfig.waiting_for_coin_price)
    await callback.message.answer("አዲሱን የ 1 ሎሚ ኮይን የገበያ ዋጋ በብር (ETB) ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_coin_price)
async def admin_save_coin_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        val = float(message.text.strip())
        set_setting('lomi_coin_price', val)
        await state.clear()
        await message.answer(f"✅ የ 1 ሎሚ ኮይን አዲስ ዋጋ ወደ {val} ETB ተቀይሯል!")
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ያስገቡ:")

@router.callback_query(F.data == "adm_set_comm")
async def admin_set_comm_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminConfig.waiting_for_commission)
    await callback.message.answer("አዲሱን የኮሚሽን መቶኛ ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_commission)
async def admin_save_commission(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        val = float(message.text.strip())
        set_setting('commission_percent', val)
        await state.clear()
        await message.answer(f"✅ የኮሚሽን መቶኛ ወደ {val}% ተቀይሯል!")
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ያስገቡ:")

@router.callback_query(F.data == "adm_set_phone")
async def admin_set_phone_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminConfig.waiting_for_support_phone)
    await callback.message.answer("አዲሱን የደንበኛ ድጋፍ ስልክ ቁጥር ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_support_phone)
async def admin_save_support_phone(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    phone = message.text.strip()
    set_setting('support_phone', phone)
    await state.clear()
    await message.answer(f"✅ የድጋፍ ስልክ ወደ {phone} ተቀይሯል!")

# ----------------- WEBHOOK SERVER -----------------
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

async def handle_chapa_webhook(request):
    try:
        data = await request.json()
        tx_ref = data.get("tx_ref")
        status = data.get("status")

        if tx_ref:
            with sqlite3.connect("binary_mlm.db") as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id, amount, type, status FROM transactions WHERE tx_ref = ?", (tx_ref,))
                tx_row = cursor.fetchone()
                
                if tx_row and tx_row[3] != 'SUCCESS':
                    user_id, amount, tx_type, _ = tx_row
                    
                    if status in ["success", "successful"]:
                        cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                        conn.commit()
                        
                        if tx_type == 'PACKAGE':
                            bot = request.app['bot']
                            await activate_user_in_matrix(user_id, bot)
                            try:
                                await bot.send_message(user_id, "🎉 <b>የፓኬጅ ክፍያዎ ተረጋግጦ አካውንትዎ ንቁ ሆኗል።</b>", parse_mode="HTML")
                            except Exception:
                                pass
                        elif tx_type == 'DEPOSIT':
                            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                            conn.commit()
                            bot = request.app['bot']
                            try:
                                await bot.send_message(user_id, f"🎉 <b>ክፍያዎ ተረጋግጧል! {amount} ETB ወደ ዋሌትዎ ገብቷል።</b>", parse_mode="HTML")
                            except Exception:
                                pass
        return web.json_response({"status": "received"})
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return web.json_response({"status": "error", "message": str(e)}, status=400)

async def start_web_server(bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_get("/", handle_ping)
    app.router.add_post("/chapa-webhook", handle_chapa_webhook)
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on port {port}")

# ----------------- BOT STARTUP -----------------
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    await start_web_server(bot)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
