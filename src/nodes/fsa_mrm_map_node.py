"""AgentCore Platform v1.0 — FIN-C2-109 FSAMRMMapNode (inner step 4)."""

# Inner subgraph step 4: map EU AI Act requirements to FSA AI MRM equivalents
# via a version-pinned EU<->FSA convergence table. This convergence mapping is
# the template's unique differentiator (not codified elsewhere).

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.convergence_service import ConvergenceService


class FSAMRMMapNode(FunctionNode):
    """Map EU AI Act requirements to FSA AI MRM equivalents (convergence table)."""

    # S-1: explicit by design, not inherited implicitly.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def __init__(self, convergence_service: ConvergenceService | None = None):
        self._convergence_service = convergence_service or ConvergenceService()

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # A degraded run carries the reason the caller can act on. The inner workflow is
        # wired with unconditional edges, so each node has to step aside itself: doing the
        # work here on a request that was already refused is exactly what must not happen.
        if state.get("error_code"):
            # the marker travels in this node's own result dict too: the S-3 re-check
            # sees that dict, not the full state, so it needs it to scope itself
            return {"error_code": state["error_code"], "status": AgentStatus.SUCCESS.value}

        checklist = state.get("documentation_checklist", [])
        verdict = state.get("high_risk_verdict", "")

        if verdict != "HIGH_RISK":
            emit_trace_event(
                "fsa_mrm_map_skipped",
                {"verdict": verdict, "reason": "convergence_mapping_only_for_high_risk"},
                state,
            )
            return {
                "fsa_convergence_map": [],
                "status": AgentStatus.SUCCESS.value,
            }

        convergence_map = self._convergence_service.map_eu_to_fsa(checklist)

        emit_trace_event(
            "fsa_mrm_mapped",
            {"convergence_entries": len(convergence_map)},
            state,
        )

        return {
            "fsa_convergence_map": convergence_map,
            "status": AgentStatus.SUCCESS.value,
        }
