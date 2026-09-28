"""AgentCore Platform v1.0"""

# Node: QueryNormalizeNode + FrameworkRouteNode (outer pre_process slot)
#  - Normalize the legal/technical query, detect language (EN/JP), extract the
#    AI system description.
#  - Route to applicable frameworks (EU AI Act Annex III / FSA AI MRM /
#    Japan AI Promotion Act) based on the system description + EU customer
#    exposure signal.
#  - A rejection the caller can act on (empty description, no applicable
#    framework) ends as a degraded success carrying an allow-listed error_code
#    (see src/services/degradation.py), not as a failure.
#  - Sets validated_input to a JSON string (Cat 2 data-flow contract): the
#    inner subgraph only receives user_input as a string, so pre_process
#    serializes ai_system_description + applicable_frameworks for the inner
#    graph's first node (hybrid_retrieve_node) to json.loads().

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from shared.services.events import emitter
from shared.services.events.types import EventType
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.degradation import EMPTY_INPUT, NO_APPLICABLE_FRAMEWORK

_EU_EXPOSURE_KEYWORDS = ("eu", "european union", "eu branch", "eu customer", "eu subsidiary")


def _detect_language(text: str) -> str:
    """Very small heuristic: presence of CJK characters -> 'ja', else 'en'."""
    for ch in text:
        if "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿":
            return "ja"
    return "en"


def _detect_eu_exposure(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _EU_EXPOSURE_KEYWORDS)


def _route_frameworks(text: str, eu_exposure: bool) -> list[str]:
    """Route to applicable regulatory frameworks based on the system description."""
    frameworks: list[str] = []
    if eu_exposure:
        frameworks.append("EU_AI_ACT_ANNEX_III")
    lowered = text.lower()
    fin_keywords = (
        "credit scoring",
        "underwriting",
        "insurance risk",
        "employment",
        "access to financial services",
        "creditworthiness",
    )
    if any(kw in lowered for kw in fin_keywords):
        frameworks.append("FSA_AI_MRM")
    if "japan" in lowered or eu_exposure:
        frameworks.append("JAPAN_AI_PROMOTION_ACT")
    # De-duplicate while preserving order.
    seen: set[str] = set()
    ordered = []
    for fw in frameworks:
        if fw not in seen:
            seen.add(fw)
            ordered.append(fw)
    return ordered


class PreProcessNode(FunctionNode):
    """QueryNormalizeNode + FrameworkRouteNode — validate input and route frameworks."""

    # S-1: explicit by design, not inherited implicitly. This node is on the outer
    # backbone, so it enforces the verified caller the manifest declares.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Progress (non-terminal) event for the caller. Outside the Marketplace runtime
        # this resolves to a no-op emitter, so it is safe on every entry path.
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Checking the request...",
            metadata={"step": "pre_process"},
        )
        user_input = state.get("user_input", "")

        if not user_input or not user_input.strip():
            emit_trace_event(
                "query_normalize_rejected",
                {"correlation_id": state.get("correlation_id"), "reason": "empty_input"},
                state,
            )
            # Caller-correctable: they can resend with a description, so the run
            # completes and says what to send.
            return {"error_code": EMPTY_INPUT, "status": AgentStatus.SUCCESS.value}

        normalized = user_input.strip()
        detected_language = _detect_language(normalized)
        eu_exposure = _detect_eu_exposure(normalized)
        frameworks = _route_frameworks(normalized, eu_exposure)

        if not frameworks:
            emit_trace_event(
                "framework_route_no_match",
                {"correlation_id": state.get("correlation_id")},
                state,
            )
            # Caller-correctable: naming the financial use case or the EU exposure
            # resolves it. No assessment is produced either way.
            return {"error_code": NO_APPLICABLE_FRAMEWORK, "status": AgentStatus.SUCCESS.value}

        emit_trace_event(
            "framework_routed",
            {
                "correlation_id": state.get("correlation_id"),
                "applicable_frameworks": frameworks,
                "detected_language": detected_language,
            },
            state,
        )

        validated_input = json.dumps(
            {"ai_system_description": normalized, "applicable_frameworks": frameworks},
            ensure_ascii=False,
        )

        return {
            "ai_system_description": normalized,
            "eu_customer_exposure": eu_exposure,
            "detected_language": detected_language,
            "applicable_frameworks": frameworks,
            "validated_input": validated_input,
            "status": AgentStatus.SUCCESS.value,
        }
