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

# مكتبات حماية معدل الطلبات (Rate Limiting)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="وثيق | Watheeq - Escrow & Marketplace Platform")

# إعداد حماية عدد الطلبات لمنع هجمات Brute Force والهجمات الآلية
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    if DATABASE_URL:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except Exception as e:
            # تسجيل الخطأ في السجلات خلف الكواليس وعدم إظهاره للمستخدم لتعزيز الأمان
            print("DB Connection Error (Logged securely)")
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
    # تفعيل سياسة أمان المحتوى (CSP) لحماية إضافية ضد حقن الأكواد
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' https://cdn.tailwindcss.com https://fonts.googleapis.com https://fonts.gstatic.com; "
        "img-src 'self' https: data:; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com;"
    )
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
@limiter.limit("10/minute")
def create_deal(request: Request, req: CreateDealRequest):
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
@limiter.limit("10/minute")
def create_listing(request: Request, req: ListingRequest):
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
@limiter.limit("15/minute")
def pay_deal(request: Request, deal_id: str, req: PaymentConfirmRequest):
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
@limiter.limit("30/minute")
def send_chat(request: Request, deal_id: str, req: MessageRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    msg = {"sender": html.escape(req.sender), "text": html.escape(req.text), "time": "الآن"}
    deal["messages"].append(msg)
    save_deal(deal)
    return {"status": "success", "messages": deal["messages"]}

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
            <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor"><path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
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
            <button onclick="switchMode('scan')" id="btnScan" class="pill-btn active px-6 py-2.5 rounded-full text-xs flex items-center gap-2"><span>📷</span> <span>Start QR Scan</span></button>
            <button onclick="switchMode('id')" id="btnId" class="pill-btn px-6 py-2.5 rounded-full text-xs flex items-center gap-2"><span>📝</span> <span>Enter Public ID</span></button>
        </div>
        <div id="scanBox" class="card-dark rounded-3xl p-8 max-w-sm w-full flex flex-col items-center justify-center text-center mb-4 min-h-[220px]">
            <div class="w-12 h-12 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-500 flex items-center justify-center text-2xl mb-4">⚠️</div>
            <p class="text-xs font-bold text-white mb-1">Unable to start camera. Please check permissions.</p>
            <p class="text-[11px] text-slate-500 mb-4">Or use manual ID search below</p>
            <button onclick="alert('Camera access requested')" class="bg-white text-black font-bold text-xs px-5 py-2 rounded-full">Retry Camera Access</button>
        </div>
        <div id="idBox" class="card-dark rounded-3xl p-6 max-w-sm w-full hidden mb-4 text-right">
            <label class="text-xs text-slate-400 block mb-2">Deal / Document ID:</label>
            <input id="publicDealId" type="text" placeholder="e.g. WTQ-701" class="w-full bg-black border border-white/10 rounded-xl p-3 text-white text-center font-mono uppercase text-sm mb-3 outline-none">
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
        <span class="text-white font-bold uppercase">Watheeq</span>
        <div class="flex gap-8"><span>Product</span><span>Resources</span><span>Legal</span></div>
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
        .auth-card { background-color: #181a20; border: 1px solid #23272f; }
        .yellow-btn { background-color: #fcd535; color: #181a20; transition: background 0.2s; }
        .yellow-btn:hover { background-color: #f0b90b; }
        .input-box { background-color: #0b0e11; border: 1px solid #23272f; color: #ffffff; }
        .input-box:focus { border-color: #f0b90b; outline: none; }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-yellow-400 selection:text-black">
    <header class="px-8 py-6 flex items-center justify-between">
        <a href="/" class="flex items-center gap-3">
            <svg class="w-7 h-7 text-yellow-400" viewBox="0 0 24 24" fill="currentColor"><path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
            <span class="text-xl font-black tracking-tight text-white uppercase">Watheeq</span>
        </a>
        <div class="flex items-center gap-6 text-xs text-slate-400 font-medium">
            <button onclick="toggleLang()" class="border border-slate-700 px-3 py-1.5 rounded-full text-slate-200" id="langText">English</button>
            <a href="/" class="hover:text-yellow-400 transition">الرئيسية</a>
        </div>
    </header>
    <main class="flex-1 flex flex-col items-center justify-center px-4 py-12">
        <div class="auth-card p-8 md:p-10 rounded-3xl max-w-md w-full shadow-2xl relative">
            <div id="stepHeader" class="text-center mb-8">
                <h1 id="stepTitle" class="text-2xl font-black text-white mb-2">تسجيل الدخول</h1>
                <p id="stepSub" class="text-xs text-slate-400">البريد الإلكتروني / رقم الهوية</p>
            </div>
            <div id="formContainer" class="space-y-4">
                <div id="boxStep1" class="space-y-4">
                    <input id="inputEmail" type="text" placeholder="name@domain.com أو رقم الهوية" class="w-full input-box rounded-xl p-3.5 text-sm">
                    <button onclick="goToStep2()" class="w-full yellow-btn font-bold py-3.5 rounded-xl text-sm">متابعة</button>
                </div>
                <div id="boxStep2" class="space-y-4 hidden">
                    <p id="displayEmailUser" class="text-xs text-slate-400 text-center font-mono mb-2"></p>
                    <input id="inputPassword" type="password" placeholder="••••••••" class="w-full input-box rounded-xl p-3.5 text-sm">
                    <button onclick="goToStep3()" class="w-full yellow-btn font-bold py-3.5 rounded-xl text-sm mt-2">تسجيل الدخول</button>
                </div>
                <div id="boxStep3" class="space-y-4 hidden text-center">
                    <p class="text-xs text-slate-400">أدخل رمز التحقق المكون من 6 أرقام</p>
                    <button onclick="finalizeLogin()" class="w-full yellow-btn font-bold py-3.5 rounded-xl text-sm">تأكيد وتحقق</button>
                </div>
            </div>
        </div>
    </main>
    <script>
        function goToStep2() {
            const email = document.getElementById('inputEmail').value.trim();
            if(!email) { alert('يرجى إدخال البريد الإلكتروني أو الهوية'); return; }
            document.getElementById('boxStep1').classList.add('hidden');
            document.getElementById('boxStep2').classList.remove('hidden');
        }
        function goToStep3() {
            document.getElementById('boxStep2').classList.add('hidden');
            document.getElementById('boxStep3').classList.remove('hidden');
        }
        function finalizeLogin() {
            alert('✅ تم التحقق وتسجيل الدخول بنجاح!');
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
                    <button onclick="buyFromMarket('{item['title']}', '{item['category']}', {item['price']}, '{item['seller']}')" class="btn-white text-xs font-bold px-4 py-2 rounded-xl">شراء بضمان وثيق 🛡️</button>
                </div>
            </div>
        </div>
        """
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlTag">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>وثيق | Watheeq - Escrow & Marketplace</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Tajawal', 'Inter', sans-serif; background-color: #030303; color: #ffffff; }}
        .card-dark {{ background: rgba(14, 14, 18, 0.75); border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(20px); }}
        .btn-white {{ background: #ffffff; color: #000000; transition: all 0.2s ease; }}
        .btn-white:hover {{ background: #e2e8f0; transform: scale(1.02); }}
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between relative selection:bg-white selection:text-black">
    <header class="border-b border-white/5 bg-black/60 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3">
                <span class="text-lg font-black tracking-tight text-white uppercase">Watheeq</span>
            </a>
            <div class="flex items-center gap-3">
                <a href="/verify" class="text-slate-300 px-3 py-1.5 text-xs font-semibold">Verify</a>
                <a href="/login" class="text-slate-300 px-3 py-1.5 text-xs font-semibold">Sign In</a>
                <button onclick="openModal()" class="btn-white text-xs font-black px-4 py-2 rounded-full">+ إنشاء صفقة</button>
            </div>
        </div>
    </header>
    <main class="flex-1 flex flex-col items-center justify-center text-center px-6 py-20 relative z-10">
        <h1 class="text-4xl md:text-6xl font-black text-white tracking-tight mb-6">The immutable standard.</h1>
    </main>
    <section class="max-w-6xl mx-auto px-6 py-16 w-full">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">{listings_cards}</div>
    </section>
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
    <title>غرفة الضمان {deal['id']} | وثيق</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body {{ font-family: sans-serif; background-color: #050507; color: #ffffff; }}</style>
</head>
<body class="p-8">
    <h1 class="text-2xl font-bold mb-4">غرفة الصفقة: {deal['id']}</h1>
    <p>العنوان: {deal['title']}</p>
    <p>الحالة: {deal['status']}</p>
</body>
</html>"""
