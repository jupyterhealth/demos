"""Offline tests for the dependency-free ``jupyterhealth_dashboard.core`` helpers."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta
from unittest import mock

from jupyterhealth_dashboard import core


class PeriodDetectionTests(unittest.TestCase):
    def test_empty_input(self):
        self.assertEqual(core.detect_cgm_periods([]), [])

    def test_single_contiguous_period(self):
        start = datetime(2026, 10, 1, 0, 0)
        stamps = [start + timedelta(minutes=5 * index) for index in range(12)]
        periods = core.detect_cgm_periods(stamps, gap_hours=24)
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0], (stamps[0], stamps[-1]))

    def test_gap_splits_periods_and_latest_is_last(self):
        start = datetime(2026, 10, 1, 0, 0)
        first = [start + timedelta(minutes=5 * index) for index in range(4)]
        second = [
            start + timedelta(hours=30) + timedelta(minutes=5 * index)
            for index in range(4)
        ]
        periods = core.detect_cgm_periods(first + second, gap_hours=24)
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[-1], (second[0], second[-1]))

    def test_gap_threshold_is_respected(self):
        start = datetime(2026, 10, 1, 0, 0)
        stamps = [start, start + timedelta(hours=12), start + timedelta(hours=23)]
        periods = core.detect_cgm_periods(stamps, gap_hours=24)
        self.assertEqual(len(periods), 1)
        periods = core.detect_cgm_periods(stamps, gap_hours=10)
        self.assertEqual(len(periods), 3)


class ConfigurationTests(unittest.TestCase):
    def test_default_gap_hours(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(core.default_gap_hours(), 24.0)

    def test_gap_hours_override(self):
        with mock.patch.dict(os.environ, {"CGM_SESSION_GAP_HOURS": "12.5"}, clear=True):
            self.assertEqual(core.default_gap_hours(), 12.5)

    def test_gap_hours_invalid_falls_back(self):
        with mock.patch.dict(os.environ, {"CGM_SESSION_GAP_HOURS": "nope"}, clear=True):
            self.assertEqual(core.default_gap_hours(), 24.0)

    def test_default_study_id(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(core.default_study_id(), 30014)

    def test_study_id_override(self):
        with mock.patch.dict(os.environ, {"JHE_STUDY_ID": "30006"}, clear=True):
            self.assertEqual(core.default_study_id(), 30006)

    def test_study_id_invalid_falls_back(self):
        with mock.patch.dict(os.environ, {"JHE_STUDY_ID": "abc"}, clear=True):
            self.assertEqual(core.default_study_id(), 30014)

    def test_default_fhir_source_id(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(core.default_fhir_source_id(), "90009")

    def test_fhir_source_id_override(self):
        with mock.patch.dict(os.environ, {"JHE_FHIR_SOURCE_ID": "90010"}, clear=True):
            self.assertEqual(core.default_fhir_source_id(), "90010")

    def test_fhir_source_id_invalid_falls_back(self):
        with mock.patch.dict(os.environ, {"JHE_FHIR_SOURCE_ID": "not-an-id"}, clear=True):
            self.assertEqual(core.default_fhir_source_id(), "90009")

    def test_default_synthetic_system(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                core.default_synthetic_system(),
                "urn:jupyterhealth:synthetic:alex-k:2026",
            )

    def test_synthetic_system_override(self):
        with mock.patch.dict(
            os.environ,
            {"JHE_AUXILIARY_SYSTEM": "urn:example:study:records"},
            clear=True,
        ):
            self.assertEqual(
                core.default_synthetic_system(),
                "urn:example:study:records",
            )

    def test_synthetic_system_blank_falls_back(self):
        with mock.patch.dict(os.environ, {"JHE_AUXILIARY_SYSTEM": "   "}, clear=True):
            self.assertEqual(
                core.default_synthetic_system(),
                "urn:jupyterhealth:synthetic:alex-k:2026",
            )

    def test_chat_flag_defaults_on(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertTrue(core.scripted_chat_enabled())

    def test_chat_flag_enabled(self):
        for value in ("1", "true", "TRUE", "yes", "on"):
            with mock.patch.dict(os.environ, {"SHOW_SCRIPTED_CHAT": value}, clear=True):
                self.assertTrue(core.scripted_chat_enabled(), value)

    def test_chat_flag_disabled_values(self):
        for value in ("0", "false", "no", "off", "maybe"):
            with mock.patch.dict(os.environ, {"SHOW_SCRIPTED_CHAT": value}, clear=True):
                self.assertFalse(core.scripted_chat_enabled(), value)


class ViewResolutionTests(unittest.TestCase):
    def test_default_practitioner(self):
        self.assertEqual(core.resolve_view_name(None), "practitioner")
        self.assertEqual(
            core.resolve_view_name("https://example.test/voila/render/x.ipynb"),
            "practitioner",
        )

    def test_patient_view(self):
        url = "https://example.test/voila/render/x.ipynb?view=patient"
        self.assertEqual(core.resolve_view_name(url), "patient")

    def test_practitioner_view(self):
        url = "https://example.test/voila/render/x.ipynb?view=practitioner"
        self.assertEqual(core.resolve_view_name(url), "practitioner")

    def test_unknown_view_falls_back(self):
        url = "https://example.test/voila/render/x.ipynb?view=admin"
        self.assertEqual(core.resolve_view_name(url), "practitioner")

    def test_misspelled_patient_does_not_silently_select_patient(self):
        url = "https://example.test/voila/render/x.ipynb?view=paitent"
        self.assertEqual(core.resolve_view_name(url), "practitioner")

    def test_query_value_is_case_and_whitespace_insensitive(self):
        self.assertEqual(
            core.resolve_view_name("https://example.test/x.ipynb?view=Patient"),
            "patient",
        )
        self.assertEqual(
            core.resolve_view_name("https://example.test/x.ipynb?view=  patient  "),
            "patient",
        )

    def test_blank_query_value_falls_back(self):
        self.assertEqual(
            core.resolve_view_name("https://example.test/x.ipynb?view="),
            "practitioner",
        )

    def test_resolution_is_pure_without_role_contamination(self):
        patient_url = "https://example.test/x.ipynb?view=patient"
        self.assertEqual(core.resolve_view_name(patient_url), "patient")
        self.assertEqual(core.resolve_view_name(None), "practitioner")
        self.assertEqual(core.resolve_view_name("https://example.test/x.ipynb?view=paitent"), "practitioner")
        self.assertEqual(core.resolve_view_name(patient_url), "patient")


class RoleHeadingTests(unittest.TestCase):
    def test_patient_greeting(self):
        self.assertEqual(core.patient_greeting("Alex"), "Hi Alex")

    def test_patient_greeting_missing_name(self):
        self.assertEqual(core.patient_greeting(None), "Hi Alex")
        self.assertEqual(core.patient_greeting("  "), "Hi Alex")

    def test_practitioner_greeting(self):
        self.assertEqual(core.practitioner_greeting("Kishore"), "Hi Dr. Kishore")

    def test_practitioner_greeting_missing_name(self):
        self.assertEqual(core.practitioner_greeting(None), "Hi Dr. Kishore")

    def test_practitioner_display_name_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(core.default_practitioner_last_name(), "Kishore")

    def test_practitioner_display_name_override(self):
        with mock.patch.dict(
            os.environ,
            {"DEMO_PRACTITIONER_LAST_NAME": "Nguyen"},
            clear=True,
        ):
            self.assertEqual(core.default_practitioner_last_name(), "Nguyen")
            self.assertEqual(
                core.greeting_for_view("practitioner"),
                "Hi Dr. Nguyen",
            )

    def test_greeting_for_view(self):
        self.assertEqual(core.greeting_for_view("patient", "Alex"), "Hi Alex")
        self.assertEqual(
            core.greeting_for_view("practitioner", "Alex", "Kishore"),
            "Hi Dr. Kishore",
        )
        self.assertEqual(
            core.greeting_for_view("practitioner"),
            "Hi Dr. Kishore",
        )


class MedicationPanelTests(unittest.TestCase):
    def test_no_active_medications(self):
        self.assertEqual(core.medication_status([]), "No active medications")

    def test_structured_medications(self):
        self.assertEqual(core.medication_status([{"name": "A"}] * 1), "1 active medication")
        self.assertEqual(core.medication_status([{}, {}]), "2 active medications")

    def test_treatment_review_constant(self):
        self.assertEqual(
            core.TREATMENT_OPTIONS_UNDER_REVIEW,
            "Treatment options under review",
        )


class QuantityFormattingTests(unittest.TestCase):
    def test_percentage_has_no_space_before_marker(self):
        self.assertEqual(core.format_quantity(6.2, "%", 1), "6.2%")
        self.assertEqual(core.format_quantity(7.0, "%", 1), "7.0%")
        self.assertEqual(core.format_quantity(98.5, "%", 1), "98.5%")

    def test_spaced_clinical_units_are_preserved(self):
        self.assertEqual(core.format_quantity(112.0, "mg/dL", 0), "112 mg/dL")
        self.assertEqual(core.format_quantity(128.0, "mmHg", 0), "128 mmHg")

    def test_missing_value_is_truthful(self):
        self.assertEqual(core.format_quantity(None, "%", 1), "n/a")


class DistinctSourceTests(unittest.TestCase):
    def test_trims_dedupes_and_drops_blank_names_in_first_seen_order(self):
        self.assertEqual(
            core.distinct_sources(
                [" Dexcom Stelo ", "Dexcom Stelo", "", "   ", "Oura Ring"]
            ),
            ["Dexcom Stelo", "Oura Ring"],
        )

    def test_missing_and_blank_only_names_yield_no_line(self):
        self.assertEqual(core.distinct_sources([]), [])
        self.assertEqual(core.distinct_sources([None, "", " "]), [])

    def test_non_string_values_are_coerced_to_safe_text(self):
        self.assertEqual(core.distinct_sources([None, 42]), ["42"])


class ChatFlagHidingTests(unittest.TestCase):
    def test_hidden_when_disabled(self):
        view = {"show_scripted_chat": False, "chat": {"summary_lines": []}}
        self.assertFalse(core.include_scripted_chat(view))

    def test_hidden_when_chat_missing(self):
        view = {"show_scripted_chat": True}
        self.assertFalse(core.include_scripted_chat(view))

    def test_shown_when_enabled(self):
        view = {"show_scripted_chat": True, "chat": {"summary_lines": []}}
        self.assertTrue(core.include_scripted_chat(view))


class ScriptedChatStructureTests(unittest.TestCase):
    def test_patient_starter_is_exact(self):
        self.assertEqual(
            core.PATIENT_CHAT_STARTER,
            "One of my sushi meals had a much sharper response than another one. Why is that?",
        )

    def test_practitioner_summary_is_three_lines(self):
        self.assertEqual(len(core.PRACTITIONER_SUMMARY_LINES), 3)
        self.assertIn("amlodipine/valsartan", core.PRACTITIONER_SUMMARY_LINES[0].lower())
        self.assertIn("valsartan/hctz", core.PRACTITIONER_SUMMARY_LINES[0].lower())
        self.assertNotIn("prescribed", " ".join(core.PRACTITIONER_SUMMARY_LINES).lower())

    def test_fallback_is_deterministic(self):
        self.assertEqual(core.scripted_sushi_fallback(), core.scripted_sushi_fallback())

    def test_fallback_isolates_two_sushi_meals_and_walk(self):
        analysis = core.scripted_sushi_fallback()
        self.assertEqual(len(analysis["meals"]), 2)
        self.assertEqual(len(analysis["traces"]), 2)
        self.assertEqual(len(analysis["activity"]), 2)
        self.assertTrue(any(meal["had_walk"] for meal in analysis["meals"]))
        walked = next(meal for meal in analysis["meals"] if meal["had_walk"])
        not_walked = next(meal for meal in analysis["meals"] if not meal["had_walk"])
        self.assertLess(walked["spike_mg_dl"], not_walked["spike_mg_dl"])
        self.assertLess(walked["iauc_mg_dl_min"], not_walked["iauc_mg_dl_min"])
        for meal in analysis["meals"]:
            self.assertIsInstance(meal["iauc_mg_dl_min"], (int, float))
            self.assertEqual(meal["timestamp"], "Synthetic demo")
            self.assertIsNone(meal["occurred_at"])
        self.assertEqual(len(analysis["minutes"]), len(analysis["traces"][0]["glucose"]))

    def test_unavailable_analysis_is_honest_and_empty(self):
        analysis = core.unavailable_sushi_analysis()
        self.assertEqual(analysis["meals"], [])
        self.assertEqual(analysis["minutes"], [])
        self.assertEqual(analysis["traces"], [])
        self.assertEqual(analysis["activity"], [])
        self.assertEqual(
            analysis["explanation"],
            core.UNAVAILABLE_SUSHI_EXPLANATION,
        )

    def test_presentation_helpers_are_dependency_free(self):
        self.assertEqual(core.meal_display_label("Synthetic sushi dinner"), "Sushi dinner")
        self.assertEqual(core.meal_display_label(None), "Meal")
        self.assertEqual(core.meal_timestamp_label(None), "Synthetic demo")
        moment = datetime(2026, 10, 15, 18, 30)
        self.assertIn("Oct 15, 2026", core.meal_timestamp_label(moment))

    def test_meal_comparison_explanation_uses_calculated_values(self):
        walked = {
            "label": "Sushi dinner (post-meal walk)",
            "spike_mg_dl": 52,
            "iauc_mg_dl_min": 1200,
        }
        not_walked = {
            "label": "Sushi dinner (no walk)",
            "spike_mg_dl": 98,
            "iauc_mg_dl_min": 2400,
        }
        explanation = core.meal_comparison_explanation(walked, not_walked)
        self.assertIn("Sushi dinner (post-meal walk)", explanation)
        self.assertIn("52 mg/dL", explanation)
        self.assertIn("98 mg/dL", explanation)
        self.assertIn("not proof that the walk caused it", explanation)

    def test_report_link_constants_are_exact(self):
        self.assertEqual(core.REPORT_LINK_LABEL, "UC HTN Way 3.0 Report")
        self.assertFalse(hasattr(core, "CLINICAL_ALGORITHM_REFERENCE_CUE"))


class ReportPathTests(unittest.TestCase):
    def test_report_destination_is_the_supplied_box_link(self):
        self.assertEqual(
            core.UC_HTN_REPORT_URL,
            "https://ucop.app.box.com/s/e3g0eozjbl8s7ueyp9nk8bo4quzzikp0",
        )


class RequestedViewNameTests(unittest.TestCase):
    def test_query_derived_when_no_env_override(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(core.requested_view_name(None), "practitioner")
            self.assertEqual(
                core.requested_view_name("https://example.test/x.ipynb?view=patient"),
                "patient",
            )

    def test_env_fallback_only_without_explicit_view_query(self):
        with mock.patch.dict(os.environ, {"JHE_VIEW": "patient"}, clear=True):
            self.assertEqual(core.requested_view_name(None), "patient")
            self.assertEqual(core.requested_view_name("https://example.test/x.ipynb"), "patient")
            self.assertEqual(
                core.requested_view_name("https://example.test/x.ipynb?view=practitioner"),
                "practitioner",
            )
            self.assertEqual(
                core.requested_view_name("https://example.test/x.ipynb?view=paitent"),
                "practitioner",
            )
            self.assertEqual(
                core.requested_view_name("https://example.test/x.ipynb?view="),
                "practitioner",
            )

    def test_invalid_env_override_falls_back_to_query(self):
        with mock.patch.dict(os.environ, {"JHE_VIEW": "admin"}, clear=True):
            self.assertEqual(core.requested_view_name(None), "practitioner")
            self.assertEqual(
                core.requested_view_name("https://example.test/x.ipynb?view=patient"),
                "patient",
            )

    def test_misspelled_query_falls_back_without_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                core.requested_view_name("https://example.test/x.ipynb?view=paitent"),
                "practitioner",
            )


class MealSleepOverlapTests(unittest.TestCase):
    def test_no_overlap_when_meals_between_sleep(self):
        sleep = [
            (datetime(2026, 10, 1, 23, 0), datetime(2026, 10, 2, 7, 0)),
            (datetime(2026, 10, 2, 23, 0), datetime(2026, 10, 3, 7, 0)),
        ]
        meals = [datetime(2026, 10, 2, 8, 0), datetime(2026, 10, 2, 12, 30)]
        self.assertEqual(core.find_meal_sleep_overlaps(meals, sleep), [])
        self.assertEqual(core.assert_no_meal_sleep_overlaps(meals, sleep), [])

    def test_overlap_is_detected(self):
        sleep = [(datetime(2026, 10, 1, 23, 0), datetime(2026, 10, 2, 7, 0))]
        meals = [datetime(2026, 10, 2, 2, 15)]
        overlaps = core.find_meal_sleep_overlaps(meals, sleep)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(overlaps[0][0], meals[0])

    def test_assert_raises_on_overlap(self):
        sleep = [(datetime(2026, 10, 1, 23, 0), datetime(2026, 10, 2, 7, 0))]
        meals = [datetime(2026, 10, 2, 2, 15)]
        with self.assertRaises(ValueError):
            core.assert_no_meal_sleep_overlaps(meals, sleep)


class ChatScriptClassificationTests(unittest.TestCase):
    def test_patient_exact_sushi_prompt(self):
        self.assertEqual(
            core.classify_chat_intent("patient", core.PATIENT_CHAT_STARTER),
            "sushi",
        )

    def test_patient_sushi_mention_matches_case_insensitively(self):
        self.assertEqual(
            core.classify_chat_intent("patient", "Why did one SUSHI meal spike higher?"),
            "sushi",
        )
        self.assertEqual(
            core.classify_chat_intent("patient", "I really like sushi"),
            "sushi",
        )

    def test_patient_reference_intent(self):
        self.assertEqual(
            core.classify_chat_intent("patient", "What is the reference range for glucose?"),
            "reference",
        )
        self.assertEqual(
            core.classify_chat_intent("patient", "what does elevated mean"),
            "reference",
        )

    def test_patient_biomarker_meaning_and_hba1c_intents(self):
        self.assertEqual(core.classify_chat_intent("patient", "What does a biomarker mean?"), "biomarker")
        self.assertEqual(core.classify_chat_intent("patient", "What is HbA1c?"), "hba1c")
        self.assertEqual(core.classify_chat_intent("patient", "Explain my A1c"), "hba1c")

    def test_patient_medbeam_and_referral_input_is_not_routed(self):
        self.assertIsNone(
            core.classify_chat_intent("patient", "review my panels for a Med-BEAM appointment")
        )
        self.assertIsNone(core.classify_chat_intent("patient", "prepare a referral"))
        self.assertIsNone(core.classify_chat_intent("patient", "book an appointment"))

    def test_patient_unsupported_prompt(self):
        self.assertIsNone(core.classify_chat_intent("patient", "hello"))
        self.assertIsNone(core.classify_chat_intent("patient", "What did I eat yesterday?"))

    def test_practitioner_unsupported_prompt(self):
        self.assertIsNone(core.classify_chat_intent("practitioner", "Summarize the Med-BEAM report"))
        self.assertIsNone(core.classify_chat_intent("practitioner", "what time is it"))
        self.assertIsNone(core.classify_chat_intent("practitioner", "Open the report"))

    def test_staged_steps_contain_required_states(self):
        patient_steps = " ".join(core.chat_staged_steps("patient", "sushi"))
        for word in ("Thinking", "Locating", "Isolating", "Comparing"):
            self.assertIn(word, patient_steps)
        self.assertNotIn("sushi", patient_steps.lower())
        self.assertEqual(core.chat_staged_steps("patient", "reference"), ())
        self.assertEqual(core.chat_staged_steps("patient", "medbeam"), ())
        self.assertEqual(core.chat_staged_steps("practitioner", "summarize"), ())

    def test_demo_limitation_is_generic_and_truthful(self):
        patient = core.chat_demo_limitation("patient")
        practitioner = core.chat_demo_limitation("practitioner")
        self.assertNotIn("prototype", patient.lower())
        self.assertNotIn("prototype", practitioner.lower())
        self.assertIn("reference ranges", patient)
        self.assertIn("sushi", patient)
        self.assertNotIn("Med-BEAM", patient)
        self.assertNotIn("appointment", patient.lower())
        self.assertNotIn("summarize", practitioner.lower())
        self.assertNotIn("Med-BEAM", practitioner)

    def test_capability_copy_is_role_aware(self):
        patient_caps = " ".join(core.patient_capabilities()).lower()
        practitioner_caps = " ".join(core.practitioner_capabilities()).lower()
        self.assertIn("reference ranges", patient_caps)
        self.assertIn("elevated biomarkers", patient_caps)
        self.assertNotIn("med-beam", patient_caps)
        self.assertIn("sushi meals", patient_caps)
        self.assertIn("glucose and activity", patient_caps)
        self.assertIn("uc htn way 3.0", practitioner_caps)


if __name__ == "__main__":
    unittest.main()
