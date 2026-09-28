# Test Specification — FIN-C2-109

## Test Strategy
- Coverage target: every node — ≥1 success path + ≥1 error/edge path; full outer+inner graph integration.
- Test types: Unit (`tests/unit/`) / Integration (`tests/integration/`) / Proof-of-Boundary (`tests/proof_of_boundary/`)

## Framework Compliance Tests (Mandatory)

| TC-ID | Test | Expected Result | Result |
|-------|------|----------------|--------|
| TC-01 | State contract: flat TypedDict | Type check pass, no Pydantic/dataclass | PASS |
| TC-02 | A caller-correctable rejection (empty description / no matched framework / no provisions) ends as a degraded success | `status == AgentStatus.SUCCESS` + allow-listed `error_code`, no assessment | PASS |
| TC-02b | An internally inconsistent run fails; a missing disclaimer withholds the assessment; a fabricated citation is downgraded | invariant failure → `status == AgentStatus.ERROR`; missing disclaimer → `SUCCESS` + `DISCLAIMER_WITHHELD`; fabricated citation → `REQUIRES_LEGAL_REVIEW` | PASS |
| TC-03 | No JWT/Credential in State | CI `gate-credential-scan`: 0 violations | PASS |
| TC-04 | InvocationContext via configurable only | No direct State access to InvocationContext | PASS |
| TC-05 | S-4: no duplicate lifecycle events in `execute()` | `node_start` / `node_complete` / `node_error` absent from `execute()` body | 0 duplicates |
| TC-06 | S-2: `_security_gate_input()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final`) | 0 overrides |
| TC-07 | S-3: `_security_gate_output()` not overridden (`FunctionNode` subclass) | `TypeError` raised at class definition if overridden (`@final`) | 0 overrides |
| TC-08 | `required_trust_level` declared on every `FunctionNode` | `gate-trust-level-check` CI: 0 violations | PASS |
| TC-09 | S-2: `_extra_security_gate_input()` — N/A for this template (default PII scan sufficient) | N/A | N/A |
| TC-10 | S-3: `_extra_security_gate_output()` non-trivial — `ResponseValidateNode` preservation check | Mandatory legal disclaimer verified present; missing → `DISCLAIMER_WITHHELD`, assessment withheld; scoped out on a degraded run (no assessment to preserve) | PASS |
| TC-11 | S-4: at least one domain `emit_trace_event()` inside each `execute()` | Domain event emitted on every invocation path | ≥1 per node |

## Proof-of-Boundary Tests (Mandatory)

| PB-ID | Boundary | Test | Expected Result | Result |
|-------|----------|------|----------------|--------|
| PB-1 | BaseNode → EventEmitter | `emit_trace_event()` fires on every invocation path | No silent failures | PASS |
| PB-2 | State serialization | Post-invoke State is primitives only | No Pydantic/dataclass | PASS |
| PB-3 | L1 → External service | `ComplianceKBService`/`ConvergenceService` deterministic retrieval (in-repo KB seed; swappable for a real vector store) | Data retrieved | PASS |
| PB-4 | Import isolation | No Level 0 imports under `src/` | AST scan: 0 violations | PASS |
| PB-5 | Checkpoint safety | No JWT/Pydantic in checkpoint | Inspection pass | PASS |
| PB-6 | Invoke execution order | `__call__()`: S-1 trust gate → S-4 `node_start` → S-2 `_security_gate_input` → `execute()` → S-3 `_security_gate_output` → S-4 `node_complete`, for every `src/nodes/*.py` `FunctionNode` | Order verified (auto-discovery, `test_pb_invoke_order.py`) | PASS |

## Business Logic Tests

| TC-ID | Test | Input | Expected Result | Result |
|-------|------|-------|----------------|--------|
| BL-01 | FrameworkRouteNode routes EU-exposed credit-scoring system to EU_AI_ACT_ANNEX_III + FSA_AI_MRM + JAPAN_AI_PROMOTION_ACT | "Credit scoring AI system with EU customer exposure" | `applicable_frameworks` contains all 3 | PASS |
| BL-02 | FrameworkRouteNode refuses input with no applicable framework signal | "A generic chatbot for internal FAQ" | degraded `SUCCESS` + `NO_APPLICABLE_FRAMEWORK`; the reason reaches `output.message` | PASS |
| BL-03 | HybridRetrieveNode retrieves EU Annex III credit-scoring provisions | description mentioning "credit scoring", frameworks=[EU_AI_ACT_ANNEX_III] | `retrieved_provisions` contains Annex III(5)(b) | PASS |
| BL-04 | ClassificationReasonNode classifies HIGH_RISK when provisions cite Annex III credit-scoring article | retrieved_provisions with Annex III(5)(b) | `high_risk_verdict == "HIGH_RISK"` | PASS |
| BL-05 | DocumentationChecklistNode generates full 11-item Annex IV checklist for HIGH_RISK | `high_risk_verdict = "HIGH_RISK"` | `len(documentation_checklist) == 11`, `hitl_required == True` | PASS |
| BL-06 | FSAMRMMapNode returns non-empty convergence map for HIGH_RISK verdict | HIGH_RISK + full checklist | `fsa_convergence_map` non-empty | PASS |
| BL-07 | FSAMRMMapNode skips convergence mapping for non-HIGH_RISK verdict | `high_risk_verdict = "LIMITED_RISK"` | `fsa_convergence_map == []` | PASS |
| BL-08 | ResponseValidateNode attaches mandatory legal disclaimer on success | valid verdict + reasoning | `disclaimers` non-empty | PASS |
| BL-09 | ResponseValidateNode drops fabricated citation and routes to REQUIRES_LEGAL_REVIEW | `classification_reasoning` cites "Article 99" not in `retrieved_provisions` | `high_risk_verdict == "REQUIRES_LEGAL_REVIEW"`, error_log records the fabrication | PASS |
| BL-10 | Full outer+inner graph integration: EU-exposed credit-scoring query → HIGH_RISK assessment with checklist + convergence + disclaimer | end-to-end `agent.invoke(...)` | `result["status"] == AgentStatus.SUCCESS.value`, `result["output"]["high_risk_verdict"] == "HIGH_RISK"` | PASS |

## Test Execution Summary
- Execution date: 2026-07-03
- Total tests: see the `pytest tests/ -v` output of the current run
- Pass: all / Fail: 0 / Skip: 0 (no vacuous skips)
- Coverage: node-level (unit) + full-graph (integration) + boundary (proof_of_boundary)

## 1. Deployment path tests

### TC-DEP-01 Marketplace entry point identity — `tests/unit/test_cli_entry_point.py`

| Case | Expected |
|---|---|
| Identity is concrete | `agent_name` / `namespace` are non-empty and not the runner default |
| Identity matches the HTTP entry point | the values equal what `src/api/server.py` passes to `secrets_factory`; where that entry point provisions no secrets, they equal the manifest `namespace` and the lower-cased template id |
| The runner call uses the constants | `run_agent_marketplace` is called with the module constants, not inline literals |

### TC-DEP-02 Standalone entry point boundary — `tests/proof_of_boundary/test_server_llm_injection.py`

| Case | Expected |
|---|---|
| Boots with no credential provisioned | the module imports and the app/agent objects are constructed |
| External bearer never reaches the internal level | resolves to the verified-external level |
| Staging runner credential reaches the internal level | resolves to the internal level |
| Wrong or missing bearer while auth is enabled | rejected with 401 |

### TC-DEP-03 The model on the deployment path — `tests/integration/test_deployment_without_llm_credentials.py`

| Case | Expected |
|---|---|
| No client passed | the default verdict `HIGH_RISK` is returned |
| The per-call client the Marketplace entry point injects, with none of the three connection values supplied | the call is attempted, cannot resolve its values, and the run ends as `status=ERROR` with no output |
| The manifest | does not declare the three connection values or the provider extra as startup requirements |

### TC-DEP-04 Where each entry point reads the model's connection values — `tests/integration/test_llm_credential_sources.py`

| Case | Expected |
|---|---|
| Marketplace entry point, values in the process environment | the provider it builds resolves them and they reach the client the adapter constructs |
| Marketplace entry point, values only in `env/agents/fin/fin-c2-109/.env.<env>` | resolved from the file |
| Standalone server, values only in the per-agent file | the provider it builds at import resolves them |
| Standalone server, values only in the process environment | not resolved; the adapter reports the values as unavailable |

### TC-08b Outer backbone trust — `tests/proof_of_boundary/test_pb_outer_trust.py`

| Case | Expected |
|---|---|
| Declared levels | `PreProcessNode`, the main-slot GraphNode and `PostProcessNode` declare the manifest's `required_trust_level` |
| `ANONYMOUS` caller at each outer slot | refused by the S-1 gate with `status=ERROR`; `execute()` never runs |
| `ANONYMOUS` caller through the compiled graph | `status=ERROR`, no output |

## Outcome classification

A refusal the caller can act on, and an assessment withheld under the answer-quality contract, end
the run as **SUCCESS carrying an allow-listed `error_code`**, with a fixed notice in
`output.message`. The refusal itself is unchanged: nothing is retrieved or classified, no
assessment is produced, and the audit events record it. `status=SUCCESS` on such a run means the
request was handled safely, not that an assessment was returned.

A security failure (credential-shaped content, baseline S-3) and an invariant failure (a verdict or
provisions a preceding step guarantees are absent) end as `status=ERROR` and are never represented
as a successful completion.

| Case | `error_code` | Covered by |
|---|---|---|
| Empty description | `EMPTY_INPUT` | `unit/test_pre_process_node.py`, `unit/test_hybrid_retrieve_node.py`, `integration/test_graph.py::test_empty_input_degrades_instead_of_failing` |
| No applicable framework | `NO_APPLICABLE_FRAMEWORK` | `unit/test_pre_process_node.py`, `integration/test_graph.py::test_no_applicable_framework_degrades` |
| No provisions found | `NO_PROVISIONS_FOUND` | `unit/test_hybrid_retrieve_node.py` (KB miss path) |
| Assessment without its disclaimer | `DISCLAIMER_WITHHELD` | `unit/test_response_validate_node.py::test_extra_security_gate_output_rejects_missing_disclaimer` |
| Missing verdict or provisions inside the workflow | — (`status=ERROR`, invariant failure) | `unit/test_classification_reason_node.py`, `unit/test_documentation_checklist_node.py`, `unit/test_response_validate_node.py` |

### Properties asserted about a degraded run

| Property | Covered by |
|---|---|
| The classifier is not merely unused — it is never reached (an injected LLM fails the test if called) | `integration/test_graph.py::test_refused_request_never_reaches_the_classifier` |
| The description is not echoed into the output | `integration/test_graph.py::test_degraded_output_never_echoes_the_description` |
| `message` is present on every run (`""` when normal) | `integration/test_graph.py::test_success_path_carries_an_empty_message` |

### Classifier failure

| ID | Test | Expected |
|---|---|---|
| U-1 | Configured classifier raises | `status == ERROR`; no `high_risk_verdict`; `error_log` starts with `CLASSIFIER_UNAVAILABLE:` |
| U-2 | Configured classifier returns nothing | same — an empty answer must not become a classification |

Covered by `unit/test_classification_reason_node.py::TestClassifierFailureEndsAsAnError`.
