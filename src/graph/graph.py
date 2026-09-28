"""AgentCore Platform v1.0 — FIN-C2-109 outer graph (Cat 2)."""

# Outer graph: AgentBaseGraph backbone (identical shape to Cat 1).
# Domain complexity is hidden inside the `main` slot via
# ComplianceWorkflowGraphNode, which wraps the inner ComplianceWorkflowGraph
# (src/graph/domain_workflow_graph.py).
#
# Pipeline (fixed backbone):
#   START -> initialize -> pre_process -> main -> {route} -> post_process -> finalize -> END
#
# ComplianceWorkflowGraphNode MUST live in this file (NOT under src/nodes/) —
# tests/proof_of_boundary/test_pb_invoke_order.py auto-discovers every BaseNode
# subclass under src/nodes/ and asserts the FunctionNode S-1->S-4->S-2->execute
# ->S-3->S-4 lifecycle. GraphNode.__call__() intentionally does NOT run that
# lifecycle (it delegates security gating to the inner subgraph) — placing it
# here keeps PB-6 from false-failing on it.

from typing import Any, ClassVar

from framework.graph.agent_base_graph import AgentBaseGraph
from shared.services.events import emitter
from shared.services.events.types import EventType
from framework.nodes.graph_node import GraphNode
from framework.schemas.agent_state import AgentState
from framework.schemas.trust_level import TrustLevel

from src.nodes.post_process_node import PostProcessNode
from src.nodes.pre_process_node import PreProcessNode
from src.schemas.state import State


class ComplianceWorkflowGraphNode(GraphNode):
    """Wraps the inner multi-framework compliance-assessment workflow (`main` slot)."""

    # S-1: the outer main slot sits on the caller's input path, so it enforces the
    # verified caller the manifest declares instead of inheriting the ANONYMOUS default.
    required_trust_level: ClassVar[TrustLevel] = TrustLevel.VERIFIED_EXTERNAL

    # "propagate" (default): re-raise inner graph exceptions as SubgraphError (fail fast).
    error_strategy: ClassVar[str] = "propagate"

    # HITL interrupts (if any) stay inside the inner graph.
    propagate_hitl: ClassVar[bool] = False

    def __init__(self, top_k: int = 8, llm: Any | None = None):
        super().__init__()
        self._top_k = top_k
        self._llm = llm

    def get_subgraph(self) -> AgentBaseGraph:
        """Instantiate the inner compliance-assessment workflow graph."""
        from src.graph.domain_workflow_graph import ComplianceWorkflowGraph

        sg = ComplianceWorkflowGraph(config=self._parent_config())
        sg.compile()
        return sg

    def extract_input(self, state: AgentState) -> str:
        """Return the JSON-string validated_input set by pre_process."""
        # Progress (non-terminal) event for the caller, emitted as the subgraph step
        # begins. Outside the Marketplace runtime this is a no-op emitter.
        emitter().emit_event(
            event_type=EventType.PROGRESS_UPDATE,
            message="Working on the request...",
            metadata={"step": "main"},
        )
        value = state.get("validated_input", state.get("user_input", ""))
        return value if isinstance(value, str) else str(value)

    def merge_output(self, state: AgentState, sub_result: dict[str, Any]) -> dict[str, Any]:
        """Map inner graph sub_result fields back into the outer state."""
        return {
            # The degradation marker has to cross the schema boundary explicitly:
            # post_process reads it to report a refusal instead of an assessment, and
            # GraphNode maps only the fields named here. A refusal raised outside the
            # subgraph is already on the parent state and is the more specific reason —
            # the inner node only sees that its input is missing — so the parent's marker
            # wins and an inner run that did not degrade cannot erase it.
            "error_code": state.get("error_code") or sub_result.get("error_code", ""),
            "high_risk_verdict": sub_result.get("high_risk_verdict"),
            "classification_reasoning": sub_result.get("classification_reasoning"),
            "documentation_checklist": sub_result.get("documentation_checklist", []),
            "fsa_convergence_map": sub_result.get("fsa_convergence_map", []),
            "hitl_required": sub_result.get("hitl_required", False),
            "conformity_timeline": sub_result.get("conformity_timeline", ""),
            "disclaimers": sub_result.get("disclaimers", []),
            "status": sub_result.get("status"),
        }

    def _parent_config(self) -> dict[str, Any]:
        """Forward config keys the inner graph needs (top_k, llm)."""
        return {"top_k": self._top_k, "llm": self._llm}


class FinC2109Graph(AgentBaseGraph):
    """FIN-C2-109 — Financial Services EU AI Act High-Risk AI Compliance Q&A Agent.

    Cat 2 outer graph: fixed backbone (initialize -> pre_process -> main ->
    post_process -> finalize). Domain complexity lives in the inner
    ComplianceWorkflowGraph, wrapped by ComplianceWorkflowGraphNode (`main` slot).
    """

    @property
    def name(self) -> str:
        return "fin-c2-109"

    @property
    def state_schema(self) -> type:
        return State

    def register_nodes(self) -> None:
        super().register_nodes()  # fills: initialize, finalize (required)
        top_k = self.config.get("top_k", 8)
        llm = self.config.get("llm")
        self._nodes["pre_process"] = PreProcessNode()
        self._nodes["main"] = ComplianceWorkflowGraphNode(top_k=top_k, llm=llm)
        self._nodes["post_process"] = PostProcessNode()

    # add_edges() is NOT overridden — backbone wiring belongs to the framework.


# Stable alias for the standalone entry point import (src/api/server.py).
Graph = FinC2109Graph
