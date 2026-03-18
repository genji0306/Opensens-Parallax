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
}

export interface OssrApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  task_id?: string;
  total?: number;
}
