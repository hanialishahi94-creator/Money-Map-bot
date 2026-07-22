"""
opportunity_scorer.py — امتیاز فرصت سرمایه‌گذاری (۰ تا ۱۰۰)

دارایی‌های پوشش داده‌شده:
  • صندوق‌های طلا  — حباب میانگین از fundbase.ir
  • صندوق‌های نقره — حباب میانگین از tradersarena.ir
  • طلا ۱۸ عیار    — حباب قیمت بازار vs ارزش ذاتی (اونس × دلار)
  • سکه تمام       — حباب قیمت بازار vs ارزش ذاتی سکه
  • دلار            — تغییر قیمت نسبت به دیروز (ذخیره‌شده در DB)

امتیاز ۰–۱۰۰:
  🟢 ≥ ۸۰  فرصت خوب
  🟡 ۶۰–۷۹  متوسط
  🟠 ۴۰–۵۹  احتیاط
  🔴  < ۴۰  ریسک بالا
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


# ─── ابزار پایه ──────────────────────────────────────────────────────────────

async def _tgju(symbol: str) -> float | None:
    """دریافت قیمت لحظه‌ای از tgju — برمی‌گردونه به ریال."""
    import aiohttp
    url = f"https://api.tgju.org/v1/market/indicator/summary-table-data/{symbol}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                rows = data.get("data", [])
                if rows:
                    return float(str(rows[0][3]).replace(",", ""))
    except Exception as e:
        logger.error(f"tgju [{symbol}]: {e}")
    return None


def _bubble_to_score(bubble_pct: float) -> int:
    """
    تبدیل درصد حباب به امتیاز.
    حباب صفر → ۸۰ | حباب منفی (ارزنده) → بالاتر | حباب مثبت (گران) → پایین‌تر
    """
    return max(5, min(100, int(80 - bubble_pct * 3.5)))


def _change_to_score(change_pct: float) -> int:
    """
    برای دلار: تغییر قیمت نسبت به دیروز.
    افت قیمت → فرصت خرید بهتر → امتیاز بالاتر
    رشد قیمت → گران‌تر شدن → امتیاز پایین‌تر
    """
    return max(5, min(95, int(60 - change_pct * 6)))


def _score_label(score: int) -> str:
    if score >= 80:
        return "🟢"
    elif score >= 60:
        return "🟡"
    elif score >= 40:
        return "🟠"
    else:
        return "🔴"


# ─── امتیازدهی هر دارایی ─────────────────────────────────────────────────────

async def score_gold_18k() -> int | None:
    """طلا ۱۸ عیار — حباب قیمت بازار vs ارزش ذاتی."""
    ons, dollar_rl, gold18_rl = await asyncio.gather(
        _tgju("ons"),
        _tgju("price_dollar_rl"),
        _tgju("geram18"),
    )
    if not all([ons, dollar_rl, gold18_rl]):
        return None
    dollar_toman = dollar_rl / 10
    market_toman = gold18_rl / 10
    intrinsic = (ons / 31.1035) * 0.75 * dollar_toman
    bubble = (market_toman - intrinsic) / intrinsic * 100
    return _bubble_to_score(bubble)


async def score_sekeh() -> int | None:
    """سکه تمام بهار آزادی — حباب قیمت بازار vs ارزش ذاتی."""
    ons, dollar_rl, sekeh_rl = await asyncio.gather(
        _tgju("ons"),
        _tgju("price_dollar_rl"),
        _tgju("sekeb"),
    )
    if not all([ons, dollar_rl, sekeh_rl]):
        return None
    dollar_toman = dollar_rl / 10
    sekeh_toman  = sekeh_rl / 10
    # سکه بهار آزادی: ۸.۱۳۳ گرم با خلوص ۹۰٪
    intrinsic = (ons / 31.1035) * 8.133 * 0.9 * dollar_toman
    bubble = (sekeh_toman - intrinsic) / intrinsic * 100
    return _bubble_to_score(bubble)


async def score_gold_funds() -> int | None:
    """صندوق‌های طلا — میانگین حباب کل از fundbase.ir."""
    import aiohttp
    from html.parser import HTMLParser

    class _TP(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_t = self.in_r = self.in_c = False
            self.rows, self.row, self.cell, self.depth = [], [], "", 0

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.in_t = True; self.depth += 1
            elif tag == "tr" and self.in_t:
                self.in_r = True; self.row = []
            elif tag in ("td", "th") and self.in_r:
                self.in_c = True; self.cell = ""

        def handle_endtag(self, tag):
            if tag == "table":
                self.depth -= 1
                if self.depth == 0: self.in_t = False
            elif tag == "tr" and self.in_r:
                if self.row: self.rows.append(self.row[:])
                self.in_r = False
            elif tag in ("td", "th") and self.in_c:
                self.row.append(self.cell.strip()); self.in_c = False

        def handle_data(self, data):
            if self.in_c: self.cell += data

    try:
        hdrs = {"User-Agent": "Mozilla/5.0", "Accept-Language": "fa-IR,fa;q=0.9"}
        async with aiohttp.ClientSession() as s:
            async with s.get("https://fundbase.ir/h", headers=hdrs,
                             timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                html = await r.text(encoding="utf-8", errors="ignore")

        tp = _TP(); tp.feed(html)
        bubbles = []
        for row in tp.rows:
            if len(row) >= 5 and row[0] not in ("نماد", "صندوق", ""):
                raw = (row[4]
                       .replace("٪", "").replace("%", "").replace("‎", "")
                       .replace("+", "").replace("−", "-").strip())
                try:
                    bubbles.append(float(raw))
                except ValueError:
                    pass
        if not bubbles:
            return None
        return _bubble_to_score(sum(bubbles) / len(bubbles))
    except Exception as e:
        logger.error(f"score_gold_funds: {e}")
        return None


async def score_silver_funds() -> int | None:
    """صندوق‌های نقره — میانگین حباب کل از tradersarena.ir."""
    import aiohttp, time as _t
    url = (f"https://tradersarena.ir/data/industries-stocks-csv/silver-funds"
           f"?_={int(_t.time() * 1000)}")
    hdrs = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://tradersarena.ir/industries/silver-funds",
        "Accept": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=hdrs, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status != 200:
                    return None
                rows = await r.json(content_type=None)
        bubbles = []
        for row in rows:
            if isinstance(row, list) and len(row) >= 16 and row[15] is not None:
                try:
                    bubbles.append(float(row[15]))
                except (TypeError, ValueError):
                    pass
        if not bubbles:
            return None
        return _bubble_to_score(sum(bubbles) / len(bubbles))
    except Exception as e:
        logger.error(f"score_silver_funds: {e}")
        return None


async def score_dollar() -> int | None:
    """
    دلار — ترکیب ۴ سیگنال (میانگین هر سیگنالی که داده داشت):
      ۱. تغییر روزانه vs دیروز
      ۲. حباب vs دلار ضمنی درهم  (AED × 3.6725)
      ۳. حباب vs دلار ضمنی طلا   (گرم ۱۸ عیار ÷ ارزش دلاری گرم)
      ۴. روند ۷ روزه
    """
    import db
    import datetime

    today = datetime.date.today()
    today_str = today.isoformat()

    # ─── دریافت همه قیمت‌ها به صورت موازی ──────────────────────────────────
    price_rl, aed_rl, ons, geram18_rl = await asyncio.gather(
        _tgju("price_dollar_rl"),
        _tgju("price_aed_rl"),
        _tgju("ons"),
        _tgju("geram18"),
    )

    if price_rl is None:
        return None

    dollar_toman = price_rl / 10

    # ذخیره قیمت امروز در DB (برای روزهای بعد)
    db.save_dollar_price(today_str, dollar_toman)

    signals = []

    # ─── سیگنال ۱: تغییر روزانه ─────────────────────────────────────────────
    yesterday_str = (today - datetime.timedelta(days=1)).isoformat()
    prev_day = db.get_dollar_price(yesterday_str)
    if prev_day:
        change_pct = (dollar_toman - prev_day) / prev_day * 100
        signals.append(max(5, min(95, int(60 - change_pct * 6))))

    # ─── سیگنال ۲: حباب دلار vs دلار ضمنی درهم ─────────────────────────────
    # ۱ USD = 3.6725 AED (نرخ ثابت پِگ امارات)
    if aed_rl:
        aed_toman = aed_rl / 10
        implied_from_aed = aed_toman * 3.6725
        bubble_aed = (dollar_toman - implied_from_aed) / implied_from_aed * 100
        signals.append(max(5, min(95, int(80 - bubble_aed * 3.5))))

    # ─── سیگنال ۳: حباب دلار vs دلار ضمنی طلا ──────────────────────────────
    # دلار ضمنی = قیمت طلای ۱۸ تومانی ÷ ارزش دلاری هر گرم (اونس÷31.1×0.75)
    if ons and geram18_rl:
        geram18_toman = geram18_rl / 10
        gold_usd_per_gram = (ons / 31.1035) * 0.75
        implied_from_gold = geram18_toman / gold_usd_per_gram
        bubble_gold = (dollar_toman - implied_from_gold) / implied_from_gold * 100
        signals.append(max(5, min(95, int(80 - bubble_gold * 3.5))))

    # ─── سیگنال ۴: روند ۷ روزه ──────────────────────────────────────────────
    week_ago_str = (today - datetime.timedelta(days=7)).isoformat()
    prev_week = db.get_dollar_price(week_ago_str)
    if prev_week:
        trend_7d = (dollar_toman - prev_week) / prev_week * 100
        # ضریب کمتر چون افت هفتگی خیلی نوسانی‌تره
        signals.append(max(5, min(95, int(60 - trend_7d * 2))))

    if not signals:
        return 55   # هنوز داده کافی نیست → امتیاز خنثی

    return max(5, min(95, int(sum(signals) / len(signals))))


# ─── تابع اصلی ───────────────────────────────────────────────────────────────

async def get_all_scores() -> dict:
    """
    دریافت همه امتیازها به صورت موازی.
    برمی‌گردونه dict با کلیدهای:
      gold_funds | silver_funds | gold_18k | sekeh | dollar
    هر مقدار عدد ۵-۱۰۰ یا None در صورت خطا.
    """
    results = await asyncio.gather(
        score_gold_funds(),
        score_silver_funds(),
        score_gold_18k(),
        score_sekeh(),
        score_dollar(),
        return_exceptions=True,
    )
    keys = ["gold_funds", "silver_funds", "gold_18k", "sekeh", "dollar"]
    out = {}
    for k, v in zip(keys, results):
        out[k] = v if isinstance(v, int) else None
    return out


def format_scores(scores: dict) -> str:
    """فرمت نهایی خروجی — فقط امتیاز."""
    assets = [
        ("gold_funds",   "صندوق‌های طلا"),
        ("silver_funds", "صندوق‌های نقره"),
        ("gold_18k",     "طلا ۱۸ عیار"),
        ("sekeh",        "سکه تمام"),
        ("dollar",       "دلار"),
    ]
    lines = ["📊 امتیاز فرصت‌ها\n"]
    for key, label in assets:
        score = scores.get(key)
        if score is None:
            lines.append(f"⚪ {label}: —")
        else:
            lines.append(f"{_score_label(score)} {label}: {score}/۱۰۰")
    lines.append("\n🟢 ≥۸۰  ·  🟡 ۶۰–۷۹  ·  🟠 ۴۰–۵۹  ·  🔴 <۴۰")
    return "\n".join(lines)