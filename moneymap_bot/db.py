# -*- coding: utf-8 -*-
"""
ماژول دیتابیس مشترک بین بات تلگرام و پنل ادمین.
از SQLite استفاده می‌کند تا دیتای کاربران، اعضای VIP و متن تحلیل‌ها
بعد از ری‌استارت شدن بات (مثلاً روی Railway) از بین نرود.
"""

import sqlite3
import time
import os
import json
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "/data/moneymap.db" if os.path.isdir("/data") else "moneymap.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


DEFAULT_ANALYSES = {
    "gold": {
        "title": "🥇 تحلیل طلا",
        "text": "هنوز تحلیلی برای طلا ثبت نشده است.",
    },
    "dollar": {
        "title": "💵 تحلیل دلار",
        "text": "هنوز تحلیلی برای دلار ثبت نشده است.",
    },
    "bitcoin": {
        "title": "₿ تحلیل بیتکوین",
        "text": "هنوز تحلیلی برای بیتکوین ثبت نشده است.",
    },
}


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                username TEXT,
                joined_at REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vip_members (
                user_id INTEGER PRIMARY KEY,
                expire_at REAL
            )
            """
        )
        # migration: ستون‌های یادآوری (برای دیتابیس‌های قدیمی‌تر که این ستون‌ها رو ندارن)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(vip_members)").fetchall()}
        for col in ("reminder_7", "reminder_3", "reminder_0"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE vip_members ADD COLUMN {col} INTEGER DEFAULT 0")

        # migration: ستون‌های سیستم رفرال (معرفی دوستان) برای جدول users
        existing_user_cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if "referred_by" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        if "referral_rewards_given" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN referral_rewards_given INTEGER DEFAULT 0")
        if "joined_channel" not in existing_user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN joined_channel INTEGER DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                asset TEXT PRIMARY KEY,
                analysis_date TEXT,
                text TEXT,
                image_path TEXT,
                updated_at REAL
            )
            """
        )
        # migration: ستون‌های اضافی برای دیتابیس‌های قدیمی‌تر
        existing_analysis_cols = {row["name"] for row in conn.execute("PRAGMA table_info(analyses)").fetchall()}
        if "image_path" not in existing_analysis_cols:
            conn.execute("ALTER TABLE analyses ADD COLUMN image_path TEXT")
        if "chart_bytes" not in existing_analysis_cols:
            conn.execute("ALTER TABLE analyses ADD COLUMN chart_bytes BLOB")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                target_price REAL NOT NULL,
                direction TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at REAL NOT NULL,
                triggered INTEGER DEFAULT 0
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS support_map (
                msg_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )

        # مقداردهی اولیه تحلیل‌ها در صورت خالی بودن جدول
        existing = conn.execute("SELECT asset FROM analyses").fetchall()
        existing_assets = {row["asset"] for row in existing}
        for asset, data in DEFAULT_ANALYSES.items():
            if asset not in existing_assets:
                conn.execute(
                    "INSERT INTO analyses (asset, analysis_date, text, image_path, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (asset, "", data["text"], None, time.time()),
                )


# ---------- کاربران ----------

def upsert_user(user_id: int, name: str, phone: str, username: str = ""):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO users (user_id, name, phone, username, joined_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                name = excluded.name,
                phone = excluded.phone,
                username = excluded.username
            """,
            (user_id, name, phone, username, time.time()),
        )


def get_user(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        return [dict(r) for r in rows]


def delete_user(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM vip_members WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))


def find_user_by_phone(phone: str):
    """جست‌وجوی کاربر با شماره موبایل (برای فعال‌سازی دستی VIP از پنل)."""
    cleaned = (phone or "").strip()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE phone = ? OR phone = ? OR phone = ?",
            (cleaned, cleaned.replace("+98", "0"), "+98" + cleaned.lstrip("0")),
        ).fetchone()
        return dict(row) if row else None


# ---------- سیستم رفرال (معرفی دوستان) ----------

def set_referrer(user_id: int, referrer_id: int):
    """فقط وقتی کاربر برای اولین‌بار از طریق لینک رفرال وارد شده ثبت می‌شه.
    اگه قبلاً referred_by داشته باشه (یا خودش معرف خودش باشه) تغییری نمی‌کنه."""
    if not referrer_id or referrer_id == user_id:
        return
    with get_conn() as conn:
        row = conn.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None or row["referred_by"] is not None:
            return
        conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?", (referrer_id, user_id))


def get_referred_by(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT referred_by FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row["referred_by"] if row else None


def get_confirmed_referral_count(referrer_id: int):
    """تعداد افرادی که این کاربر معرفی کرده و واقعاً عضو کانال شدن (رفرال موفق)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE referred_by = ? AND joined_channel = 1",
            (referrer_id,),
        ).fetchone()
        return row["cnt"] if row else 0


def mark_channel_joined(user_id: int) -> bool:
    """وقتی کاربر عضویتش در کانال تایید می‌شه این رو صدا می‌زنیم.
    اگه این اولین‌باری باشه که عضویتش ثبت می‌شه، True برمی‌گردونه (تا فقط یک‌بار جایزه/گزارش رفرال محاسبه شه)،
    وگرنه (قبلاً ثبت شده بود) False برمی‌گردونه."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT joined_channel FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        already = bool(row and row["joined_channel"])
        conn.execute(
            "UPDATE users SET joined_channel = 1 WHERE user_id = ?", (user_id,)
        )
        return not already


def get_referral_rewards_given(referrer_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referral_rewards_given FROM users WHERE user_id = ?", (referrer_id,)
        ).fetchone()
        return row["referral_rewards_given"] if row and row["referral_rewards_given"] is not None else 0


def increment_referral_rewards_given(referrer_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET referral_rewards_given = COALESCE(referral_rewards_given, 0) + 1 WHERE user_id = ?",
            (referrer_id,),
        )


def is_referral_enabled():
    val = get_setting("referral_enabled", "0")
    return str(val) == "1"


def set_referral_enabled(enabled: bool):
    set_setting("referral_enabled", "1" if enabled else "0")


def get_referral_required_count(default: int = 8):
    val = get_setting("referral_required_count")
    try:
        return int(float(val)) if val is not None else default
    except (TypeError, ValueError):
        return default


def get_users_signup_counts(days: int = 7):
    """تعداد ثبت‌نام‌های روزانه در N روز اخیر — برای نمودار رشد داشبورد."""
    import datetime
    now = time.time()
    buckets = []
    with get_conn() as conn:
        rows = conn.execute("SELECT joined_at FROM users").fetchall()
    timestamps = [r["joined_at"] for r in rows if r["joined_at"]]
    for i in range(days - 1, -1, -1):
        day_start = now - i * 86400
        day_dt = datetime.datetime.fromtimestamp(day_start)
        day_key = day_dt.strftime("%Y-%m-%d")
        count = sum(
            1 for ts in timestamps
            if datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d") == day_key
        )
        buckets.append({"date": day_key, "count": count})
    return buckets


# ---------- VIP ----------

def set_vip(user_id: int, expire_at: float):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO vip_members (user_id, expire_at, reminder_7, reminder_3, reminder_0)
            VALUES (?, ?, 0, 0, 0)
            ON CONFLICT(user_id) DO UPDATE SET
                expire_at = excluded.expire_at,
                reminder_7 = 0,
                reminder_3 = 0,
                reminder_0 = 0
            """,
            (user_id, expire_at),
        )


def add_vip_days(user_id: int, days: int):
    """تمدید اشتراک: اگه هنوز اشتراک فعال داره، روزها به انتهای اشتراکش اضافه می‌شه،
    وگرنه از همین الان حساب می‌شه. در هر حالت پرچم‌های یادآوری ریست می‌شن."""
    now = time.time()
    current = get_vip_expiry(user_id)
    base = current if (current and current > now) else now
    new_expire = base + (days * 86400)
    set_vip(user_id, new_expire)
    return new_expire


def get_vip_expiry(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT expire_at FROM vip_members WHERE user_id = ?", (user_id,)).fetchone()
        return row["expire_at"] if row else None


def get_all_vip():
    """لیست همه اعضای VIP همراه با اطلاعات کاربر (اسم/شماره) - مرتب بر اساس نزدیک‌ترین انقضا"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT v.user_id, v.expire_at, v.reminder_7, v.reminder_3, v.reminder_0,
                   u.name, u.phone, u.username
            FROM vip_members v
            LEFT JOIN users u ON u.user_id = v.user_id
            ORDER BY v.expire_at ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def mark_vip_reminder_sent(user_id: int, which: str):
    """which یکی از 'reminder_7', 'reminder_3', 'reminder_0'"""
    if which not in ("reminder_7", "reminder_3", "reminder_0"):
        return
    with get_conn() as conn:
        conn.execute(f"UPDATE vip_members SET {which} = 1 WHERE user_id = ?", (user_id,))


def remove_vip(user_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM vip_members WHERE user_id = ?", (user_id,))


# ---------- تحلیل‌ها ----------

def get_analysis(asset: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM analyses WHERE asset = ?", (asset,)).fetchone()
        return dict(row) if row else None


def get_all_analyses():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM analyses").fetchall()
        return {r["asset"]: dict(r) for r in rows}


def set_analysis(asset: str, analysis_date: str, text: str,
                 image_path: str = None, chart_bytes: bytes = None):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO analyses (asset, analysis_date, text, image_path, chart_bytes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset) DO UPDATE SET
                analysis_date = excluded.analysis_date,
                text = excluded.text,
                image_path = COALESCE(excluded.image_path, image_path),
                chart_bytes = COALESCE(excluded.chart_bytes, chart_bytes),
                updated_at = excluded.updated_at
            """,
            (asset, analysis_date, text, image_path, chart_bytes, time.time()),
        )


# ---------- تنظیمات (قیمت/مدت اشتراک VIP و ...) ----------

def get_setting(key: str, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )


def get_vip_price_usdt(default: float = 20):
    val = get_setting("vip_price_usdt")
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def get_vip_days(default: int = 30):
    val = get_setting("vip_days")
    try:
        return int(float(val)) if val is not None else default
    except (TypeError, ValueError):
        return default


def is_vip_channel_open() -> bool:
    """آیا ظرفیت کانال VIP باز است؟ (پیش‌فرض: باز)"""
    val = get_setting("vip_channel_open")
    return val != "0"


def set_vip_channel_open(value: bool):
    """باز یا بسته کردن ظرفیت کانال VIP از پنل ادمین."""
    set_setting("vip_channel_open", "1" if value else "0")


# ---------- هشدار قیمت ----------

def add_price_alert(user_id: int, asset: str, target_price: float, direction: str, message: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO price_alerts (user_id, asset, target_price, direction, message, created_at, triggered) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (user_id, asset, target_price, direction, message, time.time()),
        )
        return cur.lastrowid


def get_active_alerts_for_user(user_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_alerts WHERE user_id = ? AND triggered = 0 ORDER BY created_at ASC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_active_alerts():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_alerts WHERE triggered = 0"
        ).fetchall()
        return [dict(r) for r in rows]


def delete_price_alert(alert_id: int, user_id: int):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM price_alerts WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )


def mark_alert_triggered(alert_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE price_alerts SET triggered = 1 WHERE id = ?",
            (alert_id,),
        )


def count_active_alerts(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM price_alerts WHERE user_id = ? AND triggered = 0",
            (user_id,),
        ).fetchone()
        return row["cnt"] if row else 0


# ===== قیمت خودرو =====

def save_car_prices(prices: dict):
    """ذخیره قیمت‌های فعلی خودرو (dict: {name: price})"""
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS car_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                saved_at REAL NOT NULL
            )
            """
        )
        for name, price in prices.items():
            conn.execute(
                "INSERT INTO car_prices (name, price, saved_at) VALUES (?, ?, ?)",
                (name, price, now),
            )


def get_previous_car_prices(hours_ago: int = 20) -> dict:
    """برگرداندن آخرین قیمت‌های ذخیره‌شده قبل از X ساعت پیش"""
    cutoff = time.time() - hours_ago * 3600
    result = {}
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT name, price FROM car_prices
                WHERE saved_at <= ?
                ORDER BY saved_at DESC
                """,
                (cutoff,),
            ).fetchall()
            for row in rows:
                if row["name"] not in result:
                    result[row["name"]] = row["price"]
    except Exception:
        pass
    return result


# ---------- ویرایش تحلیل AI (پایدار در SQLite) ----------

def set_ai_edit_waiting(prompt_msg_id: int, asset_key: str, original_text: str, analysis_msg_id: int):
    """ذخیره اطلاعات ویرایش در انتظار — در SQLite تا بعد از ری‌استارت باقی بماند."""
    data = json.dumps({
        "asset_key": asset_key,
        "original_text": original_text,
        "analysis_msg_id": analysis_msg_id,
    })
    set_setting(f"ai_edit:{prompt_msg_id}", data)


def get_ai_edit_waiting(prompt_msg_id: int):
    """دریافت اطلاعات ویرایش در انتظار با شناسه پیام درخواست."""
    val = get_setting(f"ai_edit:{prompt_msg_id}")
    if not val:
        return None
    try:
        return json.loads(val)
    except Exception:
        return None


def clear_ai_edit_waiting(prompt_msg_id: int):
    """حذف رکورد ویرایش بعد از پردازش."""
    with get_conn() as conn:
        conn.execute("DELETE FROM settings WHERE key = ?", (f"ai_edit:{prompt_msg_id}",))


# ---------- نگاشت پیام پشتیبانی → کاربر ----------

def save_support_msg(msg_id: int, user_id: int):
    """ذخیره رابطه‌ی msg_id گروه پشتیبانی → user_id کاربر."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO support_map (msg_id, user_id, created_at) VALUES (?, ?, ?)",
            (msg_id, user_id, time.time()),
        )


def get_support_user(msg_id: int) -> int | None:
    """پیدا کردن user_id کاربر از msg_id پیام گروه پشتیبانی."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM support_map WHERE msg_id = ?", (msg_id,)
        ).fetchone()
        return row["user_id"] if row else None


# ---------- تاریخچه قیمت دلار (برای امتیاز فرصت) ----------

def save_dollar_price(date: str, price_toman: float):
    """ذخیره قیمت دلار برای یک روز خاص (برای محاسبه تغییر روزانه)."""
    set_setting(f"dollar_price:{date}", str(price_toman))


def get_dollar_price(date: str) -> float | None:
    """دریافت قیمت ذخیره‌شده دلار برای یک روز خاص."""
    val = get_setting(f"dollar_price:{date}")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


# هنگام import شدن، مطمئن شو جدول‌ها ساخته شده‌اند
init_db()