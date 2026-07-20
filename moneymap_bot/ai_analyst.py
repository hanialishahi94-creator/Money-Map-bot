"""
ai_analyst.py — تولید خودکار تحلیل روزانه با Groq LLaMA
"""
import os
import re
import asyncio
import datetime
import logging

import pytz

logger = logging.getLogger(__name__)
TEHRAN_TZ = pytz.timezone("Asia/Tehran")

# ─── تعریف دارایی‌ها ───────────────────────────────────────────────────────────
ASSETS = {
    "bitcoin": {
        "ticker": "BTC-USD",
        "search_query": "bitcoin BTC price analysis forecast today",
        "fa_name": "بیتکوین",
        "emoji": "₿",
    },
    "dollar": {
        "ticker": "DX-Y.NYB",
        "search_query": "DXY dollar index analysis forecast today",
        "fa_name": "شاخص دلار",
        "emoji": "💵",
    },
    "gold": {
        "ticker": "GC=F",
        "search_query": "gold XAU USD price analysis forecast today",
        "fa_name": "اونس جهانی طلا",
        "emoji": "🥇",
    },
}


# ─── توابع پاک‌سازی متن ────────────────────────────────────────────────────────

def _is_word_clean(word: str) -> bool:
    """
    True اگه کلمه فقط حاوی کاراکترهای مجاز باشه:
    ASCII + فارسی/عربی + ایموجی + نمادهای رایج
    هر کاراکتر سیریلیک (روسی)، چینی، ترکی-لاتین و غیره → False
    """
    for ch in word:
        code = ord(ch)
        if code <= 0x7F:
            continue                            # ASCII (انگلیسی، ارقام، نشانه‌گذاری)
        if 0x0600 <= code <= 0x06FF:
            continue                            # فارسی/عربی
        if 0xFB50 <= code <= 0xFDFF:
            continue                            # Arabic Presentation Forms-A
        if 0xFE70 <= code <= 0xFEFF:
            continue                            # Arabic Presentation Forms-B
        if ch in "‌‍​،؛؟":
            continue                            # نیم‌فاصله، علائم فارسی
        if 0x2000 <= code <= 0x27FF:
            continue                            # نمادها، پیکان‌ها، Dingbats
        if 0x1F000 <= code <= 0x1FFFF:
            continue                            # ایموجی (📊🎯🏦 و ...)
        if 0xFE00 <= code <= 0xFE0F:
            continue                            # Variation Selectors (برای ایموجی)
        return False                            # بقیه (روسی، چینی، ترکی-لاتین) → حذف
    return True


def _clean_search_text(text: str) -> str:
    """حذف کامل کلمات حاوی کاراکتر غیرمجاز از متن ورودی سرچ."""
    words = text.split()
    clean_words = [w for w in words if _is_word_clean(w)]
    return " ".join(clean_words)


def _clean_ai_output(text: str) -> str:
    """
    حذف کامل کلمات حاوی کاراکتر غیرمجاز از خروجی AI.
    ایموجی، فارسی، انگلیسی و نمادهای رایج حفظ می‌شن.
    کلمات روسی (немного)، چینی (析、分) و مشابه حذف می‌شن.
    """
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        words = line.split(" ")
        clean_words = [w for w in words if _is_word_clean(w)]
        clean_lines.append(" ".join(clean_words))
    result = "\n".join(clean_lines)
    result = re.sub(r" {2,}", " ", result)
    return result.strip()


# ─── تبدیل ویس به متن ────────────────────────────────────────────────────────

async def transcribe_voice(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    """تبدیل ویس به متن با Groq Whisper (رایگان)."""
    import httpx
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY تنظیم نشده")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, file_bytes, "audio/ogg")},
            data={"model": "whisper-large-v3", "language": "fa", "response_format": "text"},
        )
        response.raise_for_status()
        return response.text.strip()


# ─── فراخوانی Groq API ────────────────────────────────────────────────────────

async def _call_groq(prompt: str) -> str:
    """ارسال پرامپت به Groq LLaMA و دریافت پاسخ فارسی پاک."""
    import httpx
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY تنظیم نشده")
        return "❌ خطا: کلید GROQ_API_KEY تنظیم نشده."

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1200,
                    "temperature": 0.65,
                },
            )
            response.raise_for_status()
            result = response.json()["choices"][0]["message"]["content"]
            return _clean_ai_output(result)
    except Exception as e:
        logger.error(f"خطا در فراخوانی Groq: {e}")
        return f"❌ خطا در تولید تحلیل: {e}"


# ─── داده‌های بازار ────────────────────────────────────────────────────────────

async def _fetch_market_data(ticker: str) -> dict:
    """دریافت داده‌های قیمتی از yfinance."""
    try:
        import yfinance as yf
        loop = asyncio.get_event_loop()
        hist = await loop.run_in_executor(
            None, lambda: yf.Ticker(ticker).history(period="7d", interval="1d")
        )
        if hist.empty:
            return {}

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else latest
        price = round(float(latest["Close"]), 2)
        prev_close = round(float(prev["Close"]), 2)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        recent = []
        for idx, row in hist.tail(5).iterrows():
            recent.append({"d": idx.strftime("%m/%d"), "c": round(float(row["Close"]), 2)})

        return {
            "price": price,
            "change": change,
            "change_pct": change_pct,
            "high": round(float(latest["High"]), 2),
            "low": round(float(latest["Low"]), 2),
            "prev_close": prev_close,
            "recent": recent,
        }
    except Exception as e:
        logger.error(f"خطا در دریافت داده بازار {ticker}: {e}")
        return {}


# ─── جستجوی DuckDuckGo ────────────────────────────────────────────────────────

async def _search_analyst_opinions(query: str) -> str:
    """جستجوی دیدگاه تحلیلگران از وب (DuckDuckGo)."""
    try:
        from duckduckgo_search import DDGS
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, lambda: list(DDGS().text(query, max_results=5))
        )
        texts = []
        for r in results:
            title = _clean_search_text(r.get("title", ""))
            body = _clean_search_text(r.get("body", ""))
            combined = f"{title}: {body}".strip(": ")
            if combined:
                texts.append(f"- {combined}")
        return "\n".join(texts) if texts else "اطلاعاتی از وب یافت نشد."
    except Exception as e:
        logger.error(f"خطا در جستجوی DuckDuckGo: {e}")
        return "خطا در جستجوی وب."


async def _search_economic_calendar(date: str) -> str:
    """جستجوی رویدادهای اقتصادی امروز (DuckDuckGo)."""
    try:
        from duckduckgo_search import DDGS
        query = f"economic calendar important events today {date} CPI NFP FOMC GDP interest rate"
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None, lambda: list(DDGS().text(query, max_results=4))
        )
        texts = []
        for r in results:
            title = _clean_search_text(r.get("title", ""))
            body = _clean_search_text(r.get("body", ""))
            combined = f"{title}: {body}".strip(": ")
            if combined:
                texts.append(f"- {combined}")
        return "\n".join(texts) if texts else "رویداد اقتصادی مهمی برای امروز یافت نشد."
    except Exception as e:
        logger.error(f"خطا در جستجوی تقویم اقتصادی: {e}")
        return "خطا در جستجوی رویدادهای اقتصادی."


# ─── تولید تحلیل ─────────────────────────────────────────────────────────────

async def generate_analysis(asset_key: str) -> str:
    """تولید تحلیل روزانه برای یک دارایی."""
    asset = ASSETS[asset_key]
    today = datetime.datetime.now(TEHRAN_TZ).strftime("%Y/%m/%d")

    market_data, analyst_info, econ_calendar = await asyncio.gather(
        _fetch_market_data(asset["ticker"]),
        _search_analyst_opinions(asset["search_query"]),
        _search_economic_calendar(today),
    )

    if market_data:
        recent = market_data.get("recent", [])
        recent_str = " | ".join([f"{r['d']}: {r['c']}" for r in recent]) if recent else "N/A"
        md_text = (
            f"قیمت فعلی: {market_data.get('price', 'N/A')} | "
            f"تغییر: {market_data.get('change', 'N/A')} ({market_data.get('change_pct', 'N/A')}%) | "
            f"سقف روز: {market_data.get('high', 'N/A')} | کف روز: {market_data.get('low', 'N/A')} | "
            f"بسته دیروز: {market_data.get('prev_close', 'N/A')} | "
            f"سابقه ۵ روز: {recent_str}"
        )
    else:
        md_text = "داده‌های قیمتی در دسترس نیستند."

    if asset_key == "bitcoin":
        prompt = f"""تو یه تحلیلگر بازار کریپتو هستی. فقط و فقط به فارسی بنویس — هیچ کلمه ترکی، اندونزیایی یا غیرانگلیسی استفاده نکن. لحنت باید دقیقاً اینطور باشه: نه کتابی و آکادمیک، نه خیلی عامیانه. مثل یه متخصص که مستقیم با مخاطب حرف می‌زنه. از عباراتی مثل «به نظر میرسه»، «انتظار داریم»، «حواستون باشه»، «این سطح مهمه» استفاده کن. جملات کوتاه و مستقیم. مخاطب رو به چیزهای مهم هشدار بده.

📅 تاریخ: {today}
📈 داده‌های بازار BTC: {md_text}

🌐 دیدگاه تحلیلگران از وب:
{analyst_info}

📆 رویدادهای اقتصادی امروز:
{econ_calendar}

---
تحلیل بیتکوین رو با این ساختار بنویس:

۱. 📊 وضعیت قیمت
   قیمت و تغییر امروز رو بگو — بازار الان کجا وایستاده

۲. 📈 تکنیکال
   سطوح حمایت و مقاومت کلیدی، روند فعلی

۳. 🌍 فاندامنتال و سنتیمنت
   مهم‌ترین اخبار، ریسک‌های ژئوپلیتیک، سیاست پولی فدرال رزرو
   اگه امروز داده اقتصادی مهمی مثل CPI، NFP، FOMC یا GDP داریم، حتماً بهش اشاره کن و بگو چه تأثیری می‌تونه داشته باشه

۴. 🔗 آنچین (On-Chain)
   فقط اگه داده معناداری هست بگو — در غیر این صورت خیلی کوتاه رد کن

۵. 📊 بازار مشتقات
   فقط اگه funding rate، open interest یا put/call ratio حرفی برای گفتن داره — وگرنه یه جمله کافیه

۶. 🏦 ETF بیتکوین
   فقط اگه اتفاق مهمی افتاده بگو — وگرنه خیلی کوتاه رد کن

۷. 👥 موضع بازار
   الان بیشتر لانگ هستن یا شورت؟

۸. 🎯 بایاس امروز
   صریح بگو: صعودی / نزولی / خنثی + دلیل

حدود ۳۵۰ کلمه. بخش‌هایی که داده مهمی ندارن رو کوتاه کن."""

    elif asset_key == "dollar":
        prompt = f"""تو یه تحلیلگر بازار فارکس هستی. فقط و فقط به فارسی بنویس — هیچ کلمه ترکی، اندونزیایی یا غیرانگلیسی استفاده نکن. لحنت باید دقیقاً اینطور باشه: نه کتابی و آکادمیک، نه خیلی عامیانه. مثل یه متخصص که مستقیم با مخاطب حرف می‌زنه. از عباراتی مثل «به نظر میرسه»، «انتظار داریم»، «حواستون باشه»، «این سطح مهمه» استفاده کن. جملات کوتاه و مستقیم.

📅 تاریخ: {today}
📈 داده‌های شاخص دلار DXY: {md_text}

🌐 دیدگاه تحلیلگران از وب:
{analyst_info}

📆 رویدادهای اقتصادی امروز:
{econ_calendar}

---
تحلیل شاخص دلار رو با این ساختار بنویس:

۱. 📊 وضعیت DXY
   قیمت و تغییر امروز — دلار الان کجا وایستاده

۲. 📈 تکنیکال
   سطوح حمایت و مقاومت کلیدی، روند فعلی

۳. 🌍 سیاست پولی و اقتصاد کلان
   آخرین موضع فدرال رزرو، وضعیت تورم
   اگه امروز داده مهمی مثل CPI، NFP، FOMC یا GDP داریم، حتماً بهش اشاره کن و بگو چه تأثیری می‌تونه داشته باشه

۴. 🎯 بایاس امروز
   صریح بگو: صعودی / نزولی / خنثی + دلیل

حدود ۲۰۰ کلمه. فقط بخش‌هایی که داده واقعی داری رو بنویس."""

    else:  # gold
        prompt = f"""تو یه تحلیلگر بازار طلا هستی. فقط و فقط به فارسی بنویس — هیچ کلمه ترکی، اندونزیایی یا غیرانگلیسی استفاده نکن. لحنت باید دقیقاً اینطور باشه: نه کتابی و آکادمیک، نه خیلی عامیانه. مثل یه متخصص که مستقیم با مخاطب حرف می‌زنه. از عباراتی مثل «به نظر میرسه»، «انتظار داریم»، «حواستون باشه»، «این سطح مهمه» استفاده کن. جملات کوتاه و مستقیم.

📅 تاریخ: {today}
📈 داده‌های اونس جهانی XAU/USD: {md_text}

🌐 دیدگاه تحلیلگران از وب:
{analyst_info}

📆 رویدادهای اقتصادی امروز:
{econ_calendar}

---
تحلیل اونس جهانی طلا رو با این ساختار بنویس:

۱. 📊 وضعیت قیمت
   قیمت و تغییر امروز — طلا الان کجا وایستاده

۲. 📈 تکنیکال
   سطوح حمایت و مقاومت کلیدی، روند فعلی

۳. 🌍 فاندامنتال و سنتیمنت
   تنش‌های ژئوپلیتیک، سیاست پولی، تقاضای بانک‌های مرکزی
   اگه امروز داده مهمی مثل CPI، NFP، FOMC یا GDP داریم، حتماً بهش اشاره کن و بگو چه تأثیری می‌تونه داشته باشه

۴. 👥 موضع تحلیلگران
   دیدگاه غالب: لانگ یا شورت؟

۵. 🎯 بایاس امروز
   صریح بگو: صعودی / نزولی / خنثی + دلیل

حدود ۲۵۰ کلمه."""

    return await _call_groq(prompt)


# ─── ویرایش تحلیل ────────────────────────────────────────────────────────────

async def edit_analysis(original_text: str, edit_prompt: str, asset_key: str) -> str:
    """ویرایش تحلیل موجود بر اساس دستور ادمین."""
    asset = ASSETS[asset_key]

    prompt = f"""تحلیل زیر برای {asset['fa_name']} نوشته شده. فقط و فقط به فارسی بنویس:

{original_text}

---
دستور ویرایش از ادمین: {edit_prompt}

تحلیل رو دقیقاً طبق دستور ویرایش کن. ساختار بخشی و فرمت فارسی رو حفظ کن. هیچ کلمه غیرفارسی اضافه نکن."""

    return await _call_groq(prompt)