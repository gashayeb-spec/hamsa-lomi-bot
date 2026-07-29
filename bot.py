import os
import logging
from fastapi import FastAPI, HTTPException, Security, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# --- 1. CONFIGURATION & LOGGING ---
logging.basicConfig(level=logging.INFO)
TOKEN = "8909326861:AAGcgD1iwDewhFyDcm2LcEKRdntHHQnN0"
API_SECRET_KEY = "50LomiSecureApiKey2026_Secret"
CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY", "CHASECK_TEST-xxxxxxxxxxxxxxxxxxxxx")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_SECRET_KEY:
        return api_key_header
    raise HTTPException(status_code=403, detail="Invalid API Key")

app = FastAPI(title="50 ሎሚ Secure API & Mini App", version="2.0")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 2. DATA MODELS ---
class OrderRequest(BaseModel):
    user_id: int
    username: str
    plan: str
    amount: float
    payment_method: str  # Telebirr, CBE Birr, Chapa, Wallet
    phone_number: str = "0916039015"

# --- 3. TELEGRAM BOT HANDLERS ---
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    # Replace with your deployed web app URL (e.g., Render URL)
    web_app_url = "https://your-app-name.onrender.com/webapp"
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 50 ሎሚ Mini App ክፈት", web_app=WebAppInfo(url=web_app_url))],
            [InlineKeyboardButton(text="📞 እገዛ (Support)", callback_data="support")]
        ]
    )
    
    welcome_text = (
        "✨ **እንኳን ወደ 50 ሎሚ ቦት በደህና መጡ!**\n\n"
        "የ Telegram Premium እና ሌሎች ዲጂታል አገልግሎቶችን በቀላሉ፣ በፍጥነት እና በአስተማማኝ ሁኔታ ማግኘት ይችላሉ።\n"
        "ከታች ያለውን ღንጥ በመጫን ሚኒ አፑን ይክፈቱ!"
    )
    await message.answer(welcome_text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "support")
async def process_support(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    support_text = (
        "📞 **የእገዛ ማዕከል (50 ሎሚ)**\n\n"
        "🔹 ቴሌግራም: @50LomiSupport\n"
        "🔹 ስልክ ቁጥር: 0916039015\n"
        "🔹 ሰዓት: 24/7 አገልግሎት እንሰጣለን!"
    )
    await bot.send_message(callback_query.from_user.id, support_text, parse_mode="Markdown")

# --- 4. WEB APP FRONTEND (HTML/CSS/JS) ---
@app.get("/webapp", response_class=HTMLResponse)
async def webapp_home():
    html_content = """
    <!DOCTYPE html>
    <html lang="am">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>50 ሎሚ - Mini App</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            :root {
                --bg-color: #f8fafc;
                --card-bg: #ffffff;
                --text-color: #1e293b;
                --primary-color: #6366f1;
                --primary-hover: #4f46e5;
                --accent-color: #10b981;
                --border-color: #e2e8f0;
            }
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: var(--bg-color);
                color: var(--text-color);
                margin: 0;
                padding: 16px;
            }
            .header {
                text-align: center;
                margin-bottom: 20px;
            }
            .header h1 {
                margin: 0;
                font-size: 24px;
                color: var(--primary-color);
            }
            .header p {
                margin: 5px 0 0;
                font-size: 14px;
                color: #64748b;
            }
            .nav-tabs {
                display: flex;
                justify-content: space-around;
                background: var(--card-bg);
                padding: 10px;
                border-radius: 12px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
                margin-bottom: 20px;
            }
            .nav-tab {
                background: none;
                border: none;
                font-size: 13px;
                font-weight: 600;
                color: #64748b;
                cursor: pointer;
                padding: 8px 12px;
                border-radius: 8px;
                transition: all 0.3s;
            }
            .nav-tab.active {
                background: var(--primary-color);
                color: white;
            }
            .section {
                display: none;
                background: var(--card-bg);
                padding: 20px;
                border-radius: 16px;
                box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
                margin-bottom: 20px;
            }
            .section.active {
                display: block;
            }
            h2 {
                font-size: 18px;
                margin-top: 0;
                color: var(--text-color);
                border-bottom: 2px solid var(--border-color);
                padding-bottom: 8px;
            }
            .card-grid {
                display: grid;
                grid-template-columns: 1fr;
                gap: 12px;
                margin-top: 15px;
            }
            .service-card {
                background: #f1f5f9;
                border: 1px solid var(--border-color);
                padding: 15px;
                border-radius: 12px;
                cursor: pointer;
                transition: transform 0.2s;
            }
            .service-card:hover {
                transform: translateY(-2px);
                border-color: var(--primary-color);
            }
            .service-card h3 {
                margin: 0 0 5px;
                font-size: 16px;
                color: var(--primary-color);
            }
            .service-card p {
                margin: 0;
                font-size: 13px;
                color: #64748b;
            }
            .btn {
                background: var(--primary-color);
                color: white;
                border: none;
                width: 100%;
                padding: 12px;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                margin-top: 15px;
            }
            .btn:hover {
                background: var(--primary-hover);
            }
            .wallet-balance {
                font-size: 28px;
                font-weight: bold;
                color: var(--accent-color);
                text-align: center;
                margin: 15px 0;
            }
            .order-item {
                background: #f8fafc;
                border-left: 4px solid var(--primary-color);
                padding: 12px;
                margin-bottom: 10px;
                border-radius: 8px;
                font-size: 13px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🍋 50 ሎሚ ዳሽቦርድ</h1>
            <p>ፈጣን እና አስተማማኝ የዲጂታል አገልግሎቶች ማዕከል</p>
        </div>

        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchTab('services')">🛒 አገልግሎቶች</button>
            <button class="nav-tab" onclick="switchTab('wallet')">💰 ዋሌት</button>
            <button class="nav-tab" onclick="switchTab('orders')">📋 ትዕዛዞች</button>
            <button class="nav-tab" onclick="switchTab('guidelines')">📖 መግለጫ</button>
        </div>

        <!-- 1. SERVICES TAB -->
        <div id="services" class="section active">
            <h2>የሚገኙ አገልግሎቶች</h2>
            <div class="card-grid">
                <div class="service-card" onclick="selectService('Telegram Premium (3 Months)', 450)">
                    <h3>⭐ Telegram Premium - 3 Months</h3>
                    <p>ፈጣን ፕሪሚየም ማግበር በደህና ሁኔታ - 450 ETB</p>
                </div>
                <div class="service-card" onclick="selectService('Telegram Premium (6 Months)', 850)">
                    <h3>⭐ Telegram Premium - 6 Months</h3>
                    <p>ለግማሽ ዓመት የሚሆን ፕሪሚየም ፓኬጅ - 850 ETB</p>
                </div>
                <div class="service-card" onclick="selectService('Telegram Premium (1 Year)', 1500)">
                    <h3>⭐ Telegram Premium - 1 Year</h3>
                    <p>ለአንድ ሙሉ ዓመት የሚሆን ምርጥ ቅናሽ - 1500 ETB</p>
                </div>
            </div>
            <div id="selected-service-box" style="margin-top: 20px; display: none;">
                <h3>የተመረጠው አገልግሎት: <span id="lbl-service" style="color:var(--primary-color)"></span></h3>
                <p>ዋጋ: <span id="lbl-price"></span> ETB</p>
                <label for="pay-method" style="font-size:13px; font-weight:600;">የክፍያ አማራጭ ይምረጡ:</label>
                <select id="pay-method" style="width:100%; padding:10px; margin-top:5px; border-radius:8px; border:1px solid var(--border-color);">
                    <option value="Telebirr">ቴሌብር (Telebirr)</option>
                    <option value="CBE Birr">ሲቢኢ ብር (CBE Birr)</option>
                    <option value="Chapa">ቻፓ (Chapa Gateway)</option>
                    <option value="Wallet">ከዋሌት ባላንስ (Wallet Balance)</option>
                </select>
                <button class="btn" onclick="checkout()">ክፍያ ይፈጽሙ (Pay Now)</button>
            </div>
        </div>

        <!-- 2. WALLET TAB -->
        <div id="wallet" class="section">
            <h2>የኪስ ቦርሳ (Wallet)</h2>
            <p style="text-align:center; color:#64748b; margin-bottom:5px;">ቀሪ ሂሳብዎ (Current Balance)</p>
            <div class="wallet-balance">1,250.00 ETB</div>
            <button class="btn" onclick="alert('የሂሳብ መሙያ (Deposit) ገጽ በቅርብ ቀን ይከፈታል!')">➕ሂሳብ ይሙሉ (Deposit)</button>
        </div>

        <!-- 3. ORDERS TAB -->
        <div id="orders" class="section">
            <h2>የእርስዎ ትዕዛዞች ታሪክ (Orders History)</h2>
            <div class="order-item">
                <strong>ID: #50LM-9482</strong><br>
                ዕቅድ: Telegram Premium (3 Months)<br>
                መጠን: 450 ETB | ሁኔታ: <span style="color:var(--accent-color)">✅ ተጠናቋል (Success)</span>
            </div>
            <div class="order-item">
                <strong>ID: #50LM-9103</strong><br>
                ዕቅድ: Telegram Premium (1 Year)<br>
                መጠን: 1500 ETB | ሁኔታ: <span style="color:var(--accent-color)">✅ ተጠናቋል (Success)</span>
            </div>
        </div>

        <!-- 4. GUIDELINES TAB -->
        <div id="guidelines" class="section">
            <h2>መግለጫ እና መመሪያ (Guidelines)</h2>
            <p style="line-height:1.6; font-size:14px;">
                <strong>50 ሎሚ</strong> ሙሉ በሙሉ አውቶማቲክ በሆነ መንገድ ዲጂታል አገልግሎቶችን የምታገኙበት ዘመናዊ ሲስተም ነው።<br><br>
                1. <b>አገልግሎት መምረጥ:</b> ከሰንጠረዡ የሚፈልጉትን የቆይታ ጊዜ ይምረጡ።<br>
                2. <b>ክፍያ:</b> በቴሌብር፣ በሲቢኢ ብር ወይም በቻፓ ጌትዌይ በቀጥታ ይክፈሉ።<br>
                3. <b>ማረጋገጫ:</b> ክፍያው ሲጠናቀቅ ቦቱ ራሱ በአውቶማቲክ ሁኔታ ትዕዛዝዎን ያስተናግዳል (ስክሪንሾት መላክ አያስፈልግም)።<br><br>
                ለማንኛውም ጥያቄ በስልክ ቁጥር <b>0916039015</b> ወይም በቴሌግራም <b>@50LomiSupport</b> ያግኙን።
            </p>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            let currentService = "";
            let currentPrice = 0;

            function switchTab(tabId) {
                document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
                document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
                
                document.getElementById(tabId).classList.add('active');
                event.currentTarget.classList.add('active');
            }

            function selectService(serviceName, price) {
                currentService = serviceName;
                currentPrice = price;
                document.getElementById('lbl-service').innerText = serviceName;
                document.getElementById('lbl-price').innerText = price;
                document.getElementById('selected-service-box').style.display = 'block';
            }

            async function checkout() {
                let method = document.getElementById('pay-method').value;
                let userId = tg.initDataUnsafe?.user?.id || 123456789;
                let username = tg.initDataUnsafe?.user?.username || "george_user";

                let data = {
                    user_id: userId,
                    username: username,
                    plan: currentService,
                    amount: currentPrice,
                    payment_method: method,
                    phone_number: "0916039015"
                };

                let response = await fetch('/api/v1/create-order', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-API-Key': '50LomiSecureApiKey2026_Secret'
                    },
                    body: JSON.stringify(data)
                });

                let result = await response.json();
                if (response.ok) {
                    alert('✅ ትዕዛዝዎ በተሳካ ሁኔታ ተመዝግቧል! ክፍያውን ያጠናቅቁ።');
                    tg.close();
                } else {
                    alert('❌ ስህተት ተፈጥሯል: ' + (result.detail || 'እባክዎ እንደገና ይሞክሩ'));
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- 5. SECURE API ENDPOINTS ---
@app.post("/api/v1/create-order")
async def create_order(order: OrderRequest, api_key: str = Depends(get_api_key)):
    logging.info(f"50 Lomi New Order Processed: User={order.username}, Plan={order.plan}, Method={order.payment_method}, Phone={order.phone_number}")
    
    try:
        await bot.send_message(
            chat_id=order.user_id,
            text=(
                f"✅ **የ 50 ሎሚ ትዕዛዝዎ ተቀባይነት አግኝቷል!**\n\n"
                f"📋 ዕቅድ: {order.plan}\n"
                f"💰 መጠን: {order.amount} ETB\n"
                f"💳 የክፍያ አማራጭ: {order.payment_method}\n"
                f"📱 ስልክ ቁጥር: {order.phone_number}\n\n"
                f"ክፍያው እንደተጠናቀቀ አውቶማቲክ አገልግሎቱ ይለቀቃል!"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Telegram notification failed: {e}")

    return {
        "status": "success",
        "message": "50 Lomi order successfully created and notification sent.",
        "order_details": {
            "user": order.username,
            "plan": order.plan,
            "amount": order.amount,
            "method": order.payment_method
        }
    }

@app.get("/api/v1/status")
async def api_status(api_key: str = Depends(get_api_key)):
    return {"status": "active", "brand": "50 ሎሚ", "security": "enabled", "phone": "0916039015"}
