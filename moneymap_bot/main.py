import os
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


def run_admin_panel():
    from admin_panel import app
    port = int(os.getenv("PORT", 8000))
    logger.info(f"panel running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def run_bot():
    import telegram_bot
    telegram_bot.main()


if __name__ == "__main__":
    panel_thread = threading.Thread(target=run_admin_panel, daemon=True)
    panel_thread.start()
    run_bot()
