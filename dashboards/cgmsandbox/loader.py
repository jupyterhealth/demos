import json
import pandas as pd
from pathlib import Path
from dateutil import tz
import re
from typing import Literal, Optional

def load_cgm_data(source: Literal["file", "client"],
                  base_path: str | Path | None=None,
                  subject_id: int | None = None,
                  filename: str | None = None,
                  client_df: Optional[pd.DataFrame] = None
                 ) -> pd.DataFrame:

    # Prepare dataframe if given from JH client
    if source == "client":
        if client_df is None:
            raise ValueError("client_df must be provided when source='client'.")
        df = pd.DataFrame({
            "time": pd.to_datetime(client_df["effective_time_frame_date_time"],
                                   utc=True, errors="coerce"),
            "gl": pd.to_numeric(client_df["blood_glucose_value"], errors="coerce")
        })

        return df.sort_values("time").reset_index(drop=True)

    # Prepare dataframe if given from local file
    base_path = Path(base_path)
    subject_dir = base_path / str(subject_id) if subject_id else base_path
    if not filename:
        raise ValueError("filename required for source='file'.")

    filename = filename.format(subject_id=subject_id)
    file_path = next((p for p in [subject_dir / filename, base_path / filename] if p.exists()), None)
    if not file_path:
        raise FileNotFoundError(f"No CGM file found (tried {filename})")

    with open(file_path, "r") as f:
        data = json.load(f)

    raw = pd.json_normalize(data.get("body", []))
    df = pd.DataFrame({
        "time": pd.to_datetime(raw["effective_time_frame.date_time"], utc=True, errors="coerce"),
        "gl": pd.to_numeric(raw["blood_glucose.value"], errors="coerce")
    })
    return df.dropna(subset=["time", "gl"]).reset_index(drop=True)


def load_sleep_data(source: Literal["file", "client"],
                    base_path: str | Path | None = None,
                    subject_id: int | None = None,
                    filename: str | None = None,
                    client_df: Optional[pd.DataFrame] = None,
                   ) -> pd.DataFrame:
    # Prepare dataframe if given from JH client
    if source == "client":
        if client_df is None:
            raise ValueError("client_df must be provided when source='client'.")

        # collect all unique episode indices
        episode_indices = sorted({
            int(m.group(1))
            for c in client_df.columns
            if (m := re.match(r"sleep_stage_episodes_(\d+)_", c))
        })

        records = []
        for _, row in client_df.iterrows():
            for i in episode_indices:
                start_col = f"sleep_stage_episodes_{i}_sleep_stage_time_frame_time_interval_start_date_time"
                end_col   = f"sleep_stage_episodes_{i}_sleep_stage_time_frame_time_interval_end_date_time"
                stage_col = f"sleep_stage_episodes_{i}_sleep_stage_state"

                start = pd.to_datetime(row[start_col], utc=True, errors="coerce")
                end   = pd.to_datetime(row[end_col], utc=True, errors="coerce")
                stage = str(row.get(stage_col, "Unknown"))

                if pd.notna(start) and pd.notna(end):
                    records.append({"start": start, "end": end, "stage": stage})

        df = pd.DataFrame(records).drop_duplicates().sort_values("start").reset_index(drop=True)
        return df

    # Prepare dataframe if given from local file
    base_path = Path(base_path)
    subject_dir = base_path / str(subject_id) if subject_id is not None else base_path

    if filename:
        filename = filename.format(subject_id=subject_id)
        candidates = [subject_dir / filename, base_path / filename]
    else:
        raise ValueError("Must specify either `filename` or `subject_id`.")

    json_file = next((p for p in candidates if p.exists()), None)
    if json_file is None:
        raise FileNotFoundError(f"No CGM file found (tried {candidates})")

    with open(json_file, "r") as file:
        data = json.load(file)

    records = []

    body = data.get("body", [])

    for item in body:
        episodes = item.get("sleep_stage_episodes", [])
        for ep in episodes:
            ti = ep.get("sleep_stage_time_frame", {}).get("time_interval", {})

            start = pd.to_datetime(ti.get("start_date_time"), utc=True, errors="coerce")
            end   = pd.to_datetime(ti.get("end_date_time"),   utc=True, errors="coerce")
            stage = ep.get("sleep_stage_state")

            records.append({"start": start, "end": end, "stage": stage})

    return pd.DataFrame(records)


def load_food_entry_data(source: Literal["file", "client"],
                         base_path: str | Path | None = None,
                         subject_id: int | None = None,
                         filename: str | None = None,
                         client_df: Optional[pd.DataFrame] = None
                        ) -> pd.DataFrame:

    # Prepare dataframe if given from JH client
    if source == "client":
        if client_df is None:
            raise ValueError("client_df must be provided when source='client'.")

        df = pd.DataFrame({
            "time": pd.to_datetime(client_df["effective_time_frame_date_time"], utc=True, errors="coerce"),
            "carbohydrate": pd.to_numeric(client_df.get("carbohydrate_value"), errors="coerce"),
            "food_name": client_df.get("food_name", "Food").astype(str).str.strip().replace({"": "food_entry"}),
            "calories": pd.to_numeric(client_df.get("calories_value"), errors="coerce")
        })
        return df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)

    # Prepare dataframe if given from local file
    base_path = Path(base_path)
    subject_dir = base_path / str(subject_id) if subject_id is not None else base_path

    if filename:
        filename = filename.format(subject_id=subject_id)
        candidates = [subject_dir / filename, base_path / filename]
    else:
        raise ValueError("Must specify either `filename` or `subject_id`.")

    json_file = next((p for p in candidates if p.exists()), None)
    if json_file is None:
        raise FileNotFoundError(f"No food entry file found (tried {candidates})")

    with open(json_file, "r") as f:
        data = json.load(f)

    body = data.get("body", [])
    raw_df = pd.json_normalize(body)

    df = pd.DataFrame()
    df["time"] = pd.to_datetime(
        raw_df["effective_time_frame.date_time"], errors="coerce", utc=True
    )

    df["carbohydrate"] = pd.to_numeric(raw_df.get("carbohydrate.value"), errors="coerce")

    food_name_series = raw_df.get("food_name")
    if food_name_series is None:
        food_name_series = pd.Series(["Food"] * len(raw_df))
    df["food_name"] = food_name_series.astype(str).str.strip().replace({"": "food_entry"})

    df["calories"] = pd.to_numeric(raw_df["calories.value"], errors="coerce")

    return df


def load_sleep_nights(client_df: pd.DataFrame) -> pd.DataFrame:
    """Per-night sleep aggregates from a JHE ``ieee:sleep-stage-summary:1.0`` frame.

    Complements :func:`load_sleep_data`. That function reads stage *episodes* and
    is therefore only usable when the records carry ``sleep_stage_episodes_*``
    columns. Many real studies do not: study 30006's sleep records hold aggregate
    durations only, so ``load_sleep_data(source="client")`` cannot be used at all
    there. This returns what an aggregate-only record does support.

    Returns one row per night with durations in hours, sorted by bedtime:

    ``sleep_start``, ``sleep_end``, ``total_sleep_h``, ``deep_h``, ``light_h``,
    ``rem_h``, ``awake_h``, ``efficiency_pct``, ``in_bed_h``

    Pair with :class:`~cgmsandbox.overlays.SleepWindowOverlay` and
    :class:`~cgmsandbox.extensions.SleepCompositionExtension`.
    """
    required = [
        "effective_time_frame_time_interval_start_date_time",
        "effective_time_frame_time_interval_end_date_time",
        "sleep_stage_summary_total_sleep_time_value",
    ]
    missing = [c for c in required if c not in client_df.columns]
    if missing:
        raise ValueError(
            "load_sleep_nights expects aggregate sleep-stage-summary columns; "
            f"missing {missing}. Available: {sorted(client_df.columns)}"
        )

    n = pd.DataFrame({
        "sleep_start": pd.to_datetime(
            client_df["effective_time_frame_time_interval_start_date_time"], utc=True, errors="coerce"),
        "sleep_end": pd.to_datetime(
            client_df["effective_time_frame_time_interval_end_date_time"], utc=True, errors="coerce"),
        "total_sleep_h": pd.to_numeric(
            client_df["sleep_stage_summary_total_sleep_time_value"], errors="coerce") / 3600.0,
        "deep_h": pd.to_numeric(
            client_df.get("sleep_stage_summary_deep_sleep_duration_value"), errors="coerce") / 3600.0,
        "light_h": pd.to_numeric(
            client_df.get("sleep_stage_summary_light_sleep_duration_value"), errors="coerce") / 3600.0,
        "rem_h": pd.to_numeric(
            client_df.get("sleep_stage_summary_rem_sleep_duration_value"), errors="coerce") / 3600.0,
        "efficiency_pct": pd.to_numeric(
            client_df.get("sleep_stage_summary_sleep_efficiency_percentage_value"), errors="coerce"),
    })
    n = n.dropna(subset=["sleep_start", "sleep_end"]).sort_values("sleep_start")
    n = n.reset_index(drop=True)
    n["in_bed_h"] = (n["sleep_end"] - n["sleep_start"]).dt.total_seconds() / 3600.0
    # 'awake' = in bed but not asleep, so the stage stack sums to the night length
    n["awake_h"] = (n["in_bed_h"] - n["total_sleep_h"]).clip(lower=0)
    return n


def load_step_count(client_df: pd.DataFrame) -> pd.DataFrame:
    """One row per day of step totals, from a JHE client frame.

    Study 30006 reports ``omh:step-count:3.0`` as a single record covering a whole
    local day (``descriptive_statistic`` "sum" over denominator "d"), so each row
    is a *daily total*, not an instantaneous reading. That is what makes a
    steps-per-day histogram the natural view, and what makes an intraday step
    trace impossible to reconstruct from this data.

    Parameters
    ----------
    client_df : pandas.DataFrame
        Frame from ``jh_client.list_observations_df(..., code=...)``, or the
        equivalent flattened CSV.

    Returns
    -------
    pandas.DataFrame
        Columns ``date`` (local calendar date), ``steps``, ``start``, ``end``
        (both tz-aware UTC), sorted by ``start``.
    """
    value_col = "step_count_value"
    if value_col not in client_df.columns:
        raise KeyError(
            f"column {value_col!r} not found -- this frame does not look like an "
            "omh:step-count:3.0 record set"
        )

    start_col = "effective_time_frame_time_interval_start_date_time"
    end_col = "effective_time_frame_time_interval_end_date_time"
    if start_col not in client_df.columns:
        # point-in-time shape rather than an interval: treat the reading as a
        # single-instant total so the caller still gets usable rows
        start_col = "effective_time_frame_date_time"
        end_col = start_col

    out = pd.DataFrame(
        {
            "steps": pd.to_numeric(client_df[value_col], errors="coerce"),
            "start": pd.to_datetime(client_df[start_col], utc=True, errors="coerce"),
            "end": pd.to_datetime(client_df[end_col], utc=True, errors="coerce"),
        }
    )

    # Prefer the record's own local start for the calendar date: the day a step
    # total belongs to is a local-time notion, and the client ships that column.
    local_col = "effective_time_frame_time_interval_start_date_time_local"
    if local_col in client_df.columns:
        local_start = pd.to_datetime(client_df[local_col], errors="coerce")
        out["date"] = local_start.dt.date.values
    else:
        out["date"] = out["start"].dt.date

    out = out.dropna(subset=["start", "steps"])
    return out.sort_values("start").reset_index(drop=True)
