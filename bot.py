import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
import aiohttp
from aiohttp import web
from urllib.parse import quote_plus as quote_plus_text

# ----------------- CONFIGURATIONS -----------------
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "5351353727"))
CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY", "").strip()
CHAPA_PUBLIC_KEY = os.getenv("CHAPA_PUBLIC_KEY", "").strip()

# የድር ሰርቨር ዩአርኤል በሬንደር (Render) ላይ ሲሰራ በራስ-ሰር እንዲያዝ (Render Web Service URL)
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

CHANNEL_USERNAME = "@Hamisalomi_bot_official" 
CHANNEL_ID = -1002345678901 
TUTORIAL_VIDEO_URL = "https://t.me/Hamisalomi_bot_official"

logging.basicConfig(level=logging.INFO)
router = Router()

# ----------------- STATES -----------------
class AdminConfig(StatesGroup):
    waiting_for_price = State()
    waiting_for_commission = State()
    waiting_for_broadcast = State()
    waiting_for_video_link = State()
    waiting_for_support_phone = State()

class UserProfileSetup(StatesGroup):
    waiting_for_phone = State()
    waiting_for_payment_info = State()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

class DepositStates(StatesGroup):
    waiting_for_amount = State()

class P2PTransferStates(StatesGroup):
    waiting_for_recipient = State()
    waiting_for_amount = State()

class ServiceOrderStates(StatesGroup):
    waiting_for_detail = State()

class AdminCheckUserStates(StatesGroup):
    waiting_for_user_id = State()

# ----------------- DATABASE SETUP -----------------
def init_db():
    conn = sqlite3.connect("binary_mlm.db")
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
            phone_number TEXT,
            payment_account TEXT,
            wallet_id TEXT UNIQUE
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
    conn.close()

init_db()

def get_setting(key, default_type=float):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        if default_type == int:
            return int(float(row[0]))
        elif default_type == str:
            return str(row[0])
        return default_type(row[0])
    return "" if default_type == str else default_type(0)

def set_setting(key, value):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_wallet(wallet_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE wallet_id = ?", (wallet_id.strip(),))
    user = cursor.fetchone()
    conn.close()
    return user

def register_pending_user(user_id, username, fullname, referrer_id):
    wallet_id = f"W{user_id}"
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, fullname, referrer_id, is_active, wallet_id) 
        VALUES (?, ?, ?, ?, 0, ?)
    """, (user_id, username, fullname, referrer_id, wallet_id))
    conn.commit()
    conn.close()

# ----------------- MATRIX & REFERRAL LOGIC -----------------
async def activate_user_in_matrix(user_id, bot: Bot):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_active, referrer_id, fullname FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res or res[0] == 1:
        conn.close()
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
    conn.close()

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
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE parent_id = ? AND is_active = 1", (referrer_id,))
    count = cursor.fetchone()[0]
    conn.close()
    
    if count >= 10:
        return find_available_matrix_parent()
    return referrer_id

def find_available_matrix_parent():
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    queue = [ADMIN_ID]
    while queue:
        current_id = queue.pop(0)
        
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'LEFT' AND is_active = 1", (current_id,))
        left_child = cursor.fetchone()
        if not left_child:
            conn.close()
            return current_id
        else:
            queue.append(left_child[0])
            
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'RIGHT' AND is_active = 1", (current_id,))
        right_child = cursor.fetchone()
        if not right_child:
            conn.close()
            return current_id
        else:
            queue.append(right_child[0])
            
    conn.close()
    return ADMIN_ID

def find_available_position_under(start_user_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    queue = [start_user_id]
    while queue:
        current_id = queue.pop(0)
        
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'LEFT'", (current_id,))
        if not cursor.fetchone():
            conn.close()
            return current_id, 'LEFT'
        
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'RIGHT'", (current_id,))
        if not cursor.fetchone():
            conn.close()
            return current_id, 'RIGHT'
            
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? ORDER BY position", (current_id,))
        for child in cursor.fetchall():
            queue.append(child[0])
            
    conn.close()
    return start_user_id, 'LEFT'

# ----------------- BOT HANDLERS -----------------
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        await state.clear()
    except Exception:
        pass

    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except ValueError:
            referrer_id = None

    user = get_user(message.from_user.id)
    if not user:
        register_pending_user(
            message.from_user.id,
            message.from_user.username or "",
            message.from_user.full_name or "User",
            referrer_id
        )
        user = get_user(message.from_user.id)

    if not user[8] or not user[9]:
        await state.set_state(UserProfileSetup.waiting_for_phone)
        
        welcome_start_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 ቦቱን ይጀምሩ (Start)", callback_data="main_menu")]
        ])
        
        await message.answer(
            f"ሰላም <b>{message.from_user.full_name}</b>!\n\n"
            f"እንኳን ወደ 50 ሎሚ በሰላም መጡ! 🤝 (በጋራ እንበለጽጋለን!)\n"
            f"የሪፈራል ሊንክ ከመሰጠቱ በፊት እባክዎ <b>ስልክ ቁጥርዎን</b> ይጻፉልኝ፦\n"
            f"<i>(ምሳሌ: 0911223344)</i>",
            reply_markup=welcome_start_keyboard,
            parse_mode="HTML"
        )
        return

    await show_main_menu(message, user)

@router.callback_query(F.data == "main_menu")
async def main_menu_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
    except Exception:
        pass
    user = get_user(callback.from_user.id)
    if not user:
        register_pending_user(
            callback.from_user.id,
            callback.from_user.username or "",
            callback.from_user.full_name or "User",
            None
        )
        user = get_user(callback.from_user.id)
    await show_main_menu(callback, user)

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
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET phone_number = ?, payment_account = ? WHERE user_id = ?", 
                   (phone, payment_info, message.from_user.id))
    conn.commit()
    conn.close()
    
    await state.clear()
    user = get_user(message.from_user.id)
    await message.answer("✅ መረጃዎ በትክክል ተመዝግቧል! አሁን ወደ ዋናው ገጽ ገብተዋል፦")
    await show_main_menu(message, user)

async def show_main_menu(message_or_callback, user):
    is_admin = (message_or_callback.from_user.id == ADMIN_ID)
    
    bot_info = await message_or_callback.bot.get_me() if hasattr(message_or_callback, "bot") else await (message_or_callback.message.bot.get_me() if isinstance(message_or_callback, types.CallbackQuery) else None)
    bot_username = bot_info.username if bot_info else "Hamisalomi_bot"

    keyboard_buttons = [
        [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate Account)", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="📥 ገንዘብ ወደ ዋሌት ጫን (Deposit)", callback_data="wallet_deposit")],
        [InlineKeyboardButton(text="📊 የኔ ዋሌት እና አካውንት (Wallet)", callback_data="my_account")],
        [InlineKeyboardButton(text="🛒 የዲጂታል አገልግሎቶች (Mobile Recharge & Ads)", callback_data="digital_services")],
        [InlineKeyboardButton(text="📞 Customer Support", callback_data="customer_support")],
        [InlineKeyboardButton(text="ℹ️ ስለ 50 ሎሚ እና አሰራር (About)", callback_data="bot_about")],
        [InlineKeyboardButton(text="🎬 አጠቃቀም ቪዲዮ መመሪያ (Tutorial)", callback_data="tutorial_video")],
        [
            InlineKeyboardButton(text="🤖 ቦት ሊንክ", url=f"https://t.me/{bot_username}"),
            InlineKeyboardButton(text="📢 50 ሎሚ ቻናል", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
        ]
    ]
    
    if is_admin:
        keyboard_buttons.append([InlineKeyboardButton(text="⚙️ አድሚን ፓነል (Admin Settings)", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    current_price = get_setting('package_price', float)
    current_commission = get_setting('commission_percent', float)
    
    welcome_text = (
        f"ሰላም <b>{message_or_callback.from_user.full_name}</b>!\n\n"
        f"እንኳን ወደ 50 ሎሚ በደህና መጡ፤ <b>በጋራ እናድጋለን፣ በጋራ እንበለጽጋለን!</b> 🤝🍋\n\n"
        f"ይህ ቦት ተጠቃሚዎች በአንድነት እርስ በእርስ እየተደጋገፉ ገቢ የሚያገኙበት መድረክ ነው።\n\n"
        f"የአሁኑ የፓኬጅ ዋጋ: <b>{current_price} ETB</b>\n"
        f"የስራ ኮሚሽን: <b>{current_commission}%</b>\n\n"
        f"ከታች ካሉት አማራጮች ውስጥ የሚፈልጉትን መምረጥ ይችላሉ።"
    )
    
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

# ----------------- CHAPA PACKAGE PAYMENT & WEBHOOK CALLBACK -----------------
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

    # ከሬንደር (Render) የተገኘውን ትክክለኛ ዩአርኤል በመጠቀም የ回调/Webhook ሊንክ ማስተካከል
    base_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://your-app.onrender.com"
    callback_url = f"{base_url}/chapa-webhook"

    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(package_price),
        "currency": "ETB",
        "email": f"user{user_id}@gmail.com",
        "first_name": callback.from_user.first_name or "User",
        "last_name": callback.from_user.last_name or "Lomi",
        "tx_ref": tx_ref,
        "callback_url": callback_url,
        "customization[title]": "50 Lomi Package Activation",
        "customization[description]": f"Activate Binary MLM Account for {package_price} ETB"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO transactions (tx_ref, user_id, amount, status, type) VALUES (?, ?, ?, 'PENDING', 'PACKAGE')",
                               (tx_ref, user_id, package_price))
                conn.commit()
                conn.close()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 በቻፓ (Chapa) ክፍያ ይፈጽሙ", url=checkout_url)],
                    [InlineKeyboardButton(text="🔄 ክፍያ ከፈጸሙ በኋላ ያረጋግጡ", callback_data=f"verify_pkg_{tx_ref}")],
                    [InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
                ])
                try:
                    await callback.message.edit_text(
                        f"💳 <b>የፓኬጅ ክፍያ ማገናኛ (Checkout Link) ተዘጋጅቷል!</b>\n\n"
                        f"• መጠን: <b>{package_price} ETB</b>\n\n"
                        f"ሊንኩን በመጫን ክፍያዎን ይፈጽሙና <b>ክፍያ ከፈጸሙ በኋላ ያረጋግጡ</b> የሚለውን ይጫኑ።",
                        reply_markup=keyboard, parse_mode="HTML"
                    )
                except Exception:
                    await callback.message.answer(
                        f"💳 <b>የፓኬጅ ክፍያ ማገናኛ ተዘጋጅቷል! (መጠን: {package_price} ETB)</b>",
                        reply_markup=keyboard, parse_mode="HTML"
                    )
            else:
                await callback.answer("❌ የክፍያ ሊንክ መፍጠር አልተቻለም። እባክዎ ሐኪም/አድሚን ያነጋግሩ።", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("verify_pkg_"))
async def verify_package_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_", 2)[2]
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, user_id FROM transactions WHERE tx_ref = ?", (tx_ref,))
    tx_row = cursor.fetchone()
    if not tx_row:
        conn.close()
        await callback.answer("❌ የግብይት መረጃ አልተገኘም።", show_alert=True)
        return
    db_status, user_id = tx_row
    conn.close()

    if db_status == 'SUCCESS':
        await callback.answer("✅ ክፍያዎ ቀድሞውኑ ተረጋግጦ አካውንትዎ ገብቷል!", show_alert=True)
        return

    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success" and res_data.get("data", {}).get("status") == "success":
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                conn.commit()
                conn.close()

                # ማትሪክስ እና ኮሚሽን ማግበር
                activated = await activate_user_in_matrix(user_id, callback.bot)
                if activated:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 የኔ ዋሌት እና አካውንት (Wallet)", callback_data="my_account")]
                    ])
                    try:
                        await callback.message.edit_text(
                            "🎉 <b>እንኳን ደስ አለዎት! ክፍያዎ ተረጋግጦ አካውንትዎ ንቁ (Active) ሆኗል።</b>\n"
                            "አሁን የሪፈራል ሊንክዎ ስራ ጀምሯል!", 
                            reply_markup=keyboard, parse_mode="HTML"
                        )
                    except Exception:
                        pass
                else:
                    await callback.answer("✅ ክፍያዎ ተረጋግጧል!", show_alert=True)
            else:
                await callback.answer("❌ ክፍያዎ ገና በባንክ አልተረጋገጠም። እባክዎ ክፍያውን ከፈጸሙ ትንሽ ቆይተው እንደገና ይሞክሩ።", show_alert=True)
    await callback.answer()

# ----------------- CUSTOMER SUPPORT HANDLER -----------------
@router.callback_query(F.data == "customer_support")
async def customer_support_handler(callback: types.CallbackQuery):
    support_phone = get_setting('support_phone', str)
    if not support_phone:
        support_phone = "0916039015"
        
    text = (
        f"📞 <b>የደንበኞች ድጋፍ (Customer Support)</b>\n\n"
        f"ማንኛውም ጥያቄ፣ እርዳታ ሲፈልጉ ወይም ክፍያዎችን በተመለከተ ከታች ባለው ስልክ ቁጥር ወይም በአድሚን በኩል ማግኘት ይችላሉ።\n\n"
        f"• የድጋፍ ስልክ ቁጥር: `{support_phone}`\n"
        f"• ቻናል: https://t.me/{CHANNEL_USERNAME.replace('@', '')}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ----------------- DIGITAL SERVICES HUB -----------------
@router.callback_query(F.data == "digital_services")
async def digital_services_menu(callback: types.CallbackQuery):
    support_phone = get_setting('support_phone', str) or "0916039015"
    text = (
        f"🛒 <b>የዲጂታል አገልግሎቶች ማዕከል</b> (50 ሎሚ)\n\n"
        f"ከዋሌትዎ ቀሪ ሂሳብ በመጠቀም ወይም በቀጥታ ገንዘብ ወደ አድሚን አካውንት (Mobile Money Wallet/Commercial Bank <b>{support_phone}</b>) በማስተላለፍ አገልግሎቱን ማግኘት ይችላሉ፦\n\n"
        f"1️⃣ <b>Cell Phone Airtime</b>\n"
        f"2️⃣ <b>የቴሌግራም ፕሪሚየም (Telegram Premium)</b>\n"
        f"3️⃣ <b>የቲክቶክ እና ቴሌግራም ማስታወቂያዎች (Ads)</b>\n\n"
        f"ከታች ካሉት አማራጮች አንዱን ይምረጡ፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Cell Phone Airtime", callback_data="srv_airtime"), InlineKeyboardButton(text="⭐ ቴሌግራም ፕሪሚየም", callback_data="srv_tg_prem")],
        [InlineKeyboardButton(text="📢 የቲክቶክ/ቴሌግራም ማስታወቂያ", callback_data="srv_ads")],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
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
    support_phone = get_setting('support_phone', str) or "0916039015"
    
    await state.update_data(service_type=s_title)
    await state.set_state(ServiceOrderStates.waiting_for_detail)
    
    text = (
        f"🛒 <b>{s_title}</b>\n\n"
        f"እባክዎ ለዚህ አገልግሎት የሚፈልጉትን ዝርዝር (ለምሳሌ፦ ስልክ ቁጥር፣ የቴሌግራም ዩዘርናም ወይም የማስታወቂያ ሊንክ እና የብር መጠን) ጻፉልኝ፦\n\n"
        f"💳 <b>የክፍያ አካውንት (እንዲሞላ/እንዲከፈል የፈለጉትን ገንዘብ ከዚህ በታች ወዳለው ያስተላልፉ):</b>\n"
        f"• <b>Mobile Money Wallet / Commercial Bank:</b> `{support_phone}`"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="digital_services"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(ServiceOrderStates.waiting_for_detail)
async def process_service_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    s_type = data.get("service_type")
    detail = message.text.strip()
    user_id = message.from_user.id
    await state.clear()

    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO service_orders (user_id, service_type, detail, status) VALUES (?, ?, ?, 'PENDING')",
                   (user_id, s_type, detail))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    support_phone = get_setting('support_phone', str) or "0916039015"
    try:
        admin_text = (
            f"🔔 <b>አዲስ የዲጂታል አገልግሎት ትዕዛዝ! (50 ሎሚ)</b>\n\n"
            f"👤 ተጠቃሚ: {message.from_user.full_name} (ID: <code>{user_id}</code>)\n"
            f"📦 አገልግሎት: <b>{s_type}</b>\n"
            f"📝 ዝርዝር መረጃ:\n{detail}\n\n"
            f"💳 (ተጠቃሚው ክፍያውን በMobile Money Wallet/Commercial Bank {support_phone} ልኮ ሊሆን ስለሚችል እባክዎ አረጋግጦ ያስፈጽሙ)"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ አጽድቅ (Approved)", callback_data=f"app_srv_{order_id}")]
        ])
        await message.bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="digital_services"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")
        ]
    ])
    await message.answer(
        "✅ ትዕዛዝዎ ተቀባይነት አግኝቷል!\n"
        f"አድሚኑ ክፍያውን አረጋግጦ አገልግሎቱን በቅርቡ ይፈጽምልዎታል።", 
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("app_srv_"))
async def approve_service_order(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    order_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, service_type, status FROM service_orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()
    
    if not row or row[2] != 'PENDING':
        conn.close()
        await callback.answer("ትዕዛዙ አልተገኘም ወይም ቀድሞ ጸድቋል!", show_alert=True)
        return
        
    user_id, s_type, _ = row
    cursor.execute("UPDATE service_orders SET status = 'APPROVED' WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

    try:
        await callback.bot.send_message(
            user_id,
            f"🎉 <b>የጠየቁት አገልግሎት ({s_type}) ጸድቆ ተፈጽሟል!</b>\nእናመሰግናለን (50 ሎሚ)",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ ጸድቋል (APPROVED)", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("ትዕዛዙ ጸድቋል!")

# ----------------- WALLET DEPOSIT (CHAPA) -----------------
@router.callback_query(F.data == "wallet_deposit")
async def wallet_deposit_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(DepositStates.waiting_for_amount)
    text = (
        f"📥 <b>ገንዘብ ወደ ዋሌት ጫን (Deposit)</b>\n\n"
        f"ወደ ዋሌትዎ ማስገባት የሚፈልጉትን የብር መጠን (በETB) ይጻፉልኝ፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="main_menu"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(DepositStates.waiting_for_amount)
async def process_wallet_deposit(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ የብር መጠን ብቻ ያስገቡ።")
        return

    await state.clear()
    tx_ref = f"dep-{message.from_user.id}-{int(asyncio.get_event_loop().time())}"

    base_url = RENDER_EXTERNAL_URL if RENDER_EXTERNAL_URL else "https://your-app.onrender.com"
    callback_url = f"{base_url}/chapa-webhook"

    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(amount),
        "currency": "ETB",
        "email": f"user{message.from_user.id}@gmail.com",
        "first_name": message.from_user.first_name or "User",
        "last_name": message.from_user.last_name or "Lomi",
        "tx_ref": tx_ref,
        "callback_url": callback_url,
        "customization[title]": "50 Lomi Wallet Deposit",
        "customization[description]": f"Deposit {amount} ETB to Wallet"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO transactions (tx_ref, user_id, amount, status, type) VALUES (?, ?, ?, 'PENDING', 'DEPOSIT')",
                               (tx_ref, message.from_user.id, amount))
                conn.commit()
                conn.close()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 በቻፓ ለመክፈል እዚህ ይጫኑ", url=checkout_url)],
                    [InlineKeyboardButton(text="🔄 ክፍያ ከፈጸሙ በኋላ ያረጋግጡ", callback_data=f"verify_dep_{tx_ref}")],
                    [InlineKeyboardButton(text="🏠 ወደ ዋናው ገጽ", callback_data="main_menu")]
                ])
                await message.answer(
                    f"💳 <b>የዴፖዚት የክፍያ ማገናኛ ተዘጋጅቷል! (መጠን: {amount} ETB)</b>\n\n"
                    "ሊንኩን በመጫን ክፍያዎን ይፈጽሙና <b>ያረጋግጡ</b> የሚለውን ይጫኑ።",
                    reply_markup=keyboard, parse_mode="HTML"
                )
            else:
                await message.answer("❌ የክፍያ ሊንክ መፍጠር አልተቻለም።")

@router.callback_query(F.data.startswith("verify_dep_"))
async def verify_deposit_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_", 2)[2]
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, user_id, amount FROM transactions WHERE tx_ref = ?", (tx_ref,))
    tx_row = cursor.fetchone()
    if not tx_row:
        conn.close()
        await callback.answer("❌ የግብይት መረጃ አልተገኘም።", show_alert=True)
        return
    db_status, user_id, amount = tx_row
    conn.close()

    if db_status == 'SUCCESS':
        await callback.answer("✅ ክፍያዎ ቀድሞውኑ ተረጋግጧል!", show_alert=True)
        return

    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success" and res_data.get("data", {}).get("status") == "success":
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                conn.commit()
                conn.close()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 የኔ ዋሌት እና አካውንት", callback_data="my_account")]
                ])
                try:
                    await callback.message.edit_text(f"🎉 <b>ክፍያዎ ተረጋግጧል! {amount} ETB ወደ ዋሌትዎ ገብቷል።</b>", reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    pass
            else:
                await callback.answer("❌ ክፍያዎ ገና በባንክ አልተረጋገጠም።", show_alert=True)
    await callback.answer()

# ----------------- P2P TRANSFER (WALLET TO WALLET) -----------------
@router.callback_query(F.data == "p2p_transfer")
async def p2p_transfer_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user[7] <= 0:
        await callback.answer("❌ በዋሌትዎ ውስጥ ማስተላለፍ የሚችሉት ቀሪ ሂሳብ የለም!", show_alert=True)
        return

    await state.set_state(P2PTransferStates.waiting_for_recipient)
    text = (
        f"💸 <b>ገንዘብ ለሌላ ተጠቃሚ ማስተላለፍ (P2P Transfer)</b>\n\n"
        f"የተቀባዩን **የዋሌት መለያ (Wallet ID)** (ለምሳሌ: `W12345678`) ጻፉልኝ፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="my_account"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(P2PTransferStates.waiting_for_recipient)
async def process_p2p_recipient(message: types.Message, state: FSMContext):
    recipient_wallet = message.text.strip()
    recipient = get_user_by_wallet(recipient_wallet)
    
    if not recipient:
        await message.answer("❌ ያስገቡት የዋሌት መለያ አልተገኘም። እባክዎ ትክክለኛውን ID እንደገና ይጻፉ:")
        return

    if recipient[0] == message.from_user.id:
        await message.answer("❌ ለራስዎ ገንዘብ ማስተላለፍ አይችሉም። ሌላ ዋሌት ID ያስገቡ:")
        return

    await state.update_data(recipient_id=recipient[0], recipient_name=recipient[2], recipient_wallet=recipient_wallet)
    await state.set_state(P2PTransferStates.waiting_for_amount)
    
    user = get_user(message.from_user.id)
    await message.answer(
        f"✅ ተቀባይ ተገኝቷል: <b>{recipient[2]}</b> ({recipient_wallet})\n\n"
        f"ቀሪ ሂሳብዎ: <b>{user[7]} ETB</b>\n"
        f"ማስተላለፍ የሚፈልጉትን የብር መጠን ጻፉልኝ፦",
        parse_mode="HTML"
    )

@router.message(P2PTransferStates.waiting_for_amount)
async def process_p2p_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ብቻ ያስገቡ።")
        return

    data = await state.get_data()
    recipient_id = data.get("recipient_id")
    recipient_name = data.get("recipient_name")
    
    user = get_user(message.from_user.id)
    balance = user[7]
    
    fee_percent = get_setting('transfer_fee_percent', float)
    fee_amount = amount * (fee_percent / 100.0)
    total_deduct = amount + fee_amount

    if total_deduct > balance:
        await message.answer(f"❌ በዋሌትዎ ውስጥ በቂ ሂሳብ የለም። (የዝውውር ክፍያ {fee_percent}% ጨምሮ ጠቅላላ {total_deduct} ETB ያስፈልጋል)")
        return

    await state.clear()

    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_deduct, message.from_user.id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, recipient_id))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (fee_amount, ADMIN_ID))
    conn.commit()
    conn.close()

    try:
        await message.bot.send_message(
            recipient_id,
            f"🎉 <b>የገንዘብ ዝውውር (P2P) ደርሶዎታል!</b>\n\n"
            f"👤 ላኪ: {message.from_user.full_name}\n"
            f"💰 መጠን: <b>{amount} ETB</b>",
            parse_mode="HTML"
        )
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 ወደ ዋሌት ገጽ ተመለስ", callback_data="my_account")]
    ])
    await message.answer(
        f"✅ ገንዘቡ ለ<b>{recipient_name}</b> በትክክል ተላልፏል!\n"
        f"• የተላከው: {amount} ETB\n"
        f"• የዝውውር ክፍያ ({fee_percent}%): {fee_amount} ETB",
        reply_markup=keyboard, parse_mode="HTML"
    )

# ----------------- WITHDRAWAL HANDLERS -----------------
@router.callback_query(F.data == "request_withdraw")
async def request_withdraw_start(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user[7] <= 0:
        await callback.answer("❌ ማውጣት የሚችሉት ቀሪ ሂሳብ የለም!", show_alert=True)
        return

    await state.set_state(WithdrawStates.waiting_for_amount)
    text = (
        f"💸 <b>ገንዘብ ማውጣት (Withdrawal)</b>\n\n"
        f"ቀሪ ሂሳብዎ: <b>{user[7]} ETB</b>\n"
        f"ማውጣት የሚፈልጉትን የብር መጠን ጻፉልኝ፦"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="my_account"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ የብር መጠን ያስገቡ።")
        return

    user = get_user(message.from_user.id)
    balance = user[7]
    fee_percent = get_setting('withdraw_fee_percent', float)
    fee = amount * (fee_percent / 100.0)
    net_amount = amount - fee

    if amount > balance:
        await message.answer(f"❌ በዋሌትዎ ውስጥ በቂ ሂሳብ የለም። (ያለዎት: {balance} ETB)")
        return

    await state.clear()
    account_info = user[9] or user[8] or "አልታወቀም"

    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, message.from_user.id))
    cursor.execute("""
        INSERT INTO withdrawals (user_id, amount, fee, net_amount, account_info, status) 
        VALUES (?, ?, ?, ?, ?, 'PENDING')
    """, (message.from_user.id, amount, fee, net_amount, account_info))
    withdraw_id = cursor.lastrowid
    conn.commit()
    conn.close()

    try:
        admin_text = (
            f"🔔 <b>አዲስ የገንዘብ ማውጣት (Withdrawal) ጥያቄ!</b>\n\n"
            f"👤 ተጠቃሚ: {message.from_user.full_name} (ID: <code>{message.from_user.id}</code>)\n"
            f"💰 የጠየቀው መጠን: <b>{amount} ETB</b>\n"
            f"📉 ክፍያ ({fee_percent}%): {fee} ETB\n"
            f"💵 የሚላከው ጥርት ያለ ገንዘብ: <b>{net_amount} ETB</b>\n"
            f"🏦 የክፍያ አካውንት: <code>{account_info}</code>"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ አጽድቅ (Approve)", callback_data=f"app_wd_{withdraw_id}")]
        ])
        await message.bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 ወደ ዋሌት ገጽ", callback_data="my_account")]
    ])
    await message.answer(
        f"✅ የገንዘብ ማውጣት ጥያቄዎ በትክክል ተላልፏል!\n"
        f"• የጠየቁት: {amount} ETB\n"
        f"• የخدمة ክፍያ: {fee} ETB\n"
        f"• የሚደርስዎት: {net_amount} ETB\n\n"
        f"አድሚኑ አረጋግጦ ገንዘብዎን ይልክልዎታል።",
        reply_markup=keyboard, parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("app_wd_"))
async def approve_withdrawal(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    wd_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, net_amount, status FROM withdrawals WHERE id = ?", (wd_id,))
    row = cursor.fetchone()
    
    if not row or row[2] != 'PENDING':
        conn.close()
        await callback.answer("ጥያቄው አልተገኘም ወይም ቀድሞ ጸድቋል!", show_alert=True)
        return
        
    user_id, net_amount, _ = row
    cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (wd_id,))
    conn.commit()
    conn.close()

    try:
        await callback.bot.send_message(
            user_id,
            f"🎉 <b>የጠየቁት ገንዘብ ማውጣት ጥያቄ ጸድቆ ተፈጽሟል!</b>\n"
            f"💵 የተላከልዎ መጠን: <b>{net_amount} ETB</b>\nእናመሰግናለን (50 ሎሚ)",
            parse_mode="HTML"
        )
    except Exception:
        pass

    try:
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ ጸድቋል (APPROVED)", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("ጥያቄው ጸድቋል!")

# ----------------- ABOUT & TUTORIAL HANDLERS -----------------
@router.callback_query(F.data == "bot_about")
async def bot_about_callback(callback: types.CallbackQuery):
    text = (
        f"ℹ️ <b>ስለ 50 ሎሚ ቦት እና አሰራር ማብራሪያ</b>\n\n"
        f"ይህ ቦት ተጠቃሚዎች በአንድነት እርስ በእርስ እየተደጋገፉ ገቢ የሚያገኙበት <b>የባይነሪ ማትሪክስ (Binary MLM System)</b> እና የዲጂታል ዋሌት መድረክ ነው።\n"
        f"🌟 <b>መሪ ቃል:</b> በጋራ እናድጋለን፣ በጋራ እንበለጽጋለን!\n\n"
        f"🔹 <b>ቁልፍ ባህሪያት:</b>\n"
        f"1. የዋሌት 2 ዋሌት ዝውውር (P2P Transfer)\n"
        f"2. የዲጂታል አገልግሎቶች ሽያጭ (Cell Phone Airtime, Telegram Premium, Ads)\n"
        f"3. ከባንክ ወደ ዋሌት ዴፖዚት ማድረግ እና ዊዝድሮ ማድረግ"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="customer_support"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu"),
            InlineKeyboardButton(text="Next ➡️", callback_data="tutorial_video")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "tutorial_video")
async def tutorial_video_callback(callback: types.CallbackQuery):
    t_link = get_setting('tutorial_link', str)
    if not t_link or t_link == "0":
        t_link = TUTORIAL_VIDEO_URL
        
    text = (
        f"🎬 <b>የአጠቃቀም ቪዲዮ እና መመሪያ</b> (50 ሎሚ)\n\n"
        f"ቦቱን እንዴት መጠቀም እንደሚችሉ ከታች ባለው ሊንክ ማየት ይችላሉ፦\n\n"
        f"🔗 <a href='{t_link}'>መመሪያውን ለማየት እዚህ ይጫኑ</a>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 ቻናሉን ይጎብኙ", url=t_link)],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="bot_about"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu"),
            InlineKeyboardButton(text="Next ➡️", callback_data="my_account")
        ]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)
    await callback.answer()

# ----------------- WALLET & ACCOUNT HANDLER -----------------
@router.callback_query(F.data == "my_account")
async def my_account_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.answer("እባክዎ መጀመሪያ /start ይጫኑ።", show_alert=True)
        return

    is_active = user[6] == 1
    balance = user[7]
    phone = user[8] or 'አልገባም'
    pay_acc = user[9] or 'አልገባም'
    wallet_id = user[10] or f"W{callback.from_user.id}"
    
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (callback.from_user.id,))
    total_refs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ? AND is_active = 1", (callback.from_user.id,))
    active_refs = cursor.fetchone()[0]
    conn.close()

    keyboard_buttons = [
        [InlineKeyboardButton(text="💸 ገንዘብ ማውጣት (Withdraw)", callback_data="request_withdraw"), InlineKeyboardButton(text="🔄 ዋሌት ሼር (P2P Transfer)", callback_data="p2p_transfer")]
    ]

    if not is_active:
        text = (
            f"💳 <b>የእርስዎ ዋሌት እና አካውንት መረጃ</b> (50 ሎሚ)\n\n"
            f"👤 ስም: {callback.from_user.full_name}\n"
            f"🆔 ዋሌት ID: <code>{wallet_id}</code>\n"
            f"📞 ስልክ: {phone}\n"
            f"🏦 የክፍያ አካውንት: {pay_acc}\n"
            f"🔴 ሁኔታ: ስራ አልጀመረም (Pending)\n"
            f"💰 ዋሌት ቀሪ ሂሳብ: <b>{balance} ETB</b>\n\n"
            f"👥 የጠሯቸው ሰዎች: <b>{total_refs}</b> (ንቁ: {active_refs})"
        )
        keyboard_buttons.insert(0, [InlineKeyboardButton(text="💳 አሁኑኑ ፓኬጅ ይግዙ (Activate)", callback_data="pay_chapa")])
        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Back", callback_data="tutorial_video"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu"),
            InlineKeyboardButton(text="Next ➡️", callback_data="digital_services")
        ])
    else:
        text = (
            f"💳 <b>የእርስዎ ዋሌት እና አካውንት መረጃ</b> (50 ሎሚ)\n\n"
            f"👤 ስም: {callback.from_user.full_name}\n"
            f"🆔 ዋሌት ID: <code>{wallet_id}</code>\n"
            f"📞 ስልክ: {phone}\n"
            f"🏦 የክፍያ አካውንት: {pay_acc}\n"
            f"🟢 ሁኔታ: ንቁ (Active)\n"
            f"💰 ዋሌት ቀሪ ሂሳብ: <b>{balance} ETB</b>\n\n"
            f"👥 የጠሯቸው: ጠቅላላ <b>{total_refs}</b> | ንቁ: <b>{active_refs}</b>\n\n"
            f"🔗 <b>የእርስዎ የሪፈራል ሊንክ (ኮፒ ለማድረግ ይንኩት):</b>\n"
            f"<code>{ref_link}</code>"
        )
        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Back", callback_data="tutorial_video"),
            InlineKeyboardButton(text="🏠 ዋና ገጽ", callback_data="main_menu"),
            InlineKeyboardButton(text="Next ➡️", callback_data="digital_services")
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

# ----------------- ADMIN PANEL HANDLER -----------------
@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    price = get_setting('package_price', float)
    comm = get_setting('commission_percent', float)
    sup = get_setting('support_phone', str)

    text = (
        f"⚙️ <b>የአድሚን መቆጣጠሪያ ፓነል (Admin Panel)</b>\n\n"
        f"• የፓኬጅ ዋጋ: <b>{price} ETB</b>\n"
        f"• የኮሚሽንភាគዝ: <b>{comm}%</b>\n"
        f"• የድጋፍ ስልክ: <code>{sup}</code>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 የፓኬጅ ዋጋ ቀይር", callback_data="adm_set_price"), InlineKeyboardButton(text="📊 ኮሚሽን ቀይር", callback_data="adm_set_comm")],
        [InlineKeyboardButton(text="📞 የድጋፍ ስልክ ቀይር", callback_data="adm_set_phone")],
        [InlineKeyboardButton(text="🏠 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "adm_set_price")
async def admin_set_price_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_price)
    await callback.message.answer("አዲሱን የፓኬጅ ዋጋ በቁጥር (ETB) ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_price)
async def admin_save_price(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_price = float(message.text.strip())
        set_setting('package_price', new_price)
        await state.clear()
        await message.answer(f"✅ የፓኬጅ ዋጋ ወደ {new_price} ETB ተቀይሯል!")
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ያስገቡ:")

@router.callback_query(F.data == "adm_set_comm")
async def admin_set_comm_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_commission)
    await callback.message.answer("አዲሱን የኮሚሽን መቶኛ (ለምሳሌ 10 ወይም 15) ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_commission)
async def admin_save_commission(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        new_comm = float(message.text.strip())
        set_setting('commission_percent', new_comm)
        await state.clear()
        await message.answer(f"✅ የኮሚሽን መቶኛ ወደ {new_comm}% ተቀይሯል!")
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ያስገቡ:")

@router.callback_query(F.data == "adm_set_phone")
async def admin_set_phone_prompt(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_support_phone)
    await callback.message.answer("አዲሱን የደንበኛ ድጋፍ ስልክ ቁጥር ጻፉልኝ:")
    await callback.answer()

@router.message(AdminConfig.waiting_for_support_phone)
async def admin_save_support_phone(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    phone = message.text.strip()
    set_setting('support_phone', phone)
    await state.clear()
    await message.answer(f"✅ የድጋፍ ስልክ ቁጥር ወደ {phone} ተቀይሯል!")

# ----------------- CHAPA WEBHOOK ENDPOINT (SERVER) -----------------
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

async def handle_chapa_webhook(request):
    """
    ይህ የድር ሰርቨር (Webhook) ቻፓ ክፍያ ሲፈጸም በራሱ በሰርቨሩ በኩል መረጃውን ተቀብሎ 
    ተጠቃሚውን በራስ-ሰር ንቁ (Active) የሚያደርግ ወይም ዋሌቱን የሚሞላ ሎጂክ ነው።
    """
    try:
        data = await request.json()
        tx_ref = data.get("tx_ref")
        status = data.get("status")

        if tx_ref:
            conn = sqlite3.connect("binary_mlm.db")
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, amount, type, status FROM transactions WHERE tx_ref = ?", (tx_ref,))
            tx_row = cursor.fetchone()
            
            if tx_row and tx_row[3] != 'SUCCESS':
                user_id, amount, tx_type, _ = tx_row
                
                # ከቻፓ የተላከው መረጃ ስኬታማ መሆኑን ማረጋገጥ
                if status == "success" or status == "successful":
                    cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                    
                    if tx_type == 'PACKAGE':
                        cursor.execute("UPDATE users SET balance = balance + 0 WHERE user_id = ?", (user_id,))
                        conn.commit()
                        conn.close()
                        
                        # ቦቱን በመጠቀም ማትሪክሱን ማግበር
                        bot = request.app['bot']
                        await activate_user_in_matrix(user_id, bot)
                        try:
                            await bot.send_message(
                                user_id, 
                                "🎉 <b>በቻፓ በኩል የተፈጸመው ክፍያ ተረጋግጧል! አካውንትዎ ንቁ (Active) ሆኗል።</b>", 
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                    elif tx_type == 'DEPOSIT':
                        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
                        conn.commit()
                        conn.close()
                        
                        bot = request.app['bot']
                        try:
                            await bot.send_message(
                                user_id, 
                                f"🎉 <b>ክፍያዎ ተረጋግጧል! {amount} ETB ወደ ዋሌትዎ ገብቷል።</b>", 
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                else:
                    conn.close()
            else:
                if conn:
                    conn.close()
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
    
    # ሬንደር (Render) ላይ ሰርቨሩ እንዳይተኛ እና የቻፓ ዌብሁክ (Webhook) በትክክል እንዲሰራ የድር ሰርቨሩን ማስጀመር
    await start_web_server(bot)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
