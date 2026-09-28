"""AgentCore Platform v1.0"""

# Node: output formatting — assembles the final compliance assessment
# (high-risk verdict + documentation checklist + conformity pathway + HITL +
# timeline + disclaimers) from fields merged in from the inner subgraph.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from shared.services.events import emitter
from shared.services.events.types import EventType
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event
from src.services.degradation import explain_degradation


class PostProcessNode(FunctionNode):
    """Format and finalize the compliance-assessment output."""

    # S-1: explicit by design, not inherited implicitly. This node is on the outer
    # backbone, so it enforces the verified caller the manifest declares.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # Progress (non-terminal) event for the caller. Outside the Marketplace runtime
        # this resolves to a no-op emitter, so it is safe on every entry path.
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Preparing the result...",
            metadata={"step": "post_process"},
        )
        # A degraded run produced no assessment by design. The output keeps the
        # documented shape and states why. Every value is a constant, so nothing the refused request left
        # in State reaches the caller.
        degraded_code = state.get("error_code", "")
        if degraded_code:
            reason = explain_degradation(degraded_code)
            emit_trace_event("compliance_assessment_degraded", {"error_code": degraded_code}, state)
            return {
                "error_code": degraded_code,
                "formatted_output": {
                    "high_risk_verdict": "",
                    "applicable_frameworks": [],
                    "documentation_checklist": [],
                    "fsa_convergence_map": [],
                    "hitl_required": False,
                    "conformity_timeline": "",
                    "disclaimers": [],
                    "message": reason,
                },
                "status": AgentStatus.SUCCESS.value,
            }

        verdict = state.get("high_risk_verdict", "")
        checklist = state.get("documentation_checklist", [])
        convergence = state.get("fsa_convergence_map", [])
        hitl_required = state.get("hitl_required", False)
        timeline = state.get("conformity_timeline", "")
        disclaimers = state.get("disclaimers", [])
        frameworks = state.get("applicable_frameworks", [])

        formatted = {
            "high_risk_verdict": verdict,
            "applicable_frameworks": frameworks,
            "documentation_checklist": checklist,
            "fsa_convergence_map": convergence,
            "hitl_required": hitl_required,
            "conformity_timeline": timeline,
            "disclaimers": disclaimers,
            # present on every run so the caller can read one key whatever the outcome;
            # only a degraded run puts a sentence in it
            "message": "",
        }

        emit_trace_event(
            "compliance_assessment_finalized",
            {"correlation_id": state.get("correlation_id"), "high_risk_verdict": verdict},
            state,
        )

        return {
            "formatted_output": formatted,
            "status": AgentStatus.SUCCESS.value,
        }
