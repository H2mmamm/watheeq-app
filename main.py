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

app = FastAPI(title="وثيق | Watheeq - Escrow & Marketplace Platform")

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
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' https://cdn.tailwindcss.com https://fonts.googleapis.com https://fonts.gstatic.com; "
        "img-src 'self' https: data: blob:; "
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

@app.post("/api/deals/{deal_id}/chat")
@limiter.limit("30/minute")
def send_chat(request: Request, deal_id: str, req: MessageRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    
    text = req.text
    if any(k in text for k in ["http://", "https://", "snapchat", "whatsapp", "واتساب", "سناب", "05"]):
        text = "⚠️ [تنبيه أمان وثيق]: تم حجب محتوى التواصل الخارجي لضمان سلامة الضمان المالي."

    msg = {"sender": html.escape(req.sender), "text": html.escape(text), "time": "الآن"}
    deal["messages"].append(msg)
    save_deal(deal)
    return {"status": "success", "messages": deal["messages"]}

@app.get("/verify", response_class=HTMLResponse)
def serve_verify_page():
    return """<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
    <meta charset="UTF-8">
    <title>Watheeq | Verify Document</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>body { background-color: #030303; color: #ffffff; font-family: sans-serif; }</style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-6 text-center">
    <h1 class="text-3xl font-bold mb-4">Verify Watheeq Vault Record</h1>
    <input id="did" type="text" placeholder="WTQ-701" class="bg-black border border-white/20 p-3 rounded-xl text-center text-white font-mono mb-4 w-64">
    <button onclick="location.href='/deal/'+document.getElementById('did').value" class="bg-white text-black font-bold px-6 py-2.5 rounded-xl text-xs">Inspect Record</button>
</body>
</html>"""

@app.get("/login", response_class=HTMLResponse)
def serve_login():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول | وثيق</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-[#0b0e11] text-[#eaecef] flex items-center justify-center p-4">
    <div class="bg-[#181a20] border border-[#23272f] p-8 rounded-3xl max-w-md w-full text-center">
        <h1 class="text-2xl font-black text-white mb-4">تسجيل الدخول الآمن</h1>
        <input type="text" placeholder="البريد أو رقم الهوية" class="w-full bg-[#0b0e11] border border-[#23272f] rounded-xl p-3 text-white mb-4 text-sm">
        <button onclick="location.href='/deal/WTQ-701'" class="w-full bg-[#fcd535] text-black font-bold py-3 rounded-xl text-sm">متابعة الغرفة التجريبية</button>
    </div>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def serve_home():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>وثيق | Watheeq - الوساطة والضمان المالي المعتمد</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #030303; color: #ffffff; }
        .card-dark { background: rgba(14, 14, 18, 0.75); border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(20px); }
        .btn-white { background: #ffffff; color: #000000; transition: all 0.2s; }
        .btn-white:hover { background: #e2e8f0; transform: scale(1.02); }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">
    <div class="bg-amber-500/10 border-b border-amber-500/20 py-2.5 px-6 text-center text-xs font-semibold text-amber-300">
        🛡️ حماية الوساطة الإلزامية: تجميد الأموال بالخزينة يضمن حقوق البائع والمشتري بنسبة 100%.
    </div>

    <!-- نافذة إنشاء صفقة -->
    <div id="createModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-lg w-full border border-white/20 text-right">
            <h3 class="text-xl font-black text-white mb-1">إنشاء غرفة وساطة جديدة</h3>
            <div class="space-y-4 mt-4">
                <input id="newTitle" type="text" placeholder="عنوان الصفقة (مثال: عربون سيارة / حساب)" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm">
                <select id="newCategory" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm">
                    <option>الأصول الرقمية والألعاب (2.5%)</option>
                    <option>مركبات وعرابين (1.5%)</option>
                </select>
                <input id="newPrice" type="number" placeholder="المبلغ (ريال)" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm">
                <input id="newSeller" type="text" placeholder="يوزر البائع" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm">
                <input id="newBuyer" type="text" placeholder="يوزر المشتري" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-sm">
            </div>
            <div class="mt-6 flex gap-3">
                <button onclick="submitDeal()" class="flex-1 btn-white text-xs font-black py-3 rounded-xl">إنشاء الغرفة الآمنة 🔒</button>
                <button onclick="document.getElementById('createModal').classList.add('hidden')" class="px-5 py-3 bg-white/5 text-xs rounded-xl">إغلاق</button>
            </div>
        </div>
    </div>

    <!-- لوحة تحكم البنك وأرباح المنصة -->
    <div id="bankModal" class="fixed inset-0 bg-black/90 backdrop-blur-md hidden items-center justify-center p-4 z-50">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full border border-white/20 text-right">
            <h3 class="text-xl font-black text-white mb-2">🏦 ربط الحساب البنكي واستلام الأرباح</h3>
            <p class="text-xs text-slate-400 mb-6">اربط حسابك التجاري أو الآيبان (IBAN) لتحويل عمولات المنصة تلقائياً فور إتمام كل صفقة.</p>
            <div class="space-y-3 mb-6">
                <input type="text" placeholder="اسم صاحب الحساب التجاري" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs">
                <input type="text" placeholder="SA03 8000 ... (رقم الآيبان IBAN)" class="w-full bg-black/60 border border-white/10 rounded-xl p-3 text-white text-xs font-mono">
            </div>
            <button onclick="alert('✅ تم ربط الحساب البنكي بنجاح! سيتم تحويل عوائد العمولات فورياً.'); document.getElementById('bankModal').classList.add('hidden')" class="w-full btn-white py-3 rounded-xl font-bold text-xs">حفظ وربط الحساب البنكي 💳</button>
            <button onclick="document.getElementById('bankModal').classList.add('hidden')" class="w-full pt-3 text-slate-500 text-xs">إغلاق</button>
        </div>
    </div>

    <header class="border-b border-white/5 bg-black/60 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <span class="text-lg font-black tracking-tight text-white uppercase">Watheeq</span>
            <div class="flex items-center gap-3">
                <button onclick="document.getElementById('bankModal').classList.remove('hidden'); document.getElementById('bankModal').classList.add('flex');" class="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs px-3.5 py-1.5 rounded-full font-bold">💳 ربط الحساب البنكي للعمولات</button>
                <button onclick="document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex');" class="btn-white text-xs font-black px-4 py-2 rounded-full">+ إنشاء صفقة</button>
            </div>
        </div>
    </header>

    <main class="flex-1 flex flex-col items-center justify-center text-center px-6 py-20">
        <h1 class="text-4xl md:text-6xl font-black text-white tracking-tight mb-6">The immutable standard of escrow.</h1>
        <p class="text-slate-400 text-sm max-w-xl mb-8">المنصة الآمنة لتجميد أموال العربون والصفقات ومنع النصب المالي تماماً.</p>
        <button onclick="location.href='/deal/WTQ-701'" class="btn-white text-sm font-bold px-8 py-3.5 rounded-full">معاينة الغرفة التجريبية النشطة 🛡️</button>
    </main>

    <footer class="border-t border-white/5 py-6 bg-black text-center text-xs text-slate-500 font-mono">
        © 2026 WATHEEQ ESCROW & MARKETPLACE
    </footer>

    <script>
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
    is_pending = ("بانتظار" in deal['status'])
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>غرفة الضمان المالي {deal['id']} | وثيق</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>body {{ font-family: 'Tajawal', sans-serif; background-color: #050507; color: #ffffff; }} .card-dark {{ background: rgba(14, 14, 18, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); }}</style>
</head>
<body class="min-h-screen flex flex-col justify-between p-6">
    <div id="payModal" class="fixed inset-0 bg-black/90 z-50 backdrop-blur-md hidden items-center justify-center p-4">
        <div class="card-dark p-8 rounded-3xl max-w-md w-full border border-white/20 text-center shadow-2xl">
            <h3 class="text-xl font-bold text-white mb-2">إيداع الضمان المالي بالخزينة</h3>
            <p class="text-xs text-slate-400 mb-6 font-mono">الإجمالي شاملاً العمولة: <span class="text-emerald-400 font-bold">{deal['total_paid']:,} ريال</span></p>
            <div class="space-y-3">
                <button onclick="pay('Apple Pay ')" class="w-full bg-white text-black font-bold py-3.5 rounded-2xl text-xs">الدفع عبر Apple Pay</button>
                <button onclick="pay('بطاقة مدى Mada')" class="w-full bg-white/5 border border-white/10 text-white font-medium py-3.5 rounded-2xl text-xs">الدفع عبر بطاقة مدى</button>
                <button onclick="document.getElementById('payModal').classList.add('hidden')" class="text-xs text-slate-500 pt-2">إلغاء</button>
            </div>
        </div>
    </div>

    <header class="max-w-6xl mx-auto w-full flex justify-between items-center py-4 border-b border-white/10 mb-6">
        <a href="/" class="text-lg font-black">Watheeq Vault [{deal['id']}]</a>
        <span class="text-xs text-emerald-400 font-mono">🛡️ شات آمن ومراقب</span>
    </header>

    <main class="max-w-6xl mx-auto w-full grid grid-cols-1 md:grid-cols-3 gap-6 flex-1">
        <div class="card-dark p-6 rounded-3xl space-y-4">
            <span class="text-xs px-2.5 py-1 rounded-full bg-white/5 text-slate-300">{deal['category']}</span>
            <h2 class="text-base font-bold text-white">{deal['title']}</h2>
            <div class="border-t border-white/10 pt-4 space-y-2 text-xs font-mono">
                <div class="flex justify-between text-slate-400"><span>المبلغ:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                <div class="flex justify-between text-slate-400"><span>عمولة المنصة:</span><span class="text-slate-300">{deal['fee_amount']} ريال</span></div>
                <div class="flex justify-between text-emerald-400 border-t border-white/10 pt-2 text-sm font-bold"><span>المجموع:</span><span>{deal['total_paid']:,} ريال</span></div>
            </div>
            <div class="pt-4">
                {'<button onclick="document.getElementById(\'payModal\').classList.remove(\'hidden\'); document.getElementById(\'payModal\').classList.add(\'flex\');" class="w-full bg-white text-black font-bold py-3 rounded-2xl text-xs">إيداع وتجميد المبلغ بالخزينة 🔒</button>' if is_pending else '<button onclick="release()" class="w-full bg-emerald-600 text-white font-bold py-3 rounded-2xl text-xs">تأكيد الاستلام وتحويل للبائع ✅</button>'}
            </div>
        </div>

        <div class="md:col-span-2 card-dark rounded-3xl flex flex-col h-[540px] overflow-hidden">
            <div class="p-4 border-b border-white/10 bg-black/40 text-xs font-bold text-slate-300">سجل الشات (يدعم إرسال صور ومقاطع فحص المنتج)</div>
            <div class="flex-1 p-4 overflow-y-auto space-y-3 text-xs" id="chatContainer">
                {''.join([f'<div class="p-3 rounded-2xl bg-black/60 border border-white/5 text-slate-300"><div class="flex justify-between text-[10px] text-slate-500 mb-1"><span>{m["sender"]}</span><span>{m["time"]}</span></div><p>{m["text"]}</p></div>' for m in deal['messages']])}
            </div>
            
            <!-- شريط الكتابة ورفع الصور والفيديو -->
            <div class="p-3 border-t border-white/10 bg-black/40 flex items-center gap-2">
                <label class="cursor-pointer bg-white/10 hover:bg-white/20 text-white px-3 py-2.5 rounded-2xl text-xs flex items-center gap-1 transition" title="رفع صورة أو فيديو">
                    <span>📷 تصوير/رفع</span>
                    <input type="file" id="mediaFile" accept="image/*,video/*" class="hidden" onchange="handleMediaUpload(this)">
                </label>
                <input id="txt" type="text" placeholder="اكتب رسالة أو تفاصيل الفحص..." class="flex-1 bg-black/60 border border-white/10 rounded-2xl px-4 py-2.5 text-xs text-white outline-none" onkeydown="if(event.key==='Enter') sendText()">
                <button onclick="sendText()" class="bg-white text-black font-bold px-5 py-2.5 rounded-2xl text-xs">إرسال</button>
            </div>
        </div>
    </main>

    <script>
        const dealId = "{deal['id']}";
        async function pay(m) {
            const res = await fetch('/api/deals/'+dealId+'/pay', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({payment_method:m})});
            if(res.ok) location.reload();
        }
        async function release() {
            if(!confirm('هل أنت متأكد من استلام السلعة؟')) return;
            const res = await fetch('/api/deals/'+dealId+'/release', {method:'POST'});
            if(res.ok) location.reload();
        }
        async function sendText() {
            const i = document.getElementById('txt');
            if(!i.value.trim()) return;
            await postMsg('المستخدم', i.value);
            i.value='';
        }
        async function handleMediaUpload(input) {
            if (input.files && input.files[0]) {
                const file = input.files[0];
                const reader = new FileReader();
                reader.onload = async function(e) {
                    const htmlContent = file.type.startsWith('image') 
                        ? `<img src="${e.target.result}" class="max-w-xs rounded-xl mt-2 border border-white/10">` 
                        : `<video src="${e.target.result}" controls class="max-w-xs rounded-xl mt-2 border border-white/10"></video>`;
                    await postMsg('المستخدم (صورة/فيديو مرفق)', htmlContent);
                };
                reader.readAsDataURL(file);
            }
        }
        async function postMsg(sender, text) {
            const res = await fetch('/api/deals/'+dealId+'/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({sender, text})});
            if(res.ok) location.reload();
        }
    </script>
</body>
</html>"""
