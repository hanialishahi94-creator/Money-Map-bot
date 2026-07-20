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


def _gemini_model():
    """مدل Gemini با SDK اصلی Google."""
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("متغیر محیطی GEMINI_API_KEY تنظیم نشده است.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


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


async def _call_gemini(prompt: str) -> str:
    """ارسال پرامپت به Gemini و دریافت پاسخ (non-blocking)."""
    loop = asyncio.get_event_loop()

    def _generate():
        model = _gemini_model()
        response = model.generate_content(prompt)
        return response.text

    return await loop.run_in_executor(None, _generate)


async def generate_analysis(asset_key: str) -> str:
    """تولید تحلیل روزانه برای یک دارایی."""
    asset = ASSETS[asset_key]
    today = datetime.datetime.now(TEHRAN_TZ).strftime("%Y/%m/%d")

    market_data = await _fetch_market_data(asset["ticker"])
    analyst_info = await _search_analyst_opinions(asset["search_query"])

    if market_data:
        md_text = (
            f"قیمت فعلی: {market_data.get('price', 'N/A')} | "
            f"تغییر: {market_data.get('change', 'N/A')} ({market_data.get('change_pct', 'N/A')}%) | "
            f"سقف روز: {market_data.get('high', 'N/A')} | کف روز: {market_data.get('low', 'N/A')} | "
            f"بسته دیروز: {market_data.get('prev_close', 'N/A')} | "
            f"سابقه ۵ روز: {market_data.get('recent', [])}"
        )
    else:
        md_text = "داده‌های قیمتی در دسترس نیستند — از دانش به‌روز خود استفاده کن."

    prompt = f"""تو یک تحلیلگر مالی حرفه‌ای هستی. تحلیل روزانه زیر را کامل و حرفه‌ای به فارسی بنویس.

📅 تاریخ امروز: {today}
📊 دارایی: {asset['fa_name']}
📈 داده‌های بازار: {md_text}

🌐 اخبار و نظرات تحلیلگران از وب:
{analyst_info}

---
تحلیل جامع بنویس که حتماً شامل این ۵ بخش باشه:

۱. 📊 وضعیت فعلی بازار
   قیمت، حرکت امروز، مقایسه با دیروز

۲. 📈 تحلیل تکنیکال
   سطوح مهم حمایت و مقاومت، روند کوتاه‌مدت، الگوهای قیمتی

۳. 🌍 سنتیمنت و فاندامنتال
   تأثیر تنش‌های جنگ و سیاسی، تصمیمات بانک مرکزی و فدرال رزرو، اخبار مهم

۴. 👥 نظر تحلیلگران
   تحلیلگران بازار امروز چه پوزیشنی گرفتن (لانگ/شورت/خنثی) و چرا

۵. 🎯 بایاس روزانه
   مشخصاً بگو: صعودی / نزولی / خنثی — با دلیل روشن

قالب: پاراگراف‌های کوتاه فارسی روان. حدود ۳۰۰ کلمه. حرفه‌ای و قابل اعتماد."""

    return await _call_gemini(prompt)


async def edit_analysis(original_text: str, edit_prompt: str, asset_key: str) -> str:
    """ویرایش تحلیل موجود بر اساس دستور ادمین."""
    asset = ASSETS[asset_key]

    prompt = f"""تحلیل زیر برای {asset['fa_name']} نوشته شده:

{original_text}

---
دستور ویرایش از ادمین: {edit_prompt}

تحلیل رو دقیقاً طبق دستور ویرایش کن. ساختار ۵ بخشی و فرمت فارسی رو حفظ کن."""

    return await _call_gemini(prompt)