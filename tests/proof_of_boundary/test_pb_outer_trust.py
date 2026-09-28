"""The outer backbone enforces the verified caller the manifest declares.

The pre_process, main (GraphNode) and post_process slots sit on the caller's input path.
Each one refuses a caller below the declared level before its own work starts, so an
unauthenticated standalone request never reaches the assessment.
"""

from pathlib import Path

import pytest
import yaml
from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel

from src.graph.graph import ComplianceWorkflowGraphNode, FinC2109Graph
from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode

_ROOT = Path(__file__).resolve().parents[2]
_DESCRIPTION = "A credit scoring model for EU retail customers that decides loan eligibility"


def test_outer_slots_match_the_manifest():
    declared = yaml.safe_load((_ROOT / "config" / "agent.yaml").read_text())["required_trust_level"]
    for node_cls in (PreProcessNode, ComplianceWorkflowGraphNode, PostProcessNode):
        assert node_cls.required_trust_level == TrustLevel[declared]


@pytest.mark.parametrize("node_cls", [PreProcessNode, ComplianceWorkflowGraphNode, PostProcessNode])
def test_anonymous_caller_is_refused_before_execute(monkeypatch, node_cls):
    def must_not_run(self, state):
        raise AssertionError("execute() ran for a caller below the declared level")

    monkeypatch.setattr(node_cls, "execute", must_not_run)
    node = node_cls() if node_cls is not ComplianceWorkflowGraphNode else node_cls(top_k=8)

    result = node({"user_input": _DESCRIPTION, "caller_trust_level": TrustLevel.ANONYMOUS.value})

    assert result["status"] == AgentStatus.ERROR.value
    assert any("s-1 trust gate denied" in msg.lower() for msg in result.get("error_log", []))


def test_anonymous_caller_gets_no_assessment_end_to_end():
    agent = FinC2109Graph(config={})
    agent.compile()
    ctx = InvocationContext(session_id="anon", caller_trust_level=TrustLevel.ANONYMOUS, caller_id="t")

    result = agent.invoke(_DESCRIPTION, ctx=ctx)

    assert result["status"] == AgentStatus.ERROR.value
    assert result.get("output") is None
