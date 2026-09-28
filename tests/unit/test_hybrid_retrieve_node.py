# FIN-C2-109 — Unit Tests: HybridRetrieveNode (inner step 1)

import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.hybrid_retrieve_node import HybridRetrieveNode
from src.services import degradation


class TestHybridRetrieveNode:
    def setup_method(self):
        self.node = HybridRetrieveNode(top_k=8)

    def test_success_retrieves_eu_credit_scoring_provisions(self):
        """TC: retrieves EU Annex III credit-scoring provisions from the seeded KB."""
        payload = json.dumps(
            {
                "ai_system_description": "AI system for credit scoring and creditworthiness assessment",
                "applicable_frameworks": ["EU_AI_ACT_ANNEX_III"],
            }
        )
        state = {"user_input": payload, "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        articles = [p["article"] for p in result["retrieved_provisions"]]
        assert "Annex III(5)(b)" in articles

    def test_missing_payload_degrades(self):
        """The subgraph gets the request as a string, so it cannot tell an
        already-refused request from a dropped field — both mean the caller should
        resend a description. It degrades and the remaining nodes step aside."""
        state = {"user_input": "not-json", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["error_code"] == degradation.EMPTY_INPUT

    def test_missing_frameworks_degrades(self):
        """Description present but no framework matched: caller-correctable."""
        payload = json.dumps({"ai_system_description": "some system", "applicable_frameworks": []})
        state = {"user_input": payload, "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["error_code"] == degradation.NO_APPLICABLE_FRAMEWORK

    def test_execute_method_signature(self):
        import inspect

        assert hasattr(HybridRetrieveNode, "execute")
        sig = inspect.signature(HybridRetrieveNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "_invoke_impl" not in HybridRetrieveNode.__dict__
