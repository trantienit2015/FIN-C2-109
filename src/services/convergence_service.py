"""AgentCore Platform v1.0"""

# Service layer: EU AI Act <-> FSA AI MRM convergence table. Version-pinned
# (config eu_ai_act_version / fsa_mrm_version) config artifact — the template's
# unique differentiator. Must NOT contain security gating or credentials.

from __future__ import annotations

from typing import Any

_CONVERGENCE_TABLE: list[dict[str, str]] = [
    {
        "eu_ai_act_requirement": "General description of the AI system and its intended purpose",
        "fsa_mrm_equivalent": "FSA-MRM-3.2 model documentation — intended use and scope",
    },
    {
        "eu_ai_act_requirement": "Description of the risk management system (Article 9)",
        "fsa_mrm_equivalent": "FSA-MRM-3.2 model risk management governance framework",
    },
    {
        "eu_ai_act_requirement": "Description of appropriate human oversight measures (Article 14)",
        "fsa_mrm_equivalent": "FSA-MRM-4.1 ongoing monitoring and human-in-the-loop validation",
    },
    {
        "eu_ai_act_requirement": "Description of the system used to evaluate performance post-market (Article 72)",
        "fsa_mrm_equivalent": "FSA-MRM-4.1 ongoing monitoring and validation requirements",
    },
    {
        "eu_ai_act_requirement": "Assessment of cybersecurity measures in place",
        "fsa_mrm_equivalent": "FSA-MRM-3.2 model risk management governance (security controls)",
    },
]


class ConvergenceService:
    """Maps EU AI Act Annex IV requirements to FSA AI MRM equivalents."""

    def __init__(self, table: list[dict[str, str]] | None = None):
        self._table = table if table is not None else _CONVERGENCE_TABLE

    def map_eu_to_fsa(self, checklist: list[str]) -> list[dict[str, Any]]:
        """Return the convergence entries whose EU requirement appears in the checklist."""
        checklist_set = set(checklist)
        return [entry for entry in self._table if entry["eu_ai_act_requirement"] in checklist_set]
