#!/usr/bin/env python3
"""
IFR PRO — Backtest ve Parametre Optimizasyonu
==============================================
ifr_master_pro.pine dosyasindaki stratejinin birebir Python karsiligi.
Gercek BTC/USD verisini indirir, parametre taramasi yapar ve sonuclari
walk-forward (ileriye dogru) dogrulamadan gecirir.

KULLANIM
--------
    pip install numpy pandas requests
    python3 ifr_backtest.py                      # BTCUSDT 4h, son 4 yil
    python3 ifr_backtest.py --interval 1h --years 3
    python3 ifr_backtest.py --csv veri.csv       # kendi verinizle
    python3 ifr_backtest.py --quick              # kucuk grid, hizli deneme

CSV formati: time,open,high,low,close,volume  (time = ISO tarih veya ms epoch)

NEDEN WALK-FORWARD?
-------------------
Tum gecmise bakip en yuksek getiriyi veren ayari secmek egri uydurmadir
(curve fitting); o ayar gelecekte cogunlukla cokerler. Bu script iki sonuc
birden verir:
  1) "Tum gecmiste en iyi"  -> vitrin rakami, guvenmeyin
  2) "Walk-forward sampiyon" -> her donemde gorulmemis veride test edilmis,
     gercekte kullanilmasi gereken ayar budur.
"""

import argparse, json, math, sys, time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════
#  VERI
# ═══════════════════════════════════════════════════════════════════════════
BINANCE = "https://api.binance.com/api/v3/klines"
MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def fetch_binance(symbol: str, interval: str, years: float) -> pd.DataFrame:
    """Binance'ten OHLCV indirir (1000'lik sayfalar halinde)."""
    import requests

    step = MS[interval]
    end = int(time.time() * 1000)
    start = end - int(years * 365.25 * 86_400_000)
    rows, cur = [], start
    while cur < end:
        r = requests.get(
            BINANCE,
            params={"symbol": symbol, "interval": interval,
                    "startTime": cur, "limit": 1000},
            timeout=30,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows += batch
        cur = batch[-1][0] + step
        if len(batch) < 1000:
            break
        print(f"  ... {len(rows)} bar", end="\r", flush=True)
    print(f"  {len(rows)} bar indirildi.        ")
    df = pd.DataFrame(rows, columns=[
        "time", "open", "high", "low", "close", "volume",
        "ct", "qv", "n", "tb", "tq", "ig"])
    df = df[["time", "open", "high", "low", "close", "volume"]].astype(float)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    return df.drop_duplicates("time").set_index("time").sort_index()


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    tcol = next(c for c in df.columns if c in ("time", "date", "datetime", "timestamp"))
    if pd.api.types.is_numeric_dtype(df[tcol]):
        unit = "ms" if df[tcol].iloc[0] > 1e11 else "s"
        df[tcol] = pd.to_datetime(df[tcol], unit=unit, utc=True)
    else:
        df[tcol] = pd.to_datetime(df[tcol], utc=True)
    df = df.rename(columns={tcol: "time"})
    for c in ("open", "high", "low", "close"):
        df[c] = df[c].astype(float)
    df["volume"] = df.get("volume", 0.0).astype(float)
    return (df[["time", "open", "high", "low", "close", "volume"]]
            .drop_duplicates("time").set_index("time").sort_index())


# ═══════════════════════════════════════════════════════════════════════════
#  GOSTERGELER  (Pine ile birebir ayni formuller)
# ═══════════════════════════════════════════════════════════════════════════
EMA_LENS = [8, 13, 21, 34, 55, 89, 200]


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rma(s: pd.Series, n: int) -> pd.Series:
    """Wilder yumusatmasi = Pine'daki ta.rma()."""
    return s.ewm(alpha=1.0 / n, adjust=False).mean()


def score_components(df: pd.DataFrame):
    """Pine'daki f_score() ile ayni: fiyat konumu ve dizilim bilesenleri.
    Ikisi ayri dondurulur ki agirlik (wPrice) taramada ucuza degistirilebilsin."""
    c = df["close"]
    es = [ema(c, n) for n in EMA_LENS]
    pS = sum(np.where(c > e, 1.0, -1.0) for e in es)
    oS = sum(np.where(es[i] > es[i + 1], 1.0, -1.0) for i in range(len(es) - 1))
    pNorm = pd.Series(pS / len(es) * 100.0, index=df.index)
    oNorm = pd.Series(oS / (len(es) - 1) * 100.0, index=df.index)
    return pNorm, oNorm


def blend(pNorm, oNorm, w_price_pct: float):
    w = w_price_pct / 100.0
    return pNorm * w + oNorm * (1.0 - w)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def adx_wilder(df: pd.DataFrame, n: int = 14, sm: int = 14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - pc).abs(),
                    (df["low"] - pc).abs()], axis=1).max(axis=1)
    trn = rma(tr, n)
    pdi = 100 * rma(pd.Series(plus, index=df.index), n) / trn
    mdi = 100 * rma(pd.Series(minus, index=df.index), n) / trn
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pdi, mdi, rma(dx.fillna(0), sm)


def money_flow(df: pd.DataFrame, cvd_len=21, obv_len=21, rvol_len=20,
               vol_mult=1.5, mfi_len=14):
    """CVD / OBV / RVOL / MFI / seans VWAP -> yon bazli onay sayaclari."""
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"].fillna(0)
    rng = (h - l).replace(0, np.nan)
    up = (v * (c - l) / rng).fillna(0)
    dn = (v * (h - c) / rng).fillna(0)
    cvd = (up - dn).cumsum()
    cvd_bull = cvd > ema(cvd, cvd_len)

    step = np.sign(c.diff().fillna(0)) * v
    obv = step.cumsum()
    obv_bull = obv > ema(obv, obv_len)

    rvol_ok = v > v.rolling(rvol_len, min_periods=1).mean() * vol_mult

    hlc3 = (h + l + c) / 3
    d = hlc3.diff()
    pos = rma((hlc3 * v).where(d > 0, 0.0), mfi_len)
    neg = rma((hlc3 * v).where(d < 0, 0.0), mfi_len)
    mfi = np.where((pos + neg) == 0, 50.0,
                   np.where(neg == 0, 100.0, 100 - 100 / (1 + pos / neg.replace(0, np.nan))))
    mfi = pd.Series(mfi, index=df.index).fillna(50.0)
    mfi_bull = mfi > 50

    day = df.index.floor("D")
    pv = (hlc3 * v).groupby(day).cumsum()
    vv = v.groupby(day).cumsum()
    vwap = (pv / vv.replace(0, np.nan)).fillna(hlc3)
    vwap_bull = c > vwap

    long_cnt = (cvd_bull.astype(int) + obv_bull.astype(int) + rvol_ok.astype(int)
                + mfi_bull.astype(int) + vwap_bull.astype(int))
    short_cnt = ((~cvd_bull).astype(int) + (~obv_bull).astype(int) + rvol_ok.astype(int)
                 + (~mfi_bull).astype(int) + (~vwap_bull).astype(int))
    return long_cnt.values, short_cnt.values


def squeeze_flags(df: pd.DataFrame, adx_th=20.0, bb_len=20, bb_mult=2.0,
                  bbw_look=120, bbw_fact=1.2):
    _, _, adxv = adx_wilder(df)
    adx_sq = (adxv < adx_th).fillna(False).values
    basis = df["close"].rolling(bb_len).mean()
    dev = df["close"].rolling(bb_len).std(ddof=0) * bb_mult
    bbw = (dev * 2 / basis * 100)
    bbw_sq = (bbw <= bbw.rolling(bbw_look, min_periods=bb_len).min() * bbw_fact)
    return adx_sq, bbw_sq.fillna(False).values, adxv.values


HTF_RULE = {"15m": "15min", "1h": "1h", "4h": "4h",
            "1d": "1D", "1w": "1W", "1M": "1ME"}
# Taban zaman diliminden ust iki dilime merdiven (Pine'daki 60/240 mantigi)
HTF_LADDER = {"15m": ("1h", "4h"), "1h": ("4h", "1d"),
              "4h": ("1d", "1w"), "1d": ("1w", "1M")}


def htf_components(df: pd.DataFrame, rule: str):
    """Ust zaman diliminin skor BILESENLERI. shift(1) = KAPANMIS HTF bari
    (repaint yok), sonra taban dilime ileri-doldurma ile hizalanir.
    Bilesenler ayri dondurulur ki agirlik (w) taramada dogru uygulansin."""
    o = df.resample(rule, label="right", closed="right").agg(
        {"open": "first", "high": "max", "low": "min",
         "close": "last", "volume": "sum"}).dropna()
    p, q = score_components(o)
    return (p.shift(1).reindex(df.index, method="ffill").values,
            q.shift(1).reindex(df.index, method="ffill").values)


# ═══════════════════════════════════════════════════════════════════════════
#  SIMULASYON
# ═══════════════════════════════════════════════════════════════════════════
def simulate(op, hi, lo, cl, atrv, long_sig, short_sig, stop_arr, tp_arr,
             atr_mult, rr, use_tp, allow_rev,
             capital=10000.0, qty_pct=0.10, comm=0.0005, slip_bps=1.0):
    """Emirler bir SONRAKI barin acilisinda dolar (Pine varsayilani).
    Ayni bar icinde hem stop hem hedef gorulurse KOTUMSER varsayim: stop once."""
    n = len(cl)
    eq = capital
    pos = 0          # 0 / +1 / -1
    qty = entry = stop = tp = 0.0
    curve = np.empty(n); curve[0] = capital
    trades = []
    sl_f = slip_bps / 10000.0

    for i in range(1, n):
        # ── 1) Giris: onceki barin sinyali, bu barin acilisinda dolar ──────
        want = 1 if long_sig[i - 1] else (-1 if short_sig[i - 1] else 0)
        if want != 0 and (pos == 0 or (allow_rev and want != pos)):
            if pos != 0:                              # ters sinyal -> kapat
                px = op[i] * (1 - sl_f) if pos > 0 else op[i] * (1 + sl_f)
                pnl = (px - entry) * qty * pos - abs(px * qty) * comm
                eq += pnl
                trades.append(pnl / capital)
                pos = 0
            a = atrv[i - 1]
            if np.isfinite(a) and a > 0 and eq > 0:
                entry = op[i] * (1 + sl_f) if want > 0 else op[i] * (1 - sl_f)
                s0, t0 = stop_arr[i - 1], tp_arr[i - 1]
                if np.isfinite(s0):
                    stop, tp = s0, t0          # RANGE / BREAKOUT: seviye bazli
                else:
                    stop = entry - a * atr_mult if want > 0 else entry + a * atr_mult
                    risk = abs(entry - stop)
                    tp = entry + risk * rr if want > 0 else entry - risk * rr
                # Acilis stopun otesine gecmisse islem gecersiz
                if (want > 0 and stop < entry) or (want < 0 and stop > entry):
                    qty = eq * qty_pct / entry
                    eq -= abs(entry * qty) * comm
                    pos = want

        # ── 2) Cikis: stop / hedef ayni bar icinde kontrol edilir ─────────
        if pos != 0:
            px = None
            if pos > 0:
                if lo[i] <= stop:      px = stop
                elif use_tp and hi[i] >= tp: px = tp
            else:
                if hi[i] >= stop:      px = stop
                elif use_tp and lo[i] <= tp:  px = tp
            if px is not None:
                pnl = (px - entry) * qty * pos - abs(px * qty) * comm
                eq += pnl
                trades.append(pnl / capital)
                pos = 0

        mtm = (cl[i] - entry) * qty * pos if pos != 0 else 0.0
        curve[i] = eq + mtm

    return curve, np.array(trades)


def metrics(curve, trades, bars_per_year):
    cap = curve[0]
    ret = curve[-1] / cap - 1
    peak = np.maximum.accumulate(curve)
    dd = float(((curve - peak) / peak).min())
    yrs = max(len(curve) / bars_per_year, 1e-9)
    cagr = (curve[-1] / cap) ** (1 / yrs) - 1 if curve[-1] > 0 else -1.0
    r = np.diff(curve) / curve[:-1]
    r = r[np.isfinite(r)]
    sharpe = float(r.mean() / r.std() * math.sqrt(bars_per_year)) if len(r) > 2 and r.std() > 0 else 0.0
    wins = trades[trades > 0]; loss = trades[trades <= 0]
    pf = float(wins.sum() / abs(loss.sum())) if len(loss) and loss.sum() != 0 else (float("inf") if len(wins) else 0.0)
    return {
        "return_pct": round(ret * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_dd_pct": round(dd * 100, 2),
        "calmar": round(cagr / abs(dd), 2) if dd < 0 else 0.0,
        "sharpe": round(sharpe, 2),
        "profit_factor": round(pf, 2) if np.isfinite(pf) else 99.99,
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if len(trades) else 0.0,
        "trades": int(len(trades)),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  SINYAL URETIMI
# ═══════════════════════════════════════════════════════════════════════════
def _prev(a):
    return np.concatenate([[a[0] * 0], a[:-1]])


def _since(mask):
    """Pine'daki ta.barssince() karsiligi."""
    idx = np.arange(len(mask))
    last = np.maximum.accumulate(np.where(mask, idx, -1))
    return np.where(last < 0, 9999, idx - last)


def playbooks(pre, p):
    """Uc oyun kitabinin sinyalleri ve her modun kendi stop/hedef seviyesi.
    Pine'daki IFR Trader Pro mantiginin birebir karsiligi."""
    c, h, l, o = pre["c"], pre["h"], pre["l"], pre["o"]
    atrv, adxv = pre["atrv"], pre["adx"]
    bt, bb = pre["box_top"], pre["box_bot"]
    n = len(c)

    wf = p["w"] / 100.0
    sc = pre["pNorm"] * wf + pre["oNorm"] * (1 - wf)
    st = np.where(sc >= p["th"], 1, np.where(sc <= -p["th"], -1, 0))

    boxH = bt - bb
    boxOk = np.isfinite(bt) & np.isfinite(bb) & (boxH > 0)
    inBox = boxOk & (c <= bt) & (c >= bb)
    squeeze = np.isfinite(adxv) & (adxv < p["adxTh"])
    rangeReg = boxOk & squeeze & inBox
    trendReg = ~rangeReg

    use_r = p["mode"] in ("auto", "range")
    use_b = p["mode"] in ("auto", "breakout")
    use_t = p["mode"] in ("auto", "trend")

    # 1) RANGE — kenar fade
    edge = boxH * p["edge"] / 100.0
    rgL = use_r & rangeReg & (l <= bb + edge) & (c > bb + edge * 0.5) & (c > o)
    rgS = use_r & rangeReg & (h >= bt - edge) & (c < bt - edge * 0.5) & (c < o)

    # 2) BREAKOUT — kutu disina kapanis + hacim
    buR = boxOk & (c > bt) & pre["vol_ok"]
    bdR = boxOk & (c < bb) & pre["vol_ok"]
    boL = use_b & buR & ~_prev(buR).astype(bool)
    boS = use_b & bdR & ~_prev(bdR).astype(bool)

    # 3) TREND — serit + kalite puani
    prevst = np.concatenate([[0], st[:-1]])
    fU = _since((st == 1) & (prevst != 1))
    fD = _since((st == -1) & (prevst != -1))
    s1 = pre["h1p"] * wf + pre["h1o"] * (1 - wf)
    s2 = pre["h2p"] * wf + pre["h2o"] * (1 - wf)
    qL = (s1 >= p["th"]).astype(int) + (s2 >= p["th"]).astype(int) + pre["mf_long"]
    qS = (s1 <= -p["th"]).astype(int) + (s2 <= -p["th"]).astype(int) + pre["mf_short"]
    trL = use_t & trendReg & ~squeeze & (st == 1) & (fU <= p["flipw"]) & (qL >= p["qmin"])
    trS = use_t & trendReg & ~squeeze & (st == -1) & (fD <= p["flipw"]) & (qS >= p["qmin"])

    L, S = rgL | boL | trL, rgS | boS | trS

    stop = np.full(n, np.nan)
    tp = np.full(n, np.nan)
    for m, sv, tv in (
        (trL, c - atrv * p["atr"], c + atrv * p["atr"] * p["rr"]),
        (trS, c + atrv * p["atr"], c - atrv * p["atr"] * p["rr"]),
        (rgL, bb - atrv * p["pad"], bt),
        (rgS, bt + atrv * p["pad"], bb),
        (boL, bt - atrv * p["pad"], c + boxH),
        (boS, bb + atrv * p["pad"], c - boxH),
    ):
        stop = np.where(m, sv, stop)
        tp = np.where(m, tv, tp)
    return L, S, stop, tp


def run(pre, p, sl):
    L, S, stop, tp = playbooks(pre, p)
    curve, tr = simulate(sl["o"], sl["h"], sl["l"], sl["c"], sl["atr"], L, S, stop, tp,
                         p["atr"], p["rr"], True, p["rev"])
    return metrics(curve, tr, sl["bpy"]), curve


# ═══════════════════════════════════════════════════════════════════════════
#  KAZANAN AYARLARI .PINE DOSYASINA YAZ
# ═══════════════════════════════════════════════════════════════════════════
import re


def apply_to_pine(params: dict, path: str) -> None:
    """Optimizasyon sonucunu ifr_master_pro.pine icindeki input varsayilanlarina
    yazar. Sadece varsayilan degeri degistirir; etiket, tooltip, grup korunur."""
    src = Path(path).read_text(encoding="utf-8")

    # Bosluk sayisina bagimli olmayan esleme (\s* ile toleransli)
    def pat(name, kind):
        return r"(" + name + r"\s*=\s*input\." + kind + r"\()\s*" + \
               (r"(?:true|false)" if kind == "bool" else r"[-\d.]+")

    edits = [
        (pat("wPrice", "int"), str(int(params["w"]))),
        (pat("thUp", "float"), str(float(params["th"]))),
        (pat("thDn", "float"), str(-float(params["th"]))),
        (pat("qualityMin", "int"), str(int(params["qmin"]))),
        (pat("flipWindow", "int"), str(int(params["flipw"]))),
        (pat("adxTh", "float"), str(float(params["adxTh"]))),
        (pat("edgePct", "float"), str(float(params["edge"]))),
        (pat("atrMult", "float"), str(float(params["atr"]))),
        (pat("rrRatio", "float"), str(float(params["rr"]))),
        (pat("stopPad", "float"), str(float(params["pad"]))),
        (pat("allowRev", "bool"), str(bool(params["rev"])).lower()),
        (pat("useRange", "bool"), str(params["mode"] in ("auto", "range")).lower()),
        (pat("useBreak", "bool"), str(params["mode"] in ("auto", "breakout")).lower()),
        (pat("useTrend", "bool"), str(params["mode"] in ("auto", "trend")).lower()),
    ]
    # NOT: dongu degiskenini 'pat' yapmayin, yukaridaki pat() yardimcisini golgeler
    miss = []
    for rx, val in edits:
        src, k = re.subn(rx, lambda m, v=val: m.group(1) + v, src, count=1)
        if k == 0:
            miss.append(rx)

    Path(path).write_text(src, encoding="utf-8")
    print(f"  {path} guncellendi.")
    if miss:
        print(f"  UYARI: {len(miss)} alan bulunamadi, elle kontrol edin: {miss}")


# ═══════════════════════════════════════════════════════════════════════════
#  ANA AKIS
# ═══════════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="BTCUSDT")
    ap.add_argument("--interval", default="4h", choices=list(MS))
    ap.add_argument("--years", type=float, default=4.0)
    ap.add_argument("--csv")
    ap.add_argument("--htf1", choices=list(HTF_RULE), help="varsayilan: taban dilimin bir ustu")
    ap.add_argument("--htf2", choices=list(HTF_RULE), help="varsayilan: taban dilimin iki ustu")
    ap.add_argument("--folds", type=int, default=4, help="walk-forward dilim sayisi")
    ap.add_argument("--box-look", type=int, default=120, help="kutu geriye bakis (bar)")
    ap.add_argument("--adx-len", type=int, default=14)
    ap.add_argument("--adx-sm", type=int, default=14)
    ap.add_argument("--vol-mult", type=float, default=1.5)
    ap.add_argument("--quick", action="store_true", help="kucuk grid")
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--out", default="ifr_sonuc.json")
    ap.add_argument("--apply", metavar="PINE",
                    help="kazanan ayarlari bu .pine dosyasina yaz")
    ap.add_argument("--apply-which", choices=["walkforward", "best"],
                    default="walkforward",
                    help="hangi sonuc yazilsin (varsayilan: walk-forward sampiyonu)")
    a = ap.parse_args()

    print("── VERI ──────────────────────────────────────────────")
    df = load_csv(a.csv) if a.csv else fetch_binance(a.symbol, a.interval, a.years)
    if len(df) < 600:
        sys.exit("Yetersiz veri (<600 bar).")
    print(f"  {a.symbol} {a.interval} | {df.index[0]:%Y-%m-%d} → {df.index[-1]:%Y-%m-%d} | {len(df)} bar")

    print("── GOSTERGELER ───────────────────────────────────────")
    pNorm, oNorm = score_components(df)
    adx_sq, bbw_sq, _ = squeeze_flags(df)
    mfl, mfs = money_flow(df)
    d1, d2 = HTF_LADDER[a.interval]
    nxt, nx2 = (a.htf1 or d1), (a.htf2 or d2)
    _, _, adxv = adx_wilder(df, a.adx_len, a.adx_sm)
    atr_s = atr(df)
    # Kutu siniri bir bar geriden: "kapanis kutu disinda" sarti kendini bozmasin
    box_top = df["high"].rolling(a.box_look).max().shift(1)
    box_bot = df["low"].rolling(a.box_look).min().shift(1)
    vol_ok = (df["volume"] > df["volume"].rolling(20, min_periods=1).mean() * a.vol_mult)
    pre_full = {
        "pNorm": pNorm.values, "oNorm": oNorm.values,
        "adx_sq": adx_sq, "bbw_sq": bbw_sq,
        "mf_long": mfl, "mf_short": mfs,
        "o": df["open"].values, "h": df["high"].values,
        "l": df["low"].values, "c": df["close"].values,
        "atrv": atr_s.values, "adx": adxv.values,
        "box_top": box_top.values, "box_bot": box_bot.values,
        "vol_ok": vol_ok.values,
    }
    pre_full["h1p"], pre_full["h1o"] = htf_components(df, HTF_RULE[nxt])
    pre_full["h2p"], pre_full["h2o"] = htf_components(df, HTF_RULE[nx2])
    bpy = {"15m": 35040, "1h": 8760, "4h": 2190, "1d": 365}[a.interval]
    sl_full = {"o": df["open"].values, "h": df["high"].values, "l": df["low"].values,
               "c": df["close"].values, "atr": atr(df).values, "bpy": bpy}
    print(f"  HTF1={nxt}  HTF2={nx2}")

    if a.quick:
        grid = dict(mode=["auto", "trend", "range", "breakout"], w=[50], th=[40],
                    qmin=[2, 3], flipw=[3], atr=[1.5], rr=[2.0], adxTh=[20],
                    edge=[15], pad=[0.5], rev=[True])
    else:
        # Grid bilerek dar tutuldu: her ek parametre coklu-karsilastirma
        # yaniltmasini buyutur, yani sansa iyi gorunen ayar bulma riskini.
        grid = dict(mode=["auto", "trend", "range", "breakout"],
                    w=[50], th=[30, 40, 50], qmin=[2, 3, 4], flipw=[1, 3, 5],
                    atr=[1.5, 2.0], rr=[1.5, 2.0, 3.0], adxTh=[20, 25],
                    edge=[15], pad=[0.5], rev=[True])
    keys = list(grid)
    combos = [dict(zip(keys, v)) for v in __import__("itertools").product(*grid.values())]
    print(f"── TARAMA ── {len(combos)} kombinasyon")

    def slice_of(i0, i1):
        return ({k: v[i0:i1] for k, v in pre_full.items()},
                {"o": sl_full["o"][i0:i1], "h": sl_full["h"][i0:i1],
                 "l": sl_full["l"][i0:i1], "c": sl_full["c"][i0:i1],
                 "atr": sl_full["atr"][i0:i1], "bpy": bpy})

    # 1) Tum gecmis (vitrin — egri uydurma riski yuksek)
    full = []
    t0 = time.time()
    for k, p in enumerate(combos):
        m, _ = run(pre_full, p, sl_full)
        full.append((p, m))
        if k % 200 == 0:
            print(f"  {k}/{len(combos)}  {time.time()-t0:.0f}s", end="\r", flush=True)
    print(f"  tamamlandi ({time.time()-t0:.0f}s)                ")
    ok = [x for x in full if x[1]["trades"] >= 20]
    best_ret = max(ok or full, key=lambda x: x[1]["return_pct"])

    # 2) Walk-forward: her dilimde onceki pencerede optimize, SONRAKINDE test
    n = len(df); seg = n // (a.folds + 1)
    agg = {}
    for f in range(a.folds):
        tr0, tr1 = 0, seg * (f + 1)
        te0, te1 = tr1, min(tr1 + seg, n)
        if te1 - te0 < 120:
            continue
        pre_tr, sl_tr = slice_of(tr0, tr1)
        pre_te, sl_te = slice_of(te0, te1)
        scored = []
        for p in combos:
            m, _ = run(pre_tr, p, sl_tr)
            if m["trades"] >= 10:
                scored.append((p, m))
        if not scored:
            continue
        champ = max(scored, key=lambda x: x[1]["return_pct"])[0]
        m_te, _ = run(pre_te, champ, sl_te)
        key = json.dumps(champ, sort_keys=True)
        agg.setdefault(key, []).append(m_te["return_pct"])
        print(f"  fold {f+1}: egitim {tr1-tr0} bar → test {te1-te0} bar | "
              f"OOS getiri {m_te['return_pct']:+.1f}% ({m_te['trades']} islem)")

    print("\n══ TUM GECMISTE EN IYI GETIRI (vitrin, guvenmeyin) ══")
    print(json.dumps(best_ret[0], ensure_ascii=False), "\n ", best_ret[1])

    robust = None
    if agg:
        avg = {k: (float(np.mean(v)), len(v)) for k, v in agg.items()}
        bk = max(avg, key=lambda k: avg[k][0])
        robust = json.loads(bk)
        print("\n══ WALK-FORWARD SAMPIYON (gercekte kullanin) ══")
        print(json.dumps(robust, ensure_ascii=False))
        print(f"  ortalama OOS getiri: {avg[bk][0]:+.2f}%  ({avg[bk][1]} dilimde secildi)")
        m_all, _ = run(pre_full, robust, sl_full)
        print("  tum gecmiste:", m_all)

    print(f"\n── EN IYI {a.top} (tum gecmis, getiriye gore) ──")
    hdr = f"{'mod':>10}{'th':>5}{'qmin':>6}{'flipw':>7}{'atr':>5}{'rr':>5}{'adx':>5}" \
          f"{'getiri%':>10}{'dd%':>8}{'PF':>6}{'islem':>7}"
    print(hdr); print("-" * len(hdr))
    for p, m in sorted(ok or full, key=lambda x: -x[1]["return_pct"])[:a.top]:
        print(f"{p['mode']:>10}{p['th']:>5}{p['qmin']:>6}{p['flipw']:>7}{p['atr']:>5}"
              f"{p['rr']:>5}{p['adxTh']:>5}{m['return_pct']:>10.1f}"
              f"{m['max_dd_pct']:>8.1f}{m['profit_factor']:>6.2f}{m['trades']:>7}")

    # Referans: al-tut
    bh = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
    print(f"\nReferans — AL VE TUT: {bh:+.1f}%")

    if a.apply:
        chosen = robust if (a.apply_which == "walkforward" and robust) else best_ret[0]
        which = "walk-forward sampiyonu" if chosen is robust else "tum gecmiste en iyi"
        print(f"\n── AYARLAR UYGULANIYOR ({which}) ──")
        apply_to_pine(chosen, a.apply)

    json.dump({"symbol": a.symbol, "interval": a.interval,
               "bars": len(df), "from": str(df.index[0]), "to": str(df.index[-1]),
               "buy_hold_pct": round(bh, 2),
               "best_full_history": {"params": best_ret[0], "metrics": best_ret[1]},
               "walk_forward_champion": robust},
              open(a.out, "w"), indent=2, ensure_ascii=False)
    print(f"\nSonuclar {a.out} dosyasina yazildi.")


if __name__ == "__main__":
    main()
