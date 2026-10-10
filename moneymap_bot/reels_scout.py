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
IG_APP_ID = "936619743392459"  # app-id نسخه‌ی وب اینستاگرام
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


class InstagramAuthError(RuntimeError):
    pass


# ─── اینستاگرام (API نسخه‌ی وب — همونی که مرورگر استفاده می‌کنه) ──────────────

def _http_client():
    import httpx
    import urllib.parse
    sessionid = os.getenv("IG_SESSIONID", "").strip()
    if not sessionid:
        raise RuntimeError("IG_SESSIONID تنظیم نشده")
    sessionid = urllib.parse.unquote(sessionid)
    cookies = {"sessionid": sessionid}
    if ":" in sessionid:
        cookies["ds_user_id"] = sessionid.split(":", 1)[0]
    kwargs = {}
    proxy = os.getenv("IG_PROXY", "").strip()
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.Client(
        base_url="https://www.instagram.com",
        cookies=cookies,
        headers={
            "User-Agent": USER_AGENT,
            "X-IG-App-ID": IG_APP_ID,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.instagram.com/",
        },
        timeout=30,
        follow_redirects=False,
        **kwargs,
    )


def _get_json(client, path: str, params: dict) -> dict:
    r = client.get(path, params=params)
    if r.status_code in (301, 302) or r.status_code in (401, 403):
        raise InstagramAuthError(f"{r.status_code} login_required")
    r.raise_for_status()
    try:
        data = r.json()
    except ValueError:
        raise InstagramAuthError("پاسخ JSON نبود (احتمالاً صفحه‌ی لاگین)")
    if data.get("require_login") or data.get("message") in ("login_required", "checkpoint_required"):
        raise InstagramAuthError(data.get("message") or "login_required")
    return data


def _walk_medias(node, out: list):
    """همه‌ی آبجکت‌های مدیا رو از هر ساختار JSON بیرون می‌کشه (مستقل از چیدمان پاسخ اینستا)."""
    if isinstance(node, dict):
        if node.get("code") and "media_type" in node and "taken_at" in node:
            out.append(node)
            return
        for v in node.values():
            _walk_medias(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_medias(v, out)


def _next_hashtags() -> list[str]:
    start = int(db.get_setting(ROTATION_KEY, 0) or 0) % len(HASHTAGS)
    picked = [HASHTAGS[(start + i) % len(HASHTAGS)] for i in range(HASHTAGS_PER_RUN)]
    db.set_setting(ROTATION_KEY, (start + HASHTAGS_PER_RUN) % len(HASHTAGS))
    return picked


def _fetch_hashtag(client, tag: str) -> list[dict]:
    try:
        data = _get_json(client, "/api/v1/tags/web_info/", {"tag_name": tag})
    except InstagramAuthError:
        raise
    except Exception:
        # endpoint جایگزین (جستجوی وب) اگه web_info جواب نداد
        data = _get_json(client, "/api/v1/fbsearch/web/top_serp/", {"query": f"#{tag}"})
    medias = []
    _walk_medias(data, medias)
    return medias


def _collect_medias() -> list:
    """جمع‌آوری ریلز از اکسپلور و هشتگ‌ها (sync — داخل thread اجرا می‌شه)."""
    medias, errors, ok = [], [], 0
    with _http_client() as client:
        sources = [("explore", None)] + [(f"#{t}", t) for t in _next_hashtags()]
        for source, tag in sources:
            try:
                if tag is None:
                    data = _get_json(client, "/api/v1/discover/web/explore_grid/", {
                        "is_nonpersonalized_explore": "false",
                        "include_fixed_destinations": "true",
                        "is_prefetch": "false",
                        "omit_cover_media": "false",
                    })
                    found = []
                    _walk_medias(data, found)
                else:
                    found = _fetch_hashtag(client, tag)
                ok += 1
                medias += [(m, source) for m in found]
                logger.info(f"reels_scout {source}: {len(found)} media")
            except Exception as e:
                logger.warning(f"reels_scout {source}: {e}")
                errors.append(f"{source}: {e}")
            time.sleep(random.uniform(2, 5))
    if ok == 0:
        raise RuntimeError(
            "اینستاگرام به هیچ درخواستی جواب نداد:\n" + "\n".join(errors[:3]) +
            "\n\nاحتمالاً sessionid منقضی شده یا اینستا IP سرور رو بلاک کرده (راه‌حل: sessionid تازه یا IG_PROXY)."
        )
    return medias


def _is_finance(caption: str) -> bool:
    return any(k in caption for k in FINANCE_KEYWORDS)


def _views(m: dict) -> int:
    return int(m.get("play_count") or m.get("ig_play_count") or m.get("view_count") or 0)


def _score(m: dict) -> float:
    views = _views(m)
    if not views:
        views = int(m.get("like_count") or 0) * 30 + int(m.get("comment_count") or 0) * 100
    taken = m.get("taken_at") or (time.time() - MAX_AGE_DAYS * 86400)
    age_hours = max((time.time() - taken) / 3600, 6)
    return views / age_hours


def _filter_candidates(raw: list) -> list[dict]:
    sent = set(json.loads(db.get_setting(SENT_KEY, "[]") or "[]"))
    now = time.time()
    seen, out = set(), []
    for m, source in raw:
        code = m.get("code")
        caption = ((m.get("caption") or {}).get("text") or "") if isinstance(m.get("caption"), dict) else ""
        if code in seen or code in sent:
            continue
        if m.get("media_type") != 2:
            continue
        duration = m.get("video_duration") or 0
        if duration and duration > MAX_DURATION:
            continue
        if m.get("taken_at") and now - m["taken_at"] > MAX_AGE_DAYS * 86400:
            continue
        if not _PERSIAN_RE.search(caption):
            continue
        if source == "explore" and not _is_finance(caption):
            continue
        seen.add(code)
        out.append({
            "code": code,
            "url": f"https://www.instagram.com/reel/{code}/",
            "user": (m.get("user") or {}).get("username", ""),
            "views": _views(m),
            "likes": int(m.get("like_count") or 0),
            "comments": int(m.get("comment_count") or 0),
            "duration": round(duration),
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
        return [f"🎬 از {len(raw)} پست دریافتی از اینستاگرام، ریلز مالی فارسیِ تازه‌ی جدیدی پیدا نشد (یا همه قبلاً فرستاده شده بودن)."]
    try:
        topics = await _analyze(candidates)
        messages, used = _build_messages(topics, candidates) if topics else _fallback_messages(candidates)
    except Exception as e:
        logger.warning(f"reels_scout AI: {e}")
        messages, used = _fallback_messages(candidates)
    _remember_sent(used)
    return messages
