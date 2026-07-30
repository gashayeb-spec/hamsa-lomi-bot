import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
import aiohttp
from aiohttp import web

# ----------------- CONFIGURATIONS -----------------
TOKEN = "8975591959:AAGuD23s5I3jCcBVGc7WEXeO-Kru76NAE2w"
ADMIN_ID = 5351353727
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPiXJwRXDF6MdgchtNV"
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDlRpfBCqTczyE1OsnrrK3Zhj"

WEB_APP_URL = "https://your-render-app-url.com/index.html"

CHANNEL_USERNAME = "@Hamisalomi_bot_official" 
TUTORIAL_VIDEO_URL = "https://t.me/Hamisalomi_bot_official"

logging.basicConfig(level=logging.INFO)
router = Router()

# ----------------- STATES -----------------
class AdminConfig(StatesGroup):
    waiting_for_price = State()
    waiting_for_commission = State()
    waiting_for_m1 = State()
    waiting_for_m2 = State()
    waiting_for_m3 = State()
    waiting_for_broadcast = State()
    waiting_for_video_link = State()

class UserProfileSetup(StatesGroup):
    waiting_for_phone = State()
    waiting_for_payment_info = State()

class WithdrawStates(StatesGroup):
    waiting_for_amount = State()

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
        ('milestone_1', '3000'),
        ('milestone_2', '6000'),
        ('milestone_3', '9000'),
        ('tutorial_link', TUTORIAL_VIDEO_URL)
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
            payment_account TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            tx_ref TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'PENDING'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            account_info TEXT,
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
        return default_type(row[0])
    return default_type(0)

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

def register_pending_user(user_id, username, fullname, referrer_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, fullname, referrer_id, is_active) 
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, username, fullname, referrer_id))
    conn.commit()
    conn.close()

# ----------------- MATRIX & REFERRAL LOGIC -----------------
def activate_user_in_matrix(user_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_active, referrer_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res or res[0] == 1:
        conn.close()
        return False
    
    raw_referrer_id = res[1]
    
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
        await message.answer(
            f"ሰላም <b>{message.from_user.full_name}</b>!\n\n"
            f"እንኳን ወደ 50 ሎሚ በሰላም መጡ! 🤝\n"
            f"የሪፈራል ሊንክ ከመሰጠቱ በፊት እባክዎ አሰራሩን ለማስተካከል <b>ስልክ ቁጥርዎን</b> ይጻፉልኝ፦\n"
            f"<i>(ምሳሌ: 0911223344)</i>",
            parse_mode="HTML"
        )
        return

    await show_main_menu(message, user)

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
    
    keyboard_buttons = [
        [InlineKeyboardButton(text="🚀 የ50 ሎሚ መተግበሪያ ክፈት (Mini App)", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate Account)", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="📊 የኔ ዋሌት እና አካውንት (Wallet)", callback_data="my_account")],
        [InlineKeyboardButton(text="ℹ️ ስለ 50 ሎሚ እና አሰራር (About)", callback_data="bot_about")],
        [InlineKeyboardButton(text="🎬 አጠቃቀም ቪዲዮ መመሪያ (Tutorial)", callback_data="tutorial_video")],
        [InlineKeyboardButton(text="📢 ኦፊሴላዊ ቻናል እና ውይይት", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]
    ]
    
    if is_admin:
        keyboard_buttons.append([InlineKeyboardButton(text="⚙️ አድሚን ፓነል (Admin Settings)", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    current_price = get_setting('package_price', float)
    current_commission = get_setting('commission_percent', float)
    
    welcome_text = (
        f"ሰላም <b>{message_or_callback.from_user.full_name}</b>!\n\n"
        f"እንኳን ወደ 50 ሎሚ በደህና መጡ፤ አምሳሎ ህይወት እንዲህ ነው! 🤝\n\n"
        f"የአሁኑ የፓኬጅ ዋጋ: <b>{current_price} ብር</b>\n"
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

# ----------------- MINI APP DATA RECEIVER -----------------
@router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message, state: FSMContext):
    action = message.web_app_data.data
    user = get_user(message.from_user.id)
    
    if action == "pay_chapa":
        fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="pay_chapa")
        await pay_with_chapa(fake_callback)
    elif action == "my_account":
        fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="my_account")
        await my_account_callback(fake_callback)
    elif action == "bot_about":
        fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="bot_about")
        await bot_about_callback(fake_callback)
    elif action == "tutorial_video":
        fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="tutorial_video")
        await tutorial_video_callback(fake_callback)
    elif action == "main_menu":
        await show_main_menu(message, user)

# ----------------- ABOUT & TUTORIAL HANDLERS -----------------
@router.callback_query(F.data == "bot_about")
async def bot_about_callback(callback: types.CallbackQuery):
    text = (
        f"ℹ️ <b>ስለ 50 ሎሚ ቦት እና አሰራር ማብራሪያ</b>\n\n"
        f"ይህ ቦት ተጠቃሚዎች በአንድነት እርስ በእርስ እየተደጋገፉ ገቢ የሚያገኙበት <b>የባይነሪ ማትሪክስ (Binary MLM System)</b> መድረክ ነው።\n\n"
        f"🔹 <b>እንዴት ይሰራል?</b>\n"
        f"1. መግቢያ ክፍያ በመፈጸም አካውንትዎን ንቁ (Active) ያደርጋሉ።\n"
        f"2. የራስዎን ሪፈራል ሊንክ ለጓደኛዎችዎ በማጋራት አብረን እያደግን ኮሚሽን ይሰበስባሉ።\n"
        f"3. የተጠራቀመውን ገንዘብ በማንኛውም ሰዓት ከዋሌትዎ ውስጥ ማውጣት (Withdraw) ይችላሉ።"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
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
        f"🎬 <b>የአጠቃቀም ቪዲዮ እና መመሪያ</b>\n\n"
        f"ቦቱን እንዴት መጠቀም እንደሚችሉ ከታች ባለው ሊንክ ማየት ይችላሉ፦\n\n"
        f"🔗 <a href='{t_link}'>መመሪያውን ለማየት እዚህ ይጫኑ</a>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 ቻናሉን ይጎብኙ", url=t_link)],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)
    await callback.answer()

# ----------------- WALLET & WITHDRAWAL -----------------
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
    
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (callback.from_user.id,))
    total_refs = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ? AND is_active = 1", (callback.from_user.id,))
    active_refs = cursor.fetchone()[0]
    conn.close()

    if not is_active:
        text = (
            f"💳 <b>የእርስዎ ዋሌት እና አካውንት መረጃ</b>\n\n"
            f"👤 ስም: {callback.from_user.full_name}\n"
            f"📞 ስልክ: {phone}\n"
            f"🏦 የክፍያ አካውንት: {pay_acc}\n"
            f"🔴 ሁኔታ: ስራ አልጀመረም (Pending)\n"
            f"💰 ዋሌት ቀሪ ሂሳብ: <b>{balance} ብር</b>\n\n"
            f"👥 የጠሯቸው ሰዎች: <b>{total_refs}</b> (ንቁ: {active_refs})\n\n"
            f"⚠️ <b>ማሳሰቢያ፦</b> የሪፈራል ሊንክ ለማግኘት መጀመሪያ የፓኬጅ ክፍያ ይፈጽሙ!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 አሁኑኑ ፓኬጅ ይግዙ (Activate)", callback_data="pay_chapa")],
            [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
        ])
    else:
        share_text = f"እንኳን ወደ 50 ሎሚ በሰላም መጡ! አብረን እንስራ፦ {ref_link}"
        share_url = f"https://t.me/share/url?url={ref_link}&text={quote_plus_text(share_text)}"
        
        text = (
            f"💳 <b>የእርስዎ ዋሌት እና አካውንት መረጃ</b>\n\n"
            f"👤 ስም: {callback.from_user.full_name}\n"
            f"📞 ስልክ: {phone}\n"
            f"🏦 የክፍያ አካውንት: {pay_acc}\n"
            f"🟢 ሁኔታ: ንቁ (Active)\n"
            f"💰 ዋሌት ቀሪ ሂሳብ: <b>{balance} ብር</b>\n\n"
            f"👥 የጠሯቸው: ጠቅላላ <b>{total_refs}</b> | ንቁ: <b>{active_refs}</b>\n\n"
            f"🔗 <b>የእርስዎ የሪፈራል ሊንክ:</b>\n`{ref_link}`"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 ገንዘብ ማውጣት (Withdraw)", callback_data="request_withdraw")],
            [InlineKeyboardButton(text="📤 ሊንኩን ሼር ያድርጉ", url=share_url)],
            [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
        ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "request_withdraw")
async def request_withdraw(callback: types.CallbackQuery, state: FSMContext):
    user = get_user(callback.from_user.id)
    if not user or user[6] != 1:
        await callback.answer("አካውንትዎ ንቁ አይደለም!", show_alert=True)
        return
    
    balance = user[7]
    if balance <= 0:
        await callback.answer("❌ በዋሌትዎ ውስጥ ማውጣት የሚችሉት ቀሪ ሂሳብ የለም!", show_alert=True)
        return
        
    await state.set_state(WithdrawStates.waiting_for_amount)
    text = (
        f"💸 <b>የገንዘብ ማውጫ (Withdrawal)</b>\n\n"
        f"ቀሪ ሂሳብዎ: <b>{balance} ብር</b>\n"
        f"ማውጣት የሚፈልጉትን የብር መጠን ይጻፉልኝ፦"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ የቁጥር መጠን ብቻ ያስገቡ።")
        return
        
    user = get_user(message.from_user.id)
    balance = user[7]
    
    if amount <= 0 or amount > balance:
        await message.answer(f"❌ ትክክለኛ ያልሆነ መጠን። ከፍተኛው ሊወጣ የሚችለው {balance} ብር ነው።")
        return

    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, message.from_user.id))
    cursor.execute("INSERT INTO withdrawals (user_id, amount, account_info, status) VALUES (?, ?, ?, 'PENDING')", 
                   (message.from_user.id, amount, f"Phone: {user[8]}, Account: {user[9]}"))
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    await state.clear()
    
    try:
        admin_text = (
            f"🔔 <b>አዲስ የገንዘብ ማውጣት ጥያቄ!</b>\n\n"
            f"👤 ተጠቃሚ: {message.from_user.full_name} (ID: <code>{message.from_user.id}</code>)\n"
            f"💰 መጠን: <b>{amount} ብር</b>\n"
            f"📞 ስልክ: {user[8]}\n"
            f"🏦 አካውንት: {user[9]}"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ አጽድቅ", callback_data=f"app_w_{withdrawal_id}"),
                InlineKeyboardButton(text="❌ ውድቅ", callback_data=f"rej_w_{withdrawal_id}")
            ]
        ])
        await message.bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to notify admin: {e}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 ወደ ዋሌት ገጽ ተመለስ", callback_data="my_account")]
    ])
    await message.answer("✅ የገንዘብ ማውጣት ጥያቄዎ ለአድሚን ተልኳል!", reply_markup=keyboard, parse_mode="HTML")

# ----------------- ADMIN WITHDRAW APPROVAL HANDLERS -----------------
@router.callback_query(F.data.startswith("app_w_"))
async def approve_withdrawal(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    w_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, account_info, status FROM withdrawals WHERE id = ?", (w_id,))
    w_row = cursor.fetchone()
    
    if not w_row or w_row[3] != 'PENDING':
        conn.close()
        await callback.answer("ጥያቄው አልተገኘም ወይም ተጠናቋል!", show_alert=True)
        return
        
    user_id, amount, account_info, _ = w_row
    cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (w_id,))
    conn.commit()
    conn.close()

    try:
        await callback.bot.send_message(user_id, f"🎉 የገንዘብ ማውጣት ጥያቄዎ ጸድቋል! ({amount} ብር)", parse_mode="HTML")
    except Exception:
        pass

    try:
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ ጸድቋል (APPROVED)", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("ጸድቋል!")

@router.callback_query(F.data.startswith("rej_w_"))
async def reject_withdrawal(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    w_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, account_info, status FROM withdrawals WHERE id = ?", (w_id,))
    w_row = cursor.fetchone()
    
    if not w_row or w_row[3] != 'PENDING':
        conn.close()
        await callback.answer("ጥያቄው አልተገኘም ወይም ተጠናቋል!", show_alert=True)
        return
        
    user_id, amount, _, _ = w_row
    cursor.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (w_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

    try:
        await callback.bot.send_message(user_id, f"❌ የገንዘብ ማውጣት ጥያቄዎ ውድቅ ተደርጓል፣ ገንዘቡ ተመልሷል።", parse_mode="HTML")
    except Exception:
        pass

    try:
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ ውድቅ ተደርጓል (REJECTED)", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("ውድቅ ተደርጓል!")

# ----------------- ADMIN PANEL & USER CHECKER -----------------
@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ለአድሚን ብቻ ነው!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 ተጠቃሚ ፈልግ (Check User)", callback_data="admin_check_user")],
        [InlineKeyboardButton(text="💰 የፓኬጅ ዋጋ ቀይር", callback_data="admin_set_price"), InlineKeyboardButton(text="📈 ኮሚሽን ቀይር", callback_data="admin_set_comm")],
        [InlineKeyboardButton(text="🎬 ቪዲዮ መመሪያ ቀይር", callback_data="admin_set_video")],
        [InlineKeyboardButton(text="📢 ማስታወቂያ (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    try:
        await callback.message.edit_text("⚙️ <b>የአድሚን መቆጣጠሪያ ፓነል</b>", reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer("⚙️ <b>የአድሚን መቆጣጠሪያ ፓነል</b>", reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_check_user")
async def admin_check_user_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminCheckUserStates.waiting_for_user_id)
    try:
        await callback.message.edit_text("🔍 የተጠቃሚውን <b>የቴሌግራም ID</b> ወይም <b>ዩዘርናም</b> ይጻፉልኝ:")
    except Exception:
        pass
    await callback.answer()

@router.message(AdminCheckUserStates.waiting_for_user_id)
async def process_admin_check_user(message: types.Message, state: FSMContext):
    query_text = message.text.strip()
    await state.clear()
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    if query_text.isdigit():
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (int(query_text),))
    else:
        cursor.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{query_text.replace('@', '')}%",))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await message.answer("❌ ተጠቃሚው አልተገኘም።")
        return
    
    u_id, u_username, u_fullname, u_ref, _, _, u_active, u_bal, u_phone, u_pay = user
    status_text = "🟢 ንቁ (Active)" if u_active == 1 else "🔴 ስራ አልጀመረም (Pending)"
    
    info_text = (
        f"📊 <b>የተጠቃሚ መረጃ</b>\n\n"
        f"🆔 ID: <code>{u_id}</code>\n"
        f"👤 ስም: {u_fullname}\n"
        f"📞 ስልክ: {u_phone or 'አልገባም'}\n"
        f"🏦 አካውንት: {u_pay or 'አልገባም'}\n"
        f"📌 ሁኔታ: {status_text}\n"
        f"💰 ሂሳብ: <b>{u_bal} ብር</b>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ ወደ አድሚን ፓነል", callback_data="admin_panel")]])
    await message.answer(info_text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_set_video")
async def admin_set_video_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_video_link)
    try:
        await callback.message.edit_text("🎬 አዲሱን የቪዲዮ መመሪያ ሊንክ ይጻፉልኝ፦")
    except Exception:
        pass
    await callback.answer()

@router.message(AdminConfig.waiting_for_video_link)
async def process_new_video_link(message: types.Message, state: FSMContext):
    set_setting('tutorial_link', message.text.strip())
    await state.clear()
    await message.answer("✅ የቪዲዮ መመሪያ ሊንክ ተቀይሯል!")

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_broadcast)
    try:
        await callback.message.edit_text("📢 ለሁሉም ተጠቃሚዎች ማስተላለፍ የሚፈልጉትን ጽሁፍ ይጻፉልኝ:")
    except Exception:
        pass
    await callback.answer()

@router.message(AdminConfig.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    text_to_send = message.text
    await state.clear()
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    for u in users:
        try:
            await message.bot.send_message(u[0], f"📢 <b>ማስታወቂያ፦</b>\n\n{text_to_send}", parse_mode="HTML")
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer("✅ ማስታወቂያው ለተጠቃሚዎች ተልኳል!")

@router.callback_query(F.data == "admin_set_price")
async def admin_set_price(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminConfig.waiting_for_price)
    try:
        await callback.message.edit_text("አዲሱን የፓኬጅ ዋጋ (በብር) ይጻፉልኝ፦")
    except Exception:
        pass
    await callback.answer()

@router.message(AdminConfig.waiting_for_price)
async def process_new_price(message: types.Message, state: FSMContext):
    try:
        set_setting('package_price', float(message.text))
        await message.answer("✅ የፓኬጅ ዋጋ ተቀይሯል!")
        await state.clear()
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

@router.callback_query(F.data == "admin_set_comm")
async def admin_set_comm(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminConfig.waiting_for_commission)
    try:
        await callback.message.edit_text("አዲሱን የኮሚሽን ፐርሰንት ይጻፉልኝ፦")
    except Exception:
        pass
    await callback.answer()

@router.message(AdminConfig.waiting_for_commission)
async def process_new_comm(message: types.Message, state: FSMContext):
    try:
        set_setting('commission_percent', float(message.text))
        await message.answer("✅ የኮሚሽን ፐርሰንት ተቀይሯል!")
        await state.clear()
    except ValueError:
        await message.answer("❌ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

# ----------------- PAYMENT (CHAPA) -----------------
@router.callback_query(F.data == "pay_chapa")
async def pay_with_chapa(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[6] == 1:
        await callback.answer("እርስዎ ቀድሞውኑ አካውንትዎ ነቅቷል!", show_alert=True)
        return

    package_price = get_setting('package_price', float)
    tx_ref = f"hamsa-{callback.from_user.id}-{int(asyncio.get_event_loop().time())}"
    
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(package_price),
        "currency": "ETB",
        "email": f"user{callback.from_user.id}@gmail.com",
        "first_name": callback.from_user.first_name or "User",
        "last_name": callback.from_user.last_name or "Lomi",
        "tx_ref": tx_ref,
        "callback_url": "https://callback.render.com",
        "customization[title]": "50 Lomi",
        "customization[description]": f"Binary Package Fee ({package_price} ETB)"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers) as resp:
            res_data = await resp.json()
            if resp.status == 200 and res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO transactions (tx_ref, user_id, amount, status) VALUES (?, ?, ?, 'PENDING')",
                               (tx_ref, callback.from_user.id, package_price))
                conn.commit()
                conn.close()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 በቻፓ ለመክፈል እዚህ ይጫኑ", url=checkout_url)],
                    [InlineKeyboardButton(text="🔄 ክፍያ ከፈጸሙ በኋላ ያረጋግጡ", callback_data=f"verify_{tx_ref}")]
                ])
                try:
                    await callback.message.edit_text(
                        f"💳 <b>የክፍያ ማገናኛ ተዘጋጅቷል! (መጠን: {package_price} ብር)</b>\n\n"
                        "ሊንኩን በመጫን ክፍያዎን ይፈጽሙና <b>ያረጋግጡ</b> የሚለውን ይጫኑ።",
                        reply_markup=keyboard, parse_mode="HTML"
                    )
                except Exception:
                    await callback.message.answer("የክፍያ ሊንክ ተዘጋጅቷል", reply_markup=keyboard)
            else:
                await callback.answer("የክፍያ ሊንክ መፍጠር አልተቻለም።", show_alert=True)
    await callback.answer()

@router.callback_query(F.data.startswith("verify_"))
async def verify_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_", 1)[1]
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
                conn.commit()
                conn.close()

                activate_user_in_matrix(user_id)
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 የኔ ዋሌት እና አካውንት", callback_data="my_account")]
                ])
                try:
                    await callback.message.edit_text("🎉 <b>ክፍያዎ ተረጋግጧል! አካውንትዎ ነቅቷል።</b>", reply_markup=keyboard, parse_mode="HTML")
                except Exception:
                    pass
            else:
                await callback.answer("❌ ክፍያዎ ገና በባንክ አልተረጋገጠም።", show_alert=True)
    await callback.answer()

def quote_plus_text(text):
    import urllib.parse
    return urllib.parse.quote(text)

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
    except Exception:
        pass
    user = get_user(callback.from_user.id)
    await show_main_menu(callback, user)

# ----------------- WEB SERVER -----------------
async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.set_my_commands([BotCommand(command="start", description="ቦቱን ለመጀመር")])
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
