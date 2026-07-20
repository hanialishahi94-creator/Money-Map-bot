# -*- coding: utf-8 -*-
"""
پنل ادمین وب برای بات تلگرام Money MAP.

این فایل دو نقش دارد:
  ۱) یک REST/JSON API زیر مسیر /api/* که داشبورد جدید (React، پوشه minimapa)
     از طریق fetch با همین API صحبت می‌کند — احراز هویت بر اساس session cookie.
  ۲) سرو کردن فایل‌های build‌شده‌ی همان داشبورد React (پوشه minimapa/dist) به
     عنوان فرانت‌اند — یعنی بعد از اجرای `npm run build` در پوشه minimapa،
     همین یک سرویس Flask هم API و هم رابط کاربری را serve می‌کند.

برای توسعه‌ی محلی (npm run dev روی Vite, پورت 5173) یک پروکسی /api در
vite.config.ts تنظیم شده که این درخواست‌ها را به پورت Flask (پیش‌فرض 8000)
فوروارد می‌کند، بنابراین در حالت توسعه هم نیازی به CORS نیست.
"""

import os
import io
import time
import json
import datetime
import mimetypes
import urllib.request
import urllib.parse
from functools import wraps

from flask import (
    Flask, request, session, jsonify, send_from_directory, abort
)

import db

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv("SECRET_KEY", "moneymap-secret-key-change-me")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "09124900216")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Saba09124900216")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
VIP_CHANNEL_ID = int(os.getenv("VIP_CHANNEL_ID", "-1003794396104"))
VIP_CHANNEL_LINK = os.getenv("VIP_CHANNEL_LINK", "https://t.me/+6zpQXNwZD41mYWZk")

ASSET_LABELS = {
    "gold": "🥇 طلا",
    "dollar": "💵 دلار",
    "bitcoin": "₿ بیتکوین",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "static", "uploads", "analysis")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# پوشه‌ی خروجی build شده‌ی React (بعد از npm run build داخل پوشه minimapa)
# این پوشه باید داخل خودِ moneymap_bot کپی شود (نه یک پوشه‌ی هم‌سطح)، چون روی Railway
# تنظیم Root Directory روی /moneymap_bot است و هر چیزی خارج از این پوشه برای سرویس در حال اجرا دیده نمی‌شود.
FRONTEND_DIST = os.path.normpath(os.path.join(BASE_DIR, "frontend_dist"))


# ===================================================================
# احراز هویت
# ===================================================================

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "unauthorized"}), 401
        return view(*args, **kwargs)
    return wrapped


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"ok": True, "username": username})
    return jsonify({"ok": False, "error": "نام کاربری یا رمز عبور اشتباه است."}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me", methods=["GET"])
def api_me():
    if session.get("logged_in"):
        return jsonify({"authenticated": True, "username": session.get("username")})
    return jsonify({"authenticated": False})


# ===================================================================
# داشبورد
# ===================================================================

@app.route("/api/dashboard", methods=["GET"])
@login_required
def api_dashboard():
    users = db.get_all_users()
    vip_list = db.get_all_vip()
    now = time.time()
    active_vip = [v for v in vip_list if v["expire_at"] and v["expire_at"] > now]
    growth = db.get_users_signup_counts(7)
    return jsonify({
        "users_count": len(users),
        "vip_count": len(active_vip),
        "vip_price_usdt": db.get_vip_price_usdt(),
        "vip_days": db.get_vip_days(),
        "growth": growth,
    })


# ===================================================================
# کاربران
# ===================================================================

def _serialize_users():
    users = db.get_all_users()
    vip_map = {v["user_id"]: v for v in db.get_all_vip()}
    now = time.time()
    rows = []
    for u in users:
        vip = vip_map.get(u["user_id"])
        is_vip_active = bool(vip and vip["expire_at"] and vip["expire_at"] > now)
        rows.append({**u, "is_vip": is_vip_active})
    return rows


@app.route("/api/users", methods=["GET"])
@login_required
def api_users():
    return jsonify({"users": _serialize_users()})


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@login_required
def api_delete_user(user_id):
    db.delete_user(user_id)
    return jsonify({"ok": True})


@app.route("/api/users/<int:user_id>/activate-vip", methods=["POST"])
@login_required
def api_activate_vip_for_user(user_id):
    data = request.get_json(silent=True) or {}
    days = int(data.get("days") or db.get_vip_days())
    new_expire = db.add_vip_days(user_id, days)
    if data.get("notify"):
        expire_str = datetime.datetime.fromtimestamp(new_expire).strftime("%Y/%m/%d %H:%M")
        link = _telegram_create_vip_invite_link(user_id)
        _telegram_send_message(
            user_id,
            f"🎉 اشتراک VIP سیگنال برای شما فعال/تمدید شد!\n\n"
            f"🔗 لینک ورود به کانال (یکبار مصرف):\n{link}\n\n"
            f"تاریخ انقضا: {expire_str}",
        )
    return jsonify({"ok": True, "expire_at": new_expire})


@app.route("/api/users/<int:user_id>/remove-vip", methods=["POST"])
@login_required
def api_remove_vip_for_user(user_id):
    data = request.get_json(silent=True) or {}
    db.remove_vip(user_id)
    if data.get("notify"):
        _telegram_send_message(
            user_id,
            "⚠️ اشتراک VIP سیگنال شما توسط ادمین حذف شد.",
        )
    return jsonify({"ok": True})


# ===================================================================
# VIP
# ===================================================================

def _serialize_vip():
    vip_list = db.get_all_vip()
    now = time.time()
    rows = []
    for v in vip_list:
        remaining = v["expire_at"] - now if v["expire_at"] else 0
        is_active = remaining > 0
        days = int(remaining // 86400) if is_active else 0
        hours = int((remaining % 86400) // 3600) if is_active else 0
        expire_str = (
            datetime.datetime.fromtimestamp(v["expire_at"]).strftime("%Y/%m/%d %H:%M")
            if v["expire_at"] else "—"
        )
        rows.append({
            **v,
            "is_active": is_active,
            "days": days,
            "hours": hours,
            "expire_str": expire_str,
        })
    rows.sort(key=lambda r: (not r["is_active"], -(r["expire_at"] or 0)))
    return rows


@app.route("/api/vip", methods=["GET"])
@login_required
def api_vip():
    return jsonify({"vip": _serialize_vip()})


@app.route("/api/vip/activate", methods=["POST"])
@login_required
def api_vip_quick_activate():
    """فعال‌سازی دستی اشتراک VIP با شماره موبایل، از فرم «فعال‌سازی سریع» پنل."""
    data = request.get_json(silent=True) or {}
    phone = (data.get("phone") or "").strip()
    days = int(data.get("days") or db.get_vip_days())
    if not phone:
        return jsonify({"ok": False, "error": "شماره موبایل را وارد کن."}), 400
    user = db.find_user_by_phone(phone)
    if not user:
        return jsonify({"ok": False, "error": "کاربری با این شماره در دیتابیس پیدا نشد (باید قبلاً با بات /start زده باشد)."}), 404
    new_expire = db.add_vip_days(user["user_id"], days)
    if data.get("notify"):
        expire_str = datetime.datetime.fromtimestamp(new_expire).strftime("%Y/%m/%d %H:%M")
        link = _telegram_create_vip_invite_link(user["user_id"])
        _telegram_send_message(
            user["user_id"],
            f"🎉 اشتراک VIP سیگنال برای شما فعال/تمدید شد!\n\n"
            f"🔗 لینک ورود به کانال (یکبار مصرف):\n{link}\n\n"
            f"تاریخ انقضا: {expire_str}",
        )
    return jsonify({"ok": True, "user_id": user["user_id"], "expire_at": new_expire})


@app.route("/api/vip/<int:user_id>/extend", methods=["POST"])
@login_required
def api_vip_extend(user_id):
    data = request.get_json(silent=True) or {}
    days = int(data.get("days") or db.get_vip_days())
    new_expire = db.add_vip_days(user_id, days)
    if data.get("notify"):
        expire_str = datetime.datetime.fromtimestamp(new_expire).strftime("%Y/%m/%d %H:%M")
        link = _telegram_create_vip_invite_link(user_id)
        _telegram_send_message(
            user_id,
            f"🎉 اشتراک VIP سیگنال شما تمدید شد!\n\n"
            f"🔗 لینک ورود به کانال (یکبار مصرف):\n{link}\n\n"
            f"تاریخ انقضای جدید: {expire_str}",
        )
    return jsonify({"ok": True, "expire_at": new_expire})


@app.route("/api/vip/<int:user_id>/remove", methods=["POST"])
@login_required
def api_vip_remove(user_id):
    data = request.get_json(silent=True) or {}
    db.remove_vip(user_id)
    if data.get("notify"):
        _telegram_send_message(
            user_id,
            "⚠️ اشتراک VIP سیگنال شما توسط ادمین حذف شد.",
        )
    return jsonify({"ok": True})


@app.route("/api/vip/channel", methods=["GET", "POST"])
@login_required
def api_vip_channel():
    """وضعیت ظرفیت کانال VIP را برمی‌گرداند یا تغییر می‌دهد."""
    if request.method == "GET":
        return jsonify({"open": db.is_vip_channel_open()})
    data = request.get_json(silent=True) or {}
    db.set_vip_channel_open(bool(data.get("open", True)))
    return jsonify({"ok": True, "open": db.is_vip_channel_open()})


# ===================================================================
# تحلیل هفتگی (متن + تصویر)
# ===================================================================

@app.route("/api/analysis", methods=["GET"])
@login_required
def api_analysis_get():
    analyses = db.get_all_analyses()
    return jsonify({"analyses": analyses, "labels": ASSET_LABELS})


@app.route("/api/analysis", methods=["POST"])
@login_required
def api_analysis_post():
    asset = request.form.get("asset")
    analysis_date = (request.form.get("analysis_date") or "").strip()
    text = (request.form.get("text") or "").strip()

    if asset not in ASSET_LABELS:
        return jsonify({"ok": False, "error": "دارایی نامعتبر است."}), 400

    image_path = None
    file = request.files.get("image")
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            ext = ".jpg"
        filename = f"{asset}_{int(time.time())}{ext}"
        file.save(os.path.join(UPLOADS_DIR, filename))
        image_path = f"uploads/analysis/{filename}"

    db.set_analysis(asset, analysis_date, text, image_path)
    return jsonify({"ok": True})


# ===================================================================
# ارسال پیام گروهی (Broadcast) — از طریق Telegram Bot API
# ===================================================================

def _telegram_send_message(chat_id: int, text: str) -> bool:
    if not BOT_TOKEN:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("ok"))
    except Exception:
        return False


def _telegram_create_vip_invite_link(user_id: int) -> str:
    """ساخت یک لینک یک‌بارمصرف برای ورود کاربر به کانال VIP، برای استفاده در فعال‌سازی/تمدید از پنل ادمین.
    اگه ساخت لینک به هر دلیلی شکست بخوره، لینک ثابت (که یک‌بارمصرف نیست) به‌عنوان جایگزین برگردونده می‌شه."""
    if not BOT_TOKEN:
        return VIP_CHANNEL_LINK
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createChatInviteLink"
    payload = json.dumps({
        "chat_id": VIP_CHANNEL_ID,
        "member_limit": 1,
        "name": f"VIP-{user_id}",
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("ok"):
                return body["result"]["invite_link"]
    except Exception:
        pass
    return VIP_CHANNEL_LINK


@app.route("/api/broadcast", methods=["POST"])
@login_required
def api_broadcast():
    data = request.get_json(silent=True) or {}
    target = data.get("target", "all")
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "متن پیام خالی است."}), 400

    users = db.get_all_users()
    vip_ids = {v["user_id"] for v in db.get_all_vip() if v["expire_at"] and v["expire_at"] > time.time()}

    if target == "vip":
        targets = [u for u in users if u["user_id"] in vip_ids]
    elif target == "novip":
        targets = [u for u in users if u["user_id"] not in vip_ids]
    else:
        targets = users

    sent, failed = 0, 0
    for u in targets:
        if _telegram_send_message(u["user_id"], text):
            sent += 1
        else:
            failed += 1

    return jsonify({"ok": True, "total": len(targets), "sent": sent, "failed": failed})


# ===================================================================
# ارسال پیام مستقیم به یک کاربر خاص — از طریق Telegram Bot API
# ===================================================================

@app.route("/api/users/<int:user_id>/send-message", methods=["POST"])
@login_required
def api_send_message_to_user(user_id):
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "متن پیام خالی است."}), 400
    ok = _telegram_send_message(user_id, text)
    if not ok:
        return jsonify({"ok": False, "error": "ارسال پیام ناموفق بود (شاید کاربر بات را بلاک کرده باشد)."}), 400
    return jsonify({"ok": True})


# ===================================================================
# تنظیمات (قیمت و مدت اشتراک VIP)
# ===================================================================

@app.route("/api/settings", methods=["GET"])
@login_required
def api_settings_get():
    return jsonify({
        "vip_price_usdt": db.get_vip_price_usdt(),
        "vip_days": db.get_vip_days(),
        "referral_enabled": db.is_referral_enabled(),
        "referral_required_count": db.get_referral_required_count(),
    })


@app.route("/api/settings", methods=["POST"])
@login_required
def api_settings_post():
    data = request.get_json(silent=True) or {}
    if "vip_price_usdt" in data:
        db.set_setting("vip_price_usdt", float(data["vip_price_usdt"]))
    if "vip_days" in data:
        db.set_setting("vip_days", int(data["vip_days"]))
    if "referral_enabled" in data:
        db.set_referral_enabled(bool(data["referral_enabled"]))
    if "referral_required_count" in data:
        db.set_setting("referral_required_count", int(data["referral_required_count"]))
    return jsonify({"ok": True})


# ===================================================================
# فایل‌های آپلودی (عکس تحلیل) و فایل‌های استاتیک فرانت‌اند React
# ===================================================================

@app.route("/static/uploads/<path:subpath>")
def serve_uploads(subpath):
    return send_from_directory(os.path.join(BASE_DIR, "static", "uploads"), subpath)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """
    Serve کردن خروجی build شده‌ی داشبورد React (minimapa/dist).
    اگر هنوز build نشده باشد (npm run build اجرا نشده)، یک پیام راهنما نشان می‌دهد
    تا مشخص باشد که API به‌درستی بالا آمده و فقط فرانت‌اند build نشده است.
    """
    if not os.path.isdir(FRONTEND_DIST):
        return (
            "<h2 style='font-family:sans-serif'>Money MAP API در حال اجراست ✅</h2>"
            "<p style='font-family:sans-serif'>فرانت‌اند React هنوز build نشده. "
            "داخل پوشه <code>minimapa</code> دستورات زیر را اجرا کن:</p>"
            "<pre>npm install\nnpm run build</pre>"
            "<p style='font-family:sans-serif'>بعد از build، همین سرویس Flask به‌صورت خودکار "
            "فایل‌های پوشه‌ی <code>minimapa/dist</code> را serve می‌کند.</p>",
            200,
        )
    full_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(full_path):
        return send_from_directory(FRONTEND_DIST, path)
    # مسیرهای کلاینت-ساید React Router (مثل /users، /vip، ...) همگی index.html برمی‌گردانند
    return send_from_directory(FRONTEND_DIST, "index.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)