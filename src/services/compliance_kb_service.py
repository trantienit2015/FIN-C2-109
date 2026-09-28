"""AgentCore Platform v1.0"""

# Service layer: deterministic hybrid retrieval (dense + BM25-style article-number
# matching) over the multi-framework regulatory KB (EU AI Act Annex III, FSA AI
# MRM, Japan AI Promotion Act). Must NOT contain security gating or credentials.
# Nodes call this; this calls shared/services/ for external integrations (e.g.
# a real vector store) when configured.

from __future__ import annotations

from typing import Any

# Minimal in-repo KB seed. A production deployment would back this with a real
# vector store (e.g. Qdrant) + BM25 index; this deterministic seed keeps the
# template runnable and testable without external dependencies.
_KB_SEED: list[dict[str, Any]] = [
    {
        "framework": "EU_AI_ACT_ANNEX_III",
        "article": "Article 6",
        "text": "Classification rules for high-risk AI systems referenced in Annex III.",
        "keywords": ["credit scoring", "creditworthiness", "high-risk", "classification"],
    },
    {
        "framework": "EU_AI_ACT_ANNEX_III",
        "article": "Annex III(5)(b)",
        "text": "AI systems intended to be used to evaluate the creditworthiness of natural "
        "persons or establish their credit score, with certain exceptions.",
        "keywords": ["credit scoring", "creditworthiness", "credit score"],
    },
    {
        "framework": "EU_AI_ACT_ANNEX_III",
        "article": "Annex III(4)(c)",
        "text": "AI systems intended to be used for risk assessment and pricing in relation "
        "to natural persons in the case of life and health insurance.",
        "keywords": ["insurance risk", "life insurance", "health insurance", "pricing"],
    },
    {
        "framework": "EU_AI_ACT_ANNEX_III",
        "article": "Annex III(4)(a)",
        "text": "AI systems intended to be used for recruitment or selection of natural "
        "persons, in particular to place targeted job advertisements, to analyse and "
        "filter job applications, and to evaluate candidates.",
        "keywords": ["employment", "recruitment", "hiring"],
    },
    {
        "framework": "EU_AI_ACT_ANNEX_III",
        "article": "Article 9",
        "text": "Risk management system requirements for high-risk AI systems.",
        "keywords": ["risk management", "risk assessment"],
    },
    {
        "framework": "EU_AI_ACT_ANNEX_III",
        "article": "Article 14",
        "text": "Human oversight measures for high-risk AI systems.",
        "keywords": ["human oversight", "hitl", "human review"],
    },
    {
        "framework": "FSA_AI_MRM",
        "article": "FSA-MRM-3.2",
        "text": "Financial institutions must establish model risk management governance for "
        "AI systems used in credit decisioning and underwriting.",
        "keywords": ["credit scoring", "underwriting", "model risk", "governance"],
    },
    {
        "framework": "FSA_AI_MRM",
        "article": "FSA-MRM-4.1",
        "text": "Ongoing monitoring and validation requirements for deployed AI models in "
        "financial services, including access-to-financial-services systems.",
        "keywords": ["access to financial services", "monitoring", "validation"],
    },
    {
        "framework": "JAPAN_AI_PROMOTION_ACT",
        "article": "JP-AIPA-2025-Art.7",
        "text": "Domestic obligations for AI system operators under the Japan AI Promotion Act "
        "2025, applicable alongside EU AI Act obligations for EU-exposed entities.",
        "keywords": ["japan", "domestic", "ai promotion act"],
    },
]


class ComplianceKBService:
    """Deterministic hybrid retrieval over the multi-framework regulatory KB."""

    def __init__(self, kb: list[dict[str, Any]] | None = None):
        self._kb = kb if kb is not None else _KB_SEED

    def hybrid_search(self, query: str, frameworks: list[str], top_k: int = 8) -> list[dict[str, Any]]:
        """Dense-keyword + article-number matching, scoped to applicable frameworks.

        Deterministic scoring: count of matched keywords in the query text.
        Returns up to top_k provisions across the applicable frameworks.
        """
        lowered = query.lower()
        scored: list[tuple[int, dict[str, Any]]] = []
        for entry in self._kb:
            if entry["framework"] not in frameworks:
                continue
            score = sum(1 for kw in entry["keywords"] if kw in lowered)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        results = [
            {"framework": e["framework"], "article": e["article"], "text": e["text"]} for _score, e in scored[:top_k]
        ]
        return results
