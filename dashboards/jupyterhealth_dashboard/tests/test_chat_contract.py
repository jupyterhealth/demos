"""Offline contracts for the floating deterministic scripted chat."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from jupyterhealth_dashboard import core

try:
    import ipywidgets as widgets

    from jupyterhealth_dashboard import chat

    HAS_CHAT = True
except Exception:  # pragma: no cover - dependency-specific environment
    HAS_CHAT = False


CHAT_PATH = Path(__file__).resolve().parents[1] / "chat.py"
THEME_PATH = Path(__file__).resolve().parents[1] / "theme.css"


def _css_rule(css: str, selector: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(selector)} \{{[^{{}}]*\}}")
    match = pattern.search(css)
    if not match:
        raise AssertionError(f"selector not found: {selector}")
    return match.group(0)


def _css_rules(css: str) -> list[str]:
    return re.findall(r"(?m)^[^{}]+?\{[^{}]*\}", css)


class ChatSourceContractTests(unittest.TestCase):
    def test_chat_uses_local_icons_and_no_cdn_or_emoji(self):
        source = CHAT_PATH.read_text()
        self.assertNotIn("threading.Thread", source)
        self.assertNotIn("http://", source)
        self.assertNotIn("https://", source)
        self.assertNotIn("cdn", source.lower())
        self.assertIn("icon_background", source)
        self.assertIn("render_icon", source)
        self.assertIn("classify_chat_intent", source)

    def test_chat_declares_floating_chrome_and_typing_composer(self):
        source = CHAT_PATH.read_text()
        self.assertIn("jh-chat-launcher", source)
        self.assertIn("jh-chat-panel", source)
        self.assertIn("Textarea", source)
        self.assertIn("continuous_update=True", source)
        self.assertIn('panel.layout.display = "none"', source)

    def test_chat_has_no_suggestion_buttons(self):
        source = CHAT_PATH.read_text()
        self.assertNotIn("jh-chat-suggestion", source)
        self.assertNotIn("suggested_prompts_for_role", source)

    def test_no_enter_to_send_hint_remains(self):
        source = CHAT_PATH.read_text()
        css = THEME_PATH.read_text()
        self.assertNotIn("Enter to send", source)
        self.assertNotIn("jh-chat-hint", source)
        self.assertNotIn(".jh-chat-hint", css)


def _patient_chat() -> dict:
    analysis = core.scripted_sushi_fallback()
    return {
        "analysis": analysis,
        "context_cards": [
            {
                "label": "Fasting glucose",
                "value": "112 mg/dL",
                "reference": "70–99 mg/dL",
                "status": "high",
                "status_label": "Elevated",
            },
            {
                "label": "HbA1c",
                "value": "6.2%",
                "reference": "4.0–5.6%",
                "status": "high",
                "status_label": "Elevated",
            },
        ],
        "explanation": analysis["explanation"],
    }


def _practitioner_chat() -> dict:
    return {
        "report": {
            "label": core.REPORT_LINK_LABEL,
            "href": core.UC_HTN_REPORT_URL,
        },
        "summary_lines": list(core.PRACTITIONER_SUMMARY_LINES),
    }


@unittest.skipUnless(HAS_CHAT, "ipywidgets/plotly are not installed in this interpreter")
class ChatPlanContractTests(unittest.TestCase):
    def test_build_chat_data_wires_patient_analysis_without_extra_copy(self):
        analysis = core.scripted_sushi_fallback()
        chat_data = chat.build_chat_data("patient", analysis, _patient_chat()["context_cards"])
        self.assertEqual(chat_data["analysis"], analysis)
        self.assertEqual(chat_data["context_cards"], _patient_chat()["context_cards"])
        self.assertEqual(chat_data["explanation"], analysis["explanation"])
        self.assertNotIn("report", chat_data)

    def test_build_chat_data_defers_meal_analysis_for_clinician(self):
        def forbidden_analysis():
            raise AssertionError("Clinician report must not calculate patient meal analysis")

        chat_data = chat.build_chat_data("practitioner", forbidden_analysis, [])
        self.assertNotIn("analysis", chat_data)
        self.assertEqual(chat_data["report"]["label"], core.REPORT_LINK_LABEL)

    def test_build_chat_data_accepts_lazy_patient_analysis(self):
        calls = []
        def analysis():
            calls.append(True)
            return {"meals": [], "explanation": "No comparable meals"}

        chat_data = chat.build_chat_data("patient", analysis, [])
        self.assertEqual(calls, [True])
        self.assertEqual(chat_data["analysis"]["explanation"], "No comparable meals")

    def test_build_chat_data_wires_practitioner_report_without_composer_data(self):
        chat_data = chat.build_chat_data("practitioner", core.scripted_sushi_fallback(), [])
        self.assertEqual(chat_data["report"]["label"], core.REPORT_LINK_LABEL)
        self.assertEqual(chat_data["report"]["href"], core.UC_HTN_REPORT_URL)
        self.assertEqual(chat_data["summary_lines"], list(core.PRACTITIONER_SUMMARY_LINES))
        self.assertNotIn("analysis", chat_data)
        self.assertNotIn("context_cards", chat_data)

    def test_patient_plan_contains_staged_states_and_result(self):
        plan = chat.plan_response("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        joined = "".join(plan)
        for token in ("Thinking", "Locating", "Isolating", "Comparing"):
            self.assertIn(token, joined)
        self.assertIn("jh-chat-stage", joined)
        self.assertIn("Sushi dinner (no walk)", joined)
        self.assertNotIn("Thursday, October 15", joined)
        self.assertNotIn("Med-BEAM", joined)
        self.assertNotIn("prototype", joined.lower())

    def test_patient_result_contains_side_by_side_visualization_panels(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        rendered = plan.result
        self.assertIn("jh-chat-meal-grid", rendered)
        self.assertEqual(rendered.count("jh-chat-meal-panel "), 2)
        self.assertIn("jh-chat-meal-svg", rendered)
        self.assertIn("jh-chat-meal-glucose", rendered)
        self.assertIn("jh-chat-meal-steps", rendered)
        self.assertIn("No walk", rendered)
        self.assertIn("Post-meal walk", rendered)
        self.assertIn("Sushi dinner (no walk)", rendered)
        self.assertIn("Sushi dinner (post-meal walk)", rendered)

    def test_patient_result_uses_meal_names_and_synthetic_timestamps(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        rendered = plan.result
        self.assertNotIn("Meal 1", rendered)
        self.assertNotIn("Meal 2", rendered)
        self.assertIn("Synthetic demo", rendered)
        self.assertIn("jh-chat-meal-time", rendered)

    def test_patient_result_carries_iauc_fields_and_comparison_summary(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        rendered = plan.result
        self.assertIn("Peak rise", rendered)
        self.assertIn("iAUC", rendered)
        self.assertIn("mg·min/dL", rendered)
        self.assertIn("jh-chat-iauc-summary", rendered)
        self.assertIn("lower with the walked meal", rendered)

    def test_patient_result_has_no_derived_from_line(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        rendered = plan.result
        self.assertNotIn("Derived from:", rendered)
        self.assertNotIn("jh-chat-source", rendered)

    def test_patient_biomarker_definitions_and_missing_meals(self):
        self.assertIn("measurable sign", chat.build_plan("patient", _patient_chat(), "What does a biomarker mean?").result)
        self.assertIn("average glucose", chat.build_plan("patient", _patient_chat(), "What is HbA1c?").result)
        absent = {"analysis": {"meals": [], "explanation": "No comparable sushi meals in this period."}}
        result = chat.build_plan("patient", absent, "sushi").result
        self.assertIn("No comparable sushi meals", result)
        self.assertNotIn("jh-chat-meal-panel", result)

    def test_reference_prompt_returns_grounded_ranges(self):
        plan = chat.build_plan("patient", _patient_chat(), "What are the reference ranges?")
        self.assertEqual(plan.stages, ())
        self.assertIn("reference ranges shown in your panels", plan.result)
        self.assertIn("Fasting glucose", plan.result)
        self.assertIn("70–99 mg/dL", plan.result)
        self.assertIn("Elevated", plan.result)

    def test_medbeam_and_referral_input_never_reaches_a_result(self):
        for prompt in (
            "review my panels for a Med-BEAM appointment",
            "prepare a referral",
            "book an appointment",
        ):
            plan = chat.build_plan("patient", _patient_chat(), prompt)
            self.assertEqual(plan.stages, ())
            self.assertNotIn("Med-BEAM", plan.result)
            self.assertNotIn("appointment", plan.result.lower())

    def test_practitioner_has_no_typed_summarize_intent(self):
        plan = chat.plan_response("practitioner", _practitioner_chat(), "Summarize the report")
        self.assertEqual(len(plan), 1)
        self.assertNotIn("jh-report-link", plan[0])
        self.assertNotIn("Amlodipine", plan[0])
        self.assertNotIn("Med-BEAM", plan[0])

    def test_unsupported_prompt_gets_concise_limitation(self):
        plan = chat.plan_response("patient", _patient_chat(), "hello there")
        self.assertEqual(len(plan), 1)
        self.assertNotIn("prototype", plan[0].lower())
        self.assertIn("reference ranges", plan[0])
        self.assertIn("sushi", plan[0])
        self.assertNotIn("Med-BEAM", plan[0])

    def test_supported_plan_has_transient_stages_and_single_final_result(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        self.assertEqual(len(plan.stages), 5)
        self.assertTrue(all("jh-chat-stage" in stage for stage in plan.stages))
        self.assertNotIn("jh-chat-stage", plan.result)
        self.assertNotIn("Thursday, October 15", plan.result)
        self.assertNotIn("Med-BEAM", plan.result)
        self.assertNotIn("prototype", plan.result.lower())

    def test_transient_frames_reuse_one_stage_bubble_then_replace_it(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        frames = list(chat.transient_frames(plan))
        self.assertEqual(len(frames), len(plan.stages) + 1)
        for frame in frames[:-1]:
            self.assertEqual(len(frame), 1)
            self.assertIn("jh-chat-stage", frame[0])
        final = frames[-1]
        self.assertEqual(len(final), 1)
        self.assertIn("Sushi dinner (no walk)", final[0])
        self.assertNotIn("jh-chat-stage", final[0])

    def test_final_history_does_not_retain_all_stage_messages(self):
        plan = chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)
        final_history = [
            chat._assistant_message_html(chat.opening_message("patient")),
            chat._user_message_html(core.PATIENT_CHAT_STARTER),
            plan.result,
        ]
        rendered = "".join(final_history)
        self.assertIn("How can I help you understand the data shown here?", rendered)
        self.assertIn("One of my sushi meals", rendered)
        self.assertIn("Sushi dinner (no walk)", rendered)
        for token in ("Locating", "Isolating", "Comparing", "Preparing"):
            self.assertNotIn(token, rendered)
        self.assertNotIn("jh-chat-stage", rendered)

    def test_role_specific_opening_and_placeholder(self):
        self.assertEqual(
            chat.opening_message("patient"),
            "How can I help you understand the data shown here?",
        )
        self.assertNotIn("sushi", chat.opening_message("patient").lower())
        self.assertNotIn("sushi", chat.composer_placeholder("patient").lower())
        self.assertEqual(chat.composer_placeholder("patient"), "Ask about your data…")
        self.assertEqual(
            chat.opening_message("practitioner"),
            "A report is ready for you.",
        )
        self.assertEqual(chat.composer_placeholder("practitioner"), "")


def _find(widget, predicate):
    if predicate(widget):
        return widget
    for child in getattr(widget, "children", ()):
        found = _find(child, predicate)
        if found is not None:
            return found
    return None


def _find_all(widget, predicate):
    matches = []
    if predicate(widget):
        matches.append(widget)
    for child in getattr(widget, "children", ()):
        matches.extend(_find_all(child, predicate))
    return matches


@unittest.skipUnless(HAS_CHAT, "ipywidgets/plotly are not installed in this interpreter")
class FloatingChatWidgetContractTests(unittest.TestCase):
    @staticmethod
    def _build(role: str):
        view = {
            "role": role,
            "show_scripted_chat": True,
            "chat": _patient_chat() if role == "patient" else _practitioner_chat(),
        }
        return chat.scripted_chat_widget(view)

    def test_launcher_visible_and_panel_closed_by_default(self):
        host = self._build("patient")
        launcher = _find(
            host, lambda widget: "jh-chat-launcher" in getattr(widget, "_dom_classes", ())
        )
        panel = _find(
            host, lambda widget: "jh-chat-panel" in getattr(widget, "_dom_classes", ())
        )
        self.assertIsNotNone(launcher)
        self.assertIsNotNone(panel)
        self.assertIsNone(launcher.layout.display)
        self.assertEqual(panel.layout.display, "none")

    def test_composer_accepts_typing_and_send_is_present(self):
        host = self._build("patient")
        composer = _find(host, lambda widget: isinstance(widget, widgets.Textarea))
        send = _find(
            host,
            lambda widget: isinstance(widget, widgets.Button) and widget.description == "Send",
        )
        self.assertIsNotNone(composer)
        self.assertIsNotNone(send)
        self.assertTrue(composer.continuous_update)

    def test_header_uses_ickm_advisor_without_other_sublabels(self):
        host = self._build("patient")
        identity = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML)
            and "iCKM Advisor" in widget.value,
        )
        self.assertIsNotNone(identity)
        self.assertNotIn("JupyterHealth assistant", identity.value)
        self.assertNotIn("Clinical data assistant", identity.value)
        self.assertNotIn("Prototype assistant", identity.value)

    def test_header_actions_are_grouped_separately_from_identity(self):
        host = self._build("patient")
        header = _find(
            host,
            lambda widget: "jh-chat-header" in getattr(widget, "_dom_classes", ()),
        )
        actions = _find(
            host,
            lambda widget: "jh-chat-header-actions" in getattr(widget, "_dom_classes", ()),
        )
        self.assertIsNotNone(header)
        self.assertIsNotNone(actions)
        self.assertEqual(len(actions.children), 2)

    def test_no_visible_prototype_assistant_in_chrome(self):
        for role in ("patient", "practitioner"):
            host = self._build(role)
            stack = [host]
            while stack:
                widget = stack.pop()
                for attr in ("value", "description", "tooltip", "placeholder"):
                    text = getattr(widget, attr, "")
                    if isinstance(text, str):
                        self.assertNotIn("Prototype assistant", text)
                        self.assertNotIn("Clinical data assistant", text)
                stack.extend(getattr(widget, "children", ()))

    def test_role_specific_opening_is_in_transcript(self):
        patient_host = self._build("patient")
        self.assertIsNotNone(
            _find(
                patient_host,
                lambda widget: isinstance(widget, widgets.HTML)
                and "How can I help you understand the data shown here?" in widget.value,
            )
        )
        practitioner_host = self._build("practitioner")
        self.assertIsNotNone(
            _find(
                practitioner_host,
                lambda widget: isinstance(widget, widgets.HTML)
                and "A report is ready for you." in widget.value,
            )
        )

    def test_patient_onboarding_has_no_heading_suggestions_or_medbeam(self):
        host = self._build("patient")
        capabilities = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML)
            and "reference ranges" in widget.value
            and "elevated biomarkers" in widget.value,
        )
        self.assertIsNotNone(capabilities)
        self.assertNotIn("What this assistant can do", capabilities.value)
        self.assertNotIn("Med-BEAM", capabilities.value)
        self.assertIn("Synthetic demo", capabilities.value)
        suggestion_buttons = _find_all(
            host,
            lambda widget: isinstance(widget, widgets.Button)
            and "jh-chat-suggestion" in getattr(widget, "_dom_classes", ()),
        )
        self.assertEqual(suggestion_buttons, [])

    def test_practitioner_opening_has_only_report_and_selected_randomize(self):
        host = self._build("practitioner")
        link = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML)
            and "UC HTN Way 3.0 Report" in widget.value
            and "jh-report-link" in widget.value,
        )
        self.assertIsNotNone(link)
        self.assertIn("A report is ready for you.", link.value)
        self.assertIn(f'href="{core.UC_HTN_REPORT_URL}"', link.value)
        self.assertIn('target="_blank"', link.value)
        self.assertIn('rel="noopener"', link.value)
        self.assertLess(
            link.value.index("A report is ready for you."),
            link.value.index("jh-report-link"),
        )
        controls_match = re.search(
            r'<div class="jh-chat-report-controls">(.*?)</div>',
            link.value,
            re.DOTALL,
        )
        self.assertIsNotNone(controls_match)
        controls = controls_match.group(1)
        self.assertIn('class="jh-report-link"', controls)
        self.assertIn('class="jh-randomize-control jh-randomize-control-selected"', controls)
        self.assertIn('type="button"', controls)
        self.assertIn('aria-pressed="true"', controls)
        self.assertIn(">Randomize</button>", controls)
        self.assertLess(
            controls.index('class="jh-report-link"'),
            controls.index(">Randomize</button>"),
        )
        for line in core.PRACTITIONER_SUMMARY_LINES:
            self.assertNotIn(line, link.value)
        self.assertNotIn("jh-chat-randomization-summary", link.value)
        self.assertNotIn("jh-chat-randomization-treatment", link.value)
        self.assertEqual(link.value.count('class="jh-chat-msg jh-chat-assistant'), 1)
        self.assertNotIn("Clinical algorithm reference", link.value)
        self.assertNotIn("jh-report-cue", link.value)
        self.assertNotIn("for this patient", link.value)
        self.assertNotIn("jh-medbeam-link", link.value)
        self.assertNotIn("medbeam-report.png", link.value)
        self.assertNotIn("Med-BEAM", link.value)

    def test_practitioner_opening_escapes_report_values(self):
        rendered = chat._practitioner_opening_html(
            {
                "report": {
                    "label": "<script>unsafe()</script>",
                    "href": 'https://example.test/?next="unsafe"',
                }
            }
        )
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;unsafe()&lt;/script&gt;", rendered)
        self.assertIn("&quot;unsafe&quot;", rendered)

    def test_practitioner_feed_has_no_composer(self):
        host = self._build("practitioner")
        self.assertEqual(
            _find_all(host, lambda widget: isinstance(widget, widgets.Textarea)),
            [],
        )
        self.assertEqual(
            _find_all(
                host,
                lambda widget: isinstance(widget, widgets.Button)
                and widget.description == "Send",
            ),
            [],
        )

    def test_practitioner_header_has_hidden_keyboard_focusable_gesture(self):
        practitioner_host = self._build("practitioner")
        gesture = _find(
            practitioner_host,
            lambda widget: "jh-chat-header-gesture"
            in getattr(widget, "_dom_classes", ()),
        )
        self.assertIsInstance(gesture, widgets.Button)
        self.assertEqual(gesture.description, "")
        self.assertEqual(gesture.tooltip, "iCKM Advisor")
        self.assertFalse(gesture.disabled)
        patient_host = self._build("patient")
        self.assertIsNone(
            _find(
                patient_host,
                lambda widget: "jh-chat-header-gesture"
                in getattr(widget, "_dom_classes", ()),
            )
        )

    def test_randomization_summary_is_exact_and_separate_from_opening(self):
        rendered = chat._randomization_summary_html(_practitioner_chat())
        self.assertEqual(
            rendered,
            '<div class="jh-chat-msg jh-chat-assistant">'
            '<div class="jh-chat-bubble">'
            '<div class="jh-chat-result jh-chat-randomization-summary">'
            '<p class="jh-chat-randomization-assignment">'
            "Alex has been randomized to "
            '<strong class="jh-chat-randomization-treatment">'
            "amlodipine/valsartan</strong></p>"
            '<ul class="jh-chat-randomization-outcomes">'
            "<li>More likely to reach BP goal of 140/90</li>"
            "<li>Faster time to BP goal (3.8 vs 4.9 weeks)</li>"
            "<li>More Time in Target Range (54% vs 46%)</li>"
            "</ul></div></div></div>",
        )

    def test_gesture_appends_randomization_message_once(self):
        host = self._build("practitioner")
        gesture = _find(
            host,
            lambda widget: "jh-chat-header-gesture" in getattr(widget, "_dom_classes", ()),
        )
        transcript = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML) and "jh-chat-msg" in widget.value,
        )
        for line in core.PRACTITIONER_SUMMARY_LINES:
            self.assertNotIn(line, transcript.value)

        # Button.click models the browser activation emitted by a double-click,
        # Enter, or Space on the focusable overlay.
        gesture.click()
        self.assertNotIn(
            '<div class="jh-chat-result jh-chat-randomization-summary">',
            transcript.value,
        )
        gesture.click()

        self.assertEqual(
            transcript.value.count('class="jh-chat-msg jh-chat-assistant'),
            2,
        )
        self.assertEqual(
            transcript.value.count(
                '<div class="jh-chat-result jh-chat-randomization-summary">'
            ),
            1,
        )
        self.assertEqual(
            transcript.value.count("Alex has been randomized to "),
            1,
        )
        for line in core.PRACTITIONER_RANDOMIZATION_BENEFITS:
            self.assertEqual(transcript.value.count(line), 1)
        self.assertIn(
            '<strong class="jh-chat-randomization-treatment">'
            "amlodipine/valsartan</strong>",
            transcript.value,
        )
        self.assertNotIn("Here are the takeaways", transcript.value)
        self.assertNotIn("Med-BEAM", transcript.value)

        gesture.click()
        gesture.click()
        self.assertEqual(
            transcript.value.count(
                '<div class="jh-chat-result jh-chat-randomization-summary">'
            ),
            1,
        )
        self.assertEqual(
            transcript.value.count("Alex has been randomized to "),
            1,
        )
        for line in core.PRACTITIONER_RANDOMIZATION_BENEFITS:
            self.assertEqual(transcript.value.count(line), 1)

    def test_sushi_submit_shows_comparison_without_referral(self):
        host = self._build("patient")
        composer = _find(host, lambda widget: isinstance(widget, widgets.Textarea))
        send = _find(
            host,
            lambda widget: isinstance(widget, widgets.Button) and widget.description == "Send",
        )
        transcript = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML) and "jh-chat-msg" in widget.value,
        )
        composer.value = core.PATIENT_CHAT_STARTER
        send.click()
        self.assertIn("Sushi dinner (no walk)", transcript.value)
        self.assertNotIn("Med-BEAM", transcript.value)
        self.assertNotIn("elevated blood pressure and HbA1c", transcript.value)
        self.assertNotIn("jh-chat-referral", transcript.value)
        self.assertFalse(composer.disabled)
        self.assertFalse(send.disabled)

    def test_patient_chat_stays_available_with_missing_meals(self):
        view = {
            "role": "patient",
            "show_scripted_chat": True,
            "chat": {
                "analysis": {
                    "meals": [],
                    "minutes": [],
                    "traces": [],
                    "activity": [],
                    "explanation": "No comparable sushi meals in this period.",
                },
                "context_cards": [],
                "explanation": "No comparable sushi meals in this period.",
            },
        }
        host = chat.scripted_chat_widget(view)
        launcher = _find(
            host, lambda widget: "jh-chat-launcher" in getattr(widget, "_dom_classes", ())
        )
        self.assertIsNotNone(launcher)
        capabilities = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML)
            and "reference ranges" in widget.value
            and "elevated biomarkers" in widget.value,
        )
        self.assertIsNotNone(capabilities)
        self.assertNotIn("sushi", capabilities.value.lower())

        composer = _find(host, lambda widget: isinstance(widget, widgets.Textarea))
        send = _find(
            host,
            lambda widget: isinstance(widget, widgets.Button) and widget.description == "Send",
        )
        transcript = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML) and "jh-chat-msg" in widget.value,
        )
        composer.value = core.PATIENT_CHAT_STARTER
        send.click()
        self.assertIn("No comparable sushi meals", transcript.value)
        self.assertNotIn("jh-chat-meal-panel", transcript.value)

        unsupported = chat.build_plan("patient", view["chat"], "hello there")
        self.assertNotIn("sushi", unsupported.result.lower())
        self.assertIn("reference ranges", unsupported.result)

    def test_no_visible_rendered_string_contains_simulation_or_prototype_language(self):
        for role in ("patient", "practitioner"):
            host = self._build(role)
            stack = [host]
            while stack:
                widget = stack.pop()
                for attr in ("value", "description", "tooltip", "placeholder"):
                    text = getattr(widget, attr, "")
                    if isinstance(text, str):
                        lowered = text.lower()
                        self.assertNotIn("simulation", lowered, text)
                        self.assertNotIn("simulated demo", lowered, text)
                        self.assertNotIn("prototype", lowered, text)
                stack.extend(getattr(widget, "children", ()))

        plans = [
            chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER).result,
            chat.build_plan("patient", _patient_chat(), "hello there").result,
        ]
        for rendered in plans:
            self.assertNotIn("prototype", rendered.lower())
            self.assertNotIn("simulation", rendered.lower())


class ChatCssContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = THEME_PATH.read_text()

    def test_launcher_is_fixed_bottom_right_without_left_position(self):
        block = _css_rule(self.css, ".jh-chat-launcher")
        self.assertIn("position: fixed", block)
        self.assertIn("right:", block)
        self.assertIn("bottom:", block)
        self.assertNotIn("left:", block)

    def test_panel_is_fixed_bottom_right_without_left_position(self):
        block = _css_rule(self.css, ".jh-chat-panel")
        self.assertIn("position: fixed", block)
        self.assertIn("right:", block)
        self.assertIn("bottom:", block)
        self.assertNotIn("left:", block)
        self.assertIn("width: 620px", block)

    def test_header_actions_are_flush_right(self):
        actions = _css_rule(self.css, ".jh-chat-header-actions")
        self.assertIn("margin-left: auto", actions)
        self.assertIn("display: flex", actions)

    def test_compact_panel_has_symmetric_insets_and_launcher_stays_right(self):
        start = self.css.index("@media (max-width: 560px)")
        media = self.css[start:self.css.index("/* ---------- figure chrome ---------- */", start)]
        self.assertIn("left: 12px", media)
        self.assertIn("right: 12px", media)
        self.assertIn("right: 18px", media)
        self.assertNotIn("left: 18px", media)
        self.assertIn("grid-template-columns: 1fr", media)

    def test_send_button_centers_label_and_has_minimum_target(self):
        block = _css_rule(self.css, ".jh-chat-send")
        self.assertIn("display: flex", block)
        self.assertIn("align-items: center", block)
        self.assertIn("justify-content: center", block)
        self.assertIn("min-height: 40px", block)

    def test_textarea_and_send_share_exact_forty_pixel_height(self):
        textarea = _css_rule(self.css, ".jh-chat-composer textarea")
        send = _css_rule(self.css, ".jh-chat-send")
        for block in (textarea, send):
            self.assertIn("box-sizing: border-box", block)
            self.assertIn("height: 40px", block)
            self.assertIn("min-height: 40px", block)
            self.assertIn("max-height: 40px", block)

    def test_composer_row_centers_controls_without_overriding_widget_visibility(self):
        block = _css_rule(self.css, ".jh-chat-composer-row")
        self.assertIn("align-items: center", block)
        self.assertIn("display: flex", block)
        self.assertNotIn("display: flex !important", block)

    def test_header_and_actions_have_component_scoped_line_heights(self):
        header = _css_rule(self.css, ".jh-chat-header")
        self.assertIn("line-height: 1.2", header)
        self.assertNotIn(".jh-chat-hint", self.css)

    def test_header_gesture_is_absolute_transparent_and_full_size(self):
        block = _css_rule(self.css, ".jh-chat-header-gesture")
        self.assertIn("position: absolute", block)
        self.assertIn("opacity: 0", block)
        self.assertIn("top: 0", block)
        self.assertIn("left: 0", block)
        self.assertIn("right: 0", block)
        self.assertIn("bottom: 0", block)
        header = _css_rule(self.css, ".jh-chat-header")
        self.assertIn("position: relative", header)

    def test_meal_comparison_panels_are_side_by_side_with_timestamps(self):
        grid = _css_rule(self.css, ".jh-chat-meal-grid")
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", grid)
        svg = _css_rule(self.css, ".jh-chat-meal-svg")
        self.assertIn("width: 100%", svg)
        self.assertIn("height: 128px", svg)
        self.assertIn(".jh-chat-meal-axis", self.css)
        self.assertIn(".jh-chat-meal-time", self.css)
        steps = _css_rule(self.css, ".jh-chat-meal-steps")
        self.assertIn("fill: #4b9bd5", steps)

    def test_report_and_randomize_controls_share_a_responsive_horizontal_row(self):
        controls = _css_rule(self.css, ".jh-chat-report-controls")
        self.assertIn("align-items: center", controls)
        self.assertIn("display: flex", controls)
        self.assertIn("flex-wrap: nowrap", controls)
        link = _css_rule(self.css, ".jh-report-link")
        self.assertIn("flex: 0 1 auto", link)
        self.assertIn("min-width: 0", link)
        randomize = _css_rule(self.css, ".jh-randomize-control")
        self.assertIn("flex: 0 0 auto", randomize)

    def test_randomize_selected_state_is_visually_highlighted(self):
        selected = _css_rule(self.css, '.jh-randomize-control[aria-pressed="true"]')
        self.assertIn("background: var(--jh-navy)", selected)
        self.assertIn("color: var(--jh-white)", selected)
        treatment = _css_rule(self.css, ".jh-chat-randomization-treatment")
        self.assertIn("color: var(--jh-navy)", treatment)
        self.assertIn("font-weight:", treatment)

    def test_randomization_summary_has_no_divider_or_divider_spacing(self):
        self.assertNotIn(".jh-chat-randomization-summary {", self.css)

    def test_report_link_is_styled_without_old_summary_chrome(self):
        link = _css_rule(self.css, ".jh-report-link")
        self.assertIn("border: 1px solid", link)
        self.assertIn("display: inline-flex", link)
        self.assertNotIn(".jh-report-cue", self.css)
        self.assertNotIn(".jh-chat-takeaways", self.css)
        self.assertNotIn(".jh-chat-takeaways-row", self.css)
        self.assertNotIn(".jh-chat-summary-list", self.css)

    def test_voila_containment_override_targets_lumino_box_panel(self):
        self.assertIn("body.jp-Notebook .lm-BoxPanel,", self.css)
        self.assertIn(
            "body.jp-Notebook .lm-BoxPanel > .lm-BoxPanel-child {",
            self.css,
        )
        self.assertIn("contain: none !important;", self.css)

    def test_metric_columns_share_parent_tracks_with_subgrid_fallback(self):
        parent = _css_rule(self.css, ".jh-metric-rows")
        row = _css_rule(self.css, ".jh-metric-row")
        self.assertIn("grid-template-columns:", parent)
        self.assertIn("var(--jh-metric-label-col)", parent)
        self.assertIn("grid-column: 1 / -1", row)
        self.assertIn("var(--jh-metric-label-col)", row)
        self.assertIn("grid-template-columns: subgrid", row)

    def test_time_in_ranges_strip_is_horizontal_full_width(self):
        body = _css_rule(self.css, ".jh-agp-range-body")
        strip = _css_rule(self.css, ".jh-agp-strip")
        self.assertNotIn("grid-template-columns", body)
        self.assertNotIn("84px", body)
        self.assertIn("flex-direction: row", strip)
        self.assertIn("width: 100%", strip)
        self.assertIn("height: 18px", strip)
        self.assertNotIn(".jh-agp-seg span", self.css)

    def test_close_and_minimize_controls_have_forty_pixel_targets(self):
        sized = [
            block
            for block in _css_rules(self.css)
            if "height: 40px" in block and "width: 40px" in block
        ]
        self.assertTrue(sized)
        self.assertTrue(any(".jh-chat-close" in block for block in sized))
        self.assertTrue(any(".jh-chat-minimize" in block for block in sized))


if __name__ == "__main__":
    unittest.main()
