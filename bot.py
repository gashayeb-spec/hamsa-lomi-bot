import asyncio
import logging
import os
import random
import re
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

logging.basicConfig(level=logging.INFO)

# ================= CONFIGURATIONS =================
API_TOKEN = "8543715567:AAGXh421T4RbiVtoMzaEEefP0Zug7TGaJIQ"
ADMIN_ID = 5351353727
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDIRpfBCqTczyE1OsnrrK3Zhj"
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPjXJwRXDF6MdgchtNV"
SUPPORT_PHONE_NUMBER = "+251900000000"
# ==================================================

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

registered_users_db = {}
coin_rate_db = {"coin_price": 10}

class RegistrationStates(StatesGroup):
  waiting_for_name = State()
  waiting_for_phone = State()
  waiting_for_bank = State()
  waiting_for_id_front = State()
  waiting_for_id_back = State()
  waiting_for_face_photo = State()
  waiting_for_email = State()
  waiting_for_password = State()
  confirm_password = State()
  final_review = State()

class AdminStates(StatesGroup):
  waiting_for_broadcast = State()
  waiting_for_new_coin_price = State()

def is_valid_email(email: str) -> bool:
  return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email))

def is_valid_phone(phone: str) -> bool:
  return bool(re.match(r"^(\+2519|09|\+2517|07)\d{8}$", phone))

def is_strong_password(password: str) -> bool:
  if not (4 <= len(password) <= 16): return False
  if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password): return False
  return True

# ================= START & ANNOUNCEMENT =================

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message, state: FSMContext):
  await state.clear()
  user_id = message.from_user.id
  
  if user_id in registered_users_db:
    user_data = registered_users_db[user_id]
    if user_data.get("is_blocked"):
      await message.answer("❌ አካውንትዎ በአድሚን ታግዷል።")
      return
    if user_data.get("status") == "pending":
      await message.answer("⏳ ምዝገባዎ እና ሰነዶችዎ በአድሚን ማረጋገጫ ላይ ይገኛሉ።")
      return
    if user_data.get("status") == "verified":
      main_menu = ReplyKeyboardMarkup(
          keyboard=[
              [KeyboardButton(text="ገንዘብ ማስገባት (Deposit)"), KeyboardButton(text="ብር ወደ ኮይን ቀይር")],
              [KeyboardButton(text="ሎተሪ መግዛት"), KeyboardButton(text="ኮይን ወደ ብር ቀይር (Withdraw)")],
              [KeyboardButton(text="ገንዘብ ማስተላለፍ (P2P)")],
          ],
          resize_keyboard=True,
      )
      await message.answer("✅ አካውንትዎ ቀደም ሲል ጸድቋል!", reply_markup=main_menu)
      return

  user_name = message.from_user.full_name
  announcement_text = (
      f"📢 **ማስታወቂያ እና የቦቱ አገልግሎት መመሪያ**\n\n"
      f"ሰላም **{user_name}**! ወደ ዋሌት እና ሎተሪ ሲስተም በደህና መጡ።\n\n"
      "📌 **አገልግሎቶች፦**\n1. ደህንነቱ የተጠበቀ ዋሌት\n2. በቻፓ ፈጣን ክፍያ\n3. የኮይን እና ሎተሪ ስርዓት\n4. ጥብቅ KYC ማረጋገጫ\n\n"
      "✨ መረጃውን ካነበቡ በኋላ ለመጀመር ከታች ያለውን ቁልፍ ይጫኑ!"
  )

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="🚀 ጀምር (Start)", callback_data="welcome_start")]
      ]
  )
  await message.answer(announcement_text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data == "welcome_start")
async def process_welcome_start(callback: types.CallbackQuery, state: FSMContext):
  await callback.message.edit_text("ምዝገባውን ለመጀመር እባክዎ ሙሉ ስምዎን (Full Name) ይጻፉ:")
  await state.set_state(RegistrationStates.waiting_for_name)
  await callback.answer()

@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
  await state.update_data(full_name=message.text)
  await message.answer("ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፦ 09xxxxxxxx)፦")
  await state.set_state(RegistrationStates.waiting_for_phone)

@dp.message(RegistrationStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
  phone = message.text.strip()
  if not is_valid_phone(phone):
    await message.answer("❌ ትክክለኛ ስልክ ቁጥር አይደለም። በ 09 ወይም 07 ይጀምሩ:")
    return
  await state.update_data(phone_number=phone)
  await message.answer("የባንክ አካውንት ቁጥርዎን (ወይም የቴሌብር ቁጥር) ያስገቡ፦")
  await state.set_state(RegistrationStates.waiting_for_bank)

@dp.message(RegistrationStates.waiting_for_bank)
async def process_bank(message: types.Message, state: FSMContext):
  await state.update_data(bank_account=message.text)
  await message.answer("🪪 የብሔራዊ መታወቂያ (National ID / Fayda) የፊት ፎቶ ግልጽ ፎቶ ይላኩ:")
  await state.set_state(RegistrationStates.waiting_for_id_front)

@dp.message(RegistrationStates.waiting_for_id_front, F.photo)
async def process_id_front(message: types.Message, state: FSMContext):
  await state.update_data(id_front=message.photo[-1].file_id)
  await message.answer("🪪 የመታወቂያውን የኋላ ገጽ (Back Photo) ፎቶ ይላኩ:")
  await state.set_state(RegistrationStates.waiting_for_id_back)

@dp.message(RegistrationStates.waiting_for_id_back, F.photo)
async def process_id_back(message: types.Message, state: FSMContext):
  await state.update_data(id_back=message.photo[-1].file_id)
  await message.answer("📸 የፊት ፎቶ (Face ID / Selfie) ግልጽ ፎቶ ይላኩ:")
  await state.set_state(RegistrationStates.waiting_for_face_photo)

@dp.message(RegistrationStates.waiting_for_face_photo, F.photo)
async def process_face_photo(message: types.Message, state: FSMContext):
  await state.update_data(face_photo=message.photo[-1].file_id)
  await message.answer("📧 የሚጠቀሙበትን ትክክለኛ ኢሜይል አድራሻ (Email) ያስገቡ:")
  await state.set_state(RegistrationStates.waiting_for_email)

@dp.message(RegistrationStates.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
  email = message.text.strip()
  if not is_valid_email(email):
    await message.answer("❌ ትክክለኛ ኢሜይል አይደለም (ለምሳሌ፦ name@gmail.com)። እንደገና ይሞክሩ:")
    return
  await state.update_data(email=email)
  await message.answer("🔒 ጠንካራ የይለፍ ቃል (Password) ይፍጠሩ (ፊደል እና ቁጥር የያዘ):")
  await state.set_state(RegistrationStates.waiting_for_password)

@dp.message(RegistrationStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
  if not is_strong_password(message.text):
    await message.answer("❌ የይለፍ ቃሉ ሕጉን አልጠበቀም (ፊደል እና ቁጥር ማካተት አለበት):")
    return
  await state.update_data(password=message.text)
  await message.answer("እባክዎ የይለፍ ቃልዎን ለማረጋገጥ አንዴ እንደገና ይጻፉት:")
  await state.set_state(RegistrationStates.confirm_password)

@dp.message(RegistrationStates.confirm_password)
async def process_confirm_password(message: types.Message, state: FSMContext):
  data = await state.get_data()
  if data["password"] != message.text:
    await message.answer("❌ የይለፍ ቃሎቹ አይመሳሰሉም። የመጀመሪያውን የይለፍ ቃል እንደገና ያስገቡ:")
    await state.set_state(RegistrationStates.waiting_for_password)
    return

  summary_text = (
      "📋 **የመረጃዎ ማጠቃለያ**\n\n"
      f"• ስም፦ {data.get('full_name')}\n"
      f"• ስልክ፦ {data.get('phone_number')}\n"
      f"• ባንክ፦ {data.get('bank_account')}\n"
      f"• ኢሜይል፦ {data.get('email')}\n\n"
      "መረጃዎ ትክክል ከሆነ ቁልፉን በመጫን ለአድሚን ይላኩ!"
  )
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="✅ አረጋግጥ እና ላክ (Submit)", callback_data="submit_reg")]
      ]
  )
  await message.answer(summary_text, reply_markup=keyboard, parse_mode="Markdown")
  await state.set_state(RegistrationStates.final_review)

@dp.callback_query(F.data == "submit_reg", RegistrationStates.final_review)
async def process_final_submit(callback: types.CallbackQuery, state: FSMContext):
  data = await state.get_data()
  user_id = callback.from_user.id
  
  registered_users_db[user_id] = {
      "full_name": data.get("full_name"),
      "phone_number": data.get("phone_number"),
      "bank_account": data.get("bank_account"),
      "email": data.get("email"),
      "id_front": data.get("id_front"),
      "id_back": data.get("id_back"),
      "face_photo": data.get("face_photo"),
      "status": "pending",
      "is_blocked": False
  }
  await state.clear()

  admin_keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="✅ አረጋግጥ / ቬሪፋይ", callback_data=f"admin_verify_{user_id}"),
              InlineKeyboardButton(text="❌ ሰርዝ / ካንሰል", callback_data=f"admin_cancel_{user_id}"),
          ]
      ]
  )
  
  try:
    await bot.send_message(
        ADMIN_ID,
        f"🔔 **አዲስ የ KYC ምዝገባ ማረጋገጫ ይጠብቃል!**\n\n• ID: `{user_id}`\n• ስም፦ {data.get('full_name')}\n• ስልክ፦ {data.get('phone_number')}",
        reply_markup=admin_keyboard,
        parse_mode="Markdown"
    )
    if data.get("id_front"): await bot.send_photo(ADMIN_ID, data.get("id_front"))
    if data.get("id_back"): await bot.send_photo(ADMIN_ID, data.get("id_back"))
    if data.get("face_photo"): await bot.send_photo(ADMIN_ID, data.get("face_photo"))
  except Exception as e:
    logging.error(f"Admin send error: {e}")

  await callback.message.edit_text("⏳ ምዝገባዎ ለአድሚን ተልኳል። ሲጸድቅ ማሳወቂያ ይደርስዎታል።")
  await callback.answer()

# ================= CHAPA DEPOSIT =================

@dp.message(F.text == "ገንዘብ ማስገባት (Deposit)")
async def cmd_deposit(message: types.Message):
  user_id = message.from_user.id
  if user_id not in registered_users_db or registered_users_db[user_id].get("status") != "verified":
    await message.answer("❌ ዋሌትዎ ገና በአድሚን አልጸደቀም።")
    return

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="በቻፓ (Chapa) ክፍያ ፈጽም", callback_data="pay_with_chapa")]
      ]
  )
  await message.answer("ወደ ዋሌትዎ ገንዘብ ለመጨመር ከታች ያለውን ቁልፍ ይጫኑ፦", reply_markup=keyboard)

@dp.callback_query(F.data == "pay_with_chapa")
async def process_chapa_payment(callback: types.CallbackQuery):
  user_id = callback.from_user.id
  user_data = registered_users_db.get(user_id, {})
  
  amount = "100.00"
  currency = "ETB"
  email = user_data.get("email", "user@gmail.com")
  first_name = user_data.get("full_name", "User")
  tx_ref = f"txn-{user_id}-{int(callback.message.date.timestamp())}"

  url = "https://api.chapa.co/v1/transaction/initialize"
  headers = {
      "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
      "Content-Type": "application/json",
  }
  payload = {
      "amount": amount,
      "currency": currency,
      "email": email,
      "first_name": first_name,
      "last_name": "Ethio",
      "tx_ref": tx_ref,
      "callback_url": "https://yourdomain.com/webhook",
      "return_url": "https://t.me/bot",
  }

  try:
    async with aiohttp.ClientSession() as session:
      async with session.post(url, json=payload, headers=headers) as response:
        res_data = await response.json()
        if res_data.get("status") == "success":
          checkout_url = res_data["data"]["checkout_url"]
          keyboard = InlineKeyboardMarkup(
              inline_keyboard=[
                  [InlineKeyboardButton(text="🔗 ክፍያ ለመፈጸም ሊንኩን ይጫኑ", url=checkout_url)]
              ]
          )
          await callback.message.answer("እባክዎ ከታች ባለው ሊንክ በመሄድ ክፍያዎን ይፈጽሙ፦", reply_markup=keyboard)
        else:
          err_msg = res_data.get("message", "የክፍያ ሊንክ ማመንጨት አልተቻለም።")
          await callback.message.answer(f"❌ ስህተት አጋጥሟል፦ {err_msg}")
  except Exception as e:
    await callback.message.answer("❌ የኔትወርክ ወይም የቻፓ ግንኙነት ስህተት አጋጥሟል።")

  await callback.answer()

# ================= WALLET FEATURES =================

@dp.message(F.text == "ብር ወደ ኮይን ቀይር")
async def convert_to_coin(message: types.Message):
  await message.answer(f"የአሁኑ የኮይን ዋጋ፦ {coin_rate_db['coin_price']} ብር ነው።")

@dp.message(F.text == "ሎተሪ መግዛት")
async def buy_lottery(message: types.Message):
  await message.answer("🎟 1 ሎተሪ በ 10 ኮይን ተገዝቷል!")

@dp.message(F.text == "ኮይን ወደ ብር ቀይር (Withdraw)")
async def withdraw_money(message: types.Message):
  await message.answer("💳 ማውጣት የሚፈልጉትን የኮይን መጠን ይጻፉ:")

@dp.message(F.text == "ገንዘብ ማስተላለፍ (P2P)")
async def p2p_transfer_prompt(message: types.Message):
  await message.answer("🔄 P2P የገንዘብ ማስተላለፍ አገልግሎት።")

# ================= ADMIN VERIFY & ACTIONS =================

@dp.callback_query(F.data.startswith("admin_verify_"))
async def admin_verify_user(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID: return
  user_id = int(callback.data.split("_")[2])
  
  await callback.answer("⏳ በመረጋገጥ ላይ...")

  if user_id in registered_users_db:
    registered_users_db[user_id]["status"] = "verified"
    try:
      await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ **[STATUS: VERIFIED]**")
    except:
      await callback.message.edit_text(callback.message.text + "\n\n✅ **[STATUS: VERIFIED]**")

    main_menu = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ገንዘብ ማስገባት (Deposit)"), KeyboardButton(text="ብር ወደ ኮይን ቀይር")],
            [KeyboardButton(text="ሎተሪ መግዛት"), KeyboardButton(text="ኮይን ወደ ብር ቀይር (Withdraw)")],
            [KeyboardButton(text="ገንዘብ ማስተላለፍ (P2P)")],
        ],
        resize_keyboard=True,
    )
    try:
      await bot.send_message(user_id, "🎉 እንኳን ደስ አለዎት! መረጃዎ በአድሚን ጸድቋል፣ ዋሌትዎ ተከፍቷል!", reply_markup=main_menu)
    except: pass

@dp.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel_user(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID: return
  user_id = int(callback.data.split("_")[2])
  await callback.answer("⏳ በመሰረዝ ላይ...")
  if user_id in registered_users_db:
    registered_users_db[user_id]["status"] = "rejected"
    try:
      await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ **[STATUS: REJECTED]**")
    except: pass
    try:
      await bot.send_message(user_id, "❌ ምዝገባዎ በአድሚን ተሰርዟል። `/start` ብለው እንደገና ይሞክሩ።")
    except: pass

# ================= WEB SERVER FOR RENDER =================

async def handle_ping(request):
  return web.Response(text="Bot is running!")

async def start_web_server():
  app = web.Application()
  app.router.add_get("/", handle_ping)
  runner = web.AppRunner(app)
  await runner.setup()
  site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 10000)))
  await site.start()

async def main():
  await start_web_server()
  await dp.start_polling(bot)

if __name__ == "__main__":
  asyncio.run(main())
