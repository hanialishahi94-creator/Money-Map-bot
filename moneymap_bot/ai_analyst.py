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
                    "max_tokens": 2000,
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

async def generate_analysis(
    asset_key: str,
    support_level: float | None = None,
    resistance_level: float | None = None,
) -> str:
    """
    تولید تحلیل روزانه برای یک دارایی.
    اگه support_level یا resistance_level پاس بشن (از چارت ICT)،
    در پرامپت به AI گفته می‌شه که این سطوح رو در تحلیلش ذکر کنه
    تا عددهای چارت و متن تحلیل همخوانی داشته باشن.
    """
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

    # ─── سطوح S/R از چارت ICT (اگه موجود باشن) ─────────────────────────────
    sr_note = ""
    if support_level is not None or resistance_level is not None:
        sr_note = "\n\n📌 سطوح کلیدی تکنیکال (از تحلیل ICT Order Block — حتماً همین اعداد رو در بخش تکنیکال ذکر کن):\n"
        if support_level is not None:
            sr_note += f"  🟢 ناحیه حمایت: {support_level:,.2f}\n"
        if resistance_level is not None:
            sr_note += f"  🔴 ناحیه مقاومت: {resistance_level:,.2f}\n"
        sr_note += "(این سطوح از روی چارت واقعی ۱ ساعته محاسبه شدن و باید با متن تحلیل همخوانی داشته باشن)"

    # ─── پرامپت یکپارچه حرفه‌ای ──────────────────────────────────────────────────
    if asset_key == "bitcoin":
        asset_label = "بیتکوین (BTC/USD)"
    elif asset_key == "dollar":
        asset_label = "شاخص دلار (DXY)"
    else:
        asset_label = "اونس جهانی طلا (XAU/USD)"

    prompt = f"""تاریخ: {today}
دارایی: {asset_label}
داده‌های قیمتی ۵ روز اخیر: {md_text}{sr_note}

اطلاعات تکمیلی از وب (برای تأیید یا رد بایاس در صورت وجود داده Positioning، Long/Short Ratio، Funding Rate یا Open Interest):
{analyst_info}

---

تو یک تحلیلگر حرفه‌ای بازارهای مالی هستی. وظیفه تو تولید تحلیل روزانه برای {asset_label} است.

هدف تحلیل: کمک به تصمیم معاملاتی، نه گزارش قیمت.
هر تحلیل باید پاسخ دهد:
الان چه کسی کنترل بازار را دارد؟
معامله‌گر باید دنبال چه نشانه‌ای باشد؟
چه چیزی باعث تغییر دیدگاه می‌شود؟

لحن: روان، خودمانی، مثل یک تریدر باتجربه. نه مقاله‌ای، نه دانشگاهی.

قوانین:
- فقط فارسی. هیچ کلمه غیرانگلیسی و غیرفارسی نزن.
- از گزارش قیمت روزانه و تغییرات درصدی صرفاً برای پر کردن متن استفاده نکن.
- تمرکز روی تکنیکال. از فاندامنتال و اخبار استفاده نکن.
- اگر داده Positioning معتبر وجود ندارد، آن بخش را کاملاً حذف کن.
- هیچ قطعیتی درباره آینده نده؛ سناریو و احتمال ارائه کن.
- اسم سبک‌های تحلیلی مثل ICT، LIT، Smart Money و غیره را در متن نیاور.
- از جملات عمومی مثل «معامله‌گران باید مدیریت ریسک داشته باشند» استفاده نکن. به جای آن بگو: «تا زمانی که قیمت زیر X است، فروشنده‌ها دست بالا را دارند؛ عبور از X می‌تواند دیدگاه را تغییر دهد.»
- تایم‌فریم ۴ ساعته برای جهت اصلی، تایم‌فریم ۱ ساعته برای نقاط تصمیم.

---

ساختار خروجی (دقیقاً همین ترتیب):

## بایاس فعلی بازار
ابتدا یکی از این سه حالت را بنویس: صعودی / نزولی / خنثی
سپس دلیل آن را بر اساس ساختار قیمت توضیح بده.
اگر داده Positioning، Long/Short Ratio، Funding Rate یا Open Interest وجود داشت، از آن برای تأیید یا رد بایاس استفاده کن — نه اینکه فقط بگویی «لانگ‌ها بیشترند پس صعودی است»؛ تحلیل کن که این موضوع چه اثری روی رفتار قیمت دارد.

## وضعیت کلی بازار
روند فعلی، ساختار بازار، سقف‌ها و کف‌های مهم، مناطق عرضه و تقاضا، نقدینگی‌های مهم. از اصطلاحات تخصصی استفاده کن ولی ساده توضیح بده.

## سناریوی صعودی
شرط فعال شدن: چه چیزی باید اتفاق بیفتد؟
نقطه تصمیم: بازار در چه محدوده‌ای مهم است؟
هدف اول: ...
هدف دوم: ...
ابطال سناریو: چه چیزی باعث می‌شود این تحلیل دیگر معتبر نباشد؟

## سناریوی نزولی
شرط فعال شدن: چه چیزی باید اتفاق بیفتد؟
نقطه تصمیم: بازار در چه محدوده‌ای مهم است؟
هدف اول: ...
هدف دوم: ...
ابطال سناریو: چه چیزی باعث می‌شود این تحلیل دیگر معتبر نباشد؟

## مناطق مهم قیمتی
Zone ارائه بده، نه عدد دقیق. برای هر جهت حداقل دو منطقه. محدوده‌ها نباید فقط بر اساس نزدیک‌ترین سقف و کف روزانه باشند.
حمایت نزدیک: X تا Y
حمایت مهم: X تا Y
مقاومت نزدیک: X تا Y
مقاومت مهم: X تا Y

## جمع‌بندی معامله‌گر
مثل یک تریدر حرفه‌ای جمع‌بندی کن. بگو بازار الان دست کیست، معامله‌گر باید منتظر چه نشانه‌ای باشد، و چه چیزی دیدگاه را عوض می‌کند."""

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