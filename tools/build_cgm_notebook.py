#!/usr/bin/env python3
"""Regenerate ``dashboards/cgm-demo.ipynb`` from the cell sources below.

This script is stdlib-only and is run once during development; it is not part of
the served dashboard.
"""

from __future__ import annotations

import json
from pathlib import Path

CELL_0 = '''import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from IPython.display import display

from jupyterhealth_client import JupyterHealthClient

from jupyterhealth_dashboard.chat import build_chat_data
from jupyterhealth_dashboard.core import (
    assert_no_meal_sleep_overlaps,
    default_fhir_source_id,
    default_gap_hours,
    default_practitioner_last_name,
    default_study_id,
    default_synthetic_system,
    detect_cgm_periods,
    distinct_sources,
    format_quantity,
    greeting_for_view,
    meal_comparison_explanation,
    meal_display_label,
    meal_timestamp_label,
    requested_view_name,
    scripted_chat_enabled,
    unavailable_sushi_analysis,
)
from jupyterhealth_dashboard.ui import build_dashboard

# The SMART launch context is authoritative when present. Outside a SMART launch the local
# demo falls back to a fixed patient so the notebook can still be opened directly.
try:
    from provider_app import jhe_auth, launch_context

    ctx = launch_context.current()
except Exception:
    client = JupyterHealthClient()
    PATIENT_ID = 40032
    patient = client.get_patient(PATIENT_ID)
    patient_source = "local demo fallback"
else:
    client = jhe_auth.client_for_launch(ctx)
    patient = client.lookup_patient(
        external_id=ctx.patient_mrn,
        system=os.getenv("MRN_IDENTIFIER_SYSTEM"),
    )
    if patient is None:
        raise RuntimeError(
            "SMART launch could not resolve the selected patient; refusing to render another patient."
        )
    PATIENT_ID = patient["id"]
    patient_source = "SMART launch"

view_name = requested_view_name(os.environ.get("VOILA_REQUEST_URL"))
# JHE_STUDY_ID overrides the local 30014 demo fallback.
STUDY_ID = default_study_id()
CGM_SESSION_GAP_HOURS = default_gap_hours()
SHOW_SCRIPTED_CHAT = scripted_chat_enabled()

patient_given = str(patient.get("nameGiven") or "").strip()
patient_family = str(patient.get("nameFamily") or "").strip()
# The scripted demo heading is intentionally not tied to the authenticated
# user's surname; keep the display override defaulting to Dr. Kishore.
practitioner_last = default_practitioner_last_name()

heading = greeting_for_view(view_name, patient_given, practitioner_last)
'''


CELL_1 = '''# Configuration and full-history Exchange retrieval -------------------------------------
STUDY_TIMEZONE = ZoneInfo("America/Los_Angeles")
FHIR_SOURCE_ID = int(default_fhir_source_id())
EXCHANGE_URL = os.environ["JHE_URL"]

study = client.get_study(STUDY_ID)

# The eight mapped-Observation families this dashboard reads, as Open mHealth / IEEE codes.
OMH = "https://w3id.org/openmhealth"
IEEE = "https://w3id.org/ieee1752"
CODE_BLOOD_GLUCOSE = "omh:blood-glucose:4.0"
CODE_STEP_COUNT = "omh:step-count:3.0"
CODE_HEART_RATE = "omh:heart-rate:2.0"
CODE_FOOD_ENTRY = "ieee:food-entry:0.1"
CODE_SLEEP_EPISODE = "ieee:sleep-episode:1.0"
CODE_BODY_WEIGHT = "omh:body-weight:3.0"
CODE_BODY_HEIGHT = "omh:body-height:2.0"
CODE_BLOOD_PRESSURE = "omh:blood-pressure:4.0"
FAMILY_SYSTEMS = {
    CODE_BLOOD_GLUCOSE: OMH,
    CODE_STEP_COUNT: OMH,
    CODE_HEART_RATE: OMH,
    CODE_FOOD_ENTRY: IEEE,
    CODE_SLEEP_EPISODE: IEEE,
    CODE_BODY_WEIGHT: OMH,
    CODE_BODY_HEIGHT: OMH,
    CODE_BLOOD_PRESSURE: OMH,
}
# Sparse clinical context is fetched over the full history. The CGM-anchored modalities are
# fetched separately and clipped to the selected CGM period below.
STATIC_FAMILY_CODES = {CODE_BODY_WEIGHT, CODE_BODY_HEIGHT, CODE_BLOOD_PRESSURE}
CGM_ANCHORED_CODES = {CODE_STEP_COUNT, CODE_HEART_RATE, CODE_FOOD_ENTRY, CODE_SLEEP_EPISODE}
MAX_QUERY_WORKERS = 4
OBSERVATION_URL = f"{EXCHANGE_URL}/FHIR/R5/Observation"


def fhir_observations(code, system, start=None, end=None, source=None):
    """Fetch one exact-code Observation search, safely following all pages."""
    params = [
        ("patient", str(PATIENT_ID)),
        ("patient._has:Group:member:_id", str(STUDY_ID)),
        ("code", f"{system}|{code}"),
        ("_count", "1000"),
    ]
    if source is not None:
        params.append(("_source", source))
    if start is not None and end is not None:
        params.extend([
            ("date", f"ge{start.isoformat()}"),
            ("date", f"lt{(end + timedelta(days=1)).isoformat()}"),
        ])

    resources = []
    page = 1
    while True:
        response = client.session.get(
            OBSERVATION_URL, params=[*params, ("_page", str(page))], timeout=60
        )
        response.raise_for_status()
        bundle = response.json()
        resources.extend(
            entry["resource"] for entry in bundle.get("entry", []) if "resource" in entry
        )
        if not any(link.get("relation") == "next" for link in bundle.get("link", [])):
            return resources
        page += 1


def unique_resources(resources):
    by_id = {resource.get("id"): resource for resource in resources}
    return [by_id[resource_id] for resource_id in sorted(by_id, key=str)]


# Full-history anchors: CGM (to identify periods), sparse clinical context, and the small
# auxiliary synthetic record set. No hard-coded calendar window is applied here.
families = {code: [] for code in FAMILY_SYSTEMS}
full_history_codes = [CODE_BLOOD_GLUCOSE, *sorted(STATIC_FAMILY_CODES)]
with ThreadPoolExecutor(max_workers=MAX_QUERY_WORKERS) as executor:
    full_history_pages = list(
        executor.map(
            lambda code: fhir_observations(code, FAMILY_SYSTEMS[code]),
            full_history_codes,
        )
    )
for code, resources in zip(full_history_codes, full_history_pages):
    families[code] = unique_resources(resources)

SYNTHETIC_SYSTEM = default_synthetic_system()
AUXILIARY_CODES = (
    "source-demographics",
    "hba1c",
    "fasting_glucose",
    "heart-rate-variability-rmssd",
    "body-mass-index",
)
fhir_source = f"https://jupyterhealth.org/fhir/fhir-source/{FHIR_SOURCE_ID}"
with ThreadPoolExecutor(max_workers=MAX_QUERY_WORKERS) as executor:
    auxiliary_pages = list(
        executor.map(
            lambda code: fhir_observations(code, SYNTHETIC_SYSTEM, source=fhir_source),
            AUXILIARY_CODES,
        )
    )
auxiliary_observations = unique_resources(
    resource for resources in auxiliary_pages for resource in resources
)
'''


CELL_2 = '''## Decode raw records into data frames

def decode_attachments(resources):
    decoded = []
    for resource in resources:
        payload = json.loads(base64.b64decode(resource["valueAttachment"]["data"]))
        decoded.append(
            {"id": resource["id"], "header": payload["header"], "body": payload["body"]}
        )
    return decoded


def local_time(text):
    value = datetime.fromisoformat(str(text))
    return value if value.tzinfo else value.replace(tzinfo=STUDY_TIMEZONE)


def source_name(item):
    provenance = item["header"].get("acquisition_provenance") or {}
    return str(provenance.get("source_name") or "")


def observation_source(resource):
    device = resource.get("device")
    if isinstance(device, dict):
        return str(device.get("display") or "")
    if isinstance(device, list) and device:
        first = device[0] or {}
        if isinstance(first, dict):
            return str(first.get("display") or "")
    return ""


def frame(rows, time_column="recorded_at", columns=None):
    data = pd.DataFrame(rows, columns=columns)
    if not data.empty:
        data[time_column] = pd.to_datetime(data[time_column])
        data = data.sort_values(time_column).reset_index(drop=True)
    return data


def cgm_frame():
    rows = []
    for item in decode_attachments(families[CODE_BLOOD_GLUCOSE]):
        body = item["body"]
        rows.append({
            "recorded_at": local_time(body["effective_time_frame"]["date_time"]),
            "mg_dl": float(body["blood_glucose"]["value"]),
            "source": source_name(item),
        })
    return frame(rows, columns=["recorded_at", "mg_dl", "source"])


def steps_frame():
    rows = []
    for item in decode_attachments(families[CODE_STEP_COUNT]):
        body = item["body"]
        interval = body["effective_time_frame"]["time_interval"]
        rows.append({
            "recorded_at": local_time(interval["start_date_time"]),
            "steps": int(body["step_count"]["value"]),
            "source": source_name(item),
        })
    return frame(rows, columns=["recorded_at", "steps", "source"])


def meals_frame():
    rows = []
    for item in decode_attachments(families[CODE_FOOD_ENTRY]):
        body = item["body"]
        rows.append({
            "meal_id": item["id"],
            "occurred_at": local_time(body["effective_time_frame"]["date_time"]),
            "label": str(body.get("food_name") or "Meal"),
            "meal_type": str(body.get("meal") or "meal"),
            "carbohydrate_g": float((body.get("carbohydrate") or {}).get("value") or 0),
            "protein_g": float((body.get("protein") or {}).get("value") or 0),
            "fat_g": float((body.get("fat") or {}).get("value") or 0),
            "fiber_g": float((body.get("fiber") or {}).get("value") or 0),
            "calories_kcal": float((body.get("calories") or {}).get("value") or 0),
            "source": source_name(item),
        })
    data = frame(
        rows,
        "occurred_at",
        columns=[
            "meal_id", "occurred_at", "label", "meal_type", "carbohydrate_g",
            "protein_g", "fat_g", "fiber_g", "calories_kcal", "source",
        ],
    )
    data["recorded_at"] = data["occurred_at"]
    return data


def sleep_frame():
    rows = []
    for item in decode_attachments(families[CODE_SLEEP_EPISODE]):
        body = item["body"]
        interval = body["effective_time_frame"]["time_interval"]
        rows.append({
            "night_id": item["id"],
            "start_at": local_time(interval["start_date_time"]),
            "end_at": local_time(interval["end_date_time"]),
            "recorded_at": local_time(interval["end_date_time"]),
            "total_sleep_minutes": float((body.get("total_sleep_time") or {}).get("value") or 0),
            "efficiency_percent": float(
                (body.get("sleep_efficiency_percentage") or {}).get("value") or 0
            ),
            "deep_minutes": float((body.get("deep_sleep_duration") or {}).get("value") or 0),
            "light_minutes": float((body.get("light_sleep_duration") or {}).get("value") or 0),
            "rem_minutes": float((body.get("rem_sleep_duration") or {}).get("value") or 0),
            "awakenings": int(body.get("number_of_awakenings") or 0),
            "source": source_name(item),
        })
    return frame(
        rows,
        columns=[
            "night_id", "start_at", "end_at", "recorded_at", "total_sleep_minutes",
            "efficiency_percent", "deep_minutes", "light_minutes", "rem_minutes",
            "awakenings", "source",
        ],
    )


def heart_rate_frame():
    rows = []
    for item in decode_attachments(families[CODE_HEART_RATE]):
        body = item["body"]
        rows.append({
            "recorded_at": local_time(body["effective_time_frame"]["date_time"]),
            "bpm": float(body["heart_rate"]["value"]),
            "source": source_name(item),
        })
    return frame(rows, columns=["recorded_at", "bpm", "source"])


def body_frame(code, key):
    rows = []
    for item in decode_attachments(families[code]):
        body = item["body"]
        rows.append({
            "recorded_at": local_time(body["effective_time_frame"]["date_time"]),
            "value": float(body[key]["value"]),
            "unit": str(body[key].get("unit") or ""),
            "source": source_name(item),
        })
    return frame(rows, columns=["recorded_at", "value", "unit", "source"])


def blood_pressure_frame():
    rows = []
    for item in decode_attachments(families[CODE_BLOOD_PRESSURE]):
        body = item["body"]
        rows.append({
            "recorded_at": local_time(body["effective_time_frame"]["date_time"]),
            "systolic_mm_hg": float(body["systolic_blood_pressure"]["value"]),
            "diastolic_mm_hg": float(body["diastolic_blood_pressure"]["value"]),
            "source": source_name(item),
        })
    return frame(rows, columns=["recorded_at", "systolic_mm_hg", "diastolic_mm_hg", "source"])


def auxiliary_frame():
    rows = []
    for resource in auxiliary_observations:
        coding = (resource.get("code") or {}).get("coding") or [{}]
        quantity = resource.get("valueQuantity") or {}
        when = resource.get("effectiveDateTime")
        if quantity.get("value") is None or when is None:
            continue
        rows.append({
            "code": coding[0].get("code"),
            "recorded_at": local_time(when),
            "value": float(quantity["value"]),
            "unit": str(quantity.get("unit") or ""),
            "source": observation_source(resource),
        })
    return frame(rows, columns=["code", "recorded_at", "value", "unit", "source"])


def demographic_values():
    values = {}
    for resource in auxiliary_observations:
        coding = (resource.get("code") or {}).get("coding") or [{}]
        if coding[0].get("code") != "source-demographics":
            continue
        for component in resource.get("component") or []:
            component_coding = (component.get("code") or {}).get("coding") or [{}]
            code = component_coding[0].get("code")
            if code == "age-years":
                values["age_years"] = int(component["valueQuantity"]["value"])
            elif code == "administrative-sex":
                gender_coding = (
                    (component.get("valueCodeableConcept") or {}).get("coding") or [{}]
                )
                values["gender"] = str(gender_coding[0].get("code") or "").lower()
    return values
'''


CELL_3 = '''## Decode the full-history anchors and select the latest CGM period

cgm = cgm_frame()
weights = body_frame(CODE_BODY_WEIGHT, "body_weight")
heights = body_frame(CODE_BODY_HEIGHT, "body_height")
blood_pressure = blood_pressure_frame()
auxiliary = auxiliary_frame()
demographics = demographic_values()

if cgm.empty:
    raise RuntimeError(
        f"No CGM observations found for patient {PATIENT_ID} in study {STUDY_ID}; "
        "nothing to render."
    )

cgm_periods = detect_cgm_periods(cgm["recorded_at"], gap_hours=CGM_SESSION_GAP_HOURS)
period_start, period_end = cgm_periods[-1]
period_label = f"{period_start:%b %-d} – {period_end:%b %-d, %Y}"
'''


CELL_4 = '''## Fetch and clip the CGM-associated modalities to the selected period

def date_chunks(code, start, end):
    if code == CODE_STEP_COUNT:
        # Minute-level steps are day-chunked to keep each FHIR search small.
        day = start.date()
        last_day = end.date()
        while day <= last_day:
            yield day, day
            day += timedelta(days=1)
    else:
        yield start.date(), end.date()


jobs = [
    (code, FAMILY_SYSTEMS[code], chunk_start, chunk_end)
    for code in sorted(CGM_ANCHORED_CODES)
    for chunk_start, chunk_end in date_chunks(code, period_start, period_end)
]
with ThreadPoolExecutor(max_workers=MAX_QUERY_WORKERS) as executor:
    modality_pages = list(
        executor.map(
            lambda job: fhir_observations(job[0], job[1], job[2], job[3]),
            jobs,
        )
    )
for (code, _, _, _), resources in zip(jobs, modality_pages):
    families[code].extend(resources)
for code in CGM_ANCHORED_CODES:
    families[code] = unique_resources(families[code])

steps = steps_frame()
meals = meals_frame()
sleep = sleep_frame()
heart_rate = heart_rate_frame()

# Clip to the actual bounds of the latest contiguous CGM period.
steps = steps[(steps["recorded_at"] >= period_start) & (steps["recorded_at"] <= period_end)].reset_index(drop=True)
meals = meals[(meals["occurred_at"] >= period_start) & (meals["occurred_at"] <= period_end)].reset_index(drop=True)
heart_rate = heart_rate[(heart_rate["recorded_at"] >= period_start) & (heart_rate["recorded_at"] <= period_end)].reset_index(drop=True)
sleep = sleep[(sleep["start_at"] >= period_start) & (sleep["end_at"] <= period_end)].reset_index(drop=True)
'''


CELL_5 = '''## Calculate the report metrics for the selected period

BAND_KEYS = ("very_low", "low", "target", "high", "very_high")
VERY_LOW_BOUND = 54.0
LOW_BOUND = 70.0
TARGET_HIGH = 180.0
HIGH_BOUND = 250.0
GMI_INTERCEPT = 3.31
GMI_SLOPE = 0.02392


def mean_glucose(values):
    return round(float(values.mean()), 1) if len(values) else None


def gmi_percent(values):
    return round(GMI_INTERCEPT + GMI_SLOPE * float(values.mean()), 1) if len(values) else None


def coefficient_of_variation(values):
    if len(values) < 2:
        return None
    return round(float(values.std(ddof=1) / values.mean() * 100), 1)


def time_active(recording):
    stamps = sorted(set(recording["recorded_at"]))
    if not stamps:
        return None
    if len(stamps) == 1:
        return 100.0
    expected = int((stamps[-1] - stamps[0]).total_seconds() // 300) + 1
    return round(min(100.0, len(stamps) / expected * 100), 1)


def time_in_ranges(values):
    counts = {key: 0 for key in BAND_KEYS}
    total = len(values)
    for value in values:
        if value < VERY_LOW_BOUND:
            counts["very_low"] += 1
        elif value < LOW_BOUND:
            counts["low"] += 1
        elif value <= TARGET_HIGH:
            counts["target"] += 1
        elif value <= HIGH_BOUND:
            counts["high"] += 1
        else:
            counts["very_high"] += 1
    return {key: (round(counts[key] / total * 100, 1) if total else 0.0) for key in BAND_KEYS}


def percentile_profile(recording, step_minutes=15):
    """Aggregate the latest period into a genuine 24-hour percentile profile.

    Every sample is binned by its study-local time of day, and the 5/25/50/75/95
    percentiles are derived from the observed samples in each bin. Missing bins
    are omitted rather than filled in with invented series.
    """
    buckets = {}
    for moment, value in zip(recording["recorded_at"], recording["mg_dl"]):
        bucket = (moment.hour * 60 + moment.minute) // step_minutes * step_minutes
        buckets.setdefault(bucket, []).append(float(value))
    profile = []
    for minute in sorted(buckets):
        series = pd.Series(sorted(buckets[minute]))
        profile.append({
            "minute": minute,
            "p05": round(float(series.quantile(0.05)), 1),
            "p25": round(float(series.quantile(0.25)), 1),
            "p50": round(float(series.quantile(0.50)), 1),
            "p75": round(float(series.quantile(0.75)), 1),
            "p95": round(float(series.quantile(0.95)), 1),
        })
    return profile


# Every metric, displayed CGM trace, meal/sleep/activity clip, and scripted-chat
# derivation must use only the selected latest period. The full-history ``cgm``
# frame remains available solely for period detection.
recording = (
    cgm[(cgm["recorded_at"] >= period_start) & (cgm["recorded_at"] <= period_end)]
    .sort_values("recorded_at")
    .reset_index(drop=True)
)
values = recording["mg_dl"]

glucose_summary = {
    "period": period_label,
    # The CGM source badges come from the selected recording's own device/source name(s),
    # not a hardcoded brand and not the FHIR ingestion provenance.
    "sources": distinct_sources(recording["source"]),
    "time_active_percent": time_active(recording),
    "metrics": {
        "mean_mg_dl": mean_glucose(values),
        "gmi_percent": gmi_percent(values),
        "cv_percent": coefficient_of_variation(values),
    },
    "bands": [
        {"key": key, "percent": percent}
        for key, percent in time_in_ranges(values).items()
    ],
    "percentiles": percentile_profile(recording),
}
'''


CELL_6 = '''## Latest labs and vitals

def latest(points):
    ordered = sorted(points, key=lambda item: item[0])
    return ordered[-1] if ordered else None


def aux_latest(code):
    rows = auxiliary[auxiliary["code"] == code]
    return latest(list(zip(rows["recorded_at"], rows["value"], rows["source"])))


def when(moment):
    return moment.strftime("%b %-d, %Y") if moment is not None else "date not recorded"


def in_range_status(value, low, high):
    if value < low:
        return "low", "Below range"
    if value > high:
        return "high", "Elevated"
    return "in_range", "In range"


def format_reference(low, high, unit):
    if unit == "%":
        return f"{low:g}–{high:g}%"
    return f"{low:g}–{high:g} {unit}".strip()


def context_card(label, value, unit, status, status_label, icon, moment=None, decimals=1, reference="", source=""):
    return {
        "label": label,
        "value": format_quantity(value, unit, decimals),
        "date": when(moment),
        "status": status,
        "status_label": status_label,
        "icon": icon,
        "reference": reference,
        "source": source,
    }


hba1c = aux_latest("hba1c")
fasting = aux_latest("fasting_glucose")
hrv = aux_latest("heart-rate-variability-rmssd")
bmi = aux_latest("body-mass-index")
weight = latest(list(zip(weights["recorded_at"], weights["value"], weights["source"])))
height = latest(list(zip(heights["recorded_at"], heights["value"], heights["source"])))
bp = latest(
    list(
        zip(
            blood_pressure["recorded_at"],
            blood_pressure["systolic_mm_hg"],
            blood_pressure["diastolic_mm_hg"],
            blood_pressure["source"],
        )
    )
)


def measured_card(points, label, unit, icon, decimals=1, low=None, high=None):
    if points is None:
        return None
    moment, value = points[0], points[1]
    source = points[2] if len(points) > 2 else ""
    if low is not None and high is not None:
        status, status_label = in_range_status(value, low, high)
        reference = format_reference(low, high, unit)
    else:
        status, status_label = "na", "Informational"
        reference = "Reference varies"
    return context_card(label, value, unit, status, status_label, icon, moment, decimals, reference, source)


def blood_pressure_card():
    if bp is None:
        return None
    moment, systolic, diastolic = bp[0], bp[1], bp[2]
    source = bp[3] if len(bp) > 3 else ""
    status = "high" if (systolic >= 130 or diastolic >= 80) else "in_range"
    status_label = "Elevated" if status == "high" else "In range"
    return {
        "label": "Blood pressure",
        "value": f"{systolic:.0f}/{diastolic:.0f} mmHg",
        "date": when(moment),
        "status": status,
        "status_label": status_label,
        "icon": "bp",
        "reference": "<130/80 mmHg",
        "source": source,
    }


context_cards = [
    card
    for card in (
        measured_card(hba1c, "HbA1c", "%", "hba1c", 1, 4.0, 5.6),
        measured_card(fasting, "Fasting glucose", "mg/dL", "glucose", 0, 70, 99),
        measured_card(hrv, "HRV (RMSSD)", "ms", "hrv", 0),
        measured_card(bmi, "BMI", "kg/m²", "bmi", 1, 18.5, 24.9),
        blood_pressure_card(),
        measured_card(weight, "Weight", "kg", "weight", 1),
        measured_card(height, "Height", "cm", "height", 1),
    )
    if card is not None
]
'''


CELL_7 = '''## Prepare the trace and dashboard view

ACTIVITY_BUCKET_MINUTES = 30
ACTIVITY_CONTEXT_WINDOW_MINUTES = 60


def activity_buckets(rows):
    if rows.empty:
        return pd.DataFrame(columns=["bucket_at", "steps"])
    return (
        rows.assign(bucket_at=rows["recorded_at"].dt.floor(f"{ACTIVITY_BUCKET_MINUTES}min"))
        .groupby("bucket_at", as_index=False)["steps"].sum()
        .sort_values("bucket_at")
        .reset_index(drop=True)
    )


# A review-safe timeline never paints a meal over sleep. Assert the canonical
# data is consistent before rendering rather than silently hiding a visual overlap.
assert_no_meal_sleep_overlaps(
    meals["occurred_at"].tolist(),
    list(zip(sleep["start_at"], sleep["end_at"])),
)


def meal_activity_context(occurred_at, steps_frame):
    if steps_frame.empty:
        return "No activity recorded"
    end = occurred_at + timedelta(minutes=ACTIVITY_CONTEXT_WINDOW_MINUTES)
    nearby = steps_frame[
        (steps_frame["recorded_at"] >= occurred_at)
        & (steps_frame["recorded_at"] <= end)
    ]
    total = int(nearby["steps"].sum()) if not nearby.empty else 0
    if total:
        return f"~{total} steps in {ACTIVITY_CONTEXT_WINDOW_MINUTES} min after meal"
    return "No activity recorded"


meal_context = [
    meal_activity_context(row.occurred_at, steps) for row in meals.itertuples()
]
meal_rows = meals[
    [
        "occurred_at",
        "label",
        "meal_type",
        "carbohydrate_g",
        "protein_g",
        "fat_g",
        "fiber_g",
        "calories_kcal",
    ]
].copy()
meal_rows["activity_context"] = meal_context


explorer_sources = {
    "glucose": distinct_sources(recording["source"]),
    "meals": distinct_sources(meals["source"]),
    "activity": distinct_sources(steps["source"]),
    "sleep": distinct_sources(sleep["source"]),
}


explorer = {
    "name": "latest_period",
    "label": period_label,
    "glucose": recording[["recorded_at", "mg_dl"]].copy(),
    "meals": meal_rows.reset_index(drop=True),
    "activity": activity_buckets(steps),
    "sleep": sleep[
        [
            "start_at",
            "end_at",
            "deep_minutes",
            "light_minutes",
            "rem_minutes",
            "efficiency_percent",
            "total_sleep_minutes",
        ]
    ].reset_index(drop=True),
    "sources": explorer_sources,
}


def initials(name):
    return "".join(part[0] for part in name.split() if part)[:2].upper()


birth_date_text = str(patient.get("birthDate") or "1989-02-14")
birth_date = datetime.fromisoformat(birth_date_text).date()
report_date = period_end.date()
calculated_age = report_date.year - birth_date.year - (
    (report_date.month, report_date.day) < (birth_date.month, birth_date.day)
)
age_years = int(demographics.get("age_years") or calculated_age)
display_gender = str(
    demographics.get("gender") or patient.get("gender") or "male"
).strip().lower()

patient_name = " ".join(part for part in [patient_given, patient_family] if part) or "Alex K."

dashboard_view = {
    "role": view_name,
    "heading": heading,
    "patient": {
        "name": patient_name,
        "initials": initials(patient_name),
        "facts": [
            f"{age_years} years · {display_gender}",
            f"MRN {patient['id']}",
        ],
    },
    "context_cards": context_cards,
    "medications": [],
    "treatment_options_under_review": True,
    "glucose": glucose_summary,
    "explorer": explorer,
    "show_scripted_chat": SHOW_SCRIPTED_CHAT,
    "provenance": {
        "study": f"{study['name']} ({study['id']})",
        "fhir_source_id": FHIR_SOURCE_ID,
        "patient_source": patient_source,
    },
}
'''


CELL_8 = '''## Prepare the scripted-chat data (numeric meal traces only)

MEAL_STEP_MINUTES = 5
MEAL_OFFSETS = tuple(range(-30, 181, MEAL_STEP_MINUTES))
WALK_WINDOW_MINUTES = 10
WALK_MIN_BIN_STEPS = 60
WALK_MIN_TOTAL_STEPS = 700


def glucose_by_time():
    return dict(zip(recording["recorded_at"], recording["mg_dl"].astype(float)))


def steps_by_time():
    return dict(zip(steps["recorded_at"], steps["steps"].astype(float)))


def walk_after_meal(start, activity):
    for delay in range(16):
        window = [
            activity.get(start + timedelta(minutes=delay + offset), 0.0)
            for offset in range(WALK_WINDOW_MINUTES)
        ]
        enough_bins = sum(value >= WALK_MIN_BIN_STEPS for value in window) >= 8
        if enough_bins and sum(window) >= WALK_MIN_TOTAL_STEPS:
            return True
    return False


def trace_for_meal(start, glucose_map):
    points = []
    for minute in MEAL_OFFSETS:
        moment = start + timedelta(minutes=minute)
        value = glucose_map.get(moment)
        if value is None:
            candidates = [
                (abs((ts - moment).total_seconds()), reading)
                for ts, reading in glucose_map.items()
                if abs((ts - moment).total_seconds()) <= 150
            ]
            if not candidates:
                return None
            value = min(candidates)[1]
        points.append({"minute": minute, "glucose": float(value)})
    return points


def positive_iauc(trace, baseline, end_minutes=120):
    """Trapezoidal positive incremental AUC above baseline over 0..120 minutes."""
    points = [point for point in trace if 0 <= point["minute"] <= end_minutes]
    total = 0.0
    for earlier, later in zip(points, points[1:]):
        increment0 = max(0.0, earlier["glucose"] - baseline)
        increment1 = max(0.0, later["glucose"] - baseline)
        total += (increment0 + increment1) * (later["minute"] - earlier["minute"]) / 2.0
    return round(total, 1)


def scripted_sushi_analysis():
    glucose_map = glucose_by_time()
    activity_map = steps_by_time()

    sushi = meals[meals["label"].str.contains("sushi", case=False, na=False)]
    sushi = sushi.sort_values("occurred_at").tail(2)
    if len(sushi) < 2:
        return unavailable_sushi_analysis()

    built = []
    for row in sushi.itertuples():
        trace = trace_for_meal(row.occurred_at, glucose_map)
        if trace is None:
            return unavailable_sushi_analysis()
        pre = [point["glucose"] for point in trace if point["minute"] <= 0]
        post = [point["glucose"] for point in trace if point["minute"] >= 0]
        baseline = sum(pre) / len(pre)
        peak = max(post)
        activity_trace = [
            activity_map.get(row.occurred_at + timedelta(minutes=minute), 0.0)
            for minute in MEAL_OFFSETS
        ]
        built.append({
            "label": meal_display_label(row.label),
            "occurred_at": row.occurred_at.isoformat(),
            "timestamp": meal_timestamp_label(row.occurred_at),
            "had_walk": walk_after_meal(row.occurred_at, activity_map),
            "baseline_mg_dl": round(baseline, 1),
            "peak_mg_dl": round(peak, 1),
            "spike_mg_dl": round(peak - baseline, 1),
            "iauc_mg_dl_min": positive_iauc(trace, baseline),
            "glucose": [point["glucose"] for point in trace],
            "steps": activity_trace,
        })

    walk_meals = [meal for meal in built if meal["had_walk"]]
    no_walk_meals = [meal for meal in built if not meal["had_walk"]]
    if not walk_meals or not no_walk_meals:
        return unavailable_sushi_analysis()

    meals_out = no_walk_meals[:1] + walk_meals[:1]
    walked = meals_out[1]
    not_walked = meals_out[0]
    return {
        "meals": [
            {
                "label": meal["label"],
                "occurred_at": meal["occurred_at"],
                "timestamp": meal["timestamp"],
                "had_walk": meal["had_walk"],
                "peak_mg_dl": meal["peak_mg_dl"],
                "spike_mg_dl": meal["spike_mg_dl"],
                "iauc_mg_dl_min": meal["iauc_mg_dl_min"],
            }
            for meal in meals_out
        ],
        "minutes": list(MEAL_OFFSETS),
        "traces": [
            {"label": meal["label"], "glucose": meal["glucose"]} for meal in meals_out
        ],
        "activity": [
            {"label": meal["label"], "steps": meal["steps"]} for meal in meals_out
        ],
        "source": "synthetic demonstration CGM, meal, and step records",
        "explanation": meal_comparison_explanation(walked, not_walked),
    }


if SHOW_SCRIPTED_CHAT:
    dashboard_view["chat"] = build_chat_data(
        view_name,
        scripted_sushi_analysis,
        context_cards,
    )
'''


CELL_9 = '''## Inspect the results (hidden in Voilà)

if os.environ.get("VOILA_REQUEST_URL"):
    def preview(frame, name):
        pass
else:
    def preview(frame, name):
        print(f"{name}: shape={frame.shape}")
        print("columns:", list(frame.columns))
        display(frame.head(3))

preview(recording, "selected CGM recording")
preview(meals, "meals")
preview(steps, "steps")
preview(sleep, "sleep")
preview(heart_rate, "heart rate")
preview(weights, "weight")
preview(heights, "height")
preview(blood_pressure, "blood pressure")
preview(auxiliary, "auxiliary")
preview(pd.DataFrame(context_cards), "labs and vitals")
'''


CELL_10 = '''## Build the dashboard

dashboard = build_dashboard(dashboard_view)
display(dashboard)
'''


CELLS = [
    ("code", CELL_0),
    ("code", CELL_1),
    ("code", CELL_2),
    ("code", CELL_3),
    ("code", CELL_4),
    ("code", CELL_5),
    ("code", CELL_6),
    ("code", CELL_7),
    ("code", CELL_8),
    ("code", CELL_9),
    ("code", CELL_10),
]


def main() -> None:
    notebook = {
        "cells": [
            {
                "cell_type": cell_type,
                "execution_count": None,
                "id": str(index),
                "metadata": {},
                "outputs": [],
                "source": source.splitlines(keepends=True),
            }
            for index, (cell_type, source) in enumerate(CELLS)
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "codemirror_mode": {"name": "ipython", "version": 3},
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.12.14",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    target = (
        Path(__file__).resolve().parents[1]
        / "dashboards"
        / "cgm-demo.ipynb"
    )
    target.write_text(json.dumps(notebook, indent=1) + "\n")
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
