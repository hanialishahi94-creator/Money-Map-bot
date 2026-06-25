# -*- coding: utf-8 -*-
"""
این فایل هم بات تلگرام و هم پنل ادمین وب را با هم اجرا می‌کند،
تا فقط با یک سرویس (مثلاً یک سرویس روی Railway) هر دو بالا بیایند.
"""

import os
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


def run_admin_panel():
    from admin_panel import app
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🌐 پنل ادمین روی پورت {port} بالا آمد")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_bot():
    import telegram_bot
    telegram_bot.main()


if __name__ == "__main__":
    # پنل ادمین در یک ترد جدا (پس‌زمینه) اجرا می‌شود
    panel_thread = threading.Thread(target=run_admin_panel, daemon=True)
    panel_thread.start()

    # بات تلگرام در ترد اصلی اجرا می‌شود
    run_bot()
