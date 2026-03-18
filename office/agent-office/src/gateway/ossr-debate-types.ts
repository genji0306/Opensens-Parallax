/**
 * Types for OSSR debate integration.
 * These mirror the backend SimulationState, DiscussionTurn, and ResearcherProfile structures.
 */

export type DiscussionFormat =
  | "conference"
  | "peer_review"
  | "workshop"
  | "adversarial"
  | "longitudinal";

export type SimulationStatus =
  | "created"
  | "running"
  | "paused"
  | "completed"
  | "failed";

export interface DiscussionTurn {
  turn_id: number;
  round_num: number;
  agent_id: string;
  agent_name: string;
  agent_role: string;
  content: string;
  turn_type: string;
  cited_dois: string[];
  llm_provider: string;
  llm_model: string;
  timestamp: string;
}

export interface SimulationSummary {
  simulation_id: string;
  discussion_format: DiscussionFormat;
  status: SimulationStatus;
  topic: string;
  agent_ids: string[];
  max_rounds: number;
  current_round: number;
  transcript_length: number;
  injected_papers: string[];
  injected_topics: Array<{ topic: string; from_user: string; injected_at: string }>;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
}

export interface FormatInfo {
  id: DiscussionFormat;
  name: string;
  description: string;
  default_rounds: number;
}

export interface ResearcherAgent {
  agent_id: string;
  name: string;
  role: string;
  affiliation: string;
  primary_field: string;
  specializations: string[];
  persona: string;
  expertise_area: string;
  llm_provider: string;
  llm_model: string;
  skills: string[];
  is_super_agent: boolean;
  topic_ids: string[];
  known_paper_dois: string[];
}

export interface CreateSimulationParams {
  format: DiscussionFormat;
  topic: string;
  agent_ids: string[];
  max_rounds?: number;
  orchestrated?: boolean;
}

export interface OssrApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  task_id?: string;
  total?: number;
}

// ── Mirofish Orchestrator Types ──────────────────────────────────────

export interface MirofishOption {
  option_id: string;
  label: string;
  description: string;
}

export interface DebateFrame {
  frame_id: string;
  topic: string;
  options: MirofishOption[];
  constraints: Record<string, unknown>;
  evaluation_criteria: string[];
}

export interface OptionScore {
  option_id: string;
  label: string;
  confidence: number;
  trend: "rising" | "falling" | "stable";
  supporters: string[];
}

export interface AgentInfluence {
  agent_id: string;
  name: string;
  score: number;
}

export interface MirofishDisagreement {
  claim_a: string;
  claim_b: string;
  agents_a: string[];
  agents_b: string[];
  severity: number;
  rounds_active: number;
}

export interface MirofishCoalition {
  agents: string[];
  shared_positions: string[];
  strength: number;
}

export interface MirofishScoreboard {
  simulation_id: string;
  round_num: number;
  options: OptionScore[];
  consensus_pct: number;
  consensus_trend: "converging" | "diverging" | "stable";
  agent_influence: AgentInfluence[];
  disagreements: MirofishDisagreement[];
  coalitions: MirofishCoalition[];
}

export interface AgentStance {
  agent_id: string;
  option_id: string;
  round_num: number;
  position: number; // -1 to +1
  confidence: number; // 0 to 1
  reasoning: string;
}

export interface AnalystFeedEntry {
  round_num: number;
  narrative: string;
  key_events: string[];
}

export interface GraphNode {
  node_id: string;
  label: string;
  node_type: string;
  confidence?: number;
  created_at_round?: number;
  weight?: number;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  weight?: number;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  links: GraphEdge[];
}
