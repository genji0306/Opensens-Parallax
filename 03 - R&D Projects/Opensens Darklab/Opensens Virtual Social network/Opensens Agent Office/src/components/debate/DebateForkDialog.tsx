/**
 * DebateForkDialog — "What If?" fork dialog
 *
 * Allows the user to fork a completed debate from a specific round,
 * optionally modifying the topic, and start a new divergent simulation.
 */

import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useDebateStore } from "@/store/debate-store";
import { GitFork, X } from "lucide-react";

interface DebateForkDialogProps {
  open: boolean;
  onClose: () => void;
}

export function DebateForkDialog({ open, onClose }: DebateForkDialogProps) {
  const { t } = useTranslation("debate");
  const navigate = useNavigate();

  const format = useDebateStore((s) => s.format);
  const topic = useDebateStore((s) => s.topic);
  const maxRounds = useDebateStore((s) => s.maxRounds);
  const forkAndStartDebate = useDebateStore((s) => s.forkAndStartDebate);
  const simulationId = useDebateStore((s) => s.simulationId);

  const [fromRound, setFromRound] = useState(Math.max(1, maxRounds - 1));
  const [topicOverride, setTopicOverride] = useState("");
  const [forking, setForking] = useState(false);

  const handleFork = useCallback(async () => {
    if (forking) return;
    setForking(true);
    try {
      const modifications: Record<string, unknown> = {};
      if (topicOverride.trim()) {
        modifications.topic = topicOverride.trim();
      }
      await forkAndStartDebate(fromRound, modifications);
      onClose();
      // Navigate to the new forked debate
      const newSimId = useDebateStore.getState().simulationId;
      if (newSimId) {
        navigate(`/debate/${newSimId}`);
      }
    } catch {
      // Error handling done in store
    } finally {
      setForking(false);
    }
  }, [forking, fromRound, topicOverride, forkAndStartDebate, onClose, navigate]);

  if (!open || !simulationId) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-900">
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitFork className="h-5 w-5 text-purple-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {t("fork.title", 'Fork Debate \u2014 "What If?"')}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Current debate info */}
        <div className="mb-4 rounded-lg bg-gray-50 p-3 dark:bg-gray-800">
          <p className="text-xs text-gray-500">
            <span className="font-medium">{t("fork.format", "Format")}:</span>{" "}
            {format}
          </p>
          <p className="mt-1 text-xs text-gray-500">
            <span className="font-medium">{t("fork.topic", "Topic")}:</span>{" "}
            {topic}
          </p>
        </div>

        {/* Fork from round */}
        <div className="mb-4">
          <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
            {t("fork.fromRound", "Fork from round")}:{" "}
            <span className="text-purple-600 dark:text-purple-400">
              {fromRound}
            </span>
          </label>
          <input
            type="range"
            min={1}
            max={maxRounds}
            value={fromRound}
            onChange={(e) => setFromRound(Number(e.target.value))}
            className="w-full accent-purple-500"
          />
          <div className="mt-1 flex justify-between text-[10px] text-gray-400">
            <span>1</span>
            <span>{maxRounds}</span>
          </div>
        </div>

        {/* Topic override */}
        <div className="mb-5">
          <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
            {t("fork.topicOverride", "Modify topic (optional)")}
          </label>
          <input
            type="text"
            value={topicOverride}
            onChange={(e) => setTopicOverride(e.target.value)}
            placeholder={topic}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            {t("fork.cancel", "Cancel")}
          </button>
          <button
            onClick={handleFork}
            disabled={forking}
            className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
          >
            <GitFork className="h-3.5 w-3.5" />
            {forking
              ? t("fork.starting", "Forking...")
              : t("fork.start", "Start Forked Debate")}
          </button>
        </div>
      </div>
    </div>
  );
}
