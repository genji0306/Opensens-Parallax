/**
 * Debate Store — Zustand + Immer
 *
 * Manages the state for OSSR debate visualization mode.
 * Separate from office-store to keep concerns isolated.
 */

import { enableMapSet } from "immer";
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { OssrDebateAdapter } from "@/gateway/ossr-debate-adapter";
import type {
  DiscussionFormat,
  DiscussionTurn,
  FormatInfo,
  ResearcherAgent,
  SimulationSummary,
} from "@/gateway/ossr-debate-types";
import type { AgentVisualStatus } from "@/gateway/types";

enableMapSet();

// ── Types ─────────────────────────────────────────────────────────────

export interface DebateVisualAgent {
  id: string;
  name: string;
  role: string;
  affiliation: string;
  primaryField: string;
  specializations: string[];
  status: AgentVisualStatus;
  seatIndex: number;
  llmProvider: string;
  llmModel: string;
}

export type DebateStatus = "idle" | "setup" | "connecting" | "running" | "paused" | "completed" | "failed";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  agentId?: string;
  timestamp: string;
}

interface DebateState {
  // Connection
  ossrUrl: string;
  adapterConnected: boolean;

  // Debate metadata
  debateId: string | null;
  simulationId: string | null;
  status: DebateStatus;
  format: DiscussionFormat;
  topic: string;

  // Agents
  debateAgents: Map<string, DebateVisualAgent>;
  activeAgentId: string | null;

  // Transcript
  transcript: DiscussionTurn[];
  currentRound: number;
  maxRounds: number;

  // Formats catalog
  formats: FormatInfo[];

  // Speed control
  speedMultiplier: number;

  // Chat
  chatAgentId: string | null;
  chatMessages: ChatMessage[];
  chatOpen: boolean;

  // SSE unsubscribe function
  _unsubscribeStream: (() => void) | null;
}

interface DebateActions {
  // Connection
  setOssrUrl(url: string): void;
  connectToOssr(): Promise<void>;

  // Setup
  loadFormats(): Promise<void>;
  loadAgents(topicId?: string): Promise<ResearcherAgent[]>;
  setFormat(format: DiscussionFormat): void;
  setTopic(topic: string): void;

  // Lifecycle
  createAndStartDebate(
    format: DiscussionFormat,
    topic: string,
    agentIds: string[],
    maxRounds?: number,
  ): Promise<void>;
  stopListening(): void;

  // Live interaction
  injectTopic(topic: string, fromUser?: string): Promise<void>;
  pauseDebate(): Promise<void>;
  resumeDebate(): Promise<void>;
  setSpeed(multiplier: number): Promise<void>;

  // Transcript events
  appendTurn(turn: DiscussionTurn): void;
  setActiveAgent(agentId: string | null): void;
  markCompleted(): void;
  markPaused(): void;
  markResumed(): void;

  // Fork
  forkAndStartDebate(
    fromRound: number,
    modifications?: Record<string, unknown>,
  ): Promise<void>;

  // Chat
  openChat(agentId: string): void;
  closeChat(): void;
  sendChatMessage(message: string): Promise<void>;

  // Reset
  reset(): void;
}

type DebateStore = DebateState & DebateActions;

// ── Singleton adapter ─────────────────────────────────────────────────

let _adapter: OssrDebateAdapter | null = null;

function getAdapter(url?: string): OssrDebateAdapter {
  if (!_adapter) _adapter = new OssrDebateAdapter(url);
  return _adapter;
}

// ── Store ─────────────────────────────────────────────────────────────

const INITIAL_STATE: DebateState = {
  ossrUrl: "http://localhost:5002",
  adapterConnected: false,
  debateId: null,
  simulationId: null,
  status: "idle",
  format: "conference",
  topic: "",
  debateAgents: new Map(),
  activeAgentId: null,
  transcript: [],
  currentRound: 0,
  maxRounds: 5,
  formats: [],
  speedMultiplier: 1.0,
  chatAgentId: null,
  chatMessages: [],
  chatOpen: false,
  _unsubscribeStream: null,
};

export const useDebateStore = create<DebateStore>()(
  immer((set, get) => ({
    ...INITIAL_STATE,

    // ── Connection ──────────────────────────────────────────────────

    setOssrUrl(url: string) {
      set({ ossrUrl: url });
    },

    async connectToOssr() {
      const { ossrUrl } = get();
      const adapter = getAdapter(ossrUrl);
      try {
        await adapter.connect(ossrUrl);
        set({ adapterConnected: true });
      } catch {
        set({ adapterConnected: false });
        throw new Error("Cannot reach OSSR backend");
      }
    },

    // ── Setup ───────────────────────────────────────────────────────

    async loadFormats() {
      const adapter = getAdapter();
      const formats = await adapter.listFormats();
      set({ formats });
    },

    async loadAgents(topicId?: string) {
      const adapter = getAdapter();
      return adapter.listAgents(topicId);
    },

    setFormat(format: DiscussionFormat) {
      set({ format });
    },

    setTopic(topic: string) {
      set({ topic });
    },

    // ── Lifecycle ───────────────────────────────────────────────────

    async createAndStartDebate(format, topic, agentIds, maxRounds) {
      const adapter = getAdapter();
      set({ status: "connecting" });

      try {
        // Create simulation
        const sim = await adapter.createSimulation({
          format,
          topic,
          agent_ids: agentIds,
          max_rounds: maxRounds,
        });

        // Load agent profiles for visualization
        const agents = await adapter.getSimAgents(sim.simulation_id);
        const agentMap = new Map<string, DebateVisualAgent>();
        agents.forEach((a, index) => {
          agentMap.set(a.agent_id, {
            id: a.agent_id,
            name: a.name,
            role: a.role,
            affiliation: a.affiliation,
            primaryField: a.primary_field,
            specializations: a.specializations,
            status: "idle",
            seatIndex: index,
            llmProvider: a.llm_provider,
            llmModel: a.llm_model,
          });
        });

        set({
          simulationId: sim.simulation_id,
          format,
          topic,
          maxRounds: sim.max_rounds,
          debateAgents: agentMap,
          transcript: [],
          currentRound: 0,
          status: "running",
        });

        // Start simulation
        await adapter.startSimulation(sim.simulation_id);

        // Subscribe to SSE stream
        const unsubscribe = adapter.subscribeToStream(
          sim.simulation_id,
          (turn) => get().appendTurn(turn),
          () => get().markCompleted(),
          undefined,
          () => get().markPaused(),
          () => get().markResumed(),
        );

        set({ _unsubscribeStream: unsubscribe });
      } catch (err) {
        set({ status: "failed" });
        throw err;
      }
    },

    stopListening() {
      const { _unsubscribeStream } = get();
      _unsubscribeStream?.();
      set({ _unsubscribeStream: null });
    },

    // ── Live Interaction ────────────────────────────────────────────

    async injectTopic(topic, fromUser) {
      const { simulationId } = get();
      if (!simulationId) return;
      const adapter = getAdapter();
      await adapter.injectTopic(simulationId, topic, fromUser);
    },

    async pauseDebate() {
      const { simulationId } = get();
      if (!simulationId) return;
      const adapter = getAdapter();
      await adapter.pauseSimulation(simulationId);
    },

    async resumeDebate() {
      const { simulationId } = get();
      if (!simulationId) return;
      const adapter = getAdapter();
      await adapter.resumeSimulation(simulationId);
    },

    async setSpeed(multiplier: number) {
      const { simulationId } = get();
      if (!simulationId) return;
      const adapter = getAdapter();
      await adapter.setSpeed(simulationId, multiplier);
      set({ speedMultiplier: multiplier });
    },

    // ── Transcript ──────────────────────────────────────────────────

    appendTurn(turn: DiscussionTurn) {
      set((state) => {
        state.transcript.push(turn);
        state.currentRound = turn.round_num;
        state.activeAgentId = turn.agent_id;

        // Update agent visual status
        const agent = state.debateAgents.get(turn.agent_id);
        if (agent) agent.status = "speaking";

        // Reset previous speaker to idle
        for (const [id, a] of state.debateAgents) {
          if (id !== turn.agent_id && a.status === "speaking") {
            a.status = "idle";
          }
        }
      });
    },

    setActiveAgent(agentId: string | null) {
      set({ activeAgentId: agentId });
    },

    markCompleted() {
      set((state) => {
        state.status = "completed";
        state.activeAgentId = null;
        state._unsubscribeStream = null;
        for (const a of state.debateAgents.values()) {
          a.status = "idle";
        }
      });
    },

    markPaused() {
      set((state) => {
        state.status = "paused";
        for (const a of state.debateAgents.values()) {
          if (a.status === "speaking") a.status = "idle";
        }
      });
    },

    markResumed() {
      set({ status: "running" });
    },

    // ── Fork ─────────────────────────────────────────────────────────

    async forkAndStartDebate(fromRound, modifications) {
      const { simulationId, _unsubscribeStream } = get();
      if (!simulationId) return;
      const adapter = getAdapter();

      // Stop current stream
      _unsubscribeStream?.();
      set({ status: "connecting", _unsubscribeStream: null });

      try {
        const forked = await adapter.forkSimulation(
          simulationId,
          fromRound,
          modifications,
        );

        // Load agent profiles for forked simulation
        const agents = await adapter.getSimAgents(forked.simulation_id);
        const agentMap = new Map<string, DebateVisualAgent>();
        agents.forEach((a, index) => {
          agentMap.set(a.agent_id, {
            id: a.agent_id,
            name: a.name,
            role: a.role,
            affiliation: a.affiliation,
            primaryField: a.primary_field,
            specializations: a.specializations,
            status: "idle",
            seatIndex: index,
            llmProvider: a.llm_provider,
            llmModel: a.llm_model,
          });
        });

        // Load existing transcript from fork
        const existingTranscript = await adapter.getTranscript(
          forked.simulation_id,
        );

        set({
          simulationId: forked.simulation_id,
          format: forked.discussion_format as DiscussionFormat,
          topic: forked.topic,
          maxRounds: forked.max_rounds,
          debateAgents: agentMap,
          transcript: existingTranscript,
          currentRound: fromRound,
          activeAgentId: null,
          status: "running",
          speedMultiplier: 1.0,
        });

        // Start forked simulation
        await adapter.startSimulation(forked.simulation_id);

        // Subscribe to SSE with lastTurnId to avoid duplicates
        const lastId =
          existingTranscript.length > 0
            ? existingTranscript[existingTranscript.length - 1].turn_id
            : undefined;

        const unsubscribe = adapter.subscribeToStream(
          forked.simulation_id,
          (turn) => get().appendTurn(turn),
          () => get().markCompleted(),
          lastId,
          () => get().markPaused(),
          () => get().markResumed(),
        );

        set({ _unsubscribeStream: unsubscribe });
      } catch (err) {
        set({ status: "failed" });
        throw err;
      }
    },

    // ── Chat ────────────────────────────────────────────────────────

    openChat(agentId: string) {
      set({ chatAgentId: agentId, chatOpen: true, chatMessages: [] });
    },

    closeChat() {
      set({ chatOpen: false, chatAgentId: null, chatMessages: [] });
    },

    async sendChatMessage(message: string) {
      const { simulationId, chatAgentId } = get();
      if (!simulationId || !chatAgentId) return;

      const userMsg: ChatMessage = {
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
      };

      set((state) => {
        state.chatMessages.push(userMsg);
      });

      try {
        const adapter = getAdapter();
        const response = await adapter.chatWithAgent(
          simulationId,
          chatAgentId,
          message,
        );

        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: response,
          agentId: chatAgentId,
          timestamp: new Date().toISOString(),
        };

        set((state) => {
          state.chatMessages.push(assistantMsg);
        });
      } catch {
        const errMsg: ChatMessage = {
          role: "assistant",
          content: "[Error: could not reach the agent]",
          timestamp: new Date().toISOString(),
        };
        set((state) => {
          state.chatMessages.push(errMsg);
        });
      }
    },

    // ── Reset ───────────────────────────────────────────────────────

    reset() {
      const { _unsubscribeStream } = get();
      _unsubscribeStream?.();
      set({ ...INITIAL_STATE, adapterConnected: get().adapterConnected, ossrUrl: get().ossrUrl, formats: get().formats });
    },
  })),
);
