# FIN-C2-109 — Unit Tests: PreProcessNode (QueryNormalizeNode + FrameworkRouteNode)

import json

from framework.schemas.agent_status import AgentStatus
from src.nodes.pre_process_node import PreProcessNode
from src.services import degradation


class TestPreProcessNode:
    def setup_method(self):
        self.node = PreProcessNode()

    def test_success_routes_eu_credit_scoring(self):
        """TC: EU-exposed credit-scoring description routes to all 3 frameworks."""
        state = {
            "user_input": "Credit scoring AI system with EU customer exposure",
            "node_history": [],
            "error_log": [],
            "correlation_id": "test-1",
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert "EU_AI_ACT_ANNEX_III" in result["applicable_frameworks"]
        assert "FSA_AI_MRM" in result["applicable_frameworks"]
        assert "JAPAN_AI_PROMOTION_ACT" in result["applicable_frameworks"]
        assert result["eu_customer_exposure"] is True
        assert result["detected_language"] == "en"
        payload = json.loads(result["validated_input"])
        assert payload["ai_system_description"] == "Credit scoring AI system with EU customer exposure"
        assert payload["applicable_frameworks"] == result["applicable_frameworks"]

    def test_empty_input_degrades(self):
        """A rejection the caller can fix ends as SUCCESS + error_code, so the reason
        reaches the caller. No assessment is produced either way."""
        state = {"user_input": "", "node_history": [], "error_log": []}
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["error_code"] == degradation.EMPTY_INPUT
        assert "error_log" not in result

    def test_no_applicable_framework_degrades(self):
        """Caller-correctable: naming the financial use case or the EU exposure resolves
        it, so the reason is reported rather than the run failing."""
        state = {
            "user_input": "A generic chatbot for internal FAQ",
            "node_history": [],
            "error_log": [],
        }
        result = self.node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["error_code"] == degradation.NO_APPLICABLE_FRAMEWORK
        assert "error_log" not in result
        # the sentence the caller sees is derived from the code alone
        assert "financial use case" in degradation.explain_degradation(result["error_code"])

    def test_execute_method_signature(self):
        """The node defines execute(self, state) and does not define _invoke_impl()."""
        import inspect

        assert hasattr(PreProcessNode, "execute")
        sig = inspect.signature(PreProcessNode.execute)
        params = list(sig.parameters.keys())
        assert len(params) >= 2
        assert params[1] == "state"
        assert "_invoke_impl" not in PreProcessNode.__dict__
