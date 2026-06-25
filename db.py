# -*- coding: utf-8 -*-
"""
ماژول دیتابیس مشترک بین بات تلگرام و پنل ادمین.
از SQLite استفاده می‌کند تا دیتای کاربران، اعضای VIP و متن تحلیل‌ها
بعد از ری‌استارت شدن بات (مثلاً روی Railway) از بین نرود.
"""

import sqlite3
import time
import os
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                asset TEXT PRIMARY KEY,
                analysis_date TEXT,
                text TEXT,
                updated_at REAL
            )
            """
        )
        # مقداردهی اولیه تحلیل‌ها در صورت خالی بودن جدول
        existing = conn.execute("SELECT asset FROM analyses").fetchall()
        existing_assets = {row["asset"] for row in existing}
        for asset, data in DEFAULT_ANALYSES.items():
            if asset not in existing_assets:
                conn.execute(
                    "INSERT INTO analyses (asset, analysis_date, text, updated_at) VALUES (?, ?, ?, ?)",
                    (asset, "", data["text"], time.time()),
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


# ---------- VIP ----------

def set_vip(user_id: int, expire_at: float):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO vip_members (user_id, expire_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET expire_at = excluded.expire_at
            """,
            (user_id, expire_at),
        )


def get_vip_expiry(user_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT expire_at FROM vip_members WHERE user_id = ?", (user_id,)).fetchone()
        return row["expire_at"] if row else None


def get_all_vip():
    """لیست همه اعضای VIP همراه با اطلاعات کاربر (اسم/شماره) - مرتب بر اساس نزدیک‌ترین انقضا"""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT v.user_id, v.expire_at, u.name, u.phone, u.username
            FROM vip_members v
            LEFT JOIN users u ON u.user_id = v.user_id
            ORDER BY v.expire_at ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


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


def set_analysis(asset: str, analysis_date: str, text: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO analyses (asset, analysis_date, text, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(asset) DO UPDATE SET
                analysis_date = excluded.analysis_date,
                text = excluded.text,
                updated_at = excluded.updated_at
            """,
            (asset, analysis_date, text, time.time()),
        )


# هنگام import شدن، مطمئن شو جدول‌ها ساخته شده‌اند
init_db()
