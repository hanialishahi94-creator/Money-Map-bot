"""
ai_analyst.py — تولید خودکار تحلیل روزانه با Google Gemini (رایگان)
"""
import os
import asyncio
import datetime
import logging

import pytz

logger = logging.getLogger(__name__)
TEHRAN_TZ = pytz.timezone("Asia/Tehran")

ASSETS = {
    "gold": {
        "fa_name": "اونس جهانی طلا",
        "emoji": "🥇",
        "ticker": "GC=F",
        "search_query": "XAU gold ounce price analysis forecast analysts position today",
    },
    "dollar": {
        "fa_name": "شاخص دلار (DXY)",
        "emoji": "💵",
        "ticker": "DX-Y.NYB",
        "search_query": "DXY dollar index analysis forecast analysts today",
    },
    "bitcoin": {
        "fa_name": "بیتکوین",
        "emoji": "₿",
        "ticker": "BTC-USD",
        "search_query": "Bitcoin BTC price analysis forecast traders position today",
    },
}




async def _fetch_market_data(ticker: str) -> dict:
    """دریافت داده‌های قیمتی از yfinance (non-blocking)."""
    loop = asyncio.get_event_loop()

    def _fetch():
        try:
            import yfinance as yf
            t = yf.Ticker(ticker)
            hist = t.history(period="5d", interval="1d")
            if hist.empty:
                return {}
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]
            change = latest["Close"] - prev["Close"]
            change_pct = (change / prev["Close"]) * 100
            return {
                "price": round(float(latest["Close"]), 2),
                "open": round(float(latest["Open"]), 2),
                "high": round(float(latest["High"]), 2),
                "low": round(float(latest["Low"]), 2),
                "prev_close": round(float(prev["Close"]), 2),
                "change": round(float(change), 2),
                "change_pct": round(float(change_pct), 2),
                "recent": [
                    {"d": str(hist.index[i].date()), "c": round(float(hist.iloc[i]["Close"]), 2)}
                    for i in range(len(hist))
                ],
            }
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {ticker}: {e}")
            return {}

    return await loop.run_in_executor(None, _fetch)


async def _search_analyst_opinions(query: str) -> str:
    """جستجوی آنلاین نظرات تحلیلگران با DuckDuckGo (رایگان)."""
    loop = asyncio.get_event_loop()

    def _search():
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=6):
                    snippet = r.get("body", "")[:280]
                    results.append(f"• {r.get('title', '')}: {snippet}")
            return "\n".join(results) if results else "نتیجه‌ای یافت نشد."
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return "جستجوی آنلاین در دسترس نیست."

    return await loop.run_in_executor(None, _search)


async def _search_economic_calendar(today: str) -> str:
    """جستجوی داده‌های مهم اقتصادی امروز."""
    loop = asyncio.get_event_loop()

    def _search():
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(
                    f"economic calendar important data release {today} CPI NFP FOMC GDP",
                    max_results=4
                ):
                    snippet = r.get("body", "")[:250]
                    results.append(f"• {r.get('title', '')}: {snippet}")
            return "\n".join(results) if results else "داده اقتصادی خاصی یافت نشد."
        except Exception as e:
            logger.warning(f"Economic calendar search failed: {e}")
            return "جستجوی تقویم اقتصادی ناموفق."

    return await loop.run_in_executor(None, _search)


async def _call_groq(prompt: str) -> str:
    """ارسال پرامپت به Groq API (رایگان، سریع، مدل Llama 3.1)."""
    from openai import AsyncOpenAI
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("متغیر محیطی GROQ_API_KEY تنظیم نشده. از console.groq.com کلید رایگان بگیر.")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    response = await client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1600,
    )
    return response.choices[0].message.content


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
        prompt = f"""تو یه تحلیلگر بازار کریپتو هستی. لحنت باید دقیقاً اینطور باشه: نه کتابی و آکادمیک، نه خیلی عامیانه. مثل یه متخصص که مستقیم با مخاطب حرف می‌زنه. از عباراتی مثل «به نظر میرسه»، «انتظار داریم»، «حواستون باشه»، «این سطح مهمه» استفاده کن. جملات کوتاه و مستقیم. مخاطب رو به چیزهای مهم هشدار بده.

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
        prompt = f"""تو یه تحلیلگر بازار فارکس هستی. لحنت باید دقیقاً اینطور باشه: نه کتابی و آکادمیک، نه خیلی عامیانه. مثل یه متخصص که مستقیم با مخاطب حرف می‌زنه. از عباراتی مثل «به نظر میرسه»، «انتظار داریم»، «حواستون باشه»، «این سطح مهمه» استفاده کن. جملات کوتاه و مستقیم.

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
        prompt = f"""تو یه تحلیلگر بازار طلا هستی. لحنت باید دقیقاً اینطور باشه: نه کتابی و آکادمیک، نه خیلی عامیانه. مثل یه متخصص که مستقیم با مخاطب حرف می‌زنه. از عباراتی مثل «به نظر میرسه»، «انتظار داریم»، «حواستون باشه»، «این سطح مهمه» استفاده کن. جملات کوتاه و مستقیم.

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


async def edit_analysis(original_text: str, edit_prompt: str, asset_key: str) -> str:
    """ویرایش تحلیل موجود بر اساس دستور ادمین."""
    asset = ASSETS[asset_key]

    prompt = f"""تحلیل زیر برای {asset['fa_name']} نوشته شده:

{original_text}

---
دستور ویرایش از ادمین: {edit_prompt}

تحلیل رو دقیقاً طبق دستور ویرایش کن. ساختار ۵ بخشی و فرمت فارسی رو حفظ کن."""

    return await _call_groq(prompt)