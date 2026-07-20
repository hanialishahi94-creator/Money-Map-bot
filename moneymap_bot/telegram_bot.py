import os
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.error import TelegramError
import logging
import asyncio
from bs4 import BeautifulSoup
import db

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")  # توکن ربات از متغیر محیطی (Railway -> Variables -> BOT_TOKEN)
ADMIN_GROUP_ID = -1004358699434  # آیدی گروه ادمین
SUPPORT_GROUP_ID = -1004347648811  # آیدی گروه پشتیبانی
CHANNEL_USERNAME = "@Money_Mapp"  # یوزرنیم کانال (ربات باید توش ادمین باشه)

# ===== تنظیمات VIP =====
VIP_CHANNEL_LINK = os.getenv("VIP_CHANNEL_LINK", "https://t.me/+6zpQXNwZD41mYWZk")
VIP_PRICE_USDT = 20  # مقدار پیش‌فرض — مقدار واقعی از طریق db.get_vip_price_usdt() و پنل ادمین قابل تغییر است
VIP_CARD_NUMBER = "6219-8610-1704-6631"
VIP_CARD_OWNER = "هانیه علیشاهی"
VIP_DAYS = 30  # مقدار پیش‌فرض — مقدار واقعی از طریق db.get_vip_days() و پنل ادمین قابل تغییر است
VIP_CHANNEL_ID = -1003794396104  # آیدی کانال خصوصی VIP


CAR_PRICE_LIST = [
    # سایپا (5 مدل)
    ("کوییک",               "https://www.hamrah-mechanic.com/carprice/saipa/quick/"),
    ("شاهین",               "https://www.hamrah-mechanic.com/carprice/saipa/shahin/"),
    ("تیبا",                "https://www.hamrah-mechanic.com/carprice/saipa/tiba/"),
    ("ساینا",               "https://www.hamrah-mechanic.com/carprice/saipa/saina/"),
    ("سهند",                "https://www.hamrah-mechanic.com/carprice/saipa/sahand/"),
    # ایران‌خودرو (7 مدل)
    ("دنا",                 "https://www.hamrah-mechanic.com/carprice/irankhodro/dena/"),
    ("دنا پلاس",            "https://www.hamrah-mechanic.com/carprice/irankhodro/denaplus/"),
    ("تارا",                "https://www.hamrah-mechanic.com/carprice/irankhodro/tara/"),
    ("۲۰۷ اتوماتیک",       "https://www.hamrah-mechanic.com/carprice/irankhodro/peugeot207/1405/2884/"),
    ("۲۰۷ دنده‌ای تیپ ۵",  "https://www.hamrah-mechanic.com/carprice/irankhodro/peugeot207/1405/2874/?clr=ColorWhite"),
    ("رانا پلاس",           "https://www.hamrah-mechanic.com/carprice/irankhodro/runna/"),
    # چینی‌ها (5 مدل)
    ("ری‌را",               "https://www.hamrah-mechanic.com/carprice/irankhodro/reera/"),
    ("هاوال اچ ۶",          "https://www.hamrah-mechanic.com/carprice/haval/h6/"),
    ("جک جی ۴",            "https://www.hamrah-mechanic.com/carprice/jac/j4kermanmotor/"),
    ("چانگان سی‌اس ۳۵",    "https://www.hamrah-mechanic.com/carprice/changan/cs35%20plus/"),
    ("ام‌وی‌ام ایکس ۲۲",   "https://www.hamrah-mechanic.com/carprice/mvm/mvmx22/"),
]


def _vip_price_usdt() -> float:
    """قیمت اشتراک VIP را از تنظیمات پنل ادمین می‌خواند (در صورت نبود، مقدار پیش‌فرض)."""
    return db.get_vip_price_usdt(VIP_PRICE_USDT)


def _vip_days() -> int:
    """مدت اشتراک VIP را از تنظیمات پنل ادمین می‌خواند (در صورت نبود، مقدار پیش‌فرض)."""
    return db.get_vip_days(VIP_DAYS)

# ===================================================
# ✏️ تحلیل‌ها و اعضای VIP حالا از دیتابیس (db.py) خوانده می‌شوند
# تا با هر ری‌استارت شدن بات از بین نروند. آپدیت تحلیل‌ها از طریق
# پنل ادمین انجام می‌شود؛ این دیکشنری فقط برای سازگاری با کد قبلی نگه داشته شده.
# ===================================================

def _format_vip_date(ts: float) -> str:
    """تبدیل timestamp به تاریخ خوانا (میلادی) برای نمایش به کاربر"""
    import datetime
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%Y/%m/%d")
    except Exception:
        return "نامشخص"


def _get_analysis_text(asset: str) -> str:
    """متن کامل تحلیل (همراه تاریخ) را از دیتابیس برمی‌گرداند."""
    row = db.get_analysis(asset)
    if not row:
        return "هنوز تحلیلی ثبت نشده است."
    date_line = f"📅 تاریخ تحلیل: {row['analysis_date']}\n\n" if row.get("analysis_date") else ""
    return date_line + (row.get("text") or "")

# ===================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# توجه: کاربران و اعضای VIP حالا در دیتابیس (db.py) ذخیره می‌شوند، نه در حافظه.
ASK_NAME, ASK_PHONE, CHECK_MEMBERSHIP, MAIN_MENU, GOLD_CALC_OUNCE, GOLD_CALC_DOLLAR, VIP_RECEIPT, ALERT_ENTER_PRICE, ALERT_ENTER_MESSAGE = range(9)

# ===== تنظیمات هشدار قیمت =====
ALERT_ASSET_INFO = {
    "gold":       {"label": "طلای ۱۸ عیار",       "emoji": "🥇", "symbol": "geram18",         "divisor": 10, "unit": "تومان"},
    "dollar":     {"label": "دلار آمریکا",          "emoji": "💵", "symbol": "price_dollar_rl", "divisor": 10, "unit": "تومان"},
    "bitcoin":    {"label": "بیتکوین",              "emoji": "₿",  "symbol": "crypto-bitcoin-irr", "divisor": 10, "unit": "دلار"},
    "silver":     {"label": "نقره داخلی (هر گرم)", "emoji": "🥈", "symbol": "silver",          "divisor": 10, "unit": "تومان"},
    "ethereum":   {"label": "اتریوم",               "emoji": "Ξ",  "symbol": "crypto-ethereum-irr", "divisor": 10, "unit": "دلار"},
    "gold_ounce": {"label": "اونس جهانی طلا",       "emoji": "🌐", "symbol": "ons",            "divisor": 1,  "unit": "دلار"},
}


# ===== چک کردن عضویت کانال =====
async def is_member_of_channel(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except TelegramError as e:
        logger.error(f"خطا در چک عضویت: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # هر بار /start زده بشه، از اول شروع می‌کنیم (اسم و شماره دوباره پرسیده می‌شه)
    # اگه کاربر از طریق لینک رفرال (معرفی دوستان) وارد شده باشه، آیدی معرف رو موقتاً ذخیره کن
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg[4:])
                if referrer_id != update.effective_user.id:
                    context.user_data["referrer_id"] = referrer_id
            except ValueError:
                pass
    await update.message.reply_text(
        "👋 سلام! به ربات تحلیل بازار خوش اومدی.\n\n"
        "لطفاً اسمت رو بنویس:"
    )
    return ASK_NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    phone_button = KeyboardButton("📱 اشتراک‌گذاری شماره", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[phone_button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"ممنون {context.user_data['name']} عزیز! 🙏\n\n"
        "حالا لطفاً شماره موبایلت رو به اشتراک بذار:",
        reply_markup=keyboard,
    )
    return ASK_PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone = contact.phone_number

    await _process_phone(update, context, phone)
    return CHECK_MEMBERSHIP


async def get_phone_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اگر کاربر به‌جای زدن دکمه، شماره رو با کیبورد تایپ کرد"""
    text = update.message.text.strip()
    # حذف فاصله‌ها و خط‌تیره‌های احتمالی
    cleaned = re.sub(r"[\s\-]", "", text)
    # تبدیل ارقام فارسی/عربی به انگلیسی
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    for i, d in enumerate(persian_digits):
        cleaned = cleaned.replace(d, str(i))
    for i, d in enumerate(arabic_digits):
        cleaned = cleaned.replace(d, str(i))

    # فرمت‌های قابل قبول: 09xxxxxxxxx یا +989xxxxxxxxx یا 00989xxxxxxxxx
    is_valid = bool(
        re.fullmatch(r"09\d{9}", cleaned)
        or re.fullmatch(r"(\+98|0098)9\d{9}", cleaned)
    )

    if is_valid:
        # تبدیل به فرمت یکدست +98
        if cleaned.startswith("09"):
            phone = "+98" + cleaned[1:]
        elif cleaned.startswith("0098"):
            phone = "+98" + cleaned[4:]
        else:
            phone = cleaned
        await _process_phone(update, context, phone)
        return CHECK_MEMBERSHIP

    # شماره معتبر نبود -> راهنمایی کن، بات رو ساکت نگه نداریم
    phone_button = KeyboardButton("📱 اشتراک‌گذاری شماره", request_contact=True)
    keyboard = ReplyKeyboardMarkup([[phone_button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "⚠️ این فرمت شماره قابل قبول نیست.\n\n"
        "ساده‌ترین راه: روی دکمه «📱 اشتراک‌گذاری شماره» پایین صفحه بزن، تلگرام خودش شماره‌ات رو می‌فرسته.\n\n"
        "یا اگه می‌خوای دستی بنویسی، شماره رو به یکی از این شکل‌ها وارد کن:\n"
        "• 09123456789\n"
        "• +989123456789",
        reply_markup=keyboard,
    )
    return ASK_PHONE


async def _process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    user_id = update.effective_user.id
    name = context.user_data["name"]
    username = update.effective_user.username or "ندارد"

    db.upsert_user(user_id, name, phone, username)
    logger.info(f"کاربر جدید: {name} - {phone}")

    # اگه از طریق لینک رفرال وارد شده، فقط معرفش رو ثبت کن
    # (جایزه و گزارش رفرال بعداً، فقط وقتی این کاربر واقعاً عضو کانال بشه، چک می‌شه)
    referrer_id = context.user_data.get("referrer_id")
    if referrer_id:
        db.set_referrer(user_id, referrer_id)

    # ارسال اطلاعات به گروه ادمین
    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=f"👤 کاربر جدید ثبت‌نام کرد!\n\n"
                 f"📛 اسم: {name}\n"
                 f"📱 شماره: {phone}\n"
                 f"🔗 یوزرنیم: @{username}\n"
                 f"🆔 آیدی: {user_id}"
        )
    except Exception as e:
        logger.error(f"خطا در ارسال به گروه: {e}")

    await update.message.reply_text(
        f"✅ ثبت‌نام با موفقیت انجام شد!\n"
        f"👤 اسم: {name}\n"
        f"📱 شماره: {phone}",
        reply_markup=ReplyKeyboardRemove(),
    )

    # حالا چک کن عضو کانال هست یا نه
    await ask_to_join_channel(update, context)
    return CHECK_MEMBERSHIP


# ===== سیستم رفرال: گزارش خودکار به معرف به ازای هر عضویت موفق =====
async def _notify_referrer_progress(referrer_id: int, context: ContextTypes.DEFAULT_TYPE):
    """هر بار که یکی از دوستانِ معرفی‌شده‌ی این کاربر واقعاً عضو کانال شد،
    یه گزارش پیشرفت خودکار براش می‌فرسته (حتی اگه هنوز به جایزه نهایی نرسیده باشه)."""
    if not db.is_referral_enabled():
        return
    required = db.get_referral_required_count()
    confirmed = db.get_confirmed_referral_count(referrer_id)
    progress = confirmed % required if confirmed % required != 0 or confirmed == 0 else required
    try:
        await context.bot.send_message(
            chat_id=referrer_id,
            text=(
                "🎉 خبر خوب! یکی از دوستایی که معرفی کردی عضو کانال شد.\n\n"
                f"📊 پیشرفت فعلی تو: {progress}/{required} نفر"
            ),
        )
    except Exception as e:
        logger.error(f"خطا در ارسال گزارش پیشرفت رفرال به {referrer_id}: {e}")


# ===== سیستم رفرال: چک و اعطای جایزه عضویت رایگان =====
async def _check_referral_reward(referrer_id: int, context: ContextTypes.DEFAULT_TYPE):
    """بعد از اینکه یه کاربر جدید واقعاً عضو کانال شد، چک می‌کنه آیا معرفش
    به تعداد لازم (مثلاً ۸ نفر) رسیده یا نه. اگه رسیده و کمپین رفرال فعال باشه،
    عضویت VIP/کانال سیگنال رایگان براش فعال می‌کنه."""
    if not db.is_referral_enabled():
        return

    required = db.get_referral_required_count()
    confirmed = db.get_confirmed_referral_count(referrer_id)
    rewards_given = db.get_referral_rewards_given(referrer_id)
    earned_batches = confirmed // required

    if earned_batches <= rewards_given:
        return  # هنوز جایزه جدیدی تعلق نگرفته

    new_batches = earned_batches - rewards_given
    for _ in range(new_batches):
        db.increment_referral_rewards_given(referrer_id)

    new_expire = db.add_vip_days(referrer_id, _vip_days() * new_batches)

    try:
        invite = await context.bot.create_chat_invite_link(
            chat_id=VIP_CHANNEL_ID, member_limit=1, name=f"VIP-REF-{referrer_id}"
        )
        link = invite.invite_link
    except Exception as e:
        logger.error(f"خطا در ساخت لینک رفرال: {e}")
        link = VIP_CHANNEL_LINK

    try:
        expire_str = _format_vip_date(new_expire)
        await context.bot.send_message(
            chat_id=referrer_id,
            text=f"🎉 تبریک! شما {required} نفر رو با موفقیت معرفی کردی و عضویت کانال سیگنال برات رایگان فعال شد!\n\n"
                 f"🔗 لینک ورود به کانال (یکبار مصرف):\n{link}\n\n"
                 f"⏳ این اشتراک تا تاریخ {expire_str} معتبر است.",
        )
    except Exception as e:
        logger.error(f"خطا در اطلاع‌رسانی جایزه رفرال به {referrer_id}: {e}")


# ===== درخواست عضویت در کانال =====
async def ask_to_join_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")],
        [InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_membership")],
    ])
    text = (
        "🔒 برای استفاده از تحلیل‌ها باید عضو کانال ما باشی!\n\n"
        f"کانال: {CHANNEL_USERNAME}\n\n"
        "بعد از عضویت روی دکمه «عضو شدم» بزن 👇"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)


# ===== چک دکمه "عضو شدم" =====
async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    is_member = await is_member_of_channel(context.bot, user_id)

    if is_member:
        await query.message.reply_text("✅ عضویت تایید شد! خوش اومدی 🎉")

        # اگه این اولین‌باره که عضویتش ثبت می‌شه و از طریق رفرال اومده، به معرفش گزارش بده و چک کن جایزه‌ای تعلق گرفته یا نه
        newly_joined = db.mark_channel_joined(user_id)
        if newly_joined:
            referrer_id = db.get_referred_by(user_id)
            if referrer_id:
                await _notify_referrer_progress(referrer_id, context)
                await _check_referral_reward(referrer_id, context)

        await show_main_menu(update, context)
        return MAIN_MENU
    else:
        await query.message.reply_text(
            "❌ هنوز عضو کانال نشدی!\n"
            f"لطفاً اول عضو {CHANNEL_USERNAME} بشو، بعد دوباره دکمه رو بزن."
        )
        return CHECK_MEMBERSHIP


# ===== سنتیمنت بازار (Myfxbook) =====
MYFXBOOK_EMAIL    = os.environ.get("MYFXBOOK_EMAIL", "")
MYFXBOOK_PASSWORD = os.environ.get("MYFXBOOK_PASSWORD", "")

SENTIMENT_SYMBOLS = [
    ("EURUSD", "EUR/USD"),
    ("GBPUSD", "GBP/USD"),
    ("USDJPY", "USD/JPY"),
    ("AUDUSD", "AUD/USD"),
    ("USDCAD", "USD/CAD"),
    ("XAUUSD", "XAU/USD 🥇 طلا"),
    ("XAGUSD", "XAG/USD 🥈 نقره"),
    ("BTCUSD", "BTC/USD ₿ بیتکوین"),
]

_myfxbook_session = {"token": None}


async def get_myfxbook_session() -> str | None:
    if _myfxbook_session["token"]:
        return _myfxbook_session["token"]
    import aiohttp
    from bs4 import BeautifulSoup
    from urllib.parse import urlencode
    params = urlencode({"email": MYFXBOOK_EMAIL, "password": MYFXBOOK_PASSWORD})
    url = f"https://www.myfxbook.com/api/login.json?{params}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json(content_type=None)
                if not data.get("error"):
                    _myfxbook_session["token"] = data["session"]
                    return _myfxbook_session["token"]
                logger.error(f"[myfxbook] خطای لاگین: {data.get('message')}")
    except Exception as e:
        logger.error(f"[myfxbook] استثنا: {e}")
    return None


async def fetch_market_sentiment() -> str:
    import aiohttp
    session = await get_myfxbook_session()
    if not session:
        return "❌ خطا در اتصال به Myfxbook — بررسی کن ایمیل/پسورد درسته."
    url = f"https://www.myfxbook.com/api/get-community-outlook.json?session={session}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json(content_type=None)
                if data.get("error"):
                    _myfxbook_session["token"] = None
                    return "❌ session منقضی شد — دوباره امتحان کن."
                symbols_data = {item["name"]: item for item in data.get("symbols", [])}
                lines = [
                    "📊 *سنتیمنت معامله\u200cگران*\n",
                    
                ]
                for sym, label in SENTIMENT_SYMBOLS:
                    item = symbols_data.get(sym)
                    if not item:
                        continue
                    long_pct  = round(float(item["longPercentage"]))
                    short_pct = 100 - long_pct
                    if long_pct >= 60:
                        color = "🔵"
                    elif short_pct >= 60:
                        color = "🔴"
                    else:
                        color = "🟡"
                    long_bar  = "█" * (long_pct  // 10) + "░" * (10 - long_pct  // 10)
                    short_bar = "█" * (short_pct // 10) + "░" * (10 - short_pct // 10)
                    lines.append(
                        f"{color} *{label}*\n"
                        f"  Long  `{long_bar}` {long_pct}%\n"
                        f"  Short `{short_bar}` {short_pct}%\n"
                    )
                lines.append("🕐 _آپدیت لحظه\u200cای_")
                return "\n".join(lines)
    except Exception as e:
        logger.error(f"[sentiment] خطا: {e}")
        return "❌ خطا در دریافت سنتیمنت"


async def fetch_all_car_prices():
    import json
    from concurrent.futures import ThreadPoolExecutor

    def to_arabic(s):
        return s.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))

    def scrape_one(name, url):
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            r = scraper.get(url, timeout=15)
            if r.status_code != 200:
                logger.warning(f"car [{name}] non-200: {r.status_code}")
                return (name, None)
            html = r.text
            html_ar = to_arabic(html)
            soup = BeautifulSoup(html, "html.parser")

            # روش ۱: JSON-LD Product schema
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "Product":
                        offers = data.get("offers", {})
                        price = offers.get("price") or offers.get("lowPrice")
                        if price:
                            return (name, int(float(str(price).replace(",", ""))))
                except Exception:
                    pass

            # روش ۲: __NEXT_DATA__ (Next.js)
            next_script = soup.find("script", id="__NEXT_DATA__")
            if next_script and next_script.string:
                try:
                    nd = json.loads(next_script.string)
                    nd_text = json.dumps(nd, ensure_ascii=False)
                    for m in re.finditer(r'"(?:price|Price|قیمت)"\s*:\s*"?([\d]{8,12})"?', nd_text):
                        n = int(m.group(1))
                        if 50_000_000 <= n <= 10_000_000_000:
                            return (name, n)
                except Exception:
                    pass

            # روش ۳: meta tag قیمت
            for meta in soup.find_all("meta"):
                prop = (meta.get("property") or meta.get("name") or "").lower()
                if "price" in prop:
                    content = to_arabic(meta.get("content", "")).replace(",", "")
                    if content.isdigit():
                        n = int(content)
                        if 50_000_000 <= n <= 10_000_000_000:
                            return (name, n)

            # روش ۴: اعداد عربی + تومان
            m = re.search(r'([\d,]{7,})\s*تومان', html_ar)
            if m:
                return (name, int(m.group(1).replace(",", "")))

            # روش ۵: اعداد فارسی + تومان
            m = re.search(r'([۰-۹,،]{7,})\s*(?:تومان|ریال)', html)
            if m:
                num = to_arabic(m.group(1)).replace(",", "").replace("،", "")
                if num.isdigit() and len(num) >= 8:
                    return (name, int(num))

            # روش ۶: هر عدد بزرگ در اسکریپت‌ها
            for script in soup.find_all("script"):
                t = script.string or ""
                if not t:
                    continue
                for m in re.finditer(r'"(?:price|Price|قیمت|amount)"\s*:\s*([\d]{8,12})', t):
                    n = int(m.group(1))
                    if 50_000_000 <= n <= 10_000_000_000:
                        return (name, n)

            # debug: لاگ ۳۰۰ کاراکتر اول متن صفحه
            snippet = soup.get_text()[:300].replace("\n", " ")
            logger.warning(f"car [{name}] no price | snippet: {snippet}")
            return (name, None)
        except Exception as e:
            logger.error(f"car [{name}] error: {type(e).__name__}: {e}")
            return (name, None)

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [loop.run_in_executor(executor, scrape_one, n, u) for n, u in CAR_PRICE_LIST]
        results = await asyncio.gather(*futures)

    prev    = db.get_previous_car_prices(hours_ago=20)
    current = {}
    lines   = []

    for name, price in results:
        if price is None:
            lines.append(f"• {name}: خطا")
            continue
        current[name] = price
        p_old = prev.get(name)

        def fmt(n):
            if n >= 1_000_000_000:
                return f"{n / 1_000_000_000:.2f}".rstrip('0').rstrip('.') + " میلیارد تومان"
            return f"{n // 1_000_000:,} میلیون تومان"

        if p_old and p_old != price:
            diff = price - p_old
            pct  = diff / p_old * 100
            sign = "↑" if diff > 0 else "↓"
            lines.append(f"• {name}: {fmt(price)} {sign}{fmt(abs(diff))} ({pct:+.1f}%)")
        else:
            lines.append(f"• {name}: {fmt(price)}")

    if current:
        db.save_car_prices(current)

    # سایپا: 5 | ایران‌خودرو: 6 | چینی: 5
    s, i, c = lines[:5], lines[5:11], lines[11:]
    return "\n".join([
        "🚗 *قیمت صفر پرفروش‌ها*",
        "🔵 *سایپا*", *s, "",
        "🟡 *ایران‌خودرو*", *i, "",
        "🔴 *چینی‌ها*", *c,
    ])


async def car_prices_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⌛ در حال دریافت قیمت‌ها...")
    text = await fetch_all_car_prices()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="car_prices")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    return MAIN_MENU


async def sentiment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ در حال دریافت داده...")
    text = await fetch_market_sentiment()
    _note = (
        "راهنمای استفاده از سنتیمنت:\n\n"
        "داده\u200cی سنتیمنت (Long/Short Ratio) در واقع نشون می\u200cده چند درصد از "
        "معامله\u200cگرها لانگ هستن و چند درصد شورت؛ "
        "یعنی یه تصویر سریع از احساس غالب بازار بهت می\u200cده.\n\n"
        "وقتی مثلاً بالای ۶۵\u066a لانگ باشه، یعنی اکثر تریدرها به رشد قیمت امیدوارن "
        "و بازار به سمت \u00abهیجانی شدن لانگ\u200cها\u00bb رفته که معمولاً می\u200cتونه "
        "یه هشدار باشه برای اصلاح یا شکار لیکوییدیشن لانگ\u200cها. "
        "برعکسش هم وقتی شورت\u200cها زیاد میشن، بازار ممکنه به سمت بالا حرکت کنه.\n\n"
        "در عمل، از این دیتا بیشتر برای تشخیص اشباع احساسات (crowd positioning) "
        "استفاده می\u200cکنیم، نه جهت قطعی؛ یعنی وقتی اکثریت خیلی یک\u200cطرفه شدن، "
        "باید حواست به حرکت خلاف انتظار بازار باشه."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data="sentiment_menu")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)
    await context.bot.send_message(chat_id=query.message.chat_id, text=_note)
    return MAIN_MENU


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
      [InlineKeyboardButton("📊 تحلیل بازار", callback_data="analysis_menu"),
         InlineKeyboardButton("📈 سنتیمنت بازار", callback_data="sentiment_menu")],
        [InlineKeyboardButton("🧮 محاسبه طلا ۱۸ عیار", callback_data="gold_calc"),
         InlineKeyboardButton("🫧 حباب صندوق‌ها", callback_data="bubble_menu")],
        [InlineKeyboardButton("🚗 قیمت خودرو", callback_data="car_prices"),
         InlineKeyboardButton("🗓 تقویم اقتصادی", callback_data="calendar_menu")],
        [InlineKeyboardButton("🔔 هشدار قیمت", callback_data="alert_menu"),
         InlineKeyboardButton("💎 اشتراک VIP سیگنال", callback_data="vip_menu")],
        [InlineKeyboardButton("📞 پشتیبانی", callback_data="support_menu")],
    ])
    user_id = update.effective_user.id
    user_row = db.get_user(user_id)
    name = user_row.get("name", "کاربر") if user_row else "کاربر"
    text = f"سلام {name}! 👋\nیکی از گزینه‌های زیر رو انتخاب کن:"
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)


async def referral_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لینک رفرال شخصی کاربر و وضعیت پیشرفتش"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")]
    ])

    if not db.is_referral_enabled():
        await query.message.reply_text(
            "در حال حاضر کمپین «معرفی دوستان» فعال نیست.",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    required = db.get_referral_required_count()
    confirmed = db.get_confirmed_referral_count(user_id)
    progress = confirmed % required
    rewards_given = db.get_referral_rewards_given(user_id)

    text = (
        "👥 معرفی دوستان\n\n"
        f"اگه {required} نفر رو با لینک زیر به بات معرفی کنی، عضویت کانال سیگنال به‌صورت رایگان برات فعال می‌شه! 🎉\n\n"
        f"🔗 لینک اختصاصی تو:\n{referral_link}\n\n"
        f"📊 پیشرفت فعلی: {progress}/{required} نفر\n"
        f"🎁 تعداد جوایزی که تا الان گرفتی: {rewards_given}"
    )
    await query.message.reply_text(text, reply_markup=keyboard)
    return MAIN_MENU


async def show_analysis_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 تحلیل طلا", callback_data="gold")],
        [InlineKeyboardButton("💵 تحلیل دلار", callback_data="dollar")],
        [InlineKeyboardButton("₿ تحلیل بیتکوین", callback_data="bitcoin")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        "📊 تحلیل بازار\n\nکدام دارایی را می‌خواهی؟",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def show_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # هر بار قبل از نشون دادن تحلیل، دوباره عضویت رو چک کن
    user_id = update.effective_user.id
    is_member = await is_member_of_channel(context.bot, user_id)
    if not is_member:
        await ask_to_join_channel(update, context)
        return CHECK_MEMBERSHIP

    asset_map = {"gold": "🥇 طلا", "dollar": "💵 دلار", "bitcoin": "₿ بیتکوین"}
    asset_key  = query.data
    asset_name = asset_map[asset_key]
    analysis_text = _get_analysis_text(asset_key)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")]
    ])

    # ── ارسال چارت ICT/LIT ──────────────────────────────────────────────────
    try:
        import chart_generator
        import io as _io
        chart_bytes = await chart_generator.generate_chart_bytes_async(asset_key)
        if chart_bytes:
            caption_chart = (
                f"📊 چارت {asset_name}  ·  1H  ·  ICT/LIT Order Block\n"
                f"🟢 ناحیه حمایت  |  🔴 ناحیه مقاومت"
            )
            await query.message.reply_photo(
                photo=_io.BytesIO(chart_bytes),
                caption=caption_chart,
            )
    except Exception as _e:
        logger.warning(f"chart_generator failed for {asset_key}: {_e}")

    # ── ارسال متن تحلیل ─────────────────────────────────────────────────────
    await query.message.reply_text(
        f"📊 تحلیل {asset_name}\n{analysis_text}",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)
    return MAIN_MENU


async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع گفتگوی پشتیبانی - از کاربر می‌خواد پیامش رو بنویسه"""
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_support_message"] = True
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        "📞 پشتیبانی\n\nپیامت رو بنویس و بفرست، در اولین فرصت بهت جواب می‌دیم.",
        reply_markup=keyboard,
    )
    return MAIN_MENU


# ===== گرفتن قیمت لحظه‌ای از tgju =====
async def fetch_tgju_price(symbol: str) -> float | None:
    import aiohttp
    url = f"https://api.tgju.org/v1/market/indicator/summary-table-data/{symbol}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                # مقدار قیمت در فیلد "p" یا "price" هست
                rows = data.get("data", [])
                if rows:
                    raw = rows[0][3]  # ستون چهارم = قیمت پایانی/لحظه‌ای (نه کمترین قیمت روز)
                    price = float(str(raw).replace(",", ""))
                    return price
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت {symbol}: {e}")
    return None


def calc_gold18(ounce_usd: float, dollar_toman: float) -> tuple[float, float]:
    gram_usd = (ounce_usd / 31.1035) * 0.75
    gram_toman = gram_usd * dollar_toman
    return gram_usd, gram_toman


def gold_result_text(ounce_usd: float, dollar_toman: float, source: str, market_price_toman: float | None = None) -> str:
    gram_usd, gram_toman = calc_gold18(ounce_usd, dollar_toman)
    text = (
        f"📊 ارزش واقعی طلای ۱۸ عیار {source}\n"
        f"{'─' * 32}\n"
        f"🔸 اونس جهانی: {ounce_usd:,.2f} دلار\n"
        f"🔸 نرخ دلار (بازار آزاد): {dollar_toman:,.0f} تومان\n"
        f"{'─' * 32}\n"
        f"💰 ارزش واقعی هر گرم طلای ۱۸ عیار:\n"
        f"   {gram_toman:,.0f} تومان"
    )
    if market_price_toman:
        bubble_pct = (market_price_toman - gram_toman) / gram_toman * 100
        text += f"\n🏷️ قیمت بازار طلا: {market_price_toman:,.0f} تومان"
        if bubble_pct > 0.05:
            text += f"\n💬 الان طلا توی بازار حدود {bubble_pct:.1f}٪ گرون‌تر از ارزش واقعیشه."
        elif bubble_pct < -0.05:
            text += f"\n💬 الان طلا توی بازار حدود {abs(bubble_pct):.1f}٪ ارزون‌تر از ارزش واقعیشه."
        else:
            text += "\n💬 الان طلا توی بازار تقریباً برابر با ارزش واقعیشه."
    return text


# ===== ماشین حساب طلای ۱۸ عیار =====
async def gold_calc_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 محاسبه ارزش فعلی", callback_data="gold_live")],
        [InlineKeyboardButton("✏️ محاسبه با مفروضات دلخواه", callback_data="gold_custom")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        "🧮 محاسبه ارزش واقعی طلای ۱۸ عیار\n\nکدام روش را می‌خواهی؟",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def gold_live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("⏳ در حال دریافت قیمت‌های لحظه‌ای ...")

    ounce = await fetch_tgju_price("ons")
    dollar = await fetch_tgju_price("price_dollar_rl")
    market_price_rial = await fetch_tgju_price("geram18")

    if not ounce or not dollar:
        await query.message.reply_text(
            "⚠️ دریافت قیمت لحظه‌ای موفق نبود. لطفاً دقایقی دیگر دوباره امتحان کن یا از روش دستی استفاده کن."
        )
        return MAIN_MENU

    dollar_toman = dollar / 10
    market_price_toman = (market_price_rial / 10) if market_price_rial else None

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی مجدد", callback_data="gold_live")],
        [InlineKeyboardButton("✏️ محاسبه با مفروضات دلخواه", callback_data="gold_custom")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        gold_result_text(ounce, dollar_toman, "لحظه‌ای", market_price_toman),
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def gold_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "✏️ محاسبه با مفروضات دلخواه\n\n"
        "💡 با این ابزار می‌تونی با وارد کردن پیش‌بینی قیمت اونس طلا و نرخ دلار در آینده، "
        "ارزش طلای ۱۸ عیار رو برای هر سناریویی محاسبه کنی.\n\n"
        "مثلاً اگه فکر می‌کنی اونس به ۳۰۰۰ دلار می‌رسه و دلار ۸۰ هزار تومان می‌شه، "
        "همین اعداد رو وارد کن تا ببینی طلا چقدر می‌ارزه.\n\n"
        "━━━━━━━━━━━━━━━━━\n"
        "قیمت اونس جهانی طلا را به دلار وارد کن:\n"
        "(مثال: 2350)"
    )
    return GOLD_CALC_OUNCE


async def gold_calc_get_ounce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "").replace("،", "")
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    for i, d in enumerate(persian_digits):
        text = text.replace(d, str(i))
    try:
        ounce_price = float(text)
        if ounce_price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ عدد معتبر نیست. قیمت اونس را به صورت عددی وارد کن (مثال: 2350):"
        )
        return GOLD_CALC_OUNCE

    context.user_data["ounce_price"] = ounce_price
    await update.message.reply_text(
        f"✅ اونس: {ounce_price:,.0f} دلار\n\n"
        "حالا نرخ دلار به تومان را وارد کن:\n"
        "(مثال: 62000)"
    )
    return GOLD_CALC_DOLLAR


async def gold_calc_get_dollar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "").replace("،", "")
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    for i, d in enumerate(persian_digits):
        text = text.replace(d, str(i))
    try:
        dollar_rate = float(text)
        if dollar_rate <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ عدد معتبر نیست. نرخ دلار را به تومان وارد کن (مثال: 62000):"
        )
        return GOLD_CALC_DOLLAR

    ounce_price = context.user_data["ounce_price"]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 محاسبه مجدد", callback_data="gold_custom")],
        [InlineKeyboardButton("📡 مشاهده قیمت لحظه‌ای", callback_data="gold_live")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await update.message.reply_text(
        gold_result_text(ounce_price, dollar_rate, "با مفروضات شما"),
        reply_markup=keyboard,
    )
    return MAIN_MENU



# ===== تقویم اقتصادی =====

CURRENCY_FA = {
    "USD": "🇺🇸 دلار آمریکا",
    "EUR": "🇪🇺 یورو",
    "GBP": "🇬🇧 پوند انگلیس",
    "AUD": "🇦🇺 دلار استرالیا",
    "NZD": "🇳🇿 دلار نیوزلند",
    "JPY": "🇯🇵 ین ژاپن",
}

TARGET_CURRENCIES = set(CURRENCY_FA.keys())


async def fetch_ff_calendar(week: str = "thisweek") -> list | None:
    import aiohttp
    url = f"https://nfs.faireconomy.media/ff_calendar_{week}.json"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                logger.info(f"FF status: {resp.status}")
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
                logger.info(f"FF count: {len(data)}, sample: {data[0] if data else None}")
                return data
    except Exception as e:
        logger.error(f"خطا در دریافت تقویم: {e}")
        return None


CURRENCY_PRIORITY = {c: i for i, c in enumerate(CURRENCY_FA.keys())}


def filter_events(events: list, today_only: bool = False) -> list:
    from datetime import datetime, timezone, timedelta
    result = []
    now_tehran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    today_str = now_tehran.strftime("%Y-%m-%d")

    for e in events:
        impact = e.get("impact", "").lower()
        if impact != "high":
            continue
        if e.get("country", "") not in TARGET_CURRENCIES:
            continue
        if today_only:
            date_raw = e.get("date", "")
            try:
                dt_utc = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
                dt_tehran = dt_utc + timedelta(hours=3, minutes=30)
                if dt_tehran.strftime("%Y-%m-%d") != today_str:
                    continue
            except Exception:
                continue
        result.append(e)

    result.sort(key=lambda e: CURRENCY_PRIORITY.get(e.get("country", ""), 99))
    return result


def get_asset_impact(title: str, currency: str) -> str:
    t = title.lower()
    if any(k in t for k in ["cpi", "inflation", "pce"]):
        return "🥇 طلا، 💵 دلار"
    if any(k in t for k in ["non-farm", "nonfarm", "employment", "unemployment", "payroll", "jobless"]):
        return "💵 دلار، 🥇 طلا"
    if any(k in t for k in ["interest rate", "fomc", "rate statement", "rate decision", "fed"]):
        return "💵 دلار، 🥇 طلا، ₿ بیت‌کوین"
    if any(k in t for k in ["gdp"]):
        return "💱 ارز ملی، 📈 بورس"
    if any(k in t for k in ["retail sales"]):
        return "💵 دلار، 📈 بورس"
    if any(k in t for k in ["pmi", "manufacturing", "ism"]):
        return "💱 ارز ملی، 📈 بورس"
    if any(k in t for k in ["speech", "speaks", "testimony", "press conference"]):
        return "💵 دلار، ₿ بیت‌کوین"
    return "💱 ارز مربوطه و بازارهای هم‌سو"


def get_data_explanation(title: str) -> str:
    t = title.lower()
    period = ""
    if "m/m" in t:
        period = " نسبت به ماه قبل"
    elif "y/y" in t:
        period = " نسبت به سال قبل"
    elif "q/q" in t:
        period = " نسبت به فصل قبل"

    if "trimmed mean cpi" in t:
        return f"نرخ تورم (نسخه‌ی هرس‌شده که نوسانات شدید رو کنار می‌گذاره){period}."
    if any(k in t for k in ["cpi", "inflation", "pce"]):
        base = "نرخ تورم سالانه" if "y/y" in t else "نرخ تورم ماهانه" if "m/m" in t else "نرخ تورم"
        return f"{base}؛ میزان افزایش قیمت کالا و خدمات مصرفی{period}."
    if "unemployment rate" in t:
        return "درصد افراد بی‌کار از کل نیروی کار."
    if any(k in t for k in ["non-farm", "nonfarm", "employment", "payroll", "jobless"]):
        return "تعداد شغل‌های جدید ایجاد شده؛ نشون‌دهنده‌ی قدرت بازار کار."
    if any(k in t for k in ["interest rate", "fomc", "rate statement", "rate decision", "fed"]):
        return "نرخ بهره‌ای که بانک مرکزی تعیین می‌کنه؛ مهم‌ترین عامل تاثیرگذار روی ارزش پول."
    if "gdp" in t:
        return f"نرخ رشد اقتصادی{period}."
    if "retail sales" in t:
        return f"میزان خرید مصرف‌کننده‌ها{period}؛ نشونه‌ی قدرت اقتصادی مردمه."
    if any(k in t for k in ["pmi", "manufacturing", "ism"]):
        return "وضعیت بخش تولید و کارخانه‌ها؛ بالای ۵۰ یعنی رشد، زیر ۵۰ یعنی رکود."
    if any(k in t for k in ["speech", "speaks", "testimony", "press conference"]):
        return "صحبت‌های رسمی مقامات بانک مرکزی که می‌تونه روی انتظارات بازار اثر بگذاره."
    return "یه شاخص اقتصادی که می‌تونه روی ارزش پول ملی و بازارها اثر بگذاره."


def format_event(e: dict) -> str:
    from datetime import datetime, timezone, timedelta
    currency = e.get("country", "")
    currency_fa = CURRENCY_FA.get(currency, currency)
    title_en = e.get("title", "")
    forecast = e.get("forecast", "") or "—"
    previous = e.get("previous", "") or "—"
    impact = e.get("impact", "").lower()
    impact_icon = "🔴" if impact == "high" else "🟠"
    actual = e.get("actual", "") or ""

    date_raw = e.get("date", "")
    is_published = False
    try:
        dt_utc = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        dt_tehran = dt_utc + timedelta(hours=3, minutes=30)
        time_str = dt_tehran.strftime("%H:%M")
        day_str = dt_tehran.strftime("%Y/%m/%d")
        is_published = dt_utc <= datetime.now(timezone.utc)
    except Exception:
        time_str = "—"
        day_str = "—"

    status_line = f"✅ منتشر شد: {actual}\n" if (is_published and actual) else ""

    explanation = get_data_explanation(title_en)
    return (
        f"{impact_icon} {currency_fa}\n"
        f"📌 {title_en}\n"
        f"📅 {day_str}  ⏰ {time_str} (تهران)\n"
        f"{status_line}"
        f"🔮 پیش‌بینی: {forecast}  |  📊 قبلی: {previous}\n"
        f"ℹ️ {explanation}\n"
    )


async def calendar_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 تقویم امروز", callback_data="cal_today")],
        [InlineKeyboardButton("📆 تقویم این هفته", callback_data="cal_week")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        "🗓 تقویم اقتصادی\n\nاخبار مهم 🔴 ارزهای اصلی\nکدام بازه را می‌خواهی؟",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def calendar_today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("⏳ در حال دریافت تقویم امروز ...")

    events = await fetch_ff_calendar("thisweek")
    if events is None:
        await query.message.reply_text("⚠️ دریافت تقویم موفق نبود. لطفاً بعداً امتحان کن.")
        return MAIN_MENU

    filtered = filter_events(events, today_only=True)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📆 تقویم این هفته", callback_data="cal_week")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])

    if not filtered:
        await query.message.reply_text(
            "✅ امروز هیچ خبر مهمی (🔴) برای ارزهای اصلی وجود ندارد.",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    text = "📅 اخبار مهم امروز\n" + "━" * 30 + "\n\n"
    for e in filtered:
        text += format_event(e) + "\n"

    # تلگرام حداکثر ۴۰۹۶ کاراکتر قبول می‌کند
    if len(text) > 4000:
        text = text[:4000] + "\n..."

    await query.message.reply_text(text, reply_markup=keyboard)
    return MAIN_MENU


async def calendar_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("⏳ در حال دریافت تقویم هفته ...")

    events = await fetch_ff_calendar("thisweek")
    if events is None:
        await query.message.reply_text("⚠️ دریافت تقویم موفق نبود. لطفاً بعداً امتحان کن.")
        return MAIN_MENU

    filtered = filter_events(events, today_only=False)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 تقویم امروز", callback_data="cal_today")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])

    if not filtered:
        await query.message.reply_text(
            "✅ این هفته هیچ خبر مهمی (🔴) برای ارزهای اصلی وجود ندارد.",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    # تقسیم به پیام‌های چندتایی اگه زیاد بود
    chunks = []
    current = "📆 اخبار مهم این هفته\n" + "━" * 30 + "\n\n"
    for e in filtered:
        block = format_event(e) + "\n"
        if len(current) + len(block) > 4000:
            chunks.append(current)
            current = block
        else:
            current += block
    chunks.append(current)

    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await query.message.reply_text(chunk, reply_markup=keyboard)
        else:
            await query.message.reply_text(chunk)

    return MAIN_MENU


# ===== حباب صندوق‌ها از فاندبیس =====
async def fetch_bubble_data(fund_type: str) -> list | None:
    """
    fund_type: 'gold' یا 'silver'
    طلا: از صفحه HTML فاندبیس fundbase.ir/h (جدول استاتیک)
    نقره: از API داخلی فاندبیس (چون صفحه HTML مجزا ندارد)
    """
    import aiohttp
    from html.parser import HTMLParser

    if fund_type == "gold":
        return await _fetch_gold_bubble()
    else:
        return await _fetch_silver_bubble()


async def _fetch_gold_bubble() -> list | None:
    """حباب طلا از صفحه HTML فاندبیس"""
    import aiohttp
    from html.parser import HTMLParser

    class TableParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_table = False
            self.in_row = False
            self.in_cell = False
            self.rows = []
            self.current_row = []
            self.current_cell = ""
            self.depth = 0

        def handle_starttag(self, tag, attrs):
            if tag == "table":
                self.in_table = True
                self.depth += 1
            elif tag == "tr" and self.in_table:
                self.in_row = True
                self.current_row = []
            elif tag in ("td", "th") and self.in_row:
                self.in_cell = True
                self.current_cell = ""

        def handle_endtag(self, tag):
            if tag == "table":
                self.depth -= 1
                if self.depth == 0:
                    self.in_table = False
            elif tag == "tr" and self.in_row:
                if self.current_row:
                    self.rows.append(self.current_row[:])
                self.in_row = False
            elif tag in ("td", "th") and self.in_cell:
                self.current_row.append(self.current_cell.strip())
                self.in_cell = False

        def handle_data(self, data):
            if self.in_cell:
                self.current_cell += data

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "fa-IR,fa;q=0.9",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://fundbase.ir/h",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.error(f"fundbase gold status: {resp.status}")
                    return None
                html = await resp.text(encoding="utf-8", errors="ignore")

        parser = TableParser()
        parser.feed(html)

        funds = []
        for row in parser.rows:
            if len(row) >= 4:
                name = row[0].strip()
                if name in ("نماد", "صندوق", ""):
                    continue
                funds.append({
                    "name": name,
                    "price": row[1].strip() if len(row) > 1 else "—",
                    "bubble_price": row[2].strip() if len(row) > 2 else "—",
                    "bubble_intrinsic": row[3].strip() if len(row) > 3 else "—",
                    "bubble_total": row[4].strip() if len(row) > 4 else "—",
                })
        return funds if funds else None

    except Exception as e:
        logger.error(f"خطا در scraping طلا: {e}")
        return None


async def _fetch_silver_bubble() -> list | None:
    """
    حباب نقره از TradersArena
    فرمت: آرایه‌ای از آرایه‌ها
    index 1 = نام فارسی، index 15 = حباب کل
    """
    import aiohttp
    import time

    url = f"https://tradersarena.ir/data/industries-stocks-csv/silver-funds?_={int(time.time()*1000)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://tradersarena.ir/industries/silver-funds",
        "Accept": "application/json, text/javascript, */*",
        "Accept-Language": "fa-IR,fa;q=0.9",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                logger.info(f"silver tradersarena status: {resp.status}")
                if resp.status != 200:
                    logger.error(f"silver error: {await resp.text()}")
                    return None
                rows = await resp.json(content_type=None)

        logger.info(f"silver rows count: {len(rows) if rows else 0}")

        funds = []
        seen = set()
        for row in rows:
            if not isinstance(row, list) or len(row) < 16:
                continue
            name = str(row[1]) if row[1] else ""
            if not name or name in seen:
                continue
            seen.add(name)
            try:
                bubble = float(row[15]) if row[15] is not None else None
                if bubble is None:
                    continue
            except Exception:
                continue
            funds.append({
                "name": name,
                "price": str(row[8]) if len(row) > 8 else "—",
                "bubble_price": str(row[5]) if len(row) > 5 else "—",
                "bubble_intrinsic": str(row[14]) if len(row) > 14 else "—",
                "bubble_total": str(bubble),
            })

        logger.info(f"silver funds parsed: {len(funds)}")
        return funds if funds else None

    except Exception as e:
        logger.error(f"خطا در fetch نقره: {e}")
        return None



def bubble_icon(val: str) -> str:
    """آیکون مثبت/منفی/صفر بر اساس مقدار حباب"""
    clean = val.replace("٪", "").replace("%", "").replace("‎", "").replace("+", "").replace("−", "-").strip()
    try:
        num = float(clean)
        if num > 1:
            return "🔴"
        elif num > 0:
            return "🟡"
        elif num < 0:
            return "🟢"
        else:
            return "⚪"
    except Exception:
        return ""


async def bubble_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 حباب صندوق‌های طلا", callback_data="bubble_gold")],
        [InlineKeyboardButton("🪙 حباب صندوق‌های نقره", callback_data="bubble_silver")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        "🫧 حباب صندوق‌های سرمایه‌گذاری\n\nکدام دسته را می‌خواهی؟",
        reply_markup=keyboard,
    )
    return MAIN_MENU


def _prepare_persian_font():
    """
    فونت IranSans را آماده می‌کند.
    اگر فونت از قبل دانلود شده باشد، دوباره دانلود نمی‌کند.
    """
    import urllib.request, zipfile
    font_path = "/tmp/IranSans-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            zip_path = "/tmp/iran-sans.zip"
            urllib.request.urlretrieve(
                "https://github.com/rastikerdar/iran-sans/releases/download/v5.0.3/iran-sans.zip",
                zip_path
            )
            with zipfile.ZipFile(zip_path) as z:
                for name in z.namelist():
                    if "Regular" in name and name.endswith(".ttf") and "Condensed" not in name:
                        with z.open(name) as src, open(font_path, "wb") as dst:
                            dst.write(src.read())
                        break
            logger.info("فونت IranSans با موفقیت دانلود شد.")
        except Exception as e:
            logger.error(f"خطا در دانلود فونت IranSans: {e}")
            return None
    return font_path


def _reshape_persian(text: str) -> str:
    """متن فارسی را برای نمایش صحیح در matplotlib آماده می‌کند."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        logger.warning(f"خطا در reshape متن فارسی: {e}")
        return text


_LAST_GOOD_BUBBLE = {}


async def bubble_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import io

    query = update.callback_query
    await query.answer()
    fund_type = "gold" if query.data == "bubble_gold" else "silver"
    label = "طلا 🥇" if fund_type == "gold" else "نقره 🪙"
    title_fa = "حباب صندوق‌های طلا" if fund_type == "gold" else "حباب صندوق‌های نقره"

    await query.message.reply_text("⏳ در حال دریافت داده ...")

    funds = await fetch_bubble_data(fund_type)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی", callback_data=query.data)],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="bubble_menu")],
    ])

    if not funds:
        await query.message.reply_text(
            "⚠️ دریافت داده موفق نبود. لطفاً دقایقی دیگر امتحان کن.",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    names = []
    values = []
    for f in funds:
        raw = (
            f["bubble_total"]
            .replace("٪", "").replace("%", "")
            .replace("+", "").replace("−", "-")
            .replace("\u200e", "").strip()
        )
        try:
            val = float(raw)
            names.append(f["name"])
            values.append(val)
        except Exception:
            continue

    if not names:
        await query.message.reply_text("⚠️ داده‌های عددی قابل نمایش نبودند.", reply_markup=keyboard)
        return MAIN_MENU

    stale_note = ""
    is_all_zero = all(v == 0 for v in values)
    if is_all_zero and fund_type in _LAST_GOOD_BUBBLE:
        cached = _LAST_GOOD_BUBBLE[fund_type]
        names, values = cached["names"], cached["values"]
        stale_note = f"\n\n⏳ بازار بسته است؛ آخرین قیمت‌های معتبر (ساعت {cached['time_str']}) نمایش داده شده."
    elif not is_all_zero:
        from datetime import datetime, timezone, timedelta
        now_tehran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
        _LAST_GOOD_BUBBLE[fund_type] = {
            "names": list(names),
            "values": list(values),
            "time_str": now_tehran.strftime("%H:%M"),
        }
    elif is_all_zero:
        stale_note = "\n\n⏳ بازار بسته است."

    # مرتب نزولی
    paired = sorted(zip(values, names), reverse=True)
    values = [v for v, _ in paired]
    names_raw = [n for _, n in paired]

    colors = []
    for v in values:
        if v > 1:
            colors.append("#e53935")
        elif v > 0:
            colors.append("#FFA726")
        elif v < 0:
            colors.append("#43A047")
        else:
            colors.append("#90A4AE")

    # آماده‌سازی فونت فارسی
    font_path = _prepare_persian_font()
    if font_path:
        font_manager.fontManager.addfont(font_path)
        persian_font = font_manager.FontProperties(fname=font_path)
        fa_prop = {"fontproperties": persian_font}
    else:
        persian_font = None
        fa_prop = {}

    # reshape اسامی فارسی
    names_label = [_reshape_persian(n) for n in names_raw]
    title_display = _reshape_persian(title_fa)

    fig, ax = plt.subplots(figsize=(max(10, len(names_label) * 0.85), 5.5))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    bars = ax.bar(range(len(names_label)), values, color=colors, width=0.6, zorder=3)
    ax.axhline(0, color="#888", linewidth=1, linestyle="--", zorder=2)
    ax.set_xticks(range(len(names_label)))

    # اعمال فونت فارسی روی tick labels
    ax.set_xticklabels(names_label, fontsize=9, rotation=35, ha="right", **fa_prop)

    for bar, val in zip(bars, values):
        sign = "+" if val >= 0 else ""
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + (0.04 if val >= 0 else -0.14),
            f"{sign}{val:.1f}%",
            ha="center", va="bottom" if val >= 0 else "top",
            fontsize=8, fontweight="bold", color="#333"
        )

    # عنوان فارسی
    title_kwargs = {"fontsize": 13, "fontweight": "bold", "color": "#1a1a2e", "pad": 12}
    if persian_font:
        title_kwargs["fontproperties"] = persian_font
    ax.set_title(title_display, **title_kwargs)

    ax.set_ylabel("Bubble Total (%)", fontsize=10, color="#444")
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()

    # متن گوشه بالا راست
    wm_kw = dict(ha="right", va="top", fontsize=9, color="#C8922A", alpha=1.0, fontweight="bold")
    if persian_font:
        wm_kw["fontproperties"] = persian_font
    fig.text(0.99, 0.99, _reshape_persian("تهیه شده در گروه تحلیلی مانی مپ"), **wm_kw)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    asset_word = "طلا" if fund_type == "gold" else "نقره"
    bubble_explainer = (
        "💡 حباب یعنی چی؟\n"
        f"وقتی قیمتی که یه صندوق {asset_word} توی بازار بورس معامله می‌شه، با ارزش واقعی {asset_word}ی که پشتشه یکی نباشه، "
        "به این اختلاف «حباب» می‌گن. اگه حباب مثبت باشه یعنی صندوق گرون‌تر از ارزش واقعی داراییش معامله می‌شه؛ "
        "اگه منفی باشه یعنی ارزون‌تر معامله می‌شه."
    )
    await query.message.reply_photo(
        photo=buf,
        caption=f"🫧 حباب صندوق‌های {label}\n\n{bubble_explainer}{stale_note}",
        reply_markup=keyboard,
    )
    return MAIN_MENU

# ===== بخش VIP =====

async def fetch_usdt_price() -> float | None:
    """دریافت قیمت لحظه‌ای تتر (تومان) — اول از تی‌جی‌جی‌یو (نماد تتر)، اگه نشد از API عمومی والکس"""
    price_rial = await fetch_tgju_price("crypto-tether-irr")
    if price_rial:
        return price_rial / 10  # تبدیل ریال به تومان

    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.wallex.ir/v1/markets",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    symbols = data.get("result", {}).get("symbols", {})
                    usdt = symbols.get("USDTTMN")
                    if usdt:
                        last_price = usdt.get("stats", {}).get("lastPrice")
                        if last_price:
                            return float(last_price)
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت لحظه‌ای تتر از والکس: {e}")
    return None


async def vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    import time
    vip_expire = db.get_vip_expiry(user_id)
    if vip_expire and vip_expire > time.time():
        import datetime
        remaining_secs = vip_expire - time.time()
        remaining_days = int(remaining_secs / 86400)
        remaining_hours = int((remaining_secs % 86400) / 3600)
        expire_dt = datetime.datetime.fromtimestamp(vip_expire)
        expire_str = expire_dt.strftime("%Y/%m/%d ساعت %H:%M")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 ورود به کانال VIP", url=VIP_CHANNEL_LINK)],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
        ])
        await query.message.reply_text(
            f"✅ شما عضو فعال VIP هستید!\n\n"
            f"⏳ زمان باقی‌مانده: {remaining_days} روز و {remaining_hours} ساعت\n"
            f"📅 تاریخ انقضا: {expire_str}\n\n"
            f"از دکمه زیر وارد کانال شوید:",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    # بررسی ظرفیت کانال VIP
    if not db.is_vip_channel_open():
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
        ])
        await query.message.reply_text(
            "🔒 متأسفانه در حال حاضر ظرفیت کانال VIP تکمیل شده است.\n\n"
            "عضوگیری جدید موقتاً متوقف شده. بعداً دوباره تلاش کن! 🙏",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    # کاربر هنوز VIP فعال نداره — دو راه پیش روشه: پرداخت یا دعوت دوستان
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 پرداخت هزینه اشتراک", callback_data="vip_pay_info")],
        [InlineKeyboardButton("👥 دعوت دوستان (رایگان شو!)", callback_data="referral_menu")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    msg = (
        "💎 اشتراک VIP سیگنال\n\n"
        "برای دریافت عضویت کانال سیگنال یکی از دو راه زیر رو انتخاب کن:\n\n"
        "💳 یا هزینه اشتراک رو پرداخت کن،\n"
        "👥 یا با معرفی تعداد مشخصی از دوستات (که عضو کانال هم بشن)، عضویت رو رایگان دریافت کن!"
    )
    await query.message.reply_text(msg, reply_markup=keyboard)
    return MAIN_MENU


async def vip_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش قیمت اشتراک و اطلاعات پرداخت (شماره کارت)."""
    query = update.callback_query
    await query.answer()

    # بررسی ظرفیت کانال VIP
    if not db.is_vip_channel_open():
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
        ])
        await query.message.reply_text(
            "🔒 متأسفانه در حال حاضر ظرفیت کانال VIP تکمیل شده است.\n\n"
            "عضوگیری جدید موقتاً متوقف شده. بعداً دوباره تلاش کن! 🙏",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    vip_price_usdt = _vip_price_usdt()
    usdt_price = await fetch_usdt_price()
    if usdt_price:
        usdt_toman = usdt_price  # قبلاً تبدیل ریال→تومان در fetch انجام شده
        total_toman = int(vip_price_usdt * usdt_toman)
        price_text = f"💰 قیمت اشتراک: {vip_price_usdt:g} تتر\n💵 قیمت هر تتر: {usdt_toman:,.0f} تومان\n💳 مبلغ قابل پرداخت: {total_toman:,.0f} تومان"
    else:
        price_text = f"💰 قیمت اشتراک: {vip_price_usdt:g} تتر\n⚠️ برای اطلاع از معادل تومانی، قیمت روز تتر را در {vip_price_usdt:g} ضرب کنید"
    # ذخیره مبلغ برای نمایش در پیام ادمین
    context.user_data["vip_price_text"] = price_text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 پرداخت کردم — ارسال رسید", callback_data="vip_pay")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    msg = (
        "💎 اشتراک VIP سیگنال — یک ماهه\n"
        + "─" * 32 + "\n"
        + price_text + "\n\n"
        "🏦 شماره کارت:\n"
        "`" + VIP_CARD_NUMBER + "`\n"
        "👤 به نام: " + VIP_CARD_OWNER + "\n\n"
        "پس از واریز، روی دکمه زیر بزن و رسید را ارسال کن 👇"
    )
    await query.message.reply_text(msg, reply_markup=keyboard, parse_mode="Markdown")
    return MAIN_MENU


async def vip_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_vip_receipt"] = True
    await query.message.reply_text(
        "📸 لطفاً تصویر رسید پرداخت را ارسال کن:\n\n_(بعد از بررسی، لینک کانال VIP برایت ارسال می‌شود)_",
        parse_mode="Markdown",
    )
    return MAIN_MENU


async def handle_non_photo_while_waiting_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع آخرین هندلر فعال (fallback) برای پیام‌های متنی/فایلی خصوصی است.
    دو حالت را پوشش می‌دهد:
    ۱) کاربر منتظر ارسال رسید VIP بوده ولی به‌جای عکس چیز دیگری فرستاده.
    ۲) هیچ هندلر دیگری این پیام را نگرفته (مثلاً به‌خاطر گم‌شدن وضعیت گفتگو بعد از ریستارت سرور،
       یا پیام کاملاً نامربوط) — به‌جای سکوت کامل، باید راهنمایی شود.
    """
    if context.user_data.get("waiting_support_message"):
        context.user_data["waiting_support_message"] = False
        user_id = update.effective_user.id
        user = update.effective_user
        user_row = db.get_user(user_id)
        name = user_row.get("name", user.full_name or "نامشخص") if user_row else (user.full_name or "نامشخص")
        phone = user_row.get("phone", "—") if user_row else "—"
        username = user.username or "ندارد"
        sent = await context.bot.send_message(
            chat_id=SUPPORT_GROUP_ID,
            text=(
                "📞 پیام پشتیبانی جدید\n\n"
                f"👤 اسم: {name}\n"
                f"📱 شماره: {phone}\n"
                f"🔗 یوزرنیم: @{username}\n"
                f"🆔 آیدی: {user_id}\n\n"
                f"✉️ پیام:\n{update.message.text}"
            ),
        )
        context.bot_data.setdefault("support_map", {})[sent.message_id] = user_id
        await update.message.reply_text("✅ پیامت برای پشتیبانی ارسال شد. به‌زودی جواب می‌گیری.")
        return

    if context.user_data.get("waiting_vip_receipt"):
        await update.message.reply_text(
            "📸 لطفاً رسید پرداخت را فقط به صورت «عکس» ارسال کن (نه فایل و نه متن)."
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="menu")],
    ])
    await update.message.reply_text(
        "🤔 متوجه این پیام نشدم.\n\n"
        "اگه وسط یه مرحله گیر کردی (مثلاً محاسبه‌گر طلا)، می‌تونی دوباره از اول شروع کنی: دستور /start رو بزن.\n"
        "یا از دکمه‌ی زیر برای رفتن به منوی اصلی استفاده کن 👇",
        reply_markup=keyboard,
    )


async def support_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """وقتی ادمین توی گروه پشتیبانی روی پیام یه کاربر Reply می‌زنه، جوابش برای همون کاربر ارسال می‌شه"""
    msg = update.message
    if not msg or not msg.reply_to_message or not msg.text:
        return
    support_map = context.bot_data.get("support_map", {})
    target_user_id = support_map.get(msg.reply_to_message.message_id)
    if not target_user_id:
        return
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📞 پاسخ پشتیبانی:\n{msg.text}",
        )
        await msg.reply_text("✅ ارسال شد.")
    except Exception as e:
        await msg.reply_text(f"⚠️ خطا در ارسال پاسخ: {e}")


async def check_vip_expirations(context: ContextTypes.DEFAULT_TYPE):
    """جاب دوره‌ای: یادآوری ۷ روز/۳ روز/روز آخر مونده به اتمام اشتراک،
    و حذف خودکار + پیشنهاد تمدید برای کسانی که اشتراکشان واقعاً تمام شده."""
    import time as _time
    now = _time.time()
    for member in db.get_all_vip():
        user_id = member["user_id"]
        expire_at = member["expire_at"]
        if not expire_at:
            continue
        remaining_days = (expire_at - now) / 86400
        try:
            if remaining_days <= 0:
                # اشتراک واقعاً تمام شده: حذف از کانال VIP + دیتابیس + پیشنهاد تمدید
                db.remove_vip(user_id)
                try:
                    await context.bot.ban_chat_member(chat_id=VIP_CHANNEL_ID, user_id=user_id)
                    await context.bot.unban_chat_member(chat_id=VIP_CHANNEL_ID, user_id=user_id)
                except Exception as e:
                    logger.warning(f"خطا در حذف کاربر {user_id} از کانال VIP: {e}")
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💎 تمدید اشتراک VIP", callback_data="vip_pay")]])
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⛔ اشتراک VIP شما به پایان رسید و از کانال VIP خارج شدید.\n\n"
                         "اگه می‌خوای دوباره عضو کانال VIP باشی، روی دکمه زیر بزن و اشتراکت رو تمدید کن 👇",
                    reply_markup=keyboard,
                )
            elif remaining_days <= 1 and not member.get("reminder_0"):
                db.mark_vip_reminder_sent(user_id, "reminder_0")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ یادآوری: امروز آخرین روز اشتراک VIP شماست!\n"
                         f"📅 تاریخ پایان: {_format_vip_date(expire_at)}\n\n"
                         "اگه تمدید نکنی، فردا از کانال VIP حذف می‌شی.",
                )
            elif remaining_days <= 3 and not member.get("reminder_3"):
                db.mark_vip_reminder_sent(user_id, "reminder_3")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ یادآوری: ۳ روز دیگر اشتراک VIP شما تمام می‌شود.\n"
                         f"📅 تاریخ پایان: {_format_vip_date(expire_at)}",
                )
            elif remaining_days <= 7 and not member.get("reminder_7"):
                db.mark_vip_reminder_sent(user_id, "reminder_7")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ یادآوری: یک هفته دیگر اشتراک VIP شما تمام می‌شود.\n"
                         f"📅 تاریخ پایان: {_format_vip_date(expire_at)}",
                )
        except Exception as e:
            logger.error(f"خطا در پردازش یادآوری VIP برای کاربر {user_id}: {e}")


async def approve_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import time
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    text = update.message.text
    try:
        target_id = int(text.split("_")[1])
    except Exception:
        await update.message.reply_text("فرمت اشتباه. مثال: /approve_123456789")
        return
    new_expire = db.add_vip_days(target_id, _vip_days())
    try:
        invite = await context.bot.create_chat_invite_link(chat_id=VIP_CHANNEL_ID, member_limit=1, name=f"VIP-{target_id}")
        link = invite.invite_link
    except Exception as e:
        logger.error(f"خطا در ساخت لینک: {e}")
        link = VIP_CHANNEL_LINK
    try:
        expire_str = _format_vip_date(new_expire)
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 اشتراک VIP شما فعال/تمدید شد!\n\n🔗 لینک ورود به کانال (یکبار مصرف):\n{link}\n\n⏳ اشتراک شما تا تاریخ {expire_str} معتبر است.",
        )
        await update.message.reply_text(f"✅ کاربر {target_id} تأیید شد و لینک ارسال گردید.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا در ارسال پیام: {e}")


async def reject_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    text = update.message.text
    try:
        target_id = int(text.split("_")[1])
    except Exception:
        await update.message.reply_text("فرمت اشتباه.")
        return
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ متأسفانه رسید پرداخت شما تأیید نشد.\nدر صورت سوال با ادمین در تماس باشید.",
        )
        await update.message.reply_text(f"✅ کاربر {target_id} رد شد.")
    except Exception as e:
        await update.message.reply_text(f"⚠️ خطا: {e}")


async def handle_vip_receipt_global(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت رسید VIP از کاربر — بدون نیاز به state"""
    user_id = update.effective_user.id
    user = update.effective_user
    # فقط اگه کاربر قبلاً روی دکمه پرداخت زده باشه
    if not context.user_data.get("waiting_vip_receipt"):
        return
    context.user_data["waiting_vip_receipt"] = False
    user_row = db.get_user(user_id)
    name = user_row.get("name", user.full_name or "نامشخص") if user_row else (user.full_name or "نامشخص")
    phone = user_row.get("phone", "—") if user_row else "—"
    username = user.username or "ندارد"
    price_info = context.user_data.get("vip_price_text", f"💰 {_vip_price_usdt():g} تتر")
    caption = (
        "💎 درخواست اشتراک VIP\n\n"
        f"👤 اسم: {name}\n"
        f"📱 شماره: {phone}\n"
        f"🔗 یوزرنیم: @{username}\n"
        f"🆔 آیدی: {user_id}\n\n"
        f"💳 مبلغ نمایش داده شده:\n{price_info}"
    )
    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأیید و ارسال لینک", callback_data=f"vip_approve_{user_id}"),
            InlineKeyboardButton("❌ رد درخواست", callback_data=f"vip_reject_{user_id}"),
        ]
    ])
    await context.bot.send_photo(
        chat_id=ADMIN_GROUP_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption,
        reply_markup=admin_keyboard,
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")]])
    await update.message.reply_text(
        "✅ رسید شما دریافت شد!\nپس از بررسی (حداکثر ۷ ساعت) لینک کانال برایت ارسال می‌شود.",
        reply_markup=keyboard,
    )


async def vip_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تأیید VIP با دکمه inline در گروه ادمین"""
    import time
    query = update.callback_query
    if update.effective_chat.id != ADMIN_GROUP_ID:
        await query.answer()
        return
    if query.message.caption and ("✅ تأیید شد" in query.message.caption or "❌ رد شد" in query.message.caption):
        await query.answer("این رسید قبلاً پردازش شده — برای جلوگیری از ساخت لینک تکراری، دوباره پردازش نمی‌شود.", show_alert=True)
        return
    await query.answer()
    target_id = int(query.data.split("_")[2])
    new_expire = db.add_vip_days(target_id, _vip_days())
    try:
        invite = await context.bot.create_chat_invite_link(
            chat_id=VIP_CHANNEL_ID, member_limit=1, name=f"VIP-{target_id}"
        )
        link = invite.invite_link
    except Exception as e:
        logger.error(f"خطا در ساخت لینک: {e}")
        link = VIP_CHANNEL_LINK
    try:
        expire_str = _format_vip_date(new_expire)
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🎉 اشتراک VIP شما فعال/تمدید شد!\n\n"
                 f"🔗 لینک ورود به کانال (یکبار مصرف):\n{link}\n\n"
                 f"⏳ اشتراک شما تا تاریخ {expire_str} معتبر است.",
        )
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n✅ تأیید شد — لینک ارسال گردید.",
            reply_markup=None,
        )
    except Exception as e:
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n⚠️ خطا: {e}",
            reply_markup=None,
        )


async def vip_reject_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد VIP با دکمه inline در گروه ادمین"""
    query = update.callback_query
    if update.effective_chat.id != ADMIN_GROUP_ID:
        await query.answer()
        return
    if query.message.caption and ("✅ تأیید شد" in query.message.caption or "❌ رد شد" in query.message.caption):
        await query.answer("این رسید قبلاً پردازش شده.", show_alert=True)
        return
    await query.answer()
    target_id = int(query.data.split("_")[2])
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ متأسفانه رسید پرداخت شما تأیید نشد.\nدر صورت سوال با ادمین در تماس باشید.",
        )
        await query.edit_message_caption(
            caption=query.message.caption + "\n\n❌ رد شد.",
            reply_markup=None,
        )
    except Exception as e:
        await query.edit_message_caption(
            caption=query.message.caption + f"\n\n⚠️ خطا: {e}",
            reply_markup=None,
        )


async def whereami_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🆔 آیدی همین چت/گروه: {update.effective_chat.id}")


# ===================================================================
# 🔔 هشدار قیمت — Price Alert System
# ===================================================================

async def alert_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    active_count = db.count_active_alerts(user_id)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ هشدار جدید", callback_data="alert_new")],
        [InlineKeyboardButton(f"📋 هشدارهای من ({active_count}/10)", callback_data="alert_list")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        "🔔 هشدار قیمت\n\n"
        "می‌تونی روی هر دارایی یه قیمت هدف تعیین کنی.\n"
        "به محض رسیدن قیمت به اون هدف، بات بهت پیام می‌ده.\n\n"
        f"هشدارهای فعال: {active_count}/10",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def alert_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if db.count_active_alerts(user_id) >= 10:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 مدیریت هشدارها", callback_data="alert_list")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="alert_menu")],
        ])
        await query.message.reply_text(
            "⚠️ حداکثر ۱۰ هشدار فعال می‌تونی داشته باشی.\n"
            "اول یه هشدار قدیمی رو حذف کن، بعد هشدار جدید بذار.",
            reply_markup=keyboard,
        )
        return MAIN_MENU
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 طلای ۱۸ عیار", callback_data="alert_asset_gold")],
        [InlineKeyboardButton("💵 دلار آمریکا", callback_data="alert_asset_dollar")],
        [InlineKeyboardButton("₿ بیتکوین", callback_data="alert_asset_bitcoin")],

        [InlineKeyboardButton("Ξ اتریوم", callback_data="alert_asset_ethereum")],
        [InlineKeyboardButton("🌐 اونس جهانی طلا", callback_data="alert_asset_gold_ounce")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="alert_menu")],
    ])
    await query.message.reply_text(
        "روی کدوم دارایی می‌خوای هشدار قیمت بذاری؟",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def fetch_crypto_usd_price(irr_symbol: str) -> float | None:
    """قیمت کریپتو به دلار = قیمت ریالی ÷ نرخ دلار ریالی"""
    raw_crypto = await fetch_tgju_price(irr_symbol)
    raw_tether = await fetch_tgju_price("crypto-tether-irr")
    if not raw_crypto or not raw_tether:
        return None
    return raw_crypto / raw_tether


async def alert_asset_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    asset = query.data.replace("alert_asset_", "")
    info = ALERT_ASSET_INFO[asset]
    context.user_data["alert_asset"] = asset
    loading_msg = await query.message.reply_text("⏳ در حال دریافت قیمت، لطفاً صبر کن...")
    if asset in ("bitcoin", "ethereum"):
        current_price = await fetch_crypto_usd_price(info["symbol"])
    else:
        price_raw = await fetch_tgju_price(info["symbol"])
        current_price = price_raw / info["divisor"] if price_raw else None
    if current_price:
        context.user_data["alert_current_price"] = current_price
        price_text = f"قیمت فعلی: {current_price:,.0f} {info['unit']}"
    else:
        context.user_data["alert_current_price"] = None
        price_text = "قیمت فعلی: در دسترس نیست"
    cancel_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ لغو", callback_data="alert_cancel")],
    ])
    await loading_msg.delete()
    await query.message.reply_text(
        f"🔔 هشدار برای {info['emoji']} {info['label']}\n\n"
        f"{price_text}\n\n"
        f"قیمت هدف رو به {info['unit']} وارد کن:\n"
        f"(فقط عدد بنویس — مثال: 5000000)",
        reply_markup=cancel_kb,
    )
    return ALERT_ENTER_PRICE


async def alert_get_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "").replace("،", "").replace(" ", "")
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    for i, d in enumerate(persian_digits):
        text = text.replace(d, str(i))
    try:
        target_price = float(text)
        if target_price <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ عدد معتبر نیست.\nقیمت هدف رو فقط به صورت عددی وارد کن (مثال: 5000000):"
        )
        return ALERT_ENTER_PRICE
    context.user_data["alert_price"] = target_price
    asset = context.user_data.get("alert_asset", "")
    info = ALERT_ASSET_INFO.get(asset, {})
    current = context.user_data.get("alert_current_price")
    if current and current > 0:
        if target_price > current:
            direction = "above"
            dir_text = f"وقتی قیمت بره بالای {target_price:,.0f} {info.get('unit', '')}"
        else:
            direction = "below"
            dir_text = f"وقتی قیمت بیاد پایین‌تر از {target_price:,.0f} {info.get('unit', '')}"
        # بررسی تلورانس ۲۰٪
        diff_pct = abs(target_price - current) / current * 100
        if diff_pct > 20:
            context.user_data["alert_direction"] = direction
            warn_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ بله، مطمئنم", callback_data="alert_confirm_price")],
                [InlineKeyboardButton("❌ لغو", callback_data="alert_cancel")],
            ])
            await update.message.reply_text(
                f"⚠️ قیمتی که زدی {diff_pct:.0f}٪ با قیمت فعلی فاصله داره!\n\n"
                f"📊 قیمت فعلی: {current:,.0f} {info.get('unit', '')}\n"
                f"🎯 قیمت هدف: {target_price:,.0f} {info.get('unit', '')}\n\n"
                "مطمئنی این عدد درسته؟\n"
                "(یا یه قیمت دیگه تایپ کن)",
                reply_markup=warn_keyboard,
            )
            return ALERT_ENTER_PRICE
    else:
        direction = "above"
        dir_text = f"وقتی قیمت به {target_price:,.0f} {info.get('unit', '')} برسه"
    context.user_data["alert_direction"] = direction
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔕 بدون پیام اضافه", callback_data="alert_default_msg")],
        [InlineKeyboardButton("❌ لغو", callback_data="alert_cancel")],
    ])
    await update.message.reply_text(
        f"✅ قیمت هدف: {target_price:,.0f} {info.get('unit', '')}\n"
        f"📣 شرط: {dir_text}\n\n"
        "یه پیام برای هشدارت بنویس 👇\n"
        "مثلاً: موقع فروش یا بررسی بازار\n\n"
        "اگه پیام خاصی نمی‌خوای، دکمه زیر رو بزن:",
        reply_markup=keyboard,
    )
    return ALERT_ENTER_MESSAGE


async def alert_confirm_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر قیمت پرت را تایید کرد"""
    query = update.callback_query
    await query.answer()
    asset = context.user_data.get("alert_asset", "")
    info = ALERT_ASSET_INFO.get(asset, {})
    target_price = context.user_data.get("alert_price", 0)
    direction = context.user_data.get("alert_direction", "above")
    dir_text = (
        f"وقتی قیمت بره بالای {target_price:,.0f} {info.get('unit', '')}"
        if direction == "above"
        else f"وقتی قیمت بیاد پایین‌تر از {target_price:,.0f} {info.get('unit', '')}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔕 بدون پیام اضافه", callback_data="alert_default_msg")],
        [InlineKeyboardButton("❌ لغو", callback_data="alert_cancel")],
    ])
    await query.message.reply_text(
        f"✅ قیمت هدف تایید شد: {target_price:,.0f} {info.get('unit', '')}\n"
        f"📣 شرط: {dir_text}\n\n"
        "یه پیام برای هشدارت بنویس 👇\n"
        "مثلاً: موقع فروش یا بررسی بازار\n\n"
        "اگه پیام خاصی نمی‌خوای، دکمه زیر رو بزن:",
        reply_markup=keyboard,
    )
    return ALERT_ENTER_MESSAGE


async def alert_default_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """کاربر بدون پیام اضافه انتخاب کرد"""
    query = update.callback_query
    await query.answer()
    await _save_price_alert(update, context, "", via_callback=True)
    return MAIN_MENU


async def alert_get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت متن دلخواه پیام هشدار از کاربر"""
    message_text = update.message.text.strip()
    if not message_text:
        await update.message.reply_text("متن پیام نمیتونه خالی باشه. دوباره بنویس:")
        return ALERT_ENTER_MESSAGE
    await _save_price_alert(update, context, message_text, via_callback=False)
    return MAIN_MENU


async def _save_price_alert(update, context, message_text: str, via_callback: bool):
    user_id = update.effective_user.id
    asset = context.user_data.get("alert_asset", "")
    target_price = context.user_data.get("alert_price", 0)
    direction = context.user_data.get("alert_direction", "above")
    info = ALERT_ASSET_INFO.get(asset, {})
    if db.count_active_alerts(user_id) >= 10:
        msg = "به حداکثر ۱۰ هشدار فعال رسیدی. اول یه هشدار قدیمی حذف کن."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("هشدارهای من", callback_data="alert_list")]])
        if via_callback:
            await update.callback_query.message.reply_text(msg, reply_markup=keyboard)
        else:
            await update.message.reply_text(msg, reply_markup=keyboard)
        return
    db.add_price_alert(user_id, asset, target_price, direction, message_text)
    dir_text = "بالاتر از" if direction == "above" else "پایین‌تر از"
    confirmation = (
        f"✅ هشدار با موفقیت ثبت شد!\n\n"
        f"📊 دارایی: {info.get('emoji', '')} {info.get('label', '')}\n"
        f"🎯 قیمت هدف: {target_price:,.0f} {info.get('unit', '')}\n"
        f"📣 شرط: {dir_text} قیمت هدف\n"
        f"💬 پیام: {'(بدون پیام)' if not message_text else message_text[:80]}"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔔 هشدارهای من", callback_data="alert_list")],
        [InlineKeyboardButton("🔙 منوی اصلی", callback_data="menu")],
    ])
    if via_callback:
        await update.callback_query.message.reply_text(confirmation, reply_markup=keyboard)
    else:
        await update.message.reply_text(confirmation, reply_markup=keyboard)
    for key in ("alert_asset", "alert_price", "alert_direction", "alert_current_price"):
        context.user_data.pop(key, None)


async def alert_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    alerts = db.get_active_alerts_for_user(user_id)
    keyboard_buttons = []
    if not alerts:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ هشدار جدید", callback_data="alert_new")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="alert_menu")],
        ])
        await query.message.reply_text(
            "هیچ هشدار فعالی نداری.\nمی‌تونی یه هشدار جدید بسازی 👇",
            reply_markup=keyboard,
        )
        return MAIN_MENU
    text = f"🔔 هشدارهای فعال شما ({len(alerts)}/10):\n\n"
    for i, a in enumerate(alerts, 1):
        info = ALERT_ASSET_INFO.get(a["asset"], {})
        dir_text = "⬆️ بالاتر از" if a["direction"] == "above" else "⬇️ پایین‌تر از"
        short_msg = a["message"][:50] + ("..." if len(a["message"]) > 50 else "")
        text += (
            f"{i}. {info.get('emoji', '')} {info.get('label', '')}\n"
            f"   🎯 {dir_text} {a['target_price']:,.0f} {info.get('unit', '')}\n"
            f"   💬 {short_msg}\n\n"
        )
        keyboard_buttons.append(
            [InlineKeyboardButton(f"🗑 حذف هشدار {i}", callback_data=f"alert_del_{a['id']}")]
        )
    keyboard_buttons.append([InlineKeyboardButton("➕ هشدار جدید", callback_data="alert_new")])
    keyboard_buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="alert_menu")])
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    return MAIN_MENU


async def alert_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    alert_id = int(query.data.split("_")[2])
    db.delete_price_alert(alert_id, user_id)
    alerts = db.get_active_alerts_for_user(user_id)
    keyboard_buttons = []
    if not alerts:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ هشدار جدید", callback_data="alert_new")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="alert_menu")],
        ])
        await query.message.reply_text("✅ هشدار حذف شد.\nهیچ هشدار فعال دیگه‌ای نداری.", reply_markup=keyboard)
        return MAIN_MENU
    text = f"✅ هشدار حذف شد.\n\n🔔 هشدارهای فعال ({len(alerts)}/10):\n\n"
    for i, a in enumerate(alerts, 1):
        info = ALERT_ASSET_INFO.get(a["asset"], {})
        dir_text = "⬆️ بالاتر از" if a["direction"] == "above" else "⬇️ پایین‌تر از"
        short_msg = a["message"][:50] + ("..." if len(a["message"]) > 50 else "")
        text += (
            f"{i}. {info.get('emoji', '')} {info.get('label', '')}\n"
            f"   🎯 {dir_text} {a['target_price']:,.0f} {info.get('unit', '')}\n"
            f"   💬 {short_msg}\n\n"
        )
        keyboard_buttons.append(
            [InlineKeyboardButton(f"🗑 حذف هشدار {i}", callback_data=f"alert_del_{a['id']}")]
        )
    keyboard_buttons.append([InlineKeyboardButton("➕ هشدار جدید", callback_data="alert_new")])
    keyboard_buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="alert_menu")])
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard_buttons))
    return MAIN_MENU


async def alert_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    for key in ("alert_asset", "alert_price", "alert_direction", "alert_current_price"):
        context.user_data.pop(key, None)
    await query.message.reply_text("❌ ساخت هشدار لغو شد.")
    await show_main_menu(update, context)
    return MAIN_MENU


async def check_price_alerts(context: ContextTypes.DEFAULT_TYPE):
    """جاب دوره‌ای: بررسی هشدارهای قیمت هر ۵ دقیقه"""
    alerts = db.get_all_active_alerts()
    if not alerts:
        return
    prices = {}
    for asset, info in ALERT_ASSET_INFO.items():
        if asset in ("bitcoin", "ethereum"):
            price = await fetch_crypto_usd_price(info["symbol"])
        else:
            raw = await fetch_tgju_price(info["symbol"])
            price = raw / info["divisor"] if raw else None
        if price:
            prices[asset] = price
    for alert in alerts:
        asset = alert["asset"]
        current_price = prices.get(asset)
        if current_price is None:
            continue
        target = alert["target_price"]
        direction = alert["direction"]
        triggered = (direction == "above" and current_price >= target) or \
                    (direction == "below" and current_price <= target)
        if triggered:
            db.mark_alert_triggered(alert["id"])
            info = ALERT_ASSET_INFO.get(asset, {})
            try:
                msg_extra = f"\n\n{alert['message']}" if alert['message'] else ""
                await context.bot.send_message(
                    chat_id=alert["user_id"],
                    text=(
                        f"🔔 هشدار قیمت!\n\n"
                        f"{info.get('emoji', '')} {info.get('label', '')}: "
                        f"{current_price:,.0f} {info.get('unit', '')}"
                        + msg_extra
                    ),
                )
            except Exception as e:
                logger.error(f"خطا در ارسال هشدار قیمت به کاربر {alert['user_id']}: {e}")


# ===== تحلیل روزانه AI =====

async def cmd_trigger_ai_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /ai — تریگر دستی تحلیل همین الان (فقط در گروه پشتیبانی)."""
    if update.effective_chat.id != SUPPORT_GROUP_ID:
        return
    await update.message.reply_text("🤖 در حال تولید تحلیل‌های AI...")
    await daily_ai_analysis_job(context)


async def daily_ai_analysis_job(context: ContextTypes.DEFAULT_TYPE):
    """جاب ساعت ۹ صبح — تولید و ارسال تحلیل AI به گروه ادمین."""
    import ai_analyst
    import pytz
    TEHRAN_TZ = pytz.timezone("Asia/Tehran")
    today = __import__("datetime").datetime.now(TEHRAN_TZ).strftime("%Y/%m/%d")

    if "ai_pending" not in context.bot_data:
        context.bot_data["ai_pending"] = {}
    if "ai_edit_waiting" not in context.bot_data:
        context.bot_data["ai_edit_waiting"] = {}

    for asset_key, asset in ai_analyst.ASSETS.items():
        try:
            await context.bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                text=f"⏳ در حال تولید تحلیل {asset['emoji']} {asset['fa_name']}..."
            )
        except Exception:
            pass

        try:
            text = await ai_analyst.generate_analysis(asset_key)
        except Exception as e:
            logger.error(f"AI analysis failed for {asset_key}: {e}")
            try:
                await context.bot.send_message(
                    chat_id=SUPPORT_GROUP_ID,
                    text=f"❌ خطا در تولید تحلیل {asset['fa_name']}:\n{e}"
                )
            except Exception:
                pass
            continue

        caption = (
            f"{asset['emoji']} تحلیل AI — {asset['fa_name']}\n"
            f"📅 {today}\n\n"
            f"{text}"
        )
        # تله‌گرام حداکثر ۴۰۹۶ کاراکتر — اگه طولانی‌تر شد، برش می‌زنیم
        if len(caption) > 4090:
            caption = caption[:4087] + "..."

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تایید", callback_data=f"ai_approve:{asset_key}"),
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"ai_edit:{asset_key}"),
        ]])

        try:
            msg = await context.bot.send_message(
                chat_id=SUPPORT_GROUP_ID,
                text=caption,
                reply_markup=keyboard,
            )
            context.bot_data["ai_pending"][f"{asset_key}:{msg.message_id}"] = {
                "asset": asset_key,
                "text": text,
                "date": today,
                "msg_id": msg.message_id,
            }
        except Exception as e:
            logger.error(f"Failed to send {asset_key} analysis to support group: {e}")

        await asyncio.sleep(3)


async def ai_approve_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تایید تحلیل AI و ذخیره در دیتابیس."""
    query = update.callback_query
    await query.answer()

    asset_key = query.data.split(":")[1]
    msg_id = query.message.message_id
    key = f"{asset_key}:{msg_id}"

    pending = context.bot_data.get("ai_pending", {})
    if key not in pending:
        await query.answer("⚠️ تحلیل یافت نشد یا قبلاً پردازش شده!", show_alert=True)
        return

    data = pending.pop(key)
    import ai_analyst
    asset_name = ai_analyst.ASSETS[asset_key]["fa_name"]

    db.set_analysis(asset_key, data["date"], data["text"])

    try:
        new_text = query.message.text + f"\n\n✅ تایید شد — {update.effective_user.first_name}"
        await query.message.edit_text(new_text)
    except Exception:
        await query.message.reply_text(f"✅ تحلیل {asset_name} تایید و در بات ذخیره شد!")


async def ai_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """درخواست ویرایش تحلیل AI — ورود به حالت ویرایش."""
    query = update.callback_query
    await query.answer()

    asset_key = query.data.split(":")[1]
    msg_id = query.message.message_id
    key = f"{asset_key}:{msg_id}"

    # متن اصلی رو از ai_pending یا از db بگیر
    pending = context.bot_data.get("ai_pending", {})
    if key in pending:
        original_text = pending[key]["text"]
    else:
        row = db.get_analysis(asset_key)
        if not row or not row.get("text"):
            await query.answer("⚠️ تحلیل یافت نشد!", show_alert=True)
            return
        original_text = row["text"]

    # ذخیره حالت ویرایش برای این گروه (بر اساس chat_id)
    context.bot_data.setdefault("ai_edit_mode", {})[query.message.chat_id] = {
        "asset_key": asset_key,
        "original_text": original_text,
        "analysis_msg_id": msg_id,
    }

    await query.message.reply_text(
        "✏️ دستور ویرایشت رو بنویس و ارسال کن 👇\n\n"
        "مثال: «کوتاهترش کن» / «تکنیکالی‌تر باشه» / «لحن رسمی‌تر باشه»"
    )


async def ai_edit_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت دستور ویرایش از ادمین — هر پیام متنی در گروه بعد از کلیک ✏️."""
    msg = update.message
    if not msg:
        return

    # چک کن آیا این گروه در حالت ویرایش است
    edit_modes = context.bot_data.get("ai_edit_mode", {})
    if msg.chat_id not in edit_modes:
        return

    edit_data = edit_modes.pop(msg.chat_id)
    asset_key = edit_data["asset_key"]
    original_text = edit_data["original_text"]
    original_msg_id = edit_data["analysis_msg_id"]
    # دریافت متن یا تبدیل ویس به متن
    if msg.voice:
        try:
            voice_file = await msg.voice.get_file()
            import io
            voice_bytes = await voice_file.download_as_bytearray()
            import ai_analyst as _ai
            edit_prompt = await _ai.transcribe_voice(bytes(voice_bytes), "voice.ogg")
            await msg.reply_text(f"🎤 دریافت شد: «{edit_prompt}»")
        except Exception as e:
            await msg.reply_text(f"❌ خطا در تبدیل ویس: {e}")
            return
    else:
        edit_prompt = msg.text or ""

    import pytz as _pytz, datetime as _dt
    _tehran = _pytz.timezone("Asia/Tehran")
    today = _dt.datetime.now(_tehran).strftime("%Y/%m/%d")

    thinking = await msg.reply_text("⏳ در حال ویرایش با AI...")

    try:
        import ai_analyst
        new_text = await ai_analyst.edit_analysis(original_text, edit_prompt, asset_key)

        # ai_pending رو آپدیت کن
        pending_key = f"{asset_key}:{original_msg_id}"
        context.bot_data.setdefault("ai_pending", {})[pending_key] = {"text": new_text, "date": today}

        asset = ai_analyst.ASSETS[asset_key]
        new_caption = (
            f"{asset['emoji']} تحلیل AI — {asset['fa_name']}\n"
            f"📅 {today}\n\n"
            f"{new_text}"
        )
        if len(new_caption) > 4090:
            new_caption = new_caption[:4087] + "..."

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ تایید", callback_data=f"ai_approve:{asset_key}"),
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"ai_edit:{asset_key}"),
        ]])

        try:
            await context.bot.edit_message_text(
                chat_id=msg.chat_id,
                message_id=original_msg_id,
                text=new_caption,
                reply_markup=keyboard,
            )
        except Exception:
            await msg.reply_text(new_caption, reply_markup=keyboard)

        try:
            await thinking.edit_text("✅ تحلیل ویرایش شد! پیام بالا آپدیت شده.")
        except Exception:
            pass

    except Exception as e:
        logger.exception("ai edit error")
        try:
            await thinking.edit_text(f"❌ خطا در ویرایش: {e}")
        except Exception:
            pass


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone_text),
            ],
            CHECK_MEMBERSHIP: [
                CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"),
            ],
            MAIN_MENU: [
                CallbackQueryHandler(show_analysis_menu, pattern="^analysis_menu$"),
                CallbackQueryHandler(show_analysis, pattern="^(gold|dollar|bitcoin)$"),
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(gold_calc_start, pattern="^gold_calc$"),
                CallbackQueryHandler(gold_live, pattern="^gold_live$"),
                CallbackQueryHandler(gold_custom_start, pattern="^gold_custom$"),
                CallbackQueryHandler(calendar_menu, pattern="^calendar_menu$"),
                CallbackQueryHandler(calendar_today, pattern="^cal_today$"),
                CallbackQueryHandler(calendar_week, pattern="^cal_week$"),
                CallbackQueryHandler(bubble_menu, pattern="^bubble_menu$"),
                CallbackQueryHandler(bubble_show, pattern="^bubble_(gold|silver)$"),
                CallbackQueryHandler(vip_menu, pattern="^vip_menu$"),
                CallbackQueryHandler(vip_pay_info, pattern="^vip_pay_info$"),
                CallbackQueryHandler(vip_pay, pattern="^vip_pay$"),
                CallbackQueryHandler(referral_menu, pattern="^referral_menu$"),
                CallbackQueryHandler(car_prices_menu, pattern="^car_prices$"),
                CallbackQueryHandler(sentiment_menu, pattern="^sentiment_menu$"),
                CallbackQueryHandler(support_menu, pattern="^support_menu$"),
                CallbackQueryHandler(alert_menu, pattern="^alert_menu$"),
                CallbackQueryHandler(alert_new, pattern="^alert_new$"),
                CallbackQueryHandler(alert_asset_selected, pattern="^alert_asset_(gold|dollar|bitcoin|ethereum|gold_ounce)$"),
                CallbackQueryHandler(alert_list, pattern="^alert_list$"),
                CallbackQueryHandler(alert_delete, pattern="^alert_del_\\d+$"),
                CallbackQueryHandler(alert_cancel, pattern="^alert_cancel$"),
                CallbackQueryHandler(alert_default_msg, pattern="^alert_default_msg$"),
            ],
            ALERT_ENTER_PRICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_get_price),
                CallbackQueryHandler(alert_confirm_price, pattern="^alert_confirm_price$"),
                CallbackQueryHandler(alert_cancel, pattern="^alert_cancel$"),
            ],
            ALERT_ENTER_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, alert_get_message),
                CallbackQueryHandler(alert_default_msg, pattern="^alert_default_msg$"),
                CallbackQueryHandler(alert_cancel, pattern="^alert_cancel$"),
            ],
            GOLD_CALC_OUNCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gold_calc_get_ounce),
            ],
            GOLD_CALC_DOLLAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, gold_calc_get_dollar),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(show_analysis_menu, pattern="^analysis_menu$"))
    app.add_handler(CallbackQueryHandler(show_analysis, pattern="^(gold|dollar|bitcoin)$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(check_membership_callback, pattern="^check_membership$"))
    app.add_handler(CallbackQueryHandler(gold_calc_start, pattern="^gold_calc$"))
    app.add_handler(CallbackQueryHandler(gold_live, pattern="^gold_live$"))
    app.add_handler(CallbackQueryHandler(gold_custom_start, pattern="^gold_custom$"))
    app.add_handler(CallbackQueryHandler(calendar_menu, pattern="^calendar_menu$"))
    app.add_handler(CallbackQueryHandler(calendar_today, pattern="^cal_today$"))
    app.add_handler(CallbackQueryHandler(calendar_week, pattern="^cal_week$"))
    app.add_handler(CallbackQueryHandler(bubble_menu, pattern="^bubble_menu$"))
    app.add_handler(CallbackQueryHandler(bubble_show, pattern="^bubble_(gold|silver)$"))
    app.add_handler(CallbackQueryHandler(vip_menu, pattern="^vip_menu$"))
    app.add_handler(CallbackQueryHandler(vip_pay_info, pattern="^vip_pay_info$"))
    app.add_handler(CallbackQueryHandler(vip_pay, pattern="^vip_pay$"))
    app.add_handler(CallbackQueryHandler(referral_menu, pattern="^referral_menu$"))
    app.add_handler(CallbackQueryHandler(vip_approve_callback, pattern="^vip_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(vip_reject_callback, pattern="^vip_reject_\d+$"))
    app.add_handler(CallbackQueryHandler(car_prices_menu, pattern="^car_prices$"))
    app.add_handler(CallbackQueryHandler(sentiment_menu, pattern="^sentiment_menu$"))
    app.add_handler(CallbackQueryHandler(support_menu, pattern="^support_menu$"))
    app.add_handler(CallbackQueryHandler(alert_menu, pattern="^alert_menu$"))
    app.add_handler(CallbackQueryHandler(alert_new, pattern="^alert_new$"))
    app.add_handler(CallbackQueryHandler(alert_asset_selected, pattern="^alert_asset_(gold|dollar|bitcoin|ethereum|gold_ounce)$"))
    app.add_handler(CallbackQueryHandler(alert_list, pattern="^alert_list$"))
    app.add_handler(CallbackQueryHandler(alert_delete, pattern="^alert_del_\\d+$"))
    app.add_handler(CallbackQueryHandler(alert_confirm_price, pattern="^alert_confirm_price$"))
    app.add_handler(CallbackQueryHandler(alert_cancel, pattern="^alert_cancel$"))
    app.add_handler(CommandHandler("approve", approve_vip))
    app.add_handler(CommandHandler("reject", reject_vip))
    app.add_handler(MessageHandler(filters.Regex(r"^/approve_\d+$"), approve_vip))
    app.add_handler(MessageHandler(filters.Regex(r"^/reject_\d+$"), reject_vip))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_vip_receipt_global))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.PHOTO, handle_non_photo_while_waiting_receipt))
    # AI Analysis handlers
    app.add_handler(CommandHandler("ai", cmd_trigger_ai_analysis))
    app.add_handler(CallbackQueryHandler(ai_approve_callback, pattern=r"^ai_approve:"))
    app.add_handler(CallbackQueryHandler(ai_edit_callback, pattern=r"^ai_edit:"))
    # این handler باید با group=-1 ثبت بشه تا قبل از ConversationHandler اجرا بشه
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (filters.TEXT | filters.VOICE),
        ai_edit_prompt_handler,
    ), group=-1)

    if app.job_queue is not None:
        app.job_queue.run_repeating(check_vip_expirations, interval=3600, first=15)
        app.job_queue.run_repeating(check_price_alerts, interval=300, first=60)
        # تحلیل روزانه ساعت ۹ صبح به وقت تهران
        import datetime as _dt
        import pytz as _pytz
        _tehran = _pytz.timezone("Asia/Tehran")
        app.job_queue.run_daily(
            daily_ai_analysis_job,
            time=_dt.time(hour=9, minute=0, tzinfo=_tehran),
            name="daily_ai_analysis",
        )
    else:
        logger.warning("job_queue فعال نیست")
    logger.info("✅ ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()