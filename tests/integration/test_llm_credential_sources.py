"""Where each entry point reads the optional model's connection values.

The Marketplace entry point's provider reads the process environment first and the
per-agent file second; the standalone server's provider reads only the per-agent file.
Both are exercised through the objects the entry points build, and the values are
followed as far as the client the adapter would construct.
"""

import importlib
import os
from pathlib import Path

import pytest
from framework.secrets.context import bound_secrets
from shared.bootstrap.marketplace_app import build_marketplace_secret_provider

import cli
import src.services.azure_llm as azure_llm
from src.services.azure_llm import REQUIRED_SECRET_KEYS, AzureConfigUnavailable, LazyAzureOpenAILLM

_VALUES = {
    "AZURE_OPENAI_API_KEY": "mock-key-for-testing",
    "AZURE_OPENAI_ENDPOINT": "https://example.invalid",
    "AZURE_OPENAI_DEPLOYMENT": "mock-deployment",
}


class _RecordingClient:
    seen = None

    def __init__(self, config):
        type(self).seen = config


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    """No values anywhere to start with, and an empty working directory."""
    for key in REQUIRED_SECRET_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AGENTCORE_ENVIRONMENT", "dev")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(azure_llm, "_load_client_class", lambda: _RecordingClient)
    _RecordingClient.seen = None
    return tmp_path


def _write_agent_file(root):
    path = root / "env" / "agents" / cli._NAMESPACE / cli._AGENT_NAME / ".env.dev"
    path.parent.mkdir(parents=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in _VALUES.items()))


def _client_config(provider):
    with bound_secrets(provider):
        LazyAzureOpenAILLM()._build_client()
    return _RecordingClient.seen


def _marketplace_provider():
    return build_marketplace_secret_provider(agent_name=cli._AGENT_NAME, namespace=cli._NAMESPACE)


_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def standalone_provider(isolated):
    """The provider the standalone server builds at import, in the isolated directory.

    The module is rebuilt from the repository root afterwards, so later tests see the
    server as it is normally imported.
    """
    import src.api.server as server

    yield lambda: importlib.reload(server)._secrets_provider
    here = os.getcwd()
    os.chdir(_REPO_ROOT)
    try:
        importlib.reload(server)
    finally:
        os.chdir(here)


def test_marketplace_entry_reads_the_process_environment(isolated, monkeypatch):
    for key, value in _VALUES.items():
        monkeypatch.setenv(key, value)

    config = _client_config(_marketplace_provider())

    assert config["api_key"] == _VALUES["AZURE_OPENAI_API_KEY"]
    assert config["azure_endpoint"] == _VALUES["AZURE_OPENAI_ENDPOINT"]
    assert config["azure_deployment"] == _VALUES["AZURE_OPENAI_DEPLOYMENT"]


def test_marketplace_entry_falls_back_to_the_per_agent_file(isolated):
    _write_agent_file(isolated)

    config = _client_config(_marketplace_provider())

    assert config["api_key"] == _VALUES["AZURE_OPENAI_API_KEY"]


def test_standalone_server_reads_the_per_agent_file(isolated, standalone_provider):
    _write_agent_file(isolated)

    config = _client_config(standalone_provider())

    assert config["api_key"] == _VALUES["AZURE_OPENAI_API_KEY"]
    assert config["azure_deployment"] == _VALUES["AZURE_OPENAI_DEPLOYMENT"]


def test_standalone_server_does_not_read_the_process_environment(standalone_provider, monkeypatch):
    for key, value in _VALUES.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(AzureConfigUnavailable):
        _client_config(standalone_provider())
