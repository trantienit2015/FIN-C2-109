"""The language model on the deployment path, and the manifest that must not require it.

With no client passed, the classification step does not reason and returns its default
verdict. The Marketplace entry point passes a client that resolves the three connection
values on each call; with none of them supplied the call is attempted, cannot resolve, and
the run ends as a failure rather than as a classification. The manifest must not turn the
optional model into a startup prerequisite.
"""

from pathlib import Path

import yaml

from framework.schemas.agent_status import AgentStatus
from framework.schemas.invocation_context import InvocationContext
from framework.schemas.trust_level import TrustLevel
from framework.secrets.base import NullProvider
from framework.secrets.context import bound_secrets

from src.graph.graph import FinC2109Graph
from src.services.azure_llm import LazyAzureOpenAILLM, REQUIRED_SECRET_KEYS

_ROOT = Path(__file__).resolve().parents[2]
_DESCRIPTION = "A credit scoring model for EU retail customers that decides loan eligibility"


class _CountingLazyLLM(LazyAzureOpenAILLM):
    """The client the entry point injects, counting the calls that reach it."""

    calls = 0

    def complete(self, messages):
        type(self).calls += 1
        return super().complete(messages)


def _invoke(llm):
    config = yaml.safe_load((_ROOT / "config" / "config.yaml").read_text()) or {}
    if llm is not None:
        config["llm"] = llm
    agent = FinC2109Graph(config=config)
    agent.compile()
    ctx = InvocationContext(session_id="no-credentials", caller_trust_level=TrustLevel.VERIFIED_EXTERNAL, caller_id="t")
    # A bound provider holding none of the values: what a deployment without them supplies.
    with bound_secrets(NullProvider()):
        return agent.invoke(_DESCRIPTION, ctx=ctx)


def test_without_a_client_the_default_verdict_is_returned():
    result = _invoke(None)

    assert result["status"] == AgentStatus.SUCCESS.value
    assert result["output"]["high_risk_verdict"] == "HIGH_RISK"


def test_a_client_without_its_values_ends_the_run_as_a_failure(monkeypatch):
    for key in REQUIRED_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)
    _CountingLazyLLM.calls = 0

    result = _invoke(_CountingLazyLLM())

    # The model was really attempted, and the unanswered call is not presented as a verdict.
    assert _CountingLazyLLM.calls >= 1
    assert result["status"] == AgentStatus.ERROR.value
    assert result.get("output") is None


def test_manifest_does_not_make_the_optional_model_a_startup_prerequisite():
    manifest = yaml.safe_load((_ROOT / "config" / "agent.yaml").read_text())
    requires = manifest["requires"]
    assert not set(REQUIRED_SECRET_KEYS) & set(requires["secrets"])
    assert "openai" not in requires["extras"]
