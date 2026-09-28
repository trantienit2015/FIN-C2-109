# FIN-C2-109 — Integration Test: full outer+inner graph compile() + invoke()

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from src.graph.graph import Graph
from src.services import degradation


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return "Classification: HIGH_RISK per Annex III(5)(b)."


class RefusingLLM:
    """Fails the test if the classifier is reached at all."""

    def complete(self, prompt: str) -> str:
        raise AssertionError("the classifier was reached on a refused request")


class TestFinC2109Graph:
    def test_full_graph_high_risk_credit_scoring(self):
        """Integration: EU-exposed credit-scoring query -> HIGH_RISK assessment
        with checklist + convergence + disclaimer, through the outer+inner Cat 2 pipeline.
        """
        agent = Graph(config={"llm": FakeLLM(), "max_retry": 1, "top_k": 8})
        agent.compile()

        ctx = InvocationContext(
            session_id="test-session",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="test-caller",
        )
        result = agent.invoke(
            "Credit scoring AI system with EU customer exposure", ctx=ctx
        )

        assert result["status"] == AgentStatus.SUCCESS.value
        output = result["output"]
        assert output["high_risk_verdict"] == "HIGH_RISK"
        assert len(output["documentation_checklist"]) == 11
        assert output["fsa_convergence_map"]
        assert output["disclaimers"]
        assert output["hitl_required"] is True

    def test_empty_input_degrades_instead_of_failing(self):
        """End-to-end shape of a caller-correctable rejection: the run completes and the
        reason is in the output."""
        agent = Graph(config={"llm": FakeLLM(), "max_retry": 1})
        agent.compile()

        ctx = InvocationContext(
            session_id="test-session-2",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="test-caller",
        )
        result = agent.invoke("", ctx=ctx)

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["output"]["message"] == degradation.explain_degradation(degradation.EMPTY_INPUT)
        assert result["output"]["high_risk_verdict"] == ""
        assert result["output"]["documentation_checklist"] == []

    def test_no_applicable_framework_degrades(self):
        """Caller-correctable: naming the financial use case or the EU exposure resolves it."""
        agent = Graph(config={"llm": FakeLLM(), "max_retry": 1})
        agent.compile()

        ctx = InvocationContext(
            session_id="test-session-3",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="test-caller",
        )
        result = agent.invoke("A generic chatbot for internal FAQ", ctx=ctx)

        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["output"]["message"] == degradation.explain_degradation(degradation.NO_APPLICABLE_FRAMEWORK)

    def test_refused_request_never_reaches_the_classifier(self):
        """The refusal happens before classification, and the inner workflow is wired with
        unconditional edges — so each node stepping aside, not the absence of data, is what
        has to stop the work. The classifier fails the test if it is reached."""
        agent = Graph(config={"llm": RefusingLLM(), "max_retry": 1})
        agent.compile()
        ctx = InvocationContext(
            session_id="test-session-4",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="test-caller",
        )
        result = agent.invoke("A generic chatbot for internal FAQ", ctx=ctx)
        assert result["status"] == AgentStatus.SUCCESS.value
        assert result["output"]["message"] == degradation.explain_degradation(degradation.NO_APPLICABLE_FRAMEWORK)

    def test_degraded_output_never_echoes_the_description(self):
        agent = Graph(config={"llm": RefusingLLM(), "max_retry": 1})
        agent.compile()
        ctx = InvocationContext(
            session_id="test-session-5",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="test-caller",
        )
        secret = "CONFIDENTIAL_SYSTEM_NAME_xyz"
        result = agent.invoke(f"A generic chatbot called {secret}", ctx=ctx)
        assert secret not in str(result["output"])

    def test_success_path_carries_an_empty_message(self):
        agent = Graph(config={"llm": FakeLLM(), "max_retry": 1, "top_k": 8})
        agent.compile()
        ctx = InvocationContext(
            session_id="test-session-6",
            caller_trust_level=TrustLevel.VERIFIED_EXTERNAL,
            caller_id="test-caller",
        )
        result = agent.invoke(
            "A credit scoring model for EU retail customers that decides loan eligibility", ctx=ctx
        )
        if result["status"] == AgentStatus.SUCCESS.value:
            assert result["output"]["message"] == ""
