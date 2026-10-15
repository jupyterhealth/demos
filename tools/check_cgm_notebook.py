#!/usr/bin/env python3
"""Stdlib-only structural checks for the regenerated CGM demo notebook."""

from __future__ import annotations

import json
from pathlib import Path

REQUIRED_TOKENS = (
    "SHOW_SCRIPTED_CHAT",
    "CGM_SESSION_GAP_HOURS",
    "JHE_STUDY_ID",
    "default_study_id",
    "detect_cgm_periods",
    "requested_view_name",
    "greeting_for_view",
    '"medications": []',
    '"treatment_options_under_review": True',
    "build_dashboard",
    "default_fhir_source_id",
    "default_synthetic_system",
    "default_practitioner_last_name",
    "FHIR_SOURCE_ID = int(default_fhir_source_id())",
    "SYNTHETIC_SYSTEM = default_synthetic_system()",
    "practitioner_last = default_practitioner_last_name()",
    "auxiliary = auxiliary_frame()",
    "def aux_latest(code):",
    "format_quantity",
    'if quantity.get("value") is None or when is None:',
    "assert_no_meal_sleep_overlaps",
    '"reference"',
    '"activity_context"',
    '"Elevated"',
    '"patient_source"',
    "def percentile_profile(recording, step_minutes=15):",
    '"percentiles": percentile_profile(recording)',
    '"sources": distinct_sources(recording["source"])',
    "def observation_source(resource):",
    '"source": observation_source(resource)',
    'columns=["code", "recorded_at", "value", "unit", "source"]',
    '"source": source',
    "explorer_sources = {",
    '"activity": distinct_sources(steps["source"])',
    '"meals": distinct_sources(meals["source"])',
    '"sleep": distinct_sources(sleep["source"])',
    '"sources": explorer_sources',
    '"timestamp": meal_timestamp_label(row.occurred_at)',
    '"context_cards": context_cards',
    "build_chat_data",
    'dashboard_view["chat"] = build_chat_data(',
    "from IPython.display import display",
    "from zoneinfo import ZoneInfo",
    "def preview(frame, name):",
    'display(frame.head(3))',
    'print("columns:", list(frame.columns))',
    'preview(recording, "selected CGM recording")',
    'preview(meals, "meals")',
    'preview(steps, "steps")',
    'preview(sleep, "sleep")',
    'preview(heart_rate, "heart rate")',
    'preview(blood_pressure, "blood pressure")',
    'preview(auxiliary, "auxiliary")',
)

FORBIDDEN_TOKENS = (
    "SHOW_FOLLOW_UP",
    "ALL_SESSION_WINDOWS",
    "ppgr_comparison",
    "PPGR_STEP_MINUTES",
    "agp_profile_figure",
    "session_bounds",
    "FHIR_SOURCE_ID = 90009",
    'SYNTHETIC_SYSTEM = "urn:jupyterhealth:synthetic:alex-k:2026"',
    'practitioner.get("lastName")',
    "recording = cgm.sort_values",
    "Dexcom Stelo",
    'provenance.get("source_name") or "Exchange"',
    "Oura Ring",
    "CareX",
    "EHR",
    "Continuous glucose monitor · latest recording",
    "Review the latest CGM recording alongside labs, vitals, and medications.",
    '"subtitle"',
    "Selected latest CGM period",
    '"Source ·"',
    "PATIENT_CHAT_STARTER",
    "PRACTITIONER_REPORT_NOTE",
    "PATIENT_SIMULATION_NOTE",
    "PRACTITIONER_SIMULATION_NOTE",
    "simulation_note",
    "report_note",
    "result_title",
    '"starter"',
    "Open MedBeam report",
    '"Open Med-BEAM report"',
    "medbeam-report.png",
    "MEDBEAM_APPOINTMENT_TEXT",
    "MEDBEAM_EXPLANATION",
    "MEDBEAM_REPORT_REL_PATH",
    "CLINICAL_ALGORITHM_REFERENCE_CUE",
    '"cue"',
    '"appointment"',
    '"medbeam_explanation"',
    "date_span",
    "family_history_values",
    '"family_history"',
    '"family-history-father-heart-attack"',
    "valueString",
    "The auxiliary clinical context is small, so fetch each exact synthetic code directly.",
    "The synthetic system and FHIR source are configurable for other studies.",
    'if view_name == "patient":',
)

PERIOD_FILTER_ASSIGNMENT = (
    "recording = (\n"
    '    cgm[(cgm["recorded_at"] >= period_start) & (cgm["recorded_at"] <= period_end)]\n'
)


def main() -> int:
    path = (
        Path(__file__).resolve().parents[1]
        / "dashboards"
        / "cgm-demo.ipynb"
    )
    notebook = json.loads(path.read_text())
    assert notebook.get("nbformat") == 4, "notebook is not nbformat 4"
    text = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
    )

    missing = [token for token in REQUIRED_TOKENS if token not in text]
    forbidden = [token for token in FORBIDDEN_TOKENS if token in text]

    if PERIOD_FILTER_ASSIGNMENT not in text:
        missing.append("recording assigned as filtered latest CGM period")

    if missing or forbidden:
        if missing:
            print(f"missing required tokens: {missing}")
        if forbidden:
            print(f"forbidden tokens present: {forbidden}")
        return 1

    print("cgm-demo.ipynb structural checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
