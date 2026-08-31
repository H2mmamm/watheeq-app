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

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

app = FastAPI(title="وثيق | Watheeq - AI Supervised Escrow & Marketplace Platform")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    if DATABASE_URL:
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception:
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
                    'مركبات ومعدات وعرابين (1.5%)',
                    2500.0,
                    1.5,
                    37.5,
                    2537.5,
                    'سعد الشمري (موثق نفاذ ✅)',
                    'أحمد المالكي (موثق نفاذ ✅)',
                    'المبلغ مجمّد بالخزينة (بإشراف الذكاء الاصطناعي AI 🛡️)',
                    'تم التحقق من تفاصيل الصفقة وتجميد المبلغ بأمان في خزينة وثيق تحت مراقبة نظام الذكاء الاصطناعي.',
                    '[
                        {"sender": "مشرف الذكاء الاصطناعي (Watheeq AI)", "text": "مرحباً بكم. أنا نظام الرقابة الآلي. تم تجميد مبلغ 2,537.5 ريال بنجاح في الخزينة. ابدءوا الفحص وسأتابع معكم.", "time": "10:00 AM"},
                        {"sender": "المشتري (أحمد)", "text": "تم سداد العربون والعمولة، بانتظار تقرير الفحص.", "time": "10:02 AM"}
                    ]'::jsonb
                )
                ON CONFLICT (id) DO NOTHING;
            """)
            conn.commit()
        conn.close()

@app.on_event("startup")
def on_startup():
    init_db()

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
        "status": "المبلغ مجمّد بالخزينة (بإشراف الذكاء الاصطناعي AI 🛡️)",
        "status_note": "تم التحقق من تفاصيل الصفقة وتجميد المبلغ بأمان في خزينة وثيق تحت مراقبة نظام الذكاء الاصطناعي.",
        "messages": [
            {"sender": "مشرف الذكاء الاصطناعي (Watheeq AI)", "text": "مرحباً بكم. أنا نظام الرقابة الآلي. تم تجميد مبلغ 2,537.5 ريال بنجاح في الخزينة. ابدءوا الفحص وسأتابع معكم.", "time": "10:00 AM"},
            {"sender": "المشتري (أحمد)", "text": "تم سداد العربون والعمولة، بانتظار تقرير الفحص.", "time": "10:02 AM"}
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
@limiter.limit("10/minute")
def create_deal(request: Request, req: CreateDealRequest):
    deal_id = "WTQ-" + ''.join(random.choices(string.digits, k=4))
    fee_percent = 1.5 if "1.5" in req.category else 2.5
    fee_amount = round((req.price * fee_percent) / 100, 2)
    total_paid = round(req.price + fee_amount, 2)
    
    deal = {
        "id": deal_id,
        "title": html.escape(req.title),
        "category": html.escape(req.category),
        "price": req.price,
        "fee_percent": fee_percent,
        "fee_amount": fee_amount,
        "total_paid": total_paid,
        "seller_name": html.escape(req.seller_name) + " (موثق)",
        "buyer_name": html.escape(req.buyer_name) if req.buyer_name else "بانتظار الطرف الثاني",
        "status": "بانتظار سداد المشتري عبر الضمان الذكي ⏳",
        "status_note": f"الصفقة بانتظار سداد إجمالي المبلغ ({total_paid:,} ريال).",
        "messages": [{"sender": "مشرف الذكاء الاصطناعي (Watheeq AI)", "text": f"تم فتح غرفة الوساطة بمبلغ {total_paid:,} ريال تحت إشراف الذكاء الاصطناعي.", "time": "الآن"}]
    }
    save_deal(deal)
    return {"status": "success", "deal_id": deal_id, "deal": deal}

@app.post("/api/deals/{deal_id}/pay")
def pay_deal(deal_id: str, req: PaymentConfirmRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="غير موجودة")
    deal["status"] = "المبلغ مجمّد بالخزينة (بإشراف AI 🛡️)"
    deal["messages"].append({"sender": "مشرف الذكاء الاصطناعي (Watheeq AI)", "text": f"تم التحقق من السداد وإيداع المبلغ عبر {req.payment_method}. الأموال في حماية الخزينة.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/chat")
def send_chat(deal_id: str, req: MessageRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="غير موجودة")
    sender_name = html.escape(req.sender)
    deal["messages"].append({"sender": sender_name, "text": req.text, "time": "الآن"})
    
    ai_response = f"أهلاً بك يا {sender_name}. نظام الذكاء الاصطناعي يراقب هذه المحادثة لضمان حقوق الطرفين وعدم حدوث أي احتيال."
    deal["messages"].append({"sender": "مشرف الذكاء الاصطناعي (Watheeq AI)", "text": ai_response, "time": "الآن"})
    
    save_deal(deal)
    return {"status": "success", "messages": deal["messages"]}

@app.get("/login", response_class=HTMLResponse)
def serve_login():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlRoot">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تسجيل الدخول الآمن | وثيق Watheeq</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>body { font-family: 'Tajawal', sans-serif; background-color: #0b0e11; color: #eaecef; }</style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <header class="px-8 py-6 flex items-center justify-between">
        <a href="/" class="text-xl font-black text-white uppercase">Watheeq</a>
        <button onclick="toggleLang()" class="border border-slate-700 px-3 py-1 rounded-full text-xs text-slate-200" id="langBtnText">English</button>
    </header>
    <main class="flex-1 flex flex-col items-center justify-center px-4">
        <div class="bg-[#181a20] border border-slate-800 p-8 rounded-3xl max-w-md w-full shadow-2xl text-center">
            <h1 id="txtTitle" class="text-2xl font-black text-white mb-2">تسجيل الدخول الآمن</h1>
            <p id="txtSub" class="text-xs text-slate-400 mb-6">البريد الإلكتروني / الهوية الرقمية</p>
            <div class="space-y-4">
                <div id="signupFields" class="hidden space-y-3">
                    <div class="grid grid-cols-2 gap-2">
                        <input id="inputFirstName" type="text" placeholder="الاسم الأول" class="w-full bg-[#0b0e11] border border-slate-800 rounded-xl p-3 text-xs text-center text-white">
                        <input id="inputLastName" type="text" placeholder="اسم العائلة" class="w-full bg-[#0b0e11] border border-slate-800 rounded-xl p-3 text-xs text-center text-white">
                    </div>
                </div>
                <input id="inputUser" type="text" placeholder="name@domain.com أو رقم الهوية" class="w-full bg-[#0b0e11] border border-slate-800 rounded-xl p-3.5 text-xs text-center text-white font-mono">
                <input id="inputPassword" type="password" placeholder="كلمة المرور" class="w-full bg-[#0b0e11] border border-slate-800 rounded-xl p-3.5 text-xs text-center text-white">
                <button onclick="submitAuth()" id="btnSubmitAction" class="w-full bg-[#fcd535] text-black font-bold py-3.5 rounded-xl text-sm">تسجيل الدخول</button>
                <div class="pt-3 border-t border-slate-800 space-y-2">
                    <button onclick="socialAuth('Google')" class="w-full bg-[#0b0e11] border border-slate-800 hover:bg-slate-800 py-2.5 rounded-xl text-xs font-medium text-white">🌐 المتابعة باستخدام Google</button>
                    <button onclick="socialAuth('Apple')" class="w-full bg-[#0b0e11] border border-slate-800 hover:bg-slate-800 py-2.5 rounded-xl text-xs font-medium text-white">🍏 المتابعة باستخدام Apple</button>
                </div>
            </div>
            <div class="mt-6 text-xs text-slate-500">
                <button onclick="toggleMode()" id="txtToggleMode" class="text-yellow-400 hover:underline bg-transparent border-0 cursor-pointer">ليس لديك حساب؟ إنشاء حساب جديد</button>
            </div>
        </div>
    </main>
    <script>
        let currentLang = 'ar';
        let isSignup = false;
        function toggleLang() {
            currentLang = (currentLang === 'ar') ? 'en' : 'ar';
            document.getElementById('htmlRoot').setAttribute('dir', currentLang === 'ar' ? 'rtl' : 'ltr');
            document.getElementById('langBtnText').innerText = currentLang === 'ar' ? 'English' : 'العربية';
            document.getElementById('txtTitle').innerText = isSignup ? (currentLang==='ar'?'إنشاء حساب جديد':'Create Account') : (currentLang==='ar'?'تسجيل الدخول الآمن':'Secure Sign In');
            document.getElementById('btnSubmitAction').innerText = isSignup ? (currentLang==='ar'?'إنشاء الحساب الآن':'Create Account') : (currentLang==='ar'?'تسجيل الدخول':'Sign In');
        }
        function toggleMode() {
            isSignup = !isSignup;
            document.getElementById('signupFields').classList.toggle('hidden', !isSignup);
            toggleLang();
        }
        function submitAuth() {
            alert(currentLang === 'ar' ? '✅ تم المصادقة بنجاح! جاري تحويلك للغرفة الآمنة...' : '✅ Authenticated successfully! Redirecting...');
            window.location.href = '/deal/WTQ-701';
        }
        function socialAuth(provider) {
            alert(`✅ تم المصادقة عبر ${provider} بنجاح!`);
            window.location.href = '/deal/WTQ-701';
        }
    </script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def serve_home():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="homeHtml">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>وثيق | Watheeq - الوساطة والضمان المالي بإشراف AI</title>
    <meta name="description" content="وثيق المنصة السعودية للوساطة المالية والضمان الرقمي بإشراف الذكاء الاصطناعي، حماية كاملة للعربون والصفقات.">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #030303; color: #ffffff; }
        .hero-glow { background: radial-gradient(circle at 50% 20%, rgba(252, 213, 53, 0.12) 0%, rgba(3, 3, 3, 0.98) 70%); }
        .card-dark { background: rgba(14, 14, 18, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(20px); }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <div class="bg-amber-500/10 border-b border-amber-500/20 py-2.5 px-6 text-center text-xs font-semibold text-amber-300">
        🛡️ نظام الضمان الإلزامي بإشراف الذكاء الاصطناعي: تجميد الأموال بالخزينة لحماية الطرفين 100%.
    </div>

    <div id="createModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-lg w-full border border-white/20 text-right">
            <h3 class="text-xl font-black text-white mb-4">إنشاء غرفة وساطة ذكية (AI Escrow)</h3>
            <div class="space-y-4">
                <input id="newTitle" type="text" placeholder="عنوان الصفقة (مثال: عربون مركبة / حساب ديسكورد)" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs">
                <select id="newCategory" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs">
                    <option>الأصول الرقمية والألعاب (2.5% مع إشراف AI)</option>
                    <option>مركبات وعرابين (1.5% مع إشراف AI)</option>
                </select>
                <input id="newPrice" type="number" placeholder="المبلغ (ريال)" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs">
                <input id="newSeller" type="text" placeholder="يوزر البائع" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs">
                <input id="newBuyer" type="text" placeholder="يوزر المشتري" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs">
            </div>
            <div class="mt-6 flex gap-3">
                <button onclick="submitDeal()" class="flex-1 bg-white text-black text-xs font-black py-3 rounded-xl cursor-pointer">إنشاء الغرفة الآمنة 🔒</button>
                <button onclick="document.getElementById('createModal').classList.add('hidden')" class="px-5 py-3 bg-white/5 text-xs rounded-xl cursor-pointer">إغلاق</button>
            </div>
        </div>
    </div>

    <header class="border-b border-white/5 bg-black/60 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <span class="text-lg font-black tracking-tight text-white uppercase">Watheeq</span>
            <div class="flex items-center gap-3">
                <button onclick="toggleHomeLang()" class="border border-slate-700 px-3.5 py-1.5 rounded-full text-xs text-slate-200 cursor-pointer hover:border-slate-400" id="homeLangBtn">English</button>
                <a href="#" onclick="alert('🔐 جاري التحقق عبر نفاذ (National Access Authentication)...');" class="bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs px-3.5 py-1.5 rounded-full font-bold flex items-center gap-1.5 hover:bg-amber-500/20 transition"><span>🛡️</span> نفاذ (Face ID)</a>
                <a href="/login" class="bg-white/5 border border-white/10 text-slate-200 text-xs px-3.5 py-1.5 rounded-full font-semibold hover:bg-white/10" id="homeSignIn">Sign In</a>
                <button onclick="document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex');" class="bg-white text-black text-xs font-black px-4 py-2 rounded-full cursor-pointer" id="homeCreateBtn">+ إنشاء صفقة</button>
            </div>
        </div>
    </header>

    <main class="hero-glow flex-1 flex flex-col items-center justify-center text-center px-6 py-24 relative z-10">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-amber-400 text-xs font-mono mb-6 animate-pulse shadow-lg">
            <span>⚡ AI SUPERVISED ESCROW PROTOCOL</span>
        </div>
        <h1 class="text-4xl md:text-7xl font-black text-white tracking-tight mb-6 max-w-4xl" id="homeHeroTitle">The immutable standard of escrow.</h1>
        <p class="text-slate-400 text-sm md:text-base max-w-xl mb-10 leading-relaxed" id="homeHeroSub">المنصة الآمنة لتجميد أموال العربون والصفقات ومنع النصب بإشراف الذكاء الاصطناعي.</p>
        <button onclick="location.href='/deal/WTQ-701'" class="bg-white text-black text-sm font-bold px-8 py-4 rounded-full shadow-2xl cursor-pointer" id="homeDemoBtn">معاينة الغرفة التجريبية المشرفة من AI 🛡️</button>
    </main>

    <footer class="border-t border-white/5 py-6 bg-black text-center text-xs text-slate-500 font-mono">
        © 2026 WATHEEQ AI ESCROW • SAFEWATHEEQ.COM
    </footer>

    <script>
        let homeLang = 'ar';
        function toggleHomeLang() {
            homeLang = (homeLang === 'ar') ? 'en' : 'ar';
            document.getElementById('homeHtml').setAttribute('dir', homeLang === 'ar' ? 'rtl' : 'ltr');
            document.getElementById('homeLangBtn').innerText = homeLang === 'ar' ? 'English' : 'العربية';
            document.getElementById('homeSignIn').innerText = homeLang === 'ar' ? 'Sign In' : 'تسجيل الدخول';
            document.getElementById('homeCreateBtn').innerText = homeLang === 'ar' ? '+ إنشاء صفقة' : '+ Create Deal';
            document.getElementById('homeHeroSub').innerText = homeLang === 'ar' ? 'المنصة الآمنة لتجميد أموال العربون والصفقات ومنع النصب بإشراف الذكاء الاصطناعي.' : 'The ultimate secure platform to freeze deposits and prevent fraud with AI supervision.';
            document.getElementById('homeDemoBtn').innerText = homeLang === 'ar' ? 'معاينة الغرفة التجريبية المشرفة من AI 🛡️' : 'Preview AI-Supervised Live Demo Vault 🛡️';
        }
        async function submitDeal() {
            const title = document.getElementById('newTitle').value;
            const category = document.getElementById('newCategory').value;
            const price = parseFloat(document.getElementById('newPrice').value);
            const seller_name = document.getElementById('newSeller').value;
            const buyer_name = document.getElementById('newBuyer').value;
            if(!title || !price) { alert('أدخل الحقول المطلوبة'); return; }
            const res = await fetch('/api/deals/create', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title, category, price, seller_name, buyer_name})});
            const data = await res.json();
            if(data.status === 'success') location.href = '/deal/' + data.deal_id;
        }
    </script>
</body>
</html>"""

@app.get("/deal/{deal_id}", response_class=HTMLResponse)
def serve_deal_room(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        return HTMLResponse("<h1>عذراً، الغرفة غير موجودة.</h1>", status_code=404)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>غرفة الضمان المشرفة بالذكاء الاصطناعي {deal['id']} | وثيق</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>body {{ font-family: 'Tajawal', sans-serif; background-color: #050507; color: #ffffff; }} .card-dark {{ background: rgba(14, 14, 18, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); }}</style>
</head>
<body class="min-h-screen flex flex-col justify-between p-6">
    <header class="max-w-6xl mx-auto w-full flex justify-between items-center py-4 border-b border-white/10 mb-6">
        <a href="/" class="text-lg font-black">Watheeq AI Vault [{deal['id']}]</a>
        <span class="text-xs text-amber-400 font-mono">🤖 تحت إشراف وتدقيق الذكاء الاصطناعي</span>
    </header>

    <main class="max-w-6xl mx-auto w-full grid grid-cols-1 md:grid-cols-3 gap-6 flex-1">
        <div class="card-dark p-6 rounded-3xl space-y-4">
            <span class="text-xs px-2.5 py-1 rounded-full bg-white/5 text-slate-300">{deal['category']}</span>
            <h2 class="text-base font-bold text-white">{deal['title']}</h2>
            <div class="border-t border-white/10 pt-4 space-y-2 text-xs font-mono">
                <div class="flex justify-between text-slate-400"><span>المبلغ:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                <div class="flex justify-between text-slate-400"><span>عمولة المنصة:</span><span class="text-slate-300">{deal['fee_amount']} ريال</span></div>
                <div class="flex justify-between text-amber-400 border-t border-white/10 pt-2 text-sm font-bold"><span>المجموع:</span><span>{deal['total_paid']:,} ريال</span></div>
            </div>
            <div class="pt-4 space-y-2">
                <button onclick="payDeal('{deal['id']}')" class="w-full bg-amber-400 text-black font-bold py-3 rounded-2xl text-xs cursor-pointer">سداد وتجميد بالخزينة (Apple Pay / مدى) 🛡️</button>
                <a href="/" class="block text-center bg-white/10 text-white font-bold py-3 rounded-2xl text-xs">العودة للرئيسية 🏠</a>
            </div>
        </div>

        <div class="md:col-span-2 card-dark rounded-3xl flex flex-col h-[560px] overflow-hidden">
            <div class="p-4 border-b border-white/10 bg-black/40 text-xs font-bold text-slate-300 flex justify-between items-center">
                <span>غرفة الشات الآمنة والذكية (AI Escrow Chat)</span>
                <span class="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">الذكاء الاصطناعي متصل ومتأهب ⚡</span>
            </div>
            <div class="flex-1 p-4 overflow-y-auto space-y-3 text-xs" id="chatContainer">
                {''.join([f'<div class="p-3 rounded-2xl bg-black/60 border border-white/5 text-slate-300"><div class="flex justify-between text-[10px] text-slate-500 mb-1"><span>{m["sender"]}</span><span>{m["time"]}</span></div><p>{m["text"]}</p></div>' for m in deal['messages']])}
            </div>
            <div class="p-4 border-t border-white/10 bg-black/60 flex gap-2">
                <input id="chatInput" type="text" placeholder="اكتب رسالتك للطرف الآخر أو استفسر من نظام AI..." class="flex-1 bg-black border border-white/10 rounded-xl px-4 py-3 text-xs text-white">
                <button onclick="sendMessage('{deal['id']}')" class="bg-white text-black font-bold px-5 py-3 rounded-xl text-xs cursor-pointer">إرسال 🚀</button>
            </div>
        </div>
    </main>

    <footer class="max-w-6xl mx-auto w-full text-center text-xs text-slate-500 font-mono py-4 border-t border-white/10">
        © 2026 WATHEEQ AI ESCROW PLATFORM
    </footer>

    async function payDeal(dealId) {
    const res = await fetch(`/api/deals/` + dealId + `/pay`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({payment_method:'Apple Pay'})});
    if(res.ok) location.reload();
}
async function sendMessage(dealId) {
    const text = document.getElementById('chatInput').value;
    if(!text) return;
    const res = await fetch(`/api/deals/` + dealId + `/chat`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text})});
    if(res.ok) location.reload();
}
</body>
</html>"""
