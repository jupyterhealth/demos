"""Floating, deterministic scripted chat for the CGM demo.

No LLM, API key, or network request is involved. The widget is a closed-by-default
circular launcher that opens a bounded floating panel built only from ipywidgets and
the local Tabler icon registry.

The patient role keeps a typed composer matched deterministically to the supported
scripted branches (sushi comparison, HbA1c, biomarker meaning, and reference ranges);
unsupported input receives a concise demo-limitation reply rather than a fabricated
model answer. The patient flow has no Med-BEAM referral, appointment, or consent
branch: a matched sushi prompt ends naturally with its data visualization.

The practitioner role is a report-delivery feed, not a free-text composer. Its opening
assistant message shows ``A report is ready for you.`` followed by the locally served
UC HTN Way 3.0 link, with no additional visible caption. A hidden demo gesture
(double-click the chat header) appends a synthetic Med-BEAM summary once as a normal
assistant bubble containing the same scripted, source-grounded summary lines, never a
real clinical recommendation.

The staged thinking steps are rendered as a single transient conversation event that
is replaced in place on the active asyncio/IPython/Tornado event loop when one is
available. Outside a live kernel the deterministic final result is shown immediately.
The underlying scripted content remains the notebook-computed view dict, so the
displayed meals, windows, and summary lines stay the source of truth.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from functools import partial
from html import escape
from typing import Callable

import ipywidgets as widgets

from .core import (
    PATIENT_VIEW,
    PRACTITIONER_SUMMARY_LINES,
    PRACTITIONER_VIEW,
    REPORT_LINK_LABEL,
    SYNTHETIC_DISCLOSURE,
    UC_HTN_ALGORITHM_REL_PATH,
    capabilities_for_role,
    chat_demo_limitation,
    chat_staged_steps,
    classify_chat_intent,
    include_scripted_chat,
)
from .icons import icon_background, render_icon

_LAUNCHER_LABEL = "Open chat"
_CLOSE_LABEL = "Close chat"
_MINIMIZE_LABEL = "Minimize chat"
_RESTORE_LABEL = "Restore chat"
_STAGE_DELAY_SECONDS = 1.4
_DOUBLE_CLICK_SECONDS = 0.45


def _asyncio_scheduler():
    """Return an asyncio ``call_later`` scheduler when a running loop is active."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    if not loop.is_running():
        return None
    return partial(loop.call_later)


def _ioloop_is_running(io_loop) -> bool:
    """Return whether a Tornado IOLoop is actively pumping callbacks."""
    asyncio_loop = getattr(io_loop, "asyncio_loop", None)
    if asyncio_loop is not None:
        try:
            return bool(asyncio_loop.is_running())
        except RuntimeError:
            return False
    return bool(getattr(io_loop, "_running", False))


def _ioloop_scheduler(io_loop):
    """Return a ``call_later`` scheduler for an active Tornado IOLoop."""
    if io_loop is None or not _ioloop_is_running(io_loop):
        return None
    return partial(io_loop.call_later)


def _ipython_ioloop_scheduler():
    """Return the scheduler attached to the active IPython kernel, if any."""
    try:
        from IPython import get_ipython
    except Exception:
        return None

    shell = get_ipython()
    if shell is None:
        return None
    kernel = getattr(shell, "kernel", None)
    io_loop = getattr(kernel, "io_loop", None)
    if io_loop is None or not callable(getattr(io_loop, "call_later", None)):
        return None
    return partial(io_loop.call_later)


def _tornado_ioloop_scheduler():
    """Return the current Tornado IOLoop scheduler without creating a new loop."""
    try:
        from tornado.ioloop import IOLoop

        io_loop = IOLoop.current(instance=False)
    except Exception:
        return None
    return _ioloop_scheduler(io_loop)


def active_scheduler():
    """Resolve a non-blocking delayed-callback scheduler for the current kernel."""
    scheduler = _asyncio_scheduler()
    if scheduler is not None:
        return scheduler
    scheduler = _ipython_ioloop_scheduler()
    if scheduler is not None:
        return scheduler
    return _tornado_ioloop_scheduler()


def _install_result(render, html, restore) -> None:
    render(html)
    restore()


def schedule_plan(plan: ChatPlan, *, schedule, render, restore) -> None:
    """Schedule a transient plan on a caller-provided delayed scheduler."""
    frames = tuple(frame[0] for frame in transient_frames(plan))
    if not plan.stages:
        _install_result(render, plan.result, restore)
        return

    render(frames[0])
    for offset, frame in enumerate(frames[1:], start=1):
        delay = _STAGE_DELAY_SECONDS * offset
        callback = partial(render, frame)
        if offset == len(frames) - 1:
            callback = partial(_install_result, render, frame, restore)
        schedule(delay, callback)


def _user_message_html(text: str) -> str:
    return (
        '<div class="jh-chat-msg jh-chat-user">'
        f'<div class="jh-chat-bubble">{escape(text)}</div>'
        "</div>"
    )


def _assistant_message_html(content: str, *, staged: bool = False, extra_class: str = "") -> str:
    stage_class = " jh-chat-stage" if staged else ""
    extra = f" {extra_class}" if extra_class else ""
    return (
        f'<div class="jh-chat-msg jh-chat-assistant{stage_class}{extra}">'
        f'<div class="jh-chat-bubble">{content}</div>'
        "</div>"
    )


def _stage_html(step: str) -> str:
    """Render a staged thinking step."""
    return _assistant_message_html(escape(step), staged=True)


def _meal_comparison_svg(
    minutes: list,
    glucose: list,
    steps: list,
    glucose_lo: float,
    glucose_hi: float,
    steps_max: float,
) -> str:
    """Deterministic inline SVG of one meal's glucose trace with step bars overlaid."""
    if len(minutes) < 2 or not glucose or len(glucose) != len(minutes):
        return '<div class="jh-chat-meal-svg-empty">No trace available</div>'

    left, right = 24.0, 254.0
    top, bottom = 22.0, 112.0
    width = right - left
    height = bottom - top

    xmin = float(min(minutes))
    xmax = float(max(minutes))
    xspan = (xmax - xmin) or 1.0

    def x(minute: float) -> float:
        return left + (minute - xmin) / xspan * width

    glo = float(glucose_lo)
    ghi = float(glucose_hi)
    gspan = (ghi - glo) or 1.0

    def y(value: float) -> float:
        return bottom - (value - glo) / gspan * height

    band_top = y(min(180.0, ghi))
    band_bottom = y(max(70.0, glo))
    polyline = " ".join(
        f"{x(minute):.1f},{y(value):.1f}" for minute, value in zip(minutes, glucose)
    )
    meal_x = x(0.0)

    step_span = float(steps_max) or 1.0
    step_top = 34.0
    bars = []
    for minute, value in zip(minutes, steps):
        bar_height = max(0.0, float(value or 0.0) / step_span * step_top)
        cx = x(minute)
        bars.append(
            f'<rect class="jh-chat-meal-steps" x="{cx - 1.4:.1f}" '
            f'y="{bottom - bar_height:.1f}" width="2.8" height="{bar_height:.1f}" rx="0.8"/>'
        )

    return (
        '<svg class="jh-chat-meal-svg" viewBox="0 0 260 138" role="img" '
        'aria-label="Glucose in milligrams per deciliter and step activity from 30 minutes before through 180 minutes after this meal" '
        'preserveAspectRatio="xMidYMid meet">'
        '<line class="jh-chat-meal-legend-line" x1="24" y1="9" x2="38" y2="9"/>'
        '<text class="jh-chat-meal-axis" x="42" y="12">Glucose</text>'
        '<rect class="jh-chat-meal-steps" x="99" y="4" width="9" height="9" rx="2"/>'
        '<text class="jh-chat-meal-axis" x="112" y="12">Steps</text>'
        f'<text class="jh-chat-meal-axis" x="1" y="{top + 4:.1f}">{ghi:.0f}</text>'
        f'<text class="jh-chat-meal-axis" x="1" y="{bottom:.1f}">{glo:.0f}</text>'
        f'<rect class="jh-chat-meal-band" x="{left:.1f}" y="{band_top:.1f}" '
        f'width="{width:.1f}" height="{max(0.0, band_bottom - band_top):.1f}"/>'
        + "".join(bars)
        + f'<line class="jh-chat-meal-mealtime" x1="{meal_x:.1f}" y1="{top:.1f}" '
        f'x2="{meal_x:.1f}" y2="{bottom:.1f}"/>'
        f'<polyline class="jh-chat-meal-glucose" points="{polyline}"/>'
        f'<text class="jh-chat-meal-axis" x="{left:.1f}" y="130" text-anchor="start">−30</text>'
        f'<text class="jh-chat-meal-axis" x="{meal_x:.1f}" y="130" text-anchor="middle">Meal</text>'
        f'<text class="jh-chat-meal-axis" x="{right:.1f}" y="130" text-anchor="end">+180 min</text>'
        "</svg>"
    )


def _patient_result_html(chat_data: dict) -> str:
    analysis = chat_data.get("analysis") or {}
    explanation = chat_data.get("explanation") or analysis.get("explanation", "")

    minutes = analysis.get("minutes") or []
    meals = analysis.get("meals") or []
    if len(meals) < 2:
        return escape(explanation or "I couldn't find two comparable sushi meals in this CGM period.")
    traces = analysis.get("traces") or []
    activity = analysis.get("activity") or []

    glucose_values = [
        value
        for trace in traces
        for value in (trace.get("glucose") or [])
        if isinstance(value, (int, float))
    ]
    steps_values = [
        value
        for record in activity
        for value in (record.get("steps") or [])
        if isinstance(value, (int, float))
    ]
    glucose_lo = min(glucose_values) if glucose_values else 40.0
    glucose_hi = max(glucose_values) if glucose_values else 200.0
    steps_max = max(steps_values) if steps_values else 0.0

    panels = []
    for index, meal in enumerate(meals):
        trace = traces[index] if index < len(traces) else {}
        record = activity[index] if index < len(activity) else {}
        glucose = trace.get("glucose") or []
        steps = record.get("steps") or []
        had_walk = bool(meal.get("had_walk"))
        context = "Post-meal walk" if had_walk else "No walk"
        walk_class = "walk" if had_walk else "nowalk"
        name = str(meal.get("label") or "Meal")
        timestamp = str(meal.get("timestamp") or meal.get("occurred_at") or "Synthetic demo")
        spike = meal.get("spike_mg_dl")
        iauc = meal.get("iauc_mg_dl_min")
        spike_text = f"{float(spike):+.0f} mg/dL" if isinstance(spike, (int, float)) else "n/a"
        iauc_text = f"{float(iauc):,.0f} mg·min/dL" if isinstance(iauc, (int, float)) else "n/a"
        panels.append(
            f'<article class="jh-chat-meal-panel jh-chat-meal-panel-{walk_class}">'
            '<div class="jh-chat-meal-panel-head">'
            f'<span class="jh-chat-meal-name">{escape(name)}</span>'
            f'<span class="jh-chat-meal-context">{escape(context)}</span>'
            "</div>"
            f'<div class="jh-chat-meal-time">{escape(timestamp)}</div>'
            + _meal_comparison_svg(minutes, glucose, steps, glucose_lo, glucose_hi, steps_max)
            + '<div class="jh-chat-meal-stats">'
            f'<span>Peak rise <b>{escape(spike_text)}</b></span>'
            f'<span>iAUC <b>{escape(iauc_text)}</b></span>'
            "</div>"
            "</article>"
        )

    walk_meal = next((meal for meal in meals if meal.get("had_walk")), None)
    no_walk_meal = next((meal for meal in meals if not meal.get("had_walk")), None)
    iauc_summary = ""
    if walk_meal and no_walk_meal:
        walk_iauc = walk_meal.get("iauc_mg_dl_min")
        no_walk_iauc = no_walk_meal.get("iauc_mg_dl_min")
        if isinstance(walk_iauc, (int, float)) and isinstance(no_walk_iauc, (int, float)):
            percent_lower = (no_walk_iauc - walk_iauc) / no_walk_iauc * 100
            iauc_summary = (
                '<p class="jh-chat-iauc-summary">'
                f'iAUC {float(no_walk_iauc):,.0f} versus {float(walk_iauc):,.0f} mg·min/dL — '
                f'{percent_lower:.0f}% lower with the walked meal.'
                "</p>"
            )

    return (
        '<div class="jh-chat-result jh-chat-meal-comparison">'
        f'<div class="jh-chat-meal-grid">{"".join(panels)}</div>'
        + iauc_summary
        + f'<p class="jh-chat-explanation">{escape(explanation)}</p>'
        "</div>"
    )


def _patient_reference_html(chat_data: dict) -> str:
    cards = (chat_data or {}).get("context_cards") or []
    lines = []
    for card in cards:
        label = str(card.get("label") or "")
        if not label:
            continue
        value = str(card.get("value") or "n/a")
        reference = str(card.get("reference") or "")
        status = str(card.get("status_label") or card.get("status") or "")
        parts = [f"<b>{escape(label)}</b> {escape(value)}"]
        if reference:
            parts.append(f"reference {escape(reference)}")
        if status:
            parts.append(escape(status))
        lines.append("<li>" + " · ".join(parts) + "</li>")
    body = "".join(lines) if lines else "<li>No reference data is available.</li>"
    return (
        '<div class="jh-chat-result jh-chat-reference">'
        '<p class="jh-chat-explanation">Here are the reference ranges shown in your panels:</p>'
        f'<ul class="jh-chat-reference-list">{body}</ul>'
        "</div>"
    )


def _has_comparable_sushi(chat_data: dict) -> bool:
    """Whether the current analysis contains two comparable sushi meals."""
    meals = ((chat_data or {}).get("analysis") or {}).get("meals") or []
    return len(meals) >= 2


def _capability_items_html(role: str, chat_data: dict | None = None) -> str:
    capabilities = list(capabilities_for_role(role))
    if role == PATIENT_VIEW and not _has_comparable_sushi(chat_data or {}):
        capabilities = [
            capability
            for capability in capabilities
            if "sushi meals" not in capability.lower()
        ]
    return "".join(
        f"<li>{escape(capability)}</li>" for capability in capabilities
    )


def _capability_surface_html(role: str, chat_data: dict | None = None) -> str:
    return (
        '<div class="jh-chat-capabilities">'
        f'<ul>{_capability_items_html(role, chat_data)}</ul>'
        '<p class="jh-chat-capabilities-note">'
        f"{escape(SYNTHETIC_DISCLOSURE)} Uses only the data shown here."
        "</p>"
        "</div>"
    )


def _report_delivery_html(chat_data: dict) -> str:
    report = (chat_data or {}).get("report") or {}
    href = str(report.get("href") or UC_HTN_ALGORITHM_REL_PATH)
    label = str(report.get("label") or REPORT_LINK_LABEL)
    icon = render_icon("notes", label=label)
    return (
        '<div class="jh-chat-report-delivery">'
        f'<a class="jh-report-link" href="{escape(href, quote=True)}" '
        f'target="_blank" rel="noopener">{icon} {escape(label)}</a>'
        "</div>"
    )


def _practitioner_opening_html(chat_data: dict) -> str:
    """Opening assistant bubble carrying the locally served report link."""
    return _assistant_message_html(
        f"{escape(opening_message(PRACTITIONER_VIEW))}{_report_delivery_html(chat_data)}"
    )


def _medbeam_summary_html(chat_data: dict) -> str:
    """Return one natural assistant bubble carrying the scripted Med-BEAM takeaways."""
    lines = chat_data.get("summary_lines") or list(PRACTITIONER_SUMMARY_LINES)
    items = "".join(f"<li>{escape(line)}</li>" for line in lines)
    content = (
        '<div class="jh-chat-result jh-chat-summary">'
        '<p class="jh-chat-explanation">Here are the takeaways from the Med-BEAM report:</p>'
        f'<ul class="jh-chat-summary-list">{items}</ul>'
        "</div>"
    )
    return _assistant_message_html(content)


def result_html(chat_data: dict, intent: str) -> str:
    """Return the deterministic patient result card for a matched intent."""
    if intent == "biomarker":
        return "A biomarker is a measurable sign of a biological process or health condition. Blood pressure and HbA1c are examples; a result is interpreted in context, not on its own."
    if intent == "hba1c":
        return "HbA1c is a blood test reflecting average glucose over about three months. The value and reference range shown in your panel can be discussed with your care team in the context of your full history."
    if intent == "reference":
        return _patient_reference_html(chat_data)
    return _patient_result_html(chat_data)


@dataclass(frozen=True)
class ChatPlan:
    """A deterministic chat response separated into transient stages and final result."""

    stages: tuple[str, ...]
    result: str


def build_plan(role: str, chat_data: dict, text: str) -> ChatPlan:
    """Build the transient stage sequence and immediate final result for a prompt."""
    intent = classify_chat_intent(role, text)
    if intent is None:
        if role == PATIENT_VIEW and not _has_comparable_sushi(chat_data):
            limitation = "I can answer questions about reference ranges and elevated biomarkers when those values are shown here."
        else:
            limitation = chat_demo_limitation(role)
        return ChatPlan(
            stages=(),
            result=_assistant_message_html(limitation),
        )
    stages = tuple(_stage_html(step) for step in chat_staged_steps(role, intent))
    return ChatPlan(
        stages=stages,
        result=_assistant_message_html(result_html(chat_data, intent)),
    )


def transient_frames(plan: ChatPlan):
    """Yield the assistant-side transcript states for a transient plan."""
    if not plan.stages:
        yield (plan.result,)
        return
    stage_slot = plan.stages[0]
    yield (stage_slot,)
    for stage in plan.stages[1:]:
        stage_slot = stage
        yield (stage_slot,)
    yield (plan.result,)


def plan_response(role: str, chat_data: dict, text: str) -> list[str]:
    """Return the stage messages followed by the final result."""
    plan = build_plan(role, chat_data, text)
    if not plan.stages:
        return [plan.result]
    return [*plan.stages, plan.result]


def opening_message(role: str) -> str:
    """Role-specific first assistant message shown before any prompt."""
    if role == PATIENT_VIEW:
        return "How can I help you understand the data shown here?"
    return "A report is ready for you."


def composer_placeholder(role: str) -> str:
    """Role-specific composer placeholder."""
    if role == PATIENT_VIEW:
        return "Ask about your data…"
    return ""


def build_chat_data(
    role: str,
    analysis: dict | Callable[[], dict],
    context_cards: list | None = None,
) -> dict:
    """Wire notebook-derived results into the role-specific scripted chat.

    A callable analysis runs only for the patient role; the clinician report does
    not need to calculate meal traces.
    """
    if role == PATIENT_VIEW:
        result = analysis() if callable(analysis) else analysis
        return {
            "analysis": result,
            "context_cards": list(context_cards or []),
            "explanation": result.get("explanation", ""),
        }
    return {
        "report": {
            "label": REPORT_LINK_LABEL,
            "href": UC_HTN_ALGORITHM_REL_PATH,
        },
        "summary_lines": list(PRACTITIONER_SUMMARY_LINES),
    }


@dataclass
class DoubleClickDetector:
    """Detect two activations within a short window using a monotonic clock."""

    threshold_seconds: float = _DOUBLE_CLICK_SECONDS
    _last_at: float | None = None

    def register(self, now: float | None = None) -> bool:
        """Return ``True`` only for the second activation inside the window."""
        moment = time.monotonic() if now is None else float(now)
        if self._last_at is not None and (moment - self._last_at) <= self.threshold_seconds:
            self._last_at = None
            return True
        self._last_at = moment
        return False


def _icon_css() -> str:
    rules = []
    launcher = icon_background("chat", color="#ffffff")
    close = icon_background("close", color="#33404d")
    minimize = icon_background("minimize", color="#33404d")
    if launcher:
        rules.append(f".jh-chat-launcher {{ background-image: {launcher} !important; }}")
    if close:
        rules.append(f".jh-chat-close {{ background-image: {close} !important; }}")
    if minimize:
        rules.append(f".jh-chat-minimize {{ background-image: {minimize} !important; }}")
    return "\n".join(rules)


def scripted_chat_widget(view: dict):
    """Return the floating chat widget, or ``None`` when disabled for this render."""
    if not include_scripted_chat(view):
        return None

    role = view.get("role") or PRACTITIONER_VIEW
    chat_data = view.get("chat") or {}

    style_widget = widgets.HTML(
        value=f"<style>{_icon_css()}</style>",
        layout=widgets.Layout(width="0px", height="0px", overflow="visible"),
    )

    launcher = widgets.Button(
        description=_LAUNCHER_LABEL,
        tooltip=_LAUNCHER_LABEL,
        layout=widgets.Layout(width="56px", height="56px"),
    )
    launcher.add_class("jh-chat-launcher")

    identity = widgets.HTML(
        '<div class="jh-chat-identity">'
        '<span class="jh-chat-avatar">'
        + render_icon("assistant", label="iCKM Advisor")
        + "</span>"
        '<span class="jh-chat-identity-text">'
        '<span class="jh-chat-assistant">iCKM Advisor</span>'
        "</span></div>"
    )

    minimize_button = widgets.Button(
        description=_MINIMIZE_LABEL,
        tooltip=_MINIMIZE_LABEL,
        layout=widgets.Layout(width="40px", height="40px"),
    )
    minimize_button.add_class("jh-chat-minimize")

    close_button = widgets.Button(
        description=_CLOSE_LABEL,
        tooltip=_CLOSE_LABEL,
        layout=widgets.Layout(width="40px", height="40px"),
    )
    close_button.add_class("jh-chat-close")

    header_actions = widgets.HBox(
        [minimize_button, close_button],
        layout=widgets.Layout(
            display="flex",
            align_items="center",
        ),
    )
    header_actions.add_class("jh-chat-header-actions")

    header_children = [identity, header_actions]
    gesture_button = None
    if role == PRACTITIONER_VIEW:
        # A hidden, keyboard-focusable overlay covers the header so the demo gesture
        # (double-click) stays discoverable without a visible toggle. It is styled
        # transparent and absolutely positioned by ``theme.css``.
        gesture_button = widgets.Button(
            description="",
            tooltip="iCKM Advisor",
            layout=widgets.Layout(
                top="0px",
                left="0px",
                right="0px",
                bottom="0px",
            ),
        )
        gesture_button.add_class("jh-chat-header-gesture")
        header_children.insert(0, gesture_button)

    header = widgets.HBox(
        header_children,
        layout=widgets.Layout(
            width="100%",
            display="flex",
            align_items="center",
            justify_content="space-between",
        ),
    )
    header.add_class("jh-chat-header")

    if role == PATIENT_VIEW:
        opening_html = _assistant_message_html(opening_message(role))
        onboarding_html = _capability_surface_html(role, chat_data)
    else:
        # The clinician report link lives inside the opening transcript bubble so it
        # stays in scrollable history; the onboarding slot stays empty.
        opening_html = _practitioner_opening_html(chat_data)
        onboarding_html = ""

    transcript = widgets.HTML(value=opening_html)
    transcript_box = widgets.VBox([transcript], layout=widgets.Layout(width="100%"))
    transcript_box.add_class("jh-chat-transcript")

    body_children = [transcript_box]

    if role == PATIENT_VIEW:
        onboarding = widgets.HTML(
            value=onboarding_html,
            layout=widgets.Layout(width="100%"),
        )
        onboarding.add_class("jh-chat-onboarding")
        body_children.append(onboarding)

    composer_row = None
    if role == PATIENT_VIEW:
        composer = widgets.Textarea(
            value="",
            placeholder=composer_placeholder(role),
            rows=1,
            continuous_update=True,
            layout=widgets.Layout(width="100%"),
        )
        composer.add_class("jh-chat-composer")

        send = widgets.Button(description="Send", layout=widgets.Layout(width="auto"))
        send.add_class("jh-chat-send")

        composer_row = widgets.HBox(
            [composer, send],
            layout=widgets.Layout(width="100%", display="flex", align_items="center"),
        )
        composer_row.add_class("jh-chat-composer-row")
        body_children.append(composer_row)

    body = widgets.VBox(
        body_children,
        layout=widgets.Layout(width="100%", display="flex", flex_flow="column"),
    )
    body.add_class("jh-chat-body")

    panel = widgets.VBox(
        [header, body],
        layout=widgets.Layout(
            width="620px",
            max_width="calc(100vw - 32px)",
            display="flex",
            flex_flow="column",
        ),
    )
    panel.add_class("jh-chat-panel")
    panel.layout.display = "none"

    history = [opening_html]
    scheduler = active_scheduler()
    medbeam_revealed = {"value": False}
    double_click = DoubleClickDetector()

    def render() -> None:
        transcript.value = "".join(history)

    def hide_onboarding() -> None:
        if role == PATIENT_VIEW:
            onboarding.layout.display = "none"

    def restore_composer() -> None:
        if composer_row is not None:
            send.disabled = False
            composer.disabled = False
            composer_row.layout.display = None

    def run_plan(plan: ChatPlan) -> None:
        if scheduler is None:
            history.append(plan.result)
            render()
            restore_composer()
            return

        stage_slot_open = False

        def render_frame(html: str) -> None:
            nonlocal stage_slot_open
            if stage_slot_open:
                history[-1] = html
            else:
                history.append(html)
                stage_slot_open = True
            render()

        schedule_plan(
            plan,
            schedule=scheduler,
            render=render_frame,
            restore=restore_composer,
        )

    def reveal_medbeam_summary() -> None:
        if medbeam_revealed["value"]:
            return
        medbeam_revealed["value"] = True
        history.append(_medbeam_summary_html(chat_data))
        render()

    def on_gesture(_: widgets.Button) -> None:
        if double_click.register():
            reveal_medbeam_summary()

    def submit(text: str) -> None:
        text = (text or "").strip()
        if not text or send.disabled:
            return
        if len(history) == 1:
            history.clear()
        history.append(_user_message_html(text))
        render()
        hide_onboarding()
        send.disabled = True
        composer.disabled = True
        run_plan(build_plan(role, chat_data, text))

    def on_composer_change(change: dict) -> None:
        value = change.get("new")
        if isinstance(value, str) and value.endswith("\n"):
            composer.value = ""
            submit(value[:-1])

    def on_send(_: widgets.Button) -> None:
        value = composer.value
        composer.value = ""
        submit(value)

    def open_panel(_: widgets.Button) -> None:
        panel.layout.display = "flex"
        launcher.layout.display = "none"

    def close_panel(_: widgets.Button) -> None:
        panel.layout.display = "none"
        launcher.layout.display = None

    def toggle_minimize(_: widgets.Button) -> None:
        if body.layout.display == "none":
            body.layout.display = "flex"
            minimize_button.description = _MINIMIZE_LABEL
            minimize_button.tooltip = _MINIMIZE_LABEL
            minimize_button.remove_class("jh-chat-minimize-expanded")
        else:
            body.layout.display = "none"
            minimize_button.description = _RESTORE_LABEL
            minimize_button.tooltip = _RESTORE_LABEL
            minimize_button.add_class("jh-chat-minimize-expanded")

    launcher.on_click(open_panel)
    close_button.on_click(close_panel)
    minimize_button.on_click(toggle_minimize)
    if gesture_button is not None:
        gesture_button.on_click(on_gesture)
    if composer_row is not None:
        send.on_click(on_send)
        composer.observe(on_composer_change, names="value")

    host = widgets.VBox(
        [style_widget, launcher, panel],
        layout=widgets.Layout(
            width="0px",
            height="0px",
            overflow="visible",
            padding="0px",
            margin="0px",
            border="none",
        ),
    )
    host.add_class("jh-chat-host")
    return host
