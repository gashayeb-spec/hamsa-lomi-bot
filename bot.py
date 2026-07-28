import logging
import requests
import threading
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TOKEN = "8909326861:AAGYvN77tgE2-rQK_Gq8F-s35AfC59GaBgA"
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDlRpfBCqTczyE1OsnrrK3Zhj"
CHAPA_SECRET_KEY = "CHASECK_TEST-xxxxxxxxxxxxxxxx"
CHAPA_URL = "https://api.chapa.co/v1/transaction/initialize"

# Business Payment Details
CBE_NAME = "ጋሻዬ በጅጉ (Gashaye Bejigu)"
CBE_ACCOUNT = "1000070780201"
TELEBIRR_PHONE = "0916039015"

# Database simulation
users_db = {}

# --- FLASK WEB SERVER FOR RENDER KEEP-ALIVE ---
app = Flask(__name__)

@app.route('/')
def home():
    return "HamsaLomi Bot is active and running!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args
    ref_id = args[0] if args else "None"
    
    if user.id not in users_db:
        referred_by_id = int(ref_id) if ref_id != "None" and ref_id.isdigit() and int(ref_id) != user.id else None
        
        users_db[user.id] = {
            "name": user.first_name,
            "referred_by": referred_by_id,
            "downlines": [],
            "status": "unpaid",
            "balance": 0.0
        }
        
        if referred_by_id and referred_by_id in users_db:
            if len(users_db[referred_by_id]["downlines"]) < 10:
                users_db[referred_by_id]["downlines"].append(user.id)

    keyboard = [
        [InlineKeyboardButton("💳 በ Chapa አውቶማቲክ ክፍያ ፈጽም", callback_data="chapa_pay")],
        [InlineKeyboardButton("🏦 የንግድ ባንክ (CBE) ቁጥር ለማየት", callback_data="view_cbe")],
        [InlineKeyboardButton("📱 ቴሌብር (Telebirr) ቁጥር ለማየት", callback_data="view_telebirr")],
        [InlineKeyboardButton("👤 የኔ አካውንት እና ሪፈራል", callback_data="profile")],
        [InlineKeyboardButton("🔗 ማስተዋወቂያ ሊንክ", callback_data="mylink")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"ሰላም **{user.first_name}**! ወደ ሐምሳሎሚ አውቶማቲክ ሲስተም እንኳን በደህና መጡ።\n\n"
        f"እባክዎ ከታች ከሚገኙት የክፍያ አማራጮች አንዱን በመምረጥ ክፍያዎን ይፈጽሙ!"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# --- BUTTON HANDLERS ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    
    if data == "view_cbe":
        cbe_text = (
            f"🏦 የንግድ ባንክ (CBE) አካውንት መረጃ:\n\n"
            f"- ስም: {CBE_NAME}\n"
            f"- አካውንት ቁጥር: {CBE_ACCOUNT}\n\n"
            f"ይህንን ቁጥር በመንካት (ኮፒ በማድረግ) በባንክ መተግበሪያዎ ክፍያውን ፈጽመው ስክሪንሾቱን ይላኩ!"
        )
        back_keyboard = [[InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ ተመለስ", callback_data="main_menu")]]
        await query.message.edit_text(cbe_text, reply_markup=InlineKeyboardMarkup(back_keyboard))
        
    elif data == "view_telebirr":
        tele_text = (
            f"📱 ቴሌብር (Telebirr) መረጃ:\n\n"
            f"- ስም: {CBE_NAME}\n"
            f"- ስልክ ቁጥር: {TELEBIRR_PHONE}\n\n"
            f"ይህንን ቁጥር በመንካት በቴሌብር መተግበሪያዎ በኩል ክፍያውን መፈጸም ይችላሉ!"
        )
        back_keyboard = [[InlineKeyboardButton("🔙 ወደ ዋናው ምናሌ ተመለስ", callback_data="main_menu")]]
        await query.message.edit_text(tele_text, reply_markup=InlineKeyboardMarkup(back_keyboard))

    elif data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("💳 በ Chapa አውቶማቲክ ክፍያ ፈጽም", callback_data="chapa_pay")],
            [InlineKeyboardButton("🏦 የንግድ ባንክ (CBE) ቁጥር ለማየት", callback_data="view_cbe")],
            [InlineKeyboardButton("📱 ቴሌብር (Telebirr) ቁጥር ለማየት", callback_data="view_telebirr")],
            [InlineKeyboardButton("👤 የኔ አካውንት እና ሪፈራል", callback_data="profile")],
            [InlineKeyboardButton("🔗 ማስተዋወቂያ ሊንክ", callback_data="mylink")]
        ]
        await query.message.edit_text("ሰላም! እባክዎ ከታች ያሉትን አማራጮች ይጠቀሙ።", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data == "chapa_pay":
        tx_ref = f"hamsa-lomi-{user.id}-{int(requests.utils.datetime.datetime.utcnow().timestamp())}"
        
        payload = {
            "amount": "100",
            "currency": "ETB",
            "email": f"user_{user.id}@hamsalomi.com",
            "first_name": user.first_name,
            "last_name": "Customer",
            "tx_ref": tx_ref,
            "callback_url": "https://api.chapa.co/v1/webhook",
            "return_url": "https://t.me/" + context.bot.username
        }
        headers = {
            "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(CHAPA_URL, json=payload, headers=headers)
            res_data = response.json()
            
            if res_data.get("status") == "success":
                checkout_url = res_data["data"]["checkout_url"]
                pay_keyboard = [
                    [InlineKeyboardButton("🔗 ወደ ክፍያ ገጽ ለመሄድ እዚህ ይጫኑ", url=checkout_url)],
                    [InlineKeyboardButton("🔙 ተመለስ", callback_data="main_menu")]
                ]
                await query.message.edit_text(
                    "💳 የክፍያ ሊንክዎ ተዘጋጅቷል!\n\nከታች ባለው ሊንክ በመግባት በባንክ ወይም በቴሌብር አውቶማቲክ ክፍያዎን ማጠናቀቅ ይችላሉ።",
                    reply_markup=InlineKeyboardMarkup(pay_keyboard)
                )
            else:
                await query.message.edit_text("❌ የክፍያ ሊንክ ማመንጨት አልተቻለም። እባክዎ በባንክ ቁጥራችን በቀጥታ ይክፈሉ።")
        except Exception as e:
            logger.error(f"Chapa Error: {e}")
            await query.message.edit_text("❌ ከክፍያ ሲስተም ጋር ግንኙነት መፍጠር አልተቻለም።")

    elif data == "profile":
        u_data = users_db.get(user.id, {"status": "unpaid", "balance": 0.0})
        profile_text = (
            f"👤 የመገለጫ መረጃዎ:\n\n"
            f"- ስም: {user.first_name}\n"
            f"- ሁኔታ: {u_data['status']}\n"
            f"- ቀሪ ሂሳብ: {u_data['balance']} ብር"
        )
        back_keyboard = [[InlineKeyboardButton("🔙 ተመለስ", callback_data="main_menu")]]
        await query.message.edit_text(profile_text, reply_markup=InlineKeyboardMarkup(back_keyboard))
        
    elif data == "mylink":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user.id}"
        back_keyboard = [[InlineKeyboardButton("🔙 ተመለስ", callback_data="main_menu")]]
        await query.message.edit_text(f"🔗 የእርስዎ ማስተዋወቂያ ሊንክ:\n\n{ref_link}", reply_markup=InlineKeyboardMarkup(back_keyboard))

async def run_bot():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    logger.info("CBE & Telebirr Integrated HamsaLomi Bot is running...")
    
    # Proper async lifecycle management for Render
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    # Keep running
    stop_event = asyncio.Event()
    await stop_event.wait()

def main() -> None:
    # Start Flask server in a separate thread
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # Run Telegram bot with proper event loop
    asyncio.run(run_bot())

if __name__ == "__main__":
    main()
