import logging
import random
import re
import aiohttp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ሎጊንግ ማስተካከል
logging.basicConfig(level=logging.INFO)

# ================= CONFIGURATIONS (ከእርስዎ ምስል የተወሰዱ) =================
API_TOKEN = "8543715567:AAGXh421T4RbiVtoMzaEEefP0Zug7TGaJIQ"
ADMIN_ID = 5351353727
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDIRpfBCqTczyE1OsnrrK3Zhj"
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPjXJwRXDF6MdgchtNV"
SUPPORT_PHONE_NUMBER = "+251900000000"  # ማስተካከል ከፈለጉ መቀየር ይችላሉ
# ======================================================================

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# የምዝገባ እርምጃዎች (States)
class RegistrationStates(StatesGroup):
  waiting_for_name = State()
  waiting_for_phone = State()
  waiting_for_bank = State()
  waiting_for_id_document = State()
  waiting_for_face_photo = State()
  waiting_for_email = State()
  waiting_for_password = State()
  confirm_password = State()


# የይለፍ ቃል ጥንካሬ ማረጋገጫ (ከ 4 እስከ 16 ቁምፊዎች፣ ፊደል እና ቁጥር የያዘ)
def is_strong_password(password: str) -> bool:
  if not (4 <= len(password) <= 16):
    return False
  if not re.search(r"[A-Za-z]", password):
    return False
  if not re.search(r"\d", password):
    return False
  return True


# ================= 1. START & REGISTRATION FLOW =================


@dp.message(F.text == "/start")
async def cmd_start(message: types.Message, state: FSMContext):
  user_name = message.from_user.full_name
  keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
      [
        InlineKeyboardButton(
          text="አካውንት መክፈት ጀምር", callback_data="start_reg"
        )
      ]
    ]
  )
  await message.answer(
    f"ሰላም **{user_name}**! ወደ ባንክ አገልግሎት ቦታችን በደህና መጡ። ደህንነቱ የተጠበቀ አካውንት ለመክፈት ከታች ያለውን ቁልፍ ይጫኑ።",
    reply_markup=keyboard,
    parse_mode="Markdown",
  )


@dp.callback_query(F.data == "start_reg")
async def process_start_reg(callback: types.CallbackQuery, state: FSMContext):
  await callback.message.answer(
    "እባክዎ ሙሉ ስምዎን ይጻፉ (ከቴሌግራም ስምዎ ጋር ሊመሳሰል ይችላል ወይም መቀየር ይችላሉ)፦"
  )
  await state.set_state(RegistrationStates.waiting_for_name)
  await callback.answer()


@dp.message(RegistrationStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
  await state.update_data(full_name=message.text)
  await message.answer(
    "እባክዎ ስልክ ቁጥርዎን ያስገቡ (ለምሳሌ፦ +2519xxxxxxxx)፦"
  )
  await state.set_state(RegistrationStates.waiting_for_phone)


@dp.message(RegistrationStates.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
  await state.update_data(phone_number=message.text)
  await message.answer(
    "እባክዎ የባንክ አካውንት ቁጥርዎን (ወይም የቴሌብር አካውንት) ያስገቡ፦"
  )
  await state.set_state(RegistrationStates.waiting_for_bank)


@dp.message(RegistrationStates.waiting_for_bank)
async def process_bank(message: types.Message, state: FSMContext):
  await state.update_data(bank_account=message.text)
  await message.answer(
    "እባክዎ የብሔራዊ መታወቂያ (National ID) ወይም የፓስፖርት ፎቶ ይላኩ (Document):"
  )
  await state.set_state(RegistrationStates.waiting_for_id_document)


@dp.message(RegistrationStates.waiting_for_id_document, F.photo)
async def process_id_doc(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(id_document=photo_id)
  await message.answer(
    "አሁን ደግሞ ፊትዎ ከሰነዱ ጋር በግልጽ የሚታይበትን የራስዎን ፎቶ (Face Photo) ይላኩ:"
  )
  await state.set_state(RegistrationStates.waiting_for_face_photo)


@dp.message(RegistrationStates.waiting_for_face_photo, F.photo)
async def process_face_photo(message: types.Message, state: FSMContext):
  photo_id = message.photo[-1].file_id
  await state.update_data(face_photo=photo_id)
  await message.answer(
    "እባክዎ የሚጠቀሙበትን ትክክለኛ ኢሜይል አድራሻ (Email) ያስገቡ:"
  )
  await state.set_state(RegistrationStates.waiting_for_email)


@dp.message(RegistrationStates.waiting_for_email)
async def process_email(message: types.Message, state: FSMContext):
  await state.update_data(email=message.text)
  await message.answer(
    "አሁን ጠንካራ የይለፍ ቃል (Password) ይፍጠሩ።\n\nሕጎች፦\n- ርዝመቱ ከ 4 እስከ 16 ቁምፊዎች መሆን አለበት።\n- ፊደላትን እና ቁጥሮችን ማካተት አለበት።"
  )
  await state.set_state(RegistrationStates.waiting_for_password)


@dp.message(RegistrationStates.waiting_for_password)
async def process_password(message: types.Message, state: FSMContext):
  password = message.text
  if not is_strong_password(password):
    await message.answer(
      "ያስገቡት የይለፍ ቃል ህጉን አልጠበቀም። እባክዎ ከ 4 እስከ 16 ቁምፊዎች (ፊደል እና ቁጥር) በመጠቀም እንደገና ይሞክሩ፦"
    )
    return

  await state.update_data(password=password)
  await message.answer("እባክዎ የይለፍ ቃልዎን ለማረጋገጥ አንዴ እንደገና ይጻፉት:")
  await state.set_state(RegistrationStates.confirm_password)


@dp.message(RegistrationStates.confirm_password)
async def process_confirm_password(message: types.Message, state: FSMContext):
  data = await state.get_data()
  if data["password"] != message.text:
    await message.answer(
      "የይለፍ ቃሎቹ አይመሳሰሉም። እባክዎ የመጀመሪያውን የይለፍ ቃል እንደገና ያስገቡ:"
    )
    await state.set_state(RegistrationStates.waiting_for_password)
    return

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

  await message.answer(
    "🎉 ምዝገባዎ በተሳካ ሁኔታ ተጠናቋል! አድሚኑ መረጃዎን አረጋግጦ ሲያጸድቀው ሙሉ አገልግሎቱን መጠቀም ይጀምራሉ። ከታች ያሉትን አማራጮች መጠቀም ይችላሉ፦",
    reply_markup=main_menu,
  )


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
    "ወደ ዋሌትዎ ገንዘብ ለመጨመር ከታች ያለውን ቁልፍ ይጫኑ። ክፍያው በቀጥታ በስልክ ቁጥርዎ ይፈጸማል።\n\n"
    f"⚠️ **ማስታወሻ:** ክፍያ ሲፈጽሙ ችግር ካጋጠመዎት አድሚኑን በዚህ ስልክ ቁጥር ማግኘት ይችላሉ፦ `{SUPPORT_PHONE_NUMBER}`",
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
    "return_url": "https://t.me/8543715567_bot",
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
            "እባክዎ ከታች ባለው ሊንክ በመሄድ ክፍያዎን ይፈጽሙ።",
            reply_markup=keyboard,
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
    "💳 ያገኙትን ኮይን ወደ እውነተኛ ገንዘብ (ብር) በመቀየር ወደ ባንክ አካውንትዎ ለማስተላለፍ የሚፈልጉትን የኮይን መጠን ይጻፉ፦\n\nምሳሌ፦ `50`",
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
    "📈 **የቦቱ አጠቃላይ ሁኔታ (Statistics)**\n\n- ንቁ ዋሌቶች፦ 0\n- አጠቃላይ የክፍያ ዝውውር፦ 0 ETB"
  )


@dp.message(Command("announce"))
async def admin_announce(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    return
  command_parts = message.text.split(maxsplit=1)
  if len(command_parts) < 2:
    await message.answer(
      "እባክዎ ከትዕዛዙ ጋር ማስተላለፍ የሚፈልጉትን መልእክት ይጻፉ።\nምሳሌ፦ `/announce ሰላም ቤተሰቦች...`",
      parse_mode="Markdown",
    )
    return
  announcement_text = command_parts[1]
  await message.answer(
    f"✅ ማስታወቂያው ለተጠቃሚዎች በስኬት ተልኳል፦\n\n{announcement_text}"
  )


# ቦቱን ማስጀመር
async def main():
  await dp.start_polling(bot)


if __name__ == "__main__":
  import asyncio

  asyncio.run(main())
