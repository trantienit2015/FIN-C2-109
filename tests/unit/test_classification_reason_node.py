# FIN-C2-109 — Unit Tests: ClassificationReasonNode (inner step 2)

from framework.schemas.agent_status import AgentStatus
from src.nodes.classification_reason_node import ClassificationReasonNode
from src.services.degradation import CLASSIFIER_UNAVAILABLE


class FakeLLM:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


class TestClassificationReasonNode:
    def test_success_high_risk_with_llm(self):
        """TC: LLM response mentioning HIGH_RISK -> high_risk_verdict == HIGH_RISK."""
        node = ClassificationReasonNode(llm=FakeLLM("Classification: HIGH_RISK per Annex III(5)(b)."))
        state = {
            "ai_system_description": "credit scoring system",
            "retrieved_provisions": [{"framework": "EU_AI_ACT_ANNEX_III", "article": "Annex III(5)(b)", "text": "..."}],
            "node_history": [],
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["high_risk_verdict"] == "HIGH_RISK"

    def test_no_llm_defaults_to_high_risk(self):
        """TC: no LLM configured -> deterministic HIGH_RISK default (grounded)."""
        node = ClassificationReasonNode(llm=None)
        state = {
            "ai_system_description": "credit scoring system",
            "retrieved_provisions": [{"framework": "EU_AI_ACT_ANNEX_III", "article": "Annex III(5)(b)", "text": "..."}],
            "node_history": [],
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["high_risk_verdict"] == "HIGH_RISK"

    def test_no_provisions_returns_error(self):
        """TC: empty retrieved_provisions -> AgentStatus.ERROR (S-2 edge)."""
        node = ClassificationReasonNode(llm=None)
        state = {"ai_system_description": "x", "retrieved_provisions": [], "node_history": [], "error_log": []}
        result = node.execute(state)
        assert result["status"] == AgentStatus.ERROR

    def test_execute_method_signature(self):
        import inspect

        assert hasattr(ClassificationReasonNode, "execute")
        sig = inspect.signature(ClassificationReasonNode.execute)
        params = list(sig.parameters.keys())
        assert params[1] == "state"
        assert "_invoke_impl" not in ClassificationReasonNode.__dict__

class DictLLM:
    """A BaseLLM implementation returning the canonical completion dict — what the
    shipped Azure client actually returns."""

    def complete(self, messages):
        return {
            "content": "Classification: HIGH_RISK per Article 6.",
            "tool_calls": [],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 49, "completion_tokens": 12},
        }


class TestCompletionShape:
    def test_dict_completion_yields_the_assistant_text_only(self):
        """The canonical completion dict must not be stringified into the reasoning:
        `.upper()` on it raises, and the model name and token counts would otherwise end
        up in the recorded reasoning. The deterministic fallback hides this — it only
        surfaces on a deployment that has an LLM wired."""
        node = ClassificationReasonNode(llm=DictLLM())
        state = {
            "ai_system_description": "A credit scoring model for EU retail customers",
            "retrieved_provisions": [{"article": "Article 6", "text": "high-risk classification"}],
            "node_history": [],
            "error_log": [],
        }
        result = node.execute(state)
        assert result["status"] == AgentStatus.SUCCESS
        assert result["high_risk_verdict"] == "HIGH_RISK"
        assert result["classification_reasoning"] == "Classification: HIGH_RISK per Article 6."
        assert "usage" not in result["classification_reasoning"]
        assert "gpt-4o" not in result["classification_reasoning"]


class TestClassifierFailureEndsAsAnError:
    """A classifier call that fails is a runtime dependency failure: the run ends as
    status=ERROR with the code in error_log, and no verdict is produced. The verdict
    extractor falls through to REQUIRES_LEGAL_REVIEW on empty text, so an unanswered call
    must never reach it and be reported as a risk classification with nothing behind it.
    The code is deliberately not placed in error_code, which marks a run that completed
    without an answer."""

    @staticmethod
    def _state():
        return {
            "ai_system_description": "A credit scoring model for EU retail customers",
            "retrieved_provisions": [{"article": "EU AI Act Annex III 5(b)"}],
            "correlation_id": "c",
        }

    def test_classifier_raising_ends_as_an_error_without_a_verdict(self):
        class DeadLLM:
            def complete(self, messages):
                raise RuntimeError("provider unreachable")

        r = ClassificationReasonNode(llm=DeadLLM()).execute(self._state())

        assert r["status"] == AgentStatus.ERROR.value
        assert "error_code" not in r
        assert "high_risk_verdict" not in r
        assert r["error_log"][0].startswith(f"{CLASSIFIER_UNAVAILABLE}:")

    def test_classifier_returning_nothing_is_the_same_failure(self):
        class MuteLLM:
            def complete(self, messages):
                return {"content": "   ", "model": "fake", "usage": {}}

        r = ClassificationReasonNode(llm=MuteLLM()).execute(self._state())

        assert r["status"] == AgentStatus.ERROR.value
        assert "error_code" not in r
        assert "high_risk_verdict" not in r
        assert r["error_log"][0].startswith(f"{CLASSIFIER_UNAVAILABLE}:")
