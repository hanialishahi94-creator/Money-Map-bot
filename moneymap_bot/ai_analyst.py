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
    """ارسال پرامپت به Groq LLaMA و دریافت پاسخ فارسی پاک — با retry خودکار برای 429."""
    import httpx
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY تنظیم نشده")
        return "❌ خطا: کلید GROQ_API_KEY تنظیم نشده."

    max_retries = 4
    base_delay = 15  # ثانیه — شروع انتظار بعد از 429

    for attempt in range(max_retries):
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

                if response.status_code == 429:
                    # از هدر Retry-After استفاده کن اگه موجود بود
                    retry_after = int(response.headers.get("retry-after", base_delay * (attempt + 1)))
                    logger.warning(f"Groq 429 — تلاش {attempt + 1}/{max_retries} — صبر {retry_after}s")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        return "❌ سرور AI شلوغه، چند دقیقه دیگه دوباره امتحان کن."

                response.raise_for_status()
                result = response.json()["choices"][0]["message"]["content"]
                return _clean_ai_output(result)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                delay = base_delay * (attempt + 1)
                logger.warning(f"Groq 429 HTTPStatusError — صبر {delay}s")
                await asyncio.sleep(delay)
                continue
            logger.error(f"خطا در فراخوانی Groq: {e}")
            return f"❌ خطا در تولید تحلیل: {e}"
        except Exception as e:
            logger.error(f"خطا در فراخوانی Groq: {e}")
            return f"❌ خطا در تولید تحلیل: {e}"

    return "❌ سرور AI شلوغه، چند دقیقه دیگه دوباره امتحان کن."


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


async def _fetch_sentiment(asset_key: str) -> str:
    """دریافت سنتیمنت لحظه‌ای بازار."""
    import httpx
    result = {}

    # ── کریپتو Fear & Greed (alternative.me) ────────────────────────────────
    if asset_key == "bitcoin":
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get("https://api.alternative.me/fng/?limit=1")
                r.raise_for_status()
                data = r.json()["data"][0]
                value = int(data["value"])
                label = data["value_classification"]
                result["crypto_fng"] = f"Crypto Fear & Greed: {value}/100 ({label})"
        except Exception as e:
            logger.warning(f"crypto fng error: {e}")

    # ── CNN Fear & Greed (بازار کلی — فقط برای بیتکوین و طلا) ──────────────
    if asset_key != "dollar":
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cnn.com/"},
                )
                r.raise_for_status()
                score = r.json()["fear_and_greed"]["score"]
                rating = r.json()["fear_and_greed"]["rating"]
                result["cnn_fng"] = f"CNN Fear & Greed (بازار کلی): {score:.0f}/100 ({rating})"
        except Exception as e:
            logger.warning(f"CNN fng error: {e}")

    if not result:
        return "N/A"

    return " | ".join(result.values())


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

    market_data, analyst_info, sentiment_data = await asyncio.gather(
        _fetch_market_data(asset["ticker"]),
        _search_analyst_opinions(asset["search_query"]),
        _fetch_sentiment(asset_key),
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
        asset_emoji = "₿"
    elif asset_key == "dollar":
        asset_label = "شاخص دلار (DXY)"
        asset_emoji = "📊"
    else:
        asset_label = "اونس جهانی طلا (XAU/USD)"
        asset_emoji = "🌐"

    prompt = f"""تاریخ: {today}
دارایی: {asset_label}
داده‌های قیمتی: {md_text}{sr_note}

سنتیمنت:
{sentiment_data}

اطلاعات وب:
{analyst_info}

---

تو یه تریدر حرفه‌ای هستی که داری به یه دوست تریدر توضیح می‌دی الان {asset_label} کجاست و چی داره می‌گه. یه پاراگراف بنویس، فقط فارسی، حداکثر ۱۵۰ کلمه.

این سه چیز رو بگو:
- سنتیمنت الان چطوره؟ بازار ریسک می‌کنه یا فرار می‌کنه؟ چه تأثیری رو {asset_label} داره؟
- بایاس کلی چیه و چرا؟
- اگه حمایت بشکنه چی می‌شه، اگه مقاومت بشکنه چی می‌شه؟

سبک نوشتن:
- مستقیم و تیز بنویس. مثل کسی که واقعاً چارت داره نگاه می‌کنه.
- جمله‌های کوتاه. بدون پیچیده‌کاری.
- از این جور جمله‌ها استفاده کن: «تا وقتی این سطح رو داره»، «اگه اینجا بشکنه»، «فعلاً فروشنده‌ها کنترل دارن»، «خریدار هنوز قوی نشده»
- هیچ جمله‌ی کتابی یا ربات‌وار ننویس. نه «بازار در انتظار است»، نه «احتمالاً شاهد خواهیم بود».
- اسم {asset_label} رو درست بنویس. هیچ دارایی دیگه‌ای نیار.
- اسم سبک تحلیلی نیار.
- اعداد رو محدوده بنویس نه عدد دقیق."""

    return await _call_groq(prompt)


# ─── ریرایت سیگنال ───────────────────────────────────────────────────────────

async def rewrite_signal(raw_signal: str) -> str:
    """
    سیگنال خام (انگلیسی یا فارسی رسمی) رو به فارسی محاوره‌ای تریدری ریرایت می‌کنه.
    اعداد، جهت (buy/sell) و جزئیات مهم رو حفظ می‌کنه.
    """
    prompt = f"""یه سیگنال ترید دریافت شدم. اونو بازنویسی کن.

سیگنال اصلی:
{raw_signal}

---

قوانین بازنویسی:
- فقط فارسی بنویس
- لحن: مثل یه تریدر حرفه‌ای که داره به دوستش می‌گه — مستقیم، بدون حاشیه
- همه اعداد مهم رو حفظ کن: قیمت ورود، حد ضرر، تارگت
- جهت معامله (خرید/فروش) رو واضح بنویس
- هیچ اطلاعاتی اضافه یا کم نکن — فقط سبک رو عوض کن
- حداکثر ۵ خط
- اسم دارایی رو فارسی بنویس (Bitcoin → بیتکوین، Gold → طلا، XAUUSD → اونس طلا و غیره)
- هیچ توضیح اضافه، سلام یا امضا نزن"""

    return await _call_groq(prompt)


# ─── ویرایش تحلیل ────────────────────────────────────────────────────────────

async def edit_analysis(original_text: str, edit_prompt: str, asset_key: str) -> str:
    """ویرایش تحلیل موجود بر اساس دستور ادمین."""
    asset = ASSETS[asset_key]

    prompt = f"""این تحلیل برای {asset['fa_name']} نوشته شده:

{original_text}

---
دستور ویرایش: {edit_prompt}

تحلیل رو طبق دستور ویرایش کن. سبک نوشتن رو حفظ کن — مستقیم، تیز، مثل تریدری که داره به یه دوست توضیح می‌ده. فقط فارسی. یه پاراگراف."""

    return await _call_groq(prompt)