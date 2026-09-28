"""AgentCore Platform v1.0"""

# ADR-005: State must be a flat TypedDict — never Pydantic BaseModel.
# LangGraph checkpoints use msgpack serialization; Pydantic objects
# cause silent corruption.  Extend AgentState with agent-specific
# fields only.  Do NOT add credentials, secrets, or Pydantic models.

from typing import Any, NotRequired

from framework.schemas.agent_state import AgentState


class State(AgentState):
    """FIN-C2-109 agent state.

    Multi-framework (EU AI Act / FSA AI MRM / Japan AI Promotion Act) high-risk
    classification + conformity-documentation/HITL assessment state.
    All shared fields (user_input, status, session_id, node_history,
    error_log, hitl_*, validated_input, etc.) are inherited from AgentState.
    """

    # QueryNormalize + FrameworkRoute (outer pre_process)
    # Outcome marker. A run that completes without an assessment - a caller-correctable refusal or
    # a policy withholding - carries this code, and its output says why in wording
    # derived from the code alone (src/services/degradation.py). A security failure or
    # an internally inconsistent run ends as status=ERROR instead.
    error_code: NotRequired[str]

    ai_system_description: str
    eu_customer_exposure: bool
    detected_language: str
    applicable_frameworks: list[str]

    # HybridRetrieve + ClassificationReason (inner step 1-2)
    retrieved_provisions: list[dict[str, Any]]
    high_risk_verdict: str
    classification_reasoning: str

    # DocumentationChecklist + FSAMRMMap + ResponseValidate (inner step 3 + S-3 gate)
    documentation_checklist: list[str]
    fsa_convergence_map: list[dict[str, Any]]
    hitl_required: bool
    conformity_timeline: str
    disclaimers: list[str]
