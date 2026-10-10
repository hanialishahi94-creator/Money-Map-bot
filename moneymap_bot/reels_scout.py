"""
reels_scout.py — شکار موضوع‌های داغ ریلز مالی از اینستاگرام (پیج‌های مرجع + هشتگ‌های فارسی)

هر بار اجرا:
  ۱) ریلزهای اخیر پیج‌های مرجع (هم‌سبک پیج خودمون) و چند هشتگ مالی فارسی رو می‌گیره (با sessionid)
  ۲) ریلزهایی از پیج‌های مرجع که خیلی بیشتر از میانگین همون پیج دیده شدن = موضوع داغ؛
     از هشتگ‌ها فقط ریلزهای فارسی، کوتاه (≤ ۶۵ ثانیه)، تازه و پربازدید
  ۳) با Groq موضوع‌های داغ رو دسته‌بندی می‌کنه و برای هر کدوم ایده‌ی ریلز ۶۰ ثانیه‌ای می‌نویسه
  ۴) خروجی = لیست پیام‌های تلگرام (HTML) با لینک ریلزهای نمونه‌ی ایرانی

متغیرهای محیطی:
  IG_SESSIONID   — کوکی sessionid اکانت اینستاگرام (ترجیحاً یک اکانت فرعی، نه اکانت اصلی)
  REFERENCE_PAGES — (اختیاری) یوزرنیم پیج‌های مرجع، جدا با کاما — پیش‌فرض: REFERENCE_PAGES_DEFAULT
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
from ai_analyst import _clean_ai_output, groq_chat

logger = logging.getLogger(__name__)

HASHTAGS = [
    "طلا", "دلار", "بورس", "ارز_دیجیتال", "بیت_کوین", "سرمایه_گذاری",
    "ترید", "اقتصاد", "سکه", "بازار_مالی", "فارکس", "پول", "سواد_مالی", "کریپتو",
]
HASHTAGS_PER_RUN = 3          # برای کم کردن ریسک بلاک، هر بار فقط چند هشتگ (چرخشی)
REFERENCE_PAGES_DEFAULT = ["lurax.news", "golabi.economy", "vilifinance", "mikofinance"]
TOP_REFERENCE = 15            # چندتا از ریلزهای پیج‌های مرجع به AI داده بشه
TOP_HASHTAG = 10              # چندتا از ریلزهای هشتگ‌ها
MAX_DURATION = 65             # ثانیه
MAX_AGE_DAYS = 7
SENT_KEY = "reels_scout_sent"
ROTATION_KEY = "reels_scout_rotation"

STYLE = (
    "پیج‌های اخبار و توضیح ساده‌ی اقتصاد و پول برای مخاطب عام ایرانی — مثل @lurax.news، @golabi.economy، "
    "@vilifinance و @mikofinance: خبر اقتصادی روز با زبان ساده، چرا قیمت دلار/طلا/سکه/مسکن/خودرو تغییر کرد، "
    "تورم و قدرت خرید، تحریم و سیاست روی اقتصاد، بورس و کریپتو به زبان ساده، سواد مالی و مدیریت پول شخصی، "
    "داستان‌های جذاب اقتصادی و برندها"
)

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
    # مرورگر کوکی رو به شکل encode‌شده (‎%3A‎ به‌جای ‎:‎) می‌فرسته؛ همون شکل رو بفرستیم
    decoded = urllib.parse.unquote(sessionid)
    cookies = {"sessionid": urllib.parse.quote(decoded, safe="")}
    if ":" in decoded:
        cookies["ds_user_id"] = decoded.split(":", 1)[0]
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
    if r.status_code in (301, 302, 401, 403):
        location = r.headers.get("location", "")
        if "challenge" in location or "checkpoint" in location:
            raise InstagramAuthError(f"{r.status_code} challenge — اینستا تأیید امنیتی می‌خواد")
        raise InstagramAuthError(f"{r.status_code} login_required {location[:60]}".strip())
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
        if node.get("shortcode") and "taken_at_timestamp" in node:   # فرمت GraphQL (پروفایل وب)
            likes = (node.get("edge_liked_by") or node.get("edge_media_preview_like") or {}).get("count", 0)
            cap_edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
            out.append({
                "code": node["shortcode"],
                "media_type": 2 if node.get("is_video") else 1,
                "taken_at": node["taken_at_timestamp"],
                "video_duration": node.get("video_duration") or 0,
                "play_count": node.get("video_view_count") or 0,
                "like_count": likes,
                "comment_count": (node.get("edge_media_to_comment") or {}).get("count", 0),
                "caption": {"text": cap_edges[0]["node"]["text"] if cap_edges else ""},
                "user": {"username": (node.get("owner") or {}).get("username", "")},
            })
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


PAGES_KEY = "reels_scout_pages"


def normalize_page(text: str) -> str:
    """لینک کامل اینستا، ‎@یوزرنیم یا یوزرنیم خالی → یوزرنیم تمیز."""
    text = text.strip()
    text = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", text, flags=re.I)
    text = text.split("?")[0].split("/")[0].strip("@ ").lower()
    return text if re.fullmatch(r"[a-z0-9._]{1,30}", text) else ""


def reference_pages() -> list[str]:
    """لیست پیج‌های مرجع: اول از دیتابیس (قابل تغییر از تلگرام)، بعد env، بعد پیش‌فرض."""
    stored = db.get_setting(PAGES_KEY)
    if stored is not None:
        return json.loads(stored)
    raw = os.getenv("REFERENCE_PAGES", "").strip()
    pages = [p for p in re.split(r"[,\s]+", raw) if p] if raw else REFERENCE_PAGES_DEFAULT
    return [p for p in (normalize_page(x) for x in pages) if p]


def add_reference_page(text: str) -> tuple[str, bool]:
    """(یوزرنیم، اضافه شد؟) — یوزرنیم خالی یعنی ورودی نامعتبر بود."""
    page = normalize_page(text)
    pages = reference_pages()
    if not page or page in pages:
        return page, False
    db.set_setting(PAGES_KEY, json.dumps(pages + [page]))
    return page, True


def remove_reference_page(text: str) -> tuple[str, bool]:
    page = normalize_page(text)
    pages = reference_pages()
    if page not in pages:
        return page, False
    db.set_setting(PAGES_KEY, json.dumps([p for p in pages if p != page]))
    return page, True


def _fetch_page(client, username: str) -> list[dict]:
    """آخرین پست‌های یک پیج + نسبت بازدید هر ریلز به میانه‌ی بازدید همون پیج."""
    try:
        # همون endpointی که صفحه‌ی پروفایل وب اینستا برای گرید پست‌ها صدا می‌زنه
        data = _get_json(client, f"/api/v1/feed/user/{username}/username/", {"count": 24})
    except InstagramAuthError:
        raise
    except Exception as e:
        logger.info(f"reels_scout @{username} feed failed ({e}) — fallback web_profile_info")
        time.sleep(random.uniform(2, 4))
        data = _get_json(client, "/api/v1/users/web_profile_info/", {"username": username})
    medias = []
    _walk_medias(data, medias)
    views = sorted(_views(m) for m in medias if m.get("media_type") == 2 and _views(m))
    median = views[len(views) // 2] if views else 0
    for m in medias:
        user = m.get("user") or {}
        user["username"] = user.get("username") or username
        m["user"] = user
        m["_ratio"] = round(_views(m) / median, 1) if median else 0
    return medias


def _collect_medias() -> list:
    """جمع‌آوری ریلز از پیج‌های مرجع و هشتگ‌ها (sync — داخل thread اجرا می‌شه)."""
    medias, errors, ok = [], [], 0
    with _http_client() as client:
        sources = [(f"@{p}", "page", p) for p in reference_pages()] + \
                  [(f"#{t}", "tag", t) for t in _next_hashtags()]
        for source, kind, name in sources:
            try:
                found = _fetch_page(client, name) if kind == "page" else _fetch_hashtag(client, name)
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
            "ratio": m.get("_ratio", 0),
            "score": _score(m),
        })
    # پیج‌های مرجع: اونایی که نسبت به میانگین خود پیج بیشتر ترکوندن؛ هشتگ‌ها: سرعت بازدید
    refs = sorted((c for c in out if c["source"].startswith("@")), key=lambda c: c["ratio"], reverse=True)
    tags = sorted((c for c in out if c["source"].startswith("#")), key=lambda c: c["score"], reverse=True)
    return refs[:TOP_REFERENCE] + tags[:TOP_HASHTAG]


def _remember_sent(codes: list[str]):
    sent = json.loads(db.get_setting(SENT_KEY, "[]") or "[]")
    sent = (sent + codes)[-600:]
    db.set_setting(SENT_KEY, json.dumps(sent))


# ─── AI: دسته‌بندی موضوع و ایده‌ی ریلز ────────────────────────────────────────

async def _analyze(candidates: list[dict]) -> list[dict]:
    listing = "\n".join(
        f"[{i}] منبع:{c['source']} بازدید:{c['views']} لایک:{c['likes']} کامنت:{c['comments']} مدت:{c['duration']}ث"
        + (f" — {c['ratio']} برابر میانگین بازدید همین پیج" if c["ratio"] else "")
        + f"\nکپشن: {c['caption'].replace(chr(10), ' ')}"
        for i, c in enumerate(candidates)
    )
    prompt = f"""تو استراتژیست محتوای اینستاگرام برای پیج Money MAP هستی. سبک پیج:
{STYLE}

این‌ها ریلزهای تازه‌ی همین روزها هستن. اونایی که منبعشون @ هست از پیج‌های هم‌سبک ما هستن و «برابر میانگین» یعنی نسبت به بقیه‌ی ریلزهای همون پیج چقدر بیشتر دیده شده (بالاتر = موضوع داغ‌تر). اونایی که منبعشون # هست از هشتگ‌ها هستن و ممکنه پرت باشن:

{listing}

کار تو:
۱) هر ریلزی که به سبک پیج ما نمی‌خوره رو کامل نادیده بگیر: انگیزشی و موفقیت، فروش دوره/سیگنال/پامپ، تبلیغ صرافی، لایف‌استایل، طنز بی‌ربط، آموزش تخصصی تحلیل تکنیکال.
۲) از بقیه ۳ تا ۵ «موضوع داغ» دربیار که بشه باهاش یک ریلز حداکثر ۶۰ ثانیه‌ای خفن به سبک این پیج‌ها ساخت. اولویت با موضوع‌هایی که در پیج‌های مرجع چند برابر میانگین دیده شدن.
۳) برای هر موضوع بنویس: چرا الان داغه، یک هوک ۳ ثانیه‌ی اول (جمله‌ی دقیق)، ساختار کوتاه ریلز، و شماره‌ی ریلزهای نمونه از لیست بالا (۱ تا ۳ تا، فقط مرتبط‌ها).

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
    content = await groq_chat(prompt, kind="large", max_tokens=3000, temperature=0.6, max_retries=3, json_mode=True)
    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise ValueError(f"خروجی AI قابل خوندن نیست: {content[:150]}")
    return json.loads(match.group(0))


# ─── ساخت پیام‌ها ─────────────────────────────────────────────────────────────

def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _example_line(c: dict) -> str:
    stats = f"👁 {_fmt_num(c['views'])}" if c["views"] else f"❤️ {_fmt_num(c['likes'])}"
    if c.get("ratio", 0) >= 1.5:
        stats += f" · 🚀 {c['ratio']}x میانگین پیج"
    return f"▫️ <a href=\"{c['url']}\">@{html.escape(c['user'])}</a> — {stats} · {c['duration']}ث"


def _build_messages(topics: list[dict], candidates: list[dict]) -> tuple[list[str], list[str]]:
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3, minutes=30)))
    messages = [
        f"🎬 <b>موضوع‌های داغ ریلز مالی</b>\n🕘 {now.strftime('%Y/%m/%d — %H:%M')}\n"
        f"از {len(candidates)} ریلز تازه‌ی پیج‌های مرجع و هشتگ‌ها"
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
