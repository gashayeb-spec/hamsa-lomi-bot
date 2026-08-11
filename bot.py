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


# የምዝገባ እርምጃዎች (Steps 1 to 5 based on UI design)
class RegistrationStates(StatesGroup):
  waiting_for_language = State()
  step1_full_name = State()
  step1_phone = State()
  step1_password = State()
  step2_bank_name = State()
  step2_bank_account = State()
  step3_id_photo = State()
  step3_selfie_photo = State()
  final_review = State()


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
  user_name = message.from_user.full_name

  welcome_text = (
      f"🌟 ሰላም **{user_name}**! ወደ **Birr P2P** እንኳን ደህና መጡ.\n\n"
      "🤖 **What can this bot do? / ይህ ቦት ምን ሊያደርግልዎ ይችላል?**\n"
      "• ደህንነቱ የተጠበቀ የባንክ እና ዩኤስዲቲ (USDT) ንግድ 💳\n"
      "• በ Chapa ክፍያ በቀላሉ ገንዘብ ማስገባት ⚡️\n"
      "• ፈጣን የኮይን እና የሎተሪ አገልግሎቶች 🎟\n\n"
      "✨ እባክዎ አገልግሎቱን ለመጀመር ከታች ያለውን **'🚀 ጀምር / Start'** የሚለውን"
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
      "🌐 እባክዎ የሚፈልጉትን ቋንቋ ይምረጡ:\nPlease choose your preferred language:",
      reply_markup=lang_keyboard,
  )
  await state.set_state(RegistrationStates.waiting_for_language)
  await callback.answer()


@dp.callback_query(F.data.startswith("lang_"))
async def process_language_selection(callback: types.CallbackQuery, state: FSMContext):
  lang = callback.data.split("_")[1]
  await state.update_data(language=lang)

  if lang == "am":
    text = (
        "🇪🇹 **STEP 1 of 5: Your secure login**\n\nእባክዎ ትክክለኛ የ KYC ስምዎን"
        " (Full KYC name) ያስገቡ:"
    )
  else:
    text = (
        "🇬🇧 **STEP 1 of 5: Your secure login**\n\nPlease enter your"
        " real KYC name:"
    )

  await callback.message.edit_text(text, parse_mode="Markdown")
  await state.set_state(RegistrationStates.step1_full_name)
  await callback.answer()


# ================= 2. STEP 1: ACCOUNT & SECURE LOGIN =================


@dp.message(RegistrationStates.step1_full_name)
async def process_full_name(message: types.Message, state: FSMContext):
  await state.update_data(full_name=message.text)
  await message.answer(
      "📱 **Phone Number**\n\nእባክዎ ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፦"
      " 90000XXXX ወይም +2519...):",
      parse_mode="Markdown",
  )
  await state.set_state(RegistrationStates.step1_phone)


@dp.message(RegistrationStates.step1_phone)
async def process_phone(message: types.Message, state: FSMContext):
  phone = message.text.strip()
  if not is_valid_phone(phone):
    await message.answer(
        "❌ ያስገቡት ስልክ ቁጥር ትክክለኛ አይደለም። እባክዎ በ 09፣ 07 ወይም በ +251 የሚጀምር"
        " ትክክለኛ ቁጥር ያስገቡ፦"
    )
    return

  await state.update_data(phone_number=phone)
  await message.answer(
      "🔒 **Password**\n\nጠንካራ የይለፍ ቃል (Password) ይፍጠሩ (ፊደል እና"
      " ቁጥር ከ 4 እስከ 16 ቁምፊዎች):",
      parse_mode="Markdown",
  )
  await state.set_state(RegistrationStates.step1_password)


@dp.message(RegistrationStates.step1_password)
async def process_password(message: types.Message, state: FSMContext):
  password = message.text
  if not is_strong_password(password):
    await message.answer(
        "❌ የይለፍ ቃሉ ሕጉን አልጠበቀም። እባክዎ ፊደል እና ቁጥር ያለው የይለፍ ቃል እንደገና"
        " ያስገቡ፦"
    )
    return

  await state.update_data(password=password)

  bank_keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="Telebirr 🟢", callback_data="bank_telebirr"
              ),
              InlineKeyboardButton(
                  text="CBE (Commercial Bank)", callback_data="bank_cbe"
              ),
          ]
      ]
  )
  await message.answer(
      "🏦 **STEP 2 of 5: Primary bank**\n\nThe bank account name is"
      " locked to your KYC name for payment safety.\n\nእባክዎ የባንክ"
      " ዓይነት ይምረጡ:",
      reply_markup=bank_keyboard,
      parse_mode="Markdown",
  )
  await state.set_state(RegistrationStates.step2_bank_name)


# ================= 3. STEP 2: PRIMARY BANK =================


@dp.callback_query(
    F.data.startswith("bank_"), RegistrationStates.step2_bank_name
)
async def process_bank_choice(callback: types.CallbackQuery, state: FSMContext):
  bank_name = (
      "Telebirr"
      if "telebirr" in callback.data
      else "Commercial Bank of Ethiopia"
  )
  await state.update_data(bank_name=bank_name)

  data = await state.get_data()
  await callback.message.edit_text(
      f"🏦 **Primary bank:** {bank_name}\n\n"
      f"👤 **Locked Account Name:** {data.get('full_name')}\n\n"
      "እባክዎ የባንክ አካውንት ቁጥርዎን ወይም ስልክ ቁጥርዎን ያስገቡ:",
      parse_mode="Markdown",
  )
  await state.set_state(RegistrationStates.step2_bank_account)
  await callback.answer()


@dp.message(RegistrationStates.step2_bank_account)
async def process_bank_account_number(message: types.Message, state: FSMContext):
  await state.update_data(bank_account=message.text)

  await message.answer(
      "🪪 **STEP 3 of 5: Identity photos**\n\nUpload a clear ID image"
      " and take a live selfie for admin review.\n\nእባክዎ"
      " **የብሔራዊ መታወቂያ (National ID)** ፎቶ ይላኩ:",
      parse_mode="Markdown",
  )
  await state.set_state(RegistrationStates.step3_id_photo)


# ================= 4. STEP 3: IDENTITY PHOTOS =================


@dp.message(RegistrationStates.step3_id_photo, F.photo)
async def process_id_photo(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(id_photo=photo_id)
  await message.answer(
      "📸 አሁን ደግሞ የፊት ፎቶዎን (**Selfie**) በካሜራ አንስተው ይላኩ:"
  )
  await state.set_state(RegistrationStates.step3_selfie_photo)


@dp.message(RegistrationStates.step3_selfie_photo, F.photo)
async def process_selfie_photo(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(selfie_photo=photo_id)

  data = await state.get_data()
  summary_text = (
      "📋 **ማጠቃለያ (Registration Summary)**\n\n"
      f"• ሙሉ ስም (KYC): {data.get('full_name')}\n"
      f"• ስልክ ቁጥር: {data.get('phone_number')}\n"
      f"• ባንክ: {data.get('bank_name')} ({data.get('bank_account')})\n\n"
      "እባክዎ መረጃዎ ትክክል መሆኑን አረጋግጦ ለመጨረስ ከታች ያለውን ቁልፍ ይጫኑ!"
  )

  keyboard = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(
                  text="✅ አረጋግጥ እና ጨርስ (Submit)", callback_data="submit_final"
              )
          ]
      ]
  )
  await message.answer(summary_text, reply_markup=keyboard, parse_mode="Markdown")
  await state.set_state(RegistrationStates.final_review)


@dp.callback_query(F.data == "submit_final", RegistrationStates.final_review)
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
