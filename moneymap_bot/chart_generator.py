"""
chart_generator.py — چارت کندل‌استیک ۲H (resample از ۱H)
سطوح حمایت/مقاومت از Swing High/Low روی ۲۰ روز — محدوده معقول
"""
import io
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── تنظیمات دارایی‌ها ────────────────────────────────────────────────────────
ASSET_CONFIG = {
    "gold":    {"ticker": "GC=F",      "label": "XAU/USD · Gold · 2H",    "price_fmt": ",.1f"},
    "bitcoin": {"ticker": "BTC-USD",   "label": "BTC/USD · Bitcoin · 2H", "price_fmt": ",.0f"},
    "dollar":  {"ticker": "DX-Y.NYB",  "label": "DXY · Dollar Index · 2H","price_fmt": ",.3f"},
}

# حداقل و حداکثر فاصله سطح از قیمت (درصد)
LEVEL_DIST = {
    "bitcoin": {"min": 0.012, "max": 0.055},  # ۱.۲٪ تا ۵.۵٪
    "gold":    {"min": 0.005, "max": 0.025},  # ۰.۵٪ تا ۲.۵٪
    "dollar":  {"min": 0.002, "max": 0.012},  # ۰.۲٪ تا ۱.۲٪
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


# ─── resample 1H → 2H ────────────────────────────────────────────────────────

def _resample_2h(df: pd.DataFrame) -> pd.DataFrame:
    """تبدیل داده ۱H به ۲H با pandas resample."""
    df = df.copy()
    # ستون زمان رو index کن
    time_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.set_index(time_col)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    resampled = df.resample("2h").agg({
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }).dropna(subset=["Open", "Close"])
    resampled = resampled.reset_index()
    resampled.rename(columns={resampled.columns[0]: "Datetime"}, inplace=True)
    return resampled


# ─── پیدا کردن سطوح Swing با محدوده فاصله ───────────────────────────────────

def find_swing_levels(df: pd.DataFrame, cur: float, asset_key: str):
    """
    سطوح حمایت و مقاومت از Swing High/Low.
    هر دو حداقل و حداکثر فاصله از قیمت فعلی رعایت می‌شن.

    برمی‌گردونه: (support_level, resistance_level) هر کدوم float یا None
    """
    from scipy.signal import find_peaks

    dist_cfg  = LEVEL_DIST.get(asset_key, {"min": 0.01, "max": 0.05})
    min_dist  = cur * dist_cfg["min"]
    max_dist  = cur * dist_cfg["max"]

    highs = df["High"].values
    lows  = df["Low"].values

    # prominence: حداقل ۰.۳٪ حرکت برای تشخیص swing — نه خیلی سخت
    prominence = cur * 0.003

    # ── Swing Highs → مقاومت ──
    # distance=2: حداقل ۲ کندل ۲H (= ۴ ساعت) فاصله بین دو سقف
    peaks, _ = find_peaks(highs, distance=2, prominence=prominence)

    res_level = None
    best_res  = float("inf")
    for idx in peaks:
        lv   = highs[idx]
        dist = lv - cur
        if min_dist <= dist <= max_dist and dist < best_res:
            res_level = lv
            best_res  = dist

    # اگه در محدوده max_dist پیدا نشد، نزدیک‌ترین بالای min_dist رو بگیر
    if res_level is None:
        for idx in peaks:
            lv   = highs[idx]
            dist = lv - cur
            if dist >= min_dist and dist < best_res:
                res_level = lv
                best_res  = dist

    # ── Swing Lows → حمایت ──
    troughs, _ = find_peaks(-lows, distance=2, prominence=prominence)

    sup_level = None
    best_sup  = float("inf")
    for idx in troughs:
        lv   = lows[idx]
        dist = cur - lv
        if min_dist <= dist <= max_dist and dist < best_sup:
            sup_level = lv
            best_sup  = dist

    if sup_level is None:
        for idx in troughs:
            lv   = lows[idx]
            dist = cur - lv
            if dist >= min_dist and dist < best_sup:
                sup_level = lv
                best_sup  = dist

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
    ۲۰ روز داده ۱H رو دانلود و به ۲H تبدیل می‌کنه.
    سطوح Swing از کل ۲۰ روز، نمایش ۶۰ کندل آخر (= ۵ روز ۲H).
    برمی‌گردونه: (png_bytes, support_level, resistance_level)
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

    # ─── دانلود ۲۰ روز ۱H ───
    try:
        raw = yf.Ticker(cfg["ticker"]).history(period="20d", interval="1h")
        if raw.empty or len(raw) < 20:
            logger.error(f"No data for {asset_key}")
            return None, None, None
        raw.reset_index(inplace=True)
    except Exception as e:
        logger.error(f"yfinance error for {asset_key}: {e}")
        return None, None, None

    # ─── resample به ۲H ───
    try:
        hist_all = _resample_2h(raw)
    except Exception as e:
        logger.error(f"Resample error: {e}")
        return None, None, None

    if len(hist_all) < 10:
        return None, None, None

    cur = float(hist_all["Close"].iloc[-1])

    # ─── سطوح از کل ۲۰ روز ───
    try:
        sup_level, res_level = find_swing_levels(hist_all, cur, asset_key)
    except Exception as e:
        logger.error(f"Swing level error: {e}")
        sup_level, res_level = None, None

    # ─── ۶۰ کندل آخر برای نمایش (≈ ۵ روز روی ۲H) ───
    hist = hist_all.tail(60).copy()
    hist.reset_index(drop=True, inplace=True)

    n   = len(hist)
    fmt = cfg["price_fmt"]

    # ─── محدوده Y: سطوح رو شامل بشه ───
    y_min = hist["Low"].min()
    y_max = hist["High"].max()
    if sup_level is not None:
        y_min = min(y_min, sup_level)
    if res_level is not None:
        y_max = max(y_max, res_level)
    pad = (y_max - y_min) * 0.06

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

    # ─── محور X ───
    step = max(1, n // 10)
    tks  = list(range(0, n, step))
    ax.set_xticks(tks)
    ax.set_xticklabels([])
    axv.set_xticks(tks)
    axv.set_xticklabels(
        [pd.to_datetime(hist["Datetime"].iloc[i]).strftime("%m/%d  %H:%M") for i in tks],
        color=TEXT, fontsize=7, rotation=15, ha="right",
    )

    ax.set_xlim(-1, n + 14)
    ax.set_ylim(y_min - pad, y_max + pad)

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

    import matplotlib.patches as mp2
    legend = [
        mp2.Patch(color=SUP_CLR, label="Support  (20D Swing Low)"),
        mp2.Patch(color=RES_CLR, label="Resistance  (20D Swing High)"),
        mp2.Patch(color=CUR_CLR, label="Current Price"),
        mp2.Patch(color=UP,      label="Bullish candle"),
        mp2.Patch(color=DOWN,    label="Bearish candle"),
    ]
    ax.legend(handles=legend, loc="upper left",
              facecolor=PANEL, edgecolor=BORDER,
              labelcolor=TEXT, fontsize=8.5, framealpha=0.92)

    fig.text(0.99, 0.008, "MoneyMap Bot  ·  2H · 20D Swing",
             color="#3a3f52", fontsize=7.5, ha="right", va="bottom", style="italic")

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