import os
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from telegram.error import TelegramError
import logging

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")  # توکن ربات از متغیر محیطی (Railway -> Variables -> BOT_TOKEN)
ADMIN_GROUP_ID = -1004358699434  # آیدی گروه ادمین
CHANNEL_USERNAME = "@Money_Mapp"  # یوزرنیم کانال (ربات باید توش ادمین باشه)

# ===================================================
# ✏️ اینجا هر هفته تحلیل‌ها رو آپدیت کن
# ===================================================

ANALYSES = {
    "gold": """
📅 تاریخ تحلیل: ۱ تیر ۱۴۰۴

🥇 تحلیل طلا

📈 روند فعلی:
طلا در محدوده ۲۳۵۰ تا ۲۴۰۰ دلار در نوسانه. روند کلی صعودیه.

🛡 حمایت‌ها:
• حمایت اول: ۲۳۵۰ دلار
• حمایت دوم: ۲۳۰۰ دلار

🔺 مقاومت‌ها:
• مقاومت اول: ۲۴۰۰ دلار
• مقاومت دوم: ۲۴۵۰ دلار

🔮 پیش‌بینی کوتاه‌مدت:
در صورت شکست مقاومت ۲۴۰۰، هدف بعدی ۲۴۵۰ خواهد بود.

✅ توصیه کلی:
نگه‌داشتن پوزیشن خرید با حد ضرر زیر ۲۳۰۰ توصیه میشه.
""",

    "dollar": """
📅 تاریخ تحلیل: ۱ تیر ۱۴۰۴

💵 تحلیل دلار

📈 روند فعلی:
دلار در بازار ایران در محدوده ۶۲ تا ۶۵ هزار تومان در نوسانه.

🛡 حمایت‌ها:
• حمایت اول: ۶۲,۰۰۰ تومان
• حمایت دوم: ۶۰,۰۰۰ تومان

🔺 مقاومت‌ها:
• مقاومت اول: ۶۵,۰۰۰ تومان
• مقاومت دوم: ۶۸,۰۰۰ تومان

🔮 پیش‌بینی کوتاه‌مدت:
با توجه به شرایط سیاسی، احتمال نوسان بالاست.

✅ توصیه کلی:
خرید در کف‌های حمایتی با دید میان‌مدت توصیه میشه.
""",

    "bitcoin": """
📅 تاریخ تحلیل: ۱ تیر ۱۴۰۴

₿ تحلیل بیتکوین

📈 روند فعلی:
بیتکوین در محدوده ۶۵,۰۰۰ تا ۷۰,۰۰۰ دلار در نوسانه. روند میان‌مدت صعودیه.

🛡 حمایت‌ها:
• حمایت اول: ۶۵,۰۰۰ دلار
• حمایت دوم: ۶۰,۰۰۰ دلار

🔺 مقاومت‌ها:
• مقاومت اول: ۷۰,۰۰۰ دلار
• مقاومت دوم: ۷۵,۰۰۰ دلار

🔮 پیش‌بینی کوتاه‌مدت:
در صورت تثبیت بالای ۷۰,۰۰۰، هدف بعدی ۷۵,۰۰۰ دلاره.

✅ توصیه کلی:
خرید پله‌ای در کف‌های حمایتی با دید بلندمدت.
"""
}

# ===================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

users = {}
ASK_NAME, ASK_PHONE, CHECK_MEMBERSHIP, MAIN_MENU, GOLD_CALC_OUNCE, GOLD_CALC_DOLLAR = range(6)


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

    users[user_id] = {"name": name, "phone": phone}
    logger.info(f"کاربر جدید: {users[user_id]}")

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
        await show_main_menu(update, context)
        return MAIN_MENU
    else:
        await query.message.reply_text(
            "❌ هنوز عضو کانال نشدی!\n"
            f"لطفاً اول عضو {CHANNEL_USERNAME} بشو، بعد دوباره دکمه رو بزن."
        )
        return CHECK_MEMBERSHIP


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 تحلیل بازار", callback_data="analysis_menu")],
        [InlineKeyboardButton("🧮 محاسبه ارزش واقعی طلای ۱۸ عیار", callback_data="gold_calc")],
        [InlineKeyboardButton("🫧 حباب صندوق‌ها", callback_data="bubble_menu")],
        [InlineKeyboardButton("🗓 تقویم اقتصادی", callback_data="calendar_menu")],
    ])
    user_id = update.effective_user.id
    name = users.get(user_id, {}).get("name", "کاربر")
    text = f"سلام {name}! 👋\nیکی از گزینه‌های زیر رو انتخاب کن:"
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)


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
    asset_name = asset_map[query.data]
    analysis_text = ANALYSES[query.data]
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")]
    ])
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
                    raw = rows[0][1]  # ستون دوم = قیمت فعلی
                    price = float(str(raw).replace(",", ""))
                    return price
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت {symbol}: {e}")
    return None


def calc_gold18(ounce_usd: float, dollar_toman: float) -> tuple[float, float]:
    gram_usd = (ounce_usd / 31.1035) * 0.75
    gram_toman = gram_usd * dollar_toman
    return gram_usd, gram_toman


def gold_result_text(ounce_usd: float, dollar_toman: float, source: str) -> str:
    gram_usd, gram_toman = calc_gold18(ounce_usd, dollar_toman)
    return (
        f"📊 ارزش واقعی طلای ۱۸ عیار {source}\n"
        f"{'─' * 32}\n"
        f"🔸 اونس جهانی: {ounce_usd:,.2f} دلار\n"
        f"🔸 نرخ دلار (بازار آزاد): {dollar_toman:,.0f} تومان\n"
        f"{'─' * 32}\n"
        f"💰 ارزش هر گرم طلای ۱۸ عیار:\n"
        f"   {gram_toman:,.0f} تومان"
    )


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

    if not ounce or not dollar:
        await query.message.reply_text(
            "⚠️ دریافت قیمت لحظه‌ای موفق نبود. لطفاً دقایقی دیگر دوباره امتحان کن یا از روش دستی استفاده کن."
        )
        return MAIN_MENU

    dollar_toman = dollar / 10

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بروزرسانی مجدد", callback_data="gold_live")],
        [InlineKeyboardButton("✏️ محاسبه با مفروضات دلخواه", callback_data="gold_custom")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu")],
    ])
    await query.message.reply_text(
        gold_result_text(ounce, dollar_toman, "لحظه‌ای"),
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


def filter_events(events: list, today_only: bool = False) -> list:
    from datetime import datetime, timezone, timedelta
    result = []
    now_tehran = datetime.now(timezone.utc) + timedelta(hours=3, minutes=30)
    today_str = now_tehran.strftime("%Y-%m-%d")

    for e in events:
        impact = e.get("impact", "").lower()
        if impact not in ("high", "medium"):
            continue
        if e.get("currency", "") not in TARGET_CURRENCIES:
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
    return result


def format_event(e: dict) -> str:
    from datetime import datetime, timezone, timedelta
    currency = e.get("currency", "")
    currency_fa = CURRENCY_FA.get(currency, currency)
    title_en = e.get("title", "")
    forecast = e.get("forecast", "") or "—"
    previous = e.get("previous", "") or "—"
    impact = e.get("impact", "").lower()
    impact_icon = "🔴" if impact == "high" else "🟠"

    date_raw = e.get("date", "")
    try:
        dt_utc = datetime.fromisoformat(date_raw.replace("Z", "+00:00"))
        dt_tehran = dt_utc + timedelta(hours=3, minutes=30)
        time_str = dt_tehran.strftime("%H:%M")
        day_str = dt_tehran.strftime("%Y/%m/%d")
    except Exception:
        time_str = "—"
        day_str = "—"

    return (
        f"{impact_icon} {currency_fa}\n"
        f"📌 {title_en}\n"
        f"📅 {day_str}  ⏰ {time_str} (تهران)\n"
        f"🔮 پیش‌بینی: {forecast}  |  📊 قبلی: {previous}\n"
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
        "🗓 تقویم اقتصادی\n\nاخبار مهم 🔴 و متوسط 🟠 ارزهای اصلی\nکدام بازه را می‌خواهی؟",
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
    برای طلا از fundbase.ir/h می‌خواند
    برای نقره از fundbase.ir/h/silver می‌خواند
    """
    import aiohttp
    from html.parser import HTMLParser

    url = "https://fundbase.ir/h" if fund_type == "gold" else "https://fundbase.ir/h/silver"

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
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"fundbase status: {resp.status}")
                    return None
                html = await resp.text(encoding="utf-8", errors="ignore")

        parser = TableParser()
        parser.feed(html)

        # اولین جدول با بیش از ۲ ستون که داده دارد
        funds = []
        for row in parser.rows:
            if len(row) >= 4:
                name = row[0].strip()
                price = row[1].strip() if len(row) > 1 else "—"
                bubble_price = row[2].strip() if len(row) > 2 else "—"
                bubble_intrinsic = row[3].strip() if len(row) > 3 else "—"
                bubble_total = row[4].strip() if len(row) > 4 else "—"
                # رد کردن هدر
                if name in ("نماد", "صندوق", ""):
                    continue
                funds.append({
                    "name": name,
                    "price": price,
                    "bubble_price": bubble_price,
                    "bubble_intrinsic": bubble_intrinsic,
                    "bubble_total": bubble_total,
                })
        return funds if funds else None

    except Exception as e:
        logger.error(f"خطا در scraping فاندبیس: {e}")
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
        "🫧 حباب صندوق‌های سرمایه‌گذاری\n\nداده‌ها از فاندبیس دریافت می‌شوند.\nکدام دسته را می‌خواهی؟",
        reply_markup=keyboard,
    )
    return MAIN_MENU


async def bubble_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io

    query = update.callback_query
    await query.answer()
    fund_type = "gold" if query.data == "bubble_gold" else "silver"
    label = "\u0637\u0644\u0627 \U0001f947" if fund_type == "gold" else "\u0646\u0642\u0631\u0647 \U0001fa99"
    title = "Gold Funds Bubble" if fund_type == "gold" else "Silver Funds Bubble"

    await query.message.reply_text(f"\u23f3 \u062f\u0631 \u062d\u0627\u0644 \u062f\u0631\u06cc\u0627\u0641\u062a \u062f\u0627\u062f\u0647 ...")

    funds = await fetch_bubble_data(fund_type)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f504 \u0628\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc", callback_data=query.data)],
        [InlineKeyboardButton("\U0001f519 \u0628\u0627\u0632\u06af\u0634\u062a", callback_data="bubble_menu")],
    ])

    if not funds:
        await query.message.reply_text(
            "\u26a0\ufe0f \u062f\u0631\u06cc\u0627\u0641\u062a \u062f\u0627\u062f\u0647 \u0645\u0648\u0641\u0642 \u0646\u0628\u0648\u062f. \u0644\u0637\u0641\u0627\u064b \u062f\u0642\u0627\u06cc\u0642\u06cc \u062f\u06cc\u06af\u0631 \u0627\u0645\u062a\u062d\u0627\u0646 \u06a9\u0646.",
            reply_markup=keyboard,
        )
        return MAIN_MENU

    names = []
    values = []
    for f in funds:
        raw = f["bubble_total"].replace("\u066a", "").replace("%", "").replace("+", "").replace("\u2212", "-").replace("\u200e", "").strip()
        try:
            val = float(raw)
            names.append(f["name"])
            values.append(val)
        except Exception:
            continue

    if not names:
        await query.message.reply_text("\u26a0\ufe0f \u062f\u0627\u062f\u0647\u200c\u0647\u0627\u06cc \u0639\u062f\u062f\u06cc \u0642\u0627\u0628\u0644 \u0646\u0645\u0627\u06cc\u0634 \u0646\u0628\u0648\u062f\u0646\u062f.", reply_markup=keyboard)
        return MAIN_MENU

    # \u0645\u0631\u062a\u0628 \u0646\u0632\u0648\u0644\u06cc
    paired = sorted(zip(values, names), reverse=True)
    values = [v for v, _ in paired]
    names_label = [n for _, n in paired]

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

    fig, ax = plt.subplots(figsize=(max(10, len(names) * 0.75), 5))
    fig.patch.set_facecolor("#FAFAFA")
    ax.set_facecolor("#FAFAFA")

    bars = ax.bar(range(len(names_label)), values, color=colors, width=0.6, zorder=3)
    ax.axhline(0, color="#888", linewidth=1, linestyle="--", zorder=2)
    ax.set_xticks(range(len(names_label)))
    ax.set_xticklabels(names_label, fontsize=9, rotation=35, ha="right")

    for bar, val in zip(bars, values):
        sign = "+" if val >= 0 else ""
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + (0.04 if val >= 0 else -0.12),
            f"{sign}{val:.1f}%",
            ha="center", va="bottom" if val >= 0 else "top",
            fontsize=8, fontweight="bold", color="#333"
        )

    ax.set_title(title, fontsize=13, fontweight="bold", color="#1a1a2e", pad=12)
    ax.set_ylabel("Bubble Total (%)", fontsize=10, color="#444")
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)

    await query.message.reply_photo(photo=buf, caption=f"\U0001faa7 \u062d\u0628\u0627\u0628 \u0635\u0646\u062f\u0648\u0642\u200c\u0647\u0627\u06cc {label}", reply_markup=keyboard)
    return MAIN_MENU

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
    logger.info("✅ ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
