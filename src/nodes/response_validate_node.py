"""AgentCore Platform v1.0 — FIN-C2-109 ResponseValidateNode (inner step 5, S-3 gate)."""

# Inner subgraph step 5: mandatory legal disclaimer + no-fabricated-citation
# S-3 output gate. Every successful compliance assessment MUST carry a legal
# disclaimer (the agent assesses, it does not certify/advise) and every cited
# article in the classification reasoning MUST exist among the retrieved
# provisions (no fabrication). On violation: drop output, return a safe
# answer, and log to audit — never silent.
#
# Business validation (can set ERROR) lives in execute() per the framework rules —
# never in _extra_security_gate_output(), which must stay non-raising and
# always return a dict.

import re
from typing import Any, ClassVar

from framework.nodes.function_node import FunctionNode
from framework.schemas.agent_status import AgentStatus
from framework.schemas.trust_level import TrustLevel
from shared.utils.audit_logger import emit_trace_event

from src.services.degradation import DISCLAIMER_WITHHELD

_LEGAL_DISCLAIMER = (
    "This assessment is generated to assist compliance analysis and does not constitute "
    "binding legal advice or a certified conformity determination. Consult qualified legal "
    "counsel before relying on this output for regulatory filings."
)

_ARTICLE_PATTERN = re.compile(r"Article\s+\d+[a-zA-Z]?", re.IGNORECASE)


class ResponseValidateNode(FunctionNode):
    """S-3 gate: mandatory disclaimer + no fabricated article citations."""

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

        verdict = state.get("high_risk_verdict")
        reasoning = state.get("classification_reasoning", "")
        provisions = state.get("retrieved_provisions", [])

        if not verdict:
            emit_trace_event(
                "response_validate_rejected",
                {"reason": "missing_high_risk_verdict"},
                state,
            )
            return {
                "status": AgentStatus.ERROR.value,
                "error_log": ["ResponseValidateNode: missing high_risk_verdict"],
            }

        cited_articles = {m.group(0).upper() for m in _ARTICLE_PATTERN.finditer(reasoning)}
        known_articles = {str(p.get("article", "")).upper() for p in provisions if p.get("article")}
        fabricated = {a for a in cited_articles if a and a not in known_articles}

        if fabricated:
            emit_trace_event(
                "response_validate_fabrication_detected",
                {"fabricated_articles": sorted(fabricated)},
                state,
            )
            return {
                "high_risk_verdict": "REQUIRES_LEGAL_REVIEW",
                "classification_reasoning": (
                    "Automated classification withheld — cited article(s) could not be verified "
                    "against retrieved provisions. Route to legal review."
                ),
                "disclaimers": [_LEGAL_DISCLAIMER],
                "status": AgentStatus.SUCCESS.value,
                # Only this node's entry: error_log is an append-only channel, so handing
                # back the entries already in state would record each of them twice.
                "error_log": [f"ResponseValidateNode: dropped fabricated citation(s): {sorted(fabricated)}"],
            }

        emit_trace_event(
            "response_validated",
            {"verdict": verdict, "disclaimer_attached": True},
            state,
        )
        return {
            "disclaimers": [_LEGAL_DISCLAIMER],
            "status": AgentStatus.SUCCESS.value,
        }

    def _extra_security_gate_output(self, state: dict[str, Any]) -> dict[str, Any]:
        # Non-raising preservation check:
        # verify the mandatory legal disclaimer is present after execute() ran.
        # Never called manually from execute() — the framework's @final
        # _security_gate_output() invokes this automatically after execute().
        # The disclaimers are required of a produced assessment. A degraded run carries a
        # refusal instead of an assessment, so the requirement does not apply — the check
        # is scoped by the degradation marker rather than weakened.
        if state.get("error_code"):
            return state
        if state.get("status") == AgentStatus.SUCCESS.value and not state.get("disclaimers"):
            # A policy outcome, not a failure: the assessment is withheld under this
            # agent's answer-quality contract. The marker makes the output step blank
            # every assessment field and state the fixed reason; nothing source-derived
            # is returned.
            return {
                "error_code": DISCLAIMER_WITHHELD,
                "status": AgentStatus.SUCCESS.value,
                "error_log": [
                    *(state.get("error_log") or []),
                    "ResponseValidateNode: mandatory legal disclaimer missing from output (S-3 preservation)",
                ],
            }
        return state
