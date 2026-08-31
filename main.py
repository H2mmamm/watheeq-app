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
        "status": "بانتظار سداد المشتري للضمان والعمولة عبر (Apple Pay / مدى) ⏳",
        "status_note": f"الصفقة بانتظار سداد إجمالي المبلغ ({total_paid:,} ريال).",
        "messages": [{"sender": "النظام", "text": f"تم فتح غرفة الضمان بمبلغ {total_paid:,} ريال.", "time": "الآن"}]
    }
    save_deal(deal)
    return {"status": "success", "deal_id": deal_id, "deal": deal}

@app.post("/api/deals/{deal_id}/pay")
def pay_deal(deal_id: str, req: PaymentConfirmRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="غير موجودة")
    deal["status"] = "المبلغ مجمّد بالخزينة 🛡️ ⏳"
    deal["messages"].append({"sender": "النظام", "text": f"تم إيداع المبلغ عبر {req.payment_method}.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/release")
def release_funds(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="غير موجودة")
    deal["status"] = "تم التسليم وتحويل المستحقات للبائع ✅"
    deal["messages"].append({"sender": "النظام", "text": "تم تأكيد الاستلام وتحويل المبلغ للبائع.", "time": "الآن"})
    save_deal(deal)
    return deal

@app.post("/api/deals/{deal_id}/chat")
def send_chat(deal_id: str, req: MessageRequest):
    deal = fetch_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="غير موجودة")
    deal["messages"].append({"sender": html.escape(req.sender), "text": req.text, "time": "الآن"})
    save_deal(deal)
    return {"status": "success", "messages": deal["messages"]}

@app.get("/", response_class=HTMLResponse)
def serve_home():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="homeHtml">
<head>
    <meta charset="UTF-8">
    <title>وثيق | Watheeq - الوساطة والضمان المالي</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap" rel="stylesheet">
    <style>body { font-family: 'Tajawal', sans-serif; background: #030303; color: #fff; }</style>
</head>
<body class="min-h-screen flex flex-col justify-between p-6 text-center">
    <div>
        <h1 class="text-5xl font-black mt-20 mb-6">Watheeq Vault</h1>
        <p class="text-slate-400 mb-8">المنصة الآمنة لتجميد أموال العربون والصفقات ومنع النصب.</p>
        <a href="/deal/WTQ-701" class="bg-white text-black font-bold px-8 py-3 rounded-full">معاينة الغرفة التجريبية 🛡️</a>
    </div>
    <footer class="text-xs text-slate-600">© 2026 WATHEEQ</footer>
</body>
</html>"""

@app.get("/deal/{deal_id}", response_class=HTMLResponse)
def serve_deal_room(deal_id: str):
    deal = fetch_deal(deal_id)
    if not deal:
        return HTMLResponse("<h1>الغرفة غير موجودة</h1>", status_code=404)
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>غرفة {deal['id']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-black text-white p-6">
    <h1 class="text-2xl font-bold mb-4">{deal['title']}</h1>
    <p class="text-emerald-400 mb-4">الحالة: {deal['status']}</p>
    <a href="/" class="text-xs text-slate-400 underline">الرئيسية</a>
</body>
</html>"""
