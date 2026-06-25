# -*- coding: utf-8 -*-
"""
پنل ادمین وب برای بات تلگرام مانی‌مپ.
نمایش لیست کاربران، اعضای VIP با زمان باقی‌مانده، و فرم آپلود/ویرایش تحلیل هفتگی.
"""

import os
import time
import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash

import db

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "moneymap-secret-key-change-me")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "09124900216")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Saba09124900216")

ASSET_LABELS = {
    "gold": "🥇 طلا",
    "dollar": "💵 دلار",
    "bitcoin": "₿ بیتکوین",
}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("نام کاربری یا رمز عبور اشتباه است.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    users = db.get_all_users()
    vip_list = db.get_all_vip()
    now = time.time()
    active_vip = [v for v in vip_list if v["expire_at"] and v["expire_at"] > now]
    return render_template(
        "dashboard.html",
        users_count=len(users),
        vip_count=len(active_vip),
    )


@app.route("/users")
@login_required
def users_list():
    users = db.get_all_users()
    vip_list = {v["user_id"]: v for v in db.get_all_vip()}
    now = time.time()
    rows = []
    for u in users:
        vip = vip_list.get(u["user_id"])
        is_vip_active = bool(vip and vip["expire_at"] and vip["expire_at"] > now)
        rows.append({**u, "is_vip": is_vip_active})
    return render_template("users.html", users=rows)


@app.route("/vip")
@login_required
def vip_list_view():
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
    # فعال‌ها اول، بعد منقضی‌شده‌ها
    rows.sort(key=lambda r: (not r["is_active"], -(r["expire_at"] or 0)))
    return render_template("vip.html", vip_members=rows)


@app.route("/analysis", methods=["GET", "POST"])
@login_required
def analysis():
    if request.method == "POST":
        asset = request.form.get("asset")
        analysis_date = request.form.get("analysis_date", "").strip()
        text = request.form.get("text", "").strip()
        if asset in ASSET_LABELS:
            db.set_analysis(asset, analysis_date, text)
            flash(f"تحلیل {ASSET_LABELS[asset]} با موفقیت ذخیره شد.")
        return redirect(url_for("analysis"))

    analyses = db.get_all_analyses()
    return render_template("analysis.html", analyses=analyses, labels=ASSET_LABELS)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
