from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from enum import Enum
import html

app = FastAPI(title="Watheeq | منصة وثيق للضمان والوساطة")

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

class EscrowStatus(str, Enum):
    PENDING_DEPOSIT = "بانتظار الإيداع والعمولة"
    IN_TRADE_ROOM = "الصفقة جارية (مؤقت 10 دقائق نشط) ⏳"
    COMPLETED = "تم التسليم وتحويل المستحقات بنجاح ✅"
    AUTO_REFUNDED = "تم الاسترجاع التلقائي (تجاوز 10د) 🔄"

class CreateDealRequest(BaseModel):
    title: str = Field(..., max_length=150)
    category: str
    price: float = Field(..., gt=0)
    seller_name: str = Field(..., max_length=50)
    buyer_name: str = Field(default="", max_length=50)

deals_db = [
    {
        "id": "WTQ-701",
        "title": "عربون وضمان مبايعة سيارة ونقل ملكية",
        "category": "مركبات ومعدات (1.5%)",
        "price": 10000,
        "fee_percent": 1.5,
        "fee_amount": 150,
        "seller_net": 9850,
        "seller": "معرض النخبة (Face ID ✓)",
        "buyer": "خالد المطيري (موثق ✓)",
        "status": EscrowStatus.IN_TRADE_ROOM,
        "status_note": "المبلغ مؤمن بخزينة وثيق. غرفة الضمان مفتوحة بمهلة التسليم والفحص الميداني."
    },
    {
        "id": "WTQ-702",
        "title": "عقد تصميم وبرمجة منصة تجارية متكاملة",
        "category": "خدمات وعمل حر (3%)",
        "price": 4500,
        "fee_percent": 3.0,
        "fee_amount": 135,
        "seller_net": 4365,
        "seller": "أحمد السالم (Face ID ✓)",
        "buyer": "سعود الحربي",
        "status": EscrowStatus.PENDING_DEPOSIT,
        "status_note": "تم فتح الصفقة، بانتظار سداد العميل وتأمين المبلغ لبدء التنفيذ."
    }
]

@app.get("/api/deals")
def get_deals():
    return deals_db

@app.post("/api/deals/create")
def create_deal(req: CreateDealRequest):
    # موازنة النسب حسب نوع الصفقة والسلعة
    if "1.5" in req.category or "مركبات" in req.category:
        fee_pct = 1.5
    elif "3" in req.category or "خدمات" in req.category or "أجهزة" in req.category:
        fee_pct = 3.0
    else:
        fee_pct = 5.0

    fee_amount = round((req.price * fee_pct) / 100, 2)
    seller_net = round(req.price - fee_amount, 2)

    new_deal = {
        "id": f"WTQ-{len(deals_db) + 701}",
        "title": html.escape(req.title),
        "category": req.category,
        "price": req.price,
        "fee_percent": fee_pct,
        "fee_amount": fee_amount,
        "seller_net": seller_net,
        "seller": f"{html.escape(req.seller_name)} (Face ID ✓)",
        "buyer": f"{html.escape(req.buyer_name)} (موثق ✓)" if req.buyer_name else "بانتظار المشتري",
        "status": EscrowStatus.PENDING_DEPOSIT,
        "status_note": "تم إنشاء طلب الضمان؛ بانتظار تأمين المبلغ لفتح غرفة التسليم المشفرة ومؤقت الـ 10 دقائق."
    }
    deals_db.insert(0, new_deal)
    return new_deal

@app.post("/api/deals/{deal_id}/pay")
def pay_and_enter_room(deal_id: str):
    for d in deals_db:
        if d["id"] == deal_id:
            d["status"] = EscrowStatus.IN_TRADE_ROOM
            d["status_note"] = "تم تأمين المبلغ بالكامل في خزينة وثيق. بدأت مهلة الـ 10 دقائق للتسليم الآمن."
            return d
    raise HTTPException(status_code=404, detail="الصفقة غير موجودة")

@app.post("/api/deals/{deal_id}/complete")
def complete_deal(deal_id: str):
    for d in deals_db:
        if d["id"] == deal_id:
            d["status"] = EscrowStatus.COMPLETED
            d["status_note"] = f"تم تأكيد استلام السلعة بنجاح؛ تحويل {d['seller_net']} ر.س للبائع واقتطاع العمولة {d['fee_amount']} ر.س."
            return d
    raise HTTPException(status_code=404, detail="الصفقة غير موجودة")

@app.post("/api/deals/{deal_id}/refund")
def auto_refund_deal(deal_id: str):
    for d in deals_db:
        if d["id"] == deal_id:
            d["status"] = EscrowStatus.AUTO_REFUNDED
            d["status_note"] = "انتهت مهلة الـ 10 دقائق دون تسليم من البائع. تمت إعادة كامل المبلغ إلى المشتري فورياً."
            return d
    raise HTTPException(status_code=404, detail="الصفقة غير موجودة")

@app.get("/", response_class=HTMLResponse)
def serve_website():
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl" id="htmlTag">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title id="siteTitle">وثيق | المنصة الشاملة لحماية وتأمين كافة الصفقات</title>
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://safewatheeq.com/">
    <meta property="og:title" content="وثيق | المنصة الشاملة لحماية وتأمين كافة الصفقات">
    <meta property="og:description" content="ضمانك الأول لأي صفقة.. بيع واشتر في أي مجال وأنت مرتاح.">
    <meta property="og:image" content="https://safewatheeq.com/static/logo.png">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="https://safewatheeq.com/">
    <meta name="twitter:title" content="وثيق | المنصة الشاملة لحماية وتأمين كافة الصفقات">
    <meta name="twitter:description" content="ضمانك الأول لأي صفقة.. بيع واشتر في أي مجال وأنت مرتاح.">
    <meta name="twitter:image" content="https://safewatheeq.com/static/logo.png">
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;900&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Tajawal', sans-serif; background-color: #090d16; color: #f8fafc; line-height: 1.8; letter-spacing: 0.015em; }
        .gold-btn { background: linear-gradient(135deg, #f59e0b, #d97706); }
        .card-bg { background: #0f172a; border: 1px solid #1e293b; }
        .badge-room { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid #f59e0b; }
        .badge-done { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981; }
        .badge-refund { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid #ef4444; }
        h1, h2, h3 { line-height: 1.4 !important; }
    </style>
</head>
<body class="min-h-screen flex flex-col justify-between">

    <!-- Face ID Modal -->
    <div id="authModal" class="fixed inset-0 bg-black/80 z-50 backdrop-blur-sm hidden flex items-center justify-center p-4">
        <div class="card-bg p-8 rounded-3xl max-w-md w-full border border-amber-500/30 shadow-2xl relative text-center">
            <button onclick="toggleModal('authModal', false)" class="absolute top-5 left-5 text-gray-400 hover:text-white text-xl">✕</button>
            <div class="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 mx-auto flex items-center justify-center text-3xl mb-4">
                🛡️
            </div>
            <h3 class="text-2xl font-black mb-2" id="modalTitle">التوثيق البيومتري والأمان</h3>
            <p class="text-gray-400 text-xs mb-6 leading-relaxed" id="modalSub">لحماية الطرفين من النصب، يتم التحقق عبر Face ID أو البصمة الحيوية أو نفاذ</p>
            
            <button onclick="simulateFaceID()" id="faceIdBtn" class="w-full gold-btn text-black font-black py-3.5 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20 hover:opacity-95 transition text-sm">
                <span>📸 التحقق الفوري عبر Face ID / Touch ID</span>
            </button>
            <div id="authSuccessMsg" class="hidden mt-4 p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs font-bold">
                ✓ تم التحقق من هويتك بنجاح وتوثيق الحساب
            </div>
        </div>
    </div>

    <!-- Payment Modal -->
    <div id="payModal" class="fixed inset-0 bg-black/80 z-50 backdrop-blur-sm hidden flex items-center justify-center p-4">
        <div class="card-bg p-8 rounded-3xl max-w-lg w-full border border-amber-500/30 shadow-2xl relative">
            <button onclick="toggleModal('payModal', false)" class="absolute top-5 left-5 text-gray-400 hover:text-white text-xl">✕</button>
            <h3 class="text-2xl font-black mb-2 text-center">بوابة الإيداع وتأمين الصفقة</h3>
            <p class="text-gray-400 text-xs mb-6 text-center leading-relaxed">يتم حجز المبلغ في الخزينة ولن يُسلم للبائع إلا بعد استلامك ومعاينتك</p>

            <div class="grid grid-cols-2 gap-3 mb-6">
                <button class="p-3 bg-[#080c14] border border-gray-700 hover:border-amber-500 rounded-xl flex items-center justify-center gap-2 text-xs font-bold transition">
                    💳 بطاقة مدى / Mada
                </button>
                <button class="p-3 bg-[#080c14] border border-gray-700 hover:border-amber-500 rounded-xl flex items-center justify-center gap-2 text-xs font-bold transition">
                     Apple Pay
                </button>
                <button class="p-3 bg-[#080c14] border border-gray-700 hover:border-amber-500 rounded-xl flex items-center justify-center gap-2 text-xs font-bold transition">
                    🌐 Visa / MasterCard
                </button>
                <button class="p-3 bg-[#080c14] border border-gray-700 hover:border-amber-500 rounded-xl flex items-center justify-center gap-2 text-xs font-bold transition">
                    ₮ Crypto (USDT)
                </button>
            </div>

            <button onclick="confirmDeposit()" class="w-full gold-btn text-black font-black py-4 rounded-xl text-sm hover:opacity-95 transition shadow-lg shadow-amber-500/20">
                تأكيد الإيداع والدخول لغرفة التسليم (مهلة 10 دقائق) ⏱️
            </button>
        </div>
    </div>

    <!-- Header / Navbar -->
    <header class="border-b border-gray-800 bg-[#0c121e]/95 sticky top-0 z-40 backdrop-blur">
        <div class="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-11 h-11 rounded-xl gold-btn flex items-center justify-center font-black text-black text-2xl shadow-lg shadow-amber-500/20">و</div>
                <div>
                    <span class="text-2xl font-black tracking-wide text-white" id="brandLogo">وثيــق</span>
                    <span class="block text-[10px] text-amber-500 font-bold tracking-wider" id="brandSlogan">الضمان والوساطة المالية الشاملة</span>
                </div>
            </div>

            <div class="flex items-center gap-4">
                <select onchange="changeLanguage(this.value)" class="bg-[#080c14] border border-gray-700 text-xs font-bold rounded-xl px-3 py-2 text-amber-400 outline-none">
                    <option value="ar">🇸🇦 العربية</option>
                    <option value="en">🇺🇸 English</option>
                    <option value="es">🇪🇸 Español</option>
                </select>

                <button onclick="toggleModal('authModal', true)" id="userAuthBtn" class="bg-gray-800 border border-gray-700 hover:border-amber-500 text-gray-200 text-xs font-bold px-4 py-2.5 rounded-xl transition flex items-center gap-2">
                    <span>🛡️</span> <span id="authBtnTxt">توثيق الهوية (Face ID)</span>
                </button>

                <button onclick="document.getElementById('createSection').scrollIntoView({behavior: 'smooth'})" class="gold-btn text-black font-bold px-5 py-2.5 rounded-xl text-xs shadow-lg shadow-amber-500/20 hover:opacity-95 transition">
                    + <span id="createDealBtnTxt">إنشاء صفقة</span>
                </button>
            </div>
        </div>
    </header>

    <!-- Hero -->
    <section class="max-w-7xl mx-auto px-6 pt-16 pb-12 text-center">
        <div class="inline-flex items-center gap-2 py-1.5 px-5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold mb-6">
            <span>🛡️</span> <span id="heroBadge">بوابتك المعتمدة لحماية وتأمين كافة المبايعات والصفقات</span>
        </div>
        <h1 class="text-4xl md:text-6xl font-black leading-tight max-w-4xl mx-auto mb-6" id="heroTitle">
            ضمانك الأول لأي صفقة.. <br><span class="text-amber-500">بيع واشترِ في أي مجال وأنت مرتاح</span>
        </h1>
        <p class="text-gray-400 text-base md:text-lg max-w-3xl mx-auto mb-8 leading-relaxed" id="heroDesc">
            وساطة مالية وحماية كاملة للسيارات، السلع، الخدمات، الأجهزة، والصفقات العامة. نحفظ أموالك حتى اكتمال الفحص والتسليم بنجاح مع مؤقت تسليم آمن.
        </p>
    </section>

    <!-- 3 Pillars -->
    <section class="max-w-7xl mx-auto px-6 py-6">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="card-bg p-6 rounded-2xl">
                <div class="text-amber-500 text-3xl font-black mb-2">⏱️ 10 Min</div>
                <h3 class="text-lg font-bold mb-2" id="feature1Title">مؤقت التسليم التلقائي</h3>
                <p class="text-gray-400 text-xs leading-relaxed" id="feature1Desc">إذا لم يقم البائع بتسليم السلعة أو البيانات خلال 10 دقائق من الإيداع، تُعاد الأموال تلقائياً لمحفظة المشتري.</p>
            </div>
            <div class="card-bg p-6 rounded-2xl">
                <div class="text-amber-500 text-3xl font-black mb-2">🔒 Vault Lock</div>
                <h3 class="text-lg font-bold mb-2" id="feature2Title">حماية تامة من الاحتيال</h3>
                <p class="text-gray-400 text-xs leading-relaxed" id="feature2Desc">توثيق تسليم المعاملات والرموز داخل غرفة الصفقة رسمياً لمنع ادعاء عدم الاستلام وسحب السلعة بعد الشراء.</p>
            </div>
            <div class="card-bg p-6 rounded-2xl">
                <div class="text-amber-500 text-3xl font-black mb-2">⚖️ Smart Fees</div>
                <h3 class="text-lg font-bold mb-2" id="feature3Title">نسب متوازنة وعادلة</h3>
                <p class="text-gray-400 text-xs leading-relaxed" id="feature3Desc">عمولة مخفضة للسيارات والصفقات الكبيرة (تبدأ من 1.5%) ونسب متوازنة لكافة المجالات لتشجيع التجارة الآمنة.</p>
            </div>
        </div>
    </section>

    <!-- Live Trade Deals -->
    <section class="max-w-7xl mx-auto px-6 py-10">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h2 class="text-2xl font-black" id="liveDealsTitle">غرف صفقات وثيق النشطة</h2>
                <p class="text-gray-400 text-xs" id="liveDealsSub">متابعة فورية لحالات الضمان وتأكيد الحجوزات</p>
            </div>
        </div>
        <div id="dealsContainer" class="grid grid-cols-1 md:grid-cols-2 gap-6"></div>
    </section>

    <!-- Create Deal Section -->
    <section id="createSection" class="max-w-3xl mx-auto px-6 py-10">
        <div class="card-bg p-8 md:p-10 rounded-3xl shadow-2xl">
            <div class="text-center mb-6">
                <h2 class="text-2xl font-black" id="formHeaderTitle">فتح غرفة صفقة جديدة</h2>
                <p class="text-gray-400 text-xs mt-1" id="formHeaderSub">يتم حجز المبلغ واحتساب العمولة العادلة تلقائياً حسب نوع السلعة</p>
            </div>
            <form onsubmit="handleCreateDeal(event)" class="space-y-4">
                <div>
                    <label class="block text-xs font-bold text-gray-300 mb-1" id="labelTitle">موضوع الصفقة / السلعة أو الخدمة</label>
                    <input type="text" id="dealTitle" required placeholder="مثال: عربون سيارة، صفقة بضاعة، جهاز كمبيوتر، عقد تصميم..." class="w-full bg-[#080c14] border border-gray-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 outline-none">
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-bold text-gray-300 mb-1" id="labelCategory">نوع الصفقة (النسبة التلقائية)</label>
                        <select id="dealCategory" class="w-full bg-[#080c14] border border-gray-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 outline-none">
                            <option value="مركبات ومعدات (1.5%)">مركبات وسيارات (عمولة مخفضة 1.5%)</option>
                            <option value="خدمات وعمل حر (3%)">خدمات وعمل حر (عمولة 3%)</option>
                            <option value="أجهزة وإلكترونيات (3%)">أجهزة وإلكترونيات (عمولة 3%)</option>
                            <option value="أصول رقمية ومتاجر (5%)">أصول رقمية ومتاجر (عمولة 5%)</option>
                            <option value="سلع عامة وصفقات خاصة (3%)">سلع عامة ومبايعات خاصة (عمولة 3%)</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-gray-300 mb-1" id="labelPrice">قيمة الصفقة (ريال / USD)</label>
                        <input type="number" id="dealPrice" required placeholder="1000" class="w-full bg-[#080c14] border border-gray-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs font-bold text-gray-300 mb-1" id="labelSeller">اسم أو يوزر البائع</label>
                        <input type="text" id="dealSeller" required placeholder="البائع" class="w-full bg-[#080c14] border border-gray-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                    <div>
                        <label class="block text-xs font-bold text-gray-300 mb-1" id="labelBuyer">اسم أو يوزر المشتري</label>
                        <input type="text" id="dealBuyer" placeholder="المشتري" class="w-full bg-[#080c14] border border-gray-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 outline-none">
                    </div>
                </div>
                <button type="submit" class="w-full gold-btn text-black font-black py-4 rounded-xl text-sm hover:opacity-95 transition shadow-lg shadow-amber-500/20" id="btnSubmitDeal">
                    بدء تأمين الصفقة فوراً 🚀
                </button>
            </form>
        </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-gray-800 text-center py-6 text-gray-500 text-xs">
        © 2026 Watheeq | جميع الحقوق محفوظة لمنصة وثيق للضمان والوساطة الشاملة 🇸🇦
    </footer>

    <script>
        let currentTargetDealId = null;
        const translations = {
            ar: {
                dir: 'rtl',
                title: 'وثيق | المنصة الشاملة لحماية وتأمين كافة الصفقات',
                brandLogo: 'وثيــق',
                brandSlogan: 'الضمان والوساطة المالية الشاملة',
                heroBadge: 'بوابتك المعتمدة لحماية وتأمين كافة المبايعات والصفقات',
                heroTitle: 'ضمانك الأول لأي صفقة.. <br><span class="text-amber-500">بيع واشترِ في أي مجال وأنت مرتاح</span>',
                heroDesc: 'وساطة مالية وحماية كاملة للسيارات، السلع، الخدمات، الأجهزة، والصفقات العامة. نحفظ أموالك حتى اكتمال الفحص والتسليم بنجاح مع مؤقت تسليم آمن.',
                createDealBtnTxt: 'إنشاء صفقة',
                authBtnTxt: 'توثيق الهوية (Face ID)',
                liveDealsTitle: 'غرف صفقات وثيق النشطة',
                liveDealsSub: 'متابعة فورية لحالات الضمان وتأكيد الحجوزات',
                btnSubmitDeal: 'بدء تأمين الصفقة فوراً 🚀'
            },
            en: {
                dir: 'ltr',
                title: 'Watheeq | Comprehensive Escrow & Deal Protection Platform',
                brandLogo: 'Watheeq',
                brandSlogan: 'UNIVERSAL ESCROW & DEAL PROTECTION',
                heroBadge: 'Verified Escrow Protocol for All Transactions',
                heroTitle: 'Your #1 Guarantee for Any Deal.. <br><span class="text-amber-500">Trade Anything with Total Peace of Mind</span>',
                heroDesc: 'Full escrow protection for vehicles, goods, services, hardware, and deals. We safeguard your funds until delivery and inspection are completed.',
                createDealBtnTxt: 'Create Deal',
                authBtnTxt: 'Verify ID (Face ID)',
                liveDealsTitle: 'Active Watheeq Deal Rooms',
                liveDealsSub: 'Real-time Escrow Vault & Secure Deal Tracking',
                btnSubmitDeal: 'Start Secure Deal Now 🚀'
            },
            es: {
                dir: 'ltr',
                title: 'Watheeq | Plataforma Integral de Custodia y Garantía',
                brandLogo: 'Watheeq',
                brandSlogan: 'GARANTÍA Y PROTECCIÓN UNIVERSAL',
                heroBadge: 'Protocolo de Garantía para Todo Tipo de Tratos',
                heroTitle: 'Tu Garantía Principal en Cualquier Trato.. <br><span class="text-amber-500">Compra y Vende con Total Tranquilidad</span>',
                heroDesc: 'Protección de custodia para vehículos, servicios, equipos y acuerdos comerciales. Fondos retenidos hasta la entrega.',
                createDealBtnTxt: 'Crear Trato',
                authBtnTxt: 'Verificar (Face ID)',
                liveDealsTitle: 'Salas Activas de Watheeq',
                liveDealsSub: 'Monitoreo de depósitos y confirmación de custodia',
                btnSubmitDeal: 'Comenzar Trato Seguro 🚀'
            }
        };

        function changeLanguage(lang) {
            const t = translations[lang];
            document.getElementById('htmlTag').setAttribute('dir', t.dir);
            document.title = t.title;
            document.getElementById('brandLogo').innerText = t.brandLogo;
            document.getElementById('brandSlogan').innerText = t.brandSlogan;
            document.getElementById('heroBadge').innerText = t.heroBadge;
            document.getElementById('heroTitle').innerHTML = t.heroTitle;
            document.getElementById('heroDesc').innerText = t.heroDesc;
            document.getElementById('createDealBtnTxt').innerText = t.createDealBtnTxt;
            document.getElementById('authBtnTxt').innerText = t.authBtnTxt;
            document.getElementById('liveDealsTitle').innerText = t.liveDealsTitle;
            document.getElementById('liveDealsSub').innerText = t.liveDealsSub;
            document.getElementById('btnSubmitDeal').innerText = t.btnSubmitDeal;
        }

        function toggleModal(id, show) {
            const el = document.getElementById(id);
            if (show) el.classList.remove('hidden');
            else el.classList.add('hidden');
        }

        function simulateFaceID() {
            document.getElementById('faceIdBtn').innerHTML = '⏳ جاري مسح بصمة الوجه...';
            setTimeout(() => {
                document.getElementById('authSuccessMsg').classList.remove('hidden');
                document.getElementById('userAuthBtn').innerHTML = '<span>✅</span> موثق (Face ID)';
                document.getElementById('userAuthBtn').classList.add('border-emerald-500', 'text-emerald-400');
                setTimeout(() => toggleModal('authModal', false), 1500);
            }, 1800);
        }

        function openPayModal(id) {
            currentTargetDealId = id;
            toggleModal('payModal', true);
        }

        async function confirmDeposit() {
            if (!currentTargetDealId) return;
            await fetch('/api/deals/' + currentTargetDealId + '/pay', { method: 'POST' });
            toggleModal('payModal', false);
            fetchDeals();
        }

        async function completeDeal(id) {
            await fetch('/api/deals/' + id + '/complete', { method: 'POST' });
            fetchDeals();
        }

        async function refundDeal(id) {
            await fetch('/api/deals/' + id + '/refund', { method: 'POST' });
            fetchDeals();
        }

        async function fetchDeals() {
            const res = await fetch('/api/deals');
            const deals = await res.json();
            const container = document.getElementById('dealsContainer');
            container.innerHTML = '';

            deals.forEach(d => {
                let badgeClass = 'badge-room';
                if (d.status.includes('بنجاح')) badgeClass = 'badge-done';
                if (d.status.includes('الاسترجاع')) badgeClass = 'badge-refund';

                container.innerHTML += `
                    <div class="card-bg p-6 rounded-2xl flex flex-col justify-between hover:border-gray-600 transition">
                        <div>
                            <div class="flex justify-between items-center mb-3">
                                <span class="text-xs font-bold text-gray-300 bg-gray-800 px-3 py-1 rounded-full">${d.category}</span>
                                <span class="text-xs font-bold px-3 py-1 rounded-full ${badgeClass}">${d.status}</span>
                            </div>
                            <h3 class="text-base font-bold mb-3">${d.title}</h3>
                            <div class="grid grid-cols-2 gap-2 text-xs text-gray-400 mb-3 bg-[#080c14] p-3 rounded-xl">
                                <div>البائع: <span class="text-white font-medium">${d.seller}</span></div>
                                <div>المشتري: <span class="text-white font-medium">${d.buyer}</span></div>
                                <div>رقم العقد: <span class="text-amber-400 font-mono">${d.id}</span></div>
                                <div>عمولة وثيق: <span class="text-emerald-400 font-bold">${d.fee_percent}% (${d.fee_amount} ر.س)</span></div>
                            </div>

                            <div class="bg-[#080c14]/90 border border-gray-800 p-3 rounded-xl mb-4 text-xs">
                                <div class="text-amber-400 font-bold mb-1">📌 حالة المعاملة:</div>
                                <p class="text-gray-300 leading-relaxed">${d.status_note}</p>
                            </div>

                            <div class="bg-[#0c121e] p-3 rounded-xl mb-4 text-xs flex justify-between items-center">
                                <span class="text-gray-400">إجمالي المبلغ المحجوز:</span>
                                <span class="text-amber-400 font-bold text-base font-mono">${d.price} ر.س</span>
                            </div>
                        </div>

                        <div class="space-y-2">
                            ${d.status.includes('بانتظار الإيداع') ? `
                                <button onclick="openPayModal('${d.id}')" class="w-full gold-btn text-black font-bold py-3 rounded-xl transition text-xs shadow-lg shadow-amber-500/20">
                                    💳 تأمين المبلغ والعمولة لبدء مهلة التسليم (10 دقائق)
                                </button>
                            ` : ''}

                            ${d.status.includes('مؤقت 10 دقائق') ? `
                                <div class="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl mb-2 text-center">
                                    <span class="text-xs text-amber-400 font-bold block mb-1">⏳ الوقت المتبقي للتسليم:</span>
                                    <span class="text-xl font-black text-amber-300 font-mono">08:42</span>
                                </div>
                                <div class="grid grid-cols-2 gap-2">
                                    <button onclick="completeDeal('${d.id}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 rounded-xl transition text-xs">
                                        ✓ تأكيد الاستلام وتحويل الأرباح
                                    </button>
                                    <button onclick="refundDeal('${d.id}')" class="bg-red-600/80 hover:bg-red-700 text-white font-bold py-2.5 rounded-xl transition text-xs">
                                        ✕ استرجاع الفلوس (عدم تجاوب)
                                    </button>
                                </div>
                            ` : ''}

                            ${d.status.includes('بنجاح') ? `
                                <div class="text-center text-xs text-emerald-400 font-bold py-2 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
                                    ✓ تمت الصفقة بنجاح واقتطاع عمولة المنصة (${d.fee_amount} ر.س)
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            });
        }

        async function handleCreateDeal(e) {
            e.preventDefault();
            const title = document.getElementById('dealTitle').value;
            const category = document.getElementById('dealCategory').value;
            const price = parseFloat(document.getElementById('dealPrice').value);
            const seller_name = document.getElementById('dealSeller').value;
            const buyer_name = document.getElementById('dealBuyer').value;

            await fetch('/api/deals/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, category, price, seller_name, buyer_name })
            });

            fetchDeals();
            alert('تم فتح غرفة الصفقة بنجاح واحتساب النسبة العادلة!');
        }

        fetchDeals();
    </script>
</body>
</html>"""
