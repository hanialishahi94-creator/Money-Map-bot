"""
reels_scout.py — شکار موضوع‌های داغ ریلز مالی از اینستاگرام (اکسپلور + هشتگ‌های فارسی)

هر بار اجرا:
  ۱) ریلزهای اکسپلور و چند هشتگ مالی فارسی رو از اینستاگرام می‌گیره (با sessionid یک اکانت لاگین‌شده)
  ۲) فقط ریلزهای فارسی، کوتاه (≤ ۶۵ ثانیه)، تازه و پربازدید رو نگه می‌داره
  ۳) با Groq موضوع‌های داغ رو دسته‌بندی می‌کنه و برای هر کدوم ایده‌ی ریلز ۶۰ ثانیه‌ای می‌نویسه
  ۴) خروجی = لیست پیام‌های تلگرام (HTML) با لینک ریلزهای نمونه‌ی ایرانی

متغیرهای محیطی:
  IG_SESSIONID   — کوکی sessionid اکانت اینستاگرام (ترجیحاً یک اکانت فرعی، نه اکانت اصلی)
  IG_PROXY       — (اختیاری) پراکسی، مثلاً http://user:pass@host:port — IP سرورها معمولاً توسط اینستا محدود می‌شه
"""
import os
import re
import json
import time
import html
import random
import asyncio
import logging
import datetime

import db
from ai_analyst import _clean_ai_output

logger = logging.getLogger(__name__)

HASHTAGS = [
    "طلا", "دلار", "بورس", "ارز_دیجیتال", "بیت_کوین", "سرمایه_گذاری",
    "ترید", "اقتصاد", "سکه", "بازار_مالی", "فارکس", "پول", "سواد_مالی", "کریپتو",
]
HASHTAGS_PER_RUN = 5          # برای کم کردن ریسک بلاک، هر بار فقط چند هشتگ (چرخشی)
MAX_DURATION = 65             # ثانیه
MAX_AGE_DAYS = 7
TOP_CANDIDATES = 25
SENT_KEY = "reels_scout_sent"
ROTATION_KEY = "reels_scout_rotation"

FINANCE_KEYWORDS = [
    "طلا", "دلار", "بورس", "سکه", "ارز", "بیت", "کریپتو", "سرمایه", "ترید", "اقتصاد",
    "تورم", "پول", "سهام", "فارکس", "بازار", "نرخ", "قیمت", "پس‌انداز", "پس انداز", "درآمد",
    "مالی", "بانک", "وام", "مسکن", "خودرو", "اونس", "تتر", "صرافی",
]

_PERSIAN_RE = re.compile(r"[؀-ۿ]")
_client = None


# ─── اینستاگرام ───────────────────────────────────────────────────────────────

def _get_client():
    global _client
    if _client is not None:
        return _client
    sessionid = os.getenv("IG_SESSIONID", "").strip()
    if not sessionid:
        raise RuntimeError("IG_SESSIONID تنظیم نشده")
    from instagrapi import Client
    cl = Client()
    cl.delay_range = [2, 5]
    proxy = os.getenv("IG_PROXY", "").strip()
    if proxy:
        cl.set_proxy(proxy)
    cl.login_by_sessionid(sessionid)
    _client = cl
    return cl


def _next_hashtags() -> list[str]:
    start = int(db.get_setting(ROTATION_KEY, 0) or 0) % len(HASHTAGS)
    picked = [HASHTAGS[(start + i) % len(HASHTAGS)] for i in range(HASHTAGS_PER_RUN)]
    db.set_setting(ROTATION_KEY, (start + HASHTAGS_PER_RUN) % len(HASHTAGS))
    return picked


def _collect_medias() -> list:
    """جمع‌آوری ریلز از اکسپلور و هشتگ‌ها (sync — داخل thread اجرا می‌شه)."""
    global _client
    cl = _get_client()
    medias = []
    try:
        medias += [(m, "explore") for m in cl.explore_reels(amount=40)]
    except Exception as e:
        logger.warning(f"reels_scout explore: {e}")
        if "login" in str(e).lower():
            _client = None
            raise
    for tag in _next_hashtags():
        time.sleep(random.uniform(3, 7))
        try:
            medias += [(m, f"#{tag}") for m in cl.hashtag_medias_reels_v1(tag, amount=27)]
        except Exception as e:
            logger.warning(f"reels_scout hashtag {tag}: {e}")
    return medias


def _is_finance(caption: str) -> bool:
    return any(k in caption for k in FINANCE_KEYWORDS)


def _score(m) -> float:
    views = m.play_count or m.view_count or 0
    if not views:
        views = (m.like_count or 0) * 30 + (m.comment_count or 0) * 100
    taken = m.taken_at.timestamp() if m.taken_at else time.time() - MAX_AGE_DAYS * 86400
    age_hours = max((time.time() - taken) / 3600, 6)
    return views / age_hours


def _filter_candidates(raw: list) -> list[dict]:
    sent = set(json.loads(db.get_setting(SENT_KEY, "[]") or "[]"))
    now = time.time()
    seen, out = set(), []
    for m, source in raw:
        caption = m.caption_text or ""
        if m.code in seen or m.code in sent:
            continue
        if m.media_type != 2:
            continue
        if m.video_duration and m.video_duration > MAX_DURATION:
            continue
        if m.taken_at and now - m.taken_at.timestamp() > MAX_AGE_DAYS * 86400:
            continue
        if not _PERSIAN_RE.search(caption):
            continue
        if source == "explore" and not _is_finance(caption):
            continue
        seen.add(m.code)
        out.append({
            "code": m.code,
            "url": f"https://www.instagram.com/reel/{m.code}/",
            "user": m.user.username if m.user else "",
            "views": m.play_count or m.view_count or 0,
            "likes": m.like_count or 0,
            "comments": m.comment_count or 0,
            "duration": round(m.video_duration or 0),
            "caption": caption[:400],
            "source": source,
            "score": _score(m),
        })
    out.sort(key=lambda c: c["score"], reverse=True)
    return out[:TOP_CANDIDATES]


def _remember_sent(codes: list[str]):
    sent = json.loads(db.get_setting(SENT_KEY, "[]") or "[]")
    sent = (sent + codes)[-600:]
    db.set_setting(SENT_KEY, json.dumps(sent))


# ─── AI: دسته‌بندی موضوع و ایده‌ی ریلز ────────────────────────────────────────

async def _analyze(candidates: list[dict]) -> list[dict]:
    listing = "\n".join(
        f"[{i}] بازدید:{c['views']} لایک:{c['likes']} کامنت:{c['comments']} مدت:{c['duration']}ث منبع:{c['source']}\n"
        f"کپشن: {c['caption'].replace(chr(10), ' ')}"
        for i, c in enumerate(candidates)
    )
    prompt = f"""تو استراتژیست محتوای اینستاگرام برای یک پیج آموزش و تحلیل بازارهای مالی ایران (طلا، دلار، سکه، بورس، کریپتو) هستی.

این‌ها ریلزهای فارسی پربازدید و تازه‌ی همین روزها از اکسپلور و هشتگ‌های مالی هستن:

{listing}

کار تو:
۱) از بینشون ۳ تا ۵ «موضوع داغ» دربیار که بشه باهاش یک ریلز حداکثر ۶۰ ثانیه‌ای خفن و وایرال ساخت.
۲) برای هر موضوع بنویس: چرا الان داغه، یک هوک ۳ ثانیه‌ی اول (جمله‌ی دقیق)، ساختار کوتاه ریلز، و شماره‌ی ریلزهای نمونه از لیست بالا (۱ تا ۳ تا).

فقط و فقط یک JSON معتبر برگردون، بدون هیچ متن اضافه، با این ساختار:
{{"topics": [{{"title": "...", "why": "...", "hook": "...", "outline": "...", "examples": [0, 3]}}]}}"""
    topics = (await _groq_json(prompt)).get("topics", [])
    out = []
    for t in topics:
        if not isinstance(t, dict) or not t.get("title"):
            continue
        for k in ("title", "why", "hook", "outline"):
            if isinstance(t.get(k), str):
                t[k] = _clean_ai_output(t[k].replace("«", "").replace("»", "")).strip("\"' ")
        out.append(t)
    return out


async def _groq_json(prompt: str) -> dict:
    """فراخوانی Groq در حالت JSON (بدون پاک‌ساز متنی که ممکنه JSON رو خراب کنه)."""
    import httpx
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY تنظیم نشده")
    for attempt in range(3):
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2500,
                    "temperature": 0.6,
                    "response_format": {"type": "json_object"},
                },
            )
        if response.status_code == 429 and attempt < 2:
            await asyncio.sleep(int(response.headers.get("retry-after", 20)))
            continue
        response.raise_for_status()
        return json.loads(response.json()["choices"][0]["message"]["content"])
    raise RuntimeError("Groq شلوغه")


# ─── ساخت پیام‌ها ─────────────────────────────────────────────────────────────

def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _example_line(c: dict) -> str:
    stats = f"👁 {_fmt_num(c['views'])}" if c["views"] else f"❤️ {_fmt_num(c['likes'])}"
    return f"▫️ <a href=\"{c['url']}\">@{html.escape(c['user'])}</a> — {stats} · {c['duration']}ث"


def _build_messages(topics: list[dict], candidates: list[dict]) -> tuple[list[str], list[str]]:
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3, minutes=30)))
    messages = [
        f"🎬 <b>موضوع‌های داغ ریلز مالی</b>\n🕘 {now.strftime('%Y/%m/%d — %H:%M')}\n"
        f"از {len(candidates)} ریلز پربازدید فارسی اکسپلور و هشتگ‌ها"
    ]
    used = []
    for i, t in enumerate(topics, 1):
        examples = [candidates[j] for j in t.get("examples", []) if isinstance(j, int) and 0 <= j < len(candidates)]
        used += [c["code"] for c in examples]
        msg = f"🔥 <b>{i}. {html.escape(str(t['title']))}</b>\n\n"
        if t.get("why"):
            msg += f"📈 <b>چرا داغه:</b> {html.escape(str(t['why']))}\n\n"
        if t.get("hook"):
            msg += f"🎯 <b>هوک ۳ ثانیه اول:</b>\n«{html.escape(str(t['hook']))}»\n\n"
        if t.get("outline"):
            msg += f"🧩 <b>ساختار ریلز:</b> {html.escape(str(t['outline']))}\n\n"
        if examples:
            msg += "🇮🇷 <b>نمونه‌ها:</b>\n" + "\n".join(_example_line(c) for c in examples)
        messages.append(msg.strip())
    return messages, used


def _fallback_messages(candidates: list[dict]) -> tuple[list[str], list[str]]:
    top = candidates[:10]
    msg = "🎬 <b>پربازدیدترین ریلزهای مالی فارسی</b>\n(تحلیل AI در دسترس نبود)\n\n"
    msg += "\n\n".join(
        f"{_example_line(c)}\n{html.escape(c['caption'][:120].replace(chr(10), ' '))}" for c in top
    )
    return [msg], [c["code"] for c in top]


async def scout() -> list[str]:
    """اجرای کامل؛ لیست پیام‌های آماده‌ی ارسال (HTML) رو برمی‌گردونه."""
    raw = await asyncio.to_thread(_collect_medias)
    candidates = _filter_candidates(raw)
    if not candidates:
        return ["🎬 ریلز مالی تازه‌ی جدیدی پیدا نشد (یا همه قبلاً فرستاده شده بودن)."]
    try:
        topics = await _analyze(candidates)
        messages, used = _build_messages(topics, candidates) if topics else _fallback_messages(candidates)
    except Exception as e:
        logger.warning(f"reels_scout AI: {e}")
        messages, used = _fallback_messages(candidates)
    _remember_sent(used)
    return messages
