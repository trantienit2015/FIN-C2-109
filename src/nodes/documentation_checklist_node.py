"""AgentCore Platform v1.0 — FIN-C2-109 DocumentationChecklistNode (inner step 3)."""

# Inner subgraph step 3: generate the Annex IV conformity-documentation
# checklist (11 elements), the conformity pathway, HITL requirement, and the
# timeline to the August-2-2026 EU AI Act enforcement deadline.

from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

ANNEX_IV_CHECKLIST = [
    "General description of the AI system and its intended purpose",
    "Detailed description of system elements and the development process",
    "Detailed information about monitoring, functioning, and control of the AI system",
    "Description of the risk management system (Article 9)",
    "Description of changes made through the system's lifecycle",
    "List of applied harmonised standards or other technical specifications",
    "Copy of the EU declaration of conformity",
    "Description of the system used to evaluate performance post-market (Article 72)",
    "Description of appropriate human oversight measures (Article 14)",
    "Description of the input data and information about training/testing/validation datasets",
    "Assessment of cybersecurity measures in place",
]

_ENFORCEMENT_DEADLINE = "2026-08-02"


class DocumentationChecklistNode(FunctionNode):
    """Generate the Annex IV conformity-documentation checklist + pathway + HITL + timeline."""

    # S-1: explicit by design, not inherited implicitly.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.ANONYMOUS

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        # A degraded run carries the reason the caller can act on. The inner workflow is
        # wired with unconditional edges, so each node has to step aside itself: doing the
        # work here on a request that was already refused is exactly what must not happen.
        if state.get("error_code"):
            # the marker travels in this node's own result dict too: the S-3 re-check
            # sees that dict, not the full state, so it needs it to scope itself
            return {"error_code": state["error_code"], "status": AgentStatus.SUCCESS.value}

        verdict = state.get("high_risk_verdict", "")

        if not verdict:
            emit_trace_event(
                "documentation_checklist_rejected",
                {"reason": "missing_high_risk_verdict"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["DocumentationChecklistNode: missing high_risk_verdict"],
            }

        if verdict == "HIGH_RISK":
            checklist = list(ANNEX_IV_CHECKLIST)
            hitl_required = True
        elif verdict == "REQUIRES_LEGAL_REVIEW":
            checklist = ["Escalate to legal/compliance review before further conformity work"]
            hitl_required = True
        else:
            checklist = ["No Annex IV documentation required for LIMITED_RISK classification"]
            hitl_required = False

        timeline = (
            f"EU AI Act enforcement deadline: {_ENFORCEMENT_DEADLINE}. "
            f"Complete conformity documentation before this date to avoid exposure to "
            f"fines up to EUR 30M or 6% of global annual revenue."
        )

        emit_trace_event(
            "documentation_checklist_generated",
            {"verdict": verdict, "checklist_size": len(checklist), "hitl_required": hitl_required},
            state,
        )

        return {
            "documentation_checklist": checklist,
            "hitl_required": hitl_required,
            "conformity_timeline": timeline,
            "status": AgentStatus.SUCCESS.value,
        }
