import numpy as np
import pandas as pd

# -----------------------------
# Time-in-Range (fixed 70–180)
# -----------------------------
def tir_70_180(df: pd.DataFrame) -> float:
    """
    Percent of valid glucose points within [70, 180] mg/dL.
    """
    g = pd.to_numeric(df["gl"], errors="coerce")
    valid = g.notna()
    n = int(valid.sum())
    if n == 0:
        return np.nan
    gv = g[valid]
    mask = (gv >= 70.0) & (gv <= 180.0)
    return 100.0 * float(mask.sum()) / n

# -----------------------------
# Coefficient of Variation
# -----------------------------
def cv(df: pd.DataFrame) -> float:
    """
    CV (%) = 100 * sd(G)/mean(G)
    """
    g = pd.to_numeric(df["gl"], errors="coerce")
    m = np.nanmean(g)
    if not np.isfinite(m) or m == 0:
        return np.nan
    s = np.nanstd(g, ddof=1)
    return 100.0 * s / m

# -----------------------------
# Glucose Management Indicator
# -----------------------------
def gmi(df: pd.DataFrame) -> float:
    """
    GMI (%) = 3.31 + 0.02392 * mean(G in mg/dL)
    """
    g = pd.to_numeric(df["gl"], errors="coerce")
    m = np.nanmean(g)
    return np.nan if not np.isfinite(m) else 3.31 + 0.02392 * m


# -----------------------------
# High & Low Blood Glucose Index
# -----------------------------
def hbgi(df: pd.DataFrame) -> float:
    """
    HBGI per Kovatchev:
      f = 1.509 * (ln(G)^1.084 - 5.381); risk = 10 * f^2; HBGI = mean(risk | f > 0).
    """
    g = pd.to_numeric(df["gl"], errors="coerce")
    g = g[g > 0]
    if g.empty:
        return np.nan
    f = 1.509 * (np.power(np.log(g), 1.084) - 5.381)
    r = 10.0 * np.square(f)
    pos = r[f > 0]
    return float(np.nanmean(pos)) if len(pos) else 0.0


def lbgi(df: pd.DataFrame) -> float:
    """
    LBGI per Kovatchev:
      f = 1.509 * (ln(G)^1.084 - 5.381); risk = 10 * f^2; LBGI = mean(risk | f < 0).
    """
    g = pd.to_numeric(df["gl"], errors="coerce")
    g = g[g > 0]
    if g.empty:
        return np.nan
    f = 1.509 * (np.power(np.log(g), 1.084) - 5.381)
    r = 10.0 * np.square(f)
    neg = r[f < 0]
    return float(np.nanmean(neg)) if len(neg) else 0.0


# -----------------------------
# MAGE (Moving-Average method)
# -----------------------------
def mage_ma(df: pd.DataFrame,
            resample_rule: str = "5min",
            short_win: str = "30min",
            long_win: str = "2h",
            sd_multiplier: float = 1.0) -> float:
    """
    Moving-average MAGE:
      - Resample to 5-min grid (linear interpolation)
      - Short/long MAs (centered); zero-crossings of (short - long) define swings
      - Amplitude = peak-to-trough on the interpolated series
      - Keep amplitudes >= sd_multiplier * SD(original), then average
    """
    g = pd.to_numeric(df["gl"], errors="coerce")
    t = pd.to_datetime(df["time"], errors="coerce")
    good = g.notna() & t.notna()
    if not good.any():
        return np.nan

    s = pd.Series(g[good].values, index=pd.to_datetime(t[good])).sort_index()
    s5 = s.resample(resample_rule).mean().interpolate("time").dropna()
    if len(s5) < 5:
        return np.nan

    sma = s5.rolling(short_win, min_periods=1, center=True).mean()
    lma = s5.rolling(long_win,  min_periods=1, center=True).mean()
    diff = (sma - lma).ffill().fillna(0.0)
    sign = np.sign(diff.values)
    zc_idx = np.where(np.diff(sign) != 0)[0]
    if len(zc_idx) < 1:
        return np.nan

    seg_edges = [0] + (zc_idx + 1).tolist() + [len(s5)]
    sd_orig = np.nanstd(s5.values, ddof=1)  # sample SD
    thresh = (sd_multiplier * sd_orig) if np.isfinite(sd_orig) else 0.0

    amps = []
    for i in range(len(seg_edges) - 1):
        a, b = seg_edges[i], seg_edges[i + 1]
        seg = s5.iloc[a:b]
        if len(seg) < 2:
            continue
        amp = float(seg.max() - seg.min())
        if amp >= thresh:
            amps.append(amp)
    return float(np.mean(amps)) if amps else np.nan


def mage_ma_segments(df: pd.DataFrame,
                     resample_rule: str = "5min",
                     short_win: str = "30min",
                     long_win: str = "2h",
                     sd_multiplier: float = 1.0):
    g = pd.to_numeric(df["gl"], errors="coerce")
    t = pd.to_datetime(df["time"], errors="coerce")
    good = g.notna() & t.notna()

    s = pd.Series(g[good].values, index=pd.to_datetime(t[good])).sort_index()
    s5 = s.resample(resample_rule).mean().interpolate("time").dropna()

    sma = s5.rolling(short_win, min_periods=1, center=True).mean()
    lma = s5.rolling(long_win,  min_periods=1, center=True).mean()
    diff = (sma - lma).ffill().fillna(0.0)
    sign = np.sign(diff.values)
    zc_idx = np.where(np.diff(sign) != 0)[0]

    segs = []
    seg_edges = [0] + (zc_idx + 1).tolist() + [len(s5)]
    sd_orig = np.nanstd(s5.values, ddof=1)
    thresh = (sd_multiplier * sd_orig) if np.isfinite(sd_orig) else 0.0

    for i in range(len(seg_edges) - 1):
        a, b = seg_edges[i], seg_edges[i + 1]
        seg = s5.iloc[a:b]
        if len(seg) < 2:
            continue
        vmax, vmin = seg.max(), seg.min()
        amp = float(vmax - vmin)
        if amp >= thresh:
            t0, t1 = seg.index[0], seg.index[-1]
            t_mid = t0 + (t1 - t0) / 2
            segs.append({"t0": t0, "t1": t1, "amp": amp, "t_mid": t_mid})
    return segs


# -----------------------------
# Bundle
# -----------------------------
def summarize_measures(df: pd.DataFrame,
                      sd_multiplier: float = 1.0) -> dict:
    return {
        "cv_percent": cv(df),
        "gmi_percent": gmi(df),
        "HBGI": hbgi(df),
        "LBGI": lbgi(df),
        "MAGE": mage_ma(df, sd_multiplier=sd_multiplier),
        "in_range_70_180": tir_70_180(df),
    }
