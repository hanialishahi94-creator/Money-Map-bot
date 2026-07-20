"""
chart_generator.py — چارت کندل‌استیک ۱H با یک ناحیه حمایت + یک ناحیه مقاومت
سبک ICT/LIT (Order Block Detection)
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


# ─── الگوریتم ICT Order Block ────────────────────────────────────────────────

def find_ict_order_blocks(df: pd.DataFrame):
    """
    پیدا کردن یک Bullish OB (حمایت) و یک Bearish OB (مقاومت) بر اساس سبک ICT.

    Bullish OB = آخرین کندل نزولی قبل از یک حرکت صعودی قوی → ناحیه حمایت
    Bearish OB = آخرین کندل صعودی قبل از یک حرکت نزولی قوی → ناحیه مقاومت

    هر OB که هنوز Mitigate نشده (قیمت کاملاً ازش رد نشده) اولویت داره.
    """
    opens  = df["Open"].values
    closes = df["Close"].values
    highs  = df["High"].values
    lows   = df["Low"].values
    n      = len(df)
    cur    = closes[-1]

    # حداقل درصد حرکت بعدی که یک OB رو تأیید می‌کنه
    move_thresh = 0.004   # 0.4% برای BTC/Gold/DXY تناسب داره

    candidates_bull = []   # OB‌های صعودی (حمایت) — زیر قیمت فعلی
    candidates_bear = []   # OB‌های نزولی (مقاومت) — بالای قیمت فعلی

    for i in range(2, n - 4):
        # ─── حرکت قوی بعدی (در ۳ کندل آینده) ───
        move = (closes[i + 3] - closes[i]) / closes[i]

        # ── Bullish OB ──
        # کندل i نزولی باشه (close < open)
        # حرکت بعدی به بالا باشه (move > thresh)
        if closes[i] < opens[i] and move > move_thresh:
            ob_low  = min(opens[i], closes[i])
            ob_high = max(opens[i], closes[i])

            # OB باید زیر قیمت فعلی باشه (ناحیه حمایت)
            if ob_high < cur:
                # بررسی unmitigated: قیمت بعداً از OB رد نشده باشه
                future_low = lows[i + 1: min(i + 30, n)].min() if i + 1 < n else ob_low
                is_fresh = future_low >= ob_low * 0.997   # در tolerance ۰.۳٪

                candidates_bull.append({
                    "low":    ob_low,
                    "high":   ob_high,
                    "idx":    i,
                    "fresh":  is_fresh,
                    "dist":   cur - ob_high,
                })

        # ── Bearish OB ──
        # کندل i صعودی باشه (close > open)
        # حرکت بعدی به پایین باشه (move < -thresh)
        if closes[i] > opens[i] and move < -move_thresh:
            ob_low  = min(opens[i], closes[i])
            ob_high = max(opens[i], closes[i])

            # OB باید بالای قیمت فعلی باشه (ناحیه مقاومت)
            if ob_low > cur:
                # بررسی unmitigated
                future_high = highs[i + 1: min(i + 30, n)].max() if i + 1 < n else ob_high
                is_fresh = future_high <= ob_high * 1.003

                candidates_bear.append({
                    "low":    ob_low,
                    "high":   ob_high,
                    "idx":    i,
                    "fresh":  is_fresh,
                    "dist":   ob_low - cur,
                })

    # ── انتخاب بهترین OB برای هر طرف ──
    # اولویت: fresh (unmitigated) و نزدیک‌ترین به قیمت فعلی
    def best_ob(candidates):
        if not candidates:
            return None
        fresh = [c for c in candidates if c["fresh"]]
        pool  = fresh if fresh else candidates
        return min(pool, key=lambda c: c["dist"])

    support    = best_ob(candidates_bull)
    resistance = best_ob(candidates_bear)

    # ── Fallback: اگه OB پیدا نشد از swing low/high استفاده کن ──
    if support is None:
        from scipy.signal import find_peaks
        troughs, _ = find_peaks(-lows, distance=5,
                                 prominence=(highs.max() - lows.min()) * 0.002)
        below = [(i, lows[i]) for i in troughs if lows[i] < cur]
        if below:
            idx, lv = max(below, key=lambda x: x[0])
            support = {
                "low":  lv,
                "high": max(opens[idx], closes[idx]),
                "idx":  idx,
                "fresh": True,
                "dist": cur - lv,
            }

    if resistance is None:
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(highs, distance=5,
                               prominence=(highs.max() - lows.min()) * 0.002)
        above = [(i, highs[i]) for i in peaks if highs[i] > cur]
        if above:
            idx, lv = max(above, key=lambda x: x[0])
            resistance = {
                "low":  min(opens[idx], closes[idx]),
                "high": lv,
                "idx":  idx,
                "fresh": True,
                "dist": lv - cur,
            }

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

    # ─── دریافت داده ───
    try:
        hist = yf.Ticker(cfg["ticker"]).history(period="30d", interval="1h")
        if hist.empty:
            logger.error(f"No data for {asset_key}")
            return None, None, None
        hist = hist.tail(120).copy()
        hist.reset_index(inplace=True)
    except Exception as e:
        logger.error(f"yfinance error for {asset_key}: {e}")
        return None, None, None

    # ─── محاسبه OB ───
    try:
        support, resistance = find_ict_order_blocks(hist)
    except Exception as e:
        logger.error(f"OB detection error: {e}")
        support, resistance = None, None

    # ─── میانه‌ی ناحیه‌ها (برای پاس دادن به AI) ───
    sup_mid = (support["low"] + support["high"]) / 2 if support else None
    res_mid = (resistance["low"] + resistance["high"]) / 2 if resistance else None

    n      = len(hist)
    cur    = hist["Close"].iloc[-1]
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

    # ─── ناحیه حمایت (Bullish OB) ───
    if support:
        z_lo, z_hi = support["low"], support["high"]
        # محدوده zone رو کمی گشاد کن که بهتر دیده بشه
        gap = max((z_hi - z_lo) * 0.2, (p_max - p_min) * 0.003)
        ax.axhspan(z_lo - gap * 0.5, z_hi + gap * 0.5,
                   color=SUP_CLR, alpha=0.15, zorder=1)
        ax.axhline(z_lo - gap * 0.5, color=SUP_CLR, lw=1.5, ls="--", alpha=0.9, zorder=4)
        ax.axhline(z_hi + gap * 0.5, color=SUP_CLR, lw=1.5, ls="--", alpha=0.9, zorder=4)

        # نقطه OB روی چارت
        ax.axvline(support["idx"], color=SUP_CLR, lw=0.5, ls=":", alpha=0.4, zorder=1)

        mid_sup = (z_lo + z_hi) / 2
        ax.text(n + 0.8, mid_sup,
                f" 🟢 Support OB\n {mid_sup:{fmt}}",
                color=SUP_CLR, fontsize=8.5, va="center",
                fontweight="bold", clip_on=False, linespacing=1.5)

    # ─── ناحیه مقاومت (Bearish OB) ───
    if resistance:
        z_lo, z_hi = resistance["low"], resistance["high"]
        gap = max((z_hi - z_lo) * 0.2, (p_max - p_min) * 0.003)
        ax.axhspan(z_lo - gap * 0.5, z_hi + gap * 0.5,
                   color=RES_CLR, alpha=0.15, zorder=1)
        ax.axhline(z_lo - gap * 0.5, color=RES_CLR, lw=1.5, ls="--", alpha=0.9, zorder=4)
        ax.axhline(z_hi + gap * 0.5, color=RES_CLR, lw=1.5, ls="--", alpha=0.9, zorder=4)

        ax.axvline(resistance["idx"], color=RES_CLR, lw=0.5, ls=":", alpha=0.4, zorder=1)

        mid_res = (z_lo + z_hi) / 2
        ax.text(n + 0.8, mid_res,
                f" 🔴 Resist OB\n {mid_res:{fmt}}",
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
        m = (support["low"] + support["high"]) / 2
        info_parts.append(f"Support OB: {m:{fmt}}")
    if resistance:
        m = (resistance["low"] + resistance["high"]) / 2
        info_parts.append(f"Resist OB: {m:{fmt}}")
    if info_parts:
        fig.text(0.013, 0.912, "  ·  ".join(info_parts),
                 color=TEXT, fontsize=9, va="top")

    legend = [
        mpatches.Patch(color=SUP_CLR, label="Bullish OB — Support"),
        mpatches.Patch(color=RES_CLR, label="Bearish OB — Resistance"),
        mpatches.Patch(color=CUR_CLR, label="Current Price"),
        mpatches.Patch(color=UP,      label="Bullish candle"),
        mpatches.Patch(color=DOWN,    label="Bearish candle"),
    ]
    ax.legend(handles=legend, loc="upper left",
              facecolor=PANEL, edgecolor=BORDER,
              labelcolor=TEXT, fontsize=8.5, framealpha=0.92)

    fig.text(0.99, 0.008, "MoneyMap Bot  ·  ICT/LIT Order Block",
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