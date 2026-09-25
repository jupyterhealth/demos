import pandas as pd
import numpy as np
import ruptures as rpt
from typing import Literal


def process_cgm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Covert glucose values to numeric by mapping
    df["gl"] = df["gl"].replace({"Low": "39", "High": "401"})
    df["gl"] = pd.to_numeric(df["gl"], errors="coerce")
    df = df.dropna(subset=["gl"])
    df = df.sort_values("time")

    df["date"] = df["time"].dt.floor("D")

    # Get valid full days
    full_days = df["date"].value_counts().loc[lambda x: x > 0].index.sort_values()
    if len(full_days) < 3:
        return df.iloc[0:0]  # Not enough days to trim

    # Trim first and last partial days
    df = df[df["date"].between(full_days[1], full_days[-2])]

    # Remove first 24 hours
    start_time = df["time"].min() + pd.Timedelta(hours=24)
    df = df[df["time"] >= start_time]

    return df.drop(columns="date")


MethodType = Literal["low_variability", "derivative", "changepoint", "personalized_sd"]
def detect_stable_glucose(df: pd.DataFrame,
                          method: MethodType="low_variability",
                          window: int=30,
                          sd_thresh: float=5,
                          range_thresh: float=10,
                          slope_thresh: float=0.1,
                          min_segment_length: int=6,
                          sampling_interval: float=5.0,
                          min_hours: float=2.0,
                          sd_multiplier: float=1.0,
                          **kwargs) -> pd.DataFrame:
    """
    Detect stable/basal glucose segments using different methods.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'time' (datetime) and 'gl' (float).
    method : str
        One of ['low_variability', 'derivative', 'changepoint', 'personalized_sd'].
    window : int
        Rolling window size in minutes (for low_variability and derivative).
    sd_thresh : float
        SD threshold for low variability detection.
    range_thresh : float
        Range threshold for low variability detection.
    slope_thresh : float
        Absolute slope threshold (mg/dL per min) for derivative method.
    min_segment_length : int
        Minimum segment length (number of points) for derivative/changepoint.
    sampling_interval : float
        Sampling interval in minutes between CGM readings.
    min_hours : float
        Minimum segment duration in hours to be considered stable.

    Returns
    -------
    pd.DataFrame : original df with added 'stable_label' column.
    """

    out = df.copy()
    out["stable_label"] = "unstable"

    pts_window = int(window / sampling_interval)

    # --- Method 1: Low Variability ---
    if method == "low_variability":
        rolling = out["gl"].rolling(pts_window, center=True)
        out["rolling_sd"] = rolling.std()
        out["rolling_range"] = rolling.max() - rolling.min()
        mask = (out["rolling_sd"] <= sd_thresh) & (out["rolling_range"] <= range_thresh)
        out.loc[mask, "stable_label"] = "stable"

    # --- Method 2: Derivative ---
    elif method == "derivative":
        out["slope"] = out["gl"].diff() / (sampling_interval)
        mask = out["slope"].abs().rolling(pts_window, center=True).mean() <= slope_thresh
        out.loc[mask, "stable_label"] = "stable"

    # --- Method 3: Change Point Detection ---
    elif method == "changepoint":
        if rpt is None:
            raise ImportError("ruptures package is required for changepoint detection.")
        signal = out["gl"].values
        algo = rpt.Pelt(model="rbf").fit(signal)
        bkps = algo.predict(pen=kwargs.get("penalty", 3))
        stable_idx = []
        last = 0
        for b in bkps:
            segment = out.iloc[last:b]
            if len(segment) >= min_segment_length and segment["gl"].std() <= sd_thresh:
                stable_idx.extend(segment.index)
            last = b
        out.loc[stable_idx, "stable_label"] = "stable"

    # --- Method 4: Personalized SD ---
    elif method == "personalized_sd":
        win = f"{24*60}min"
        out = out.set_index("time")
        rolling_mean = out["gl"].rolling(win, min_periods=5).mean()
        rolling_sd = out["gl"].rolling(win, min_periods=5).std()

        lower = rolling_mean - (sd_multiplier * rolling_sd)
        upper = rolling_mean + (sd_multiplier * rolling_sd)

        mask = (
            (out["gl"] >= lower) &
            (out["gl"] <= upper)
        )
        out.loc[mask, "stable_label"] = "stable"
        out = out.reset_index()

    if min_hours > 0:
        stable_points = out[out["stable_label"] == "stable"]
        if not stable_points.empty:
            group_id = (stable_points.index.to_series().diff() > 1).cumsum()
            valid_idx = []
            for _, seg in stable_points.groupby(group_id):
                seg_hours = (seg["time"].iloc[-1] - seg["time"].iloc[0]).total_seconds() / 3600
                if seg_hours >= min_hours:
                    valid_idx.extend(seg.index)
            out.loc[~out.index.isin(valid_idx), "stable_label"] = "unstable"

    return out


def detect_fasting_segments(cgm_df: pd.DataFrame,
                            food_df: pd.DataFrame,
                            fasting_window_hours: float=8.0) -> pd.DataFrame:
    """
    Label CGM points as fasting or non-fasting based on time since last meal.

    Parameters
    ----------
    cgm_df : pd.DataFrame
        Must contain 'time' (datetime) and 'gl' (float).
    food_df : pd.DataFrame
        Must contain 'meal_time' (datetime) for food intake events.
    fasting_window_hours : float
        Minimum hours since last meal to consider as fasting.

    Returns
    -------
    pd.DataFrame
        Original cgm_df with an added 'fasting_label' column.
    """

    out = cgm_df.copy()
    out["fasting_label"] = "non_fasting"

    # Sort food log times
    cgm_times = pd.to_datetime(out["time"])
    food_times = pd.to_datetime(food_df["time"])
    food_times = food_times.dt.tz_convert(cgm_times.dt.tz)

    # Find the last meal before each CGM point
    last_meal_idx = food_times.searchsorted(cgm_times, side="right") - 1
    last_meal_idx[last_meal_idx < 0] = 0
    last_meal = food_times.iloc[last_meal_idx].to_numpy()
    last_meal[last_meal_idx < 0] = np.datetime64("NaT")  # reapply NaT where no prior meal

    out["last_meal_time"] = last_meal
    out["hours_since_last_meal"] = (out["time"] - out["last_meal_time"]) / np.timedelta64(1, "h")

    # Label fasting segments
    mask = out["hours_since_last_meal"] >= fasting_window_hours
    out.loc[mask, "fasting_label"] = "fasting"

    return out


def extract_wakeup_glucose(cgm_df: pd.DataFrame,
                           sleep_df: pd.DataFrame,
                           min_sleep_hours: float=7.0,
                           gap_threshold_minutes: float=30.0) -> pd.DataFrame:
    """
    Extract the last CGM point from each long sleep period (>= min_sleep_hours).

    Parameters
    ----------
    cgm_df : pd.DataFrame
        CGM data with columns ['time', 'gl'] (timezone-aware datetimes).
    sleep_df : pd.DataFrame
        Sleep data with columns ['start', 'end', 'stage'] (timezone-aware datetimes).
    min_sleep_hours : float
        Minimum sleep duration (hours) to be considered for wakeup glucose.
    gap_threshold_minutes : float
        Max gap (minutes) between consecutive sleep stages to be merged.

    Returns
    -------
    pd.DataFrame
        Columns: ['sleep_start', 'sleep_end', 'wakeup_time', 'wakeup_glucose']
    """
    if sleep_df is None or sleep_df.empty:
        return pd.DataFrame(columns=["sleep_start", "sleep_end", "wakeup_time", "wakeup_glucose"])

    sleep_df = sleep_df.sort_values("start").reset_index(drop=True)
    gap_threshold = pd.Timedelta(minutes=gap_threshold_minutes)

    # Merge sleep stages into blocks based on gap threshold
    blocks = []
    current_block = []

    for _, row in sleep_df.iterrows():
        if current_block and (row["start"] - current_block[-1]["end"]) > gap_threshold:
            blocks.append(current_block)
            current_block = []
        current_block.append(row)
    if current_block:
        blocks.append(current_block)

    results = []
    for block in blocks:
        block_start = block[0]["start"]
        block_end = block[-1]["end"]
        duration_h = (block_end - block_start).total_seconds() / 3600

        if duration_h >= min_sleep_hours:
            # Get CGM points during this block
            mask = (cgm_df["time"] >= block_start) & (cgm_df["time"] <= block_end)
            block_cgm = cgm_df[mask]

            if not block_cgm.empty:
                wake_time = block_cgm["time"].iloc[-1]
                wake_glucose = block_cgm["gl"].iloc[-1]
                results.append({
                    "sleep_start": block_start,
                    "sleep_end": block_end,
                    "wakeup_time": wake_time,
                    "wakeup_glucose": wake_glucose
                })

    return pd.DataFrame(results)


def extract_ppgr_pairs(cgm_df: pd.DataFrame,
                       food_df: pd.DataFrame,
                       window_minutes: int=120,
                       include_metadata: bool=True) -> pd.DataFrame:
    """
    Extract (meal, 2-hour CGM curve) pairs in long format.

    Parameters
    ----------
    cgm_df : pd.DataFrame
        Must contain 'time' (datetime-like) and 'gl' (float).
        For best results, 'time' should be timezone-aware (tz-aware).
    food_df : pd.DataFrame
        Must contain either 'meal_time' (datetime-like) or 'time' (datetime-like)
        indicating each food intake event. Optional extra metadata columns
        (e.g., 'meal_type', 'nutrients', etc.) will be copied per meal if
        include_metadata=True.
    window_minutes : int
        Length of postprandial window to extract (default 120 minutes).
    include_metadata : bool
        If True, copy any extra columns from food_df onto each CGM row
        belonging to that meal window.

    Returns
    -------
    pd.DataFrame
        Long-format dataframe with columns:
          - 'meal_id'    : int, 0..N-1 within the provided food_df
          - 'meal_time'  : datetime64[ns, tz], aligned to cgm_df tz if present
          - 't_rel_min'  : float, minutes since the meal start (0..window)
          - 'time'       : datetime64[ns, tz], CGM timestamps
          - 'gl'         : float, CGM glucose
        Plus any metadata columns from food_df if include_metadata=True.
    """
    cgm = cgm_df.copy()
    meals = food_df.copy()

    cgm_times = pd.to_datetime(cgm["time"])
    food_times = pd.to_datetime(meals["time"])
    food_times = food_times.dt.tz_localize(cgm_times.dt.tz)
    meals["time"] = food_times

    window = pd.Timedelta(minutes=window_minutes)
    rows = []

    nutrient_keys = []
    if "nutrients" in meals.columns:
        nutrient_keys = sorted({k for x in meals["nutrients"].dropna()
                                  for k in (x.keys() if isinstance(x, dict) else [])})

    for meal_id, m in meals.iterrows():
        t0 = m["time"]
        t1 = t0 + window
        sub = cgm[(cgm["time"] >= t0) & (cgm["time"] <= t1)][["time", "gl"]].dropna()

        row = {
            "meal_id": meal_id,
            "meal_time": t0,
            "gl": sub["gl"].astype(float).tolist(),
        }

        if "meal_type" in meals.columns:
            row["meal_type"] = m.get("meal_type")

        if "nutrients" in meals.columns:
            nd = m.get("nutrients", {})
            if isinstance(nd, dict):
                for k in nutrient_keys:
                    row[k] = nd.get(k, np.nan)

        rows.append(row)

    out = pd.DataFrame(rows)
    return out


# Glucose target range, mg/dL.
TARGET_RANGE = (70, 180)


def label_sleep_period(cgm: pd.DataFrame, nights: pd.DataFrame,
                       time_col: str = "effective_time_frame_date_time",
                       value_col: str = "blood_glucose_value") -> pd.DataFrame:
    """Tag each glucose reading with whether it falls inside a sleep window.

    Parameters
    ----------
    cgm : pandas.DataFrame
        Raw glucose frame, or the output of :func:`process_cgm` (``time``/``gl``).
    nights : pandas.DataFrame
        Output of :func:`~cgmsandbox.loader.load_sleep_nights`.

    Returns
    -------
    pandas.DataFrame with columns ``time``, ``gl``, ``asleep``.
    """
    if "time" in cgm.columns and "gl" in cgm.columns:
        out = cgm[["time", "gl"]].copy()
    else:
        out = cgm[[time_col, value_col]].copy()
        out.columns = ["time", "gl"]
    out["time"] = pd.to_datetime(out["time"], utc=True, errors="coerce")
    out["gl"] = pd.to_numeric(out["gl"], errors="coerce")
    out = out.dropna().sort_values("time").reset_index(drop=True)
    out["asleep"] = False
    for _, r in nights.iterrows():
        m = (out["time"] >= r.sleep_start) & (out["time"] < r.sleep_end)
        out.loc[m, "asleep"] = True
    return out


def nocturnal_vs_diurnal(cgm: pd.DataFrame, nights: pd.DataFrame,
                         target: tuple[int, int] = TARGET_RANGE) -> pd.DataFrame:
    """Mean, variability and time-in-range for asleep vs awake periods.

    This is the measure that genuinely requires BOTH modalities: it cannot be
    computed from the glucose record alone (no sleep) nor the sleep record alone
    (no glucose).
    """
    lab = label_sleep_period(cgm, nights)
    rows = []
    for asleep, g in lab.groupby("asleep"):
        tir = ((g.gl >= target[0]) & (g.gl <= target[1])).mean() * 100
        rows.append({
            "period": "asleep" if asleep else "awake",
            "readings": int(len(g)),
            "mean_mgdl": round(float(g.gl.mean()), 1),
            "sd": round(float(g.gl.std()), 1),
            "cv_pct": round(float(g.gl.std() / g.gl.mean() * 100), 1),
            "time_in_range_pct": round(float(tir), 1),
        })
    return pd.DataFrame(rows)
