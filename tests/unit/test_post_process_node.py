# FIN-C2-109 — Unit Tests: PostProcessNode

from framework.schemas.agent_status import AgentStatus
from src.nodes.post_process_node import PostProcessNode


class TestPostProcessNode:
    def setup_method(self):
        self.node = PostProcessNode()

    def test_success_assembles_formatted_output(self):
        """TC: merged inner fields assembled into formatted_output."""
        state = {
            "high_risk_verdict": "HIGH_RISK",
            "applicable_frameworks": ["EU_AI_ACT_ANNEX_III"],
            "documentation_checklist": ["item 1"],
            "fsa_convergence_map": [{"eu_ai_act_requirement": "x", "fsa_mrm_equivalent": "y"}],
            "hitl_required": True,
            "conformity_timeline": "deadline info",
            "disclaimers": ["disclaimer text"],
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["formatted_output"]["high_risk_verdict"] == "HIGH_RISK"
        assert result["formatted_output"]["hitl_required"] is True

    def test_missing_fields_default_gracefully(self):
        """TC: minimal state -> formatted_output still assembled with defaults (edge)."""
        state = {"node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["formatted_output"]["documentation_checklist"] == []

    def test_execute_method_signature(self):
        import inspect

        assert hasattr(PostProcessNode, "execute")
        sig = inspect.signature(PostProcessNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "_invoke_impl" not in PostProcessNode.__dict__
