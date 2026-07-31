import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- CONFIGURATIONS ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPiXJwRXDF6MdgchtNV"
CHAPA_PUBLIC_KEY = "CHAPAPUBK-hLBEJPiKDlRpfBCqTczyE10snrrK3Zhj"
PORT = int(os.getenv("PORT", 10000))

REGISTRATION_FEE = 500.0   
COMMISSION_AMOUNT = 100.0  

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise ValueError("⚠️ BOT_TOKEN environment variable not set!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

users_db = {}  

class WalletAction(StatesGroup):
    waiting_for_topup_amount = State()
    waiting_for_p2p_target = State()
    waiting_for_cbe = State()
    waiting_for_telebirr = State()
    waiting_for_mpesa = State()

# --- START & BINARY TREE REGISTRATION ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split()
    
    referrer_id = None
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
        except ValueError:
            pass

    if user_id not in users_db:
        users_db[user_id] = {
            "referred_by": referrer_id if referrer_id != user_id else None,
            "left": None,
            "right": None,
            "paid": False,
            "balance": 0.0,
            "cbe_account": "አልተመዘገበም (---)",
            "telebirr_phone": "አልተመዘገበም (---)",
            "mpesa_phone": "አልተመዘገበም (---)"
        }
        
        if referrer_id and referrer_id in users_db:
            ref_data = users_db[referrer_id]
            if ref_data["left"] is None:
                ref_data["left"] = user_id
            elif ref_data["right"] is None:
                ref_data["right"] = user_id

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 ዋሌት በቻፓ መሙላት (Top-up)", callback_data="topup_chapa")],
            [types.InlineKeyboardButton(text="👥 በዋሌት ቀሪ ሌላ ሰው መመዝገብ (Pay for Peer)", callback_data="p2p_pay")],
            [types.InlineKeyboardButton(text="👤 የኔ መገለጫ እና ዋሌት", callback_data="my_profile")],
            [types.InlineKeyboardButton(text="⚙️ የባንክ እና ስልክ ቁጥር ማስተካከያ", callback_data="setup_accounts")]
        ]
    )

    welcome_text = (
        f"እንኳን ወደ **Hamsa Lomi Binary Matrix** በደህና መጡ!\n\n"
        f"📌 የአሁኑ የምዝገባ ክፍያ: **{REGISTRATION_FEE} ETB**\n"
        f"📌 የሪፈራል ኮሚሽን: **{COMMISSION_AMOUNT} ETB**\n\n"
        "ከታች ያሉትን አማራጮች በመጠቀም ሲስተሙን ማስተዳደር ይችላሉ።"
    )
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

# --- PROFILE & WALLET ---
@dp.callback_query(F.data == "my_profile")
async def show_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = users_db.get(user_id, {})
    
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user_id}"

    text = (
        f"👤 **የእርስዎ መገለጫ (Profile):**\n\n"
        f"💰 የዋሌት ቀሪ ሂሳብ: **{user.get('balance', 0.0)} ETB**\n"
        f"🟢 የክፍያ ሁኔታ: **{'የተከፈለ (Active)' if user.get('paid') else 'ያልተከፈለ (Inactive)'}**\n\n"
        f"🏦 **የክፍያ መቀበያ መለያዎችዎ:**\n"
        f"• የንግድ ባንክ (CBE): `{user.get('cbe_account')}`\n"
        f"• ቴሌብር (Telebirr): `{user.get('telebirr_phone')}`\n"
        f"• ኤምፔሳ (M-Pesa): `{user.get('mpesa_phone')}`\n\n"
        f"🔗 **የእርስዎ የሪፈራል ሊንክ:**\n`{ref_link}`"
    )
    
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="💳 ዋሌት መሙላት", callback_data="topup_chapa")],
            [types.InlineKeyboardButton(text="🔙 ወደ ዋናው ምናሌ", callback_data="main_menu")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

# --- WALLET TOP-UP VIA CHAPA ---
@dp.callback_query(F.data == "topup_chapa")
async def prompt_topup_amount(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(f"እባክዎ በዋሌትዎ ማስገባት (መሙላት) የሚፈልጉትን የብር መጠን ይጻፉ (ለምሳሌ: `{REGISTRATION_FEE}`):", parse_mode="Markdown")
    await state.set_state(WalletAction.waiting_for_topup_amount)
    await callback.answer()

@dp.message(WalletAction.waiting_for_topup_amount)
async def process_topup_chapa(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("⚠️ እባክዎ ትክክለኛ የቁጥር መጠን ያስገቡ!")
        return

    await state.clear()
    user_id = message.from_user.id
    tx_ref = f"wallet-topup-{user_id}-{int(asyncio.get_event_loop().time())}"

    url = "https://api.chapa.co/v1/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": str(amount),
        "currency": "ETB",
        "email": f"user_{user_id}@hamsa.com",
        "first_name": message.from_user.first_name or "User",
        "tx_ref": tx_ref,
        "customization[title]": "Wallet Top-up",
        "customization[description]": "Adding funds to Matrix Wallet"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            res_data = await response.json()
            if res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                keyboard = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(text="🌐 በቻፓ ክፍያ ለመፈጸም ይጫኑ", url=checkout_url)],
                        [types.InlineKeyboardButton(text="✅ ክፍያ ፈጽሜያለሁ አረጋግጥ", callback_data=f"verify_topup_{tx_ref}_{amount}")]
                    ]
                )
                await message.answer("እባክዎ ከታች ባለው ሊንክ በመሄድ የዋሌት መሙያ ክፍያዎን ይፈጸሙ፦", reply_markup=keyboard)
            else:
                await message.answer("⚠️ የክፍያ ሊንክ ማመንጨት አልተቻለም።")

@dp.callback_query(F.data.startswith("verify_topup_"))
async def verify_topup_action(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    tx_ref = parts[2]
    amount = float(parts[3])
    user_id = callback.from_user.id

    url = f"https://api.chapa.co/v1/transaction/verify/{tx_ref}"
    headers = {"Authorization": f"Bearer {CHAPA_SECRET_KEY}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            res_data = await response.json()
            if res_data.get("status") == "success":
                users_db[user_id]["balance"] += amount
                users_db[user_id]["paid"] = True
                await callback.message.answer(f"🎉 ክፍያዎ ተረጋግጧል! {amount} ETB ወደ ዋሌትዎ ገቢ ሆኗል።")
            else:
                await callback.message.answer("❌ ክፍያው ገና አልተጠናቀቀም።")
    await callback.answer()

# --- P2P / PAY FOR DOWNLINE ---
@dp.callback_query(F.data == "p2p_pay")
async def p2p_prompt(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    user_balance = users_db.get(user_id, {}).get("balance", 0.0)

    if user_balance < REGISTRATION_FEE:
        await callback.answer(f"⚠️ በዋሌትዎ ውስጥ በቂ ብር የለም! (ቀሪ: {user_balance} ETB, የሚያስፈልግ: {REGISTRATION_FEE} ETB)", show_alert=True)
        return

    await callback.message.answer(
        f"👥 በዋሌትዎ ቀሪ ሂሳብ ሌላ አባልን መመዝገብ ይችላሉ።\n"
        f"እባክዎ ሊከፍሉለት የሚፈልጉትን **የተጠቃሚ ቴሌግራም ዩዘር አይዲ (Telegram User ID)** ቁጥር ያስገቡ:"
    )
    await state.set_state(WalletAction.waiting_for_p2p_target)
    await callback.answer()

@dp.message(WalletAction.waiting_for_p2p_target)
async def process_p2p_payment(message: types.Message, state: FSMContext):
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ እባክዎ ትክክለኛ የቁጥር ዩዘር አይዲ (User ID) ያስገቡ!")
        return

    await state.clear()
    payer_id = message.from_user.id

    if payer_id not in users_db or users_db[payer_id]["balance"] < REGISTRATION_FEE:
        await message.answer("⚠️ በቂ ቀሪ ሂሳብ የለዎትም!")
        return

    if target_id not in users_db:
        users_db[target_id] = {
            "referred_by": payer_id,
            "left": None, "right": None,
            "paid": False, "balance": 0.0,
            "cbe_account": "---", "telebirr_phone": "---", "mpesa_phone": "---"
        }

    users_db[payer_id]["balance"] -= REGISTRATION_FEE
    users_db[target_id]["paid"] = True

    referrer_id = users_db[target_id].get("referred_by")
    if referrer_id and referrer_id in users_db:
        users_db[referrer_id]["balance"] += COMMISSION_AMOUNT
        try:
            await bot.send_message(referrer_id, f"💰 በአንዱ እግርዎ ስር አባል በመመዝገቡ {COMMISSION_AMOUNT} ETB ኮሚሽን አግኝተዋል!")
        except Exception:
            pass

    await message.answer(f"✅ ለተጠቃሚ ID `{target_id}` የተደረገው የምዝገባ ክፍያ በዋሌትዎ ተከፍሎ ተጠናቋል!")
    try:
        await bot.send_message(target_id, "🎉 ክፍያዎ በጓደኛዎ/በአስተዋዋቂዎ በኩል ተፈጽሞ አካውንትዎ ገብሯል!")
    except Exception:
        pass

# --- ACCOUNT SETUP ---
@dp.callback_query(F.data == "setup_accounts")
async def setup_accounts_menu(callback: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🏦 የባንክ አካውንት (CBE) ያስገቡ", callback_data="set_cbe")],
            [types.InlineKeyboardButton(text="📱 የቴሌብር ቁጥር ያስገቡ", callback_data="set_telebirr")],
            [types.InlineKeyboardButton(text="🌍 የኤምፔሳ (M-Pesa) ቁጥር ያስገቡ", callback_data="set_mpesa")],
            [types.InlineKeyboardButton(text="🔙 ተመለስ", callback_data="my_profile")]
        ]
    )
    await callback.message.edit_text("⚙️ የሚስተካከለውን የክፍያ አማራጭ ይምረጡ:", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "set_cbe")
async def prompt_cbe(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("እባክዎ የንግድ ባንክ (CBE) የሂሳብ ቁጥርዎን ወይም ስምዎን ያስገቡ:", parse_mode="Markdown")
    await state.set_state(WalletAction.waiting_for_cbe)
    await callback.answer()

@dp.message(WalletAction.waiting_for_cbe)
async def save_cbe(message: types.Message, state: FSMContext):
    users_db[message.from_user.id]["cbe_account"] = message.text
    await state.clear()
    await message.answer("✅ የንግድ ባንክ አካውንትዎ ተመዝግቧል!")

@dp.callback_query(F.data == "set_telebirr")
async def prompt_telebirr(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("እባክዎ የቴሌብር ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ: `+2519...`):", parse_mode="Markdown")
    await state.set_state(WalletAction.waiting_for_telebirr)
    await callback.answer()

@dp.message(WalletAction.waiting_for_telebirr)
async def save_telebirr(message: types.Message, state: FSMContext):
    users_db[message.from_user.id]["telebirr_phone"] = message.text
    await state.clear()
    await message.answer("✅ የቴሌብር ስልክ ቁጥርዎ ተመዝግቧል!")

@dp.callback_query(F.data == "set_mpesa")
async def prompt_mpesa(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("እባክዎ የኤምፔሳ (M-Pesa) ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ: `+2517...`):", parse_mode="Markdown")
    await state.set_state(WalletAction.waiting_for_mpesa)
    await callback.answer()

@dp.message(WalletAction.waiting_for_mpesa)
async def save_mpesa(message: types.Message, state: FSMContext):
    users_db[message.from_user.id]["mpesa_phone"] = message.text
    await state.clear()
    await message.answer("✅ የኤምፔሳ ስልክ ቁጥርዎ ተመዝግቧል!")

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

# --- WEB SERVER FOR RENDER PORT REQUIREMENT ---
async def handle(request):
    return web.Response(text="Hamsa Lomi Bot is running successfully!")

async def web_server():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# --- MAIN FUNCTION ---
async def main():
    print("Hamsa Lomi Advanced Matrix Bot is running...")
    # ዌብ ሰርቨሩን እና የቴሌግራም ቦቱን በአንድ ላይ ማስጀመር
    await web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
