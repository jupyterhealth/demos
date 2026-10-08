"""Small, evidence-bound client for the optional NRP clinician chat sidecar.

The notebook prepares the evidence.  This module deliberately does not retrieve
patient records or perform analytics, and it has no MCP implementation yet.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import os
import secrets
import time
from typing import Any, Mapping, Optional, Sequence
from urllib import error, request


DEFAULT_BASE_URL = "https://ellm.nrp-nautilus.io/v1"
DEFAULT_MODEL = "gpt-oss"


class ChatUnavailable(RuntimeError):
    """Raised when chat cannot be used in the current runtime."""

    safe_for_display = True


class ChatRequestError(RuntimeError):
    """A safe, retryable-or-not error suitable for display in the chat UI."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.safe_for_display = True


@dataclass(frozen=True)
class ChatResult:
    """A response plus the exact dashboard evidence labels supplied to NRP."""

    answer: str
    evidence: tuple[str, ...]


def _cache_salt() -> str:
    """Create the NRP-recommended base64 encoding of 256 random bits."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


class NRPChatClient:
    """OpenAI-compatible NRP chat client with bounded, evidence-only requests.

    ``tools`` is intentionally accepted as a future integration seam.  No tools
    or MCP servers are configured or invoked by this client today.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
        tools: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("NRP_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.getenv("NRP_MODEL", DEFAULT_MODEL)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.tools = tuple(tools or ())
        self.cache_salt = _cache_salt()

    def ask(self, question: str, evidence: Mapping[str, Any]) -> ChatResult:
        """Ask a concise clinician-facing question using prepared dashboard evidence."""
        token = os.getenv("NRP_TOKEN")
        if not token:
            raise ChatUnavailable("Clinician chat is unavailable: NRP_TOKEN is not configured.")
        question = question.strip()
        if not question:
            raise ChatRequestError("Enter a question before sending.")

        labels = tuple(_evidence_labels(evidence))
        body = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": 650,
            "cache_salt": self.cache_salt,
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "prepared_evidence": evidence},
                        separators=(",", ":"),
                        default=str,
                    ),
                },
            ],
        }
        payload = json.dumps(body, separators=(",", ":"), default=str).encode("utf-8")
        endpoint = f"{self.base_url}/chat/completions"

        for attempt in range(self.max_retries + 1):
            req = request.Request(
                endpoint,
                data=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                content = parsed["choices"][0]["message"]["content"]
                if not isinstance(content, str) or not content.strip():
                    raise ChatRequestError("Chat returned no usable answer. Please try again.", retryable=True)
                return ChatResult(answer=content.strip(), evidence=labels)
            except error.HTTPError as exc:
                retryable = exc.code == 429 or 500 <= exc.code < 600
                if retryable and attempt < self.max_retries:
                    time.sleep(0.4 * (2**attempt))
                    continue
                if retryable:
                    raise ChatRequestError(
                        "Chat is temporarily unavailable. Please retry your question.", retryable=True
                    ) from None
                raise ChatRequestError("Chat could not complete this request.") from None
            except (error.URLError, TimeoutError):
                if attempt < self.max_retries:
                    time.sleep(0.4 * (2**attempt))
                    continue
                raise ChatRequestError(
                    "Chat connection failed. Please retry your question.", retryable=True
                ) from None
            except (KeyError, IndexError, TypeError, ValueError):
                raise ChatRequestError("Chat returned an unreadable response. Please retry.", retryable=True) from None

        raise ChatRequestError("Chat is temporarily unavailable. Please retry your question.", retryable=True)


def _system_prompt() -> str:
    return (
        "You are a concise clinician-facing dashboard assistant. Describe only the supplied "
        "evidence; do not diagnose or recommend treatment. Do not claim causality. State when "
        "evidence is insufficient. Mention relevant session/date labels and metric values. "
        "Do not use outside knowledge or infer unprovided patient facts. The evidence can "
        "include multiple sessions available through the dashboard selector; call them "
        "available dashboard sessions rather than implying each is currently selected."
    )


def _evidence_labels(evidence: Mapping[str, Any]) -> list[str]:
    """Produce deterministic, compact disclosure labels without interpreting data."""
    labels = []
    patient = evidence.get("patient")
    if patient:
        labels.append(f"Patient context: {patient}")
    for session in evidence.get("sessions", ()):  # prepared notebook summaries only
        label = session.get("label", "Session") if isinstance(session, Mapping) else "Session"
        period = session.get("period", "") if isinstance(session, Mapping) else ""
        metrics = session.get("metrics", {}) if isinstance(session, Mapping) else {}
        metric_bits = []
        if isinstance(metrics, Mapping):
            for key, display in (
                ("mean_mg_dl", "mean glucose"),
                ("gmi_percent", "GMI"),
                ("cv_percent", "CV"),
            ):
                if metrics.get(key) is not None:
                    suffix = " mg/dL" if key == "mean_mg_dl" else "%"
                    metric_bits.append(f"{display} {metrics[key]}{suffix}")
        detail = f"; {', '.join(metric_bits)}" if metric_bits else ""
        labels.append(f"AGP session: {label}{f' ({period})' if period else ''}{detail}")
    for card in evidence.get("context_cards", ()):
        if isinstance(card, Mapping) and card.get("label"):
            values = [
                str(card.get(key))
                for key in ("previous", "previous_date", "current", "current_date", "detail")
                if card.get(key)
            ]
            suffix = f"; {' · '.join(values)}" if values else ""
            labels.append(f"Context card: {card['label']}{suffix}")
    if evidence.get("ppgr_comparison"):
        labels.append("Postprandial response comparison")
    return labels or ["No prepared dashboard evidence was available."]
