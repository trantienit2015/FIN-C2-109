# FIN-C2-109 — Unit Tests: FSAMRMMapNode (inner step 4)

from framework.schemas.agent_status import AgentStatus
from src.nodes.documentation_checklist_node import ANNEX_IV_CHECKLIST
from src.nodes.fsa_mrm_map_node import FSAMRMMapNode


class TestFSAMRMMapNode:
    def setup_method(self):
        self.node = FSAMRMMapNode()

    def test_high_risk_returns_non_empty_convergence_map(self):
        """TC: HIGH_RISK verdict with full checklist -> non-empty convergence map."""
        state = {
            "high_risk_verdict": "HIGH_RISK",
            "documentation_checklist": ANNEX_IV_CHECKLIST,
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert len(result["fsa_convergence_map"]) > 0

    def test_non_high_risk_skips_mapping(self):
        """TC: non-HIGH_RISK verdict -> empty convergence map (edge)."""
        state = {
            "high_risk_verdict": "LIMITED_RISK",
            "documentation_checklist": [],
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["fsa_convergence_map"] == []

    def test_execute_method_signature(self):
        import inspect

        assert hasattr(FSAMRMMapNode, "execute")
        sig = inspect.signature(FSAMRMMapNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "_invoke_impl" not in FSAMRMMapNode.__dict__
