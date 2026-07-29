import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import aiohttp

# ----------------- CONFIGURATIONS -----------------
TOKEN = "8909326861:AAGcgDU1iwDewhFyDcm2LcEKTRdntHHQnN0"
ADMIN_ID = 5351353727
CHAPA_SECRET_KEY = "CHASECK-SncZN81MX80yQcPiXJwRXDF6MdgehtNV"
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDlRpfBCqTczyE10snrrK3Zhj"

# የፓኬጅ ዋጋ (በብር) - 5 ሎሚ (Package Price)
PACKAGE_PRICE = 500.0  

logging.basicConfig(level=logging.INFO)
router = Router()

# ----------------- DATABASE SETUP -----------------
def init_db():
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            fullname TEXT,
            referrer_id INTEGER,
            parent_id INTEGER,
            position TEXT, -- 'LEFT' or 'RIGHT'
            is_active INTEGER DEFAULT 0, -- 0: Pending, 1: Active
            balance REAL DEFAULT 0.0
        )
    """)
    
    # Transactions Table
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

# ----------------- DATABASE HELPERS -----------------
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
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, fullname, referrer_id, is_active) VALUES (?, ?, ?, ?, 0)",
                   (user_id, username, fullname, referrer_id))
    conn.commit()
    conn.close()

def activate_user_in_matrix(user_id):
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res:
        conn.close()
        return
    
    referrer_id = res[0]
    
    # If no valid referrer or referrer is admin/not found, place under admin or root
    parent_id, position = find_available_position(referrer_id if referrer_id else ADMIN_ID)
    
    cursor.execute("""
        UPDATE users SET parent_id = ?, position = ?, is_active = 1 WHERE user_id = ?
    """, (parent_id, position, user_id))
    
    conn.commit()
    conn.close()

def find_available_position(start_user_id):
    """BFS to find the first available left or right spot in binary tree"""
    conn = sqlite3.connect("binary_mlm.db")
    cursor = conn.cursor()
    
    queue = [start_user_id]
    while queue:
        current_id = queue.pop(0)
        
        # Check Left child
        cursor.execute("SELECT user_id FROM users WHERE parent_id = ? AND position = 'LEFT'", (current_id,))
        left_child = cursor.fetchone()
        if not left_child:
            conn.close()
            return current_id, 'LEFT'
        else:
            queue.append(left_child[0])
            
        # Check Right child
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
async def cmd_start(message: types.Message):
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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate Account)", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="📊 የኔ አካውንት እና ሊንክ", callback_data="my_account")]
    ])

    welcome_text = (
        f"ሰላም <b>{message.from_user.full_name}</b>!\n\n"
        f"እንኳን ወደ አባብል / <b>Hamsa Lomi Binary System</b> በደህና መጡ።\n"
        f"ማትሪክስ ውስጥ ለመሰለፍ እና ገቢ መፍጠር ለመጀመር መግቢያ ክፍያውን መፈጸም ይኖርብዎታል።"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "my_account")
async def my_account_callback(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("እባክዎ መጀመሪያ /start ይጫኑ።")
        return

    status = "🟢 ንቁ (Active)" if user[6] == 1 else "🔴 ስራ አልጀመረም (Pending)"
    bot_info = await callback.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={callback.from_user.id}"

    text = (
        f"👤 <b>የመለያ መረጃዎ</b>\n\n"
        f"ስም: {callback.from_user.full_name}\n"
        f"ሁኔታ: {status}\n"
        f"ቀሪ ሂሳብ: {user[7]} ብር\n\n"
        f"🔗 <b>የእርስዎ የሪፈራል ሊንክ:</b>\n`{ref_link}`"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 አሁኑኑ ክፍያ ይፈጽሙ", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="🔙 ወደ ዋናው ገጽ", callback_data="main_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 ፓኬጅ ይግዙ (Activate Account)", callback_data="pay_chapa")],
        [InlineKeyboardButton(text="📊 የኔ አካውንት እና ሊንክ", callback_data="my_account")]
    ])
    await callback.message.edit_text("ወደ ዋናው ገጽ ተመልሰዋል፦", reply_markup=keyboard)

@router.callback_query(F.data == "pay_chapa")
async def pay_with_chapa(callback: types.CallbackQuery):
    user = get_user(callback.from_user.id)
    if user and user[6] == 1:
        await callback.answer("እርስዎ ቀድሞውኑ አካውንትዎ ገብቷል/ነቅቷል!", show_alert=True)
        return

    tx_ref = f"hamsa-lomi-{callback.from_user.id}-{int(asyncio.get_event_loop().time())}"
    
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": str(PACKAGE_PRICE),
        "currency": "ETB",
        "email": f"user{callback.from_user.id}@hamsalomi.com",
        "first_name": callback.from_user.first_name,
        "last_name": callback.from_user.last_name or "Hamsa",
        "tx_ref": tx_ref,
        "callback_url": "https://webhook.site/placeholder", # በቀጣይ ወደ δ your server redirect URL መቀየር ይቻላል
        "customization[title]": "Hamsa Lomi Package",
        "customization[description]": "Binary Matrix Registration Fee"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers) as resp:
            res_data = await resp.json()
            if res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                
                # Save transaction
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO transactions (tx_ref, user_id, amount, status) VALUES (?, ?, ?, 'PENDING')",
                               (tx_ref, callback.from_user.id, PACKAGE_PRICE))
                conn.commit()
                conn.close()

                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔗 በቻፓ ለመክፈል እዚህ ይጫኑ", url=checkout_url)],
                    [InlineKeyboardButton(text="🔄 ክፍያ ከፈጸሙ በኋላ ያረጋግጡ", callback_data=f"verify_{tx_ref}")]
                ])
                await callback.message.edit_text(
                    "💳 <b>የክፍያ ማገናኛ ተዘጋጅቷል!</b>\n\n"
                    "ከታች ያለውን ሊንክ በመጫን በቴሌብር፣ በባንክ ወይም በቻፓ ክፍያዎን ይፈጽሙና <b>ክፍያ ከፈጸሙ በኋላ ያረጋግጡ</b> የሚለውን ይጫኑ።",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await callback.answer("የክፍያ ሊንክ ማመንጨት አልተቻለም። እባክዎ እንደገና ይሞክሩ።", show_alert=True)

@router.callback_query(F.data.startswith("verify_"))
async def verify_payment(callback: types.CallbackQuery):
    tx_ref = callback.data.split("_")[1]
    
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.chapa.co/v1/transaction/verify/{tx_ref}", headers=headers) as resp:
            res_data = await resp.json()
            
            if res_data.get("status") == "success":
                # Update transaction and activate user
                conn = sqlite3.connect("binary_mlm.db")
                cursor = conn.cursor()
                cursor.execute("UPDATE transactions SET status = 'SUCCESS' WHERE tx_ref = ?", (tx_ref,))
                cursor.execute("SELECT user_id FROM transactions WHERE tx_ref = ?", (tx_ref,))
                row = cursor.fetchone()
                conn.commit()
                conn.close()

                if row:
                    user_id = row[0]
                    activate_user_in_matrix(user_id)
                    
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📊 የኔ አካውንት", callback_data="my_account")]
                    ])
                    await callback.message.edit_text(
                        "🎉 <b>እንኳን ደስ አሎት! ክፍያዎ በተሳካ ሁኔታ ተረጋግጧል።</b>\n\n"
                        "አካውንትዎ በባይነሪ ማትሪክስ ውስጥ በትክክል ሰፍሯል። አሁን ሰዎችን በመጋበዝ ገቢ መፍጠር ይችላሉ!",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
            else:
                await callback.answer("❌ ክፍያዎ ገና አልተጠናቀቀም ወይም አልተረጋገጠም። እባክዎ ክፍያውን ከፈጸሙ በኋላ ትንሽ ቆይተው እንደገና ይሞክሩ።", show_alert=True)

# ----------------- MAIN ENTRY -----------------
async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    
    print("Hamsa Lomi Binary Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
