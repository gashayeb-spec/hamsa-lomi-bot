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

# ዴታቤዝ (Memory Database for Users and Settings)
registered_users_db = {}
coin_rate_db = {"coin_price": 10}


# የምዝገባ እርምጃዎች (Single-Flow Registration States)
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

class AdminStates(StatesGroup):
  waiting_for_broadcast = State()
  waiting_for_new_coin_price = State()


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
  user_id = message.from_user.id
  
  if user_id in registered_users_db:
    user_data = registered_users_db[user_id]
    if user_data.get("is_blocked"):
      await message.answer("❌ አካውንትዎ በአድሚን ታግዷል።")
      return
    if user_data.get("status") == "pending":
      await message.answer("⏳ ምዝገባዎ በአድሚን ማረጋገጫ (Pending Verification) ላይ ይገኛል። እባክዎ አድሚኑ እስኪያጸድቀው ይጠብቁ።")
      return
    if user_data.get("status") == "verified":
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
      await message.answer("✅ አካውንትዎ ቀደም ሲል ጸድቋል! ዋናውን ሜኑ መጠቀም ይችላሉ፦", reply_markup=main_menu)
      return

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
      "ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፦ 09xxxxxxxx ወይም 07xxxxxxxx ወይም በ +251 ይጀምሩ)፦",
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
      "🪪 **የ KYC ማረጋገጫ (Identity Verification)**\n\nእባክዎ ትክክለኛ **የኢትዮጵያ ብሔራዊ መታወቂያ (National ID / Fayda)** ወይም **ፓስፖርት የፊት ገጽ (Front Photo)** ግልጽ ፎቶ ይላኩ:",
      reply_markup=keyboard,
      parse_mode="Markdown"
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
      "🪪 **የመታወቂያው የኋላ ገጽ (Back Photo)** ግልጽ ፎቶ ይላኩ:", reply_markup=keyboard, parse_mode="Markdown"
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
      "🪪 **የ KYC ማረጋገጫ (Identity Verification)**\n\nእባክዎ ትክክለኛ **የኢትዮጵያ ብሔራዊ መታወቂያ (National ID / Fayda)** ወይም **ፓስፖርት የፊት ገጽ (Front Photo)** ግልጽ ፎቶ ይላኩ:",
      reply_markup=keyboard,
      parse_mode="Markdown"
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
      "📸 አሁን ደግሞ ከላይ ያስገቡት መታወቂያ ባለቤት እርስዎ መሆንዎን ለማረጋገጥ ፊትዎ በግልጽ የሚታይበትን **የራስዎን ፎቶ (Face ID / Selfie)** ይላኩ:",
      reply_markup=keyboard,
      parse_mode="Markdown"
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
      "🪪 **የመታወቂያው የኋላ ገጽ (Back Photo)** ግልጽ ፎቶ ይላኩ:",
      reply_markup=keyboard,
      parse_mode="Markdown"
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
      "📸 አሁን ደግሞ ከላይ ያስገቡት መታወቂያ ባለቤት እርስዎ መሆንዎን ለማረጋገጥ ፊትዎ በግልጽ የሚታይበትን **የራስዎን ፎቶ (Face ID / Selfie)** ይላኩ:",
      reply_markup=keyboard,
      parse_mode="Markdown"
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

  summary_text = (
      "📋 **የመረጃዎ ማጠቃለያ (Registration Summary)**\n\n"
      f"• ሙሉ ስም፦ {data.get('full_name')}\n"
      f"• ስልክ ቁጥር፦ {data.get('phone_number')}\n"
      f"• የባንክ አካውንት፦ {data.get('bank_account')}\n"
      f"• ኢሜይል፦ {data.get('email')}\n\n"
      "እባክዎ መረጃዎ ትክክል መሆኑን በደንብ ያረጋግጡ። መረጃዎ ትክክል ከሆነ ከታች ያለውን **'አረጋግጥ እና ለአድሚን ላክ (Submit)'** ቁልፍ በመጫን ለአድሚን ማረጋገጫ ይላኩ!"
  )

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="✅ አረጋግጥ እና ለአድሚን ላክ (Submit)", callback_data="submit_reg"
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
  data = await state.get_data()
  user_id = callback.from_user.id
  
  # መረጃዎችን በ Pending (በጥበቃ) ሁኔታ ማስቀመጥ (አድሚን እስኪያጸድቅ ዋሌት አይከፈትም)
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

  # ለአድሚኑ ማሳወቂያ እና የ KYC ፎቶዎችን መላክ
  admin_keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="✅ አረጋግጥ / ቬሪፋይ አድርግ", callback_data=f"admin_verify_{user_id}"),
              InlineKeyboardButton(text="❌ ሰርዝ / ካንሰል", callback_data=f"admin_cancel_{user_id}"),
          ],
          [
              InlineKeyboardButton(text="🚫 አግድ (Block User)", callback_data=f"admin_block_{user_id}")
          ]
      ]
  )

  admin_msg = (
      f"🔔 **አዲስ የ KYC ምዝገባ ማረጋገጫ ይጠብቃል!**\n\n"
      f"• መለያ ቁጥር (ID): `{user_id}`\n"
      f"• ስም፦ {data.get('full_name')}\n"
      f"• ስልክ፦ {data.get('phone_number')}\n"
      f"• ባንክ፦ {data.get('bank_account')}\n"
      f"• ኢሜይል፦ {data.get('email')}"
  )
  
  try:
    await bot.send_message(ADMIN_ID, admin_msg, reply_markup=admin_keyboard, parse_mode="Markdown")
    if data.get("id_front"):
      await bot.send_photo(ADMIN_ID, data.get("id_front"), caption=f"🪪 የ {data.get('full_name')} ናሽናል አይዲ (ፊት)")
    if data.get("id_back"):
      await bot.send_photo(ADMIN_ID, data.get("id_back"), caption=f"🪪 የ {data.get('full_name')} ናሽናል አይዲ (ኋላ)")
    if data.get("face_photo"):
      await bot.send_photo(ADMIN_ID, data.get("face_photo"), caption=f"📸 የ {data.get('full_name')} ፊት ፎቶ (Face ID / Selfie)")
  except Exception as e:
    logging.error(f"Error sending to admin: {e}")

  await callback.message.edit_text(
      "⏳ ምዝገባዎ እና የ KYC ሰነዶችዎ ለአድሚን ተልከዋል!\n\nአድሚኑ መረጃዎን እና መታወቂያዎን በጥንቃቄ አረጋግጦ ሲያጸድቀው (Verify ሲያደርገው) የዋሌት አካውንትዎ ይከፈታል እና ማሳወቂያ ይደርስዎታል። እባክዎ በትዕግስት ይጠብቁ።"
  )
  await callback.answer()


# ================= 2. DEPOSIT & CHAPA INTEGRATION =================


@dp.message(F.text == "ገንዘብ ማስገባት (Deposit)")
async def cmd_deposit(message: types.Message):
  user_id = message.from_user.id
  if user_id not in registered_users_db or registered_users_db[user_id].get("status") != "verified":
    await message.answer("❌ ዋሌትዎ ገና በአድሚን አልጸደቀም። እባክዎ ምዝገባዎ እስኪረጋገጥ ይጠብቁ።")
    return

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
  user_data = registered_users_db.get(user_id, {})
  
  amount = "100.00"
  currency = "ETB"
  email = user_data.get("email", "user@gmail.com")
  first_name = user_data.get("full_name", callback.from_user.first_name)
  last_name = "User"
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
          err_msg = res_data.get("message", "ክፍያ ሊንክ ማመንጨት አልተቻለም። ኪዎቹን (Secret/Public Keys) ያረጋግጡ።")
          await callback.message.answer(f"❌ ስህተት አጋጥሟል፦ {err_msg}")
  except Exception as e:
    await callback.message.answer(
        "የኔትወርክ ወይም የቻፓ ኤፒአይ ኪ (Chapa API Keys) ስህተት አጋጥሟል፣ እባክዎ ኪዎቹን ያረጋግጡ።"
    )

  await callback.answer()


# ================= 3. COIN CONVERSION & LOTTERY SYSTEM =================


@dp.message(F.text == "ብር ወደ ኮይን ቀይር")
async def convert_to_coin(message: types.Message):
  user_id = message.from_user.id
  if user_id not in registered_users_db or registered_users_db[user_id].get("status") != "verified":
    await message.answer("❌ ዋሌትዎ ገና በአድሚን አልጸደቀም።")
    return

  price = coin_rate_db["coin_price"]
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text=f"{price} ብር = 1 ኮይን ቀይር", callback_data="convert_1"
              )
          ],
          [
              InlineKeyboardButton(
                  text=f"{price * 5} ብር = 5 ኮይን ቀይር", callback_data="convert_5"
              )
          ],
      ]
  )
  await message.answer(
      f"ኢትዮ ብር (ETB) ወደ ቦቱ ልዩ ኮይን በመቀየር ሎተሪ መግዛት ይችላሉ፦\nየአሁኑ የኮይን ዋጋ፦ **{price} ብር**",
      reply_markup=keyboard,
      parse_mode="Markdown"
  )


@dp.callback_query(F.data.startswith("convert_"))
async def process_conversion(callback: types.CallbackQuery):
  count = callback.data.split("_")[1]
  price = coin_rate_db["coin_price"] * int(count)
  await callback.message.answer(
      f"✅ በስኬት {price} ብር በመክፈል {count} ኮይን አግኝተዋል!"
  )
  await callback.answer()


@dp.message(F.text == "ሎተሪ መግዛት")
async def buy_lottery(message: types.Message):
  user_id = message.from_user.id
  if user_id not in registered_users_db or registered_users_db[user_id].get("status") != "verified":
    await message.answer("❌ ዋሌትዎ ገና በአድሚን አልጸደቀም።")
    return

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
  user_id = message.from_user.id
  if user_id not in registered_users_db or registered_users_db[user_id].get("status") != "verified":
    await message.answer("❌ ዋሌትዎ ገና በአድሚን አልጸደቀም።")
    return

  await message.answer(
      "💳 ያገኙትን ኮይን ወደ እውነተኛ ገንዘብ (ብር) በመቀየር ወደ ባንክ አካውንትዎ"
      " ለማስተላለፍ የሚፈልጉትን የኮይን መጠን ይጻፉ፦\n\nምሳሌ፦ `50`",
      parse_mode="Markdown",
  )


@dp.message(F.text == "ገንዘብ ማስተላለፍ (P2P)")
async def p2p_transfer_prompt(message: types.Message):
  user_id = message.from_user.id
  if user_id not in registered_users_db or registered_users_db[user_id].get("status") != "verified":
    await message.answer("❌ ዋሌትዎ ገና በአድሚን አልጸደቀም።")
    return

  await message.answer(
      "🔄 ገንዘብ ለሌላ ተጠቃሚ ለማስተላለፍ የውሃ ማስተላለፊያ ትዕዛዝ ይጠቀሙ።"
  )
  try:
    await bot.send_message(ADMIN_ID, f"⚠️ ተጠቃሚ `{user_id}` የ P2P የገንዘብ ማስተላለፍ ሂደት ጀምሯል።", parse_mode="Markdown")
  except:
    pass


# ================= 4. ENHANCED ADMIN CONTROLS =================

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  
  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="📊 የተጠቃሚዎች ብዛት (Users)", callback_data="admin_stats"),
              InlineKeyboardButton(text="📢 ማስታወቂያ ስራ (Announce)", callback_data="admin_broadcast")
          ],
          [
              InlineKeyboardButton(text="🎟 ሎተሪ ድሮ አውጣ (Lottery Draw)", callback_data="admin_lottery_draw"),
              InlineKeyboardButton(text="🪙 የኮይን ዋጋ ቀይር (Change Price)", callback_data="admin_change_coin_price")
          ]
      ]
  )
  await message.answer("👑 **የአድሚን መቆጣጠሪያ ፓነል (Admin Panel)**\n\nከታች ያሉትን አማራጮች በመምረጥ ቦቱን መቆጣጠር ይችላሉ፦", reply_markup=keyboard, parse_mode="Markdown")


@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return
  total_users = len(registered_users_db)
  verified_users = sum(1 for u in registered_users_db.values() if u.get("status") == "verified")
  
  await callback.message.answer(
      f"📊 **የቦቱ አጠቃላይ ስታቲስቲክስ**\n\n"
      f"• አጠቃላይ የተመዘገቡ ተጠቃሚዎች፦ **{total_users}**\n"
      f"• የተረጋገጡ (Verified) ዋሌቶች፦ **{verified_users}**\n"
      f"• የአሁኑ የኮይን ዋጋ፦ **{coin_rate_db['coin_price']} ብር**"
  )
  await callback.answer()


@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery, state: FSMContext):
  if callback.from_user.id != ADMIN_ID:
    return
  await callback.message.answer("📢 ለሁሉም ተጠቃሚዎች ማስተላለፍ የሚፈልጉትን መልእክት አሁን ይጻፉልኝ:")
  await state.set_state(AdminStates.waiting_for_broadcast)
  await callback.answer()


@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
  if message.from_user.id != ADMIN_ID:
    return
  text = message.text
  await state.clear()
  
  success_count = 0
  for uid in registered_users_db.keys():
    try:
      await bot.send_message(uid, f"📢 **ማስታወቂያ ከአድሚን፦**\n\n{text}", parse_mode="Markdown")
      success_count += 1
    except:
      pass
      
  await message.answer(f"✅ ማስታወቂያው ለ **{success_count}** ተጠቃሚዎች በተሳካ ሁኔታ ተልኳል!")


@dp.callback_query(F.data == "admin_lottery_draw")
async def admin_lottery_draw_callback(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return
  if not registered_users_db:
    await callback.message.answer("❌ እስካሁን የተመዘገበ ተጠቃሚ የለም።")
    await callback.answer()
    return
    
  verified_list = [uid for uid, u in registered_users_db.items() if u.get("status") == "verified"]
  if not verified_list:
    await callback.message.answer("❌ እስካሁን የተረጋገጠ (Verified) ተጠቃሚ የለም።")
    await callback.answer()
    return

  winner_id = random.choice(verified_list)
  winner_info = registered_users_db[winner_id]
  
  await callback.message.answer(
      f"🎉 **የሎተሪ ዕጣ አሸናፊ (Lottery Draw Winner)**\n\n"
      f"• መለያ ቁጥር (ID): `{winner_id}`\n"
      f"• ስም፦ {winner_info.get('full_name')}\n"
      f"• ስልክ፦ {winner_info.get('phone_number')}"
  )
  
  try:
    await bot.send_message(winner_id, "🎉 እንኳን ደስ አለዎት! በዛሬው የሎተሪ ዕጣ አሸናፊ ሆናዋል!")
  except:
    pass
    
  await callback.answer()


@dp.callback_query(F.data == "admin_change_coin_price")
async def admin_change_coin_price_callback(callback: types.CallbackQuery, state: FSMContext):
  if callback.from_user.id != ADMIN_ID:
    return
  await callback.message.answer(f"🪙 አዲሱን የኮይን ዋጋ በቁጥር ብቻ ይጻፉ (አሁን ያለው፦ {coin_rate_db['coin_price']} ብር):")
  await state.set_state(AdminStates.waiting_for_new_coin_price)
  await callback.answer()


@dp.message(AdminStates.waiting_for_new_coin_price)
async def process_new_coin_price(message: types.Message, state: FSMContext):
  if message.from_user.id != ADMIN_ID:
    return
  try:
    new_price = int(message.text.strip())
    coin_rate_db["coin_price"] = new_price
    await state.clear()
    await message.answer(f"✅ የኮይን ዋጋ በስኬት ወደ **{new_price} ብር** ተቀይሯል!")
  except ValueError:
    await message.answer("❌ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")


# አድሚን ተጠቃሚን የማረጋገጥ፣ የመሰረዝ ወይም የማግድ እርምጃዎች (Verify, Cancel, Block)
@dp.callback_query(F.data.startswith("admin_verify_"))
async def admin_verify_user(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return
  user_id = int(callback.data.split("_")[2])
  if user_id in registered_users_db:
    registered_users_db[user_id]["status"] = "verified"
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ **[STATUS: VERIFIED & WALLET OPENED]**")
    
    # ተጠቃሚው ቬሪፋይ ሲደረግ ዋሌቱ ይከፈታል እና ሜኑ ይላካለታል
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
    try:
      await bot.send_message(user_id, "🎉 እንኳን ደስ አለዎት! መረጃዎ እና መታወቂያዎ በአድሚን ተረጋግጧል። አሁን የዋሌት አካውንትዎ ተከፍቷል ሙሉ አገልግሎቱን መጠቀም ይችላሉ!", reply_markup=main_menu)
    except:
      pass
  await callback.answer("ተጠቃሚው ተረጋግጧል፣ ዋሌቱ ተከፍቷል!")


@dp.callback_query(F.data.startswith("admin_cancel_"))
async def admin_cancel_user(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return
  user_id = int(callback.data.split("_")[2])
  if user_id in registered_users_db:
    registered_users_db[user_id]["status"] = "rejected"
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ **[STATUS: REJECTED/CANCELLED]**")
    try:
      await bot.send_message(user_id, "❌ የላኩት መታወቂያ ወይም መረጃ ትክክለኛ አለመሆኑ ተረጋግጦ ምዝገባዎ በአድሚን ተሰርዟል። እባክዎ `/start` ብለው እንደገና በትክክል ይመዝገቡ።", parse_mode="Markdown")
    except:
      pass
  await callback.answer("ምዝገባው ተሰርዟል!")


@dp.callback_query(F.data.startswith("admin_block_"))
async def admin_block_user(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    return
  user_id = int(callback.data.split("_")[2])
  if user_id in registered_users_db:
    registered_users_db[user_id]["is_blocked"] = True
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n🚫 **[STATUS: BLOCKED]**")
    try:
      await bot.send_message(user_id, "🚫 አካውንትዎ በአድሚን ታግዷል።")
    except:
      pass
  await callback.answer("ተጠቃሚው ታግዷል!")


@dp.message(Command("users"))
async def admin_users_count(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  total_users = len(registered_users_db)
  verified_users = sum(1 for u in registered_users_db.values() if u.get("status") == "verified")
  await message.answer(
      f"📊 **የተጠቃሚዎች መረጃ**\n\n- አጠቃላይ የተመዘገቡ፦ **{total_users}**\n- የተረጋገጡ (Verified): **{verified_users}**"
  )


@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  await message.answer(
      f"📈 **የቦቱ አጠቃላይ ሁኔታ (Statistics)**\n\n- ንቁ ዋሌቶች፦ {len(registered_users_db)}\n- አጠቃላይ የክፍያ ዝውውር፦ 0 ETB"
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
  
  success_count = 0
  for uid in registered_users_db.keys():
    try:
      await bot.send_message(uid, f"📢 **ማስታወቂያ፦**\n\n{announcement_text}", parse_mode="Markdown")
      success_count += 1
    except:
      pass

  await message.answer(
      f"✅ ማስታወቂያው ለ **{success_count}** ተጠቃሚዎች በስኬት ተልኳል!"
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
