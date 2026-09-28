"""AgentCore Platform v1.0 — FIN-C2-109 HybridRetrieveNode (inner step 1)."""

# Inner subgraph step 1: hybrid retrieval (dense embedding + BM25 article-number
# matching) across the multi-framework regulatory KB (EU AI Act Annex III,
# FSA AI MRM, Japan AI Promotion Act). Deterministic — no LLM call here.
#
# NOTE (Cat 2 data flow): BaseGraph.invoke() seeds the inner graph with only
# `user_input` (string) + shared fields — the outer state's typed fields
# (ai_system_description/applicable_frameworks) are NOT visible here. The
# outer pre_process sets validated_input to a JSON string
# (see ComplianceWorkflowGraphNode.extract_input); this node is the inner
# entry point and must json.loads(state["user_input"]) to recover the payload.

import json
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.compliance_kb_service import ComplianceKBService
from src.services.degradation import EMPTY_INPUT, NO_APPLICABLE_FRAMEWORK, NO_PROVISIONS_FOUND


class HybridRetrieveNode(FunctionNode):
    """Retrieve relevant provisions across the applicable regulatory frameworks."""

    # S-1: explicit by design, not inherited implicitly.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, kb_service: ComplianceKBService | None = None, top_k: int = 8):
        self._kb_service = kb_service or ComplianceKBService()
        self._top_k = top_k

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        raw = state.get("user_input", "")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        # A degraded run carries the reason the caller can act on. The inner workflow is
        # wired with unconditional edges, so each node has to step aside itself: doing the
        # work here on a request that was already refused is exactly what must not happen.
        if state.get("error_code"):
            # the marker travels in this node's own result dict too: the S-3 re-check
            # sees that dict, not the full state, so it needs it to scope itself
            return {"error_code": state["error_code"], "status": AgentStatus.SUCCESS.value}

        description = payload.get("ai_system_description", "")
        frameworks = payload.get("applicable_frameworks", [])

        if not description or not frameworks:
            emit_trace_event(
                "hybrid_retrieve_rejected",
                {"reason": "missing_description_or_frameworks"},
                state,
            )
            # The subgraph receives the request as a serialized string, so this node
            # cannot tell "the outer step already refused" from "upstream dropped the
            # field". Both readings point at the same thing the caller can do, so it
            # degrades and the remaining nodes step aside.
            return {
                "error_code": EMPTY_INPUT if not description else NO_APPLICABLE_FRAMEWORK,
                "status": AgentStatus.SUCCESS.value,
            }

        provisions = self._kb_service.hybrid_search(description, frameworks, top_k=self._top_k)
        if not provisions:
            # Caller-correctable: a more concrete description matches provisions. No
            # assessment is produced either way.
            emit_trace_event("hybrid_retrieve_no_provisions", {"reason": NO_PROVISIONS_FOUND}, state)
            return {"error_code": NO_PROVISIONS_FOUND, "status": AgentStatus.SUCCESS.value}

        emit_trace_event(
            "hybrid_retrieve_completed",
            {"frameworks": frameworks, "provisions_count": len(provisions)},
            state,
        )

        return {
            "ai_system_description": description,
            "applicable_frameworks": frameworks,
            "retrieved_provisions": provisions,
            "status": AgentStatus.SUCCESS.value,
        }
