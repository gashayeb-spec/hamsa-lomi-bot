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

# ----------------- CONFIGURATIONS -----------------
TOKEN = "8975591959:AAGuD23s5I3jCcBVGc7WEXeO-Kru76NAE2w"
ADMIN_ID = 5351353727
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPiXJwRXDF6MdgchtNV"
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDlRpfBCqTczyE1OsnrrK3Zhj"

logging.basicConfig(level=logging.INFO)
router = Router()

# ----------------- STATES FOR ADMIN -----------------
class AdminConfig(StatesGroup):
    waiting_for_price = State()
    waiting_for_commission = State()
    waiting_for_m1 = State()
    waiting_for_m2 = State()
    waiting_for_m3 = State()

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
        ('milestone_3', '9000')
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
            balance REAL DEFAULT 0.0
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

def get_total_users_count():
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def register_pending_user(user_id, username, fullname, referrer_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    # ሪፈረር ከሌለ ወይም ራሱ ከሆነ Null ይደረጋል
    cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, fullname, referrer_id, is_active) 
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, username, fullname, referrer_id))
    conn.commit()
    conn.close()

def activate_user_in_matrix(user_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT is_active, referrer_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res or res[0] == 1:
        conn.close()
        return False
    
    referrer_id = res[1]
    parent_id, position = find_available_position(referrer_id if referrer_id else ADMIN_ID)
    
    package_price = get_setting('package_price', float)
    commission_percent = get_setting('commission_percent', float)
    commission_amount = package_price * (commission_percent / 100.0)
    
    if referrer_id:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (commission_amount, referrer_id))
    
    cursor.execute("""
        UPDATE users SET parent_id = ?, position = ?, is_active = 1 WHERE user_id = ?
    """, (parent_id, position, user_id))
    
    conn.commit()
    conn.close()
    return True

def find_available_position(start_user_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    queue = [start_user_id]
    while queue:
        current_id = queue.pop(0)
        
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'LEFT'", (current_id,))
        left_child = cursor.fetchone()
        if not left_child:
            conn.close()
            return current_id, 'LEFT'
        else:
            queue.append(left_child[0])
            
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'RIGHT'", (current_id,))
        right_child = cursor.fetchone()
        if not right_child:
            conn.close()
            return current_id, 'RIGHT'
        else:
            queue.append(right_child[0])
            
    conn.close()
    return start_user_id, 'LEFT'

# ----------------- BOT HANDLERS -----------------
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id == message.from_user.id:
                referrer_id = None
        except ValueError:
            pass

    user = get_user(message.from_user.id)
    if not user:
        register_pending_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.full_name,
            referrer_id
        )
    else:
        # ቀድሞ የተመዘገበ ከሆነ ግን ሪፈረር ከሌለው እና አዲስ ሊንክ ይዞ ከመጣ ማዘመን ይቻላል
        if not user[3] and referrer_id and referrer_id != message.from_user.id:
            conn = sqlite3.connect("binary_mlm.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET referrer_id = ? WHERE user_id = ?", (referrer_id, message.from_user.id))
            conn.commit()
            conn.close()

    keyboard_buttons = [
        [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate Account)", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="📊 የኔ አካውንት እና ሊንክ", callback_data="my_account")],
        [InlineKeyboardButton(text="🎁 የሽልማት እቅዶች (Rewards)", callback_data="rewards_info")]
    ]
    
    if message.from_user.id == ADMIN_ID:
        keyboard_buttons.append([InlineKeyboardButton(text="⚙️ አድሚን ፓነል (Admin Settings)", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    current_price = get_setting('package_price', float)
    current_commission = get_setting('commission_percent', float)
    
    welcome_text = (
        f"ሰላም <b>{message.from_user.full_name}</b>!\n\n"
        f"እንኳን ወደ አብሮነት በሰላም መጡ!\n"
        f"ይህ ማባበያ ሳይሆን ተጋግዘን የምንሰራበት ስራ ነው። "
        f"እንኳን ወደ አብሮነት እድገት በደህና መጡ፤ አምሳሎ ህይወት እንዲህ ነው! 🤝\n\n"
        f"የአሁኑ የፓኬጅ ዋጋ: <b>{current_price} ብር</b>\n"
        f"የስራ ኮሚሽን: <b>{current_commission}%</b>\n\n"
        f"ማትሪክስ ውስጥ ለመሰለፍ እና አብረን ለመስራት መግቢያ ክፍያውን መፈጸም ይኖርብዎታል።"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

# ----------------- ADMIN PANEL -----------------
@router.callback_query(F.data == "admin_panel")
async def admin_panel_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("ይህ ትዕዛዝ ለአድሚን ብቻ ነው!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 የፓኬጅ ዋጋ ቀይር", callback_data="admin_set_price")],
        [InlineKeyboardButton(text="📈 የኮሚሽን ፐርሰንት ቀይር", callback_data="admin_set_comm")],
        [InlineKeyboardButton(text="🏆 የሽልማት ገደቦችን (Milestones) ቀይር", callback_data="admin_set_milestones")],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    await callback.message.edit_text("⚙️ <b>የአድሚን መቆጣጠሪያ ፓነል</b>\n\nምን ማስተካከል ይፈልጋሉ?", reply_markup=keyboard, parse_mode="HTML")

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

@router.callback_query(F.data == "admin_set_milestones")
async def admin_set_m1(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminConfig.waiting_for_m1)
    await callback.message.edit_text("አዲስ ዙር ለመጀመር ወይም ገደቦችን ለመቀየር፦\n\nየመጀመሪያውን ደረጃ ሽልማት ቁጥር ያስገቡ፦\n(ለምሳሌ: 3000)")

@router.message(AdminConfig.waiting_for_m1)
async def process_m1(message: types.Message, state: FSMContext):
    try:
        m1 = int(message.text)
        set_setting('milestone_1', m1)
        await state.set_state(AdminConfig.waiting_for_m2)
        await message.answer(f"✅ ደረጃ 1 ሽልማት ወደ {m1} ተቀይሯል።\n\nአሁን የሁለተኛውን ደረጃ ሽልማት ቁጥር ያስገቡ፦\n(ለምሳሌ: 6000)")
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

@router.message(AdminConfig.waiting_for_m2)
async def process_m2(message: types.Message, state: FSMContext):
    try:
        m2 = int(message.text)
        set_setting('milestone_2', m2)
        await state.set_state(AdminConfig.waiting_for_m3)
        await message.answer(f"✅ ደረጃ 2 ሽልማት ወደ {m2} ተቀይሯል።\n\nበመጨረሻም የሶስተኛውን (ዋናውን) ሽልማት ቁጥር ያስገቡ፦\n(ለምሳሌ: 9000)")
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

@router.message(AdminConfig.waiting_for_m3)
async def process_m3(message: types.Message, state: FSMContext):
    try:
        m3 = int(message.text)
        set_setting('milestone_3', m3)
        await message.answer("🎉 <b>በጣም ጥሩ! አዲሱ የሽልማት ዙር በተሳካ ሁኔታ ተጀምሯል። አባላት በአዲሱ ገደብ መሰረት ሽልማት ይጠብቃሉ።</b>", parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

# ----------------- REGULAR MENUS -----------------
@router.callback_query(F.data == "rewards_info")
async def rewards_info_callback(callback: types.CallbackQuery):
    total_active = get_total_users_count()
    m1 = get_setting('milestone_1', int)
    m2 = get_setting('milestone_2', int)
    m3 = get_setting('milestone_3', int)
    
    text = (
        f"🎁 <b>አጠቃላይ የሽልማት ዝግጅቶች እና አዲስ እቅዶች</b>\n\n"
        f"አሁን ባለንበት ዙር የተዘጋጁልን ልዩ ሽልማቶች፦\n\n"
        f"👥 አጠቃላይ ንቁ አባላት: <b>{total_active} / {m1}</b>\n"
        f"🥉 <b>{m1} አባላት ሲሞሉ:</b> የመጀመሪያ ደረጃ ሽልማት ይዘጋጃል!\n\n"
        f"👥 አጠቃላይ ንቁ አባላት: <b>{total_active} / {m2}</b>\n"
        f"🥈 <b>{m2} አባላት ሲሞሉ:</b> መካከለኛ የትብብር ሽልማት!\n\n"
        f"👥 አጠቃላይ ንቁ አባላት: <b>{total_active} / {m3}</b>\n"
        f"🥇 <b>{m3} አባላት እና ከዚያ በላይ ሲሞሉ:</b> ታላቅ የአብሮነት ዋና ሽልማት!\n\n"
        f"<i>ማሳሰቢያ፦ አንድ ዙር ሽልማት ሲጠናቀቅ በአድሚኑ በኩል አዲስ ዙር እና አዲስ ቁጥር ይፋ ይደረጋል!</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "my_account")
async def my_account_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("እባክዎ መጀመሪያ /start ይጫኑ።")
        return

    is_active = user[6] == 1
    commission_percent = get_setting('commission_percent', float)
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    if not is_active:
        text = (
            f"👤 <b>የመለያ መረጃዎ</b>\n\n"
            f"ስም: {callback.from_user.full_name}\n"
            f"ሁኔታ: 🔴 ስራ አልጀመረም / ክፍያ አልፈጸሙም (Pending)\n"
            f"የኮሚሽን ቀሪ ሂሳብ: {user[7]} ብር\n\n"
            f"⚠️ <b>ማሳሰቢያ፦</b> የሪፈራል ሊንክዎን ለማግኘት እና አብሮነት ስራ ለመጀመር መጀመሪያ የፓኬጅ ክፍያ መፈጸም አለብዎት!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 አሁኑኑ ክፍያ ይፈጽሙ (Activate)", callback_data="pay_chapa")],
            [InlineKeyboardButton(text="🎁 የሽልማት እቅዶች", callback_data="rewards_info")],
            [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
        ])
    else:
        share_text = f"እንኳን ወደ አብሮነት በሰላም መጡ! አብረን እንስራ፦ {ref_link}"
        share_url = f"https://t.me/share/url?url={ref_link}&text={quote_plus_text(share_text)}"
        
        text = (
            f"👤 <b>የመለያ መረጃዎ</b>\n\n"
            f"ስም: {callback.from_user.full_name}\n"
            f"ሁኔታ: 🟢 ንቁ (Active)\n"
            f"የኮሚሽን ({commission_percent}%) ቀሪ ሂሳብ: {user[7]} ብር\n\n"
            f"🔗 <b>የእርስዎ የሪፈራል ሊንክ:</b>\n`{ref_link}`\n\n"
            f"👇 ከታች ባለው ቁልፍ በመጫን ሊንኩን በቀጥታ ለጓደኞችዎ ወይም ግሩፖች ማጋራት (Share ማድረግ) ይችላሉ!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 ሊንኩን ለጓደኛ ሼር ያድርጉ", url=share_url)],
            [InlineKeyboardButton(text="🎁 የሽልማት እቅዶች", callback_data="rewards_info")],
            [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
        ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

def quote_plus_text(text):
    import urllib.parse
    return urllib.parse.quote(text)

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard_buttons = [
        [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate Account)", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="📊 የኔ አካውንት እና ሊንክ", callback_data="my_account")],
        [InlineKeyboardButton(text="🎁 የሽልማት እቅዶች (Rewards)", callback_data="rewards_info")]
    ]
    if callback.from_user.id == ADMIN_ID:
        keyboard_buttons.append([InlineKeyboardButton(text="⚙️ አድሚን ፓነል (Admin Settings)", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text("ወደ ዋናው አብሮነት ገጽ ተመልሰዋል፦", reply_markup=keyboard)

# ----------------- PAYMENT PROCESS -----------------
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
        "last_name": callback.from_user.last_name or "Hamsa",
        "tx_ref": tx_ref,
        "callback_url": "https://callback.render.com",
        "customization[title]": "Hamsa Lomi",
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
    tx_ref = callback.data.split("_")[1]
    
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, user_id FROM transactions WHERE tx_ref = ?", (tx_ref,))
    tx_row = cursor.fetchone()
    conn.close()

    if not tx_row:
        await callback.answer("❌ የግብይት መረጃ አልተገኘም። እባክዎ እንደገና ይሞክሩ።", show_alert=True)
        return

    db_status, user_id = tx_row
    if db_status == 'SUCCESS':
        await callback.answer("✅ ይህ ክፍያ ቀድሞውኑ ተረጋግጦ አካውንትዎ ነቅቷል!", show_alert=True)
        return

    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            
            if resp.status == 200 and res_data.get("status") == "success":
                data_obj = res_data.get("data", {})
                chapa_status = data_obj.get("status")
                
                if chapa_status == "success":
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

                    total_active = get_total_users_count()
                    m1 = get_setting('milestone_1', int)
                    m2 = get_setting('milestone_2', int)
                    m3 = get_setting('milestone_3', int)
                    
                    milestone_msg = ""
                    if total_active == m3:
                        milestone_msg = f"\n\n🏆 <b>እንኳን ደስ አሎት! {m3} አባላት ገደብ አልፏል - የታላቁ ሽልማት ዝግጅት ደርሷል!</b>"
                    elif total_active == m2:
                        milestone_msg = f"\n\n🥈 <b>እንኳን ደስ አሎት! {m2} አባላት ገደብ አልፏል - የመካከለኛ ሽልማት ዝግጅት ተጀምሯል!</b>"
                    elif total_active == m1:
                        milestone_msg = f"\n\n🥉 <b>እንኳን ደስ አሎት! {m1} አባላት ገደብ አልፏል - የምስረታ ሽልማት ዝግጅት ተጀምሯል!</b>"

                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 የኔ አካውንት እና ሊንክ", callback_data="my_account")],
                        [InlineKeyboardButton(text="🎁 የሽልማት እቅዶች", callback_data="rewards_info")]
                    ])
                    await callback.message.edit_text(
                        f"🎉 <b>እንኳን ደስ አሎት! ክፍያዎ በተሳካ ሁኔታ ተረጋግጧል።</b>\n\n"
                        f"አካውንትዎ በባይነሪ ማትሪክስ ውስጥ በትክክል ሰፍሯል፤ አሁን የሪፈራል ሊንክዎ እና የሼር ቁልፍዎ ነቅቷል!{milestone_msg}",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                else:
                    await callback.answer("❌ ክፍያዎ ገና በባንክ በኩል አልተጠናቀቀም (Pending/Failed)። እባክዎ ክፍያውን ከፈጸሙ በኋላ እንደገና ይሞክሩ።", show_alert=True)
            else:
                await callback.answer("❌ ክፍያዎ ገና አልተጠናቀቀም ወይም አልተረጋገጠም። እባክዎ ክፍያውን ከፈጸሙ በኋላ ትንሽ ቆይተው እንደገና ይሞክሩ።", show_alert=True)

# ----------------- WEB SERVER FOR RENDER (FREE WEB SERVICE) -----------------
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
    
    print("Hamsa Lomi Binary Bot is running with Live Keys...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
