from dotenv import load_dotenv
import os
load_dotenv()
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import logging

# ===== تنظیمات =====
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
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
ASK_NAME, ASK_PHONE, MAIN_MENU = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in users:
        await show_main_menu(update, context)
        return MAIN_MENU
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
    if not contact:
        await update.message.reply_text("لطفاً از دکمه زیر شماره‌ات رو به اشتراک بذار.")
        return ASK_PHONE

    user_id = update.effective_user.id
    name = context.user_data["name"]
    phone = contact.phone_number
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
    await show_main_menu(update, context)
    return MAIN_MENU


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥇 تحلیل طلا", callback_data="gold")],
        [InlineKeyboardButton("💵 تحلیل دلار", callback_data="dollar")],
        [InlineKeyboardButton("₿ تحلیل بیتکوین", callback_data="bitcoin")],
    ])
    user_id = update.effective_user.id
    name = users.get(user_id, {}).get("name", "کاربر")
    text = f"سلام {name}! 👋\nیکی از گزینه‌های زیر رو انتخاب کن:"
    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=keyboard)


async def show_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
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


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)
    return MAIN_MENU


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_PHONE: [MessageHandler(filters.CONTACT, get_phone)],
            MAIN_MENU: [
                CallbackQueryHandler(show_analysis, pattern="^(gold|dollar|bitcoin)$"),
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(show_analysis, pattern="^(gold|dollar|bitcoin)$"))
    app.add_handler(CallbackQueryHandler(back_to_menu, pattern="^menu$"))
    logger.info("✅ ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()
