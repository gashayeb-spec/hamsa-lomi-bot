import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
TOKEN = "8909326861:AAGYvN77tgE2-rQK_Gq8F-s35AfC59GaBgA"

# Database simulation
users_db = {}  # {user_id: {"name": str, "referred_by": int, "downlines": [], "status": str, "balance": float}}

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
            "balance": 0.0,
            "cycle_count": 0
        }
        
        if referred_by_id and referred_by_id in users_db:
            if len(users_db[referred_by_id]["downlines"]) < 10:
                users_db[referred_by_id]["downlines"].append(user.id)

    keyboard = [
        [InlineKeyboardButton("💳 ክፍያ ፈጽም (Chapa / ማረጋገጫ)", callback_data="pay_action")],
        [InlineKeyboardButton("👤 የኔ አካውንት እና ኮሚሽን", callback_data="profile")],
        [InlineKeyboardButton("🔗 ማስተዋወቂያ ሊንክ", callback_data="mylink")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"ሰላም **{user.first_name}**! ወደ ሐምሳሎሚ ማትሪክስ ቦት እንኳን በደህና መጡ።\n\n"
        f"ይህ ሲስተም የሪፈራል ኔትወርክዎን፣ አውቶማቲክ የኮሚሽን ቅንጭብ እና የአንድ-ክሊክ ማረጋገጫ ያስተዳድራል።\n"
        f"እባክዎ ከታች ያሉትን አማራጮች ይጠቀሙ!"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

# --- BUTTON HANDLERS ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user
    
    if data == "pay_action":
        users_db[user.id]["status"] = "pending_approval"
        msg = (
            "💳 **የክፍያ ማረጋገጫ (Payment Submission):**\n\n"
            "እባክዎ የክፍያ መረጃዎን (የግብይት ቁጥር ወይም የባንክ ስክሪንሾት) በቀጥታ በዚህ ቦት ቻት ውስጥ ይጻፉ/ይላቁ።\n"
            "ሲስተሙ ለጋባዥዎ እና ለአስተዳዳሪው በራስ-ሰር ያስተላልፋል!"
        )
        await query.message.edit_text(msg, parse_mode="Markdown")
        
    elif data == "profile":
        u_data = users_db.get(user.id, {"status": "unpaid", "downlines": [], "balance": 0.0})
        downline_count = len(u_data["downlines"])
        
        profile_text = (
            f"👤 **የመገለጫ መረጃዎ:**\n\n"
            f"• ስም: {user.first_name}\n"
            f"• ID: `{user.id}`\n"
            f"• ሁኔታ: `{u_data['status']}`\n"
            f"• የተጠራቀመ ኮሚሽን/ቀሪ ሂሳብ: **{u_data['balance']} ብር**\n"
            f"• ስርዎ ያሉ ሰዎች: **{downline_count} / 10**"
        )
        await query.message.edit_text(profile_text, parse_mode="Markdown")
        
    elif data == "mylink":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user.id}"
        await query.message.edit_text(
            f"🔗 **የእርስዎ ማስተዋወቂያ ሊንክ:**\n\n`{ref_link}`\n\nይህንን ሊንክ ለሌሎች ያጋሩ!"
        )
        
    elif data.startswith("fwd_admin_"):
        target_user_id = int(data.split("_")[2])
        await query.message.edit_text(f"✅ የዚህ ተጠቃሚ (ID: {target_user_id}) የክፍያ ማረጋገጫ ለአስተዳዳሪው (Admin) ተልኳል!")
        
    elif data.startswith("approve_"):
        target_user_id = int(data.split("_")[1])
        if target_user_id in users_db:
            users_db[target_user_id]["status"] = "active"
            
            parent_id = users_db[target_user_id].get("referred_by")
            if parent_id and parent_id in users_db:
                if len(users_db[parent_id]["downlines"]) >= 10:
                    users_db[parent_id]["cycle_count"] = users_db[parent_id].get("cycle_count", 0) + 1

            await query.message.edit_text(f"✅ ተጠቃሚ (ID: {target_user_id}) ክፍያው ጸድቋል!")
            try:
                await context.bot.send_message(chat_id=target_user_id, text="🎉 እንኳን ደስ አለዎት! ክፍያዎ ጸድቆ ሲስተሙ ውስጥ ገብተዋል!")
            except Exception:
                pass

# --- MESSAGE & RECEIPT HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = update.message.text
    
    if user.id in users_db and users_db[user.id]["status"] == "pending_approval":
        referred_by = users_db[user.id].get("referred_by")
        
        if referred_by and referred_by in users_db:
            referrer_keyboard = [
                [InlineKeyboardButton("📤 ኮሚሽን ቆርጠህ ለአድሚን ላክ (One-Click)", callback_data=f"fwd_admin_{user.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(referrer_keyboard)
            
            notif_text = (
                f"🔔 **ከስርዎ ካለ ተጠቃሚ አዲስ የክፍያ ማረጋገጫ መጣ!**\n\n"
                f"• ስም: {user.first_name}\n"
                f"• ID: `{user.id}`\n"
                f"• መረጃ: {text or 'ፋይል/ስክሪንሾት ተልኳል'}\n\n"
                f"እባክዎ የራስዎን ኮሚሽን ቆርጠው ቀሪውን ለአድሚን ለማስተላለፍ ከታች ያለውን ይጫኑ።"
            )
            try:
                await context.bot.send_message(chat_id=referred_by, text=notif_text, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception:
                pass
                
        await update.message.reply_text("⏳ የክፍያ ማረጋገጫዎ ለጋባዥዎ እና ለአድሚን ተልኳል፤ ሲረጋገጥ ይነገራል።")

def main() ->none:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Advanced HamsaLomi Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
