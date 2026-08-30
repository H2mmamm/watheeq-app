from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from enum import Enum
import html
import random
import string
import time

app = FastAPI(title="منصة وثيق للضمان والوساطة")

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

class EscrowStatus(str, Enum):
    PENDING_DEPOSIT = "بانتظار الإيداع وتجميد المبلغ ⏳"
    ACTIVE = "الصفقة جارية (المبلغ محجوز بأمان) 🛡️"
    COMPLETED = "تم التسليم وتحويل المبلغ للبائع بنجاح ✅"
    DISPUTED = "تم إيقاف الصفقة (نزاع تحت مراجعة الإدارة) ⚠️"
    AUTO_REFUNDED = "تم استرجاع المبلغ للمشتري ↩️"

# قاعدة بيانات مؤقتة للصفقات
deals_db = {}

# صفقة تجريبية أولية
deals_db["WTQ-701"] = {
    "id": "WTQ-701",
    "title": "عربون وضمان مبايعة سيارة ونقل ملكية",
    "category": "مركبات ومعدات (1.5%)",
    "price": 10000.0,
    "fee_percent": 1.5,
    "fee_amount": 150.0,
    "total_paid": 10150.0,
    "seller_name": "سعد الشمري",
    "buyer_name": "أحمد المالكي",
    "status": EscrowStatus.ACTIVE,
    "status_note": "المبلغ مجمّد بالكامل في خزينة وثيق. بانتظار تسليم البائع.",
    "messages": [
        {"sender": "النظام", "text": "تم تجميد المبلغ بقيمة 10,000 ريال بنجاح في خزينة وثيق 🔒", "time": "10:00 AM"},
        {"sender": "المشتري (أحمد)", "text": "أهلاً سعد، تم إيداع المبلغ. بانتظار إتمام المبايعة ونقل الملكية.", "time": "10:02 AM"}
    ]
}

class CreateDealRequest(BaseModel):
    title: str = Field(..., max_length=150)
    category: str
    price: float = Field(..., gt=0)
    seller_name: str = Field(..., max_length=50)
    buyer_name: str = Field(default="", max_length=50)

class MessageRequest(BaseModel):
    sender: str
    text: str

# API لإنشاء صفقة برابط فريد
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
        "seller_name": clean_seller,
        "buyer_name": clean_buyer,
        "status": EscrowStatus.ACTIVE,
        "status_note": "تم إنشاء الصفقة وتجميد الضمان المالي في خزينة وثيق.",
        "messages": [
            {"sender": "النظام", "text": f"تم إنشاء الغرفة وتجميد الضمان المالي للصفقة ({clean_title}) بقيمة {req.price:,} ريال.", "time": "الآن"}
        ]
    }
    deals_db[deal_id] = deal
    return {"status": "success", "deal_id": deal_id, "deal": deal}

# API تأكيد الاستلام
@app.post("/api/deals/{deal_id}/release")
def release_funds(deal_id: str):
    if deal_id not in deals_db:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deals_db[deal_id]["status"] = EscrowStatus.COMPLETED
    deals_db[deal_id]["status_note"] = "تم تأكيد الاستلام من المشتري، وتم الإفراج عن المبلغ وتحويله للبائع بنجاح."
    deals_db[deal_id]["messages"].append({"sender": "النظام", "text": "✅ أكد المشتري استلام الطلب. تم تحويل المبلغ إلى حساب البائع.", "time": "الآن"})
    return deals_db[deal_id]

# API رفع نزاع
@app.post("/api/deals/{deal_id}/dispute")
def dispute_deal(deal_id: str):
    if deal_id not in deals_db:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    deals_db[deal_id]["status"] = EscrowStatus.DISPUTED
    deals_db[deal_id]["status_note"] = "تم رفع اعتراض وتجميد المستحقات تحت رقابة فريق الإدارة والتحكيم المالي."
    deals_db[deal_id]["messages"].append({"sender": "النظام", "text": "⚠️ تم رفع نزاع وتجميد العملية. سيتدخل فريق وثيق للتحقق من الإثباتات.", "time": "الآن"})
    return deals_db[deal_id]

# API إرسال رسالة في الشات
@app.post("/api/deals/{deal_id}/chat")
def send_chat(deal_id: str, req: MessageRequest):
    if deal_id not in deals_db:
        raise HTTPException(status_code=404, detail="الصفقة غير موجودة")
    msg = {"sender": html.escape(req.sender), "text": html.escape(req.text), "time": "الآن"}
    deals_db[deal_id]["messages"].append(msg)
    return {"status": "success", "messages": deals_db[deal_id]["messages"]}

# الصفحة الرئيسية
@app.get("/", response_class=HTMLResponse)
def serve_home():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>وثيق | المنصة الشاملة لحماية وتأمين كافة الصفقات</title>
    
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://safewatheeq.com/">
    <meta property="og:title" content="وثيق | المنصة الشاملة للضمان والوساطة المالية">
    <meta property="og:description" content="ضمانك الأول لأي صفقة.. بيع واشتر في أي مجال وأنت مرتاح.">
    <meta property="og:image" content="https://safewatheeq.com/static/logo.png">

    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #090d16; color: #f8fafc; }
        .gold-btn { background: linear-gradient(135deg, #f59e0b, #d97706); }
        .card-bg { background: #0f172a; border: 1px solid #1e293b; }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">

    <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-black text-xl">و</div>
                <div>
                    <h1 class="text-xl font-black text-white">وثيق</h1>
                    <p class="text-xs text-amber-400/80 font-medium">الضمان والوساطة المالية الشاملة</p>
                </div>
            </div>
            <button onclick="openModal()" class="gold-btn text-slate-950 font-bold px-5 py-2.5 rounded-xl shadow-lg hover:opacity-90 transition">+ إنشاء صفقة آمنة</button>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-6 py-16 flex-1 flex flex-col items-center justify-center text-center">
        <div class="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-amber-400 text-sm font-semibold mb-6">
            🛡️ بوابتك المعتمدة لتأمين المعاملات والصفقات
        </div>
        <h2 class="text-4xl md:text-6xl font-black text-white leading-tight mb-6 max-w-3xl">
            ضمانك الأول لأي صفقة..<br><span class="text-amber-400">بيع واشتر في أي مجال وأنت مرتاح</span>
        </h2>
        <p class="text-slate-400 text-lg max-w-2xl mb-10 leading-relaxed">
            نحجز المبلغ في خزينة محايدة وآمنة، ولا يتم تحويل الريال للبائع إلا بعد فحص المشتري وتأكيده التام للاستلام.
        </p>

        <div class="flex flex-wrap justify-center gap-4">
            <button onclick="openModal()" class="gold-btn text-slate-950 font-black text-lg px-8 py-4 rounded-xl shadow-xl hover:scale-105 transition">ابدأ صفقة جديدة الآن ⚡</button>
            <a href="/deal/WTQ-701" class="border border-slate-700 bg-slate-900 text-white font-bold text-lg px-8 py-4 rounded-xl hover:bg-slate-800 transition">معاينة صفقة حية (WTQ-701) 👁️</a>
        </div>
    </main>

    <!-- Modal إنشاء صفقة -->
    <div id="createModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm hidden items-center justify-center p-4 z-50">
        <div class="card-bg p-8 rounded-2xl max-w-lg w-full text-right">
            <h3 class="text-xl font-bold text-white mb-4">إنشاء رابط صفقة وساطة جديد</h3>
            <div class="space-y-4">
                <div>
                    <label class="text-xs text-slate-400 block mb-1">عنوان الصفقة / الغرض</label>
                    <input id="newTitle" type="text" placeholder="مثال: شراء حساب / عربون سيارة / تصميم موقع" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
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
                        <label class="text-xs text-slate-400 block mb-1">اسم البائع</label>
                        <input id="newSeller" type="text" placeholder="اسمك أو يوزرك" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                    <div>
                        <label class="text-xs text-slate-400 block mb-1">اسم المشتري (اختياري)</label>
                        <input id="newBuyer" type="text" placeholder="اسم المشتري" class="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                </div>
            </div>
            <div class="mt-6 flex gap-3">
                <button onclick="submitDeal()" class="flex-1 gold-btn text-slate-950 font-bold py-3 rounded-xl">إنشاء الرابط وحجز الضمان</button>
                <button onclick="closeModal()" class="px-5 py-3 border border-slate-700 text-slate-400 rounded-xl">إلغاء</button>
            </div>
        </div>
    </div>

    <footer class="border-t border-slate-800 py-6 text-center text-xs text-slate-500">
        جميع الحقوق محفوظة © منصة وثيق للوساطة الآمنة | safewatheeq.com
    </footer>

    <script>
        function openModal() { document.getElementById('createModal').classList.remove('hidden'); document.getElementById('createModal').classList.add('flex'); }
        function closeModal() { document.getElementById('createModal').classList.add('hidden'); document.getElementById('createModal').classList.remove('flex'); }

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
    </script>
</body>
</html>"""

# صفحة غرفة الصفقة المستقلة
@app.get("/deal/{deal_id}", response_class=HTMLResponse)
def serve_deal_room(deal_id: str):
    if deal_id not in deals_db:
        return HTMLResponse("<h1>عذراً، الصفقة غير موجودة أو انتهت صلاحيتها.</h1>", status_code=404)
    
    deal = deals_db[deal_id]
    
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

    <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-40">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <a href="/" class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 font-black text-xl">و</div>
                <div>
                    <h1 class="text-xl font-black text-white">وثيق</h1>
                    <p class="text-xs text-amber-400/80 font-medium">غرفة الوساطة والضمان المشترك</p>
                </div>
            </a>
            <div class="flex items-center gap-2">
                <span class="text-xs bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 font-mono">رقم الصفقة: {deal['id']}</span>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-6 py-8 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 w-full">
        
        <!-- تفاصيل الصفقة والتحكم -->
        <div class="lg:col-span-1 space-y-6">
            <div class="card-bg p-6 rounded-2xl">
                <div class="flex justify-between items-center mb-4">
                    <span class="text-xs px-2.5 py-1 rounded-md bg-amber-500/20 text-amber-400 border border-amber-500/30">{deal['category']}</span>
                    <span id="dealStatusBadge" class="text-xs px-2.5 py-1 rounded-md bg-blue-500/20 text-blue-400 border border-blue-500/30 font-bold">{deal['status']}</span>
                </div>
                <h2 class="text-xl font-black text-white mb-4">{deal['title']}</h2>
                
                <div class="border-t border-slate-800 pt-4 space-y-2 text-sm">
                    <div class="flex justify-between text-slate-400"><span>المبلغ الأساسي:</span><span class="text-white font-bold">{deal['price']:,} ريال</span></div>
                    <div class="flex justify-between text-slate-400"><span>رسوم الوساطة ({deal['fee_percent']}%):</span><span class="text-amber-400 font-bold">{deal['fee_amount']} ريال</span></div>
                    <div class="flex justify-between text-slate-400 border-t border-slate-800 pt-2 text-base"><span>الإجمالي المحجوز:</span><span class="text-emerald-400 font-black">{deal['total_paid']:,} ريال</span></div>
                </div>

                <div class="border-t border-slate-800 mt-4 pt-4 text-xs space-y-1 text-slate-400">
                    <div>👤 البائع: <span class="text-white font-semibold">{deal['seller_name']}</span></div>
                    <div>👤 المشتري: <span class="text-white font-semibold">{deal['buyer_name']}</span></div>
                </div>
            </div>

            <!-- أزرار الإجراءات -->
            <div class="card-bg p-6 rounded-2xl space-y-3">
                <h4 class="text-sm font-bold text-white mb-2">إجراءات الأمان والتحكم</h4>
                <button onclick="confirmRelease()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 rounded-xl transition">✅ تأكيد الاستلام وتحويل المبلغ للبائع</button>
                <button onclick="raiseDispute()" class="w-full bg-rose-600/20 border border-rose-500/40 hover:bg-rose-600/30 text-rose-400 font-bold py-2.5 rounded-xl transition text-xs">⚠️ رفع نزاع وتجميد الصفقة</button>
                <button onclick="copyDealLink()" class="w-full bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold py-2.5 rounded-xl transition text-xs">🔗 نسخ رابط الصفقة للطرف الآخر</button>
            </div>
        </div>

        <!-- غرفة المحادثة المباشرة والإثباتات -->
        <div class="lg:col-span-2 card-bg rounded-2xl flex flex-col h-[600px] overflow-hidden">
            <div class="p-4 border-b border-slate-800 bg-slate-900/50 flex justify-between items-center">
                <div class="flex items-center gap-2">
                    <div class="w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
                    <span class="text-sm font-bold text-white">المحادثة الآمنة وتوثيق التسليم</span>
                </div>
                <span class="text-xs text-slate-400">مشفرة وموثقة لدى وثيق 🔒</span>
            </div>

            <!-- الرسائل -->
            <div id="chatBox" class="flex-1 p-4 overflow-y-auto space-y-3 text-sm">
                {''.join([f'<div class="p-3 rounded-xl {"bg-amber-500/10 border border-amber-500/20 text-amber-300" if m["sender"]=="النظام" else "bg-slate-800 text-slate-200"}"><div class="flex justify-between text-xs opacity-60 mb-1"><span>{m["sender"]}</span><span>{m["time"]}</span></div><p>{m["text"]}</p></div>' for m in deal['messages']])}
            </div>

            <!-- إرسال رسالة -->
            <div class="p-4 border-t border-slate-800 bg-slate-900/30 flex gap-2">
                <input id="chatInput" type="text" placeholder="اكتب رسالة أو بيانات التسليم أو ملاحظاتك..." class="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white focus:border-amber-500 outline-none" onkeydown="if(event.key==='Enter') sendMessage()">
                <button onclick="sendMessage()" class="gold-btn text-slate-950 font-bold px-5 py-2.5 rounded-xl">إرسال</button>
            </div>
        </div>

    </main>

    <script>
        const dealId = "{deal['id']}";

        function copyDealLink() {{
            navigator.clipboard.writeText(window.location.href);
            alert('تم نسخ رابط الصفقة! شاركه مع المشتري أو البائع.');
        }}

        async function confirmRelease() {{
            if(!confirm('هل أنت متأكد من استلام السلعة/الخدمة بالكامل وبدون مشاكل؟ سيتم تحويل المبلغ للبائع فوراً.')) return;
            const res = await fetch('/api/deals/' + dealId + '/release', {{method: 'POST'}});
            if(res.ok) location.reload();
        }}

        async function raiseDispute() {{
            if(!confirm('هل تريد تجميد الصفقة ورفع اعتراض لفريق الإدارة؟')) return;
            const res = await fetch('/api/deals/' + dealId + '/dispute', {{method: 'POST'}});
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
