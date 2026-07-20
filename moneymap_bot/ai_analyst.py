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
        prompt = f"""تو یک تحلیلگر حرفه‌ای بازار کریپتو هستی. تحلیلت باید دقیق، رک و مستقیم باشه — نه خشک و آکادمیک، نه خیلی عامیانه. مثل یه متخصص باتجربه که آدم‌رو جدی می‌گیره و بدون حاشیه حرف می‌زنه.

📅 تاریخ: {today}
📈 داده‌های بازار BTC: {md_text}

🌐 دیدگاه تحلیلگران از وب:
{analyst_info}

📆 رویدادهای اقتصادی امروز:
{econ_calendar}

---
تحلیل بیتکوین رو با این ساختار بنویس:

۱. 📊 وضعیت قیمت
   قیمت فعلی، تغییر روزانه و اینکه بازار الان کجا ایستاده

۲. 📈 تحلیل تکنیکال
   سطوح حمایت و مقاومت کلیدی، روند غالب، الگوهای مهم

۳. 🌍 فاندامنتال و سنتیمنت
   مهم‌ترین اخبار، تنش‌های ژئوپلیتیک، سیاست پولی فدرال رزرو
   اگه امروز داده اقتصادی کلیدی مثل CPI، NFP، FOMC یا GDP داریم، حتماً تأثیرش رو تحلیل کن

۴. 🔗 آنچین (On-Chain)
   فقط اگه داده معنادار داری بگو: جریان به صرافی‌ها، رفتار whaleها، هولدرهای بلندمدت — در غیر این صورت این بخش رو خیلی کوتاه کن

۵. 📊 بازار مشتقات
   فقط اگه داده مهمی وجود داره: funding rate، open interest، نسبت put/call — در غیر این صورت یه جمله کافیه

۶. 🏦 ETF بیتکوین
   فقط اگه اتفاق قابل توجهی افتاده بگو — در غیر این صورت خیلی کوتاه رد کن

۷. 👥 موضع‌گیری بازار
   تریدرهای حرفه‌ای الان بیشتر لانگ هستن یا شورت؟

۸. 🎯 جمع‌بندی و بایاس روزانه
   صریح و قاطع بگو: صعودی / نزولی / خنثی — و دلیلت رو توضیح بده

حدود ۳۵۰ کلمه. فارسی روان و حرفه‌ای. بخش‌هایی که داده مهمی ندارن رو کوتاه کن."""

    elif asset_key == "dollar":
        prompt = f"""تو یک تحلیلگر حرفه‌ای بازار فارکس هستی. تحلیلت باید دقیق، رک و مستقیم باشه — نه خشک و آکادمیک، نه خیلی عامیانه. مثل یه متخصص باتجربه که بدون حاشیه حرف می‌زنه.

📅 تاریخ: {today}
📈 داده‌های شاخص دلار DXY: {md_text}

🌐 دیدگاه تحلیلگران از وب:
{analyst_info}

📆 رویدادهای اقتصادی امروز:
{econ_calendar}

---
تحلیل شاخص دلار رو با این ساختار بنویس:

۱. 📊 وضعیت DXY
   سطح فعلی، تغییر روزانه و اینکه دلار الان کجا ایستاده

۲. 📈 تحلیل تکنیکال
   سطوح حمایت و مقاومت کلیدی، روند غالب

۳. 🌍 سیاست پولی و اقتصاد کلان
   آخرین موضع‌گیری فدرال رزرو، وضعیت تورم
   اگه امروز داده اقتصادی کلیدی مثل CPI، NFP، FOMC یا GDP داریم، حتماً تأثیرش رو تحلیل کن

۴. 🎯 جمع‌بندی و بایاس روزانه
   صریح و قاطع بگو: صعودی / نزولی / خنثی — و دلیلت رو توضیح بده

حدود ۲۰۰ کلمه. فارسی روان و حرفه‌ای. فقط بخش‌هایی که داده واقعی داری رو بنویس."""

    else:  # gold
        prompt = f"""تو یک تحلیلگر حرفه‌ای بازار طلا هستی. تحلیلت باید دقیق، رک و مستقیم باشه — نه خشک و آکادمیک، نه خیلی عامیانه. مثل یه متخصص باتجربه که بدون حاشیه حرف می‌زنه.

📅 تاریخ: {today}
📈 داده‌های اونس جهانی XAU/USD: {md_text}

🌐 دیدگاه تحلیلگران از وب:
{analyst_info}

📆 رویدادهای اقتصادی امروز:
{econ_calendar}

---
تحلیل اونس جهانی طلا رو با این ساختار بنویس:

۱. 📊 وضعیت قیمت
   قیمت فعلی، تغییر روزانه و اینکه طلا الان کجا ایستاده

۲. 📈 تحلیل تکنیکال
   سطوح حمایت و مقاومت کلیدی، روند غالب

۳. 🌍 فاندامنتال و سنتیمنت
   تنش‌های ژئوپلیتیک، سیاست پولی، خرید بانک‌های مرکزی
   اگه امروز داده اقتصادی کلیدی مثل CPI، NFP، FOMC یا GDP داریم، حتماً تأثیرش رو تحلیل کن

۴. 👥 موضع‌گیری تحلیلگران
   دیدگاه غالب در بازار: خرید یا فروش؟

۵. 🎯 جمع‌بندی و بایاس روزانه
   صریح و قاطع بگو: صعودی / نزولی / خنثی — و دلیلت رو توضیح بده

حدود ۲۵۰ کلمه. فارسی روان و حرفه‌ای."""

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