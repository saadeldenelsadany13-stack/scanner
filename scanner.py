"""
ماسح الأزواج - نسخة Bollinger
تعليمي فقط، مش نصيحة مالية ومفيش ضمان ربح. جرّب على Demo.
"""
import numpy as np
import pandas as pd

# ===== إعدادات تقدر تغيّرها =====
INTERVAL = "5m"                 # 1m / 5m / 15m
DURATIONS_MIN = [5, 10]         # مدد الصفقة بالدقايق
PAYOUT = 0.85
MIN_WINRATE = 70.0              # الحد الأدنى لنسبة النجاح (غيّره هنا)
LOOKBACK_HOURS = 4
USE_SESSION = True              # ساعات لندن + نيويورك بس
SESSION_UTC = (7, 20)
MIN_TRAIN_TRADES = 30
MIN_TEST_TRADES = 20
TOP_N = 2
PAIRS = {
    "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X", "USD/CAD": "USDCAD=X", "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X", "EUR/JPY": "EURJPY=X", "GBP/JPY": "GBPJPY=X",
    "EUR/GBP": "EURGBP=X",
}
MAX_PERIOD = {"1m": "7d", "5m": "60d", "15m": "60d"}
MINUTES = {"1m": 1, "5m": 5, "15m": 15}
HIGH_IMPACT = ["nfp", "payroll", "cpi", "inflation", "fomc", "fed ", "rate decision",
               "interest rate", "ecb", "boe", "boj", "gdp", "powell", "lagarde"]
# =================================

BREAKEVEN = 1 / (1 + PAYOUT) * 100
HORIZONS = [d // MINUTES[INTERVAL] for d in DURATIONS_MIN if d >= MINUTES[INTERVAL]]
LOOK = int(LOOKBACK_HOURS * 60 / MINUTES[INTERVAL])


def fetch(symbol):
    import yfinance as yf
    df = yf.download(symbol, interval=INTERVAL, period=MAX_PERIOD[INTERVAL],
                     auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna().iloc[:-1]


def rsi_of(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def variants(df):
    c = df["Close"]
    ma, sd = c.rolling(20).mean(), c.rolling(20).std()
    up_b, lo_b = ma + 2 * sd, ma - 2 * sd
    rev = pd.Series(np.where(c < lo_b, 1, np.where(c > up_b, -1, 0)), index=df.index)
    brk = pd.Series(np.where(c > up_b, 1, np.where(c < lo_b, -1, 0)), index=df.index)
    if USE_SESSION:
        idx = df.index.tz_convert("UTC") if df.index.tz is not None else df.index
        in_sess = pd.Series((idx.hour >= SESSION_UTC[0]) & (idx.hour < SESSION_UTC[1]), index=df.index)
        rev, brk = rev.where(in_sess, 0), brk.where(in_sess, 0)
    return {"Bollinger ارتداد": rev, "Bollinger اختراق": brk}


def win_stats(c, s, h):
    fut = c.shift(-h)
    ok = (s != 0) & fut.notna() & (fut != c)
    if ok.sum() == 0:
        return np.nan, 0
    win = ((s == 1) & (fut > c)) | ((s == -1) & (fut < c))
    return win[ok].mean() * 100, int(ok.sum())


def analyze(name, sym):
    df = fetch(sym)
    c = df["Close"]
    cut = int(len(df) * 0.7)
    vs = variants(df)

    best = None
    for vname, s in vs.items():
        for h in HORIZONS:
            r, n = win_stats(c.iloc[:cut], s.iloc[:cut], h)
            if n >= MIN_TRAIN_TRADES and (best is None or r > best[2]):
                best = (vname, h, r)

    last_c = float(c.iloc[-1])
    out = {"pair": name, "sym": sym, "price": last_c, "signal": "WAIT",
           "rsi": float(rsi_of(c).iloc[-1]),
           "trend4h": float((c.iloc[-1] - c.iloc[-LOOK]) / c.iloc[-LOOK:].std()),
           "pos4h": float((c.iloc[-1] - c.iloc[-LOOK:].min()) /
                          max(c.iloc[-LOOK:].max() - c.iloc[-LOOK:].min(), 1e-12)),
           "chg4h": float((c.iloc[-1] / c.iloc[-LOOK] - 1) * 100),
           "horizon": None, "train": np.nan, "test": np.nan, "test_n": 0, "variant": ""}
    if best:
        vname, h, r = best
        t_rate, t_n = win_stats(c.iloc[cut:], vs[vname].iloc[cut:], h)
        cur = int(vs[vname].iloc[-1])
        out.update(signal={1: "BUY", -1: "SELL", 0: "WAIT"}[cur], horizon=h,
                   train=r, test=t_rate, test_n=t_n, variant=vname)
    return out


def news_check(sym):
    try:
        import yfinance as yf
        items = yf.Ticker(sym).news or []
    except Exception:
        return None
    titles = []
    for it in items:
        t = it.get("title") or (it.get("content") or {}).get("title")
        if t:
            titles.append(t)
    high = [t for t in titles if any(k in t.lower() for k in HIGH_IMPACT)]
    return {"count": len(titles), "high": high[:2]}


def main():
    mins = MINUTES[INTERVAL]
    print(f"الفريم {INTERVAL} | استراتيجية Bollinger | نقطة التعادل {BREAKEVEN:.1f}%")
    print(f"بيفحص {len(PAIRS)} زوج...\n")
    rows = []
    for name, sym in PAIRS.items():
        try:
            rows.append(analyze(name, sym))
        except Exception as e:
            print(f"  تعذّر {name}: {e}")
    rows = [r for r in rows if r["horizon"] and r["test_n"] >= MIN_TEST_TRADES]
    if not rows:
        print("مفيش بيانات أو إشارات كفاية. جرّب وقت السوق مفتوح فيه.")
        return

    rows.sort(key=lambda x: (x["signal"] != "WAIT", x["test"]), reverse=True)
    ar = {"BUY": "صعود 🟢", "SELL": "هبوط 🔴", "WAIT": "انتظار ⚪"}

    for i, r in enumerate(rows[:TOP_N], 1):
        print("=" * 40)
        print(f"#{i}  {r['pair']}   السعر: {r['price']:.5f}")
        print(f"آخر {LOOKBACK_HOURS} ساعات: تغير {r['chg4h']:+.3f}% | RSI {r['rsi']:.0f}")
        print(f"الاستراتيجية: {r['variant']}")
        print(f"التوقع: {ar[r['signal']]}   المدة: {r['horizon'] * mins} دقيقة")
        print(f"نجاح تاريخي: {r['train']:.1f}% (تعلّم) / {r['test']:.1f}% (تحقق على {r['test_n']} صفقة)")
        if r["test"] < BREAKEVEN:
            print(f"⚠️ أقل من نقطة التعادل ({BREAKEVEN:.1f}%): تاريخيًا خاسرة، اعتبرها تدريب.")
        nw = news_check(r["sym"])
        if nw is None:
            print("الأخبار: تعذّر الجلب (راجع التقويم الاقتصادي يدويًا)")
        elif nw["high"]:
            print(f"الأخبار: ⚠️ عناوين مؤثرة → {nw['high'][0][:70]}")
        else:
            print("الأخبار: ما فيش عناوين مؤثرة")
        if r["signal"] == "WAIT":
            print("الحكم: لا توجد إشارة دلوقتي. استنى.")
        elif r["test"] >= MIN_WINRATE:
            print("الحكم: فيه إشارة. ادخل بعد إغلاق الشمعة، وبمبلغ صغير.")
        else:
            print("الحكم: ⛔ أقل من الحد الأدنى للنجاح اللي حددته.")
    print("=" * 40)
    print("تعليمي فقط، مش نصيحة مالية ومفيش ضمان ربح.")


if __name__ == "__main__":
    main()
