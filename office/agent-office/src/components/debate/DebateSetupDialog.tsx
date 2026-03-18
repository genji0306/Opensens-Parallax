/**
 * DebateSetupDialog — Modal for creating a new debate
 *
 * Format selector, topic input, agent picker, max rounds slider.
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useDebateStore } from "@/store/debate-store";
import type { ResearcherAgent } from "@/gateway/ossr-debate-types";
import { BarChart3, MessageCircle, Play, Users, Zap } from "lucide-react";

export function DebateSetupDialog() {
  const { t } = useTranslation("debate");
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // URL params from OSSR frontend redirect
  const paramOssr = searchParams.get("ossr");
  const paramTopic = searchParams.get("topic");
  const paramFormat = searchParams.get("format");
  const paramAgents = searchParams.get("agents"); // comma-separated IDs
  const paramRounds = searchParams.get("rounds");

  const {
    formats,
    adapterConnected,
    ossrUrl,
    connectToOssr,
    loadFormats,
    loadAgents,
    createAndStartDebate,
  } = useDebateStore();

  const [format, setFormat] = useState(paramFormat || "conference");
  const [topic, setTopic] = useState(paramTopic || "");
  const [maxRounds, setMaxRounds] = useState(paramRounds ? Number(paramRounds) : 5);
  const [agents, setAgents] = useState<ResearcherAgent[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectionUrl, setConnectionUrl] = useState(paramOssr || ossrUrl);

  // Connect + load formats on mount (with URL param support)
  useEffect(() => {
    async function init() {
      try {
        // If OSSR URL was passed via params, set it before connecting
        if (paramOssr) {
          useDebateStore.getState().setOssrUrl(paramOssr);
        }
        if (!adapterConnected) await connectToOssr();
        await loadFormats();
        const agentList = await loadAgents();
        setAgents(agentList);

        // Pre-select agents from URL params
        if (paramAgents) {
          const ids = paramAgents.split(",").filter(Boolean);
          const validIds = ids.filter((id) => agentList.some((a) => a.agent_id === id));
          if (validIds.length > 0) {
            setSelectedIds(new Set(validIds));
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Connection failed");
      }
    }
    void init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleConnect = useCallback(async () => {
    setError(null);
    useDebateStore.getState().setOssrUrl(connectionUrl);
    try {
      await connectToOssr();
      await loadFormats();
      const agentList = await loadAgents();
      setAgents(agentList);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    }
  }, [connectionUrl, connectToOssr, loadFormats, loadAgents]);

  const toggleAgent = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(agents.map((a) => a.agent_id)));
  }, [agents]);

  const handleStart = useCallback(async () => {
    if (selectedIds.size < 2) {
      setError("Select at least 2 agents");
      return;
    }
    if (!topic.trim()) {
      setError("Enter a debate topic");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await createAndStartDebate(
        format as "conference",
        topic.trim(),
        Array.from(selectedIds),
        maxRounds,
      );
      const simId = useDebateStore.getState().simulationId;
      navigate(`/debate/${simId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start debate");
    } finally {
      setLoading(false);
    }
  }, [selectedIds, topic, format, maxRounds, createAndStartDebate, navigate]);

  // Update default rounds when format changes
  useEffect(() => {
    const fmt = formats.find((f) => f.id === format);
    if (fmt) setMaxRounds(fmt.default_rounds);
  }, [format, formats]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-4 dark:bg-gray-950">
      <div className="w-full max-w-2xl rounded-2xl border border-gray-200 bg-white p-8 shadow-xl dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-6 flex items-center gap-3">
          <MessageCircle className="h-6 w-6 text-blue-500" />
          <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            {t("setup.title", "Create Research Debate")}
          </h1>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Connection */}
        {!adapterConnected && (
          <div className="mb-6">
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
              {t("setup.ossrUrl", "OSSR Backend URL")}
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={connectionUrl}
                onChange={(e) => setConnectionUrl(e.target.value)}
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
                placeholder="http://localhost:5002"
              />
              <button
                onClick={handleConnect}
                className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
              >
                {t("setup.connect", "Connect")}
              </button>
            </div>
          </div>
        )}

        {adapterConnected && (
          <>
            {/* Format */}
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                <Zap className="mr-1 inline h-4 w-4" />
                {t("setup.format", "Discussion Format")}
              </label>
              <select
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
              >
                {formats.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} — {f.description}
                  </option>
                ))}
              </select>
            </div>

            {/* Topic */}
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t("setup.topic", "Debate Topic")}
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder={t("setup.topicPlaceholder", "e.g., The role of AI in drug discovery...")}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
              />
            </div>

            {/* Max Rounds */}
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                {t("setup.rounds", "Max Rounds")}: {maxRounds}
              </label>
              <input
                type="range"
                min={1}
                max={15}
                value={maxRounds}
                onChange={(e) => setMaxRounds(Number(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Mirofish Orchestrated Mode */}
            <div className="mb-4">
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 px-3 py-2.5 hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800">
                <input
                  type="checkbox"
                  checked={useDebateStore.getState().orchestrated}
                  onChange={(e) => {
                    useDebateStore.setState({ orchestrated: e.target.checked });
                  }}
                  className="rounded"
                />
                <BarChart3 className="h-4 w-4 text-blue-500" />
                <div>
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {t("setup.orchestrated", "Mirofish Orchestrated Mode")}
                  </span>
                  <p className="text-xs text-gray-500">
                    {t("setup.orchestratedDesc", "Structured debate with scoreboard, knowledge graph, and stance tracking")}
                  </p>
                </div>
              </label>
            </div>

            {/* Agent Picker */}
            <div className="mb-6">
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  <Users className="mr-1 inline h-4 w-4" />
                  {t("setup.agents", "Select Agents")} ({selectedIds.size} selected)
                </label>
                <button
                  onClick={selectAll}
                  className="text-xs text-blue-500 hover:text-blue-600"
                >
                  {t("setup.selectAll", "Select All")}
                </button>
              </div>
              <div className="max-h-48 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-700">
                {agents.length === 0 ? (
                  <p className="p-3 text-center text-sm text-gray-500">
                    {t("setup.noAgents", "No agents found. Generate agents in OSSR first.")}
                  </p>
                ) : (
                  agents.map((agent) => (
                    <label
                      key={agent.agent_id}
                      className="flex cursor-pointer items-center gap-3 border-b border-gray-100 px-3 py-2 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800"
                    >
                      <input
                        type="checkbox"
                        checked={selectedIds.has(agent.agent_id)}
                        onChange={() => toggleAgent(agent.agent_id)}
                        className="rounded"
                      />
                      <div className="flex-1">
                        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                          {agent.name}
                        </span>
                        <span className="ml-2 text-xs text-gray-500">
                          {agent.role} — {agent.affiliation}
                        </span>
                      </div>
                      {agent.llm_provider && (
                        <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                          {agent.llm_provider}
                        </span>
                      )}
                    </label>
                  ))
                )}
              </div>
            </div>

            {/* Start Button */}
            <button
              onClick={handleStart}
              disabled={loading || selectedIds.size < 2 || !topic.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {loading
                ? t("setup.starting", "Starting Debate...")
                : t("setup.start", "Start Visual Debate")}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
