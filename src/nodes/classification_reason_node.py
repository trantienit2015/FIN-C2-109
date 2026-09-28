"""AgentCore Platform v1.0 — FIN-C2-109 ClassificationReasonNode (inner step 2)."""

# Inner subgraph step 2: determine the high-risk classification with an
# Annex-III reasoning chain, grounded in the cited provisions retrieved in
# step 1. Uses an injected LLM client for the reasoning step only — retrieval
# stays deterministic (step 1).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.degradation import CLASSIFIER_UNAVAILABLE


def _completion_text(completion: Any) -> str:
    """Return the assistant text from a BaseLLM completion.

    ``complete()`` returns the canonical dict — ``{content, tool_calls, model, usage}`` —
    so treating the whole thing as text puts the model name and token counts into the
    reasoning, and `.upper()` on it raises. The deterministic fallback hides this: with no
    LLM configured the branch never runs, so it only surfaces on a deployment that has one.

    A non-dict return is tolerated (an implementation may return the text directly).
    """
    if isinstance(completion, dict):
        content = completion.get("content", "")
    else:
        content = completion
    return str(content or "").strip()


class ClassificationReasonNode(FunctionNode):
    """Reason about high-risk classification grounded in retrieved provisions."""

    # S-1: explicit by design, not inherited implicitly.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # A degraded run carries the reason the caller can act on. The inner workflow is
        # wired with unconditional edges, so each node has to step aside itself: doing the
        # work here on a request that was already refused is exactly what must not happen.
        if state.get("error_code"):
            # the marker travels in this node's own result dict too: the S-3 re-check
            # sees that dict, not the full state, so it needs it to scope itself
            return {"error_code": state["error_code"], "status": AgentStatus.SUCCESS.value}

        description = state.get("ai_system_description", "")
        provisions = state.get("retrieved_provisions", [])

        if not provisions:
            emit_trace_event(
                "classification_reason_rejected",
                {"reason": "no_retrieved_provisions"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ClassificationReasonNode: no retrieved_provisions to reason over"],
            }

        cited_articles = [p.get("article", "") for p in provisions if p.get("article")]
        prompt = (
            "You are a financial-AI compliance classifier. Given the AI system description and the "
            "cited regulatory provisions below, determine whether the system is HIGH_RISK, "
            "LIMITED_RISK, or REQUIRES_LEGAL_REVIEW under the applicable frameworks. Ground your "
            "answer ONLY in the cited articles; do not invent citations.\n\n"
            f"System description: {description}\n"
            f"Cited provisions: {provisions}\n"
        )

        if self._llm is not None:
            # A runtime dependency failure ends the run as status=ERROR. The code travels
            # in error_log and the audit event, not in error_code, which marks a run that
            # completed without an answer. An unanswered call must not become a risk
            # classification either: the verdict extractor below falls through to
            # REQUIRES_LEGAL_REVIEW on empty text.
            try:
                reasoning = _completion_text(self._llm.complete([{"role": "user", "content": prompt}]))
            except Exception as exc:  # noqa: BLE001 - provider exception types are unknown here
                emit_trace_event(
                    "classification_reason_model_failed",
                    {"error_code": CLASSIFIER_UNAVAILABLE, "error": type(exc).__name__},
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [
                        f"{CLASSIFIER_UNAVAILABLE}: ClassificationReasonNode: classifier call failed ({type(exc).__name__})"
                    ],
                }
            if not reasoning.strip():
                emit_trace_event(
                    "classification_reason_model_empty",
                    {
                        "error_code": CLASSIFIER_UNAVAILABLE,
                    },
                    state,
                )
                return {
                    "status": AgentStatus.ERROR.value,
                    "error_log": [
                        f"{CLASSIFIER_UNAVAILABLE}: ClassificationReasonNode: classifier returned no usable content"
                    ],
                }
        else:
            reasoning = (
                "No LLM configured — defaulting to HIGH_RISK pending legal review. "
                f"Grounded in: {', '.join(cited_articles) or 'no citations available'}."
            )

        verdict = self._extract_verdict(reasoning)

        emit_trace_event(
            "classification_reasoned",
            {"high_risk_verdict": verdict, "cited_articles": cited_articles},
            state,
        )

        return {
            "high_risk_verdict": verdict,
            "classification_reasoning": reasoning,
            "status": AgentStatus.SUCCESS.value,
        }

    @staticmethod
    def _extract_verdict(reasoning: str) -> str:
        upper = reasoning.upper()
        if "HIGH_RISK" in upper or "HIGH RISK" in upper:
            return "HIGH_RISK"
        if "REQUIRES_LEGAL_REVIEW" in upper or "REQUIRES LEGAL REVIEW" in upper:
            return "REQUIRES_LEGAL_REVIEW"
        if "LIMITED_RISK" in upper or "LIMITED RISK" in upper:
            return "LIMITED_RISK"
        return "REQUIRES_LEGAL_REVIEW"
