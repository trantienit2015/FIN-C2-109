# Template Design Specification — FIN-C2-109

## Position in AgentCore Architecture

- **Agent Class**: `FinC2109Graph`
- **L1 Base**: AgentBaseGraph (outer graph, Cat 2) — inherits directly, no L2 intermediary.
- **Three-Layer Separation**:
  - State: flat TypedDict composition extending `AgentState` (no Pydantic — msgpack incompatible)
  - Node: L1 inheritance (Template Method: `execute(self, state: dict) -> dict` override only)
  - Graph: composition (`register_nodes()` for node substitution); Cat 2 = outer `AgentBaseGraph`
    + `GraphNode` in the `main` slot wrapping an inner `BaseGraph` domain workflow.

## Architecture Overview — Cat 2 (outer + inner)

### Outer graph (`src/graph/graph.py`, `FinC2109Graph`)

| Node | Responsibility | Input State | Output State | Inherits/Overrides |
|------|---------------|-------------|--------------|-------------------|
| initialize | Set schema_version, session_id, trust_level | — | — | InitializeNode (default) |
| pre_process | QueryNormalizeNode + FrameworkRouteNode: normalize query, detect language, route to applicable frameworks (EU Act / FSA MRM / Japan Act) | `user_input` | `ai_system_description`, `eu_customer_exposure`, `detected_language`, `applicable_frameworks`, `validated_input` (JSON string) | `PreProcessNode(FunctionNode)` |
| main | `ComplianceWorkflowGraphNode(GraphNode)` — wraps inner `ComplianceWorkflowGraph` (HybridRetrieve → ClassificationReason → DocumentationChecklist → FSAMRMMap → ResponseValidate/S-3) | `validated_input` | `high_risk_verdict`, `classification_reasoning`, `documentation_checklist`, `fsa_convergence_map`, `hitl_required`, `conformity_timeline`, `disclaimers` | `GraphNode` |
| post_process | Assemble final compliance-assessment output | merged inner fields | `formatted_output` | `PostProcessNode(FunctionNode)` |
| finalize | Build response_metadata, total_time_ms | — | — | FinalizeNode (default) |

### Inner graph (`src/graph/domain_workflow_graph.py`, `ComplianceWorkflowGraph`)

Linear pipeline: `START → hybrid_retrieve → classification_reason → documentation_checklist → fsa_mrm_map → response_validate → END`

| Inner node | Responsibility |
|---|---|
| `HybridRetrieveNode` | Deterministic hybrid retrieval (keyword-scored dense + article-number match) across the multi-framework KB (`ComplianceKBService`), scoped to `applicable_frameworks`. First inner node — `json.loads(state["user_input"])` to recover the outer payload (Cat 2 data-flow contract: inner graph only sees `user_input` string). |
| `ClassificationReasonNode` | LLM-driven Annex-III reasoning chain grounded in retrieved provisions; classifies HIGH_RISK / LIMITED_RISK / REQUIRES_LEGAL_REVIEW. |
| `DocumentationChecklistNode` | Generates the Annex IV conformity checklist (11 elements), HITL requirement, and Aug-2-2026 timeline. |
| `FSAMRMMapNode` | Maps EU AI Act Annex IV requirements to FSA AI MRM equivalents via `ConvergenceService` (version-pinned convergence table), only for HIGH_RISK verdicts. |
| `ResponseValidateNode` | **S-3 output gate**: mandatory legal disclaimer (non-suppressible, verified via `_extra_security_gate_output()` preservation check) + no-fabricated-citation check (drops fabricated citations, routes to REQUIRES_LEGAL_REVIEW, logs to audit). |

### Data Flow

```
START → initialize → pre_process → main(GraphNode→inner graph) → post_process → finalize → END
                                            ↓ (retry, max 3)
                                          pre_process
```

Cat 2 data-flow contract: `BaseGraph.invoke()` seeds the inner graph with only `user_input` (string)
+ shared fields — NOT the outer state's typed fields. `pre_process` serializes
`{ai_system_description, applicable_frameworks}` into `validated_input` (JSON string);
`ComplianceWorkflowGraphNode.extract_input()` passes that string to the inner graph;
`HybridRetrieveNode` (first inner node) `json.loads()`s it back.

### State Definition (`src/schemas/state.py`)

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| `ai_system_description` | `str` | Normalized AI system description from the caller | pre_process |
| `eu_customer_exposure` | `bool` | Whether the system serves EU customers | pre_process |
| `detected_language` | `str` | EN/JP language detection | pre_process |
| `applicable_frameworks` | `list[str]` | Routed frameworks (EU_AI_ACT_ANNEX_III / FSA_AI_MRM / JAPAN_AI_PROMOTION_ACT) | pre_process |
| `retrieved_provisions` | `list[dict]` | Cited provisions from hybrid retrieval | inner step 1 |
| `high_risk_verdict` | `str` | HIGH_RISK / LIMITED_RISK / REQUIRES_LEGAL_REVIEW | inner step 2 |
| `classification_reasoning` | `str` | LLM reasoning chain grounded in cited articles | inner step 2 |
| `documentation_checklist` | `list[str]` | Annex IV checklist items | inner step 3 |
| `fsa_convergence_map` | `list[dict]` | EU↔FSA convergence entries | inner step 4 |
| `hitl_required` | `bool` | Whether human review is required | inner step 3 |
| `conformity_timeline` | `str` | Timeline to Aug-2-2026 deadline | inner step 3 |
| `disclaimers` | `list[str]` | Mandatory legal disclaimer(s) | inner step 5 (S-3) |

**State Constraints (mandatory):**
- Flat TypedDict only (primitives + JSON-serializable types)
- No JWT, API keys, credentials in State (checkpoint DB leakage)
- InvocationContext via `config["configurable"]` only (not in State)
- No Pydantic models, dataclass, arbitrary Python objects (msgpack incompatible)

## Framework Utilization

### Shared Components Used
- [x] InvocationContext (correlation_id, session_id, caller_trust_level)
- [x] S-1: the outer backbone slots (`PreProcessNode`, the `ComplianceWorkflowGraphNode` main slot
      and `PostProcessNode`) declare `VERIFIED_EXTERNAL`, the level `config/agent.yaml` declares, so
      a caller below it is refused before any step runs. The inner workflow's steps are reached only
      through the main slot and stay `ANONYMOUS`.
## Outcome classification

Nothing is ever silently assessed: a refused description produces no compliance assessment. Each
way a run can end without an assessment falls into one class, and the class decides how it is
reported.

| Class | In this agent | Reported as |
|---|---|---|
| Security failure | Credential-shaped content detected by the baseline S-3 gate | `status=ERROR`, `output=None` |
| Policy withholding | An assessment missing its mandatory legal disclaimers | `status=SUCCESS`, `error_code=DISCLAIMER_WITHHELD`, every assessment field blanked, fixed notice |
| Caller-correctable | Description empty, no applicable framework, or no provisions found | `status=SUCCESS`, `error_code` = `EMPTY_INPUT` / `NO_APPLICABLE_FRAMEWORK` / `NO_PROVISIONS_FOUND` |
| No model configured | No classifier client is passed | `status=SUCCESS` with the default verdict `HIGH_RISK`, stated as pending legal review |
| Dependency failure | A configured classifier model fails or returns nothing | `status=ERROR`; the code is recorded in `error_log` and the audit event, never as a completed run (`CLASSIFIER_UNAVAILABLE`); no verdict is reached |
| Invariant failure | A verdict or provisions a preceding step guarantees are absent | `status=ERROR`; never represented as successful completion |
| Fail-safe downgrade | An assessment citing articles that were never retrieved | `status=SUCCESS`, verdict downgraded to `REQUIRES_LEGAL_REVIEW`, fabricated citation dropped |

Credential-shaped content detected by baseline S-3 causes fail-closed termination:
`status=ERROR`, `output=None`. The template does not transform this terminal status to SUCCESS
and does not emit any source-derived response.

On a policy-withholding or caller-correctable run, `status=SUCCESS` means the agent finished
handling the request safely; it does not mean an assessment was returned. The notice is derived from
the `error_code` alone, so nothing from the request is echoed back. The disclaimer check itself is unchanged: an assessment that
fails it is withheld in full.

**The workflow stops at the refusal.** The inner workflow is wired with unconditional edges, so
each inner node steps aside when the marker is set — doing the work on an already-refused request
is exactly what must not happen. The marker travels in each node's own result dict as well
(the S-3 re-check sees that dict, not the full state), crosses the subgraph boundary through
`get_output` and `merge_output`, and is composed **outer-first**: a refusal raised before the
subgraph is the specific reason, while an inner node only sees that its input is missing.
`PostProcessNode` then returns the documented output shape built from constants, with the reason
in `message`; `message` is present on every run and holds `""` on a normal one. Wording lives in
`src/services/degradation.py` and is derived from the allow-listed code alone, so the description
is never echoed back.

- [x] SecurityViolationError-equivalent: a rejection the caller can act on (empty description, no applicable framework, no provisions found) ends as a degraded success carrying an allow-listed `error_code` — see §Rejection handling
- [ ] S-2: `_extra_security_gate_input()` — not needed; default PII scan on `user_input`/`validated_input` is sufficient for this template's input shape (free-text system description).
- [x] S-3: `_extra_security_gate_output()` — `ResponseValidateNode` implements the **preservation variant**: verifies the mandatory legal disclaimer is present in output after `execute()` (non-raising; returns `state`, or a `DISCLAIMER_WITHHELD` result that makes the output step blank every assessment field). The requirement is scoped by the degradation marker: a refusal carries no assessment, so the check does not apply to it.
- [x] S-4: `emit_trace_event()` — at least one domain-specific event inside every node's `execute()` (query_normalize_rejected/framework_routed, hybrid_retrieve_completed, classification_reasoned, documentation_checklist_generated, fsa_mrm_mapped/skipped, response_validated/response_validate_fabrication_detected, compliance_assessment_finalized).

> **S-2/S-3 gate behaviour by node type (ADR-017):**
> - `FunctionNode` subclass (all 7 domain nodes here) → framework `@final` gate always runs automatically; extended via `_extra_security_gate_output()` only on `ResponseValidateNode`.
> - `GraphNode` (`ComplianceWorkflowGraphNode`) → deliberate no-op; the inner subgraph's own `ResponseValidateNode` S-3 gate already applies before `merge_output()`.

### Composition Pattern

- **Pattern**: Cat 2 — outer `AgentBaseGraph` + `GraphNode` (`main` slot) wrapping inner `BaseGraph` subgraph.
- **Composition target**: `ComplianceWorkflowGraph` (inner, `src/graph/domain_workflow_graph.py`).
- **Error propagation strategy**: `propagate` (fail fast — inner graph exceptions re-raise as `SubgraphError`).

## Import Isolation Confirmation
- [x] Template does not import agenticstar-platform SDK (Level 0)
- [x] Import targets: `framework/` and `shared/` only (no `agents/base/` required)

## Design Decision Record

| Decision | Option A | Option B | Chosen | Rationale |
|----------|----------|----------|--------|-----------|
| L1 base type | AgentBaseGraph | AutonomousBaseGraph | **AgentBaseGraph** | Fixed multi-step pipeline for a specific compliance job (Cat 2), not an autonomous reasoning loop. |
| Composition pattern | Flat 3-node (Cat 1 style) | Outer+GraphNode+inner (Cat 2) | **Outer+GraphNode+inner** | Cat 2 requires the outer `AgentBaseGraph` + `GraphNode`(main) + inner `BaseGraph` pattern per `gate-composition`; the 7-step design workflow does not fit the fixed 3-slot Cat 1 backbone. |
| Node count (7 workflow steps → final) | 7 flat nodes | 3 outer slots + 5 inner nodes | **3 outer + 5 inner** | QueryNormalize+FrameworkRoute → outer `pre_process`; HybridRetrieve/ClassificationReason/DocumentationChecklist/FSAMRMMap/ResponseValidate → 5 inner nodes; output assembly → outer `post_process`. |
| S-3 gate placement | Outer `post_process` | Inner `ResponseValidateNode` | **Inner `ResponseValidateNode`** | The disclaimer/no-fabrication check depends on `classification_reasoning` + `retrieved_provisions`, both inner-only fields; gating inside the inner graph keeps the check close to the data it validates. |

## 1. Deployment entry points

The agent is reachable through two entry points, and both resolve their runtime inputs the same way.

| Entry point | File | Used by |
|---|---|---|
| Standalone HTTP | `src/api/server.py` | staging rehearsal, direct invocation |
| Marketplace one-shot Pod | `cli.py` | the platform runner (container `CMD`) |

Both read runtime parameters from `config/config.yaml` — the manifest carries discovery metadata
only — and both scope secrets to the same location (`namespace=fin`, `agent_name=fin-c2-109`), so a
value in the per-agent file `env/agents/fin/fin-c2-109/.env.<env>` resolves identically on both
paths. The Marketplace entry point's provider reads the process environment first and the file
second; the standalone server's provider reads only the file.

**Deployment-provided LLM client.** The three Azure OpenAI connection values
(`AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT` — the bare resource endpoint — and
`AZURE_OPENAI_DEPLOYMENT`) are resolved through the agent's own secret provider — the agent code
never reads the process environment itself; which sources that provider consults is set per entry
point, as above. The standalone entry point passes a client as `config["llm"]` only when the
provider client is available and all three values already resolve at startup; otherwise the key
stays unset. The Marketplace entry point cannot resolve the values while the graph is built, so
whenever the provider client is available it passes a client that resolves them on each call. With
no client passed, the classification step does not reason: it returns the default verdict
`HIGH_RISK`, stated in the reasoning as pending legal review, with the retrieved citations. With a
client passed, a value missing at call time or a failed call ends the run as `status=ERROR` with
`CLASSIFIER_UNAVAILABLE` recorded in `error_log` and the audit event; neither the missing value nor
the provider's own error text is returned. The manifest declares neither the three secrets nor the
provider extra: the model is optional, and declaring them would make it a startup prerequisite.

**Progress events.** Each pipeline stage emits a non-terminal progress event at its start, so a
caller sees the run advancing. Outside the Marketplace runtime the emitter resolves to a no-op, so
the same code is safe on every path. Terminal events belong to the platform runner and are never
emitted by this agent.

**Caller authentication at the standalone entry point.** A caller that no upstream middleware
vouched for stays anonymous unless it presents a deployment-level credential: the external bearer
token grants the verified-external level, and a separate staging-only runner credential is the only
way to reach the internal level. Trust established upstream is never changed.

## Classifier failure

A configured classifier model that fails or returns nothing is a runtime dependency failure:
the run ends as `status=ERROR`, and `CLASSIFIER_UNAVAILABLE` is recorded in `error_log` and in
the audit event. The code is not placed in `error_code`, which marks a run that completed
without an assessment.

No verdict is produced on that path. The verdict extractor falls through to
`REQUIRES_LEGAL_REVIEW` on empty text, so an unanswered call would otherwise be reported as a
risk classification with no reasoning behind it.

**A composing caller branches on `error_code`, not on `status`.** `status=SUCCESS` with a
non-empty `error_code` means the run completed and no assessment was produced; the code
says why the agent declined (`EMPTY_INPUT`, `NO_APPLICABLE_FRAMEWORK`,
`NO_PROVISIONS_FOUND`). A run that could not perform ends as `status=ERROR`. `merge_output`
maps the marker to the parent. An assessment withheld by the disclaimer check is reported the
same way (`DISCLAIMER_WITHHELD`). An internally inconsistent run is a defect and ends as
`status=ERROR`.
