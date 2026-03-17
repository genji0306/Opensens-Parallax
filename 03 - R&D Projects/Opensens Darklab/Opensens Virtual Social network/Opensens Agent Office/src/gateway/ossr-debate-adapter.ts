/**
 * OSSR Debate Adapter
 *
 * Connects the Agent Office to the OSSR backend (Flask :5002) for debate
 * visualization. Uses REST for CRUD + SSE for real-time transcript streaming.
 *
 * This is separate from the GatewayAdapter (which connects to OpenClaw).
 */

import type {
  CreateSimulationParams,
  DiscussionTurn,
  FormatInfo,
  OssrApiResponse,
  ResearcherAgent,
  SimulationSummary,
} from "./ossr-debate-types";

const DEFAULT_OSSR_URL = "http://localhost:5002";

export class OssrDebateAdapter {
  private baseUrl: string;
  private connected = false;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl ?? DEFAULT_OSSR_URL).replace(/\/$/, "");
  }

  // ── Connection ────────────────────────────────────────────────────

  async connect(baseUrl?: string): Promise<void> {
    if (baseUrl) this.baseUrl = baseUrl.replace(/\/$/, "");
    const resp = await this.get<{ papers: number }>("/stats");
    if (!resp.success) throw new Error("OSSR backend not reachable");
    this.connected = true;
  }

  disconnect(): void {
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  // ── Formats & Agents ──────────────────────────────────────────────

  async listFormats(): Promise<FormatInfo[]> {
    const resp = await this.get<FormatInfo[]>("/simulate/formats");
    return resp.data ?? [];
  }

  async listAgents(topicId?: string): Promise<ResearcherAgent[]> {
    const params = topicId ? `?topic_id=${encodeURIComponent(topicId)}` : "";
    const resp = await this.get<ResearcherAgent[]>(`/agents${params}`);
    return resp.data ?? [];
  }

  async getSimAgents(simulationId: string): Promise<ResearcherAgent[]> {
    const resp = await this.get<ResearcherAgent[]>(
      `/simulate/${simulationId}/agents`,
    );
    return resp.data ?? [];
  }

  // ── Simulation Lifecycle ──────────────────────────────────────────

  async createSimulation(
    params: CreateSimulationParams,
  ): Promise<SimulationSummary> {
    const resp = await this.post<SimulationSummary>("/simulate", params);
    if (!resp.success || !resp.data) throw new Error(resp.error ?? "Create failed");
    return resp.data;
  }

  async startSimulation(simulationId: string): Promise<string> {
    const resp = await this.post<never>(`/simulate/${simulationId}/start`, {});
    if (!resp.success) throw new Error(resp.error ?? "Start failed");
    return resp.task_id ?? "";
  }

  async pauseSimulation(simulationId: string): Promise<void> {
    const resp = await this.post(`/simulate/${simulationId}/pause`, {});
    if (!resp.success) throw new Error(resp.error ?? "Pause failed");
  }

  async resumeSimulation(simulationId: string): Promise<void> {
    const resp = await this.post(`/simulate/${simulationId}/resume`, {});
    if (!resp.success) throw new Error(resp.error ?? "Resume failed");
  }

  async setSpeed(simulationId: string, multiplier: number): Promise<void> {
    const resp = await this.post(`/simulate/${simulationId}/speed`, {
      multiplier,
    });
    if (!resp.success) throw new Error(resp.error ?? "Speed change failed");
  }

  async getSimulationStatus(simulationId: string): Promise<SimulationSummary> {
    const resp = await this.get<SimulationSummary>(
      `/simulate/${simulationId}/status`,
    );
    if (!resp.success || !resp.data) throw new Error(resp.error ?? "Not found");
    return resp.data;
  }

  async getTranscript(
    simulationId: string,
    round?: number,
  ): Promise<DiscussionTurn[]> {
    const params = round !== undefined ? `?round=${round}` : "";
    const resp = await this.get<DiscussionTurn[]>(
      `/simulate/${simulationId}/transcript${params}`,
    );
    return resp.data ?? [];
  }

  async listSimulations(): Promise<SimulationSummary[]> {
    const resp = await this.get<SimulationSummary[]>("/simulate");
    return resp.data ?? [];
  }

  // ── Live Interaction ──────────────────────────────────────────────

  /**
   * Subscribe to live SSE stream for a simulation.
   * Returns an unsubscribe function.
   */
  subscribeToStream(
    simulationId: string,
    onTurn: (turn: DiscussionTurn) => void,
    onComplete?: () => void,
    lastTurnId?: number,
    onPaused?: () => void,
    onResumed?: () => void,
  ): () => void {
    const url = `${this.baseUrl}/api/research/simulate/${simulationId}/stream`;
    const es = new EventSource(url);

    // Set Last-Event-ID for reconnection (browser handles automatically on reconnect)
    if (lastTurnId !== undefined) {
      // EventSource doesn't support setting Last-Event-ID directly for initial connection.
      // The browser will send it automatically on reconnect though.
    }

    es.addEventListener("turn", (event: MessageEvent) => {
      try {
        const turn: DiscussionTurn = JSON.parse(event.data);
        if (!lastTurnId || turn.turn_id > lastTurnId) {
          onTurn(turn);
        }
      } catch {
        // Ignore parse errors
      }
    });

    es.addEventListener("completed", () => {
      onComplete?.();
      es.close();
    });

    es.addEventListener("failed", () => {
      onComplete?.();
      es.close();
    });

    es.addEventListener("paused", () => {
      onPaused?.();
    });

    es.addEventListener("resumed", () => {
      onResumed?.();
    });

    es.onerror = () => {
      // EventSource auto-reconnects. On permanent failure, close.
      if (es.readyState === EventSource.CLOSED) {
        onComplete?.();
      }
    };

    return () => es.close();
  }

  async injectTopic(
    simulationId: string,
    topic: string,
    fromUser?: string,
  ): Promise<void> {
    const resp = await this.post(`/simulate/${simulationId}/inject-topic`, {
      topic,
      from_user: fromUser ?? "",
    });
    if (!resp.success) throw new Error(resp.error ?? "Inject failed");
  }

  async chatWithAgent(
    simulationId: string,
    agentId: string,
    message: string,
  ): Promise<string> {
    const resp = await this.post<{ agent_id: string; response: string }>(
      `/simulate/${simulationId}/chat`,
      { agent_id: agentId, message },
    );
    if (!resp.success || !resp.data)
      throw new Error(resp.error ?? "Chat failed");
    return resp.data.response;
  }

  async forkSimulation(
    simulationId: string,
    fromRound: number,
    modifications?: Record<string, unknown>,
  ): Promise<SimulationSummary> {
    const resp = await this.post<SimulationSummary>(
      `/simulate/${simulationId}/fork`,
      { from_round: fromRound, modifications: modifications ?? {} },
    );
    if (!resp.success || !resp.data) throw new Error(resp.error ?? "Fork failed");
    return resp.data;
  }

  // ── Reports ───────────────────────────────────────────────────────

  async generateReport(
    simulationId: string,
    type: "evolution" | "comparative",
  ): Promise<string> {
    const resp = await this.post<never>(`/report/${simulationId}`, { type });
    return resp.task_id ?? "";
  }

  // ── HTTP Helpers ──────────────────────────────────────────────────

  private async get<T>(path: string): Promise<OssrApiResponse<T>> {
    const resp = await fetch(`${this.baseUrl}/api/research${path}`);
    return resp.json();
  }

  private async post<T>(
    path: string,
    body: unknown,
  ): Promise<OssrApiResponse<T>> {
    const resp = await fetch(`${this.baseUrl}/api/research${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return resp.json();
  }
}
