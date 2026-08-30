from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import html
import random
import string
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="وثيق | Watheeq - Escrow & Marketplace Platform")

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except Exception as e:
            print("DB Connection Error:", e)
            return None
    return None

def init_db():
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS deals (
                    id VARCHAR(50) PRIMARY KEY,
                    title VARCHAR(255),
                    category VARCHAR(100),
                    price NUMERIC,
                    fee_percent NUMERIC,
                    fee_amount NUMERIC,
                    total_paid NUMERIC,
                    seller_name VARCHAR(100),
                    buyer_name VARCHAR(100),
                    status VARCHAR(100),
                    status_note TEXT,
                    messages JSONB DEFAULT '[]'::jsonb
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255),
                    price NUMERIC,
                    category VARCHAR(100),
                    country VARCHAR(100),
                    seller VARCHAR(100),
                    media_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cur.execute("""
                INSERT INTO deals (id, title, category, price, fee_percent, fee_amount, total_paid, seller_name, buyer_name, status, status_note, messages)
                VALUES (
                    'WTQ-701',
                    'عربون حجز وفحص مركبة',
                    'مركبات ومعدات وعرابين (1.5%)',
                    2500.0,
                    1.5,
                    37.5,
                    2537.5,
                    'سعد الشمري (موثق نفاذ ✅)',
                    'أحمد المالكي (موثق نفاذ ✅)',
                    'المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳',
                    'تم سداد 2,537.5 ريال وتجميدها بأمان عبر Apple Pay في خزينة وثيق شاملة عمولة الوساطة.',
                    '[
                        {"sender": "النظام (أمان وثيق)", "text": "تم استلام 2,537.5 ريال وتجميدها بنجاح عبر Apple Pay شاملة عمولة الضمان 🔒", "time": "10:00 AM"},
                        {"sender": "المشتري (أحمد)", "text": "تم تجميد العربون والعمولة بالمنصة، بانتظار إتمام الفحص.", "time": "10:02 AM"}
                    ]'::jsonb
                )
                ON CONFLICT (id) DO NOTHING;
            """)
            conn.commit()
        conn.close()

@app.on_event("startup")
def on_startup():
    init_db()

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

memory_deals = {
    "WTQ-701": {
        "id": "WTQ-701",
        "title": "عربون حجز وفحص مركبة",
        "category": "مركبات ومعدات وعرابين (1.5%)",
        "price": 2500.0,
        "fee_percent": 1.5,
        "fee_amount": 37.5,
        "total_paid": 2537.5,
        "seller_name": "سعد الشمري (موثق نفاذ ✅)",
        "buyer_name": "أحمد المالكي (موثق نفاذ ✅)",
        "status": "المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳",
        "status_note": "تم سداد 2,537.5 ريال وتجميدها بأمان عبر Apple Pay في خزينة وثيق شاملة عمولة الوساطة.",
        "messages": [
            {"sender": "النظام (أمان وثيق)", "text": "تم استلام 2,537.5 ريال وتجميدها بنجاح عبر Apple Pay شاملة عمولة الضمان 🔒", "time": "10:00 AM"},
            {"sender": "المشتري (أحمد)", "text": "تم تجميد العربون والعمولة بالمنصة، بانتظار إتمام الفحص.", "time": "10:02 AM"}
        ]
    }
}

memory_listings = [
    {
        "id": 1,
        "title": "نيسان باترول بلاتينيوم 2023 - فل كامل",
        "price": 245000,
        "category": "مركبات وعرابين",
        "country": "🇸🇦 السعودية - الرياض",
        "seller": "أبو فهد (موثق نفاذ ✅)",
        "media_url": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=600&auto=format&fit=crop&q=80"
    },
    {
        "id": 2,
        "title": "حساب كود MW3 & BO6 نادر (أوريون ولفلات ماكس)",
        "price": 1400,
        "category": "أصول رقمية وحسابات",
        "country": "🇸🇦 السعودية - المدينة",
        "seller": "مرعب_COD (موثق ✅)",
        "media_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?w=600&auto=format&fit=crop&q=80"
    },
    {
        "id": 3,
        "title": "ساعة رولكس صبمارينر أصلية مع الصندوق والضمان",
        "price": 42000,
        "category": "سلع عامة وإلكترونيات",
        "country": "🇦🇪 الإمارات - دبي",
        "seller": "الماس الخليج (موثق ✅)",
        "media_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=600&auto=format&fit=crop&q=80"
    }
]

def fetch_deal(deal_id: str):
    conn = get_db()
    if conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM deals WHERE id = %s;", (deal_id,))
            row = cur.fetchone()
        conn.close()
        if row:
            row['price'] = float(row['price'])
            row['fee_percent'] = float(row['fee_percent'])
            row['fee_amount'] = float(row['fee_amount'])
            row['total_paid'] = float(row['total_paid'])
            if isinstance(row['messages'], str):
                row['messages'] = json.loads(row['messages'])
            return dict(row)
    return memory_deals.get(deal_id)

def save_deal(deal: dict):
    conn = get_db()
    if conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO deals (id, title, category, price, fee_percent, fee_amount, total_paid, seller_name, buyer_name, status, status_note, messages)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    status_note = EXCLUDED.status_note,
                    messages = EXCLUDED.messages;
            """, (
                deal['id'], deal['title'], deal['category'], deal['price'],
                deal['fee_percent'], deal['fee_amount'], deal['total_paid'],
                deal['seller_name'], deal['buyer_name'], deal['status'],
                deal['status_note'], json.dumps(deal['messages'], ensure_ascii=False)
            ))
            conn.commit()
        conn.close()
    memory_deals[deal['id']] = deal

class CreateDealRequest(BaseModel):
    title: str = Field(..., max_length=150)
    category: str
    price: float = Field(..., gt=0)
    seller_name: str = Field(..., max_length=50)
    buyer_name: str = Field(default="", max_length=50)

class ListingRequest(BaseModel):
    title: str
    price: float
    category: str
    country: str
    seller: str
    media_url: str

class MessageRequest(BaseModel):
    sender: str
    text: str

class PaymentConfirmRequest(BaseModel):
    payment_method: str

@app.post("/api/deals/create")
def create_deal(req: CreateDealRequest):
    deal_id = "WTQ-" + ''.join(random.choices(string.digits, k=4))
    
    fee_percent = 2.0
    if "1.5" in req.category:
        fee_percent = 1.5
    elif "2.5" in req.category:
        fee_percent = 2.5
        
    fee_amount = round((req.price * fee_percent) / 100, 2)
    total_paid = round(req.price + fee_amount, 2)
    
    clean_title = html.escape(req.title)
    clean_seller = html.escape(req.seller_name)
    clean_buyer = html.escape(req.buyer_name) if req.buyer_name else "بانتظار الطرف الثاني"
    clean_category = html.escape(req.category)

    deal = {
        "id": deal_id,
        "title": clean_title,
        "category": clean_category,
        "price": req.price,
        "fee_percent": fee_percent,
        "fee_amount": fee_amount,
        "total_paid": total_paid,
        "seller_name": clean_seller + " (موثق)",
        "buyer_name": clean_buyer,
        "status": "بانتظار سداد المشتري للضمان والعمولة عبر (Apple Pay / مدى) ⏳",
        "status_note": f"الصفقة بانتظار سداد إجمالي المبلغ ({total_paid:,} ريال) شاملاً قيمة السلعة وعمولة الوساطة عبر بوابة الدفع الآمنة.",
        "messages": [
            {"sender": "النظام (أمان وثيق)", "text": f"تم فتح غرفة الضمان المالي ({clean_title}). المطلوب سداده شاملاً عمولة المنصة: {total_paid:,} ريال في الخزينة.", "time": "الآن"}
        ]
    }
    save_deal(deal)
    return {"status": "success", "deal_id": deal_id, "deal": deal}

@app.post("/api/listings/create")
def create_listing(req: ListingRequest):
    item = {
        "id": len(memory_listings) + 1,
        "title": html.escape(req.title),
        "price": req.price,
        "category": html.escape(req.category),
        "country": html.escape(req.country),
        "seller": html.escape(req.seller) + " (موثق ✅)",
        "media_url": req.media_url if req.media_url else "https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=600&auto=format&fit=crop&q=80"
    }
    memory_listings.insert(0, item)
    return {"status": "success", "listing": item}

@app.post("/api/deals/{deal_id}/pay")
def pay_deal(deal_id: str, req: PaymentConfirmRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳"
    deal["status_note"] = f"تم إيداع وتجميد إجمالي المبلغ بنجاح عبر {req.payment_method} شاملاً عمولة الوساطة. بدأ مؤقت حماية التسليم."
    deal["messages"].append({"sender": "بوابة الدفع الآمنة", "text": f"💳 تم تأكيد إيداع {deal['total_paid']:,} ريال بنجاح (المبلغ + عمولة وثيق). تم تجميد المستحقات بالخزينة.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/release")
def release_funds(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "تم التسليم وتحويل المستحقات للبائع بنجاح ✅"
    deal["status_note"] = f"تم تأكيد الاستلام من المشتري، وتم تحويل صافي مستحقات البائع ({deal['price']:,} ريال) وخصم عمولة الوساطة تلقائياً."
    deal["messages"].append({"sender": "النظام (أمان وثيق)", "text": f"✅ تم تأكيد الاستلام بنجاح، وتحويل صافي المبلغ ({deal['price']:,} ريال) للبائع بعد اقتطاع عمولة الوساطة.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/refund")
def auto_refund_deal(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "تم الاسترجاع التلقائي للمشتري ↩️"
    deal["status_note"] = "تم استرجاع كامل المبلغ لحساب المشتري البنكي فورياً وتلقائياً لعدم تسليم السلعة."
    deal["messages"].append({"sender": "نظام الحماية التلقائي", "text": "↩️ تم تفعيل الاسترجاع التلقائي وإعادة كامل المبلغ للمشتري لحمايته من التأخير.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/dispute")
def dispute_deal(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "تم إيقاف الصفقة (نزاع تحت مراجعة الإدارة) ⚠️"
    deal["status_note"] = "تم رفع اعتراض وتجميد المستحقات والعمولة تحت مراجعة فريق التحكيم المالي."
    deal["messages"].append({"sender": "إدارة الرقابة والتحكيم", "text": "⚠️ تم تجميد الصفقة بناءً على طلب أحد الأطراف. يجري تدقيق السجلات من الوسيط.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/chat")
def send_chat(deal_id: str, req: MessageRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    msg = {"sender": html.escape(req.sender), "text": html.escape(req.text), "time": "الآن"}
    deal["messages"].append(msg)
    save_deal(deal)
    return {"status": "success", "messages": deal["messages"]}

# صفحة فحص الوثائق Verify المطابقة للصورة
@app.get("/verify", response_class=HTMLResponse)
def serve_verify_page():
    return """<!DOCTYPE html>
<html lang="en" dir="ltr" id="verifyHtml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watheeq | Verify Document</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22%23ffffff%22><path d=%22M4.5 12.75l6 6 9-13.5%22 stroke=%22%23ffffff%22 stroke-width=%222.5%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 fill=%22none%22/></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', 'Tajawal', sans-serif; background-color: #030303; color: #ffffff; }
        .card-dark { background: rgba(14, 14, 18, 0.7); border: 1px solid rgba(255, 255, 255, 0.08); }
        .pill-btn { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); color: #94a3b8; }
        .pill-btn.active { background: #ffffff; color: #000000; font-weight: 700; }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-white selection:text-black">

    <header class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between w-full">
        <a href="/" class="flex items-center gap-3">
            <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
            <span class="text-xl font-bold tracking-tight text-white uppercase">Watheeq</span>
        </a>

        <div class="flex items-center gap-6 text-xs font-medium text-slate-400">
            <a href="/" class="hover:text-white transition">Product</a>
            <a href="/#security" class="hover:text-white transition">Security</a>
            <a href="/#market" class="hover:text-white transition">Contact</a>
            <a href="/verify" class="text-white">Verify</a>
            <a href="/login" class="bg-white text-black font-bold px-4 py-2 rounded-full hover:bg-slate-200 transition">Sign In</a>
        </div>
    </header>

    <main class="flex-1 flex flex-col items-center justify-center text-center px-6 py-12">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 text-emerald-400 text-xs font-mono mb-8">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>LIVE VERIFICATION</span>
        </div>

        <h1 class="text-4xl md:text-6xl font-extrabold text-white tracking-tight mb-3">Verify Document.</h1>
        <p class="text-xs md:text-sm text-slate-400 mb-8 max-w-md">Enter a document ID or scan a QR code to verify authenticity</p>

        <div class="flex items-center gap-3 mb-8">
            <button onclick="switchMode('scan')" id="btnScan" class="pill-btn active px-6 py-2.5 rounded-full text-xs flex items-center gap-2">
                <span>📷</span> <span>Start QR Scan</span>
            </button>
            <button onclick="switchMode('id')" id="btnId" class="pill-btn px-6 py-2.5 rounded-full text-xs flex items-center gap-2">
                <span>📝</span> <span>Enter Public ID</span>
            </button>
        </div>

        <div id="scanBox" class="card-dark rounded-3xl p-8 max-w-sm w-full flex flex-col items-center justify-center text-center mb-4 min-h-[220px]">
            <div class="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 flex items-center justify-center text-2xl mb-4">⚠️</div>
            <p class="text-xs font-bold text-white mb-1">Unable to start camera. Please check permissions.</p>
            <p class="text-[11px] text-slate-500 mb-4">Or use manual ID search below</p>
            <button onclick="alert('Camera access requested')" class="bg-white text-black font-bold text-xs px-5 py-2 rounded-full hover:bg-slate-200">Retry Camera Access</button>
        </div>

        <div id="idBox" class="card-dark rounded-3xl p-6 max-w-sm w-full hidden mb-4 text-right">
            <label class="text-xs text-slate-400 block mb-2">Deal / Document ID:</label>
            <input id="publicDealId" type="text" placeholder="e.g. WTQ-701" class="w-full bg-black border border-white/10 rounded-xl p-3 text-white text-center font-mono uppercase text-sm mb-3 outline-none focus:border-white/30">
            <button onclick="lookupDeal()" class="w-full bg-white text-black font-bold text-xs py-2.5 rounded-xl">Inspect Vault Record</button>
        </div>

        <p class="text-xs text-slate-500 mb-10 font-mono">Or scan QR code</p>

        <div class="flex items-center gap-6 text-xs text-slate-500 font-mono">
            <span>🛡️ Bank-grade Security</span>
            <span>⚡ Instant Results</span>
            <span>⚖️ Zero Knowledge</span>
        </div>
    </main>

    <footer class="border-t border-white/5 py-8 max-w-7xl mx-auto px-6 w-full flex justify-between items-center text-xs text-slate-600">
        <div class="flex items-center gap-2">
            <span class="text-white font-bold uppercase">Watheeq</span>
        </div>
        <div class="flex gap-8">
            <span>Product</span>
            <span>Resources</span>
            <span>Legal</span>
        </div>
    </footer>

    <script>
        function switchMode(m) {
            if(m === 'scan') {
                document.getElementById('btnScan').classList.add('active');
                document.getElementById('btnId').classList.remove('active');
                document.getElementById('scanBox').classList.remove('hidden');
                document.getElementById('idBox').classList.add('hidden');
            } else {
                document.getElementById('btnId').classList.add('active');
                document.getElementById('btnScan').classList.remove('active');
                document.getElementById('scanBox').classList.add('hidden');
                document.getElementById('idBox').classList.remove('hidden');
            }
        }
        function lookupDeal() {
            const id = document.getElementById('publicDealId').value.trim();
            if(id) window.location.href = '/deal/' + id;
        }
    </script>
</body>
</html>"""

# صفحة تسجيل الدخول الجديدة المطابقة تماماً لصور بينانس/منصات الأمان
@app.get("/login", response_class=HTMLResponse)
@app.get("/issuer/login", response_class=HTMLResponse)
def serve_login():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="loginHtml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول | وثيق Watheeq</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22%23ffffff%22><path d=%22M4.5 12.75l6 6 9-13.5%22 stroke=%22%23ffffff%22 stroke-width=%222.5%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 fill=%22none%22/></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #0b0e11; color: #eaecef; }
        .auth-card {
            background-color: #181a20;
            border: 1px solid #23272f;
        }
        .yellow-btn {
            background-color: #fcd535;
            color: #181a20;
            transition: background 0.2s;
        }
        .yellow-btn:hover {
            background-color: #f0b90b;
        }
        .input-box {
            background-color: #0b0e11;
            border: 1px solid #23272f;
            color: #ffffff;
        }
        .input-box:focus {
            border-color: #f0b90b;
            outline: none;
        }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-yellow-400 selection:text-black">

    <header class="px-8 py-6 flex items-center justify-between">
        <a href="/" class="flex items-center gap-3">
            <svg class="w-7 h-7 text-yellow-400" viewBox="0 0 24 24" fill="currentColor">
                <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
            <span class="text-xl font-black tracking-tight text-white uppercase">Watheeq</span>
        </a>
        <div class="flex items-center gap-6 text-xs text-slate-400 font-medium">
            <button onclick="toggleLang()" class="border border-slate-700 px-3 py-1.5 rounded-full text-slate-200" id="langText">English</button>
            <a href="/" class="hover:text-yellow-400 transition">الرئيسية</a>
        </div>
    </header>

    <main class="flex-1 flex flex-col items-center justify-center px-4 py-12">
        <div class="auth-card p-8 md:p-10 rounded-3xl max-w-md w-full shadow-2xl relative">
            
            <!-- Logo Icon -->
            <div class="flex items-center justify-center gap-2 mb-6">
                <svg class="w-8 h-8 text-yellow-400" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
            </div>

            <!-- Dynamic Header Step 1, 2, 3 -->
            <div id="stepHeader" class="text-center mb-8">
                <h1 id="stepTitle" class="text-2xl font-black text-white mb-2">تسجيل الدخول</h1>
                <p id="stepSub" class="text-xs text-slate-400">البريد الإلكتروني / رقم الهوية</p>
            </div>

            <!-- Form Container -->
            <div id="formContainer" class="space-y-4">
                
                <!-- Step 1: Email/ID -->
                <div id="boxStep1" class="space-y-4">
                    <div>
                        <input id="inputEmail" type="text" placeholder="name@domain.com أو رقم الهوية" class="w-full input-box rounded-xl p-3.5 text-sm">
                    </div>
                    <button onclick="goToStep2()" class="w-full yellow-btn font-bold py-3.5 rounded-xl text-sm">متابعة</button>
                    
                    <div class="pt-4 border-t border-slate-800 space-y-3">
                        <button onclick="alert('Google Auth')" class="w-full input-box hover:bg-slate-800 py-3 rounded-xl text-xs flex items-center justify-center gap-2 font-medium">🌐 المتابعة باستخدام Google</button>
                        <button onclick="alert('Apple Auth')" class="w-full input-box hover:bg-slate-800 py-3 rounded-xl text-xs flex items-center justify-center gap-2 font-medium">🍏 المتابعة باستخدام Apple</button>
                    </div>
                </div>

                <!-- Step 2: Password -->
                <div id="boxStep2" class="space-y-4 hidden">
                    <p id="displayEmailUser" class="text-xs text-slate-400 text-center font-mono mb-2"></p>
                    <div>
                        <label class="block text-[11px] text-slate-400 mb-1">كلمة المرور</label>
                        <input id="inputPassword" type="password" placeholder="••••••••" class="w-full input-box rounded-xl p-3.5 text-sm">
                    </div>
                    <div class="flex justify-between items-center text-xs">
                        <button onclick="alert('تم إرسال رابط استعادة كلمة المرور عبر الإيميل')" class="text-yellow-400 hover:underline">هل نسيت كلمة المرور؟</button>
                        <button onclick="backToStep1()" class="text-slate-400 hover:text-white">تغيير الحساب</button>
                    </div>
                    <button onclick="goToStep3()" class="w-full yellow-btn font-bold py-3.5 rounded-xl text-sm mt-2">تسجيل الدخول</button>
                </div>

                <!-- Step 3: OTP Code (6 digits) -->
                <div id="boxStep3" class="space-y-4 hidden text-center">
                    <p class="text-xs text-slate-400">أدخل رمز التحقق المكون من 6 أرقام تم إرساله إلى بريدك</p>
                    <div class="flex justify-center gap-2 py-3">
                        <input type="text" maxlength="1" class="w-12 h-12 text-center text-lg font-bold input-box rounded-xl">
                        <input type="text" maxlength="1" class="w-12 h-12 text-center text-lg font-bold input-box rounded-xl">
                        <input type="text" maxlength="1" class="w-12 h-12 text-center text-lg font-bold input-box rounded-xl">
                        <input type="text" maxlength="1" class="w-12 h-12 text-center text-lg font-bold input-box rounded-xl">
                        <input type="text" maxlength="1" class="w-12 h-12 text-center text-lg font-bold input-box rounded-xl">
                        <input type="text" maxlength="1" class="w-12 h-12 text-center text-lg font-bold input-box rounded-xl">
                    </div>
                    <button onclick="finalizeLogin()" class="w-full yellow-btn font-bold py-3.5 rounded-xl text-sm">تأكيد وتحقق</button>
                </div>

            </div>

            <div class="mt-8 text-center text-xs text-slate-500 space-y-2">
                <a href="/" class="text-yellow-400 block hover:underline">إنشاء حساب وثيق جديد</a>
                <a href="/" class="block hover:text-slate-300">ألا يمكنك تسجيل الدخول؟</a>
            </div>

        </div>
    </main>

    <footer class="px-8 py-6 text-center text-xs text-slate-600 font-mono border-t border-slate-900">
        WATHEEQ SECURE GATEWAY • SAFEWATHEEQ.COM
    </footer>

    <script>
        let currentLang = 'ar';
        let savedUser = '';

        function toggleLang() {
            currentLang = (currentLang === 'ar') ? 'en' : 'ar';
            document.getElementById('langText').innerText = (currentLang === 'ar') ? 'English' : 'العربية';
            document.getElementById('loginHtml').setAttribute('dir', currentLang === 'ar' ? 'rtl' : 'ltr');
            document.getElementById('loginHtml').setAttribute('lang', currentLang);
        }

        function goToStep2() {
            const email = document.getElementById('inputEmail').value.trim();
            if(!email) { alert('يرجى إدخال البريد الإلكتروني أو الهوية'); return; }
            savedUser = email;
            document.getElementById('displayEmailUser').innerText = email;
            document.getElementById('boxStep1').classList.add('hidden');
            document.getElementById('boxStep2').classList.remove('hidden');
            document.getElementById('stepTitle').innerText = 'أدخل كلمة المرور';
            document.getElementById('stepSub').innerText = email;
        }

        function backToStep1() {
            document.getElementById('boxStep2').classList.add('hidden');
            document.getElementById('boxStep1').classList.remove('hidden');
            document.getElementById('stepTitle').innerText = 'تسجيل الدخول';
            document.getElementById('stepSub').innerText = 'البريد الإلكتروني / رقم الهوية';
        }

        function goToStep3() {
            const pass = document.getElementById('inputPassword').value.trim();
            if(!pass) { alert('يرجى إدخال كلمة المرور'); return; }
            document.getElementById('boxStep2').classList.add('hidden');
            document.getElementById('boxStep3').classList.remove('hidden');
            document.getElementById('stepTitle').innerText = 'التحقق الأمني الثنائي';
            document.getElementById('stepSub').innerText = 'أدخل رمز التحقق المرسل';
        }

        function finalizeLogin() {
            alert('✅ تم التحقق وتسجيل الدخول بنجاح! جاري تحويلك لغرفة الصفقات...');
            window.location.href = '/deal/WTQ-701';
        }
    </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def serve_home():
    listings_cards = ""
    for item in memory_listings:
        listings_cards += f"""
        <div class="card-dark rounded-2xl overflow-hidden border border-white/10 flex flex-col justify-between group hover:border-white/30 transition">
            <div class="relative h-48 w-full bg-slate-900 overflow-hidden">
                <img src="{item['media_url']}" alt="{item['title']}" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">
                <span class="absolute top-3 right-3 bg-black/70 backdrop-blur-md px-2.5 py-1 rounded-md text-[11px] font-mono text-white border border-white/10">{item['country']}</span>
                <span class="absolute bottom-3 left-3 bg-emerald-500/80 backdrop-blur-md text-black font-black px-2.5 py-1 rounded-md text-xs">{item['category']}</span>
            </div>
            <div class="p-5 flex-1 flex flex-col justify-between text-right">
                <div>
                    <h4 class="text-base font-bold text-white mb-2 line-clamp-1">{item['title']}</h4>
                    <p class="text-xs text-slate-400 mb-4">👤 المعلن: {item['seller']}</p>
                </div>
                <div class="border-t border-white/10 pt-4 flex items-center justify-between">
                    <div>
                        <span class="text-[10px] text-slate-500 block">السعر المطلوب</span>
                        <span class="text-lg font-black text-emerald-400 font-mono">{item['price']:,} ريال</span>
                    </div>
                    <button onclick="buyFromMarket('{item['title']}', '{item['category']}', {item['price']}, '{item['seller']}')" class="btn-white text-xs font-bold px-4 py-2 rounded-xl">
                        شراء بضمان وثيق 🛡️
                    </button>
                </div>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlTag">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="siteTitle">وثيق | Watheeq - Escrow & Marketplace</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22%23ffffff%22><path d=%22M4.5 12.75l6 6 9-13.5%22 stroke=%22%23ffffff%22 stroke-width=%222.5%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 fill=%22none%22/></svg>">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Tajawal', 'Inter', sans-serif; background-color: #030303; color: #ffffff; overflow-x: hidden; }}
        .hero-glow {{
            background: radial-gradient(circle at 50% 25%, rgba(255, 255, 255, 0.08) 0%, rgba(3, 3, 3, 0.98) 75%);
        }}
        .light-streak {{
            position: absolute;
            width: 130%;
            height: 320px;
            top: 20%;
            left: -15%;
            background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.12) 0%, rgba(255,255,255,0.02) 40%, rgba(0,0,0,0) 70%);
            transform: rotate(-10deg);
            pointer-events: none;
            filter: blur(50px);
        }}
        .card-dark {{
            background: rgba(14, 14, 18, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(20px);
        }}
        .btn-white {{
            background: #ffffff;
            color: #000000;
            transition: all 0.2s ease;
        }}
        .btn-white:hover {{
            background: #e2e8f0;
            transform: scale(1.02);
        }}
        .btn-glass {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #ffffff;
            transition: all 0.2s ease;
        }}
        .pill-badge {{
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between relative selection:bg-white selection:text-black">

    <div class="light-streak"></div>

    <div class="bg-amber-500/10 border-b border-amber-500/20 py-2.5 px-6 text-center text-xs font-semibold text-amber-300 flex items-center justify-center gap-2">
        <span>🛡️ نظام الضمان الإلزامي:</span>
        <span>لا يمكن دفع أي مستحقات للطرف الآخر خارج المنصة. يتم إيداع وتجميد كامل قيمة السلعة وعمولة الوساطة بنكياً دفعة واحدة لحماية الطرفين.</span>
    </div>

    <div id="authModal" class="fixed inset-0 bg-black/90 z-50 backdrop-blur-md hidden items-center justify-center p-4">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full border border-white/20 text-center relative shadow-2xl">
            <div class="w-16 h-16 rounded-2xl bg-white/10 border border-white/20 mx-auto flex items-center justify-center text-3xl mb-4">🪪</div>
            <h3 class="text-xl font-black text-white mb-2">توثيق الهوية الوطنية وبصمة الوجه (نفاذ)</h3>
            <p class="text-xs text-slate-400 mb-6">لحماية الصفقات من الحسابات الوهمية والاحتيال، يتم ربط هويات البائع والمشتري بنظام التحقق الثنائي.</p>
            
            <div class="space-y-3 mb-6 text-right">
                <div>
                    <label class="text-xs text-slate-400 block mb-1">رقم الهوية الوطنية / الإقامة:</label>
                    <input id="nafathId" type="text" placeholder="1XXXXXXXXX" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm font-mono text-center tracking-widest outline-none focus:border-white/40">
                </div>
            </div>

            <div class="flex gap-3">
                <button onclick="simulateNafath()" class="flex-1 btn-white text-xs font-black py-3 rounded-xl">طلب رمز التحقق (نفاذ Face ID) 📱</button>
                <button onclick="closeAuthModal()" class="px-5 py-3 btn-glass text-xs rounded-xl">إغلاق</button>
            </div>
            <p class="text-[10px] text-slate-500 mt-4">🔒 مشفر بنظام التشفير الحكومي ومحمي ضد التزوير</p>
        </div>
    </div>

    <header class="border-b border-white/5 bg-black/60 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3 cursor-pointer">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                </svg>
                <div class="flex flex-col text-right">
                    <span class="text-lg font-black tracking-tight text-white uppercase">Watheeq</span>
                    <span class="text-[10px] text-slate-400 font-medium tracking-wider uppercase font-mono">الوساطة والضمان المالي</span>
                </div>
            </a>
            
            <nav class="hidden md:flex items-center gap-6 text-xs font-semibold text-slate-400">
                <a href="#market" class="hover:text-white transition text-emerald-400">حراج وإعلانات وثيق 🛍️</a>
                <a href="#calculator" class="hover:text-white transition" id="navCalc">حاسبة العمولات</a>
                <a href="#security" class="hover:text-white transition" id="navSec">بروتوكول الأمان</a>
                <a href="/deal/WTQ-701" class="hover:text-white transition" id="navLive">غرفة حية (WTQ-701)</a>
            </nav>

            <div class="flex items-center gap-3">
                <button onclick="toggleLanguage()" id="langBtn" class="pill-badge text-slate-300 px-3 py-1.5 rounded-full text-xs font-semibold hover:border-white/30 transition">
                    🌐 English
                </button>
                
                <button onclick="openAuthModal()" id="nafathBtn" class="pill-badge text-amber-400 border-amber-500/30 bg-amber-500/10 px-3 py-1.5 rounded-full text-xs font-semibold hover:bg-amber-500/20 transition flex items-center gap-1">
                    <span>🛡️</span> <span id="nafathText">نفاذ (Face ID)</span>
                </button>

                <a href="/verify" class="pill-badge text-slate-300 px-3.5 py-1.5 rounded-full text-xs font-semibold hover:border-white/30 transition">
                    Verify
                </a>

                <a href="/login" class="pill-badge text-slate-300 px-3.5 py-1.5 rounded-full text-xs font-semibold hover:border-white/30 transition">
                    Sign In
                </a>

                <button onclick="openModal()" class="btn-white text-xs font-black px-4 py-2 rounded-full shadow-sm hover:scale-105 transition" id="btnNav">
                    + إنشاء صفقة
                </button>
            </div>
        </div>
    </header>

    <main class="hero-glow flex-1 flex flex-col items-center justify-center text-center px-6 py-20 relative z-10">
        
        <div class="inline-flex items-center gap-2 px-4 py-1 rounded-full pill-badge text-emerald-400 text-xs font-mono tracking-wide mb-8">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span id="heroBadge">V1.0 IS LIVE & SECURE</span>
        </div>

        <h1 class="text-4xl md:text-6xl font-black text-white tracking-tight leading-[1.2] max-w-4xl mb-6" id="heroHeadline">
            The immutable<br><span class="text-slate-400 font-light">standard.</span>
        </h1>

        <p class="text-slate-400 text-sm md:text-base max-w-2xl mb-10 leading-relaxed font-normal" id="heroSub">
            المنصة والوساطة المالية السعودية لضمان وتأمين كافة المبايعات والصفقات والإعلانات بأقل عمولة في السوق (تبدأ من 1%). يتم سداد وحجز كامل المبلغ مع العمولة بنكياً عبر Apple Pay ومدى حتى الفحص والتسليم التام.
        </p>

        <div class="flex flex-wrap items-center justify-center gap-4 mb-16">
            <button onclick="openModal()" class="btn-white text-sm font-bold px-8 py-3.5 rounded-full flex items-center gap-2" id="heroBtn1">
                <span>ابدأ صفقة جديدة</span>
                <span class="text-base">⚡</span>
            </button>
            <a href="#market" class="btn-glass text-sm font-semibold px-8 py-3.5 rounded-full">
                تصفح الإعلانات والسوق 🛒
            </a>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl w-full text-right" id="statsContainer">
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat1Label">الأصول والحسابات والألعاب</p>
                <p class="text-lg font-black text-white font-mono">2.5% <span class="text-[11px] text-emerald-400 font-normal" id="stat1Sub">أقل عمولة</span></p>
            </div>
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat2Label">عربون وفحص السيارات</p>
                <p class="text-lg font-black text-white font-mono">1.5% <span class="text-[11px] text-slate-400 font-normal">ضمان فحص</span></p>
            </div>
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat3Label">مؤقت الاسترجاع التلقائي</p>
                <p class="text-lg font-black text-white font-mono">10 Min <span class="text-[11px] text-slate-400 font-normal">حماية فورية</span></p>
            </div>
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat4Label">بوابات الدفع المشفرة</p>
                <div class="flex items-center gap-2 text-white mt-1">
                    <svg class="w-5 h-5 fill-current" viewBox="0 0 170 170"><path d="M150.37 130.25c-2.45 5.66-5.35 10.87-8.71 15.66-4.58 6.53-8.33 11.05-11.22 13.56-4.48 4.12-9.28 6.23-14.42 6.35-3.69 0-8.14-1.05-13.32-3.18-5.19-2.12-9.97-3.17-14.34-3.17-4.58 0-9.49 1.05-14.75 3.17-5.26 2.13-9.5 3.24-12.74 3.35-4.35.13-9.16-1.9-14.42-6.08-3.69-3.08-7.78-8.08-12.28-15-6.3-9.76-11.38-20.91-15.24-33.45-3.86-12.54-5.79-24.3-5.79-35.28 0-14.28 3.57-26.15 10.72-35.61 7.15-9.46 16.29-14.32 27.42-14.58 4.8.12 10.33 1.34 16.59 3.66 6.26 2.32 10.02 3.54 11.28 3.66 2.01-.33 6.07-1.74 12.18-4.23 6.11-2.49 11.66-3.62 16.65-3.39 12.77 1.07 22.84 5.98 30.21 14.74-11.13 6.75-16.58 16.03-16.36 27.84.22 9.25 3.86 16.99 10.92 23.23 7.06 6.24 15.42 9.77 25.08 10.6-2.12 6.53-4.78 13.06-7.98 19.59zM119.22 33.64c0-7.39 2.65-14.35 7.95-20.88 5.3-6.53 11.83-10.72 19.59-12.57.8 7.39-1.63 14.36-7.29 20.91-5.66 6.55-12.41 10.73-20.25 12.54z"/></svg>
                    <span class="font-bold text-sm">Pay / مدى</span>
                </div>
            </div>
        </div>

    </main>

    <section id="market" class="max-w-6xl mx-auto px-6 py-16 w-full relative z-10">
        <div class="flex flex-col md:flex-row justify-between items-start md:items-end mb-8 gap-4">
            <div class="text-right">
                <div class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold mb-2">
                    🛍️ السوق والوساطة المفتوحة لكافة الدول
                </div>
                <h3 class="text-2xl md:text-3xl font-black text-white">إعلانات وسلع معروضة بضمان وثيق</h3>
                <p class="text-xs text-slate-400">اشتري أي سلعة أو عربون سيارة مشفر بأمان، أو أضف إعلانك الخاص للبيع</p>
            </div>
            <button onclick="openListingModal()" class="btn-white text-xs font-bold px-6 py-3 rounded-full flex items-center gap-2">
                <span>+ أضف إعلان سلعة/سيارة جديد</span>
            </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            {listings_cards}
        </div>
    </section>

    <section id="calculator" class="max-w-4xl mx-auto px-6 py-12 w-full relative z-10">
        <div class="card-dark p-8 md:p-10 rounded-3xl">
            <div class="text-center mb-8">
                <h3 class="text-2xl font-black text-white mb-2" id="calcHead">حاسبة كسر السوق والعمولات الشفافة</h3>
                <p class="text-xs text-slate-400" id="calcSub">تحطيم أسعار العمولات التقليدية لضمان أعلى فائدة للبائع والمشتري</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div>
                    <label class="block text-xs font-bold text-slate-400 mb-2" id="lblAmount">قيمة الصفقة أو العربون:</label>
                    <input id="calcAmount" type="number" value="1000" oninput="runCalculator()" class="w-full bg-black/60 border border-white/10 rounded-2xl p-3.5 text-white font-mono font-bold outline-none focus:border-white/40">
                </div>
                <div>
                    <label class="block text-xs font-bold text-slate-400 mb-2" id="lblCat">مجال الوساطة:</label>
                    <select id="calcCategory" onchange="runCalculator()" class="w-full bg-black/60 border border-white/10 rounded-2xl p-3.5 text-white text-sm outline-none focus:border-white/40">
                        <option value="digital" id="opt1">الأصول الرقمية، الحسابات، والألعاب (2.5%)</option>
                        <option value="freelance" id="opt2">الخدمات والعمل الحر والبرمجة (2.5%)</option>
                        <option value="car_deposit" id="opt3">عربون حجز وفحص المركبات (1.5%)</option>
                        <option value="goods" id="opt4">الأجهزة الإلكترونية والسلع (1.5%)</option>
                    </select>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 text-center mb-6 font-mono">
                <div>
                    <span class="block text-[11px] text-slate-500 mb-1" id="resSeller">المبلغ الصافي للبائع</span>
                    <span id="calcNet" class="text-base md:text-lg font-bold text-white">1,000 ريال</span>
                </div>
                <div>
                    <span class="block text-[11px] text-slate-400 mb-1" id="resFee">عمولة وثيق المحسومة</span>
                    <span id="calcFee" class="text-base md:text-lg font-bold text-slate-300">25 ريال</span>
                </div>
                <div>
                    <span class="block text-[11px] text-emerald-400 mb-1" id="resTotal">الإجمالي الإلزامي للإيداع</span>
                    <span id="calcTotal" class="text-base md:text-lg font-black text-emerald-400">1,025 ريال</span>
                </div>
            </div>

            <div class="text-center">
                <button onclick="openModalWithValues()" class="btn-white text-xs font-black px-8 py-3.5 rounded-full" id="calcBtn">
                    ابدأ بهذه الحسبة وتجميد المبلغ 🚀
                </button>
            </div>
        </div>
    </section>

    <section id="security" class="max-w-6xl mx-auto px-6 py-12 relative z-10">
        <div class="text-center mb-10">
            <h3 class="text-2xl font-black text-white mb-2" id="secHead">ترسانة الحماية ومنع الاحتيال</h3>
            <p class="text-xs text-slate-400" id="secSub">آليات مالية صارمة لحماية أموالك وسلعك أثناء البيع والشراء</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 text-right">
            <div class="card-dark p-6 rounded-2xl">
                <div class="text-3xl mb-3">⏱️</div>
                <h4 class="text-sm font-bold text-white mb-2" id="sec1Title">مؤقت الاسترجاع الفوري (10 دقائق)</h4>
                <p class="text-xs text-slate-400 leading-relaxed" id="sec1Desc">في الصفقات الرقمية والحسابات، إذا لم يقم البائع بتسليم البيانات خلال 10 دقائق، يقوم النظام تلقائياً بإرجاع كامل المبلغ للمشتري.</p>
            </div>
            <div class="card-dark p-6 rounded-2xl">
                <div class="text-3xl mb-3">🚗</div>
                <h4 class="text-sm font-bold text-white mb-2" id="sec2Title">ضمان عربون فحص السيارات</h4>
                <p class="text-xs text-slate-400 leading-relaxed" id="sec2Desc">احجز سيارتك وافحصها بالورشة وأنت مطمئن؛ العربون محفوظ بالخزينة ولا يتحول للبائع إلا بموافقتك بعد التأكد من سلامة الفحص.</p>
            </div>
            <div class="card-dark p-6 rounded-2xl">
                <div class="text-3xl mb-3">
                    <svg class="w-8 h-8 fill-current text-white mb-1" viewBox="0 0 170 170"><path d="M150.37 130.25c-2.45 5.66-5.35 10.87-8.71 15.66-4.58 6.53-8.33 11.05-11.22 13.56-4.48 4.12-9.28 6.23-14.42 6.35-3.69 0-8.14-1.05-13.32-3.18-5.19-2.12-9.97-3.17-14.34-3.17-4.58 0-9.49 1.05-14.75 3.17-5.26 2.13-9.5 3.24-12.74 3.35-4.35.13-9.16-1.9-14.42-6.08-3.69-3.08-7.78-8.08-12.28-15-6.3-9.76-11.38-20.91-15.24-33.45-3.86-12.54-5.79-24.3-5.79-35.28 0-14.28 3.57-26.15 10.72-35.61 7.15-9.46 16.29-14.32 27.42-14.58 4.8.12 10.33 1.34 16.59 3.66 6.26 2.32 10.02 3.54 11.28 3.66 2.01-.33 6.07-1.74 12.18-4.23 6.11-2.49 11.66-3.62 16.65-3.39 12.77 1.07 22.84 5.98 30.21 14.74-11.13 6.75-16.58 16.03-16.36 27.84.22 9.25 3.86 16.99 10.92 23.23 7.06 6.24 15.42 9.77 25.08 10.6-2.12 6.53-4.78 13.06-7.98 19.59zM119.22 33.64c0-7.39 2.65-14.35 7.95-20.88 5.3-6.53 11.83-10.72 19.59-12.57.8 7.39-1.63 14.36-7.29 20.91-5.66 6.55-12.41 10.73-20.25 12.54z"/></svg>
                </div>
                <h4 class="text-sm font-bold text-white mb-2" id="sec3Title">حجز مصرفي إلزامي عبر Apple Pay ومدى</h4>
                <p class="text-xs text-slate-400 leading-relaxed" id="sec3Desc">يتم تحصيل وسداد العمولة مع المبلغ في حركة واحدة لمنع التحويلات الخارجية وضمان استلام الحقوق كاملاً.</p>
            </div>
        </div>
    </section>

    <div id="createModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-lg w-full border border-white/20 text-right">
            <h3 class="text-xl font-black text-white mb-1" id="mTitle">إنشاء رابط صفقة وساطة جديد</h3>
            <p class="text-xs text-slate-400 mb-6" id="mSub">سيتم إنشاء غرفة تسليم مشفرة برابط مباشر للأطراف مع بوابة حجز بنكي تشمل العمولة والضمان.</p>
            
            <div class="space-y-4">
                <div>
                    <label class="text-xs text-slate-400 block mb-1" id="mLabel1">عنوان الصفقة أو السلعة</label>
                    <input id="newTitle" type="text" placeholder="عربون فحص كامري / حساب ألعاب / برمجة متجر" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1" id="mLabel2">القسم والتصنيف</label>
                    <select id="newCategory" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                        <option>الأصول الرقمية والحسابات (2.5%)</option>
                        <option>الخدمات والعمل الحر (2.5%)</option>
                        <option>مركبات ومعدات وعرابين (1.5%)</option>
                        <option>الأجهزة الإلكترونية والسلع (1.5%)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1" id="mLabel3">المبلغ المطلوب (ريال)</label>
                    <input id="newPrice" type="number" placeholder="1000" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs text-slate-400 block mb-1" id="mLabel4">اسم / يوزر البائع</label>
                        <input id="newSeller" type="text" placeholder="البائع" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400 block mb-1" id="mLabel5">اسم / يوزر المشتري</label>
                        <input id="newBuyer" type="text" placeholder="المشتري (اختياري)" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                    </div>
                </div>
            </div>

            <div class="mt-6 flex gap-3">
                <button onclick="submitDeal()" class="flex-1 btn-white text-xs font-black py-3 rounded-xl" id="mBtnSubmit">إنشاء الرابط وحجز الضمان والعمولة 🔒</button>
                <button onclick="closeModal()" class="px-5 py-3 btn-glass text-xs rounded-xl" id="mBtnCancel">إلغاء</button>
            </div>
        </div>
    </div>

    <div id="listingModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-lg w-full border border-white/20 text-right">
            <h3 class="text-xl font-black text-white mb-1">إضافة إعلان جديد في حراج وثيق</h3>
            <p class="text-xs text-slate-400 mb-6">اعرض سلعتك أو سيارتك لكافة الدول مع حماية المشتري والبائع عبر الضمان المالي.</p>
            
            <div class="space-y-4">
                <div>
                    <label class="text-xs text-slate-400 block mb-1">عنوان الإعلان / السلعة</label>
                    <input id="listTitle" type="text" placeholder="مثال: لكزس 2024 فل كامل / بي سي قيمنق" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">السعر (ريال)</label>
                        <input id="listPrice" type="number" placeholder="5000" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">الدولة والمدينة</label>
                        <select id="listCountry" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                            <option>🇸🇦 السعودية - الرياض</option>
                            <option>🇸🇦 السعودية - جدة</option>
                            <option>🇸🇦 السعودية - المدينة</option>
                            <option>🇦🇪 الإمارات - دبي</option>
                            <option>🇰🇼 الكويت</option>
                            <option>🇶🇦 قطر</option>
                            <option>🇧🇭 البحرين</option>
                            <option>🇴🇲 عمان</option>
                            <option>🌍 دولي / أونلاين</option>
                        </select>
                    </div>
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">القسم</label>
                    <select id="listCategory" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                        <option>مركبات وعرابين</option>
                        <option>أصول رقمية وحسابات</option>
                        <option>سلع عامة وإلكترونيات</option>
                        <option>خدمات وعمل حر</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">رابط صورة أو فيديو السلعة (URL)</label>
                    <input id="listMedia" type="text" placeholder="https://..." class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">اسم / يوزر البائع</label>
                    <input id="listSeller" type="text" placeholder="اسمك أو يوزرك" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
            </div>

            <div class="mt-6 flex gap-3">
                <button onclick="submitListing()" class="flex-1 btn-white text-xs font-black py-3 rounded-xl">نشر الإعلان الآن 📢</button>
                <button onclick="closeListingModal()" class="px-5 py-3 btn-glass text-xs rounded-xl">إلغاء</button>
            </div>
        </div>
    </div>

    <footer class="border-t border-white/5 py-8 bg-black text-center text-xs text-slate-500 relative z-10 space-y-2 font-mono">
        <p id="footerRights">© 2026 WATHEEQ ESCROW & MARKETPLACE | SAFEWATHEEQ.COM</p>
        <p class="text-slate-600" id="footerReg">SECURE ESCROW • MANDATORY FEE LOCK • ANTI-FRAUD</p>
    </footer>

    <script>
        let currentLang = 'ar';
        const i18n = {{
            ar: {{
                langBtn: '🌐 English',
                navCalc: 'حاسبة العمولات',
                navSec: 'بروتوكول الأمان',
                navLive: 'غرفة حية (WTQ-701)',
                btnNav: '+ إنشاء صفقة',
                curr: ' ريال'
            }},
            en: {{
                langBtn: '🌐 العربية',
                navCalc: 'Fee Calculator',
                navSec: 'Security Protocol',
                navLive: 'Live Deal (WTQ-701)',
                btnNav: '+ Create Deal',
                curr: ' SAR'
            }}
        }};

        function toggleLanguage() {{
            currentLang = (currentLang === 'ar') ? 'en' : 'ar';
            const htmlTag = document.getElementById('htmlTag');
            const data = i18n[currentLang];
            htmlTag.setAttribute('dir', currentLang === 'ar' ? 'rtl' : 'ltr');
            htmlTag.setAttribute('lang', currentLang);
            document.getElementById('langBtn').innerText = data.langBtn;
            runCalculator();
        }}

        function runCalculator() {{
            const amount = parseFloat(document.getElementById('calcAmount').value) || 0;
            const cat = document.getElementById('calcCategory').value;
            let fee = (amount * 2.5) / 100;
            if(cat === 'car_deposit' || cat === 'goods') {{
                fee = (amount * 1.5) / 100;
            }}
            const total = amount + fee;
            const cur = i18n[currentLang].curr;
            document.getElementById('calcNet').innerText = amount.toLocaleString() + cur;
            document.getElementById('calcFee').innerText = fee.toLocaleString() + cur;
            document.getElementById('calcTotal').innerText = total.toLocaleString() + cur;
        }}

        function openModal() {{ document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex'); }}
        function openModalWithValues() {{ document.getElementById('newPrice').value = document.getElementById('calcAmount').value; openModal(); }}
        function closeModal() {{ document.getElementById('createModal').classList.add('hidden'); document.getElementById('createModal').classList.remove('flex'); }}
        function openListingModal() {{ document.getElementById('listingModal').classList.remove('hidden'); document.getElementById('listingModal').classList.add('flex'); }}
        function closeListingModal() {{ document.getElementById('listingModal').classList.add('hidden'); document.getElementById('listingModal').classList.remove('flex'); }}
        function openAuthModal() {{ document.getElementById('authModal').classList.remove('hidden'); document.getElementById('authModal').classList.add('flex'); }}
        function closeAuthModal() {{ document.getElementById('authModal').classList.add('hidden'); document.getElementById('authModal').classList.remove('flex'); }}

        function simulateNafath() {{
            const id = document.getElementById('nafathId').value.trim();
            if(id.length < 10) {{ alert('يرجى إدخال رقم هوية صحيح مكون من 10 أرقام'); return; }}
            alert('تم إرسال طلب التحقق إلى تطبيق نفاذ (Face ID) برمز تأكيد: ' + Math.floor(10 + Math.random() * 90));
            closeAuthModal();
            document.getElementById('nafathBtn').innerHTML = '<span>✅</span> <span>موثق بنفاذ</span>';
            document.getElementById('nafathBtn').classList.remove('text-amber-400', 'border-amber-500/30', 'bg-amber-500/10');
            document.getElementById('nafathBtn').classList.add('text-emerald-400', 'border-emerald-500/30', 'bg-emerald-500/10');
        }}

        async function submitDeal() {{
            const title = document.getElementById('newTitle').value;
            const categoryElem = document.getElementById('newCategory');
            const category = categoryElem.options[categoryElem.selectedIndex].text;
            const price = parseFloat(document.getElementById('newPrice').value);
            const seller_name = document.getElementById('newSeller').value;
            const buyer_name = document.getElementById('newBuyer').value;
            if(!title || !price || !seller_name) {{ alert('يرجى تعبئة الحقول الأساسية'); return; }}
            const res = await fetch('/api/deals/create', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{title, category, price, seller_name, buyer_name}})
            }});
            const data = await res.json();
            if(data.status === 'success') {{ window.location.href = '/deal/' + data.deal_id; }}
        }}

        async function submitListing() {{
            const title = document.getElementById('listTitle').value;
            const price = parseFloat(document.getElementById('listPrice').value);
            const country = document.getElementById('listCountry').value;
            const category = document.getElementById('listCategory').value;
            const media_url = document.getElementById('listMedia').value;
            const seller = document.getElementById('listSeller').value;
            if(!title || !price || !seller) {{ alert('يرجى تعبئة الحقول الأساسية'); return; }}
            const res = await fetch('/api/listings/create', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{title, price, category, country, seller, media_url}})
            }});
            if(res.ok) {{ alert('تم نشر إعلانك بنجاح في حراج وثيق!'); location.reload(); }}
        }}

        function buyFromMarket(title, category, price, seller) {{
            document.getElementById('newTitle').value = 'شراء إعلان: ' + title;
            document.getElementById('newPrice').value = price;
            document.getElementById('newSeller').value = seller;
            openModal();
        }}

        runCalculator();
    </script>
</body>
</html>"""

@app.get("/deal/{deal_id}", response_class=HTMLResponse)
def serve_deal_room(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        return HTMLResponse("<h1>عذراً، الصفقة غير موجودة أو انتهت صلاحيتها.</h1>", status_code=404)
    
    is_pending = ("بانتظار" in deal['status'])
    
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>غرفة الضمان {deal['id']} | وثيق</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22%23ffffff%22><path d=%22M4.5 12.75l6 6 9-13.5%22 stroke=%22%23ffffff%22 stroke-width=%222.5%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 fill=%22none%22/></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Tajawal', 'Inter', sans-serif; background-color: #050507; color: #ffffff; }}
        .card-dark {{ background: rgba(14, 14, 18, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(20px); }}
        .btn-white {{ background: #ffffff; color: #000000; transition: all 0.2s; }}
        .btn-white:hover {{ background: #e2e8f0; transform: scale(1.02); }}
        .btn-glass {{ background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); color: #ffffff; }}
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">

    <div id="paymentModal" class="fixed inset-0 bg-black/90 z-50 backdrop-blur-md hidden items-center justify-center p-4">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full border border-white/20 text-center relative shadow-2xl">
            <div class="w-14 h-14 rounded-2xl bg-white/10 mx-auto flex items-center justify-center text-2xl mb-4">💳</div>
            <h3 class="text-xl font-bold text-white mb-2">إيداع الضمان المالي في خزينة وثيق</h3>
            <p class="text-xs text-slate-400 mb-6">المبلغ يُحجز مشفراً شاملاً عمولة الوساطة، ولا يُحول للبائع إلا بعد فحصك وموافقتك التامة.</p>
            
            <div class="bg-black/60 border border-white/10 p-4 rounded-2xl mb-6 text-right space-y-2 text-sm font-mono">
                <div class="flex justify-between text-slate-400"><span>المبلغ الأساسي للسلعة:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                <div class="flex justify-between text-xs text-slate-400"><span>عمولة الضمان والوساطة ({deal['fee_percent']}%):</span><span class="text-amber-400 font-bold">{deal['fee_amount']} ريال</span></div>
                <div class="flex justify-between border-t border-white/10 pt-2 text-base"><span>الإجمالي المطلوب سداده:</span><span class="text-emerald-400 font-black">{deal['total_paid']:,} ريال</span></div>
            </div>

            <div class="space-y-3">
                <button onclick="executePayment('Apple Pay ')" class="w-full btn-white font-bold py-3.5 rounded-2xl flex items-center justify-center gap-2">
                    <svg class="w-5 h-5 fill-current" viewBox="0 0 170 170"><path d="M150.37 130.25c-2.45 5.66-5.35 10.87-8.71 15.66-4.58 6.53-8.33 11.05-11.22 13.56-4.48 4.12-9.28 6.23-14.42 6.35-3.69 0-8.14-1.05-13.32-3.18-5.19-2.12-9.97-3.17-14.34-3.17-4.58 0-9.49 1.05-14.75 3.17-5.26 2.13-9.5 3.24-12.74 3.35-4.35.13-9.16-1.9-14.42-6.08-3.69-3.08-7.78-8.08-12.28-15-6.3-9.76-11.38-20.91-15.24-33.45-3.86-12.54-5.79-24.3-5.79-35.28 0-14.28 3.57-26.15 10.72-35.61 7.15-9.46 16.29-14.32 27.42-14.58 4.8.12 10.33 1.34 16.59 3.66 6.26 2.32 10.02 3.54 11.28 3.66 2.01-.33 6.07-1.74 12.18-4.23 6.11-2.49 11.66-3.62 16.65-3.39 12.77 1.07 22.84 5.98 30.21 14.74-11.13 6.75-16.58 16.03-16.36 27.84.22 9.25 3.86 16.99 10.92 23.23 7.06 6.24 15.42 9.77 25.08 10.6-2.12 6.53-4.78 13.06-7.98 19.59zM119.22 33.64c0-7.39 2.65-14.35 7.95-20.88 5.3-6.53 11.83-10.72 19.59-12.57.8 7.39-1.63 14.36-7.29 20.91-5.66 6.55-12.41 10.73-20.25 12.54z"/></svg>
                    <span>الدفع وحجز الضمان بـ Apple Pay</span>
                </button>
                <button onclick="executePayment('بطاقة مدى Mada')" class="w-full btn-glass font-medium py-3.5 rounded-2xl flex items-center justify-center gap-2">
                    <span>💳</span> <span>الدفع ببطاقة مدى / فيزا</span>
                </button>
                <button onclick="closePaymentModal()" class="w-full py-2.5 text-slate-500 text-xs">إلغاء</button>
            </div>
        </div>
    </div>

    <header class="border-b border-white/5 bg-black/60 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                </svg>
                <span class="text-lg font-black tracking-tight text-white uppercase">Watheeq</span>
            </a>
            <span class="text-xs bg-white/5 px-3 py-1.5 rounded-full border border-white/10 text-slate-300 font-mono">رقم الصفقة: {deal['id']}</span>
        </div>
    </header>

    <div class="bg-white/[0.02] border-b border-white/5 py-2 px-6 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
        <span>⏱️ مؤقت الاسترجاع التلقائي:</span>
        <span id="countdownTimer" class="text-white font-bold">{'09:59' if not is_pending else 'بانتظار سداد المشتري للضمان'}</span>
        <span>(تسترجع الأموال فورياً في حال عدم التسليم)</span>
    </div>

    <main class="max-w-6xl mx-auto px-6 py-8 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 w-full">
        <div class="lg:col-span-1 space-y-6">
            <div class="card-dark p-6 rounded-3xl">
                <div class="flex justify-between items-center mb-4">
                    <span class="text-[11px] px-2.5 py-1 rounded-full bg-white/5 text-slate-300 border border-white/10">{deal['category']}</span>
                    <span class="text-[11px] px-2.5 py-1 rounded-full {'bg-amber-500/20 text-amber-400' if is_pending else 'bg-emerald-500/20 text-emerald-400'} font-medium">{deal['status']}</span>
                </div>
                <h2 class="text-lg font-bold text-white mb-4">{deal['title']}</h2>
                
                <div class="border-t border-white/10 pt-4 space-y-2 text-xs font-mono">
                    <div class="flex justify-between text-slate-400"><span>مبلغ الصفقة الأساسي:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                    <div class="flex justify-between text-slate-400"><span>عمولة الوساطة المحسومة:</span><span class="text-slate-300">{deal['fee_amount']} ريال</span></div>
                    <div class="flex justify-between text-slate-400 border-t border-white/10 pt-2 text-sm"><span>الإجمالي المجمّد بالخزينة:</span><span class="text-emerald-400 font-bold">{deal['total_paid']:,} ريال</span></div>
                </div>

                <div class="border-t border-white/10 mt-4 pt-4 text-xs space-y-2 text-slate-400">
                    <div class="flex items-center justify-between"><span>👤 البائع:</span><span class="text-white">{deal['seller_name']}</span></div>
                    <div class="flex items-center justify-between"><span>👤 المشتري:</span><span class="text-white">{deal['buyer_name']}</span></div>
                </div>
            </div>

            <div class="card-dark p-6 rounded-3xl space-y-3">
                <h4 class="text-xs font-bold text-slate-400 mb-2">إجراءات الأمان</h4>
                {'<button onclick="openPaymentModal()" class="w-full btn-white font-bold py-3 rounded-2xl flex items-center justify-center gap-2 mb-2"><svg class="w-5 h-5 fill-current" viewBox="0 0 170 170"><path d="M150.37 130.25c-2.45 5.66-5.35 10.87-8.71 15.66-4.58 6.53-8.33 11.05-11.22 13.56-4.48 4.12-9.28 6.23-14.42 6.35-3.69 0-8.14-1.05-13.32-3.18-5.19-2.12-9.97-3.17-14.34-3.17-4.58 0-9.49 1.05-14.75 3.17-5.26 2.13-9.5 3.24-12.74 3.35-4.35.13-9.16-1.9-14.42-6.08-3.69-3.08-7.78-8.08-12.28-15-6.3-9.76-11.38-20.91-15.24-33.45-3.86-12.54-5.79-24.3-5.79-35.28 0-14.28 3.57-26.15 10.72-35.61 7.15-9.46 16.29-14.32 27.42-14.58 4.8.12 10.33 1.34 16.59 3.66 6.26 2.32 10.02 3.54 11.28 3.66 2.01-.33 6.07-1.74 12.18-4.23 6.11-2.49 11.66-3.62 16.65-3.39 12.77 1.07 22.84 5.98 30.21 14.74-11.13 6.75-16.58 16.03-16.36 27.84.22 9.25 3.86 16.99 10.92 23.23 7.06 6.24 15.42 9.77 25.08 10.6-2.12 6.53-4.78 13.06-7.98 19.59zM119.22 33.64c0-7.39 2.65-14.35 7.95-20.88 5.3-6.53 11.83-10.72 19.59-12.57.8 7.39-1.63 14.36-7.29 20.91-5.66 6.55-12.41 10.73-20.25 12.54z"/></svg> <span>إيداع وتجميد المبلغ والعمولة</span></button>' if is_pending else '<button onclick="confirmRelease()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-2xl transition">✅ تأكيد الفحص والاستلام (تحويل للبائع)</button>'}
                <button onclick="raiseDispute()" class="w-full bg-rose-500/10 border border-rose-500/30 text-rose-400 font-medium py-2.5 rounded-2xl transition text-xs">⚠️ رفع نزاع وتجميد فوري للوسيط</button>
                <button onclick="triggerRefund()" class="w-full btn-glass text-slate-300 py-2.5 rounded-2xl transition text-xs">↩️ طلب استرجاع فوري</button>
                <button onclick="copyDealLink()" class="w-full btn-glass text-slate-300 py-2.5 rounded-2xl transition text-xs">🔗 نسخ رابط الصفقة للطرف الآخر</button>
            </div>
        </div>

        <div class="lg:col-span-2 card-dark rounded-3xl flex flex-col h-[620px] overflow-hidden">
            <div class="p-4 border-b border-white/10 flex justify-between items-center bg-black/40">
                <div class="flex items-center gap-2">
                    <div class="w-2.5 h-2.5 bg-emerald-400 rounded-full animate-pulse"></div>
                    <span class="text-xs font-bold text-white uppercase tracking-wider">سجل المحادثة وتوثيق التسليم</span>
                </div>
                <span class="text-[11px] text-slate-500 font-mono">🔒 مشفرة ومحمية</span>
            </div>

            <div id="chatBox" class="flex-1 p-4 overflow-y-auto space-y-3 text-xs">
                {''.join([f'<div class="p-3 rounded-2xl {"bg-white/5 border border-white/10 text-slate-200" if "النظام" in m["sender"] or "الدفع" in m["sender"] else "bg-black/60 text-slate-300 border border-white/5"}"><div class="flex justify-between text-[10px] text-slate-500 mb-1"><span>{m["sender"]}</span><span>{m["time"]}</span></div><p class="leading-relaxed">{m["text"]}</p></div>' for m in deal['messages']])}
            </div>

            <div class="p-4 border-t border-white/10 bg-black/40 flex gap-2">
                <input id="chatInput" type="text" placeholder="اكتب بيانات التسليم أو الاستفسار هنا..." class="flex-1 bg-black/60 border border-white/10 rounded-2xl px-4 py-2.5 text-xs text-white focus:border-white/40 outline-none" onkeydown="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()" class="btn-white font-bold px-6 py-2.5 rounded-2xl text-xs">إرسال</button>
            </div>
        </div>
    </main>

    <script>
        const dealId = "{deal['id']}";
        const isPending = {'true' if is_pending else 'false'};
        if(!isPending) {{
            let timeLeft = 600;
            const timerElem = document.getElementById('countdownTimer');
            setInterval(() => {{
                if(timeLeft <= 0) return;
                timeLeft--;
                const mins = Math.floor(timeLeft / 60).toString().padStart(2, '0');
                const secs = (timeLeft % 60).toString().padStart(2, '0');
                timerElem.innerText = mins + ':' + secs;
            }}, 1000);
        }}
        function openPaymentModal() {{ document.getElementById('paymentModal').classList.remove('hidden'); document.getElementById('paymentModal').classList.add('flex'); }}
        function closePaymentModal() {{ document.getElementById('paymentModal').classList.add('hidden'); document.getElementById('paymentModal').classList.remove('flex'); }}
        async function executePayment(method) {{
            const res = await fetch('/api/deals/' + dealId + '/pay', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{payment_method: method}})
            }});
            if(res.ok) {{ alert('✅ تم إيداع وتجميد إجمالي المبلغ والعمولة في خزينة وثيق بنجاح عبر ' + method); location.reload(); }}
        }}
        function copyDealLink() {{
            navigator.clipboard.writeText(window.location.href);
            alert('تم نسخ رابط الصفقة بنجاح!');
        }}
        async function confirmRelease() {{
            if(!confirm('هل تأكدت من استلام السلعة/الخدمة وفحصها 100%؟ سيتم تحويل صافي المبلغ للبائع فوراً بعد خصم العمولة.')) return;
            const res = await fetch('/api/deals/' + dealId + '/release', {{method: 'POST'}});
            if(res.ok) location.reload();
        }}
        async function raiseDispute() {{
            if(!confirm('هل تريد تجميد الصفقة وتحويلها لمراجعة الوسيط؟')) return;
            const res = await fetch('/api/deals/' + dealId + '/dispute', {{method: 'POST'}});
            if(res.ok) location.reload();
        }}
        async function triggerRefund() {{
            if(!confirm('هل انتهت المهلة ولم يتم تسليمك؟ سيتم استرجاع كامل المبلغ لحسابك.')) return;
            const res = await fetch('/api/deals/' + dealId + '/refund', {{method: 'POST'}});
            if(res.ok) location.reload();
        }}
        async function sendMessage() {{
            const input = document.getElementById('chatInput');
            const text = input.value.trim();
            if(!text) return;
            const res = await fetch('/api/deals/' + dealId + '/chat', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{sender: 'المستخدم', text: text}})
            }});
            if(res.ok) {{ input.value = ''; location.reload(); }}
        }}
    </script>
</body>
</html>"""
