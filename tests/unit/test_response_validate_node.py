# FIN-C2-109 — Unit Tests: ResponseValidateNode (inner step 5, S-3 gate)

from framework.schemas.agent_status import AgentStatus
from src.nodes.response_validate_node import ResponseValidateNode
from src.services.degradation import DISCLAIMER_WITHHELD


class TestResponseValidateNode:
    def setup_method(self):
        self.node = ResponseValidateNode()

    def test_success_attaches_disclaimer(self):
        """TC: valid verdict + reasoning grounded in retrieved provisions -> disclaimer attached."""
        state = {
            "high_risk_verdict": "HIGH_RISK",
            "classification_reasoning": "Classification: HIGH_RISK per Annex III(5)(b).",
            "retrieved_provisions": [{"framework": "EU_AI_ACT_ANNEX_III", "article": "Annex III(5)(b)"}],
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["disclaimers"]

    def test_fabricated_citation_routes_to_legal_review(self):
        """TC: cited article not present among retrieved provisions -> dropped + REQUIRES_LEGAL_REVIEW."""
        state = {
            "high_risk_verdict": "HIGH_RISK",
            "classification_reasoning": "Classification: HIGH_RISK per Article 99 (fabricated).",
            "retrieved_provisions": [{"framework": "EU_AI_ACT_ANNEX_III", "article": "Annex III(5)(b)"}],
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["high_risk_verdict"] == "REQUIRES_LEGAL_REVIEW"
        assert any("fabricated" in e.lower() for e in result["error_log"])
        assert result["disclaimers"]

    def test_fabricated_citation_returns_only_its_own_log_entry(self):
        """error_log is an append-only channel: entries already in state must not come back,
        or each of them is recorded twice."""
        state = {
            "high_risk_verdict": "HIGH_RISK",
            "classification_reasoning": "Classification: HIGH_RISK per Article 99 (fabricated).",
            "retrieved_provisions": [{"framework": "EU_AI_ACT_ANNEX_III", "article": "Annex III(5)(b)"}],
            "node_history": [],
            "error_log": ["an earlier entry"],
        }
        result = self.node.execute(state)
        assert "an earlier entry" not in result["error_log"]
        assert len(result["error_log"]) == 1

    def test_missing_verdict_returns_error(self):
        """TC: missing high_risk_verdict -> AgentStatus.ERROR (edge)."""
        state = {"node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_extra_security_gate_output_preserves_disclaimer(self):
        """S-3 preservation: gate passes through state unchanged when disclaimer present."""
        state = {"status": AgentStatus.SUCCESS, "disclaimers": ["some disclaimer"]}
        result = self.node._extra_security_gate_output(state)
        assert result == state

    def test_extra_security_gate_output_rejects_missing_disclaimer(self):
        """S-3 preservation: an assessment without its disclaimer is withheld.

        A policy outcome, not a failure. The marker is what makes the outer output
        step blank every assessment field, so asserting it is asserting the withholding.
        """
        state = {"status": AgentStatus.SUCCESS, "disclaimers": [], "error_log": []}
        result = self.node._extra_security_gate_output(state)
        assert result["error_code"] == DISCLAIMER_WITHHELD
        assert result["status"] == AgentStatus.SUCCESS.value
        assert any("disclaimer" in e.lower() for e in result["error_log"])
        # Non-raising: must always return a dict, never None.
        assert isinstance(result, dict)

    def test_execute_method_signature(self):
        import inspect

        assert hasattr(ResponseValidateNode, "execute")
        sig = inspect.signature(ResponseValidateNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "_invoke_impl" not in ResponseValidateNode.__dict__
