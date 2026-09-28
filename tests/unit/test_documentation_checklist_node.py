# FIN-C2-109 — Unit Tests: DocumentationChecklistNode (inner step 3)

from framework.schemas.agent_status import AgentStatus
from src.nodes.documentation_checklist_node import ANNEX_IV_CHECKLIST, DocumentationChecklistNode


class TestDocumentationChecklistNode:
    def setup_method(self):
        self.node = DocumentationChecklistNode()

    def test_high_risk_generates_full_checklist(self):
        """TC: HIGH_RISK verdict -> full 11-item Annex IV checklist + HITL required."""
        state = {"high_risk_verdict": "HIGH_RISK", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["documentation_checklist"]) == len(ANNEX_IV_CHECKLIST) == 11
        assert result["hitl_required"] is True
        assert "2026-08-02" in result["conformity_timeline"]

    def test_limited_risk_no_hitl(self):
        """TC: LIMITED_RISK verdict -> no HITL, minimal checklist."""
        state = {"high_risk_verdict": "LIMITED_RISK", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["hitl_required"] is False

    def test_missing_verdict_returns_error(self):
        """TC: missing high_risk_verdict -> AgentStatus.ERROR (edge)."""
        state = {"node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_execute_method_signature(self):
        import inspect

        assert hasattr(DocumentationChecklistNode, "execute")
        sig = inspect.signature(DocumentationChecklistNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "_invoke_impl" not in DocumentationChecklistNode.__dict__
