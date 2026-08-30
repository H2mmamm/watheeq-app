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

app = FastAPI(title="وثيق | Watheeq - Escrow & Trust Platform")

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
        if ("50" in req.category or "Cap" in req.category) and fee_amount > 50:
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

# صفحة تسجيل الدخول Login
@app.get("/login", response_class=HTMLResponse)
@app.get("/issuer/login", response_class=HTMLResponse)
def serve_login():
    return """<!DOCTYPE html>
<html lang="en" dir="ltr" id="loginHtml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Watheeq | Sign In</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', 'Tajawal', sans-serif; background-color: #030303; color: #ffffff; }
        .input-dark {
            background-color: #0b0b0e;
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #ffffff;
            transition: all 0.2s;
        }
        .input-dark:focus {
            border-color: rgba(255, 255, 255, 0.3);
            outline: none;
        }
        .card-dark {
            background: rgba(14, 14, 18, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.06);
        }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between selection:bg-white selection:text-black">

    <!-- Top Header -->
    <header class="px-8 py-6 flex items-center justify-between">
        <a href="/" class="flex items-center gap-3">
            <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
            <span class="text-xl font-bold tracking-tight text-white uppercase">Watheeq</span>
        </a>

        <div class="flex items-center gap-6 text-xs font-medium text-slate-400">
            <button onclick="toggleLoginLang()" class="hover:text-white transition font-mono border border-white/10 px-3 py-1.5 rounded-full" id="lLangBtn">EN / AR</button>
            <a href="/" class="hover:text-white transition" id="lHomeLink">Home</a>
            <a href="/#calculator" class="hover:text-white transition" id="lVerifyLink">Calculator</a>
        </div>
    </header>

    <!-- Center Content (Split View) -->
    <main class="max-w-6xl mx-auto px-6 py-12 flex-1 grid grid-cols-1 md:grid-cols-2 gap-16 items-center w-full">
        
        <!-- Left Column: Login Form -->
        <div class="max-w-md w-full">
            <h1 class="text-3xl font-extrabold text-white mb-2 tracking-tight" id="lHeading">Issuer Login</h1>
            <p class="text-xs text-slate-400 mb-8" id="lSubHeading">Sign in to your issuer and escrow dashboard</p>

            <form onsubmit="handleLogin(event)" class="space-y-4">
                <div>
                    <label class="block text-xs font-medium text-slate-400 mb-2" id="lEmailLabel">Email / Identifier</label>
                    <input type="text" id="loginEmail" value="tuwaiq@tuwaiq.sa" class="w-full input-dark rounded-xl px-4 py-3 text-sm" placeholder="name@domain.com">
                </div>

                <div>
                    <div class="flex justify-between items-center mb-2">
                        <label class="text-xs font-medium text-slate-400" id="lPassLabel">Password</label>
                        <a href="#" class="text-[11px] text-slate-500 hover:text-white transition" id="lForgot">Forgot password?</a>
                    </div>
                    <input type="password" id="loginPass" value="••••••••" class="w-full input-dark rounded-xl px-4 py-3 text-sm" placeholder="••••••••">
                </div>

                <button type="submit" class="w-full bg-white hover:bg-slate-200 text-black font-semibold text-sm py-3.5 rounded-xl transition duration-200 mt-2" id="lSubmitBtn">
                    Continue
                </button>
            </form>

            <p class="text-xs text-slate-500 text-center mt-8">
                <span id="lNoAcc">Don't have an account?</span> <a href="/" class="text-white hover:underline" id="lContact">Create Deal</a>
            </p>
        </div>

        <!-- Right Column: Enterprise Security Visual -->
        <div class="hidden md:flex flex-col items-center justify-center text-center p-8">
            <div class="flex gap-4 mb-8">
                <div class="card-dark p-4 rounded-2xl w-40 text-left border border-white/10 shadow-2xl">
                    <div class="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-xs mb-3 text-emerald-400">✓</div>
                    <div class="h-2 w-16 bg-white/20 rounded mb-1.5"></div>
                    <div class="h-1.5 w-10 bg-white/10 rounded"></div>
                </div>
                <div class="card-dark p-4 rounded-2xl w-40 text-left border border-white/10 shadow-2xl">
                    <div class="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center text-xs mb-3 text-slate-300">🔒</div>
                    <div class="h-2 w-16 bg-white/20 rounded mb-1.5"></div>
                    <div class="h-1.5 w-10 bg-white/10 rounded"></div>
                </div>
            </div>

            <h3 class="text-xl font-bold text-white mb-2 tracking-tight" id="lSecTitle">Enterprise Security</h3>
            <p class="text-xs text-slate-400 max-w-sm leading-relaxed" id="lSecDesc">
                Bank-grade encryption and immutable escrow records ensure your deposits and digital transactions remain tamper-proof forever.
            </p>
        </div>

    </main>

    <!-- Footer -->
    <footer class="px-8 py-6 text-center text-xs text-slate-600 border-t border-white/5 font-mono">
        IMMUTABLE RECORD • BANK-GRADE ESCROW • SAFEWATHEEQ.COM
    </footer>

    <script>
        let isEn = true;

        function toggleLoginLang() {
            isEn = !isEn;
            const html = document.getElementById('loginHtml');
            html.setAttribute('dir', isEn ? 'ltr' : 'rtl');
            html.setAttribute('lang', isEn ? 'en' : 'ar');
            document.getElementById('lLangBtn').innerText = isEn ? 'EN / AR' : 'AR / EN';

            if(!isEn) {
                document.getElementById('lHomeLink').innerText = 'الرئيسية';
                document.getElementById('lVerifyLink').innerText = 'الحاسبة';
                document.getElementById('lHeading').innerText = 'تسجيل الدخول';
                document.getElementById('lSubHeading').innerText = 'الدخول إلى لوحة إدارة الصفقات والضمان المالي';
                document.getElementById('lEmailLabel').innerText = 'البريد الإلكتروني / الهوية';
                document.getElementById('lPassLabel').innerText = 'كلمة المرور';
                document.getElementById('lForgot').innerText = 'نسيت كلمة المرور؟';
                document.getElementById('lSubmitBtn').innerText = 'متابعة الدخول';
                document.getElementById('lNoAcc').innerText = 'ليس لديك حساب؟';
                document.getElementById('lContact').innerText = 'إنشاء صفقة فورية';
                document.getElementById('lSecTitle').innerText = 'أمان مالي مصرفي مشفر';
                document.getElementById('lSecDesc').innerText = 'تشفير بنكي وسجلات غير قابلة للتعديل لضمان بقاء العرابين والصفقات محمية للأبد.';
            } else {
                document.getElementById('lHomeLink').innerText = 'Home';
                document.getElementById('lVerifyLink').innerText = 'Calculator';
                document.getElementById('lHeading').innerText = 'Issuer Login';
                document.getElementById('lSubHeading').innerText = 'Sign in to your issuer and escrow dashboard';
                document.getElementById('lEmailLabel').innerText = 'Email / Identifier';
                document.getElementById('lPassLabel').innerText = 'Password';
                document.getElementById('lForgot').innerText = 'Forgot password?';
                document.getElementById('lSubmitBtn').innerText = 'Continue';
                document.getElementById('lNoAcc').innerText = "Don't have an account?";
                document.getElementById('lContact').innerText = 'Create Deal';
                document.getElementById('lSecTitle').innerText = 'Enterprise Security';
                document.getElementById('lSecDesc').innerText = 'Bank-grade encryption and immutable escrow records ensure your deposits and digital transactions remain tamper-proof forever.';
            }
        }

        function handleLogin(e) {
            e.preventDefault();
            alert(isEn ? 'Logged in successfully! Redirecting...' : 'تم تسجيل الدخول بنجاح! جاري التحويل...');
            window.location.href = '/deal/WTQ-701';
        }
    </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def serve_home():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlTag">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="siteTitle">وثيق | Watheeq - The Immutable Standard</title>
    
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://safewatheeq.com/">
    <meta property="og:title" content="Watheeq | الوساطة والضمان المالي الذكي">
    <meta property="og:description" content="The immutable standard for sovereign trust and secure escrow.">
    
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', 'Inter', sans-serif; background-color: #030303; color: #ffffff; overflow-x: hidden; }
        .hero-glow {
            background: radial-gradient(circle at 50% 25%, rgba(255, 255, 255, 0.08) 0%, rgba(3, 3, 3, 0.98) 75%);
        }
        .light-streak {
            position: absolute;
            width: 130%;
            height: 320px;
            top: 20%;
            left: -15%;
            background: radial-gradient(ellipse at center, rgba(255, 255, 255, 0.12) 0%, rgba(255,255,255,0.02) 40%, rgba(0,0,0,0) 70%);
            transform: rotate(-10deg);
            pointer-events: none;
            filter: blur(50px);
        }
        .card-dark {
            background: rgba(14, 14, 18, 0.75);
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
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: #ffffff;
            transition: all 0.2s ease;
        }
        .btn-glass:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        .pill-badge {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between relative selection:bg-white selection:text-black">

    <div class="light-streak"></div>

    <!-- Navigation Bar -->
    <header class="border-b border-white/5 bg-black/60 backdrop-blur-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <!-- Brand Logo -->
            <a href="/" class="flex items-center gap-3 cursor-pointer">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                </svg>
                <div class="flex flex-col text-right">
                    <span class="text-lg font-black tracking-tight text-white">وثيق</span>
                    <span class="text-[10px] text-slate-400 font-medium tracking-wider uppercase font-mono">WATHEEQ</span>
                </div>
            </a>
            
            <!-- Nav Links -->
            <nav class="hidden md:flex items-center gap-8 text-xs font-semibold text-slate-400">
                <a href="#calculator" class="hover:text-white transition" id="navCalc">حاسبة العمولات</a>
                <a href="#security" class="hover:text-white transition" id="navSec">بروتوكول الأمان</a>
                <a href="/deal/WTQ-701" class="hover:text-white transition" id="navLive">غرفة حية (WTQ-701)</a>
            </nav>

            <!-- Actions -->
            <div class="flex items-center gap-3">
                <button onclick="toggleLanguage()" id="langBtn" class="pill-badge text-slate-300 px-3.5 py-1.5 rounded-full text-xs font-semibold hover:border-white/30 transition">
                    🌐 English
                </button>
                <a href="/login" class="pill-badge text-slate-300 px-4 py-1.5 rounded-full text-xs font-semibold hover:border-white/30 transition flex items-center gap-1.5" id="navSignIn">
                    Sign In
                </a>
                <button onclick="openModal()" class="btn-white text-xs font-black px-5 py-2 rounded-full shadow-sm hover:scale-105 transition" id="btnNav">
                    + إنشاء صفقة
                </button>
            </div>
        </div>
    </header>

    <!-- Main Hero Section -->
    <main class="hero-glow flex-1 flex flex-col items-center justify-center text-center px-6 py-20 relative z-10">
        
        <!-- Live Status Badge -->
        <div class="inline-flex items-center gap-2 px-4 py-1 rounded-full pill-badge text-emerald-400 text-xs font-mono tracking-wide mb-8">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span id="heroBadge">V1.0 IS LIVE & SECURE</span>
        </div>

        <!-- Hero Headline -->
        <h1 class="text-4xl md:text-6xl font-black text-white tracking-tight leading-[1.2] max-w-4xl mb-6" id="heroHeadline">
            The immutable<br><span class="text-slate-400 font-light">standard.</span>
        </h1>

        <p class="text-slate-400 text-sm md:text-base max-w-2xl mb-10 leading-relaxed font-normal" id="heroSub">
            المنصة والوساطة المالية السعودية لضمان وتأمين كافة المبايعات والصفقات بأقل عمولة في السوق (تبدأ من 1%). حجز المبالغ بنكياً عبر Apple Pay ومدى حتى الفحص والتسليم التام.
        </p>

        <!-- CTA Buttons -->
        <div class="flex flex-wrap items-center justify-center gap-4 mb-16">
            <button onclick="openModal()" class="btn-white text-sm font-bold px-8 py-3.5 rounded-full flex items-center gap-2" id="heroBtn1">
                <span>ابدأ صفقة جديدة</span>
                <span class="text-base">⚡</span>
            </button>
            <a href="#calculator" class="btn-glass text-sm font-semibold px-8 py-3.5 rounded-full" id="heroBtn2">
                احسب العمولة المخفضة 🧮
            </a>
        </div>

        <!-- Market Breaker Rates Bar -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl w-full text-right" id="statsContainer">
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat1Label">الأصول والحسابات والألعاب</p>
                <p class="text-lg font-black text-white font-mono">2.5% <span class="text-[11px] text-emerald-400 font-normal" id="stat1Sub">أقل عمولة</span></p>
            </div>
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat2Label">عربون وفحص السيارات</p>
                <p class="text-lg font-black text-white font-mono">1% <span class="text-[11px] text-slate-400 font-normal" id="stat2Sub">(حد أقصى 50﷼)</span></p>
            </div>
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat3Label">مؤقت الاسترجاع التلقائي</p>
                <p class="text-lg font-black text-white font-mono">10 Min <span class="text-[11px] text-slate-400 font-normal" id="stat3Sub">حماية فورية</span></p>
            </div>
            <div class="card-dark p-5 rounded-2xl">
                <p class="text-xs text-slate-400 mb-1" id="stat4Label">بوابات الدفع المشفرة</p>
                <p class="text-lg font-black text-white font-mono">Pay / مدى</p>
            </div>
        </div>

    </main>

    <!-- Calculator Section -->
    <section id="calculator" class="max-w-4xl mx-auto px-6 py-16 w-full relative z-10">
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
                        <option value="car_deposit" id="opt3">عربون حجز وفحص المركبات (1% بحد أقصى 50 ريال)</option>
                        <option value="goods" id="opt4">الأجهزة الإلكترونية والسلع (1%)</option>
                    </select>
                </div>
            </div>

            <div class="grid grid-cols-3 gap-4 p-4 rounded-2xl bg-white/[0.02] border border-white/5 text-center mb-6 font-mono">
                <div>
                    <span class="block text-[11px] text-slate-500 mb-1" id="resSeller">المبلغ للبائع</span>
                    <span id="calcNet" class="text-base md:text-lg font-bold text-white">1,000 ريال</span>
                </div>
                <div>
                    <span class="block text-[11px] text-slate-400 mb-1" id="resFee">عمولة وثيق</span>
                    <span id="calcFee" class="text-base md:text-lg font-bold text-slate-300">25 ريال</span>
                </div>
                <div>
                    <span class="block text-[11px] text-emerald-400 mb-1" id="resTotal">الإجمالي المطلوب للدفع</span>
                    <span id="calcTotal" class="text-base md:text-lg font-black text-emerald-400">1,025 ريال</span>
                </div>
            </div>

            <div class="text-center">
                <button onclick="openModalWithValues()" class="btn-white text-xs font-black px-8 py-3.5 rounded-full" id="calcBtn">
                    ابدأ بهذه الحسبة المخفضة 🚀
                </button>
            </div>
        </div>
    </section>

    <!-- Security Protocol Section -->
    <section id="security" class="max-w-6xl mx-auto px-6 py-12 relative z-10">
        <div class="text-center mb-10">
            <h3 class="text-2xl font-black text-white mb-2" id="secHead">ترسانة الحماية ومنع الاحتيال</h3>
            <p class="text-xs text-slate-400" id="secSub">آليات مالية صارمة لحماية أموالك وسلعك أثناء البيع والشراء</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="card-dark p-6 rounded-2xl">
                <div class="text-3xl mb-3">⏱️</div>
                <h4 class="text-sm font-bold text-white mb-2" id="sec1Title">مؤقت الاسترجاع الفوري (10 دقائق)</h4>
                <p class="text-xs text-slate-400 leading-relaxed" id="sec1Desc">في الصفقات الرقمية والحسابات، إذا لم يقم البائع بتسليم البيانات خلال 10 دقائق، يقوم النظام تلقائياً بإرجاع المبلغ للمشتري.</p>
            </div>
            <div class="card-dark p-6 rounded-2xl">
                <div class="text-3xl mb-3">🚗</div>
                <h4 class="text-sm font-bold text-white mb-2" id="sec2Title">ضمان عربون فحص السيارات</h4>
                <p class="text-xs text-slate-400 leading-relaxed" id="sec2Desc">احجز سيارتك وافحصها بالورشة وأنت مطمئن؛ العربون محفوظ ولا يتحول للبائع إلا بموافقتك بعد التأكد من سلامة الفحص.</p>
            </div>
            <div class="card-dark p-6 rounded-2xl">
                <div class="text-3xl mb-3">Pay</div>
                <h4 class="text-sm font-bold text-white mb-2" id="sec3Title">حجز مصرفي عبر Apple Pay ومدى</h4>
                <p class="text-xs text-slate-400 leading-relaxed" id="sec3Desc">الأموال لا تذهب لحسابات أفراد شخصية، بل تُجمد بنكياً في خزينة منصة وثيق المحايدة حتى اكتمال التبادل بالكامل.</p>
            </div>
        </div>
    </section>

    <!-- Modal إنشاء صفقة -->
    <div id="createModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-lg w-full border border-white/20">
            <h3 class="text-xl font-black text-white mb-1" id="mTitle">إنشاء رابط صفقة وساطة جديد</h3>
            <p class="text-xs text-slate-400 mb-6" id="mSub">سيتم إنشاء غرفة تسليم مشفرة برابط مباشر للأطراف مع بوابة حجز بنكي.</p>
            
            <div class="space-y-4">
                <div>
                    <label class="text-xs text-slate-400 block mb-1" id="mLabel1">عنوان الصفقة أو السلعة</label>
                    <input id="newTitle" type="text" placeholder="عربون فحص كامري / حساب ألعاب / برمجة متجر" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1" id="mLabel2">القسم والتصنيف</label>
                    <select id="newCategory" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm outline-none focus:border-white/40">
                        <option value="digital">الأصول الرقمية والحسابات (2.5%)</option>
                        <option value="freelance">الخدمات والعمل الحر (2.5%)</option>
                        <option value="car_deposit">عربون وفحص المركبات (1% بحد أقصى 50 ريال)</option>
                        <option value="goods">الأجهزة الإلكترونية والسلع (1%)</option>
                    </select>
                </div>
                <div>
                    <label class="text-xs text-slate-400 block mb-1" id="mLabel3">المبلغ المطلوب</label>
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
                <button onclick="submitDeal()" class="flex-1 btn-white text-xs font-black py-3 rounded-xl" id="mBtnSubmit">إنشاء الرابط وحجز الضمان 🔒</button>
                <button onclick="closeModal()" class="px-5 py-3 btn-glass text-xs rounded-xl" id="mBtnCancel">إلغاء</button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="border-t border-white/5 py-8 bg-black text-center text-xs text-slate-500 relative z-10 space-y-2">
        <p id="footerRights">جميع الحقوق محفوظة © منصة وثيق للوساطة والضمان المالي المشترك | safewatheeq.com</p>
        <p class="text-slate-600" id="footerReg">نظام وساطة رقمي آمن ومعتمد - خاضع للأنظمة التجارية السعودية</p>
    </footer>

    <script>
        let currentLang = 'ar';

        const i18n = {
            ar: {
                langBtn: '🌐 English',
                navCalc: 'حاسبة العمولات',
                navSec: 'بروتوكول الأمان',
                navLive: 'غرفة حية (WTQ-701)',
                navSignIn: 'Sign In',
                btnNav: '+ إنشاء صفقة',
                heroBadge: 'نظام الضمان المالي المشفر نشط 24/7',
                heroHeadline: 'The immutable<br><span class="text-slate-400 font-light">standard.</span>',
                heroSub: 'المنصة والوساطة المالية السعودية لضمان وتأمين كافة المبايعات والصفقات بأقل عمولة في السوق (تبدأ من 1%). حجز المبالغ بنكياً عبر Apple Pay ومدى حتى الفحص والتسليم التام.',
                heroBtn1: 'ابدأ صفقة جديدة ⚡',
                heroBtn2: 'احسب العمولة المخفضة 🧮',
                stat1Label: 'الأصول والحسابات والألعاب',
                stat1Sub: 'أقل عمولة',
                stat2Label: 'عربون وفحص السيارات',
                stat2Sub: '(حد أقصى 50﷼)',
                stat3Label: 'مؤقت الاسترجاع التلقائي',
                stat3Sub: 'حماية فورية',
                stat4Label: 'بوابات الدفع المشفرة',
                calcHead: 'حاسبة كسر السوق والعمولات الشفافة',
                calcSub: 'تحطيم أسعار العمولات التقليدية لضمان أعلى فائدة للبائع والمشتري',
                lblAmount: 'قيمة الصفقة أو العربون (ريال سعودي):',
                lblCat: 'مجال الوساطة:',
                opt1: 'الأصول الرقمية، الحسابات، والألعاب (2.5%)',
                opt2: 'الخدمات والعمل الحر والبرمجة (2.5%)',
                opt3: 'عربون حجز وفحص المركبات (1% بحد أقصى 50 ريال)',
                opt4: 'الأجهزة الإلكترونية والسلع (1%)',
                resSeller: 'المبلغ للبائع',
                resFee: 'عمولة وثيق',
                resTotal: 'الإجمالي المطلوب للدفع',
                calcBtn: 'ابدأ بهذه الحسبة المخفضة 🚀',
                secHead: 'ترسانة الحماية ومنع الاحتيال',
                secSub: 'آليات مالية صارمة لحماية أموالك وسلعك أثناء البيع والشراء',
                sec1Title: 'مؤقت الاسترجاع الفوري (10 دقائق)',
                sec1Desc: 'في الصفقات الرقمية والحسابات، إذا لم يقم البائع بتسليم البيانات خلال 10 دقائق، يقوم النظام تلقائياً بإرجاع المبلغ للمشتري.',
                sec2Title: 'ضمان عربون فحص السيارات',
                sec2Desc: 'احجز سيارتك وافحصها بالورشة وأنت مطمئن؛ العربون محفوظ ولا يتحول للبائع إلا بموافقتك بعد التأكد من سلامة الفحص.',
                sec3Title: 'حجز مصرفي عبر Apple Pay ومدى',
                sec3Desc: 'الأموال لا تذهب لحسابات أفراد شخصية، بل تُجمد بنكياً في خزينة منصة وثيق المحايدة حتى اكتمال التبادل بالكامل.',
                mTitle: 'إنشاء رابط صفقة وساطة جديد',
                mSub: 'سيتم إنشاء غرفة تسليم مشفرة برابط مباشر للأطراف مع بوابة حجز بنكي.',
                mLabel1: 'عنوان الصفقة أو السلعة',
                mLabel2: 'القسم والتصنيف',
                mLabel3: 'المبلغ المطلوب (ريال)',
                mLabel4: 'اسم / يوزر البائع',
                mLabel5: 'اسم / يوزر المشتري (اختياري)',
                mBtnSubmit: 'إنشاء الرابط وحجز الضمان 🔒',
                mBtnCancel: 'إلغاء',
                footerRights: 'جميع الحقوق محفوظة © منصة وثيق للوساطة والضمان المالي المشترك | safewatheeq.com',
                footerReg: 'نظام وساطة رقمي آمن ومعتمد - خاضع للأنظمة التجارية السعودية',
                curr: ' ريال'
            },
            en: {
                langBtn: '🌐 العربية',
                navCalc: 'Fee Calculator',
                navSec: 'Security Protocol',
                navLive: 'Live Deal (WTQ-701)',
                navSignIn: 'Sign In',
                btnNav: '+ Create Deal',
                heroBadge: 'V1.0 IS LIVE & BANK-GRADE SECURED',
                heroHeadline: 'The immutable<br><span class="text-slate-400 font-light">standard.</span>',
                heroSub: 'The premier Saudi escrow and trust platform. Secure any digital asset, freelance milestone, or car inspection deposit with ultra-low fees starting at 1% via Apple Pay & Mada.',
                heroBtn1: 'Start Secure Deal ⚡',
                heroBtn2: 'Calculate Lowest Fees 🧮',
                stat1Label: 'Digital Assets & Gaming',
                stat1Sub: 'Lowest in Market',
                stat2Label: 'Car Deposit & Inspection',
                stat2Sub: '(Max 50 SAR Cap)',
                stat3Label: 'Auto-Refund Timer',
                stat3Sub: 'Instant Protection',
                stat4Label: 'Encrypted Payment',
                calcHead: 'Market Breaker Fee Calculator',
                calcSub: 'Transparent, ultra-low fees engineered to maximize savings for buyers and sellers',
                lblAmount: 'Deal / Deposit Amount (SAR):',
                lblCat: 'Escrow Category:',
                opt1: 'Digital Assets, Accounts & Gaming (2.5%)',
                opt2: 'Freelance, Services & Code (2.5%)',
                opt3: 'Car Inspection Deposit (1% capped at 50 SAR)',
                opt4: 'Electronics & General Goods (1%)',
                resSeller: 'Net to Seller',
                resFee: 'Watheeq Fee',
                resTotal: 'Total Deposit Required',
                calcBtn: 'Start Deal with this Calculation 🚀',
                secHead: 'Anti-Fraud & Security Suite',
                secSub: 'Rigorous financial and technical safeguards eliminating transaction fraud',
                sec1Title: '10-Minute Auto Refund',
                sec1Desc: 'For fast digital trades, if credentials are not delivered within 10 minutes, full funds automatically refund to the buyer.',
                sec2Title: 'Vehicle Inspection Deposit',
                sec2Desc: 'Inspect vehicles with peace of mind. Deposits are held in neutral escrow until you approve the mechanical report.',
                sec3Title: 'Apple Pay & Mada Escrow Vault',
                sec3Desc: 'No personal bank transfers. Funds are frozen inside institutional banking vaults until verified completion.',
                mTitle: 'Create New Escrow Deal Room',
                mSub: 'Generate an instant encrypted escrow room with integrated checkout.',
                mLabel1: 'Deal Title / Item Description',
                mLabel2: 'Category',
                mLabel3: 'Required Amount (SAR)',
                mLabel4: 'Seller Username / Name',
                mLabel5: 'Buyer Username (Optional)',
                mBtnSubmit: 'Generate Room & Lock Escrow 🔒',
                mBtnCancel: 'Cancel',
                footerRights: '© 2026 Watheeq Escrow Inc. All rights reserved | safewatheeq.com',
                footerReg: 'Compliant with Saudi eCommerce and Digital Escrow Regulations',
                curr: ' SAR'
            }
        };

        function toggleLanguage() {
            currentLang = (currentLang === 'ar') ? 'en' : 'ar';
            const htmlTag = document.getElementById('htmlTag');
            const data = i18n[currentLang];

            htmlTag.setAttribute('dir', currentLang === 'ar' ? 'rtl' : 'ltr');
            htmlTag.setAttribute('lang', currentLang);

            document.getElementById('langBtn').innerText = data.langBtn;
            document.getElementById('navCalc').innerText = data.navCalc;
            document.getElementById('navSec').innerText = data.navSec;
            document.getElementById('navLive').innerText = data.navLive;
            document.getElementById('navSignIn').innerText = data.navSignIn;
            document.getElementById('btnNav').innerText = data.btnNav;
            
            document.getElementById('heroBadge').innerText = data.heroBadge;
            document.getElementById('heroHeadline').innerHTML = data.heroHeadline;
            document.getElementById('heroSub').innerText = data.heroSub;
            document.getElementById('heroBtn1').innerHTML = data.heroBtn1;
            document.getElementById('heroBtn2').innerText = data.heroBtn2;

            document.getElementById('stat1Label').innerText = data.stat1Label;
            document.getElementById('stat1Sub').innerText = data.stat1Sub;
            document.getElementById('stat2Label').innerText = data.stat2Label;
            document.getElementById('stat2Sub').innerText = data.stat2Sub;
            document.getElementById('stat3Label').innerText = data.stat3Label;
            document.getElementById('stat3Sub').innerText = data.stat3Sub;
            document.getElementById('stat4Label').innerText = data.stat4Label;

            document.getElementById('calcHead').innerText = data.calcHead;
            document.getElementById('calcSub').innerText = data.calcSub;
            document.getElementById('lblAmount').innerText = data.lblAmount;
            document.getElementById('lblCat').innerText = data.lblCat;
            document.getElementById('opt1').innerText = data.opt1;
            document.getElementById('opt2').innerText = data.opt2;
            document.getElementById('opt3').innerText = data.opt3;
            document.getElementById('opt4').innerText = data.opt4;
            document.getElementById('resSeller').innerText = data.resSeller;
            document.getElementById('resFee').innerText = data.resFee;
            document.getElementById('resTotal').innerText = data.resTotal;
            document.getElementById('calcBtn').innerText = data.calcBtn;

            document.getElementById('secHead').innerText = data.secHead;
            document.getElementById('secSub').innerText = data.secSub;
            document.getElementById('sec1Title').innerText = data.sec1Title;
            document.getElementById('sec1Desc').innerText = data.sec1Desc;
            document.getElementById('sec2Title').innerText = data.sec2Title;
            document.getElementById('sec2Desc').innerText = data.sec2Desc;
            document.getElementById('sec3Title').innerText = data.sec3Title;
            document.getElementById('sec3Desc').innerText = data.sec3Desc;

            document.getElementById('mTitle').innerText = data.mTitle;
            document.getElementById('mSub').innerText = data.mSub;
            document.getElementById('mLabel1').innerText = data.mLabel1;
            document.getElementById('mLabel2').innerText = data.mLabel2;
            document.getElementById('mLabel3').innerText = data.mLabel3;
            document.getElementById('mLabel4').innerText = data.mLabel4;
            document.getElementById('mLabel5').innerText = data.mLabel5;
            document.getElementById('mBtnSubmit').innerText = data.mBtnSubmit;
            document.getElementById('mBtnCancel').innerText = data.mBtnCancel;

            document.getElementById('footerRights').innerText = data.footerRights;
            document.getElementById('footerReg').innerText = data.footerReg;

            runCalculator();
        }

        function runCalculator() {
            const amount = parseFloat(document.getElementById('calcAmount').value) || 0;
            const cat = document.getElementById('calcCategory').value;
            let fee = (amount * 2.5) / 100;
            
            if(cat === 'car_deposit') {
                fee = (amount * 1.0) / 100;
                if(fee > 50) fee = 50;
            } else if(cat === 'goods') {
                fee = (amount * 1.0) / 100;
            }

            const total = amount + fee;
            const cur = i18n[currentLang].curr;

            document.getElementById('calcNet').innerText = amount.toLocaleString() + cur;
            document.getElementById('calcFee').innerText = fee.toLocaleString() + cur;
            document.getElementById('calcTotal').innerText = total.toLocaleString() + cur;
        }

        function openModal() { document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex'); }
        function openModalWithValues() { document.getElementById('newPrice').value = document.getElementById('calcAmount').value; openModal(); }
        function closeModal() { document.getElementById('createModal').classList.add('hidden'); document.getElementById('createModal').classList.remove('flex'); }

        async function submitDeal() {
            const title = document.getElementById('newTitle').value;
            const categoryElem = document.getElementById('newCategory');
            const category = categoryElem.options[categoryElem.selectedIndex].text;
            const price = parseFloat(document.getElementById('newPrice').value);
            const seller_name = document.getElementById('newSeller').value;
            const buyer_name = document.getElementById('newBuyer').value;

            if(!title || !price || !seller_name) {
                alert(currentLang === 'ar' ? 'يرجى تعبئة الحقول الأساسية' : 'Please fill required fields');
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
    <title>غرفة الضمان {deal['id']} | وثيق</title>
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

    <!-- نافذة الدفع وحجز المبلغ (Apple Pay / مدى) -->
    <div id="paymentModal" class="fixed inset-0 bg-black/90 z-50 backdrop-blur-md hidden flex items-center justify-center p-4">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full border border-white/20 text-center relative shadow-2xl">
            <div class="w-14 h-14 rounded-2xl bg-white/10 mx-auto flex items-center justify-center text-2xl mb-4">💳</div>
            <h3 class="text-xl font-bold text-white mb-2">إيداع الضمان المالي في خزينة وثيق</h3>
            <p class="text-xs text-slate-400 mb-6">المبلغ يُحجز مشفراً ولا يُحول للبائع إلا بعد فحصك وموافقتك التامة.</p>
            
            <div class="bg-black/60 border border-white/10 p-4 rounded-2xl mb-6 text-right space-y-2 text-sm font-mono">
                <div class="flex justify-between text-slate-400"><span>المبلغ الإجمالي:</span><span class="text-emerald-400 font-bold text-base">{deal['total_paid']:,} ريال</span></div>
                <div class="flex justify-between text-xs text-slate-500"><span>شامل رسوم الضمان ({deal['fee_percent']}%):</span><span>{deal['fee_amount']} ريال</span></div>
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
            <a href="/" class="flex items-center gap-3">
                <svg class="w-6 h-6 text-white" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M4.5 12.75l6 6 9-13.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
                </svg>
                <span class="text-lg font-black tracking-tight text-white uppercase">Watheeq</span>
            </a>
            <span class="text-xs bg-white/5 px-3 py-1.5 rounded-full border border-white/10 text-slate-300 font-mono">رقم الصفقة: {deal['id']}</span>
        </div>
    </header>

    <!-- شريط حالة الصفقة والمؤقت -->
    <div class="bg-white/[0.02] border-b border-white/5 py-2 px-6 text-center text-xs text-slate-400 flex items-center justify-center gap-2 font-mono">
        <span>⏱️ مؤقت الاسترجاع التلقائي:</span>
        <span id="countdownTimer" class="text-white font-bold">{'09:59' if not is_pending else 'بانتظار الإيداع'}</span>
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
                    <div class="flex justify-between text-slate-400"><span>مبلغ الصفقة:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                    <div class="flex justify-between text-slate-400"><span>عمولة الضمان:</span><span class="text-slate-300">{deal['fee_amount']} ريال</span></div>
                    <div class="flex justify-between text-slate-400 border-t border-white/10 pt-2 text-sm"><span>الإجمالي المجمّد:</span><span class="text-emerald-400 font-bold">{deal['total_paid']:,} ريال</span></div>
                </div>

                <div class="border-t border-white/10 mt-4 pt-4 text-xs space-y-2 text-slate-400">
                    <div class="flex items-center justify-between"><span>👤 البائع:</span><span class="text-white">{deal['seller_name']}</span></div>
                    <div class="flex items-center justify-between"><span>👤 المشتري:</span><span class="text-white">{deal['buyer_name']}</span></div>
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
                    <span class="text-xs font-bold text-white uppercase tracking-wider">سجل المحادثة وتوثيق التسليم</span>
                </div>
                <span class="text-[11px] text-slate-500 font-mono">🔒 مشفرة ومحمية</span>
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
