"""AgentCore Platform v1.0 — FIN-C2-109 inner domain workflow graph."""

# Inner graph for the Cat 2 compliance-assessment workflow.
# Inherits BaseGraph directly for a fully custom node topology.
# Called by ComplianceWorkflowGraphNode.get_subgraph() in graph.py.
#
# Pipeline (linear):
#   START -> hybrid_retrieve -> classification_reason -> documentation_checklist
#         -> fsa_mrm_map -> response_validate -> END
#
# Data flow note: hybrid_retrieve (first inner node) parses
# json.loads(state["user_input"]) to recover ai_system_description +
# applicable_frameworks — see src/nodes/hybrid_retrieve_node.py.

from typing import Any

from framework.graph.base_graph import BaseGraph
from framework.schemas.agent_state import AgentState
from framework.schemas.agent_status import AgentStatus
from langgraph.graph import END, START

from src.nodes.classification_reason_node import ClassificationReasonNode
from src.nodes.documentation_checklist_node import DocumentationChecklistNode
from src.nodes.fsa_mrm_map_node import FSAMRMMapNode
from src.nodes.hybrid_retrieve_node import HybridRetrieveNode
from src.nodes.response_validate_node import ResponseValidateNode
from src.schemas.state import State


class ComplianceWorkflowGraph(BaseGraph):
    """Inner graph for the FIN-C2-109 multi-framework compliance-assessment workflow."""

    # ── Identity ──────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "fin_c2_109_compliance_workflow"

    @property
    def state_schema(self) -> type:
        return State

    # ── Config validation ────────────────────────────────────────────────

    def _validate_config(self) -> None:
        """No mandatory config for this inner workflow — top_k/llm are optional."""
        pass

    # ── Node registration ────────────────────────────────────────────────

    def register_nodes(self) -> None:
        """Register domain nodes. No super() — BaseGraph.register_nodes() is abstract.

        initialize/finalize are outer backbone concerns, handled by AgentBaseGraph
        in graph.py — do NOT register them here.
        """
        top_k = self.config.get("top_k", 8) if hasattr(self, "config") else 8
        llm = self.config.get("llm") if hasattr(self, "config") else None

        self._nodes["hybrid_retrieve"] = HybridRetrieveNode(top_k=top_k)
        self._nodes["classification_reason"] = ClassificationReasonNode(llm=llm)
        self._nodes["documentation_checklist"] = DocumentationChecklistNode()
        self._nodes["fsa_mrm_map"] = FSAMRMMapNode()
        self._nodes["response_validate"] = ResponseValidateNode()

    # ── Edge wiring ───────────────────────────────────────────────────────

    def add_edges(self) -> None:
        self._sg.add_edge(START, "hybrid_retrieve")
        self._sg.add_edge("hybrid_retrieve", "classification_reason")
        self._sg.add_edge("classification_reason", "documentation_checklist")
        self._sg.add_edge("documentation_checklist", "fsa_mrm_map")
        self._sg.add_edge("fsa_mrm_map", "response_validate")
        self._sg.add_edge("response_validate", END)

    # ── Routing ───────────────────────────────────────────────────────────

    def route(self, state: AgentState) -> str:
        """Required by BaseGraph ABC. Linear topology -> never called."""
        return END if state.get("status") == AgentStatus.ERROR.value else "response_validate"

    # ── Output shape ──────────────────────────────────────────────────────

    def get_output(self, state: AgentState) -> dict[str, Any]:
        """Shape the sub_result dict consumed by ComplianceWorkflowGraphNode.merge_output()."""
        return {
            "error_code": state.get("error_code"),
            "high_risk_verdict": state.get("high_risk_verdict"),
            "classification_reasoning": state.get("classification_reasoning"),
            "documentation_checklist": state.get("documentation_checklist", []),
            "fsa_convergence_map": state.get("fsa_convergence_map", []),
            "hitl_required": state.get("hitl_required", False),
            "conformity_timeline": state.get("conformity_timeline", ""),
            "disclaimers": state.get("disclaimers", []),
            "status": state.get("status"),
            "trace_id": state.get("trace_id"),
            "correlation_id": state.get("correlation_id"),
            "node_history": state.get("node_history", []),
        }
