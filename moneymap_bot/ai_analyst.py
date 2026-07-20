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

    market_data = await _fetch_market_data(asset["ticker"])
    analyst_info = await _search_analyst_opinions(asset["search_query"])

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

    prompt = f"""تو یه تحلیلگر مالی باحال و صمیمی هستی که با زبان ساده و عامیانه فارسی حرف می‌زنی. مثل یه دوست متخصص که داره به رفیقش توضیح میده.

📅 تاریخ: {today}
📊 دارایی: {asset['fa_name']}
📈 داده‌های بازار: {md_text}

🌐 اخبار و نظرات تحلیلگران از وب:
{analyst_info}

---
یه تحلیل بنویس که شامل این ۵ بخش باشه. لحن: صمیمی، ساده، عامیانه — مثل پیام واتساپ به یه دوست تریدر:

۱. 📊 بازار الان کجاست؟
   قیمت، تغییر امروز رو ساده توضیح بده

۲. 📈 تکنیکال چی میگه؟
   حمایت و مقاومت مهم، روند — ساده و کوتاه

۳. 🌍 فاندامنتال و سنتیمنت
   جنگ، سیاست پولی، اخبار مهم — اثرشون رو توضیح بده

۴. 👥 تحلیلگرا چی میگن؟
   پوزیشن‌شون لانگه یا شورت؟ چرا؟

۵. 🎯 بایاس امروز
   صریح بگو: صعودی / نزولی / خنثی — با دلیل

حدود ۲۵۰ کلمه. فارسی محاوره‌ای و راحت. از کلمات سنگین پرهیز کن."""

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