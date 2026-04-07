# Parallax V3 — Autonomous Research Operating System

> **Date:** 2026-03-28
> **Author:** Claude Code (Opus 4.6) + OpenSens DarkLab Team
> **Status:** Architecture Spec — Pre-Implementation

---

## 1. Executive Summary

Parallax V3 is not a rewrite. It is a **meta-orchestration layer** that unifies five existing OpenSens systems into one governed research operating system:

| System | What It Does | What V3 Uses From It |
|--------|-------------|---------------------|
| **Parallax V2** | Graph-based research pipeline (Search→Draft→Revise) | Workflow DAG engine, 14 source adapters, SDK event protocol |
| **OAS (Agent Swarm)** | LangGraph swarm with governance middleware | Campaign DAG, DRVP events, Paperclip budget/audit, OpenViking memory |
| **DarkLab** | 4-device distributed AI cluster | OpenClaw gateway, 16 skills, Ed25519 signing, device discovery |
| **OAE (Academic Explorer)** | Material/sensor discovery agents | Campaign orchestrator, phase reflection, convergence scoring |
| **DAMD** | Decentralized compute marketplace | Job dispatch, site scoring, financial modeling, simulation engine |

**V3's job:** Connect a research question to literature, debate, experiment, simulation, and compute execution within one governed, restartable, cost-visible workflow.

**V3 is NOT:**
- A generic AI chat app
- A static dashboard
- A React rewrite of the Vue frontend (frontend evolves incrementally)

**V3 IS:**
- The command center for OpenSens DarkLab
- A workflow cockpit where humans and agents collaborate on research
- A bridge from reasoning to execution (experiments, simulations, compute jobs)

---

## 2. Product Definition

### 2.1 Four Operating Modes

```
                    ┌─────────────────────────────────────────┐
                    │         PARALLAX V3 COMMAND CENTER       │
                    ├────────┬────────┬──────────┬────────────┤
                    │Academic│Experi- │  DAMD    │Governance  │
                    │Research│ment    │Intel     │& Collab    │
                    ├────────┼────────┼──────────┼────────────┤
                    │Search  │EIP     │Site Score│Budgets     │
                    │Map     │Safety  │Job Spec  │Approvals   │
                    │Debate  │Execute │Dispatch  │Audit Trail │
                    │Validate│QC      │Simulate  │Multi-User  │
                    │Ideas   │Analyze │Forecast  │Templates   │
                    │Draft   │Report  │Cost Est  │Lineage     │
                    │Revise  │Compare │Telemetry │Issues      │
                    └────────┴────────┴──────────┴────────────┘
                                      │
                    ┌─────────────────┼─────────────────────┐
                    │                 │                     │
              ┌─────▼─────┐   ┌──────▼──────┐   ┌────────▼────────┐
              │ DarkLab    │   │ OAS Swarm   │   │ DAMD Compute    │
              │ Cluster    │   │ + Paperclip │   │ Marketplace     │
              │ (3 Macs)   │   │ Governance  │   │ (Distributed)   │
              └────────────┘   └─────────────┘   └─────────────────┘
```

### 2.2 Core User Journey

```
Topic → [Swarm Research] → [Debate] → [Novelty Validation] → [Plan]
  → [Simulation / Experiment] → [Report] → [Archive / Restart / Branch]
```

Every step is:
- Restartable from any point
- Versioned (artifacts, drafts, configs)
- Event-emitting (DRVP protocol)
- Cost-visible (Paperclip ledger)
- Auditable (append-only log)
- Governed (approval gates for risky actions)

---

## 3. System Architecture

### 3.1 Layer Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    FRONTEND APPLICATION LAYER                     │
│  Vue 3 + TypeScript + Pinia + Tailwind CSS 4                    │
│  ┌──────────┬──────────────────┬──────────────┬────────────────┐│
│  │ Sidebar  │  Center Workspace │  Inspector   │ Event Timeline ││
│  │ Projects │  Phase Content    │  Settings    │ DRVP Console   ││
│  │ Workflow │  Graph/Map/3D     │  Evidence    │ Cost Ticker    ││
│  │ Controls │  Draft Editor     │  Costs       │ Agent Activity ││
│  └──────────┴──────────────────┴──────────────┴────────────────┘│
└──────────────────────────┬───────────────────────────────────────┘
                           │ REST + SSE + WebSocket
┌──────────────────────────▼───────────────────────────────────────┐
│                      V3 GATEWAY SERVICE                          │
│  FastAPI + Python 3.11                                           │
│  ┌──────────────┬──────────────┬──────────────┬────────────────┐│
│  │ Workflow API  │ Agent API    │ Execution API│ Governance API ││
│  │ (phases,      │ (dispatch,   │ (EIP, RR,    │ (budget,       ││
│  │  restart,     │  skills,     │  jobs,       │  approvals,    ││
│  │  artifacts)   │  memory)     │  sandbox)    │  audit, RBAC)  ││
│  └──────┬───────┴──────┬───────┴──────┬───────┴───────┬────────┘│
└─────────┼──────────────┼──────────────┼───────────────┼─────────┘
          │              │              │               │
┌─────────▼──────────────▼──────────────▼───────────────▼─────────┐
│                    ORCHESTRATION LAYER                            │
│  ┌──────────────┬──────────────┬──────────────┬────────────────┐│
│  │ Parallax V2  │ OAS Campaign │ OAE Campaign │ DRVP Event     ││
│  │ DAG Engine   │ DAG Engine   │ Orchestrator │ Bus (Redis)    ││
│  └──────┬───────┴──────┬───────┴──────┬───────┴───────┬────────┘│
│         │              │              │               │          │
│  ┌──────▼──────────────▼──────────────▼───────────────▼────────┐│
│  │              MIDDLEWARE PIPELINE                              ││
│  │  Request → Budget → Audit → Governance → Memory → Handler   ││
│  └─────────────────────────────────────────────────────────────┘│
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                      EXECUTION LAYER                             │
│  ┌──────────────┬──────────────┬──────────────────────────────┐ │
│  │ Local        │ DarkLab      │ DAMD Marketplace             │ │
│  │ Sandbox      │ Cluster      │ (Distributed Compute)        │ │
│  │ (subprocess) │ (OpenClaw)   │                              │ │
│  └──────────────┴──────────────┴──────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                      PERSISTENCE LAYER                           │
│  ┌──────────────┬──────────────┬──────────────┬────────────────┐│
│  │ PostgreSQL   │ SQLite       │ Redis        │ File Store     ││
│  │ (Paperclip   │ (V2 legacy,  │ (DRVP events,│ (artifacts,    ││
│  │  governance, │  dev mode)   │  pub/sub,    │  figures,      ││
│  │  V3 tables)  │              │  cache)      │  exports)      ││
│  └──────────────┴──────────────┴──────────────┴────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Key Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend framework | **Vue 3** (evolve, not rewrite) | 137 tests, 9 stage components, working stores — rewrite adds months with no user benefit |
| V3 Gateway | **FastAPI** (new service) | Async-native, Pydantic v2 contracts, consistent with DAMD/OAE stack |
| V2 backend | **Keep running** as internal service | 43 endpoints work — V3 gateway proxies/extends, doesn't replace |
| Primary DB | **PostgreSQL** (new tables) | Paperclip already uses it; V3 governance/cost/audit tables need real ACID |
| Legacy DB | **SQLite** (V2 pipeline data) | Stays for dev mode + existing runs; V3 reads via V2 service |
| Event bus | **Redis Pub/Sub** (DRVP) | OAS already uses it; 22 event types defined; V3 adds ~10 more |
| Agent dispatch | **OAS middleware pipeline** | Budget→Audit→Governance→Memory already built; V3 reuses it |
| Compute dispatch | **DAMD Coordinator** | 4 dispatch strategies, marketplace matching, 498 tests |

### 3.3 What V3 Gateway Does vs What It Delegates

| Responsibility | V3 Gateway | Delegated To |
|---------------|------------|--------------|
| Project CRUD, templates | **Owns** | — |
| Workflow phase definitions | **Owns** | — |
| Unified cost ledger | **Owns** | Paperclip (source of truth for per-agent costs) |
| Approval lifecycle | **Owns** | Paperclip (issue tracking backend) |
| Unified event stream | **Owns** (aggregates) | Redis DRVP (transport) |
| Research pipeline execution | Delegates | Parallax V2 engine (via SDK or internal API) |
| Agent swarm dispatch | Delegates | OAS campaign engine |
| Experiment sandbox | Delegates | DarkLab experiment node (via OpenClaw) |
| Distributed compute jobs | Delegates | DAMD Coordinator |
| Material discovery | Delegates | OAE campaign orchestrator |
| Memory/context | Delegates | OpenViking (OAS memory service) |

---

## 4. Domain Model

### 4.1 Core Entities

```
Project
  ├── has many → Workflow Runs
  │                ├── has many → Phases (DAG nodes)
  │                │               ├── has → PhaseConfig
  │                │               ├── has → PhaseInputs / PhaseOutputs
  │                │               ├── has many → Artifacts
  │                │               ├── has many → CostEntries
  │                │               └── has many → Events
  │                ├── has many → Edges (DAG connections)
  │                └── has → BudgetAllocation
  ├── has many → Approvals
  ├── has many → AuditEntries
  └── has many → Members (roles)

Agent
  ├── has → Role (research | debate | author | experiment | compute)
  ├── has many → Skills
  ├── has → CostClass (cheap | standard | premium)
  └── has → EscalationPolicy

Artifact
  ├── type: paper | topic_map | debate_log | draft | figure | dataset |
  │         experiment_plan | run_record | simulation_report | compute_result
  ├── has → parent Artifact (lineage)
  ├── has → producing Phase
  └── has → producing Agent

ExperimentIntentPackage (EIP)
  ├── derived from → Draft or ValidatedProtocol
  ├── has → SafetyChecks
  ├── has → DeviceRequirements
  ├── has → MaterialsList
  ├── has → ApprovalStatus
  └── produces → RunRecord (RR)

ComputeJobSpec
  ├── has → ResourceRequirements (CPU, GPU, memory, time)
  ├── has → CostEstimate
  ├── has → ExecutionTarget (local | cluster | DAMD)
  └── produces → Artifact (result)
```

### 4.2 Phase Types (Superset of V2 Nodes)

```python
class PhaseType(str, Enum):
    # Research phases (from V2)
    SEARCH = "search"
    MAP = "map"
    DEBATE = "debate"
    VALIDATE = "validate"
    IDEATE = "ideate"
    DRAFT = "draft"
    REVISE = "revise"
    PASS = "pass"

    # Experiment phases (new)
    EXPERIMENT_PLAN = "experiment_plan"      # Generate EIP
    SAFETY_CHECK = "safety_check"           # Validate EIP
    EXPERIMENT_EXECUTE = "experiment_execute" # Run experiment
    EXPERIMENT_ANALYZE = "experiment_analyze" # Analyze results
    EXPERIMENT_COMPARE = "experiment_compare" # Compare runs

    # Compute phases (new)
    COMPUTE_ESTIMATE = "compute_estimate"    # Cost/latency estimate
    COMPUTE_DISPATCH = "compute_dispatch"    # Send to execution target
    COMPUTE_MONITOR = "compute_monitor"      # Track progress
    COMPUTE_COLLECT = "compute_collect"      # Gather results

    # Simulation phases (new)
    SIMULATE_DESIGN = "simulate_design"      # Design simulation
    SIMULATE_RUN = "simulate_run"            # Execute simulation
    SIMULATE_ANALYZE = "simulate_analyze"    # Analyze outputs

    # Governance phases (new)
    APPROVAL_GATE = "approval_gate"          # Human sign-off
    REVIEW_GATE = "review_gate"              # Expert review

    # Synthesis (new)
    SYNTHESIZE = "synthesize"                # Cross-phase synthesis
    REPORT = "report"                        # Generate final report
```

### 4.3 Edge Types (Extended)

```python
class EdgeType(str, Enum):
    DEPENDENCY = "dependency"       # Hard block (from V2)
    CONDITIONAL = "conditional"     # At least one parent (from V2)
    OPTIONAL = "optional"           # Nice-to-have (from V2)
    FEEDBACK = "feedback"           # Loop-back (from V2)
    APPROVAL = "approval"           # Requires human sign-off (new)
    BRANCH = "branch"               # Fork into alternative paths (new)
    MERGE = "merge"                 # Converge alternative paths (new)
```

---

## 5. Data Contracts and Schemas

### 5.1 Project

```typescript
interface Project {
  project_id: string;           // uuid
  name: string;
  description: string;
  domain: "academic" | "experiment" | "simulation" | "damd" | "hybrid";
  template_id?: string;
  owner_id: string;
  budget_cap_usd: number;
  status: "active" | "paused" | "completed" | "archived";
  created_at: string;           // ISO 8601
  updated_at: string;
}
```

### 5.2 Workflow Run

```typescript
interface WorkflowRun {
  run_id: string;               // uuid
  project_id: string;
  template_id?: string;
  config: RunConfig;
  status: "pending" | "running" | "paused" | "completed" | "failed";
  budget_spent_usd: number;
  created_at: string;
  updated_at: string;
}

interface RunConfig {
  sources: string[];
  max_papers: number;
  default_model: string;
  step_settings: Record<string, StepSettings>;
  execution_target: "local" | "cluster" | "damd";
  auto_advance: boolean;
  approval_policy: "auto" | "gate_risky" | "gate_all";
}
```

### 5.3 Phase (Workflow Node)

```typescript
interface Phase {
  phase_id: string;
  run_id: string;
  phase_type: PhaseType;
  label: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped" | "invalidated" | "awaiting_approval";
  config: Record<string, unknown>;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  artifacts: string[];          // artifact_ids
  assigned_agent?: string;      // agent_id
  model_used?: string;
  cost_usd: number;
  score?: number;
  error?: string;
  started_at?: string;
  completed_at?: string;
}
```

### 5.4 Experiment Intent Package (EIP)

```typescript
interface ExperimentIntentPackage {
  eip_id: string;
  run_id: string;
  source_phase_id: string;      // draft or validation that produced this
  title: string;
  hypothesis: string;
  method: string;
  materials: Material[];
  devices: Device[];
  parameters: Parameter[];
  safety_class: "low" | "medium" | "high" | "critical";
  safety_checks: SafetyCheck[];
  estimated_duration_hours: number;
  estimated_cost_usd: number;
  approval_status: "pending" | "approved" | "denied" | "auto_approved";
  approved_by?: string;
  created_at: string;
}

interface Material {
  name: string;
  cas_number?: string;
  quantity: string;
  hazard_class?: string;
}

interface SafetyCheck {
  check_type: string;
  description: string;
  passed: boolean;
  details: string;
}
```

### 5.5 Run Record (RR)

```typescript
interface RunRecord {
  rr_id: string;
  eip_id: string;
  run_id: string;
  status: "running" | "completed" | "failed" | "aborted";
  planned_parameters: Record<string, unknown>;
  actual_parameters: Record<string, unknown>;
  deviations: Deviation[];
  qc_alerts: QCAlert[];
  results: Record<string, unknown>;
  artifacts: string[];          // plots, datasets, logs
  started_at: string;
  completed_at?: string;
  operator: string;             // agent_id or user_id
}

interface QCAlert {
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  parameter: string;
  expected: string;
  actual: string;
  timestamp: string;
}
```

### 5.6 Compute Job Spec

```typescript
interface ComputeJobSpec {
  job_id: string;
  run_id: string;
  phase_id: string;
  workload_type: "simulation" | "training" | "indexing" | "scoring" | "benchmark";
  resource_requirements: {
    cpu_cores: number;
    gpu_type?: string;
    memory_gb: number;
    storage_gb: number;
    max_duration_hours: number;
  };
  execution_target: "local" | "cluster" | "damd";
  cost_estimate: {
    compute_usd: number;
    energy_kwh: number;
    latency_estimate_minutes: number;
  };
  input_artifacts: string[];
  status: "estimating" | "queued" | "dispatched" | "running" | "completed" | "failed";
  damd_node_id?: string;        // if dispatched to DAMD
  created_at: string;
}
```

### 5.7 Unified Cost Entry

```typescript
interface CostEntry {
  entry_id: string;
  project_id: string;
  run_id: string;
  phase_id?: string;
  agent_id?: string;
  source_system: "parallax" | "oas" | "oae" | "damd" | "darklab";
  cost_type: "llm_call" | "compute" | "api" | "storage" | "energy";
  model_name?: string;
  tokens_in?: number;
  tokens_out?: number;
  cost_usd: number;
  timestamp: string;
}
```

### 5.8 Approval Request

```typescript
interface ApprovalRequest {
  approval_id: string;
  project_id: string;
  run_id: string;
  phase_id: string;
  reason: string;
  risk_class: "low" | "medium" | "high" | "critical";
  details: Record<string, unknown>;
  status: "pending" | "approved" | "denied" | "expired";
  requested_by: string;         // agent_id
  decided_by?: string;          // user_id
  decided_at?: string;
  created_at: string;
}
```

### 5.9 DRVP Event (Extended)

```typescript
interface DRVPEvent {
  event_id: string;
  event_type: string;           // 32+ types (see section 6)
  source_system: string;
  project_id?: string;
  run_id?: string;
  phase_id?: string;
  agent_id?: string;
  payload: Record<string, unknown>;
  timestamp: string;
}
```

---

## 6. Event Model (DRVP Extended)

V3 extends the existing 22 DRVP event types with research and experiment events:

### Existing (from OAS)

| Category | Events |
|----------|--------|
| Request | `request.created`, `request.completed`, `request.failed` |
| Agent | `agent.thinking`, `agent.responding`, `agent.error`, `agent.idle` |
| Handoff | `handoff.initiated`, `handoff.completed` |
| LLM | `llm.call.started`, `llm.call.completed`, `llm.call.boosted` |
| Campaign | `campaign.started`, `campaign.step.started`, `campaign.step.completed`, `campaign.completed` |
| Budget | `budget.warning`, `budget.exhausted` |
| Governance | `campaign.approval.required`, `campaign.approval.granted` |
| Memory | `memory.loaded`, `memory.stored` |

### New for V3

| Category | Events |
|----------|--------|
| Phase | `phase.started`, `phase.completed`, `phase.failed`, `phase.restarted` |
| Research | `ideas.ready`, `score.received`, `feedback.loop`, `gap.detected` |
| Experiment | `eip.created`, `safety.checked`, `experiment.started`, `experiment.qc_alert`, `experiment.completed` |
| Compute | `job.estimated`, `job.dispatched`, `job.progress`, `job.completed` |
| Artifact | `artifact.created`, `artifact.versioned` |
| Approval | `approval.required`, `approval.granted`, `approval.denied` |
| Pipeline | `pipeline.completed`, `pipeline.failed`, `pipeline.branched` |

All events flow through Redis Pub/Sub → V3 Gateway SSE → Frontend stores.

---

## 7. Agent Taxonomy

### 7.1 Research Agents

| Agent | Skills | Cost Class | Escalation |
|-------|--------|------------|------------|
| Literature Scout | `research`, `literature`, `browser_agent` | standard | none |
| Topic Mapper | `research`, `synthesize` | standard | none |
| Gap Analyst | `research`, `deepresearch` | premium | none |
| Novelty Judge | `debate`, `deepresearch` | premium | flag low-confidence |
| Citation Verifier | `literature`, `browser_agent` | cheap | none |

### 7.2 Debate Agents

| Agent | Skills | Cost Class | Escalation |
|-------|--------|------------|------------|
| Critical Reviewer | `debate` | standard | none |
| Method Reviewer | `debate`, `doe` | standard | none |
| Feasibility Reviewer | `debate`, `simulate` | standard | none |
| Statistical Reviewer | `debate`, `analyze` | premium | flag weak stats |
| Domain Reviewer | `debate` (per-domain prompt) | premium | none |
| Devil's Advocate | `debate` | standard | none |
| Synthesizer | `synthesize`, `debate` | premium | none |

### 7.3 Author Agents

| Agent | Skills | Cost Class | Escalation |
|-------|--------|------------|------------|
| Structure Author | `paper` | standard | none |
| Technical Writer | `paper`, `literature` | standard | none |
| Figure Planner | `paper`, `analyze` | standard | none |
| Revision Author | `paper`, `debate` | premium | none |
| Rebuttal Author | `paper`, `debate` | premium | none |

### 7.4 Experiment Agents

| Agent | Skills | Cost Class | Escalation |
|-------|--------|------------|------------|
| Protocol Builder | `doe`, `simulate` | standard | none |
| Safety Checker | `doe` | cheap | **always escalate high/critical** |
| Script Generator | `simulate`, `synthetic` | standard | none |
| Sandbox Executor | `simulate` | standard | escalate on failure |
| Result Plotter | `analyze`, `report-data` | cheap | none |
| Run Analyst | `analyze`, `report` | premium | none |

### 7.5 Compute / DAMD Agents

| Agent | Skills | Cost Class | Escalation |
|-------|--------|------------|------------|
| Resource Estimator | (DAMD internal) | cheap | none |
| Dispatch Planner | (DAMD internal) | cheap | escalate high-cost jobs |
| Cost Optimizer | (DAMD internal) | cheap | none |
| Site Intelligence Analyst | (DAMD mapping) | standard | none |
| Simulation Coordinator | `simulate`, `analyze` | premium | none |

### 7.6 Agent Configuration Schema

```typescript
interface AgentDefinition {
  agent_id: string;
  name: string;
  role: "research" | "debate" | "author" | "experiment" | "compute";
  skills: string[];
  cost_class: "cheap" | "standard" | "premium";
  preferred_model: string;
  max_budget_per_task_usd: number;
  escalation_policy: "none" | "flag_low_confidence" | "always_escalate" | "escalate_on_failure";
  output_schema: string;        // JSON schema reference
  system_prompt_template: string;
}
```

---

## 8. Workflow Engine Design

### 8.1 Protocol Templates

V3 ships with protocol templates that define the default DAG for each mode:

#### Academic Research Protocol

```
Search → Map ──┬── Debate → Validate ←── (feedback)
               │                │                │
               └── Ideate → Draft → Experiment Plan → Revise → Pass
                                    (conditional)
```
*Same as V2 but with stronger agent assignment and budget constraints.*

#### Experiment Protocol

```
[Import Research] → Experiment Plan → Safety Check → [Approval Gate]
                                                          │
                    ┌─────────────────────────────────────┘
                    ▼
              Experiment Execute → Experiment Analyze → Experiment Compare
                    │                                        │
                    └──────── (loop if QC fails) ────────────┘
                                                        │
                                                   Report → Pass
```

#### Simulation Protocol

```
[Import Research] → Simulate Design → Compute Estimate → [Approval Gate]
                                                               │
                         ┌─────────────────────────────────────┘
                         ▼
                   Compute Dispatch → Compute Monitor → Compute Collect
                         │                                      │
                         └──── (retry on failure) ──────────────┘
                                                           │
                                                   Simulate Analyze → Report → Pass
```

#### Full Research-to-Experiment Protocol

```
Search → Map → Debate → Validate → Ideate → Draft
                                                │
                                    ┌───────────┤
                                    ▼           ▼
                              Experiment    Simulate Design
                              Plan          → Compute Estimate
                              → Safety      → [Approval]
                              → [Approval]  → Dispatch
                              → Execute     → Monitor
                              → Analyze     → Collect
                                    │           │
                                    └─────┬─────┘
                                          ▼
                                    Synthesize → Revise → Pass
```

### 8.2 Phase Contract

Every phase must define:

```typescript
interface PhaseContract {
  phase_type: PhaseType;
  input_schema: JSONSchema;     // What data this phase needs
  output_schema: JSONSchema;    // What data this phase produces
  artifact_types: string[];     // What artifact types it creates
  validation_rules: ValidationRule[];
  suggested_agents: string[];   // Agent roles that can execute this
  eligible_models: string[];    // Models that can be used
  budget_estimate_usd: number;  // Expected cost range
  requires_approval: boolean;   // Whether approval gate applies
  next_transitions: {           // Valid next phases
    phase_type: PhaseType;
    edge_type: EdgeType;
    condition?: string;
  }[];
}
```

### 8.3 Execution Flow

```
1. User creates Project (selects template + domain)
2. V3 Gateway creates WorkflowRun + Phase DAG
3. Gateway calls get_next_executable() — finds ready phases
4. For each ready phase:
   a. Check budget (Paperclip middleware)
   b. Check approval (if required)
   c. Resolve agent + model
   d. Emit phase.started event (DRVP)
   e. Dispatch to execution backend:
      - Research phases → Parallax V2 SDK
      - Swarm phases → OAS Campaign Engine
      - Experiment phases → DarkLab via OpenClaw
      - Compute phases → DAMD Coordinator
   f. Collect outputs + artifacts
   g. Record cost entry
   h. Emit phase.completed event
   i. Auto-advance if configured
5. Handle feedback loops (same as V2)
6. Handle approval gates (pause + emit approval.required)
7. On pipeline completion → emit pipeline.completed
```

---

## 9. DAMD Integration Design

### 9.1 Compute Dispatch Flow

```
V3 Phase (compute_estimate)
    │
    ├── Gather workload requirements from phase config
    ├── Query DAMD Coordinator: POST /api/v1/estimate
    │   Response: { cost_usd, latency_min, energy_kwh, node_offers[] }
    ├── Present estimates to user / auto-approve if within budget
    │
    ▼
V3 Phase (compute_dispatch)
    │
    ├── Select node (cheapest / fastest / greenest / local)
    ├── Submit job: POST /api/v1/jobs
    ├── Emit job.dispatched event
    │
    ▼
V3 Phase (compute_monitor)
    │
    ├── Poll DAMD: GET /api/v1/jobs/{id}/status
    ├── Emit job.progress events
    ├── Handle timeout / failure → retry or escalate
    │
    ▼
V3 Phase (compute_collect)
    │
    ├── Fetch results: GET /api/v1/jobs/{id}/results
    ├── Store as Artifacts
    ├── Record cost entry
    └── Emit job.completed event
```

### 9.2 Workload Types

| Workload | Example | Typical Target |
|----------|---------|---------------|
| Large literature indexing | 10K+ papers across 14 adapters | DAMD (parallel) |
| Debate swarm simulation | 6+ agents, 10+ rounds | DarkLab cluster |
| Financial scenario ensemble | 1000 Monte Carlo runs | DAMD |
| Geospatial site scoring | 50+ cities, 7-dimension analysis | DAMD |
| Model benchmarking | Multiple models on same task | DAMD |
| Mirofish-like simulation | Multi-agent social/market sim | DarkLab cluster |
| ML experiment | Train + evaluate model | Local sandbox or DAMD |

---

## 10. DarkLab Experiment Integration Design

### 10.1 Research → Experiment Loop

```
Draft (validated) → Experiment Plan Agent
    │
    ├── Extract claims needing evidence
    ├── Generate EIP with:
    │   ├── hypothesis
    │   ├── method (CV, EIS, Raman, etc.)
    │   ├── materials + quantities
    │   ├── device requirements
    │   ├── parameter ranges
    │   ├── expected outcomes
    │   └── safety classification
    │
    ▼
Safety Checker Agent
    │
    ├── Check hazard classes
    ├── Validate device compatibility
    ├── Check for dangerous combinations
    ├── Classify risk: low / medium / high / critical
    │
    ▼
[Approval Gate] — if high/critical, require human sign-off
    │
    ▼
Experiment Execute (via DarkLab experiment node)
    │
    ├── OpenClaw dispatch to experiment Mac
    ├── Generate execution script
    ├── Run in sandbox (timeout, memory cap, no network)
    ├── Collect stdout, stderr, artifacts
    ├── Monitor QC thresholds
    │   └── If QC alert → emit experiment.qc_alert → pause or continue
    │
    ▼
Run Analyst Agent
    │
    ├── Compare planned vs actual parameters
    ├── Generate plots (loss curves, spectra, CV plots)
    ├── Produce Run Record (RR)
    ├── Score experiment success
    │
    ▼
Feed back into Revise phase → Draft improvement → Next experiment
```

### 10.2 Governance Planes (from DarkLab architecture)

| Plane | Responsibility | V3 Implementation |
|-------|---------------|-------------------|
| Governance | Approvals, budgets, policies | Paperclip + V3 approval gates |
| Knowledge | Memory, context, literature | OpenViking + Parallax V2 paper store |
| Control | Workflow orchestration, dispatch | V3 Gateway + DAG engines |
| Data | Artifacts, results, audit logs | PostgreSQL + file store + Redis |

---

## 11. Governance and Safety Model

### 11.1 Policy Classes

| Class | Behavior | Example |
|-------|----------|---------|
| `auto_approve` | No human needed | Literature search, topic mapping, cheap LLM calls |
| `gate_risky` | Approve if cost > threshold OR safety_class >= high | Experiment execution, DAMD dispatch > $10 |
| `gate_all` | Always require approval | Novel chemistry, external publication, multi-hour runs |

### 11.2 Budget Enforcement

```
Per-project budget cap (set at creation)
    ├── Per-run allocation (automatic split or manual)
    ├── Per-agent daily limit (from Paperclip)
    └── Per-model cost tracking (from CostTracker)

Budget check flow:
    Phase starts → Middleware checks:
    1. Project budget remaining?
    2. Run budget remaining?
    3. Agent daily limit remaining?
    4. Model cost within step estimate?
    → If any fail: emit budget.warning or budget.exhausted → pause
```

### 11.3 Audit Trail

Every state change produces an audit entry:

```typescript
interface AuditEntry {
  entry_id: string;
  timestamp: string;
  actor: string;                // user_id or agent_id
  action: string;               // "phase.started", "approval.granted", etc.
  resource_type: string;        // "phase", "eip", "job", "artifact"
  resource_id: string;
  details: Record<string, unknown>;
  signature?: string;           // Ed25519 signature (for DarkLab actions)
}
```

---

## 12. UI/UX Design

### 12.1 Layout Architecture

```
┌──────────────────────────────────────────────────────────────┐
│ [Logo] Parallax V3   [Search]   [Cost: $4.28]   [User]     │
├───────┬──────────────────────────────────┬───────────────────┤
│       │                                  │                   │
│  P    │     CENTER WORKSPACE             │   INSPECTOR       │
│  R    │                                  │                   │
│  O    │  ┌─────────────────────────┐     │  ┌─────────────┐ │
│  J    │  │  Phase Content          │     │  │ Settings    │ │
│  E    │  │  (Graph / Editor /      │     │  │ Evidence    │ │
│  C    │  │   Map / Debate /        │     │  │ Agents      │ │
│  T    │  │   Experiment /          │     │  │ Costs       │ │
│       │  │   Simulation)           │     │  │ Artifacts   │ │
│  S    │  │                         │     │  │ Metadata    │ │
│  I    │  └─────────────────────────┘     │  └─────────────┘ │
│  D    │                                  │                   │
│  E    │                                  │                   │
│  B    │                                  │                   │
│  A    │                                  │                   │
│  R    │                                  │                   │
│       │                                  │                   │
├───────┴──────────────────────────────────┴───────────────────┤
│  EVENT TIMELINE / DRVP CONSOLE                               │
│  [▶ phase.started search] [▶ llm.call] [▶ phase.completed]  │
│  [Budget: $4.28 / $50.00] [Agents: 3 active] [Events: 47]  │
└──────────────────────────────────────────────────────────────┘
```

### 12.2 Module → View Mapping

| Module | Center Workspace Content |
|--------|------------------------|
| Command Center | Project cards, template picker, activity feed |
| Literature + Map | Paper browser, D3 topic graph, evidence clusters |
| Debate | Agent debate transcript, contradiction matrix, score chart |
| Draft / Paper Lab | Section editor, citations panel, weakness tracker |
| Experiment | EIP form, safety checklist, run monitor, result plots |
| Simulation / DAMD | Job builder, cost estimator, node map, progress tracker |
| DarkLab Explorer | Event timeline, experiment tree, artifact lineage, plot gallery |
| Governance | Budget charts, approval queue, audit log, issue list |

### 12.3 Inspector Panel (Right Side)

The inspector is context-sensitive — it shows relevant metadata for whatever is selected in the center workspace:

| Context | Inspector Shows |
|---------|----------------|
| Phase selected | Config, model, cost, agent, artifacts, status history |
| Paper selected | Title, abstract, figures, relevance, citations |
| Debate round | Agent stances, confidence, key arguments |
| EIP selected | Materials, devices, safety checks, approval status |
| Job selected | Resource requirements, cost estimate, node info, progress |
| Artifact selected | Type, lineage, producing agent, version history |

### 12.4 Event Timeline (Bottom Panel)

Horizontal scrolling timeline showing DRVP events in real time:

```
─────┤search.started├──┤llm.call├──┤llm.call├──┤search.completed├──┤map.started├──→
     10:30:01          10:30:03    10:30:08    10:30:42            10:30:43
     Agent: Scout       Sonnet      Sonnet      Agent: Scout        Agent: Mapper
     $0.02              $0.01       $0.01       papers: 47          $0.00
```

---

## 13. Phased Implementation Plan

### Phase 1: V3 Gateway + Unified Events (4 weeks)

**Goal:** Stand up the V3 Gateway service that proxies V2 and adds the unified event/cost/governance layer.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| 1 | FastAPI project scaffold, Project CRUD, PostgreSQL schema (projects, runs, cost_entries, audit_entries, approvals) | Gateway boots, creates projects |
| 2 | Phase DAG engine (reuse V2 logic, add new phase types + edge types), protocol templates | Templates create DAGs, phases execute in order |
| 3 | DRVP event aggregation (Redis → SSE), unified cost recording, Paperclip budget middleware integration | Events flow to frontend, costs are real |
| 4 | Wire V2 SDK as execution backend for research phases, frontend routes V3 Gateway for projects | Research pipeline runs through V3 Gateway |

**Success criteria:**
- Create project → select academic template → pipeline runs via V2 → costs visible → events stream to frontend

### Phase 2: Experiment + DarkLab Integration (4 weeks)

**Goal:** EIP generation, safety checks, sandbox execution, run records.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| 5 | EIP schema, Protocol Builder agent, Safety Checker agent | EIP generated from validated draft |
| 6 | Approval gate phases, approval UI in frontend | Human can approve/deny experiment |
| 7 | Sandbox executor (subprocess with limits), OpenClaw dispatch to experiment node | Experiment runs in sandbox |
| 8 | Run Record generation, result plotting, QC alerts, experiment → revise feedback loop | Full experiment cycle works |

**Success criteria:**
- Draft → EIP → safety check → approval → execute → analyze → feed back into revision

### Phase 3: DAMD + Simulation Integration (3 weeks)

**Goal:** Compute estimation, dispatch, monitoring for heavy workloads.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| 9 | Compute estimate phase (calls DAMD Coordinator), cost/latency UI | User sees job cost before dispatch |
| 10 | Compute dispatch + monitor phases, DAMD WebSocket progress | Jobs run on DAMD nodes |
| 11 | Simulation design + analyze phases, result artifact collection | Full simulation workflow |

**Success criteria:**
- Design simulation → estimate cost → approve → dispatch to DAMD → collect results

### Phase 4: Production Backbone (4 weeks)

**Goal:** Auth, CI/CD, monitoring, PostgreSQL as primary.

| Week | Tasks | Deliverable |
|------|-------|-------------|
| 12 | JWT auth (V3 Gateway), API keys for SDK, RBAC for projects | Authenticated access |
| 13 | Docker (gateway + frontend + PostgreSQL + Redis), GitHub Actions CI | `docker compose up` works |
| 14 | Prometheus metrics, Grafana dashboard, structured logging | Production monitoring |
| 15 | Multi-user project sharing, role-based access, budget per user | Teams can collaborate |

### Phase 5: Polish + Platform Integration (ongoing)

- Template marketplace UI
- Zotero/arXiv export
- 3D debate visualization
- Mobile-responsive oversight
- Batch SDK execution
- Webhook notifications
- Data retention policies

---

## 14. Recommended MVP Cut (First 4 Weeks)

The MVP is Phase 1 — the V3 Gateway that wraps V2:

**Build:**
1. FastAPI V3 Gateway service (`v3_gateway/`)
2. PostgreSQL schema for projects, cost_entries, audit_entries, approvals
3. Protocol template system with academic research template
4. DRVP event aggregation (Redis → SSE)
5. Unified cost recording (every LLM call → cost_entries table)
6. Paperclip budget middleware integration
7. V2 SDK as execution backend for research phases
8. Frontend: project creation with template picker, event timeline, cost display

**Skip (defer to later phases):**
- Experiment execution (Phase 2)
- DAMD dispatch (Phase 3)
- Authentication (Phase 4)
- Multi-user (Phase 4)
- 3D visualization (Phase 5)

**Why this MVP works:**
- It immediately fixes the $0.00 cost display (biggest V2 complaint)
- It adds real event streaming (DRVP) — users see what agents are doing
- It introduces project-level governance (budgets, approvals)
- It doesn't break V2 — the gateway proxies to V2, doesn't replace it
- Everything after builds on this foundation

---

## 15. 4-Week Execution Plan

### Week 1: Gateway Foundation

**Day 1-2:** Scaffold FastAPI project
```
v3_gateway/
  __init__.py
  main.py              # FastAPI app factory
  config.py            # Settings from env
  db.py                # PostgreSQL (asyncpg / SQLAlchemy async)
  models/
    project.py         # Project, WorkflowRun
    phase.py           # Phase, Edge
    cost.py            # CostEntry
    audit.py           # AuditEntry
    approval.py        # ApprovalRequest
  api/
    projects.py        # Project CRUD
    runs.py            # WorkflowRun lifecycle
    phases.py          # Phase status, artifacts
    events.py          # SSE endpoint
    costs.py           # Cost queries
  services/
    workflow_engine.py  # Phase DAG engine
    event_bus.py       # Redis DRVP consumer/publisher
    cost_recorder.py   # Unified cost recording
  middleware/
    budget.py          # Budget check middleware
    audit.py           # Audit logging middleware
```

**Day 3-4:** PostgreSQL schema + Alembic migrations
- `projects` table
- `workflow_runs` table
- `phases` table (DAG nodes)
- `phase_edges` table (DAG edges)
- `cost_entries` table
- `audit_entries` table
- `approval_requests` table

**Day 5:** Project CRUD API + tests

### Week 2: Workflow Engine + Templates

**Day 1-2:** Port V2 DAG logic to V3 engine
- `create_workflow_from_template()`
- `get_next_executable()`
- `restart_from_phase()`
- `handle_feedback_loop()`

**Day 3:** Protocol templates
- Academic research template (9 phases, 12 edges)
- Experiment template (7 phases)
- Simulation template (6 phases)
- Full research-to-experiment template (15+ phases)

**Day 4-5:** Phase execution dispatch
- Route research phases to V2 SDK
- Phase lifecycle: pending → running → completed/failed
- Auto-advance logic

### Week 3: Events + Cost

**Day 1-2:** DRVP event bus
- Redis consumer that listens to all DRVP channels
- Event aggregation into PostgreSQL `unified_events` view
- SSE endpoint streaming events to frontend

**Day 3:** Unified cost recording
- Instrument V2 SDK callbacks to record costs
- Cost query API: per-project, per-run, per-phase, per-agent

**Day 4-5:** Paperclip budget integration
- Middleware checks budget before phase execution
- Budget warning/exhaustion events
- Budget display in frontend header

### Week 4: Frontend Integration

**Day 1-2:** Wire frontend to V3 Gateway
- New API client for V3 endpoints
- Project creation with template selection
- Route project detail through V3 status API

**Day 3:** Event timeline component
- Bottom panel showing DRVP events in real time
- Color-coded by category (research, agent, llm, budget)
- Cost ticker in header

**Day 4:** Cost dashboard
- Per-project cost breakdown
- Per-phase cost attribution
- Budget progress bar

**Day 5:** Integration testing + documentation

---

## 16. Prioritized Backlog (Epics)

| Priority | Epic | Size | Phase |
|----------|------|------|-------|
| P0 | V3 Gateway scaffold + PostgreSQL schema | M | 1 |
| P0 | Workflow engine with template system | M | 1 |
| P0 | DRVP event aggregation + SSE | M | 1 |
| P0 | Unified cost recording + budget middleware | M | 1 |
| P0 | V2 SDK as execution backend | S | 1 |
| P0 | EIP schema + Protocol Builder agent | M | 2 |
| P0 | Safety Checker + Approval gates | M | 2 |
| P0 | Sandbox experiment executor | L | 2 |
| P1 | Run Record + result plotting | M | 2 |
| P1 | DAMD compute estimation | M | 3 |
| P1 | DAMD job dispatch + monitoring | L | 3 |
| P1 | JWT auth + RBAC | L | 4 |
| P1 | Docker + CI/CD | M | 4 |
| P1 | Prometheus + Grafana monitoring | M | 4 |
| P1 | Multi-user project sharing | L | 4 |
| P2 | Template marketplace UI | M | 5 |
| P2 | Zotero / arXiv export | M | 5 |
| P2 | 3D debate visualization | L | 5 |
| P2 | Mobile-responsive UI | M | 5 |
| P2 | Webhook notifications | M | 5 |

---

## 17. Key Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| V3 Gateway adds latency to V2 pipeline | Medium | Medium | Keep V2 as direct backend for hot-path; V3 wraps for governance only |
| PostgreSQL + SQLite dual-DB complexity | High | High | Clear ownership: V3 owns PostgreSQL, V2 owns SQLite. Gateway translates. |
| DRVP event flood overwhelms frontend | Medium | Medium | Client-side throttling, event batching, level-of-detail filtering |
| Experiment sandbox escape | Critical | Low | No network in sandbox, memory cap, timeout, chroot where possible |
| Budget tracking drift between Paperclip + V3 | Medium | Medium | V3 cost_entries is source of truth; Paperclip is notified, not queried |
| Agent swarm contention on shared DB | High | Medium | Run-scoped isolation (V2 pattern), per-thread connections, WAL mode |
| Scope creep — building all 5 phases at once | Critical | High | Strict MVP cut (Phase 1 only first 4 weeks). Ship gateway before experiments. |

---

## 18. Revision Log

| Date | Change |
|------|--------|
| 2026-03-28 | Initial V3 architecture spec from ecosystem audit |
