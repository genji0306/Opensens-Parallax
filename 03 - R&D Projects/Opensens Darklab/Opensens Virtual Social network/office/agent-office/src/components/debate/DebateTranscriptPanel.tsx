/**
 * DebateTranscriptPanel — Side panel showing the full text transcript
 *
 * Grouped by round, with agent names, roles, and turn types.
 * Clickable agent names to open post-sim chat.
 */

import { useEffect, useRef, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useDebateStore } from "@/store/debate-store";
import { STATUS_COLORS } from "@/lib/constants";
import { ScrollText, MessageSquare } from "lucide-react";

const TURN_TYPE_COLORS: Record<string, string> = {
  presentation: "#3b82f6",
  question: "#f59e0b",
  response: "#22c55e",
  review_summary: "#8b5cf6",
  critique: "#ef4444",
  rebuttal: "#06b6d4",
  idea_proposal: "#ec4899",
  build_on: "#14b8a6",
  synthesis: "#a855f7",
  opening_position: "#f97316",
  counterargument: "#ef4444",
  closing: "#6366f1",
  update: "#3b82f6",
  discussion: "#22c55e",
  reflection: "#8b5cf6",
};

export function DebateTranscriptPanel() {
  const { t } = useTranslation("debate");
  const transcript = useDebateStore((s) => s.transcript);
  const status = useDebateStore((s) => s.status);
  const openChat = useDebateStore((s) => s.openChat);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new turns
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [transcript.length]);

  // Group turns by round
  const roundGroups = useMemo(() => {
    const groups = new Map<number, typeof transcript>();
    for (const turn of transcript) {
      const arr = groups.get(turn.round_num) ?? [];
      arr.push(turn);
      groups.set(turn.round_num, arr);
    }
    return Array.from(groups.entries()).sort(([a], [b]) => a - b);
  }, [transcript]);

  return (
    <div className="flex h-full w-80 flex-col border-l border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-gray-200 px-4 py-3 dark:border-gray-700">
        <ScrollText className="h-4 w-4 text-gray-500" />
        <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {t("transcript.title", "Transcript")}
        </h2>
        <span className="ml-auto text-xs text-gray-400">
          {transcript.length} {t("transcript.turns", "turns")}
        </span>
      </div>

      {/* Scrollable transcript */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2">
        {transcript.length === 0 ? (
          <p className="mt-8 text-center text-sm text-gray-400">
            {status === "running"
              ? t("transcript.waiting", "Waiting for first turn...")
              : t("transcript.empty", "No transcript yet")}
          </p>
        ) : (
          roundGroups.map(([roundNum, turns]) => (
            <div key={roundNum} className="mb-4">
              {/* Round header */}
              <div className="sticky top-0 z-10 mb-2 bg-white/90 py-1 text-xs font-semibold uppercase tracking-wide text-gray-400 backdrop-blur dark:bg-gray-900/90">
                Round {roundNum}
              </div>

              {turns.map((turn) => {
                const typeColor =
                  TURN_TYPE_COLORS[turn.turn_type] ?? "#6b7280";
                const isClickable =
                  status === "running" ||
                  status === "paused" ||
                  status === "completed";

                return (
                  <div
                    key={turn.turn_id}
                    className="mb-3 rounded-lg border border-gray-100 bg-gray-50/50 p-2.5 dark:border-gray-800 dark:bg-gray-800/50"
                  >
                    {/* Agent name + turn type */}
                    <div className="mb-1 flex items-center gap-2">
                      <button
                        onClick={() => isClickable && openChat(turn.agent_id)}
                        disabled={!isClickable}
                        className={`text-sm font-semibold ${
                          isClickable
                            ? "text-blue-600 hover:underline dark:text-blue-400"
                            : "text-gray-900 dark:text-gray-100"
                        }`}
                      >
                        {turn.agent_name}
                      </button>
                      <span
                        className="rounded px-1.5 py-0.5 text-[10px] font-medium text-white"
                        style={{ backgroundColor: typeColor }}
                      >
                        {turn.turn_type}
                      </span>
                      {isClickable && (
                        <button
                          onClick={() => openChat(turn.agent_id)}
                          className="ml-auto text-gray-400 hover:text-blue-500"
                          title={t("transcript.chatWith", "Chat with this agent")}
                        >
                          <MessageSquare className="h-3 w-3" />
                        </button>
                      )}
                    </div>

                    {/* Role */}
                    <p className="mb-1 text-[10px] text-gray-400">
                      {turn.agent_role}
                      {turn.llm_provider && ` · ${turn.llm_provider}`}
                    </p>

                    {/* Content */}
                    <p className="whitespace-pre-wrap text-xs leading-relaxed text-gray-700 dark:text-gray-300">
                      {turn.content}
                    </p>

                    {/* Citations */}
                    {turn.cited_dois.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {turn.cited_dois.map((doi) => (
                          <span
                            key={doi}
                            className="rounded bg-blue-50 px-1 py-0.5 text-[9px] text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
                          >
                            {doi}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
