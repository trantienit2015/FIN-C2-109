"""Caller-facing wording for runs that end without an assessment.

Each outcome here is reported by completing the run with an allow-listed ``error_code``
and a fixed sentence derived from that code alone. No request value is ever
interpolated, so a notice can never echo caller content back. On such a run
``status=SUCCESS`` means the agent finished handling the request safely; it does not
mean an assessment was returned.

Caller-correctable: EMPTY_INPUT, NO_APPLICABLE_FRAMEWORK and NO_PROVISIONS_FOUND — an
empty description, one no framework applies to, or one the compliance knowledge base
finds no provisions for. Each sentence names what to send instead.

Policy withholding: DISCLAIMER_WITHHELD. An assessment that reaches the output without
its mandatory legal disclaimers is withheld under this agent's answer-quality contract,
with every assessment field blanked. (An assessment citing articles that were never
retrieved is not withheld: it is downgraded to a legal-review verdict, which is the
fail-safe answer and reaches the caller intact.)

Not reported here, and ending as ``status=ERROR`` instead: credential-shaped content,
which fails closed with no output and no status conversion; an internally inconsistent
run (state a preceding step guarantees is absent), which is a defect; and a failed call
to a required external dependency. None of these is ever represented as a successful
completion. A missing or unusable configuration is refused at startup rather than
reported per request.
"""

from __future__ import annotations

EMPTY_INPUT = "EMPTY_INPUT"
NO_APPLICABLE_FRAMEWORK = "NO_APPLICABLE_FRAMEWORK"
NO_PROVISIONS_FOUND = "NO_PROVISIONS_FOUND"
# Diagnostic code for a run that ends as status=ERROR because the classifier model failed
# or returned nothing. Recorded in error_log and the audit event only; it has no
# caller-facing notice because the run is not reported as a completed one.
CLASSIFIER_UNAVAILABLE = "CLASSIFIER_UNAVAILABLE"
DISCLAIMER_WITHHELD = "DISCLAIMER_WITHHELD"

_MESSAGES: dict[str, str] = {
    EMPTY_INPUT: (
        "No AI system description was received. Describe the system to assess — what it "
        "does, who uses it, and whether it is offered to customers in the EU."
    ),
    NO_APPLICABLE_FRAMEWORK: (
        "No regulatory framework could be matched to the description. State the "
        "financial use case explicitly (credit scoring, insurance pricing, fraud "
        "detection and so on) and whether the system serves customers in the EU."
    ),
    NO_PROVISIONS_FOUND: (
        "No regulatory provisions were found for the description. Describe the system's "
        "purpose and the decisions it makes in more concrete terms, then resend."
    ),
}

_MESSAGES[DISCLAIMER_WITHHELD] = (
    "An assessment was assembled but not returned, because it lacked the legal "
    "disclaimer this agent attaches to every assessment. No risk classification was "
    "reached — send the description again."
)

_FALLBACK = "The description could not be accepted and no compliance assessment was produced."


def explain_degradation(code: str) -> str:
    """Return one caller-facing sentence for a degradation code."""
    return _MESSAGES.get(code, f"{_FALLBACK} [{code}]" if code else _FALLBACK)
