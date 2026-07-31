import os
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler

# ሎጊንግ ማስተካከል
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- የቴሌግራም እና የቻፓ ኪዎች ---
TELEGRAM_TOKEN = "8909326861:AAGcgDU1iwDewhFyDcm2LcEKtRdnthHQnN0"
CHAPA_SECRET_KEY = "CHASECK-SncZN81Mx80yQcPiXJwRXDF6MdgehtNV"
CHAPA_PUBLIC_KEY = "CHAPUBK-hLBEJPiKDlRpfBCqTczyE10snrrK3Zhj"

# የተጠቃሚዎ የአድሚን ቴሌግራም ID ተካቷል
ADMIN_ID = 5351353727

# የውሂብ ማከማቻ (ለቀላልነት በዲክሽናሪ መልክ)
booked_tickets = {} # {ticket_num: {"name": name, "phone": phone, "user_id": user_id}}
user_temp_data = {} # ተጠቃሚው በሚሞላበት ጊዜያዊ መረጃ

# የConversation ደረጃዎች
GET_NAME, GET_PHONE, GET_ADDRESS, CHOOSE_TICKET = range(4)

# --- 1. ቦቱን ሲጀምሩ ---
async def start(update: Update, context: ContextTypes.DEFAULT_ID):
    user_id = update.effective_user.id
    user_temp_data[user_id] = {}
    await update.message.reply_text("ሰላም! እንኳን ወደ ጋሻዬ ሀዋሳ የእቁብ መመዝገቢያ ቦት በደህና መጡ።\n\nእባክዎ **ሙሉ ስምዎን** ያስገቡ፡")
    return GET_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_ID):
    user_id = update.effective_user.id
    user_temp_data[user_id]['name'] = update.message.text
    await update.message.reply_text("አመሰግናለሁ! አሁን ደግሞ **ስልክ ቁጥርዎን** ያስገቡ (ለምሳሌ 09...):")
    return GET_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_ID):
    user_id = update.effective_user.id
    user_temp_data[user_id]['phone'] = update.message.text
    await update.message.reply_text("በመቀጠል **አድራሻዎን** ያስገቡ:")
    return GET_ADDRESS

async def receive_address(update: Update, context: ContextTypes.DEFAULT_ID):
    user_id = update.effective_user.id
    user_temp_data[user_id]['address'] = update.message.text
    
    # ቁጥር እንዲመርጥ ማድረግ (ለናሙና የመጀመሪያዎቹ 20 ቁጥሮች)
    keyboard = []
    row = []
    for i in range(1, 21):
        if i in booked_tickets:
            btn_text = f"❌ {i} (ተያዟል)"
            callback_data = "booked"
        else:
            btn_text = f"✅ {i}"
            callback_data = f"ticket_{i}"
        
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
        
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("መረጃዎ ተመዝግቧል! ከዚህ በታች የሚፈልጉትን **ክፍት የእቁብ ቁጥር** ይምረጡ፡", reply_markup=reply_markup)
    return CHOOSE_TICKET

# --- 2. ቁጥር ሲመርጡ እና የቻፓ ክፍያ ማመቻቸት ---
async def ticket_chosen(update: Update, context: ContextTypes.DEFAULT_ID):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data == "booked":
        await query.edit_message_text("ይህ ቁጥር უკვე ተይዟል። እባክዎ ሌላ ይምረጡ። (/start በመጠቀም እንደገና ይሞክሩ)")
        return ConversationHandler.END
        
    ticket_num = int(data.split("_")[1])
    user_id = update.effective_user.id
    if user_id not in user_temp_data:
        user_temp_data[user_id] = {'name': 'ተጠቃሚ', 'phone': '0900000000'}
    
    user_temp_data[user_id]['ticket'] = ticket_num
    
    # የቻፓ ክፍያ ማቀናበር (Chapa Initialize)
    amount = "1000" # የእቁብ መጠን (በብር)
    email = "customer@gashaye.com"
    full_name = user_temp_data[user_id].get('name', 'Gashaye Customer')
    name_parts = full_name.split()
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "Gashaye"
    tx_ref = f"gashaye-equb-{user_id}-{ticket_num}"
    
    headers = {
        "Authorization": f"Bearer {CHAPA_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "amount": amount,
        "currency": "ETB",
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "phone_number": user_temp_data[user_id].get('phone', '0900000000'),
        "tx_ref": tx_ref,
        "callback_url": "https://webhook.site/placeholder",
        "customization[title]": "ጋሻዬ ሀዋሳ እቁብ",
        "customization[description]": f"ለእቁብ ቁጥር {ticket_num} የሚሆን ክፍያ"
    }
    
    try:
        response = requests.post("https://api.chapa.co/v1/transaction/initialize", json=payload, headers=headers)
        res_data = response.json()
        
        if res_data.get('status') == 'success':
            checkout_url = res_data['data']['checkout_url']
            
            pay_keyboard = [
                [InlineKeyboardButton("💳 አሁን በቻፓ ክፈፍ", url=checkout_url)],
                [InlineKeyboardButton("🔄 ክፍያ ከፍያለሁ ግን ቁጥሬ አልተያዘም (Report)", callback_data=f"report_{ticket_num}")]
            ]
            await query.edit_message_text(
                f"ይምረጡት ቁጥር፦ **{ticket_num}**\nክፍያ ለመፈጸም ከታች ያለውን ሊንክ ይጠቀሙ፡",
                reply_markup=InlineKeyboardMarkup(pay_keyboard),
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text("የክፍያ ሊንክ ማመንጨት አልተቻለም። እባክዎ እንደገና ይሞክሩ። /start")
    except Exception as e:
        logging.error(f"Chapa Error: {e}")
        await query.edit_message_text("የኔትወርክ ችግር አጋጥሟል። እባክዎ ቆይተው እንደገና ይሞክሩ።")

    return ConversationHandler.END

# --- 3. ክፍያ ከፍሎ ቁጥሩ ካልተያዘ ለአድሚን ሪፖርት ማድረግ ---
async def report_missing_ticket(update: Update, context: ContextTypes.DEFAULT_ID):
    query = update.callback_query
    await query.answer()
    
    ticket_num = int(query.data.split("_")[1])
    user_id = update.effective_user.id
    u_data = user_temp_data.get(user_id, {})
    
    name = u_data.get('name', 'ስም አልታወቀም')
    phone = u_data.get('phone', 'ስልክ አልታወቀም')
    
    admin_keyboard = [
        [
            InlineKeyboardButton("✅ ጸድቅ (Approve)", callback_data=f"approve_{ticket_num}_{user_id}"),
            InlineKeyboardButton("❌ ውድቅ አድርግ", callback_data=f"reject_{ticket_num}")
        ]
    ]
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚨 **የክፍያ ቅሬታ ጥያቄ!**\n\nተጠቃሚው ክፍያ ከፍያለሁ ይላል ግን ቁጥሩ አልያዘለትም።\n\n* ስም፦ {name}\n* ስልክ፦ {phone}\n* የጠየቀው ቁጥር፦ {ticket_num}\n* ዩዘር ID፦ {user_id}",
            reply_markup=InlineKeyboardMarkup(admin_keyboard),
            parse_mode="Markdown"
        )
        await query.edit_message_text("ቅሬታዎ ለአድሚን ተልኳል። አድሚኑ ሲያረጋግጠው ቁጥርዎ ይመዝገብልዎታል። እናመሰግናለን!")
    except Exception as e:
        await query.edit_message_text("ቅሬታውን መላክ አልተቻለም። እባክዎ አድሚኑን በቀጥታ ያነጋግሩ።")

# --- 4. አድሚኑ አፕሩቭ ሲያደርግ ---
async def admin_action(update: Update, context: ContextTypes.DEFAULT_ID):
    query = update.callback_query
    await query.answer()
    
    data_parts = query.data.split("_")
    action = data_parts[0]
    ticket_num = int(data_parts[1])
    
    if action == "approve":
        user_id = int(data_parts[2])
        u_data = user_temp_data.get(user_id, {})
        
        booked_tickets[ticket_num] = {
            "name": u_data.get('name', 'Unknown'),
            "phone": u_data.get('phone', 'Unknown'),
            "user_id": user_id
        }
        
        await query.edit_message_text(f"✅ ቁጥር {ticket_num} ለተጠቃሚው በተሳካ ሁኔታ ጸድቋል!")
        
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 እንኳን ደስ አለዎት! ክፍያዎ በአድሚን ጸድቋል፤ የእቁብ ቁጥርዎ **{ticket_num}** ሆኖ ተመዝግቧል።",
                parse_mode="Markdown"
            )
        except:
            pass
            
    elif action == "reject":
        await query.edit_message_text(f"❌ ቁጥር {ticket_num} ጥያቄ ውድቅ ተደርጓል።")

# --- ዋና ማስኬጃ (Main Function) ---
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
            GET_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_address)],
            CHOOSE_TICKET: [CallbackQueryHandler(ticket_chosen, pattern="^ticket_|^booked$")]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(report_missing_ticket, pattern="^report_"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve|reject)_"))
    
    print("ቦቱ በመጀመር ላይ ነው...")
    app.run_polling()

if __name__ == '__main__':
    main()
