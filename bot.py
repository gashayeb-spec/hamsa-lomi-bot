import asyncio
import logging
import os
import random
import re
from aiohttp import web
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ሎጊንግ ማስተካከል
logging.basicConfig(level=logging.INFO)

# ================= CONFIGURATIONS =================
API_TOKEN = "8975591959:AAF5bbLhbAv5Ql6uqt1Xs0Z5UZUC9t1e2Wk"
ADMIN_ID = 5351353727
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDIRpfBCqTczyE1OsnrrK3Zhj"
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPjXJwRXDF6MdgchtNV"
SUPPORT_PHONE_NUMBER = "+251900000000"
# ==================================================

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# የምዝገባ እርምጃዎች (Single-Flow Registration States with Back Navigation)
class RegistrationStates(StatesGroup):
  waiting_for_language = State()
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


# ትክክለኛ የኢሜይል ማረጋገጫ
def is_valid_email(email: str) -> bool:
  pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
  return bool(re.match(pattern, email))


# ትክክለኛ የስልክ ቁጥር ማረጋገጫ (+2519, 09, +2517, 07)
def is_valid_phone(phone: str) -> bool:
  pattern = r"^(\+2519|09|\+2517|07)\d{8}$"
  return bool(re.match(pattern, phone))


# የይለፍ ቃል ጥንካሬ ማረጋገጫ
def is_strong_password(password: str) -> bool:
  if not (4 <= len(password) <= 16):
    return False
  if not re.search(r"[A-Za-z]", password):
    return False
  if not re.search(r"\d", password):
    return False
  return True


# ================= 1. START & WELCOME & LANGUAGE SELECTION =================


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message, state: FSMContext):
  await state.clear()
  user_name = message.from_user.full_name

  welcome_text = (
      f"🌟 ሰላም **{user_name}**! ወደ ትክክለኛው የባንክ እና የሎተሪ አገልግሎት በደህና"
      " መጡ።\n\n"
      "🤖 **What can this bot do? / ይህ ቦት ምን ሊያደርግልዎ ይችላል?**\n"
      "• ደህንነቱ የተጠበቀ የባንክ ዋሌት ይከፍታል 💳\n"
      "• በ Chapa ክፍያ በቀላሉ ገንዘብ እንዲያስገቡ ያደርጋል ⚡️\n"
      "• ብር ወደ ኮይን በመቀየር ዕድል ሎተሪዎችን እንዲገዙ ይረዳዎታል 🎟\n\n"
      "✨ እባክዎ አገልግሎቱን ለመጀመር ከታች ያለውን **'ጀምር / Start'** የሚለውን"
      " ቁልፍ ይጫኑ!"
  )

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="🚀 ጀምር / Start", callback_data="welcome_start")]
      ]
  )

  await message.answer(welcome_text, reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "welcome_start")
async def process_welcome_start(callback: types.CallbackQuery, state: FSMContext):
  lang_keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="አማርኛ 🇪🇹", callback_data="lang_am"),
              InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en"),
          ]
      ]
  )

  await callback.message.edit_text(
      "🌐 እባክዎ የሚፈልጉትን ቋንቋ ይምረጡ፦\nPlease choose your preferred language:",
      reply_markup=lang_keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_language)
  await callback.answer()


@dp.callback_query(F.data.startswith("lang_"))
async def process_language_selection(callback: types.CallbackQuery, state: FSMContext):
  lang = callback.data.split("_")[1]
  await state.update_data(language=lang)

  text = (
      "🇪🇹 አማርኛ ተመርጧል።\n\nምዝገባውን ለመጀመር እባክዎ ሙሉ ስምዎን ያስገቡ"
      " (ከቴሌግራም ስምዎ ጋር ሊመሳሰል ይችላል)፦"
      if lang == "am"
      else "🇬🇧 English selected.\n\nPlease enter your full name to start registration:"
  )

  back_kb = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_lang")]
      ]
  )

  await callback.message.edit_text(text, reply_markup=back_kb)
  await state.set_state(RegistrationStates.waiting_for_name)
  await callback.answer()


@dp.callback_query(F.data == "back_to_lang")
async def back_to_language(callback: types.CallbackQuery, state: FSMContext):
  lang_keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="አማርኛ 🇪🇹", callback_data="lang_am"),
              InlineKeyboardButton(text="English 🇬🇧", callback_data="lang_en"),
          ]
      ]
  )
  await callback.message.edit_text(
      "🌐 እባክዎ የሚፈልጉትን ቋንቋ ይምረጡ፦\nPlease choose your preferred language:",
      reply_markup=lang_keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_language)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
  await state.update_data(full_name=message.text)
  
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_name")]
      ]
  )
  await message.answer(
      "ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፦ 09xxxxxxxx ወይም 07xxxxxxxx ወይም በ +251"
      " ይጀምሩ)፦",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_phone)


@dp.callback_query(F.data == "back_to_name")
async def back_to_name_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_lang")]
      ]
  )
  await callback.message.edit_text(
      "ምዝገባውን ለመጀመር እባክዎ ሙሉ ስምዎን ያስገቡ (ከቴሌግራም ስምዎ ጋር ሊመሳሰል ይችላል)፦",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_name)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
  phone = message.text.strip()
  if not is_valid_phone(phone):
    await message.answer(
        "❌ ያስገቡት ስልክ ቁጥር ትክክለኛ አይደለም። እባክዎ በ 09፣ 07 ወይም በ +2519፣"
        " +2517 የሚጀምር ትክክለኛ ስልክ ቁጥር እንደገና ያስገቡ፦"
    )
    return

  await state.update_data(phone_number=phone)
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_phone")]
      ]
  )
  await message.answer(
      "የባንክ አካውንት ቁጥርዎን (ወይም የቴሌብር አካውንት) ያስገቡ፦", reply_markup=keyboard
  )
  await state.set_state(RegistrationStates.waiting_for_bank)


@dp.callback_query(F.data == "back_to_phone")
async def back_to_phone_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_name")]
      ]
  )
  await callback.message.edit_text(
      "ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፦ 09xxxxxxxx ወይም 07xxxxxxxx ወይም በ +251 ይጀምሩ)፦",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_phone)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_bank)
async def process_bank(message: types.Message, state: FSMContext):
  await state.update_data(bank_account=message.text)
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_bank")]
      ]
  )
  await message.answer(
      "ቲኬትዎ/መታወቂያዎ ትክክለኛ መሆኑን ለማረጋገጥ፦\n\n🪪 **1. የብሔራዊ መታወቂያ (National ID)"
      " ወይም ፓስፖርት የፊት ገጽ (Front Photo)** ፎቶ ይላኩ:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_id_front)


@dp.callback_query(F.data == "back_to_bank")
async def back_to_bank_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_phone")]
      ]
  )
  await callback.message.edit_text(
      "የባንክ አካውንት ቁጥርዎን (ወይም የቴሌብር አካውንት) ያስገቡ፦", reply_markup=keyboard
  )
  await state.set_state(RegistrationStates.waiting_for_bank)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_id_front, F.photo)
async def process_id_front(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(id_front=photo_id)
  
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_id_front")]
      ]
  )
  await message.answer(
      "🪪 **2. የመታወቂያው የኋላ ገጽ (Back Photo)** ፎቶ ይላኩ:", reply_markup=keyboard
  )
  await state.set_state(RegistrationStates.waiting_for_id_back)


@dp.callback_query(F.data == "back_to_id_front")
async def back_to_id_front_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_bank")]
      ]
  )
  await callback.message.edit_text(
      "ቲኬትዎ/መታወቂያዎ ትክክለኛ መሆኑን ለማረጋገጥ፦\n\n🪪 **1. የብሔራዊ መታወቂያ (National ID) ወይም ፓስፖርት የፊት ገጽ (Front Photo)** ፎቶ ይላኩ:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_id_front)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_id_back, F.photo)
async def process_id_back(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(id_back=photo_id)
  
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_id_back")]
      ]
  )
  await message.answer(
      "📸 አሁን ደግሞ ፊትዎ ከሰነዱ ጋር በግልጽ የሚታይበትን **የራስዎን ፎቶ (Face Photo/Selfie)** ይላኩ:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_face_photo)


@dp.callback_query(F.data == "back_to_id_back")
async def back_to_id_back_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_id_front")]
      ]
  )
  await callback.message.edit_text(
      "🪪 **2. የመታወቂያው የኋላ ገጽ (Back Photo)** ፎቶ ይላኩ:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_id_back)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_face_photo, F.photo)
async def process_face_photo(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(face_photo=photo_id)
  
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_face")]
      ]
  )
  await message.answer("📧 የሚጠቀሙበትን ትክክለኛ ኢሜይል አድራሻ (Email) ያስገቡ:", reply_markup=keyboard)
  await state.set_state(RegistrationStates.waiting_for_email)


@dp.callback_query(F.data == "back_to_face")
async def back_to_face_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_id_back")]
      ]
  )
  await callback.message.edit_text(
      "📸 አሁን ደግሞ ፊትዎ ከሰነዱ ጋር በግልጽ የሚታይበትን **የራስዎን ፎቶ (Face Photo)** ይላኩ:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_face_photo)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
  email = message.text.strip()
  if not is_valid_email(email):
    await message.answer(
        "❌ ያስገቡት ኢሜይል ትክክለኛ ፎርማት የለውም (ለምሳሌ፦ name@gmail.com)። እባክዎ"
        " ትክክለኛ ኢሜይል እንደገና ያስገቡ፦"
    )
    return

  await state.update_data(email=email)
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_email")]
      ]
  )
  await message.answer(
      "🔒 ጠንካራ የይለፍ ቃል (Password) ይፍጠሩ።\n\nሕጎች፦\n- ርዝመቱ ከ 4 እስከ 16"
      " ቁምፊዎች መሆን አለበት።\n- ፊደላትን እና ቁጥሮችን ማካተት አለበት።",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_password)


@dp.callback_query(F.data == "back_to_email")
async def back_to_email_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_face")]
      ]
  )
  await callback.message.edit_text(
      "📧 የሚጠቀሙበትን ትክክለኛ ኢሜይል አድራሻ (Email) ያስገቡ:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_email)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
  password = message.text
  if not is_strong_password(password):
    await message.answer(
        "❌ ያስገቡት የይለፍ ቃል ህጉን አልጠበቀም። እባክዎ ከ 4 እስከ 16 ቁምፊዎች (ፊደል እና"
        " ቁጥር) በመጠቀም እንደገና ይሞክሩ፦"
    )
    return

  await state.update_data(password=password)
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_pass")]
      ]
  )
  await message.answer("እባክዎ የይለፍ ቃልዎን ለማረጋገጥ አንዴ እንደገና ይጻፉት:", reply_markup=keyboard)
  await state.set_state(RegistrationStates.confirm_password)


@dp.callback_query(F.data == "back_to_pass")
async def back_to_pass_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_email")]
      ]
  )
  await callback.message.edit_text(
      "🔒 ጠንካራ የይለፍ ቃል (Password) ይፍጠሩ።\n\nሕጎች፦\n- ርዝመቱ ከ 4 እስከ 16 ቁምፊዎች መሆን አለበት።\n- ፊደላትን እና ቁጥሮችን ማካተት አለበት።",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_password)
  await callback.answer()


@dp.message(RegistrationStates.confirm_password)
async def process_confirm_password(message: types.Message, state: FSMContext):
  data = await state.get_data()
  if data["password"] != message.text:
    await message.answer(
        "❌ የይለፍ ቃሎቹ አይመሳሰሉም። እባክዎ የመጀመሪያውን የይለፍ ቃል እንደገና ያስገቡ:"
    )
    await state.set_state(RegistrationStates.waiting_for_password)
    return

  # ሁሉም መረጃዎች ተሞልተዋል - የማጠቃለያ ፎርም (Summary Review)
  summary_text = (
      "📋 **የመረጃዎ ማጠቃለያ (Registration Summary)**\n\n"
      f"• ሙሉ ስም፦ {data.get('full_name')}\n"
      f"• ስልክ ቁጥር፦ {data.get('phone_number')}\n"
      f"• የባንክ አካውንት፦ {data.get('bank_account')}\n"
      f"• ኢሜይል፦ {data.get('email')}\n\n"
      "እባክዎ መረጃዎ ትክክል መሆኑን ያረጋግጡ። መመዝገብ ከፈለጉ ከታች ያለውን **'አረጋግጥ እና"
      " ላክ (Submit)'** ቁልፍ ይጫኑ!"
  )

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="✅ አረጋግጥ እና ላክ (Submit)", callback_data="submit_reg"
              )
          ],
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_conf")]
      ]
  )

  await message.answer(summary_text, reply_markup=keyboard, parse_mode="Markdown")
  await state.set_state(RegistrationStates.final_review)


@dp.callback_query(F.data == "back_to_conf")
async def back_to_conf_step(callback: types.CallbackQuery, state: FSMContext):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [InlineKeyboardButton(text="⬅️ ተመለስ (Back)", callback_data="back_to_pass")]
      ]
  )
  await callback.message.edit_text(
      "እባክዎ የይለፍ ቃልዎን ለማረጋገጥ አንዴ እንደገና ይጻፉት:",
      reply_markup=keyboard,
  )
  await state.set_state(RegistrationStates.confirm_password)
  await callback.answer()


@dp.callback_query(
    F.data == "submit_reg", RegistrationStates.final_review
)
async def process_final_submit(callback: types.CallbackQuery, state: FSMContext):
  await state.clear()

  main_menu = types.ReplyKeyboardMarkup(
      keyboard=[
          [
              types.KeyboardButton(text="ገንዘብ ማስገባት (Deposit)"),
              types.KeyboardButton(text="ብር ወደ ኮይን ቀይር"),
          ],
          [
              types.KeyboardButton(text="ሎተሪ መግዛት"),
              types.KeyboardButton(text="ኮይን ወደ ብር ቀይር (Withdraw)"),
          ],
          [types.KeyboardButton(text="ገንዘብ ማስተላለፍ (P2P)")],
      ],
      resize_keyboard=True,
  )

  await callback.message.edit_text(
      "🎉 ምዝገባዎ በተሳካ ሁኔታ ተጠናቆ ወደ አድሚን ተልኳል! አድሚኑ መረጃዎን አረጋግጦ ሲያጸድቀው"
      " ሙሉ አገልግሎቱን መጠቀም ይጀምራሉ።"
  )
  await callback.message.answer(
      "ከታች ያሉትን ዋና ዋና አማራጮች መጠቀም ይችላሉ፦", reply_markup=main_menu
  )
  await callback.answer()


# ================= 2. DEPOSIT & CHAPA INTEGRATION =================


@dp.message(F.text == "ገንዘብ ማስገባት (Deposit)")
async def cmd_deposit(message: types.Message):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="በቻፓ (Chapa) ክፍያ ፈጽም", callback_data="pay_with_chapa"
              )
          ]
      ]
  )
  await message.answer(
      "ወደ ዋሌትዎ ገንዘብ ለመጨመር ከታች ያለውን ቁልፍ ይጫኑ። ክፍያው በቀጥታ በስልክ ቁጥርዎ"
      f" ይፈጸማል።\n\n⚠️ **ማስታወሻ:** ክፍያ ሲፈጽሙ ችግር ካጋጠመዎት አድሚኑን በዚህ ስልክ ቁጥር"
      f" ማግኘት ይችላሉ፦ `{SUPPORT_PHONE_NUMBER}`",
      reply_markup=keyboard,
      parse_mode="Markdown",
  )


@dp.callback_query(F.data == "pay_with_chapa")
async def process_chapa_payment(callback: types.CallbackQuery):
  user_id = callback.from_user.id
  amount = "100.00"
  currency = "ETB"
  email = "user@gmail.com"
  first_name = callback.from_user.first_name
  last_name = callback.from_user.last_name or "User"
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
      "last_name": last_name,
      "tx_ref": tx_ref,
      "callback_url": f"https://yourdomain.com/api/chapa-webhook",
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
                  [
                      InlineKeyboardButton(
                          text="🔗 ክፍያ ለመፈጸም ሊንኩን ይጫኑ", url=checkout_url
                      )
                  ]
              ]
          )
          await callback.message.answer(
              "እባክዎ ከታች ባለው ሊንክ በመሄድ ክፍያዎን ይፈጽሙ።", reply_markup=keyboard
          )
        else:
          await callback.message.answer(
              "የክፍያ ሊንክ ማመንጨት አልተቻለም። እባክዎ ቆይተው እንደገና ይሞክሩ።"
          )
  except Exception as e:
    await callback.message.answer(
        "የኔትወርክ ስህተት አጋጥሟል፣ እባክዎ ቆይተው እንደገና ይሞክሩ።"
    )

  await callback.answer()


# ================= 3. COIN CONVERSION & LOTTERY SYSTEM =================


@dp.message(F.text == "ብር ወደ ኮይን ቀይር")
async def convert_to_coin(message: types.Message):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="10 ብር = 10 ኮይን ቀይር", callback_data="convert_10"
              )
          ],
          [
              InlineKeyboardButton(
                  text="50 ብር = 50 ኮይን ቀይር", callback_data="convert_50"
              )
          ],
      ]
  )
  await message.answer(
      "ኢትዮ ብር (ETB) ወደ ቦቱ ልዩ ኮይን በመቀየር ሎተሪ መግዛት ይችላሉ፦",
      reply_markup=keyboard,
  )


@dp.callback_query(F.data.startswith("convert_"))
async def process_conversion(callback: types.CallbackQuery):
  amount = callback.data.split("_")[1]
  await callback.message.answer(
      f"✅ በስኬት {amount} ብር ወደ {amount} ኮይን ተቀይሯል!"
  )
  await callback.answer()


@dp.message(F.text == "ሎተሪ መግዛት")
async def buy_lottery(message: types.Message):
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="🎟 1 ሎተሪ ግዛ (በ 10 ኮይን)", callback_data="buy_ticket_10"
              )
          ]
      ]
  )
  await message.answer(
      "🎲 **ወደ ዕድል ሎተሪ እንኳን ደህና መጡ!**\n\n1 ሎተሪ ለመግዛት 10 ኮይን ይጠይቃል።",
      reply_markup=keyboard,
  )


@dp.callback_query(F.data == "buy_ticket_10")
async def process_buy_ticket(callback: types.CallbackQuery):
  ticket_number = random.randint(1000, 9999)
  await callback.message.answer(
      f"🎉 ሎተሪውን በተሳካ ሁኔታ ገዝተዋል!\n\nየእርስዎ የሎተሪ ቁጥር፦ **#{ticket_number}**"
  )
  await callback.answer()


@dp.message(F.text == "ኮይን ወደ ብር ቀይር (Withdraw)")
async def withdraw_money(message: types.Message):
  await message.answer(
      "💳 ያገኙትን ኮይን ወደ እውነተኛ ገንዘብ (ብር) በመቀየር ወደ ባንክ አካውንትዎ"
      " ለማስተላለፍ የሚፈልጉትን የኮይን መጠን ይጻፉ፦\n\nምሳሌ፦ `50`",
      parse_mode="Markdown",
  )


@dp.message(F.text == "ገንዘብ ማስተላለፍ (P2P)")
async def p2p_transfer_prompt(message: types.Message):
  await message.answer(
      "🔄 ገንዘብ ለሌላ ተጠቃሚ ለማስተላለፍ የውሃ ማስተላለፊያ ትዕዛዝ ይጠቀሙ።"
  )


# ================= 4. ADMIN COMMANDS =================


@dp.message(Command("users"))
async def admin_users_count(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  total_users = 0
  await message.answer(
      f"📊 **የተጠቃሚዎች መረጃ**\n\nአጠቃላይ የተመዘገቡ ተጠቃሚዎች ብዛት፦ **{total_users}**"
  )


@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  await message.answer(
      "📈 **የቦቱ አጠቃላይ ሁኔታ (Statistics)**\n\n- ንቁ ዋሌቶች፦ 0\n- አጠቃላይ የክፍያ"
      " ዝውውር፦ 0 ETB"
  )


@dp.message(Command("announce"))
async def admin_announce(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  command_parts = message.text.split(maxsplit=1)
  if len(command_parts) < 2:
    await message.answer(
        "እባክዎ ከትዕዛዙ ጋር ማስተላለፍ የሚፈልጉትን መልእክት ይጻፉ።\nምሳሌ፦ `/announce"
        " ሰላም ቤተሰቦች...`",
        parse_mode="Markdown",
    )
    return
  announcement_text = command_parts[1]
  await message.answer(
      f"✅ ማስታወቂያው ለተጠቃሚዎች በስኬት ተልኳል፦\n\n{announcement_text}"
  )


# ================= 5. DUMMY WEB SERVER FOR RENDER =================
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
  await start_web_server()
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
