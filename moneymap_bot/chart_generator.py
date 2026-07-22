"""
chart_generator.py — چارت کندل‌استیک ۱H
سطوح حمایت/مقاومت از Swing High/Low روی ۳۰ روز داده ۱H
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

# حداقل فاصله سطح از قیمت فعلی (درصد)
MIN_DIST_PCT = {
    "bitcoin": 0.025,  # ۲.۵٪
    "gold":    0.010,  # ۱٪
    "dollar":  0.004,  # ۰.۴٪
}

# ─── رنگ‌های تم (TradingView Dark) ───────────────────────────────────────────
BG      = "#131722"
PANEL   = "#1e222d"
GRID    = "#2a2e39"
TEXT    = "#d1d4dc"
BORDER  = "#363c4e"
UP      = "#26a69a"
DOWN    = "#ef5350"
SUP_CLR = "#00e676"
RES_CLR = "#ff1744"
CUR_CLR = "#ffeb3b"


# ─── پیدا کردن سطوح Swing از داده ۱H (بازه بلندتر) ─────────────────────────

def find_swing_levels(df: pd.DataFrame, cur: float, asset_key: str):
    """
    سطوح حمایت و مقاومت رو از Swing High/Low پیدا می‌کنه.
    df باید ۳۰ روز داده ۱H باشه تا سطوح معنادار و بازتر باشن.

    برمی‌گردونه: (support_level, resistance_level) — هر کدوم float یا None
    """
    from scipy.signal import find_peaks

    highs = df["High"].values
    lows  = df["Low"].values
    n     = len(df)

    min_dist_pct = MIN_DIST_PCT.get(asset_key, 0.01)
    min_dist     = cur * min_dist_pct

    # prominence: حداقل چقدر از اطراف بزرگ‌تر/کوچک‌تر باشه
    price_range  = highs.max() - lows.min()
    prominence   = max(cur * 0.004, price_range * 0.02)

    # ── Swing Highs → مقاومت ──
    # distance=12: حداقل ۱۲ کندل (= ۱۲ ساعت) بین دو سقف
    peaks, _ = find_peaks(highs, distance=12, prominence=prominence)

    res_level  = None
    best_res   = float("inf")
    for idx in peaks:
        lv   = highs[idx]
        dist = lv - cur
        if dist >= min_dist and dist < best_res:
            res_level = lv
            best_res  = dist

    # ── Swing Lows → حمایت ──
    troughs, _ = find_peaks(-lows, distance=12, prominence=prominence)

    sup_level  = None
    best_sup   = float("inf")
    for idx in troughs:
        lv   = lows[idx]
        dist = cur - lv
        if dist >= min_dist and dist < best_sup:
            sup_level = lv
            best_sup  = dist

    # ── Fallback: اگه swing پیدا نشد → از کف/سقف کل بازه استفاده کن ──
    if sup_level is None:
        lv = lows.min()
        if cur - lv >= min_dist:
            sup_level = lv
        else:
            # کف کل دوره حتی اگه نزدیکه
            sup_level = lv

    if res_level is None:
        lv = highs.max()
        if lv - cur >= min_dist:
            res_level = lv
        else:
            res_level = lv

    return sup_level, res_level


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
    ۳۰ روز داده ۱H رو دانلود می‌کنه.
    سطوح Swing از کل ۳۰ روز محاسبه می‌شن (بازتر).
    فقط ۶۰ کندل آخر روی چارت نشون داده می‌شه.
    برمی‌گردونه: (png_bytes, support_level, resistance_level) یا (None, None, None)
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

    # ─── دریافت ۳۰ روز داده ۱H (یه call) ───
    try:
        hist_all = yf.Ticker(cfg["ticker"]).history(period="30d", interval="1h")
        if hist_all.empty or len(hist_all) < 20:
            logger.error(f"No data for {asset_key}")
            return None, None, None
        hist_all.reset_index(inplace=True)
    except Exception as e:
        logger.error(f"yfinance error for {asset_key}: {e}")
        return None, None, None

    cur = float(hist_all["Close"].iloc[-1])

    # ─── سطوح از کل ۳۰ روز ───
    try:
        sup_level, res_level = find_swing_levels(hist_all, cur, asset_key)
    except Exception as e:
        logger.error(f"Swing level error: {e}")
        sup_level, res_level = None, None

    # ─── ۶۰ کندل آخر برای نمایش ───
    hist = hist_all.tail(60).copy()
    hist.reset_index(drop=True, inplace=True)

    n   = len(hist)
    fmt = cfg["price_fmt"]

    # ─── محدوده Y: همیشه سطوح رو شامل بشه ───
    y_min = hist["Low"].min()
    y_max = hist["High"].max()
    if sup_level is not None:
        y_min = min(y_min, sup_level)
    if res_level is not None:
        y_max = max(y_max, res_level)
    pad   = (y_max - y_min) * 0.06

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

    # ─── خط حمایت ───
    if sup_level is not None:
        band = max(cur * 0.001, (y_max - y_min) * 0.003)
        ax.axhspan(sup_level - band, sup_level + band, color=SUP_CLR, alpha=0.18, zorder=1)
        ax.axhline(sup_level, color=SUP_CLR, lw=1.8, ls="--", alpha=0.95, zorder=4)
        ax.text(n + 0.8, sup_level,
                f" 🟢 Support\n {sup_level:{fmt}}",
                color=SUP_CLR, fontsize=8.5, va="center",
                fontweight="bold", clip_on=False, linespacing=1.5)

    # ─── خط مقاومت ───
    if res_level is not None:
        band = max(cur * 0.001, (y_max - y_min) * 0.003)
        ax.axhspan(res_level - band, res_level + band, color=RES_CLR, alpha=0.18, zorder=1)
        ax.axhline(res_level, color=RES_CLR, lw=1.8, ls="--", alpha=0.95, zorder=4)
        ax.text(n + 0.8, res_level,
                f" 🔴 Resistance\n {res_level:{fmt}}",
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
    ax.set_ylim(y_min - pad, y_max + pad)

    # محور Y (قیمت)
    ax.yaxis.tick_right()
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:{fmt}}"))
    ax.tick_params(axis="y", colors=TEXT, labelsize=7.5,
                   right=True, labelright=True, left=False, labelleft=False)
    axv.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}K"
    ))

    # ─── عنوان ───
    fig.text(0.013, 0.978, cfg["label"], color=TEXT,
             fontsize=13, fontweight="bold", va="top")
    fig.text(0.013, 0.945, f"Price: {cur:{fmt}}",
             color=CUR_CLR, fontsize=10.5, va="top", fontweight="bold")

    info_parts = []
    if sup_level is not None:
        info_parts.append(f"Support: {sup_level:{fmt}}")
    if res_level is not None:
        info_parts.append(f"Resistance: {res_level:{fmt}}")
    if info_parts:
        fig.text(0.013, 0.912, "  ·  ".join(info_parts),
                 color=TEXT, fontsize=9, va="top")

    legend = [
        mpatches.Patch(color=SUP_CLR, label="Support  (30D Swing Low)"),
        mpatches.Patch(color=RES_CLR, label="Resistance  (30D Swing High)"),
        mpatches.Patch(color=CUR_CLR, label="Current Price"),
        mpatches.Patch(color=UP,      label="Bullish candle"),
        mpatches.Patch(color=DOWN,    label="Bearish candle"),
    ]
    ax.legend(handles=legend, loc="upper left",
              facecolor=PANEL, edgecolor=BORDER,
              labelcolor=TEXT, fontsize=8.5, framealpha=0.92)

    fig.text(0.99, 0.008, "MoneyMap Bot  ·  30D Swing High/Low",
             color="#3a3f52", fontsize=7.5, ha="right", va="bottom", style="italic")

    # ─── ذخیره ───
    plt.tight_layout(rect=[0, 0, 0.90, 1])
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150,
                bbox_inches="tight", facecolor=BG, edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), sup_level, res_level


async def generate_chart_bytes_async(asset_key: str):
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_chart_bytes, asset_key)