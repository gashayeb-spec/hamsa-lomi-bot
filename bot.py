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

# እዚህ ጋር የሰሩትን የ index.html ሊንክ ያስገቡ (ለምሳሌ: https://your-app.onrender.com/index.html)
WEB_APP_URL = "https://your-render-app-url.com/index.html"

# የ 50 ሎሚ ኦፊሴላዊ የቴሌግራም ቻናል ትስስር
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
        # 🚀 ፎቶ ላይ እንዳየነው ዘመናዊ መተግበሪያ መክፈቻ በለም ግሪን ከለር
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
        f"ከታች ካሉት አማራጮች ውስጥ የሚፈልጉትን መምረጥ ይችላሉ ወይም ከላይ ያለውን **Mini App** መክፈት ይችላሉ።"
    )
    
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_text(welcome_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

# ----------------- MINI APP DATA RECEIVER -----------------
@router.message(F.web_app_data)
async def handle_web_app_data(message: types.Message, state: FSMContext):
    action = message.web_app_data.data
    user = get_user(message.from_user.id)
    
    if action == "pay_chapa":
        fake_callback = types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="pay_chapa")
        await pay_chapa(fake_callback)
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
        f"3. የተጠራቀመውን ገንዘብ በማንኛውም ሰዓት ከዋሌትዎ ውስጥ ማውጣት (Withdraw) ይችላሉ።\n"
        f"4. በኦፊሴላዊው ቻናላችን በመቀላቀል ሌሎች አባላትን ማበረታታት እና መወያየት ይቻላል!"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "tutorial_video")
async def tutorial_video_callback(callback: types.CallbackQuery):
    t_link = get_setting('tutorial_link', str)
    if not t_link or t_link == "0":
        t_link = TUTORIAL_VIDEO_URL
        
    text = (
        f"🎬 <b>የአጠቃቀም ቪዲዮ እና መመሪያ</b>\n\n"
        f"ቦቱን እንዴት መጠቀም እንደሚችሉ፣ ክፍያ እንዴት እንደሚፈጽሙ እና ሊንክዎን እንዴት ማጋራት እንዳለብዎ የሚያሳይ መመሪያ ከታች ባለው ሊንክ ማየት ይችላሉ፦\n\n"
        f"🔗 <a href='{t_link}'>መመሪያውን ለማየት እዚህ ይጫኑ</a>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📺 ቻናሉን ይጎብኙ", url=t_link)],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=False)

# ----------------- WALLET & WITHDRAWAL -----------------
@router.callback_query(F.data == "my_account")
async def my_account_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("እባክዎ መጀመሪያ /start ይጫኑ።")
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
            f"👥 የጠሯቸው ሰዎች ብዛት: <b>{total_refs}</b> (ንቁ: {active_refs})\n\n"
            f"⚠️ <b>ማሳሰቢያ፦</b> የሪፈራል ሊንክዎን ለማግኘት እና ገንዘብ ማውጣት ለመጀመር መጀመሪያ የፓኬጅ ክፍያ መፈጸም አለብዎት!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 አሁኑኑ ፓኬጅ ይግዙ (Activate)", callback_data="pay_chapa")],
            [InlineKeyboardButton(text="📢 ቻናሉን ይቀላቀሉ", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
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
            f"👥 የጠሯቸው ሰዎች: ጠቅላላ <b>{total_refs}</b> | ንቁ አባላት: <b>{active_refs}</b>\n\n"
            f"🔗 <b>የእርስዎ የሪፈራል ሊንክ:</b>\n`{ref_link}`"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💸 ገንዘብ ማውጣት (Withdraw)", callback_data="request_withdraw")],
            [InlineKeyboardButton(text="📤 ሊንኩን ሼር ያድርጉ", url=share_url)],
            [InlineKeyboardButton(text="💬 የኦፊሴላዊ ቻናል", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
            [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
        ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

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
    await callback.message.edit_text(
        f"💸 <b>የገንዘብ ማውጫ (Withdrawal) አማራጮች</b>\n\n"
        f"አሁን በዋሌትዎ ውስጥ ያለው ቀሪ ሂሳብ: <b>{balance} ብር</b>\n"
        f"የመቀበያ አካውንትዎ: <b>{user[9]}</b>\n\n"
        f"ማውጣት የሚፈልጉትን የብር መጠን ይጻፉልኝ፦"
    )

@router.message(WithdrawStates.waiting_for_amount)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ የቁጥር መጠን ብቻ ያስገቡ።")
        return
        
    user = get_user(message.from_user.id)
    balance = user[7]
    
    if amount <= 0:
        await message.answer("❌ ትክክለኛ ያልሆነ መጠን።")
        return
        
    if amount > balance:
        await message.answer(f"❌ በዋሌትዎ ውስጥ ያለው ከፍተኛ ሂሳብ {balance} ብር ብቻ ነው። እንደገና ትክክለኛ መጠን ያስገቡ፦")
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
            f"🔔 <b>አዲስ የገንዘብ ማውጣት (Withdrawal) ጥያቄ!</b>\n\n"
            f"👤 ተጠቃሚ: {message.from_user.full_name} (ID: <code>{message.from_user.id}</code>)\n"
            f"💰 የተጠየቀ መጠን: <b>{amount} ብር</b>\n"
            f"📞 ስልክ ቁጥር: {user[8]}\n"
            f"🏦 የክፍያ አካውንት: {user[9]}\n\n"
            f"<i>እባክዎ ከታች ያሉትን ቁልፎች በመጫን ያጽድቁ ወይም ውድቅ ያድርጉ!</i>"
        )
        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ አጽድቅ (Approve)", callback_data=f"app_w_{withdrawal_id}"),
                InlineKeyboardButton(text="❌ ውድቅ አድርግ (Reject)", callback_data=f"rej_w_{withdrawal_id}")
            ]
        ])
        await message.bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_keyboard, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to send withdraw notice to admin: {e}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 ወደ ዋሌት ገጽ ተመለስ", callback_data="my_account")]
    ])
    await message.answer(
        f"✅ <b>የገንዘብ ማውጣት ጥያቄዎ ለአድሚን ተልኳል!</b>\n\n"
        f"የጠየቁት መጠን: <b>{amount} ብር</b>\n"
        f"የመቀበያ አካውንትዎ: <b>{user[9]} ({user[8]})</b>\n\n"
        f"አድሚኑ ጥያቄውን አረጋግጦ ሲያጸድቀው ገንዘቡ ወደ አካውንትዎ ይለቀቃል።",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# ----------------- ADMIN WITHDRAW APPROVAL HANDLERS -----------------
@router.callback_query(F.data.startswith("app_w_"))
async def approve_withdrawal(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ትዕዛዝ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    w_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, account_info, status FROM withdrawals WHERE id = ?", (w_id,))
    w_row = cursor.fetchone()
    
    if not w_row:
        conn.close()
        await callback.answer("❌ የጥያቄ መረጃው አልተገኘም!", show_alert=True)
        return
        
    user_id, amount, account_info, status = w_row
    
    if status != 'PENDING':
        conn.close()
        await callback.answer(f"⚠️ ይህ ጥያቄ ቀድሞውኑ ተጠናቋል ({status})!", show_alert=True)
        return

    cursor.execute("UPDATE withdrawals SET status = 'APPROVED' WHERE id = ?", (w_id,))
    conn.commit()
    conn.close()

    try:
        user_msg = (
            f"🎉 <b>የገንዘብ ማውጣት (Withdrawal) ጥያቄዎ ጸድቋል!</b>\n\n"
            f"💰 የተለቀቀው መጠን: <b>{amount} ብር</b>\n"
            f"🏦 አካውንትዎ: {account_info}\n\n"
            f"<i>ገንዘቡ በተጠቀሰው አካውንትዎ ገብቷል። እናመሰግናለን!</i>"
        )
        await callback.bot.send_message(user_id, user_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to notify user about approval: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"✅ <b>ሁኔታ: በአድሚን ጸድቋል (APPROVED)</b>",
        parse_mode="HTML"
    )
    await callback.answer("ጥያቄው በተሳካ ሁኔታ ጸድቋል!", show_alert=True)

@router.callback_query(F.data.startswith("rej_w_"))
async def reject_withdrawal(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ትዕዛዝ ለአድሚን ብቻ ነው!", show_alert=True)
        return

    w_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, account_info, status FROM withdrawals WHERE id = ?", (w_id,))
    w_row = cursor.fetchone()
    
    if not w_row:
        conn.close()
        await callback.answer("❌ የጥያቄ መረጃው አልተገኘም!", show_alert=True)
        return
        
    user_id, amount, account_info, status = w_row
    
    if status != 'PENDING':
        conn.close()
        await callback.answer(f"⚠️ ይህ ጥያቄ ቀድሞውኑ ተጠናቋል ({status})!", show_alert=True)
        return

    cursor.execute("UPDATE withdrawals SET status = 'REJECTED' WHERE id = ?", (w_id,))
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

    try:
        user_msg = (
            f"❌ <b>የገንዘብ ማውጣት (Withdrawal) ጥያቄዎ ውድቅ ተደርጓል!</b>\n\n"
            f"💰 የተጠየቀው መጠን: <b>{amount} ብር</b>\n"
            f"🔄 የተቆረጠው ገንዘብ ተመልሶ ወደ ዋሌትዎ ገብቷል።"
        )
        await callback.bot.send_message(user_id, user_msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"Failed to notify user about rejection: {e}")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n"
        f"❌ <b>ሁኔታ: በአድሚን ውድቅ ተደርጓል (REJECTED - ገንዘቡ ተመልሷል)</b>",
        parse_mode="HTML"
    )
    await callback.answer("ጥያቄው ውድቅ ተደርጓል፣ ገንዘቡም ለተጠቃሚው ተመልሷል።", show_alert=True)

# ----------------- ADMIN PANEL & USER CHECKER -----------------
@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ትዕዛዝ ለአድሚን ብቻ ነው!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 የተጠቃሚ ዝርዝር ፈልግ (Check User)", callback_data="admin_check_user")],
        [InlineKeyboardButton(text="💰 የፓኬጅ ዋጋ ቀይር", callback_data="admin_set_price"), InlineKeyboardButton(text="📈 የኮሚሽን ፐርሰንት ቀይር", callback_data="admin_set_comm")],
        [InlineKeyboardButton(text="🎬 የቪዲዮ መመሪያ ሊንክ ቀይር", callback_data="admin_set_video")],
        [InlineKeyboardButton(text="📢 ለሁሉም ተጠቃሚዎች መልእክት ላክ (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    await callback.message.edit_text("⚙️ <b>የአድሚን መቆጣጠሪያ ፓነል</b>\n\nምን ማስተካከል ይፈልጋሉ?", reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_check_user")
async def admin_check_user_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminCheckUserStates.waiting_for_user_id)
    await callback.message.edit_text("🔍 የትኛውን ተጠቃሚ ማየት ይፈልጋሉ?\n\nእባክዎ የተጠቃሚውን <b>የቴሌግራም ID</b> ወይም <b>ዩዘርናም</b> ይጻፉልኝ:")

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
    
    if not user:
        conn.close()
        await message.answer("❌ ተጠቃሚው በዳታቤዝ ውስጥ አልተገኘም። እንደገና /start በመጫን ይሞክሩ።")
        return
        
    u_id, u_username, u_fullname, u_ref, u_parent, u_pos, u_active, u_bal, u_phone, u_pay = user
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (u_id,))
    total_referred = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ? AND is_active = 1", (u_id,))
    active_referred = cursor.fetchone()[0]
    
    conn.close()
    
    status_text = "🟢 ንቁ (Active)" if u_active == 1 else "🔴 ስራ አልጀመረም (Pending)"
    
    info_text = (
        f"📊 <b>የተጠቃሚ ዝርዝር መረጃ (Admin View)</b>\n\n"
        f"🆔 ID: <code>{u_id}</code>\n"
        f"👤 ስም: {u_fullname}\n"
        f"ዩዘርናም: @{u_username if u_username else 'የሌለው'}\n"
        f"📞 ስልክ: {u_phone if u_phone else 'አልገባም'}\n"
        f"🏦 የክፍያ አካውንት: {u_pay if u_pay else 'አልገባም'}\n"
        f"📌 ሁኔታ: {status_text}\n"
        f"💰 ዋሌት ቀሪ ሂሳብ: <b>{u_bal} ብር</b>\n\n"
        f"👥 <b>የሪፈራል መረጃ፦</b>\n"
        f"• የጠራቸው ጠቅላላ ሰዎች: <b>{total_referred}</b>\n"
        f"• ንቁ (Active) አባላት: <b>{active_referred}</b>\n"
        f"• የጋበዘው ሰው (Referrer ID): {u_ref if u_ref else 'አስተዳዳሪ'}"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ ወደ አድሚን ፓነል ተመለስ", callback_data="admin_panel")]
    ])
    await message.answer(info_text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "admin_set_video")
async def admin_set_video_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_video_link)
    await callback.message.edit_text("🎬 አዲሱን የቪዲዮ መመሪያ ሊንክ ይጻፉልኝ፦")

@router.message(AdminConfig.waiting_for_video_link)
async def process_new_video_link(message: types.Message, state: FSMContext):
    link = message.text.strip()
    set_setting('tutorial_link', link)
    await state.clear()
    await message.answer(f"✅ የቪዲዮ መመሪያ ሊንክ በተሳካ ሁኔታ ተቀይሯል፦\n{link}")

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminConfig.waiting_for_broadcast)
    await callback.message.edit_text("📢 ለሁሉም ተጠቃሚዎች ማስተላለፍ የሚፈልጉትን ጽሁፍ ወይም መልእክት ይጻፉልኝ:")

@router.message(AdminConfig.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    text_to_send = message.text
    await state.clear()
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    sent_count = 0
    for u in users:
        try:
            await message.bot.send_message(u[0], f"📢 <b>ማስታወቂያ ከ 50 ሎሚ አስተዳዳሪ፦</b>\n\n{text_to_send}", parse_mode="HTML")
            sent_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
            
    await message.answer(f"✅ ማስታወቂያው ለተጠቃሚዎች ተልኳል (ተሳክቷል: {sent_count} ተጠቃሚዎች)")

@router.callback_query(F.data == "admin_set_price")
async def admin_set_price(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminConfig.waiting_for_price)
    await callback.message.edit_text("አዲሱን የፓኬጅ ዋጋ (በብር) ይጻፉልኝ፦\n(ለምሳሌ: 500, 1000)")

@router.message(AdminConfig.waiting_for_price)
async def process_new_price(message: types.Message, state: FSMContext):
    try:
        new_price = float(message.text)
        set_setting('package_price', new_price)
        await message.answer(f"✅ የፓኬጅ ዋጋ በተሳካ ሁኔታ ወደ <b>{new_price} ብር</b> ተቀይሯል።", parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

@router.callback_query(F.data == "admin_set_comm")
async def admin_set_comm(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminConfig.waiting_for_commission)
    await callback.message.edit_text("አዲሱን የኮሚሽን ፐርሰንት ይጻፉልኝ፦\n(ለምሳሌ: 10, 15, 20)")

@router.message(AdminConfig.waiting_for_commission)
async def process_new_comm(message: types.Message, state: FSMContext):
    try:
        new_comm = float(message.text)
        set_setting('commission_percent', new_comm)
        await message.answer(f"✅ የኮሚሽን ፐርሰንት በተሳካ ሁኔታ ወደ <b>{new_comm}%</b> ተቀይሯል።", parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

# ----------------- PAYMENT PROCESS (CHAPA) -----------------
@router.callback_query(F.data == "pay_chapa")
async def pay_with_chapa(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[6] == 1:
        await callback.answer("እርስዎ ቀድሞውኑ አካውንትዎ ገብቷል/ነቅቷል!", show_alert=True)
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
                await callback.message.edit_text(
                    f"💳 <b>የክፍያ ማገናኛ ተዘጋጅቷል! (መጠን: {package_price} ብር)</b>\n\n"
                    "ከታች ያለውን ሊንክ በመጫን በቴሌብር፣ በባንክ ወይም በቻፓ ክፍያዎን ይፈጽሙና <b>ክፍያ ከፈጸሙ በኋላ ያረጋግጡ</b> የሚለውን ይጫኑ።",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                err_msg = res_data.get("message", "Unknown error")
                await callback.answer(f"የክፍያ ሊንክ ስህተት: {err_msg}", show_alert=True)

@router.callback_query(F.data.startswith("verify_"))
async def verify_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_", 1)[1]
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, user_id FROM transactions WHERE tx_ref = ?", (tx_ref,))
    tx_row = cursor.fetchone()
    
    if not tx_row:
        cursor.execute("SELECT tx_ref, status FROM transactions WHERE user_id = ? ORDER BY rowid DESC LIMIT 1", (callback.from_user.id,))
        last_tx = cursor.fetchone()
        if last_tx:
            tx_ref = last_tx[0]
            db_status = last_tx[1]
            user_id = callback.from_user.id
        else:
            conn.close()
            await callback.answer("❌ የግብይት መረጃ አልተገኘም።", show_alert=True)
            return
    else:
        db_status, user_id = tx_row

    conn.close()

    if db_status == 'SUCCESS':
        await callback.answer("✅ ይህ ክፍያ ቀድሞውኑ ተረጋግጦ አካውንትዎ ነቅቷል!", show_alert=True)
        return

    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            
            is_success_response = False
            if resp.status == 200:
                if res_data.get("status") == "success":
                    data_obj = res_data.get("data", {})
                    if data_obj.get("status") == "success":
                        is_success_response = True

            if is_success_response:
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                conn.commit()
                conn.close()

                activated = activate_user_in_matrix(user_id)
                
                if activated:
                    package_price = get_setting('package_price', float)
                    try:
                        admin_notification_text = (
                            f"🔔 <b>አዲስ የተሳካ ክፍያ (Payment Confirmed)!</b>\n\n"
                            f"👤 ተጠቃሚ: {callback.from_user.full_name} (ID: <code>{user_id}</code>)\n"
                            f"💰 የተከፈለ መጠን: <b>{package_price} ብር</b>\n"
                            f"🔖 የግብይት ቁጥር (TxRef): <code>{tx_ref}</code>\n"
                            f"🟢 ሁኔታ: አካውንቱ በማትሪክስ ውስጥ ሰፍሯል!"
                        )
                        await callback.bot.send_message(ADMIN_ID, admin_notification_text, parse_mode="HTML")
                    except Exception as e:
                        logging.error(f"Failed to send admin notification: {e}")

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 የኔ ዋሌት እና አካውንት", callback_data="my_account")],
                    [InlineKeyboardButton(text="📢 ኦፊሴላዊ ቻናል", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")]
                ])
                await callback.message.edit_text(
                    f"🎉 <b>እንኳን ደስ አሎት! ክፍያዎ በተሳካ ሁኔታ ተረጋግጧል።</b>\n\n"
                    f"አካውንትዎ በባይነሪ ማትሪክስ ውስጥ በትክክል ሰፍሯል፤ አሁን የሪፈራል ሊንክዎ እና የዋሌት ቁልፍዎ ነቅቷል!",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback.answer("❌ ክፍያዎ በባንክ በኩል ገና አልተረጋገጠም። እባክዎ ትንሽ ቆይተው እንደገና ይሞክሩ።", show_alert=True)

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
    print(f"Web server started on port {port}")

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    commands = [
        BotCommand(command="start", description="ቦቱን ለመጀመር / ዋናው ገጽ"),
    ]
    await bot.set_my_commands(commands)

    await start_web_server()
    
    print("50 Lomi Binary Bot is running with Mini App integration...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
