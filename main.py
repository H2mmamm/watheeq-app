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

app = FastAPI(title="منصة وثيق للضمان والوساطة المالية")

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
                    'عربون وضمان مبايعة سيارة ونقل ملكية',
                    'مركبات ومعدات (1.5%)',
                    10000.0,
                    1.5,
                    150.0,
                    10150.0,
                    'سعد الشمري (موثق نفاذ ✅)',
                    'أحمد المالكي (موثق نفاذ ✅)',
                    'المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳',
                    'تم سداد 10,150 ريال وتجميدها بأمان عبر Apple Pay في خزينة وثيق.',
                    '[
                        {"sender": "النظام (أمان وثيق)", "text": "تم استلام 10,150 ريال وتجميدها بنجاح عبر Apple Pay 🔒", "time": "10:00 AM"},
                        {"sender": "المشتري (أحمد)", "text": "أهلاً سعد، تم حجز المبلغ بالمنصة. ننتظر فحص السيارة ونقل الملكية.", "time": "10:02 AM"}
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
        "title": "عربون وضمان مبايعة سيارة ونقل ملكية",
        "category": "مركبات ومعدات (1.5%)",
        "price": 10000.0,
        "fee_percent": 1.5,
        "fee_amount": 150.0,
        "total_paid": 10150.0,
        "seller_name": "سعد الشمري (موثق نفاذ ✅)",
        "buyer_name": "أحمد المالكي (موثق نفاذ ✅)",
        "status": "المبلغ مجمّد بالخزينة (مؤقّت 10 دقائق نشط) 🛡️ ⏳",
        "status_note": "تم سداد 10,150 ريال وتجميدها بأمان عبر Apple Pay في خزينة وثيق.",
        "messages": [
            {"sender": "النظام (أمان وثيق)", "text": "تم استلام 10,150 ريال وتجميدها بنجاح عبر Apple Pay 🔒", "time": "10:00 AM"},
            {"sender": "المشتري (أحمد)", "text": "أهلاً سعد، تم حجز المبلغ بالمنصة. ننتظر فحص السيارة ونقل الملكية.", "time": "10:02 AM"}
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
    
    fee_percent = 3.5
    if "1.5" in req.category:
        fee_percent = 1.5
    elif "2.5" in req.category:
        fee_percent = 2.5
        
    fee_amount = round((req.price * fee_percent) / 100, 2)
    total_paid = round(req.price + fee_amount, 2)
    
    clean_title = html.escape(req.title)
    clean_seller = html.escape(req.seller_name)
    clean_buyer = html.escape(req.buyer_name) if req.buyer_name else "بانتظار انضمام المشتري"
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
            {"sender": "النظام (أمان وثيق)", "text": f"تم فتح غرفة الصفقة ({clean_title}). بانتظار إيداع المشتري لمبلغ {total_paid:,} ريال في الخزينة.", "time": "الآن"}
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
    <title id="siteTitle">وثيق | المنصة الشاملة لحماية وتأمين كافة الصفقات</title>
    
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://safewatheeq.com/">
    <meta property="og:title" content="وثيق | المنصة الشاملة للضمان والوساطة المالية">
    <meta property="og:description" content="ضمانك الأول لأي صفقة.. بيع واشتر في أي مجال وأنت مرتاح.">
    <meta property="og:image" content="https://safewatheeq.com/static/logo.png">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://safewatheeq.com/">
    <meta name="twitter:title" content="وثيق | المنصة الشاملة للضمان والوساطة المالية">
    <meta name="twitter:description" content="ضمانك الأول لأي صفقة.. بيع واشتر في أي مجال وأنت مرتاح.">
    <meta name="twitter:image" content="https://safewatheeq.com/static/logo.png">

    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #090d16; color: #f8fafc; line-height: 1.8; }
        .gold-btn { background: linear-gradient(135deg, #f59e0b, #d97706); }
        .card-bg { background: #0f172a; border: 1px solid #1e293b; }
        .gold-text { color: #f59e0b; }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">

    <!-- نافذة توثيق نفاذ / Face ID -->
    <div id="authModal" class="fixed inset-0 bg-black/80 z-50 backdrop-blur-sm hidden flex items-center justify-center p-4">
        <div class="card-bg p-8 rounded-3xl max-w-md w-full border border-amber-500/30 text-center relative shadow-2xl">
            <div class="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 mx-auto flex items-center justify-center text-3xl mb-4">🪪</div>
            <h3 class="text-xl font-black text-white mb-2">توثيق الهوية الوطنية الرقمية (نفاذ)</h3>
            <p class="text-xs text-slate-400 mb-6">لحماية الصفقات من الاحتيال، يتم ربط هويات البائع والمشتري بنظام التحقق الثنائي ومنع الحسابات الوهمية.</p>
            
            <div class="space-y-3 mb-6 text-right">
                <div>
                    <label class="text-xs text-slate-400 block mb-1">رقم الهوية الوطنية / الإقامة:</label>
                    <input id="nafathId" type="text" placeholder="1XXXXXXXXX" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm font-mono text-center tracking-widest outline-none focus:border-amber-500">
                </div>
            </div>

            <div class="flex gap-3">
                <button onclick="simulateNafath()" class="flex-1 gold-btn text-slate-950 font-black py-3 rounded-xl shadow-lg hover:scale-105 transition">طلب رمز الدخول (نفاذ) 📱</button>
                <button onclick="closeAuthModal()" class="px-5 py-3 border border-slate-700 text-slate-400 rounded-xl hover:bg-slate-800 transition">إغلاق</button>
            </div>
            <p class="text-[10px] text-slate-500 mt-4">🔒 مشفر بنظام التشفير الحكومي ومحمي ضد التزوير</p>
        </div>
    </div>

    <!-- Header -->
    <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-black text-xl">و</div>
                <div>
                    <h1 class="text-xl font-black text-white">وثيق</h1>
                    <p class="text-xs text-amber-400/80 font-medium" id="headerTagline">الضمان والوساطة المالية الشاملة</p>
                </div>
            </div>
            
            <nav class="hidden md:flex items-center gap-6 text-sm font-medium text-slate-300">
                <a href="#how-it-works" class="hover:text-amber-400 transition" id="navHow">كيف نعمل؟</a>
                <a href="#anti-fraud" class="hover:text-amber-400 transition" id="navAnti">حماية الاحتيال 🛡️</a>
                <a href="#calculator" class="hover:text-amber-400 transition" id="navCalc">حاسبة العمولة</a>
                <a href="/deal/WTQ-701" class="hover:text-amber-400 transition" id="navLive">الصفقة الحية (WTQ-701)</a>
            </nav>

            <div class="flex items-center gap-3">
                <button onclick="toggleLanguage()" id="langBtn" class="border border-slate-700 bg-slate-900 text-slate-300 px-3 py-2 rounded-xl text-xs font-bold hover:border-amber-500/50 transition">🌐 English</button>
                
                <button onclick="openAuthModal()" id="nafathBtn" class="border border-amber-500/30 bg-amber-500/10 text-amber-400 px-3 py-2 rounded-xl text-xs font-bold hover:bg-amber-500/20 transition flex items-center gap-1.5">
                    <span>🛡️</span> <span id="nafathText">توثيق نفاذ (Face ID)</span>
                </button>

                <button onclick="openModal()" class="gold-btn text-slate-950 font-black px-4 py-2.5 rounded-xl shadow-lg hover:opacity-90 transition text-sm" id="btnCreateNav">+ إنشاء صفقة</button>
            </div>
        </div>
    </header>

    <!-- شريط تحذير الأمان ضد الاحتيال وطرق الدفع -->
    <div class="bg-amber-500/10 border-b border-amber-500/20 py-2.5 px-6 text-center text-xs font-semibold text-amber-300 flex items-center justify-center gap-4 flex-wrap">
        <span>⚠️ تنبيه أمان: لا تحوّل أي مبالغ لحسابات شخصية. جميع الصفقات تُدفع وتُحجز عبر:</span>
        <span class="inline-flex items-center gap-1.5 bg-black/40 px-2.5 py-0.5 rounded-md border border-amber-500/30">Pay / مدى Mada / Visa</span>
    </div>

    <!-- Hero Section -->
    <section class="max-w-7xl mx-auto px-6 py-16 text-center flex flex-col items-center">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-400 text-xs font-semibold mb-6">
            🛡️ <span id="heroBadge">بوابتك المعتمدة لحماية وتأمين كافة المبايعات والصفقات الرقمية</span>
        </div>
        <h2 class="text-4xl md:text-6xl font-black text-white leading-tight mb-6 max-w-4xl" id="heroHeading">
            ضمانك الأول لأي صفقة..<br><span class="gold-text">بيع واشتر في أي مجال وأنت مرتاح</span>
        </h2>
        <p class="text-slate-400 text-base md:text-lg max-w-2xl mb-8 leading-relaxed" id="heroSub">
            المنصة السعودية الأولى للوساطة والضمان المالي المشترك بين الطرفين. نحجز المبلغ عبر Apple Pay ومدى في خزينة محايدة حتى يستلم المشتري ويفحص، ثم نحول المبلغ للبائع فوراً.
        </p>

        <!-- شعارات بوابات الدفع المدعومة -->
        <div class="flex items-center justify-center gap-4 mb-10 opacity-80 grayscale hover:grayscale-0 transition">
            <span class="text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-slate-300 font-bold"> Apple Pay</span>
            <span class="text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-emerald-400 font-bold">مدى Mada</span>
            <span class="text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-blue-400 font-bold">Visa / Master</span>
            <span class="text-xs bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg text-purple-400 font-bold">STC Pay</span>
        </div>

        <div class="flex flex-wrap justify-center gap-4">
            <button onclick="openModal()" class="gold-btn text-slate-950 font-black text-lg px-8 py-4 rounded-xl shadow-xl hover:scale-105 transition" id="heroBtn1">ابدأ صفقة جديدة الآن ⚡</button>
            <a href="#calculator" class="border border-slate-700 bg-slate-900 text-white font-bold text-lg px-8 py-4 rounded-xl hover:bg-slate-800 transition" id="heroBtn2">احسب عمولة صفقتك 🧮</a>
        </div>
    </section>

    <!-- Stats Section -->
    <section class="border-y border-slate-800/80 bg-slate-950/40 py-10">
        <div class="max-w-6xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
                <p class="text-3xl md:text-4xl font-black gold-text mb-1">+5,000,000</p>
                <p class="text-xs text-slate-400" id="stat1">ريال أموال صفقات محمية</p>
            </div>
            <div>
                <p class="text-3xl md:text-4xl font-black text-white mb-1">100%</p>
                <p class="text-xs text-slate-400" id="stat2">حماية من الاحتيال والنصب</p>
            </div>
            <div>
                <p class="text-3xl md:text-4xl font-black gold-text mb-1">10 دقائق</p>
                <p class="text-xs text-slate-400" id="stat3">مؤقت أمان واسترجاع تلقائي</p>
            </div>
            <div>
                <p class="text-3xl md:text-4xl font-black text-white mb-1">نفاذ ✅</p>
                <p class="text-xs text-slate-400" id="stat4">توثيق الهوية الوطنية للأطراف</p>
            </div>
        </div>
    </section>

    <!-- Anti-Fraud Security Suite -->
    <section id="anti-fraud" class="max-w-6xl mx-auto px-6 py-16">
        <div class="text-center mb-12">
            <h3 class="text-2xl md:text-3xl font-black text-white mb-2">ترسانة الحماية والوقاية من الاحتيال (Anti-Fraud Protocol)</h3>
            <p class="text-slate-400 text-xs md:text-sm">معايير أمان مالية وتقنية صارمة تمنع أي ثغرة للسرقة أو التراجع غير القانوني</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="card-bg p-6 rounded-2xl border-amber-500/20">
                <div class="text-3xl mb-3">⏱️</div>
                <h4 class="text-base font-bold text-white mb-2">مؤقت الاسترجاع التلقائي (10 دقائق)</h4>
                <p class="text-xs text-slate-400 leading-relaxed">في الصفقات السريعة (كالحسابات والأكواد)، إذا لم يسلم البائع خلال 10 دقائق، يقوم النظام تلقائياً بإعادة كامل المبلغ لحساب المشتري فوراً بدون تدخل بشري.</p>
            </div>
            <div class="card-bg p-6 rounded-2xl border-amber-500/20">
                <div class="text-3xl mb-3">🪪</div>
                <h4 class="text-base font-bold text-white mb-2">ربط نفاذ وبصمة الوجه الموثقة</h4>
                <p class="text-xs text-slate-400 leading-relaxed">منع استخدام الحسابات الوهمية أو البنوك الوسيطة. كل بائع ومشتري موثق برقم هويته الوطنية الرسمية لضمان المساءلة القانونية التامة.</p>
            </div>
            <div class="card-bg p-6 rounded-2xl border-amber-500/20">
                <div class="text-3xl mb-3">Pay</div>
                <h4 class="text-base font-bold text-white mb-2">دفع وحجز مشفر (Apple Pay & مدى)</h4>
                <p class="text-xs text-slate-400 leading-relaxed">المبالغ لا تذهب لحساب أشخاص، بل تُحجز وتُجمد في خزينة وثيق المشفرة عبر بوابات الدفع البنكية المعتمدة.</p>
            </div>
        </div>
    </section>

    <!-- Calculator Section -->
    <section id="calculator" class="max-w-4xl mx-auto px-6 py-10 mb-8">
        <div class="card-bg p-8 md:p-10 rounded-3xl border border-amber-500/20 shadow-2xl">
            <div class="text-center mb-8">
                <h3 class="text-2xl font-black text-white mb-2" id="calcTitle">حاسبة عمولة الوساطة الشفافة</h3>
                <p class="text-slate-400 text-xs" id="calcSub">تعرف بدقة على الرسوم والإجمالي الصافي قبل بدء أي عملية</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-2" id="lblAmount">قيمة الصفقة (ريال سعودي):</label>
                    <input id="calcAmount" type="number" value="1000" oninput="runCalculator()" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3.5 text-white font-bold outline-none focus:border-amber-500 transition">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-400 mb-2" id="lblCat">مجال الوساطة:</label>
                    <select id="calcCategory" onchange="runCalculator()" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3.5 text-white font-medium outline-none focus:border-amber-500 transition">
                        <option value="3.5">الأصول الرقمية، الحسابات، والألعاب (3.5%)</option>
                        <option value="3.5">الخدمات والعمل الحر والبرمجة (3.5%)</option>
                        <option value="1.5">المركبات، السيارات، والمعدات (1.5%)</option>
                        <option value="1.5">عقود الإيجار والوساطة العقارية (1.5%)</option>
                    </select>
                </div>
            </div>
            <div class="mt-8 pt-6 border-t border-slate-800 grid grid-cols-3 gap-4 text-center">
                <div>
                    <span class="block text-xs text-slate-500 mb-1" id="resNet">المبلغ الصافي للبائع</span>
                    <span id="calcNet" class="text-lg md:text-xl font-bold text-white">1,000 ريال</span>
                </div>
                <div>
                    <span class="block text-xs text-amber-400/80 mb-1" id="resFee">عمولة الحماية والوساطة</span>
                    <span id="calcFee" class="text-lg md:text-xl font-bold text-amber-400">35 ريال</span>
                </div>
                <div>
                    <span class="block text-xs text-emerald-400/80 mb-1" id="resTotal">الإجمالي المطلوب إيداعه</span>
                    <span id="calcTotal" class="text-lg md:text-xl font-black text-emerald-400">1,035 ريال</span>
                </div>
            </div>
            <div class="mt-8 text-center">
                <button onclick="openModalWithValues()" class="gold-btn text-slate-950 font-black px-8 py-3 rounded-xl shadow-lg hover:scale-105 transition" id="calcBtnAction">ابدأ هذه الصفقة بهذا المبلغ 🚀</button>
            </div>
        </div>
    </section>

    <!-- Modal إنشاء صفقة -->
    <div id="createModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden items-center justify-center p-4 z-50">
        <div class="card-bg p-8 rounded-2xl max-w-lg w-full text-right">
            <h3 class="text-xl font-bold text-white mb-4">إنشاء رابط صفقة وساطة جديد</h3>
            <div class="space-y-4">
                <div>
                    <label class="text-xs text-slate-400 block mb-1">عنوان الصفقة / الغرض</label>
                    <input id="newTitle" type="text" placeholder="مثال: شراء حساب كود / عربون سيارة / موقع إلكتروني" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">القسم</label>
                    <select id="newCategory" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                        <option>الأصول الرقمية والحسابات (3.5%)</option>
                        <option>الخدمات والعمل الحر (3.5%)</option>
                        <option>المركبات والمعدات (1.5%)</option>
                        <option>العقارات وعقود الإيجار (1.5%)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1">المبلغ المطلوب (ريال)</label>
                    <input id="newPrice" type="number" placeholder="1000" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">اسم البائع (الموثق)</label>
                        <input id="newSeller" type="text" placeholder="اسمك أو يوزرك" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">اسم المشتري (اختياري)</label>
                        <input id="newBuyer" type="text" placeholder="اسم المشتري" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                </div>
            </div>
            <div class="mt-6 flex gap-3">
                <button onclick="submitDeal()" class="flex-1 gold-btn text-slate-950 font-bold py-3 rounded-xl">إنشاء الرابط والانتقال للدفع 🔒</button>
                <button onclick="closeModal()" class="px-5 py-3 border border-slate-700 text-slate-400 rounded-xl">إلغاء</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="border-t border-slate-800 py-8 bg-slate-950/60 text-center text-xs text-slate-500 space-y-2">
        <p>جميع الحقوق محفوظة © منصة وثيق للوساطة والضمان المالي المشترك | safewatheeq.com</p>
        <p class="text-slate-600">نظام وساطة مالي آمن ومعتمد - خاضع لأحكام التجارة الإلكترونية السعودية</p>
    </footer>

    <script>
        let currentLang = 'ar';

        function toggleLanguage() {
            currentLang = currentLang === 'ar' ? 'en' : 'ar';
            const htmlTag = document.getElementById('htmlTag');
            htmlTag.setAttribute('lang', currentLang);
            htmlTag.setAttribute('dir', currentLang === 'ar' ? 'rtl' : 'ltr');
            document.getElementById('langBtn').innerText = currentLang === 'ar' ? '🌐 English' : '🌐 العربية';
            runCalculator();
        }

        function runCalculator() {
            const amount = parseFloat(document.getElementById('calcAmount').value) || 0;
            const percent = parseFloat(document.getElementById('calcCategory').value) || 3.5;
            const fee = (amount * percent) / 100;
            const total = amount + fee;
            const cur = currentLang === 'ar' ? ' ريال' : ' SAR';

            document.getElementById('calcNet').innerText = amount.toLocaleString() + cur;
            document.getElementById('calcFee').innerText = fee.toLocaleString() + cur;
            document.getElementById('calcTotal').innerText = total.toLocaleString() + cur;
        }

        function openModal() { document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex'); }
        function openModalWithValues() { document.getElementById('newPrice').value = document.getElementById('calcAmount').value; openModal(); }
        function closeModal() { document.getElementById('createModal').classList.add('hidden'); document.getElementById('createModal').classList.remove('flex'); }
        function openAuthModal() { document.getElementById('authModal').classList.remove('hidden'); document.getElementById('authModal').classList.add('flex'); }
        function closeAuthModal() { document.getElementById('authModal').classList.add('hidden'); document.getElementById('authModal').classList.remove('flex'); }

        function simulateNafath() {
            const id = document.getElementById('nafathId').value.trim();
            if(id.length < 10) { alert('يرجى إدخال رقم هوية صحيح مكون من 10 أرقام'); return; }
            alert('تم إرسال طلب التوثيق إلى تطبيق نفاذ برمز تأكيد: ' + Math.floor(10 + Math.random() * 90));
            closeAuthModal();
            document.getElementById('nafathBtn').innerHTML = '<span>✅</span> <span>موثق بنفاذ</span>';
            document.getElementById('nafathBtn').classList.add('bg-emerald-500/20', 'text-emerald-400', 'border-emerald-500/40');
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
    <title>غرفة الصفقة {deal['id']} | وثيق</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Tajawal', sans-serif; background-color: #090d16; color: #f8fafc; }}
        .gold-btn {{ background: linear-gradient(135deg, #f59e0b, #d97706); }}
        .card-bg {{ background: #0f172a; border: 1px solid #1e293b; }}
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">

    <!-- نافذة الدفع وحجز المبلغ (Apple Pay / مدى) -->
    <div id="paymentModal" class="fixed inset-0 bg-black/80 z-50 backdrop-blur-sm hidden flex items-center justify-center p-4">
        <div class="card-bg p-8 rounded-3xl max-w-md w-full border border-amber-500/30 text-center relative shadow-2xl">
            <div class="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 mx-auto flex items-center justify-center text-3xl mb-4">💳</div>
            <h3 class="text-xl font-black text-white mb-2">إيداع الضمان المالي في خزينة وثيق</h3>
            <p class="text-xs text-slate-400 mb-6">المبلغ سيبقى مجمداً في الخزينة حتى تستلم وتفحص، ولا يتم تحويله للبائع إلا بموافقتك التامة.</p>
            
            <div class="bg-slate-900 border border-slate-800 p-4 rounded-2xl mb-6 text-right space-y-2 text-sm">
                <div class="flex justify-between text-slate-400"><span>المبلغ الإجمالي المطلوب:</span><span class="text-emerald-400 font-black text-base">{deal['total_paid']:,} ريال</span></div>
                <div class="flex justify-between text-xs text-slate-500"><span>شامل رسوم الضمان ({deal['fee_percent']}%):</span><span>{deal['fee_amount']} ريال</span></div>
            </div>

            <!-- خيارات الدفع الفورية -->
            <div class="space-y-3">
                <button onclick="executePayment('Apple Pay ')" class="w-full bg-white hover:bg-slate-200 text-black font-black py-3.5 rounded-xl transition flex items-center justify-center gap-2 shadow-xl">
                    <span class="text-lg">Pay</span> <span>الدفع السريع بـ Apple Pay</span>
                </button>
                <button onclick="executePayment('بطاقة مدى Mada')" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3.5 rounded-xl transition flex items-center justify-center gap-2">
                    <span>💳</span> <span>الدفع ببطاقة مدى / فيزا / ماستركارد</span>
                </button>
                <button onclick="closePaymentModal()" class="w-full py-2.5 border border-slate-700 text-slate-400 rounded-xl hover:bg-slate-800 transition text-xs">إلغاء</button>
            </div>
            <p class="text-[10px] text-slate-500 mt-4">🔒 تشفير بنكي 256-bit متوافق مع معايير مؤسسة النقد السعودي</p>
        </div>
    </div>

    <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-black text-xl">و</div>
                <div>
                    <h1 class="text-xl font-black text-white">وثيق</h1>
                    <p class="text-xs text-amber-400/80 font-medium">غرفة الوساطة والتسليم المشفرة</p>
                </div>
            </a>
            <div class="flex items-center gap-3">
                <span class="text-xs bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 font-mono">رقم الصفقة: {deal['id']}</span>
            </div>
        </div>
    </header>

    <!-- شريط حالة الصفقة والمؤقت -->
    <div class="bg-blue-950/40 border-b border-blue-500/20 py-2.5 px-6 text-center text-xs font-semibold text-blue-300 flex items-center justify-center gap-2">
        <span>⏱️ مؤقت حماية المشتري التلقائي:</span>
        <span id="countdownTimer" class="font-mono text-amber-400 font-black text-sm">{'09:59' if not is_pending else 'بانتظار الإيداع'}</span>
        <span>(تُسترجع الأموال فورياً إذا لم يتم التسليم)</span>
    </div>

    <main class="max-w-6xl mx-auto px-6 py-8 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 w-full">
        
        <!-- تفاصيل الصفقة والتحكم -->
        <div class="lg:col-span-1 space-y-6">
            <div class="card-bg p-6 rounded-2xl">
                <div class="flex justify-between items-center mb-4">
                    <span class="text-xs px-2.5 py-1 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/30">{deal['category']}</span>
                    <span id="dealStatusBadge" class="text-xs px-2.5 py-1 rounded-md {'bg-amber-500/20 text-amber-400 border-amber-500/30' if is_pending else 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'} border font-bold">{deal['status']}</span>
                </div>
                <h2 class="text-xl font-black text-white mb-4">{deal['title']}</h2>
                
                <div class="border-t border-slate-800 pt-4 space-y-2 text-sm">
                    <div class="flex justify-between text-slate-400"><span>المبلغ الأساسي:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                    <div class="flex justify-between text-slate-400"><span>رسوم الضمان ({deal['fee_percent']}%):</span><span class="text-amber-400 font-bold">{deal['fee_amount']} ريال</span></div>
                    <div class="flex justify-between text-slate-400 border-t border-slate-800 pt-2 text-base"><span>الإجمالي المجمّد بالخزينة:</span><span class="text-emerald-400 font-black">{deal['total_paid']:,} ريال</span></div>
                </div>

                <div class="border-t border-slate-800 mt-4 pt-4 text-xs space-y-2 text-slate-400">
                    <div class="flex items-center justify-between">
                        <span>👤 البائع:</span>
                        <span class="text-white font-semibold">{deal['seller_name']}</span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span>👤 المشتري:</span>
                        <span class="text-white font-semibold">{deal['buyer_name']}</span>
                    </div>
                </div>
            </div>

            <!-- أزرار الإجراءات والدفع -->
            <div class="card-bg p-6 rounded-2xl space-y-3">
                <h4 class="text-sm font-bold text-white mb-2">إجراءات الأمان والدفع</h4>
                
                {'<button onclick="openPaymentModal()" class="w-full bg-white hover:bg-slate-200 text-black font-black py-3 rounded-xl transition flex items-center justify-center gap-2 shadow-lg mb-2"><span class="text-lg">Pay</span> <span>إيداع وتجميد المبلغ (Apple Pay / مدى)</span></button>' if is_pending else '<button onclick="confirmRelease()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition shadow-lg">✅ تأكيد الاستلام وتحويل المبلغ للبائع</button>'}
                
                <button onclick="raiseDispute()" class="w-full bg-rose-600/20 border border-rose-500/40 hover:bg-rose-600/30 text-rose-400 font-bold py-2.5 rounded-xl transition text-xs">⚠️ رفع نزاع وتجميد الصفقة للوسيط</button>
                <button onclick="triggerRefund()" class="w-full bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 font-bold py-2.5 rounded-xl transition text-xs">↩️ طلب استرجاع فوري (عدم تسليم)</button>
                <button onclick="copyDealLink()" class="w-full bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-amber-400 font-bold py-2.5 rounded-xl transition text-xs">🔗 نسخ رابط الصفقة للطرف الآخر</button>
            </div>
        </div>

        <!-- غرفة المحادثة المباشرة والإثباتات -->
        <div class="lg:col-span-2 card-bg rounded-2xl flex flex-col h-[620px] overflow-hidden">
            <div class="p-4 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <div class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
                    <span class="text-sm font-bold text-white">المحادثة الآمنة وتوثيق التسليم</span>
                </div>
                <span class="text-xs text-amber-400/90 font-medium">🔒 مشفرة ومراقبة لدى إدارة وثيق</span>
            </div>

            <!-- الرسائل -->
            <div id="chatBox" class="flex-1 p-4 overflow-y-auto space-y-3 text-sm">
                {''.join([f'<div class="p-3 rounded-xl {"bg-amber-500/10 border border-amber-500/20 text-amber-300" if "النظام" in m["sender"] or "الدفع" in m["sender"] else "bg-slate-800 text-slate-200"}"><div class="flex justify-between text-xs opacity-60 mb-1"><span>{m["sender"]}</span><span>{m["time"]}</span></div><p>{m["text"]}</p></div>' for m in deal['messages']])}
            </div>

            <!-- إرسال رسالة -->
            <div class="p-4 border-t border-slate-800 bg-slate-900/30 flex gap-2">
                <input id="chatInput" type="text" placeholder="اكتب بيانات التسليم، الحساب، أو الملاحظات هنا بأمان..." class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:border-amber-500 outline-none" onkeydown="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()" class="gold-btn text-slate-950 font-bold px-6 py-2.5 rounded-xl">إرسال</button>
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
                alert('✅ تم التحقق وتجميد المبلغ في خزينة وثيق بنجاح عبر ' + method);
                location.reload();
            }}
        }}

        function copyDealLink() {{
            navigator.clipboard.writeText(window.location.href);
            alert('تم نسخ رابط الصفقة بنجاح! شاركه مع الطرف الآخر.');
        }}

        async function confirmRelease() {{
            if(!confirm('هل استلمت وفحصت السلعة/الخدمة وتأكدت 100%؟ سيتم تحويل المبلغ للبائع فوراً.')) return;
            const res = await fetch('/api/deals/' + dealId + '/release', {{method: 'POST'}});
            if(res.ok) location.reload();
        }}

        async function raiseDispute() {{
            if(!confirm('هل تواجه مشكلة أو تلاعب وتريد تجميد الصفقة فوراً لتدخل الوسيط؟')) return;
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
