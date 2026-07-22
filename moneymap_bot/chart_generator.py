"""
chart_generator.py — چارت کندل‌استیک ۱H با سطوح حمایت/مقاومت از Daily Swing High/Low
"""
import io
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── تنظیمات دارایی‌ها ────────────────────────────────────────────────────────
ASSET_CONFIG = {
    "gold":    {"ticker": "GC=F",      "label": "XAU/USD · Gold · 1H",    "price_fmt": ",.1f"},
    "bitcoin": {"ticker": "BTC-USD",   "label": "BTC/USD · Bitcoin · 1H", "price_fmt": ",.0f"},
    "dollar":  {"ticker": "DX-Y.NYB",  "label": "DXY · Dollar Index · 1H","price_fmt": ",.3f"},
}

# حداقل فاصله سطح از قیمت فعلی (درصد) — برای فیلتر سطوح خیلی نزدیک
MIN_DIST_PCT = {
    "bitcoin": 0.02,   # ۲٪ برای بیتکوین (نوسان بالا)
    "gold":    0.008,  # ۰.۸٪ برای طلا
    "dollar":  0.003,  # ۰.۳٪ برای دلار ایندکس
}

# ─── رنگ‌های تم (TradingView Dark) ───────────────────────────────────────────
BG      = "#131722"
PANEL   = "#1e222d"
GRID    = "#2a2e39"
TEXT    = "#d1d4dc"
BORDER  = "#363c4e"
UP      = "#26a69a"
DOWN    = "#ef5350"
SUP_CLR = "#00e676"   # سبز حمایت
RES_CLR = "#ff1744"   # قرمز مقاومت
CUR_CLR = "#ffeb3b"   # زرد قیمت فعلی


# ─── پیدا کردن سطوح کلیدی از Daily Swing High/Low ───────────────────────────

def find_key_levels(ticker: str, cur: float, asset_key: str) -> tuple:
    """
    سطوح حمایت و مقاومت رو از داده‌های Daily (۹۰ روز) پیدا می‌کنه.
    از Swing High/Low با حداقل فاصله معنادار از قیمت فعلی استفاده می‌کنه.

    برمی‌گردونه: (support_dict, resistance_dict)
    هر dict داره: {"level": float, "low": float, "high": float}
    """
    import yfinance as yf
    from scipy.signal import find_peaks

    min_dist_pct = MIN_DIST_PCT.get(asset_key, 0.01)
    min_dist = cur * min_dist_pct

    try:
        daily = yf.Ticker(ticker).history(period="90d", interval="1d")
        if daily.empty or len(daily) < 10:
            return None, None
    except Exception:
        return None, None

    highs = daily["High"].values
    lows  = daily["Low"].values
    n     = len(daily)

    # ── Swing Highs (مقاومت) ──
    # پیک‌هایی که از هر دو طرف بالاترند (حداقل ۳ روز فاصله)
    prominence_thresh = (highs.max() - lows.min()) * 0.008
    peaks, props = find_peaks(highs, distance=3, prominence=prominence_thresh)

    resistance = None
    best_res_dist = float("inf")
    for idx in peaks:
        level = highs[idx]
        dist = level - cur
        if dist >= min_dist and dist < best_res_dist:
            # ناحیه: از low کندل تا high کندل
            body_lo = min(daily["Open"].iloc[idx], daily["Close"].iloc[idx])
            resistance = {
                "level": level,
                "low":   body_lo,
                "high":  level,
                "dist":  dist,
            }
            best_res_dist = dist

    # ── Swing Lows (حمایت) ──
    troughs, _ = find_peaks(-lows, distance=3, prominence=prominence_thresh)

    support = None
    best_sup_dist = float("inf")
    for idx in troughs:
        level = lows[idx]
        dist = cur - level
        if dist >= min_dist and dist < best_sup_dist:
            body_hi = max(daily["Open"].iloc[idx], daily["Close"].iloc[idx])
            support = {
                "level": level,
                "low":   level,
                "high":  body_hi,
                "dist":  dist,
            }
            best_sup_dist = dist

    # ── Fallback: اگه هیچ swing پیدا نشد، از کف/سقف ۹۰ روزه استفاده کن ──
    if support is None:
        level = lows.min()
        if cur - level >= min_dist:
            support = {"level": level, "low": level, "high": level * 1.001, "dist": cur - level}

    if resistance is None:
        level = highs.max()
        if level - cur >= min_dist:
            resistance = {"level": level, "low": level * 0.999, "high": level, "dist": level - cur}

    return support, resistance


# ─── رسم کندل‌استیک ──────────────────────────────────────────────────────────

def _draw_candles(ax, df):
    import matplotlib.patches as mpatches
    for i, (_, r) in enumerate(df.iterrows()):
        o, h, l, c = r["Open"], r["High"], r["Low"], r["Close"]
        clr = UP if c >= o else DOWN
        ax.plot([i, i], [l, h], color=clr, lw=0.7, zorder=2)
        bh = max(abs(c - o), (h - l) * 0.005)
        ax.add_patch(mpatches.Rectangle(
            (i - 0.32, min(o, c)), 0.64, bh,
            fc=clr, ec=clr, lw=0, zorder=3
        ))


# ─── تابع اصلی تولید چارت ────────────────────────────────────────────────────

def generate_chart_bytes(asset_key: str):
    """
    داده ۱H رو از yfinance می‌گیره، OB حمایت و مقاومت رو حساب می‌کنه،
    و یه tuple (png_bytes, support_mid, resistance_mid) برمی‌گردونه.
    در صورت خطا None برمی‌گردونه.
    """
    import yfinance as yf
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import matplotlib.patches as mpatches

    cfg = ASSET_CONFIG.get(asset_key)
    if not cfg:
        return None, None, None

    # ─── دریافت داده ۱H برای چارت ───
    try:
        hist = yf.Ticker(cfg["ticker"]).history(period="5d", interval="1h")
        if hist.empty:
            logger.error(f"No data for {asset_key}")
            return None, None, None
        hist = hist.tail(80).copy()
        hist.reset_index(inplace=True)
    except Exception as e:
        logger.error(f"yfinance error for {asset_key}: {e}")
        return None, None, None

    cur_price = hist["Close"].iloc[-1]

    # ─── سطوح از Daily Swing High/Low ───
    try:
        support, resistance = find_key_levels(cfg["ticker"], cur_price, asset_key)
    except Exception as e:
        logger.error(f"Key level detection error: {e}")
        support, resistance = None, None

    # ─── میانه‌ی ناحیه‌ها (برای پاس دادن به caption) ───
    sup_mid = support["level"] if support else None
    res_mid = resistance["level"] if resistance else None

    n      = len(hist)
    cur    = cur_price
    fmt    = cfg["price_fmt"]
    p_min  = hist["Low"].min()
    p_max  = hist["High"].max()
    pad    = (p_max - p_min) * 0.08

    # ─── Figure ───
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    gs  = fig.add_gridspec(5, 1, hspace=0)
    ax  = fig.add_subplot(gs[:4, 0])
    axv = fig.add_subplot(gs[4, 0], sharex=ax)

    for x in [ax, axv]:
        x.set_facecolor(PANEL)
        x.tick_params(colors=TEXT, labelsize=8)
        for sp in x.spines.values():
            sp.set_color(BORDER)
        x.grid(color=GRID, lw=0.45, ls="-", alpha=0.7)

    # ─── کندل‌ها ───
    _draw_candles(ax, hist)

    # ─── ولوم ───
    for i, (_, r) in enumerate(hist.iterrows()):
        axv.bar(i, r["Volume"], color=(UP if r["Close"] >= r["Open"] else DOWN),
                alpha=0.4, width=0.6)

    # ─── خط حمایت (Daily Swing Low) ───
    if support:
        s_lv = support["level"]
        band = max(cur * 0.002, (p_max - p_min) * 0.004)   # باند نمایشی
        ax.axhspan(s_lv - band, s_lv + band, color=SUP_CLR, alpha=0.18, zorder=1)
        ax.axhline(s_lv, color=SUP_CLR, lw=1.8, ls="--", alpha=0.95, zorder=4)
        ax.text(n + 0.8, s_lv,
                f" 🟢 Support\n {s_lv:{fmt}}",
                color=SUP_CLR, fontsize=8.5, va="center",
                fontweight="bold", clip_on=False, linespacing=1.5)

    # ─── خط مقاومت (Daily Swing High) ───
    if resistance:
        r_lv = resistance["level"]
        band = max(cur * 0.002, (p_max - p_min) * 0.004)
        ax.axhspan(r_lv - band, r_lv + band, color=RES_CLR, alpha=0.18, zorder=1)
        ax.axhline(r_lv, color=RES_CLR, lw=1.8, ls="--", alpha=0.95, zorder=4)
        ax.text(n + 0.8, r_lv,
                f" 🔴 Resistance\n {r_lv:{fmt}}",
                color=RES_CLR, fontsize=8.5, va="center",
                fontweight="bold", clip_on=False, linespacing=1.5)

    # ─── قیمت فعلی ───
    ax.axhline(cur, color=CUR_CLR, lw=1.1, ls="-", alpha=0.95, zorder=5)
    ax.text(n + 0.8, cur, f" ▶ {cur:{fmt}}",
            color=CUR_CLR, fontsize=9, va="center",
            fontweight="bold", clip_on=False)

    # ─── محور X (تاریخ) ───
    step = max(1, n // 10)
    tks  = list(range(0, n, step))
    time_col = "Datetime" if "Datetime" in hist.columns else hist.columns[0]
    ax.set_xticks(tks)
    ax.set_xticklabels([])
    axv.set_xticks(tks)
    axv.set_xticklabels(
        [pd.to_datetime(hist[time_col].iloc[i]).strftime("%m/%d  %H:%M") for i in tks],
        color=TEXT, fontsize=7, rotation=15, ha="right",
    )

    ax.set_xlim(-1, n + 14)
    ax.set_ylim(p_min - pad, p_max + pad)

    # محور Y (قیمت)
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v:{fmt}}"
    ))
    ax.tick_params(axis="y", colors=TEXT, labelsize=7.5,
                   right=True, labelright=True, left=False, labelleft=False)

    axv.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}K"
    ))

    # ─── عنوان و راهنما ───
    fig.text(0.013, 0.978, cfg["label"], color=TEXT,
             fontsize=13, fontweight="bold", va="top")
    fig.text(0.013, 0.945, f"Price: {cur:{fmt}}",
             color=CUR_CLR, fontsize=10.5, va="top", fontweight="bold")

    # ICT info
    info_parts = []
    if support:
        info_parts.append(f"Support: {support['level']:{fmt}}")
    if resistance:
        info_parts.append(f"Resistance: {resistance['level']:{fmt}}")
    if info_parts:
        fig.text(0.013, 0.912, "  ·  ".join(info_parts),
                 color=TEXT, fontsize=9, va="top")

    legend = [
        mpatches.Patch(color=SUP_CLR, label="Support — Daily Swing Low"),
        mpatches.Patch(color=RES_CLR, label="Resistance — Daily Swing High"),
        mpatches.Patch(color=CUR_CLR, label="Current Price"),
        mpatches.Patch(color=UP,      label="Bullish candle"),
        mpatches.Patch(color=DOWN,    label="Bearish candle"),
    ]
    ax.legend(handles=legend, loc="upper left",
              facecolor=PANEL, edgecolor=BORDER,
              labelcolor=TEXT, fontsize=8.5, framealpha=0.92)

    fig.text(0.99, 0.008, "MoneyMap Bot  ·  Daily Swing High/Low",
             color="#3a3f52", fontsize=7.5, ha="right", va="bottom", style="italic")

    # ─── ذخیره در حافظه ───
    plt.tight_layout(rect=[0, 0, 0.90, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150,
                bbox_inches="tight", facecolor=BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), sup_mid, res_mid


async def generate_chart_bytes_async(asset_key: str):
    """
    نسخه async از generate_chart_bytes — برای استفاده در telegram_bot.
    برمی‌گردونه: (png_bytes, support_mid, resistance_mid) یا (None, None, None)
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_chart_bytes, asset_key)