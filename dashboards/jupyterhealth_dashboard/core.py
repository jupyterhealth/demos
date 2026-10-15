"""Dependency-free helpers for the CGM demo notebook.

This module intentionally imports only the standard library. It holds the small,
testable pieces of behaviour that the notebook and the presentation layer share:

* environment configuration and defaults;
* contiguous CGM period detection;
* role-view resolution and greetings;
* the deterministic scripted-chat copy and fallback structure.

The notebook remains the owner of all Exchange retrieval, decoding,
normalisation, and metric calculation; the presentation modules remain the
owner of layout and drawing. This module is only the glue that both can import
without pulling in pandas, plotly, or ipywidgets.
"""

from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

DEFAULT_STUDY_ID = 30014
DEFAULT_GAP_HOURS = 24.0

PATIENT_VIEW = "patient"
PRACTITIONER_VIEW = "practitioner"
_KNOWN_VIEWS = {PATIENT_VIEW, PRACTITIONER_VIEW}

UNAVAILABLE_SUSHI_EXPLANATION = (
    "I couldn't find two comparable sushi meals with complete glucose and activity "
    "records in this CGM period."
)

# Canonical example used by tests as a sushi-mentioning patient prompt. It is
# intentionally no longer shown as an onboarding starter.
PATIENT_CHAT_STARTER = (
    "One of my sushi meals had a much sharper response than another one. Why is that?"
)

PRACTITIONER_SUMMARY_LINES = (
    "Amlodipine/valsartan modeled faster blood-pressure control than valsartan/HCTZ over 26 weeks.",
    "It provides more time under blood-pressure control over 26 weeks.",
    "Compare adverse effects and patient circumstances before any decision.",
)

SYNTHETIC_DISCLOSURE = "Synthetic demo — not a real patient record."

NO_ACTIVE_MEDICATIONS = "No active medications"
TREATMENT_OPTIONS_UNDER_REVIEW = "Treatment options under review"

PATIENT_CHAT_STEPS = (
    "Thinking…",
    "Locating the highlighted meals…",
    "Isolating the glucose and activity windows…",
    "Comparing the post-meal responses…",
    "Preparing the result…",
)

# Local link contract for the practitioner report-delivery feed. The path is
# relative to the rendered notebook route, which lives in
# ``dashboards/cgm-demo.ipynb``. The package directory beside that notebook is
# ``jupyterhealth_dashboard``, so the local asset must be reached through that
# prefix. The attached hypertension algorithm image is vendored at
# ``dashboards/jupyterhealth_dashboard/assets/uc-way-htn-algorithm.png`` and is
# served by Voilà's default ``file_allowlist`` (it already permits PNG images).
UC_HTN_ALGORITHM_REL_PATH = "jupyterhealth_dashboard/assets/uc-way-htn-algorithm.png"

# Practitioner report-delivery copy.
REPORT_LINK_LABEL = "UC HTN Way 3.0 Report"

def scripted_chat_enabled() -> bool:
    """Whether the deterministic demo chat should be rendered."""
    return os.getenv("SHOW_SCRIPTED_CHAT", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def default_gap_hours() -> float:
    """Contiguous-CGM gap threshold from the environment, defaulting to 24 hours."""
    raw = os.getenv("CGM_SESSION_GAP_HOURS", str(DEFAULT_GAP_HOURS))
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_GAP_HOURS
    return value if value > 0 else DEFAULT_GAP_HOURS


def default_study_id() -> int:
    """Study id from the environment, falling back to the local demo study."""
    raw = os.getenv("JHE_STUDY_ID", str(DEFAULT_STUDY_ID))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return DEFAULT_STUDY_ID


def default_fhir_source_id() -> str:
    """FHIR source id from the environment, falling back to the local demo source."""
    fallback = "90009"
    raw = os.getenv("JHE_FHIR_SOURCE_ID", fallback).strip()
    try:
        int(raw)
    except (TypeError, ValueError):
        return fallback
    return raw


def default_synthetic_system() -> str:
    """Synthetic auxiliary code system, configurable per study or deployment."""
    fallback = "urn:jupyterhealth:synthetic:alex-k:2026"
    raw = os.getenv("JHE_AUXILIARY_SYSTEM", fallback).strip()
    return raw or fallback


def distinct_sources(values) -> list:
    """Trim, de-duplicate, and drop blank CGM recording source names.

    The dashboard shows the recording's own device/source name(s) --- derived
    from the selected recording, never a hardcoded brand or the FHIR ingestion
    provenance. Names are coerced to text, stripped of surrounding whitespace,
    emptied values are dropped, and the first occurrence of each distinct name
    is kept in the order the recording recorded them.
    """
    if values is None:
        return []
    names: list = []
    for value in values:
        if value is None:
            continue
        name = str(value).strip()
        if not name or name in names:
            continue
        names.append(name)
    return names


def resolve_view_name(raw_url: str | None = None, default: str = PRACTITIONER_VIEW) -> str:
    """Resolve the requested role view from a Voilà request URL.

    The query value is normalized and matched exactly against the known roles.
    Absent, blank, invalid, or misspelled values fall back to ``default`` so a
    malformed query (such as ``?view=paitent``) can never silently select a role.
    """
    if not raw_url:
        return default
    try:
        query = urlsplit(raw_url).query
    except (TypeError, ValueError, AttributeError):
        return default
    values = parse_qs(query).get("view", [])
    if not values:
        return default
    name = (values[0] or "").strip().lower()
    return name if name in _KNOWN_VIEWS else default


def requested_view_name(
    raw_url: str | None = None, default: str = PRACTITIONER_VIEW
) -> str:
    """Resolve the role for this render deterministically.

    The hosted Berkeley deployment keeps the query-derived ``view=`` parameter as
    the authoritative source. Local Voilà review without a query can set the
    ``JHE_VIEW`` environment variable (``patient`` or ``practitioner``) to force a
    deterministic role instead of relying on the default practitioner fallback.
    An explicit query takes precedence over the local-only fallback, including
    malformed values (which fail closed to the default role). This lets one Voilà
    process serve both roles without leaking a prior render's role.
    """
    if raw_url and "view" in parse_qs(urlsplit(raw_url).query, keep_blank_values=True):
        return resolve_view_name(raw_url, default=default)
    env_view = os.getenv("JHE_VIEW", "").strip().lower()
    if env_view in _KNOWN_VIEWS:
        return env_view
    return resolve_view_name(raw_url, default=default)


def detect_cgm_periods(timestamps, gap_hours: float = DEFAULT_GAP_HOURS) -> list:
    """Split timestamps into contiguous runs separated by more than ``gap_hours``.

    Each returned item is a ``(start, end)`` tuple taken from the timestamps
    themselves, so the notebook can use the *actual* bounds of the latest
    recording rather than a hard-coded calendar window.
    """
    ordered = sorted(timestamps)
    if not ordered:
        return []

    threshold = timedelta(hours=float(gap_hours))
    periods: list = []
    start = ordered[0]
    previous = ordered[0]
    for moment in ordered[1:]:
        if moment - previous > threshold:
            periods.append((start, previous))
            start = moment
        previous = moment
    periods.append((start, previous))
    return periods


def patient_greeting(given_name: str | None = None, fallback: str = "Alex") -> str:
    """Patient-facing greeting, safe when the given name is missing."""
    name = (given_name or "").strip() or fallback
    return f"Hi {name}"


def practitioner_greeting(last_name: str | None = None, fallback: str = "Kishore") -> str:
    """Practitioner-facing greeting, safe when the surname is missing."""
    name = (last_name or "").strip() or fallback
    return f"Hi Dr. {name}"


def default_practitioner_last_name() -> str:
    """Display surname for the scripted practitioner greeting.

    The demo must show ``Hi Dr. Kishore`` regardless of the authenticated
    user's unrelated surname. Deployments that want the greeting to follow a
    real user can set ``DEMO_PRACTITIONER_LAST_NAME`` explicitly.
    """
    fallback = "Kishore"
    raw = os.getenv("DEMO_PRACTITIONER_LAST_NAME", fallback).strip()
    return raw or fallback


def greeting_for_view(
    view_name: str,
    patient_given: str | None = None,
    practitioner_last: str | None = None,
) -> str:
    """Return the role greeting for ``view_name``."""
    if view_name == PATIENT_VIEW:
        return patient_greeting(patient_given)
    return practitioner_greeting(practitioner_last or default_practitioner_last_name())


def find_meal_sleep_overlaps(meal_times, sleep_intervals) -> list:
    """Return ``(meal_time, sleep_start, sleep_end)`` for every meal inside sleep.

    Both ``meal_times`` and ``sleep_intervals`` are compared at the timestamp level.
    ``sleep_intervals`` is an iterable of ``(start, end)`` pairs. A meal exactly on a
    sleep boundary is also reported because a review-safe timeline must leave a
    buffer after wake and before sleep rather than merely avoiding strict interior
    overlap.
    """
    overlaps = []
    for meal_time in meal_times:
        for start, end in sleep_intervals:
            if start <= meal_time <= end:
                overlaps.append((meal_time, start, end))
    return overlaps


def assert_no_meal_sleep_overlaps(meal_times, sleep_intervals) -> list:
    """Assert that no meal timestamp falls inside a sleep interval.

    Returns an empty list when valid. Raises :class:`ValueError` with the first
    offending pair when the canonical data is inconsistent, so the dashboard fails
    clearly instead of painting an impossible timeline.
    """
    overlaps = find_meal_sleep_overlaps(meal_times, sleep_intervals)
    if overlaps:
        meal_time, start, end = overlaps[0]
        raise ValueError(
            "Meal/sleep data overlap in the selected period: "
            f"{len(overlaps)} meal timestamp(s) fall inside a sleep interval; "
            f"first is {meal_time} inside {start} -> {end}. Refusing to render an "
            "inconsistent timeline."
        )
    return overlaps


def patient_capabilities() -> tuple[str, ...]:
    """Exact deterministic actions the patient role can complete."""
    return (
        "Answer questions about reference ranges and what elevated biomarkers mean.",
        "Review the displayed blood pressure, HbA1c, and other lab values.",
        "Compare sensor insights across glucose and activity for the logged sushi meals.",
    )


def practitioner_capabilities() -> tuple[str, ...]:
    """Exact deterministic actions the practitioner role can complete."""
    return ("Open the attached UC HTN Way 3.0 clinical algorithm reference.",)


def capabilities_for_role(role: str | None = None) -> tuple[str, ...]:
    """Return the deterministic capability copy for ``role``."""
    if role == PATIENT_VIEW:
        return patient_capabilities()
    return practitioner_capabilities()


# Natural-language intent matching for the patient composer. Sushi, HbA1c,
# biomarker-meaning, and reference ranges are deliberate regex "mentions" so
# paraphrases work without pretending the demo understands free text.
# Misspelled or unrelated input falls through to a truthful fallback. The
# practitioner feed has no composer, so only patient intents are matched.
_SUSHI_RE = re.compile(r"\bsushi\b", re.IGNORECASE)
_HBA1C_RE = re.compile(r"\b(?:hba1c|a1c)\b", re.IGNORECASE)
_BIOMARKER_MEANING_RE = re.compile(
    r"\b(?:what (?:is|does)|define|meaning of)\b.{0,30}\bbiomarker\b|\bbiomarker\b.{0,20}\bmean\b",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"\b(reference|ranges?|elevated|biomarkers?|meaning|lab|labs|normal)\b",
    re.IGNORECASE,
)


def patient_sushi_intent(normalized: str) -> bool:
    """Return whether a normalized patient prompt mentions sushi."""
    return bool(_SUSHI_RE.search(normalized or ""))


def classify_chat_intent(role: str, text: str | None) -> str | None:
    """Map a typed composer prompt to a deterministic demo intent, or ``None``."""
    normalized = " ".join((text or "").strip().lower().split())
    if not normalized:
        return None

    if role != PATIENT_VIEW:
        return None
    if _SUSHI_RE.search(normalized):
        return "sushi"
    if _HBA1C_RE.search(normalized):
        return "hba1c"
    if _BIOMARKER_MEANING_RE.search(normalized):
        return "biomarker"
    if _REFERENCE_RE.search(normalized):
        return "reference"
    return None


def unavailable_sushi_analysis() -> dict:
    """Honest empty structure returned when the period lacks two comparable meals."""
    return {
        "meals": [],
        "minutes": [],
        "traces": [],
        "activity": [],
        "explanation": UNAVAILABLE_SUSHI_EXPLANATION,
    }


def meal_display_label(label: str | None) -> str:
    """Drop the generator's ``Synthetic`` prefix and sentence-case a meal label."""
    text = str(label or "").removeprefix("Synthetic ").strip() or "Meal"
    return text[:1].upper() + text[1:]


def meal_timestamp_label(moment: datetime | None) -> str:
    """Format a meal timestamp for the scripted comparison, or the demo fallback."""
    if moment is None:
        return "Synthetic demo"
    return moment.strftime("%b %-d, %Y · %-I:%M %p")


def meal_comparison_explanation(walked: dict, not_walked: dict) -> str:
    """Return the role-neutral, data-grounded explanation for the two-meal comparison."""
    return (
        "The two sushi dinners had the same logged composition. "
        f"{walked['label']} was followed by a qualifying post-meal walk, and its recorded "
        f"glucose rise ({walked['spike_mg_dl']:.0f} mg/dL above baseline) and iAUC "
        f"({walked['iauc_mg_dl_min']:,.0f} mg·min/dL) were lower than "
        f"{not_walked['label']} ({not_walked['spike_mg_dl']:.0f} mg/dL above baseline, "
        f"{not_walked['iauc_mg_dl_min']:,.0f} mg·min/dL). The lower response is an observed "
        "association with the walk, not proof that the walk caused it."
    )


def chat_staged_steps(role: str, intent: str | None = None) -> tuple:
    """Return the role/intent-specific staged thinking steps."""
    if role == PATIENT_VIEW and intent == "sushi":
        return PATIENT_CHAT_STEPS
    return ()


def chat_demo_limitation(role: str | None = None) -> str:
    """Professional role-specific reply for unsupported composer input.

    This states the exact deterministic actions without implying a live model,
    so the transcript stays truthful even after the onboarding surface has been
    dismissed.
    """
    if role == PATIENT_VIEW:
        return (
            "I can answer questions about reference ranges and elevated biomarkers, or "
            "compare your logged sushi meals. Try typing “sushi” or “reference ranges”."
        )
    return "This feed delivers the attached report; there is no text composer."


def medication_status(medications) -> str:
    """Human-readable active-medication status.

    ``medications`` is the list of future structured medication entries. An empty
    list is the current demo state and must render the explicit cue rather than
    implying the data was simply missing.
    """
    if not medications:
        return NO_ACTIVE_MEDICATIONS
    return f"{len(medications)} active medication{'s' if len(medications) != 1 else ''}"


def format_quantity(value: float | int | None, unit: str = "", decimals: int = 0) -> str:
    """Format a clinical value with unit-aware spacing.

    Percentage values are the compact ``6.2%`` form, while non-empty units such as
    ``mg/dL`` and ``mmHg`` retain a separating space. ``None`` values render the same
    truthful missing-data cue used by the rest of the dashboard.
    """
    if value is None:
        return "n/a"
    unit = (unit or "").strip()
    if unit == "%":
        return f"{value:.{decimals}f}%"
    if unit:
        return f"{value:.{decimals}f} {unit}"
    return f"{value:.{decimals}f}"


def include_scripted_chat(view: dict) -> bool:
    """Whether ``build_dashboard`` should render the scripted chat section."""
    return bool(view.get("show_scripted_chat")) and bool(view.get("chat"))


def _fallback_minutes() -> list[int]:
    return list(range(-30, 181, 5))


def _fallback_glucose(spike: float) -> list[float]:
    baseline = 114.0
    values = []
    for minute in _fallback_minutes():
        if minute < 0:
            value = baseline
        else:
            value = baseline + spike * math.exp(-((minute - 55) / 28.0) ** 2)
            value -= spike * 0.16 * minute / 180.0
        values.append(round(value, 1))
    return values


def _fallback_walk_steps() -> list[float]:
    return [90.0 if 8 <= minute <= 23 else 0.0 for minute in _fallback_minutes()]


def _positive_iauc(
    minutes: list[int],
    glucose: list[float],
    baseline: float,
    end_minutes: int = 120,
) -> float:
    """Trapezoidal positive incremental AUC above baseline over 0..``end_minutes``.

    Increments below baseline are floored at zero, matching the notebook's primary
    iAUC definition, and the returned value is in ``mg·min/dL``.
    """
    points = [(m, g) for m, g in zip(minutes, glucose) if 0 <= m <= end_minutes]
    total = 0.0
    for (m0, g0), (m1, g1) in zip(points, points[1:]):
        increment0 = max(0.0, g0 - baseline)
        increment1 = max(0.0, g1 - baseline)
        total += (increment0 + increment1) * (m1 - m0) / 2.0
    return round(total, 1)


def scripted_sushi_fallback() -> dict:
    """Deterministic fallback used when the period lacks two matching sushi meals.

    The real notebook path derives these values from the displayed meal, activity,
    and CGM records. This structure exists so the demo chat never depends on data
    quality. It carries no invented meal timestamps; the synthetic nature is
    explicit in ``timestamp`` and ``source``.
    """
    minutes = _fallback_minutes()
    baseline = 114.0
    no_walk_glucose = _fallback_glucose(98.0)
    walk_glucose = _fallback_glucose(52.0)
    meals = [
        {
            "label": "Sushi dinner (no walk)",
            "timestamp": "Synthetic demo",
            "occurred_at": None,
            "had_walk": False,
            "peak_mg_dl": 212,
            "spike_mg_dl": 98,
            "iauc_mg_dl_min": _positive_iauc(minutes, no_walk_glucose, baseline),
        },
        {
            "label": "Sushi dinner (post-meal walk)",
            "timestamp": "Synthetic demo",
            "occurred_at": None,
            "had_walk": True,
            "peak_mg_dl": 166,
            "spike_mg_dl": 52,
            "iauc_mg_dl_min": _positive_iauc(minutes, walk_glucose, baseline),
        },
    ]
    return {
        "meals": meals,
        "minutes": minutes,
        "traces": [
            {"label": meals[0]["label"], "glucose": no_walk_glucose},
            {"label": meals[1]["label"], "glucose": walk_glucose},
        ],
        "activity": [
            {"label": meals[0]["label"], "steps": [0.0] * len(minutes)},
            {"label": meals[1]["label"], "steps": _fallback_walk_steps()},
        ],
        "source": "synthetic demonstration CGM, meal, and step records",
        "explanation": (
            "The two sushi dinners had the same logged composition. "
            "Sushi dinner (post-meal walk) was followed by a qualifying post-meal walk, and its "
            "recorded glucose rise and iAUC were lower than Sushi dinner (no walk)'s; the lower "
            "response is an observed association with the walk, not proof that the walk caused it."
        ),
    }
