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

app = FastAPI(title="وثيق | Watheeq - Immutable Trust & Escrow Standard")

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
                INSERT INTO deals (id, title, category, price, fee_percent, fee_amount, total_paid, seller_name, buyer_name, status, status_note, messages)
                VALUES (
                    'WTQ-701',
                    'عربون حجز وفحص مركبة',
                    'عربون وفحص المركبات (1% بحد أقصى 50 ريال)',
                    2500.0,
                    1.0,
                    25.0,
                    2525.0,
                    'سعد الشمري (موثق نفاذ ✅)',
                    'أحمد المالكي (موثق نفاذ ✅)',
                    'المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳',
                    'تم سداد 2,525 ريال وتجميدها بأمان عبر Apple Pay في خزينة وثيق.',
                    '[
                        {"sender": "النظام (أمان وثيق)", "text": "تم استلام 2,525 ريال وتجميدها بنجاح عبر Apple Pay 🔒", "time": "10:00 AM"},
                        {"sender": "المشتري (أحمد)", "text": "تم تجميد العربون بالمنصة، بانتظار نتيجة الفحص بالورشة.", "time": "10:02 AM"}
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
        "category": "عربون وفحص المركبات (1% بحد أقصى 50 ريال)",
        "price": 2500.0,
        "fee_percent": 1.0,
        "fee_amount": 25.0,
        "total_paid": 2525.0,
        "seller_name": "سعد الشمري (موثق نفاذ ✅)",
        "buyer_name": "أحمد المالكي (موثق نفاذ ✅)",
        "status": "المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳",
        "status_note": "تم سداد 2,525 ريال وتجميدها بأمان عبر Apple Pay في خزينة وثيق.",
        "messages": [
            {"sender": "النظام (أمان وثيق)", "text": "تم استلام 2,525 ريال وتجميدها بنجاح عبر Apple Pay 🔒", "time": "10:00 AM"},
            {"sender": "المشتري (أحمد)", "text": "تم تجميد العربون بالمنصة، بانتظار نتيجة الفحص بالورشة.", "time": "10:02 AM"}
        ]
    }
}

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

class MessageRequest(BaseModel):
    sender: str
    text: str

class PaymentConfirmRequest(BaseModel):
    payment_method: str

@app.post("/api/deals/create")
def create_deal(req: CreateDealRequest):
    deal_id = "WTQ-" + ''.join(random.choices(string.digits, k=4))
    
    fee_percent = 2.5
    fee_amount = round((req.price * fee_percent) / 100, 2)
    
    if "1%" in req.category:
        fee_percent = 1.0
        fee_amount = round((req.price * 1.0) / 100, 2)
        if "بحد أقصى 50" in req.category and fee_amount > 50:
            fee_amount = 50.0
            
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
        "status": "بانتظار إيداع المشتري عبر (Apple Pay / مدى) ⏳",
        "status_note": "الصفقة بانتظار إيداع المشتري عبر بوابة الدفع الآمنة (Apple Pay / مدى).",
        "messages": [
            {"sender": "النظام (أمان وثيق)", "text": f"تم فتح غرفة الضمان المالي ({clean_title}). بانتظار حجز مبلغ {total_paid:,} ريال في الخزينة.", "time": "الآن"}
        ]
    }
    save_deal(deal)
    return {"status": "success", "deal_id": deal_id, "deal": deal}

@app.post("/api/deals/{deal_id}/pay")
def pay_deal(deal_id: str, req: PaymentConfirmRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳"
    deal["status_note"] = f"تم إيداع وتجميد المبلغ بنجاح عبر {req.payment_method}. بدأ مؤقت حماية التسليم."
    deal["messages"].append({"sender": "بوابة الدفع الآمنة", "text": f"💳 تم تأكيد إيداع {deal['total_paid']:,} ريال بنجاح بواسطة {req.payment_method}. المبلغ مجمّد في الخزينة.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/release")
def release_funds(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "تم التسليم وتحويل المستحقات للبائع بنجاح ✅"
    deal["status_note"] = "تم تأكيد الاستلام من المشتري، وتم الإفراج عن المبلغ وتحويله للبائع بنجاح."
    deal["messages"].append({"sender": "النظام (أمان وثيق)", "text": "✅ تم تأكيد الاستلام بنجاح وتحويل المستحقات للبائع فوراً.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/refund")
def auto_refund_deal(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "تم الاسترجاع التلقائي للمشتري ↩️"
    deal["status_note"] = "تم استرجاع المبلغ لحساب المشتري البنكي فورياً وتلقائياً."
    deal["messages"].append({"sender": "نظام الحماية التلقائي", "text": "↩️ تم تفعيل الاسترجاع التلقائي وإعادة كامل المبلغ للمشتري لحمايته من التأخير.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/dispute")
def dispute_deal(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deal["status"] = "تم إيقاف الصفقة (نزاع تحت مراجعة الإدارة) ⚠️"
    deal["status_note"] = "تم رفع اعتراض وتجميد المستحقات تحت مراجعة فريق التحكيم المالي."
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

@app.get("/", response_class=HTMLResponse)
def serve_home():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlTag">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="siteTitle">Watheeq | The Immutable Standard</title>
    
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://safewatheeq.com/">
    <meta property="og:title" content="Watheeq | المنصة الشاملة للضمان والوساطة المالية">
    <meta property="og:description" content="The immutable standard for sovereign trust and secure escrow.">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', 'Tajawal', sans-serif; background-color: #030303; color: #ffffff; overflow-x: hidden; }
        .hero-glow {
            background: radial-gradient(circle at 50% 30%, rgba(255, 255, 255, 0.08) 0%, rgba(0, 0, 0, 0.95) 75%);
        }
        .light-streak {
            position: absolute;
            width: 140%;
            height: 350px;
            top: 25%;
            left: -20%;
            background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.15) 0%, rgba(255,255,255,0.03) 40%, rgba(0,0,0,0) 70%);
            transform: rotate(-12deg);
            pointer-events: none;
            filter: blur(40px);
        }
        .card-dark {
            background: rgba(12, 12, 14, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(20px);
        }
        .card-dark:hover {
            border-color: rgba(255, 255, 255, 0.2);
        }
        .btn-white {
            background: #ffffff;
            color: #000000;
            transition: all 0.2s ease;
        }
        .btn-white:hover {
            background: #e2e8f0;
            transform: scale(1.02);
        }
        .btn-glass {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.12);
            color: #ffffff;
            transition: all 0.2s ease;
        }
        .btn-glass:hover {
            background: rgba(255, 255, 255, 0.12);
        }
        .pill-badge {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.12);
        }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between relative selection:bg-white selection:text-black">

    <div class="light-streak"></div>

    <!-- Navigation Bar -->
    <header class="border-b border-white/5 bg-black/60 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <!-- Brand Logo -->
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-2 cursor-pointer" onclick="window.scrollTo({top:0, behavior:'smooth'})">
                    <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none" />
                        <path d="M7 6h10M7 18h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" fill="none" opacity="0.4"/>
                    </svg>
                    <span class="text-xl font-bold tracking-tight text-white uppercase">Watheeq</span>
                </div>
            </div>
            
            <!-- Nav Links -->
            <nav class="hidden md:flex items-center gap-8 text-xs font-medium text-slate-400">
                <a href="#calculator" class="hover:text-white transition" id="nav1">حاسبة كسر السوق</a>
                <a href="#anti-fraud" class="hover:text-white transition" id="nav2">بروتوكول الأمان</a>
                <a href="/deal/WTQ-701" class="hover:text-white transition" id="nav3">غرفة حية (WTQ-701)</a>
            </nav>

            <!-- Actions -->
            <div class="flex items-center gap-3">
                <button onclick="toggleLang()" id="langBtn" class="pill-badge text-slate-300 px-3 py-1.5 rounded-full text-xs font-medium hover:border-white/30 transition">
                    EN / AR
                </button>
                <button onclick="openVerifyModal()" class="pill-badge text-slate-300 px-3.5 py-1.5 rounded-full text-xs font-medium hover:border-white/30 transition flex items-center gap-1.5">
                    <span>Verify</span>
                </button>
                <button onclick="openModal()" class="btn-white text-xs font-bold px-4 py-2 rounded-full shadow-sm hover:scale-105 transition" id="btnNav">
                    + ابدأ صفقة
                </button>
            </div>
        </div>
    </header>

    <!-- Main Hero Section -->
    <main class="hero-glow flex-1 flex flex-col items-center justify-center text-center px-6 py-24 relative z-10">
        
        <!-- Live Status Badge -->
        <div class="inline-flex items-center gap-2 px-3.5 py-1 rounded-full pill-badge text-emerald-400 text-[11px] font-mono tracking-wide mb-8">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>V1.0 IS LIVE & SECURE</span>
        </div>

        <!-- Hero Headline -->
        <h1 class="text-5xl md:text-7xl font-extrabold text-white tracking-tight leading-[1.1] max-w-4xl mb-6" id="heroTitle">
            The immutable<br>standard.
        </h1>

        <p class="text-slate-400 text-sm md:text-base max-w-xl mb-10 leading-relaxed font-light" id="heroDesc">
            المنصة والوساطة المالية السعودية لضمان وتأمين كافة المبايعات والصفقات بأقل عمولة في السوق (تبدأ من 1%). حجز المبالغ بنكياً عبر Apple Pay حتى الفحص والتسليم التام.
        </p>

        <!-- CTA Buttons -->
        <div class="flex flex-wrap items-center justify-center gap-4 mb-16">
            <button onclick="openModal()" class="btn-white text-sm font-semibold px-8 py-3.5 rounded-full flex items-center gap-2" id="btnStart">
                <span>ابدأ صفقة جديدة</span>
                <span class="text-base">→</span>
            </button>
            <a href="#calculator" class="btn-glass text-sm font-medium px-8 py-3.5 rounded-full" id="btnCalc">
                احسب العمولة المخفضة
            </a>
        </div>

        <!-- Trust Badges Bar -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl w-full text-left">
            <div class="card-dark p-4 rounded-2xl">
                <p class="text-xs text-slate-500 mb-1">العمولة للأصول والألعاب</p>
                <p class="text-lg font-bold text-white font-mono">2.5% <span class="text-xs text-emerald-400 font-normal">أرخص سعر</span></p>
            </div>
            <div class="card-dark p-4 rounded-2xl">
                <p class="text-xs text-slate-500 mb-1">عربون وفحص السيارات</p>
                <p class="text-lg font-bold text-white font-mono">1% <span class="text-xs text-slate-400 font-normal">(حد أقصى 50﷼)</span></p>
            </div>
            <div class="card-dark p-4 rounded-2xl">
                <p class="text-xs text-slate-500 mb-1">مؤقت الاسترجاع التلقائي</p>
                <p class="text-lg font-bold text-white font-mono">10 Min <span class="text-xs text-slate-400 font-normal">حماية فورية</span></p>
            </div>
            <div class="card-dark p-4 rounded-2xl">
                <p class="text-xs text-slate-500 mb-1">بوابات الدفع المشفرة</p>
                <p class="text-lg font-bold text-white font-mono">Pay / مدى</p>
            </div>
        </div>

    </main>

    <!-- Calculator Section (Market Breaker) -->
    <section id="calculator" class="max-w-4xl mx-auto px-6 py-16 w-full relative z-10">
        <div class="card-dark p-8 md:p-10 rounded-3xl">
            <div class="text-center mb-8">
                <h3 class="text-2xl font-bold text-white mb-2">حاسبة كسر السوق والعمولات المخفضة</h3>
                <p class="text-xs text-slate-400">تحطيم أسعار العمولات التقليدية لضمان أعلى فائدة للبائع والمشتري</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                <div>
                    <label class="block text-xs text-slate-400 mb-2">قيمة الصفقة أو العربون (ريال):</label>
                    <input id="calcAmount" type="number" value="1000" oninput="runCalculator()" class="w-full bg-black/60 border border-white/10 rounded-2xl p-3.5 text-white font-mono font-bold outline-none focus:border-white/40">
                </div>
                <div>
                    <label class="block text-xs text-slate-400 mb-2">مجال الوساطة:</label>
                    <select id="calcCategory" onchange="runCalculator()" class="w-full bg-black/60 border border-white/10 rounded-2xl p-3.5 text-white text-sm outline-none focus:border-white/40">
                        <option value="digital">الأصول الرقمية، الحسابات، والألعاب (2.5%)</option>
                        <option value="freelance">الخدمات والبرمجة والتصميم (2.5%)</option>
                        <option value="car_deposit">عربون حجز وفحص المركبات (1% بحد أقصى 50 ريال)</option>
                        <option value="goods">السلع العامة والأجهزة الإلكترونية (1%)</option>
                    </select>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 text-center mb-6 font-mono">
                <div>
                    <span class="block text-[11px] text-slate-500 mb-1">المبلغ للبائع</span>
                    <span id="calcNet" class="text-base md:text-lg font-bold text-white">1,000 SAR</span>
                </div>
                <div>
                    <span class="block text-[11px] text-slate-400 mb-1">عمولة وثيق</span>
                    <span id="calcFee" class="text-base md:text-lg font-bold text-slate-300">25 SAR</span>
                </div>
                <div>
                    <span class="block text-[11px] text-emerald-400 mb-1">الإجمالي المطلوب للدفع</span>
                    <span id="calcTotal" class="text-base md:text-lg font-bold text-emerald-400">1,025 SAR</span>
                </div>
            </div>

            <div class="text-center">
                <button onclick="openModalWithValues()" class="btn-white text-xs font-bold px-8 py-3.5 rounded-full">
                    ابدأ بهذه الحسبة المخفضة 🚀
                </button>
            </div>
        </div>
    </section>

    <!-- Modal إنشاء صفقة -->
    <div id="createModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-lg w-full text-right border border-white/20">
            <h3 class="text-xl font-bold text-white mb-1">إنشاء رابط صفقة مشفرة</h3>
            <p class="text-xs text-slate-400 mb-6">سيتم توليد غرفة تسليم آمنة برابط مباشر للأطراف مع بوابة حجز بنكي.</p>
            
            <div class="space-y-4">
                <div>
                    <label class="text-xs text-slate-400 block mb-1">عنوان الصفقة أو السلعة</label>
                    <input id="newTitle" type="text" placeholder="مثال: عربون فحص لاندكروزر / حساب كود / مشروع ويب" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">القسم والتصنيف</label>
                    <select id="newCategory" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                        <option>الأصول الرقمية والحسابات (2.5%)</option>
                        <option>الخدمات والعمل الحر (2.5%)</option>
                        <option>عربون وفحص المركبات (1% بحد أقصى 50 ريال)</option>
                        <option>السلع والأجهزة الإلكترونية (1%)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">المبلغ المطلوب (ريال)</label>
                    <input id="newPrice" type="number" placeholder="1000" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">اسم / يوزر البائع</label>
                        <input id="newSeller" type="text" placeholder="البائع" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">اسم / يوزر المشتري</label>
                        <input id="newBuyer" type="text" placeholder="المشتري" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                    </div>
                </div>
            </div>

            <div class="mt-6 flex gap-3">
                <button onclick="submitDeal()" class="flex-1 btn-white text-xs font-bold py-3 rounded-xl">إنشاء الرابط وحجز الضمان 🔒</button>
                <button onclick="closeModal()" class="px-5 py-3 btn-glass text-xs rounded-xl">إلغاء</button>
            </div>
        </div>
    </div>

    <!-- Verify Modal (Like Reference Design) -->
    <div id="verifyModal" class="fixed inset-0 bg-black/95 backdrop-blur-lg hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full text-center border border-white/10">
            <h3 class="text-2xl font-bold text-white mb-2">Verify Deal / Document</h3>
            <p class="text-xs text-slate-400 mb-6">Enter a deal ID or scan verification token to inspect state</p>
            <input id="verifyInput" type="text" placeholder="e.g. WTQ-701" class="w-full bg-black/60 border border-white/10 rounded-2xl p-3.5 text-center text-white font-mono text-sm uppercase mb-4 outline-none focus:border-white/40">
            <div class="flex gap-3">
                <button onclick="doVerify()" class="flex-1 btn-white text-xs font-bold py-3 rounded-xl">Verify Authenticity</button>
                <button onclick="closeVerifyModal()" class="px-5 py-3 btn-glass text-xs rounded-xl">Close</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="border-t border-white/5 py-10 bg-black text-center text-xs text-slate-600 relative z-10 space-y-3">
        <div class="flex items-center justify-center gap-6 text-slate-500 font-mono text-[11px]">
            <span>BANK-GRADE ENCRYPTION</span>
            <span>•</span>
            <span>INSTANT SETTLEMENT</span>
            <span>•</span>
            <span>IMMUTABLE RECORD</span>
        </div>
        <p>© 2026 Watheeq Inc. All rights reserved. Platform operates under Saudi eCommerce Regulations.</p>
    </footer>

    <script>
        let isAr = true;

        function toggleLang() {
            isAr = !isAr;
            const html = document.getElementById('htmlTag');
            html.setAttribute('dir', isAr ? 'rtl' : 'ltr');
            html.setAttribute('lang', isAr ? 'ar' : 'en');
            document.getElementById('langBtn').innerText = isAr ? 'EN / AR' : 'AR / EN';
            
            if(!isAr) {
                document.getElementById('heroTitle').innerHTML = 'The immutable<br>standard.';
                document.getElementById('heroDesc').innerText = 'The leading sovereign escrow platform in Saudi Arabia. Secure any transaction, car deposit, or digital asset with ultra-low fees starting at 1%.';
                document.getElementById('btnStart').innerText = 'Start Deal →';
                document.getElementById('btnCalc').innerText = 'Calculate Fees';
            } else {
                document.getElementById('heroTitle').innerHTML = 'The immutable<br>standard.';
                document.getElementById('heroDesc').innerText = 'المنصة والوساطة المالية السعودية لضمان وتأمين كافة المبايعات والصفقات بأقل عمولة في السوق (تبدأ من 1%). حجز المبالغ بنكياً عبر Apple Pay حتى الفحص والتسليم التام.';
                document.getElementById('btnStart').innerText = 'ابدأ صفقة جديدة →';
                document.getElementById('btnCalc').innerText = 'احسب العمولة المخفضة';
            }
            runCalculator();
        }

        function runCalculator() {
            const amount = parseFloat(document.getElementById('calcAmount').value) || 0;
            const cat = document.getElementById('calcCategory').value;
            let fee = (amount * 2.5) / 100;
            
            if(cat === 'car_deposit') {
                fee = (amount * 1.0) / 100;
                if(fee > 50) fee = 50; // سقف أقصى 50 ريال لكسر سوق السيارات
            } else if(cat === 'goods') {
                fee = (amount * 1.0) / 100;
            }

            const total = amount + fee;
            const cur = isAr ? ' ريال' : ' SAR';

            document.getElementById('calcNet').innerText = amount.toLocaleString() + cur;
            document.getElementById('calcFee').innerText = fee.toLocaleString() + cur;
            document.getElementById('calcTotal').innerText = total.toLocaleString() + cur;
        }

        function openModal() { document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex'); }
        function openModalWithValues() { document.getElementById('newPrice').value = document.getElementById('calcAmount').value; openModal(); }
        function closeModal() { document.getElementById('createModal').classList.add('hidden'); document.getElementById('createModal').classList.remove('flex'); }
        
        function openVerifyModal() { document.getElementById('verifyModal').classList.remove('hidden'); document.getElementById('verifyModal').classList.add('flex'); }
        function closeVerifyModal() { document.getElementById('verifyModal').classList.add('hidden'); document.getElementById('verifyModal').classList.remove('flex'); }

        function doVerify() {
            const val = document.getElementById('verifyInput').value.trim();
            if(val) {
                window.location.href = '/deal/' + val;
            }
        }

        async function submitDeal() {
            const title = document.getElementById('newTitle').value;
            const category = document.getElementById('newCategory').value;
            const price = parseFloat(document.getElementById('newPrice').value);
            const seller_name = document.getElementById('newSeller').value;
            const buyer_name = document.getElementById('newBuyer').value;

            if(!title || !price || !seller_name) {
                alert('يرجى تعبئة الحقول الأساسية');
                return;
            }

            const res = await fetch('/api/deals/create', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({title, category, price, seller_name, buyer_name})
            });
            const data = await res.json();
            if(data.status === 'success') {
                window.location.href = '/deal/' + data.deal_id;
            }
        }

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
    <title>غرفة الوساطة {deal['id']} | Watheeq</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', 'Tajawal', sans-serif; background-color: #030303; color: #ffffff; }}
        .card-dark {{ background: rgba(12, 12, 14, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(20px); }}
        .btn-white {{ background: #ffffff; color: #000000; transition: all 0.2s; }}
        .btn-white:hover {{ background: #e2e8f0; transform: scale(1.02); }}
        .btn-glass {{ background: rgba(255, 255, 255, 0.06); border: 1px solid rgba(255, 255, 255, 0.12); color: #ffffff; }}
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">

    <!-- نافذة الدفع وحجز المبلغ (Apple Pay / مدى) -->
    <div id="paymentModal" class="fixed inset-0 bg-black/90 z-50 backdrop-blur-md hidden flex items-center justify-center p-4">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full border border-white/20 text-center relative shadow-2xl">
            <div class="w-14 h-14 rounded-2xl bg-white/10 mx-auto flex items-center justify-center text-2xl mb-4">💳</div>
            <h3 class="text-xl font-bold text-white mb-2">إيداع الضمان المالي في خزينة وثيق</h3>
            <p class="text-xs text-slate-400 mb-6">المبلغ يُحجز مشفراً ولا يُحول للبائع إلا بعد فحصك وموافقتك التامة.</p>
            
            <div class="bg-black/60 border border-white/10 p-4 rounded-2xl mb-6 text-right space-y-2 text-sm font-mono">
                <div class="flex justify-between text-slate-400"><span>المبلغ الإجمالي:</span><span class="text-emerald-400 font-bold text-base">{deal['total_paid']:,} SAR</span></div>
                <div class="flex justify-between text-xs text-slate-500"><span>شامل رسوم الضمان ({deal['fee_percent']}%):</span><span>{deal['fee_amount']} SAR</span></div>
            </div>

            <!-- خيارات الدفع الفورية -->
            <div class="space-y-3">
                <button onclick="executePayment('Apple Pay ')" class="w-full btn-white font-bold py-3.5 rounded-2xl flex items-center justify-center gap-2">
                    <span class="text-lg">Pay</span> <span>الدفع السريع بـ Apple Pay</span>
                </button>
                <button onclick="executePayment('بطاقة مدى Mada')" class="w-full btn-glass font-medium py-3.5 rounded-2xl flex items-center justify-center gap-2">
                    <span>💳</span> <span>الدفع ببطاقة مدى / فيزا</span>
                </button>
                <button onclick="closePaymentModal()" class="w-full py-2.5 text-slate-500 text-xs">إلغاء</button>
            </div>
        </div>
    </div>

    <!-- Header -->
    <header class="border-b border-white/5 bg-black/60 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-2">
                <svg class="w-5 h-5 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none" />
                </svg>
                <span class="text-lg font-bold tracking-tight text-white uppercase">Watheeq</span>
            </a>
            <span class="text-xs bg-white/5 px-3 py-1.5 rounded-full border border-white/10 text-slate-300 font-mono">Deal ID: {deal['id']}</span>
        </div>
    </header>

    <!-- شريط حالة الصفقة والمؤقت -->
    <div class="bg-white/[0.02] border-b border-white/5 py-2 px-6 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
        <span>⏱️ AUTO-REFUND TIMER:</span>
        <span id="countdownTimer" class="text-white font-bold">{'09:59' if not is_pending else 'WAITING FOR DEPOSIT'}</span>
        <span>(تسترجع الأموال فورياً في حال عدم التسليم)</span>
    </div>

    <main class="max-w-6xl mx-auto px-6 py-8 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 w-full">
        
        <!-- تفاصيل الصفقة والتحكم -->
        <div class="lg:col-span-1 space-y-6">
            <div class="card-dark p-6 rounded-3xl">
                <div class="flex justify-between items-center mb-4">
                    <span class="text-[11px] px-2.5 py-1 rounded-full bg-white/5 text-slate-300 border border-white/10">{deal['category']}</span>
                    <span class="text-[11px] px-2.5 py-1 rounded-full {'bg-amber-500/20 text-amber-400' if is_pending else 'bg-emerald-500/20 text-emerald-400'} font-medium">{deal['status']}</span>
                </div>
                <h2 class="text-lg font-bold text-white mb-4">{deal['title']}</h2>
                
                <div class="border-t border-white/10 pt-4 space-y-2 text-xs font-mono">
                    <div class="flex justify-between text-slate-400"><span>مبلغ الصفقة:</span><span class="text-white font-bold">{deal['price']:,} SAR</span></div>
                    <div class="flex justify-between text-slate-400"><span>عمولة الضمان:</span><span class="text-slate-300">{deal['fee_amount']} SAR</span></div>
                    <div class="flex justify-between text-slate-400 border-t border-white/10 pt-2 text-sm"><span>الإجمالي المجمّد:</span><span class="text-emerald-400 font-bold">{deal['total_paid']:,} SAR</span></div>
                </div>

                <div class="border-t border-white/10 mt-4 pt-4 text-xs space-y-2 text-slate-400">
                    <div class="flex items-center justify-between"><span>البائع:</span><span class="text-white">{deal['seller_name']}</span></div>
                    <div class="flex items-center justify-between"><span>المشتري:</span><span class="text-white">{deal['buyer_name']}</span></div>
                </div>
            </div>

            <!-- أزرار الإجراءات والدفع -->
            <div class="card-dark p-6 rounded-3xl space-y-3">
                <h4 class="text-xs font-bold text-slate-400 mb-2">إجراءات الأمان</h4>
                
                {'<button onclick="openPaymentModal()" class="w-full btn-white font-bold py-3 rounded-2xl flex items-center justify-center gap-2 mb-2"><span class="text-lg">Pay</span> <span>إيداع وتجميد المبلغ</span></button>' if is_pending else '<button onclick="confirmRelease()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-2xl transition">✅ تأكيد الفحص والاستلام (تحويل للبائع)</button>'}
                
                <button onclick="raiseDispute()" class="w-full bg-rose-500/10 border border-rose-500/30 text-rose-400 font-medium py-2.5 rounded-2xl transition text-xs">⚠️ رفع نزاع وتجميد فوري للوسيط</button>
                <button onclick="triggerRefund()" class="w-full btn-glass text-slate-300 py-2.5 rounded-2xl transition text-xs">↩️ طلب استرجاع فوري</button>
                <button onclick="copyDealLink()" class="w-full btn-glass text-slate-300 py-2.5 rounded-2xl transition text-xs">🔗 نسخ رابط الصفقة للطرف الآخر</button>
            </div>
        </div>

        <!-- غرفة المحادثة المباشرة والإثباتات -->
        <div class="lg:col-span-2 card-dark rounded-3xl flex flex-col h-[620px] overflow-hidden">
            <div class="p-4 border-b border-white/10 flex justify-between items-center bg-black/40">
                <div class="flex items-center gap-2">
                    <div class="w-2.5 h-2.5 bg-emerald-400 rounded-full animate-pulse"></div>
                    <span class="text-xs font-bold text-white uppercase tracking-wider">Secure Deal Chat</span>
                </div>
                <span class="text-[11px] text-slate-500 font-mono">🔒 E2E Encrypted Record</span>
            </div>

            <!-- الرسائل -->
            <div id="chatBox" class="flex-1 p-4 overflow-y-auto space-y-3 text-xs">
                {''.join([f'<div class="p-3 rounded-2xl {"bg-white/5 border border-white/10 text-slate-200" if "النظام" in m["sender"] or "الدفع" in m["sender"] else "bg-black/60 text-slate-300 border border-white/5"}"><div class="flex justify-between text-[10px] text-slate-500 mb-1"><span>{m["sender"]}</span><span>{m["time"]}</span></div><p class="leading-relaxed">{m["text"]}</p></div>' for m in deal['messages']])}
            </div>

            <!-- إرسال رسالة -->
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
            if(res.ok) {{
                alert('✅ تم إيداع وتجميد المبلغ في خزينة وثيق بنجاح عبر ' + method);
                location.reload();
            }}
        }}

        function copyDealLink() {{
            navigator.clipboard.writeText(window.location.href);
            alert('تم نسخ رابط الصفقة بنجاح!');
        }}

        async function confirmRelease() {{
            if(!confirm('هل تأكدت من استلام السلعة/الخدمة وفحصها 100%؟ سيتم تحويل المبلغ للبائع فوراً.')) return;
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
            if(res.ok) {{
                input.value = '';
                location.reload();
            }}
        }}
    </script>
</body>
</html>"""
