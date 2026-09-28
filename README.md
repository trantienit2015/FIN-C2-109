# FIN-C2-109 — Financial Services EU AI Act High-Risk AI Compliance Q&A Agent

> **Category**: Cat 2 (multi-step workflow for a specific job-to-be-done)
> **Industry**: FIN

## Overview

This agent assesses a financial AI system against the AI regulations that apply to it. Given a description of the system and where its customers are, it routes across the applicable frameworks, retrieves the relevant provisions, reasons about whether the system falls into a high-risk category, and produces the conformity-documentation checklist that classification implies. It also maps requirements across frameworks, so an institution subject to more than one can see where a single piece of evidence satisfies both.

This is an agent template built with the **AGENTIC STAR** development platform and the
**AgentCore Framework**. It is intended to be taken as a starting point: fork it, adapt it to
your own data and policies, and run it inside your own AGENTIC STAR deployment.

## Requirements

**This template does not run standalone.** It requires:

| Requirement | Notes |
|---|---|
| **AGENTIC STAR platform** | The agent connects to the platform at start-up. Without it, start-up fails immediately (see *Behaviour without the platform* below). Deployment guides and API documentation: [AGENTIC STAR Developers](https://developers.fd.agenticstar.tm.softbank.jp/) |
| **AgentCore Framework** (`agenticstar-agentcore`) | Installed from PyPI as a dependency. |
| Python | >=3.11 |

```bash
pip install -e .
```

### Behaviour without the platform

The framework is designed to run **only** on AGENTIC STAR. There is no fallback or degraded
mode. If the platform is unreachable or the SDK version does not match, the agent raises
`PlatformRequired` during graph compile / start-up preflight rather than starting in a partially
working state. This is intentional — a half-running agent is worse than one that refuses to start.

## Credentials — optional, you supply them

This agent can use an Azure OpenAI deployment to reason over the retrieved provisions.
The deployment's credentials are **not** in this repository and are not shipped with it:
they are yours and they bill to your account. They are optional, so `config/agent.yaml`
does not declare them as startup requirements:

| Name | Used for |
|---|---|
| `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_DEPLOYMENT` | Reasoning over the retrieved provisions to reach a risk classification |

Where the agent reads them depends on the entry point:

- **Marketplace entry point (`cli.py`)** — environment variables on the agent's runtime,
  read first; otherwise the per-agent file below.
- **Standalone server (`src/api/server.py`)** — only the per-agent file; the process
  environment is not read on this path. Put the values in
  `env/agents/fin/fin-c2-109/.env.<env>` under the working directory, where `<env>` is
  `dev`, `stg` or `prod` as selected by `AGENTCORE_ENVIRONMENT` (default `dev`). A
  namespace-wide `env/namespaces/fin/.env.<env>` is read too; the per-agent file wins.

Never commit these values or files, and never put them in `config/config.yaml` — that
file ships in the image.

**A model that cannot be reached ends the run as a failure.** The run ends with
`status=ERROR` and the cause recorded in `error_log`; it never presents an unanswered call
as an answer. When no model is configured at all, the classification step does not reason:
it returns the default verdict `HIGH_RISK`, stated as pending legal review. The standalone
server configures a model only when all three values resolve at startup; the Marketplace
entry point configures one whenever the provider library is present in the runtime, so
there a missing value ends the run as a failure too.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

Tests run without a platform connection. Running the agent itself does not.

## Project Structure

```
src/          agent implementation (nodes, services, schemas)
tests/        unit, integration and boundary tests
config/       agent configuration
docs/         design and test specification
```

See `docs/02_design.md` for the design and `docs/03_test_spec.md` for the test specification.

## Customising

1. Adjust `config/` for your own environment and policies.
2. Replace the knowledge sources and sample data with your own.
3. Review the node implementations under `src/nodes/` for domain-specific logic.
4. Re-run the test suite.

## License

MIT — see [LICENSE](LICENSE).

## Status of this repository

This template is published **as is**, by its individual author, under the MIT license. It carries
**no warranty and no support commitment**, and no organisation stands behind its behaviour or
fitness for any purpose. Issues and pull requests may or may not receive a response; that is at
the sole discretion of the repository owner.
