/**
 * DebateControlBar — Bottom control bar
 *
 * Pause/resume, speed slider, topic injection, social sharing, fork ("What If?").
 */

import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useDebateStore } from "@/store/debate-store";
import {
  MessageCirclePlus,
  Share2,
  FileText,
  ArrowLeft,
  Pause,
  Play,
  GitFork,
  BarChart3,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { DebateForkDialog } from "./DebateForkDialog";

export function DebateControlBar() {
  const { t } = useTranslation("debate");
  const navigate = useNavigate();

  const status = useDebateStore((s) => s.status);
  const currentRound = useDebateStore((s) => s.currentRound);
  const maxRounds = useDebateStore((s) => s.maxRounds);
  const injectTopic = useDebateStore((s) => s.injectTopic);
  const pauseDebate = useDebateStore((s) => s.pauseDebate);
  const resumeDebate = useDebateStore((s) => s.resumeDebate);
  const speedMultiplier = useDebateStore((s) => s.speedMultiplier);
  const setSpeed = useDebateStore((s) => s.setSpeed);
  const reset = useDebateStore((s) => s.reset);
  const orchestrated = useDebateStore((s) => s.orchestrated);
  const mirofishHudVisible = useDebateStore((s) => s.mirofishHudVisible);
  const toggleMirofishHud = useDebateStore((s) => s.toggleMirofishHud);

  const [injectionText, setInjectionText] = useState("");
  const [injecting, setInjecting] = useState(false);
  const [forkDialogOpen, setForkDialogOpen] = useState(false);

  const isActive = status === "running" || status === "paused";

  const handleInject = useCallback(async () => {
    if (!injectionText.trim() || !isActive) return;
    setInjecting(true);
    try {
      await injectTopic(injectionText.trim());
      setInjectionText("");
    } catch {
      // silently fail
    } finally {
      setInjecting(false);
    }
  }, [injectionText, isActive, injectTopic]);

  const handleBack = useCallback(() => {
    reset();
    navigate("/debate");
  }, [reset, navigate]);

  return (
    <div className="flex items-center gap-3 border-t border-gray-200 bg-white px-4 py-2.5 dark:border-gray-700 dark:bg-gray-900">
      {/* Back button */}
      <button
        onClick={handleBack}
        className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
        title={t("controls.back", "Back to setup")}
      >
        <ArrowLeft className="h-3.5 w-3.5" />
      </button>

      {/* Pause/Resume button */}
      {isActive && (
        <button
          onClick={() =>
            status === "running" ? pauseDebate() : resumeDebate()
          }
          className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
          title={
            status === "running"
              ? t("controls.pause", "Pause debate")
              : t("controls.resume", "Resume debate")
          }
        >
          {status === "running" ? (
            <Pause className="h-3.5 w-3.5" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
        </button>
      )}

      {/* Speed slider */}
      {isActive && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-400">
            {t("controls.speed", "Speed")}
          </span>
          <input
            type="range"
            min={0.5}
            max={5}
            step={0.5}
            value={speedMultiplier}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="w-16 accent-blue-500"
          />
          <span className="w-8 text-right text-[10px] font-medium text-gray-600 dark:text-gray-400">
            {speedMultiplier}x
          </span>
        </div>
      )}

      {/* Round indicator */}
      <div className="flex items-center gap-2">
        <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
          <div
            className="h-full rounded-full bg-blue-500 transition-all duration-500"
            style={{
              width:
                maxRounds > 0
                  ? `${(currentRound / maxRounds) * 100}%`
                  : "0%",
            }}
          />
        </div>
        <span className="text-xs text-gray-500">
          {currentRound}/{maxRounds}
        </span>
      </div>

      {/* Topic injection (during running or paused) */}
      {isActive && (
        <div className="flex flex-1 items-center gap-2">
          <input
            type="text"
            value={injectionText}
            onChange={(e) => setInjectionText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleInject()}
            placeholder={t(
              "controls.injectPlaceholder",
              "Inject a question or topic...",
            )}
            className="flex-1 rounded-lg border border-gray-300 px-3 py-1.5 text-xs dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100"
          />
          <button
            onClick={handleInject}
            disabled={!injectionText.trim() || injecting}
            className="flex items-center gap-1 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-600 disabled:opacity-50"
          >
            <MessageCirclePlus className="h-3.5 w-3.5" />
            {t("controls.inject", "Inject")}
          </button>
        </div>
      )}

      {/* Mirofish HUD toggle */}
      {orchestrated && (
        <button
          onClick={toggleMirofishHud}
          className={`flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium ${
            mirofishHudVisible
              ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
              : "text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
          }`}
          title={mirofishHudVisible ? "Hide scoreboard" : "Show scoreboard"}
        >
          <BarChart3 className="h-3.5 w-3.5" />
        </button>
      )}

      {/* Spacer if not active */}
      {!isActive && <div className="flex-1" />}

      {/* Social sharing + fork (completed) */}
      {status === "completed" && (
        <>
          <button
            onClick={() => setForkDialogOpen(true)}
            className="flex items-center gap-1 rounded-lg bg-purple-100 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:hover:bg-purple-900/50"
            title={t(
              "controls.whatIf",
              'Fork & explore "What If?" scenario',
            )}
          >
            <GitFork className="h-3.5 w-3.5" />
            {t("controls.whatIf", "What If?")}
          </button>
          <button
            className="flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
            title={t("controls.share", "Share to social media")}
          >
            <Share2 className="h-3.5 w-3.5" />
            {t("controls.share", "Share")}
          </button>
          <button
            className="flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
            title={t("controls.report", "Generate AI report")}
          >
            <FileText className="h-3.5 w-3.5" />
            {t("controls.report", "AI Report")}
          </button>
        </>
      )}

      {/* Fork dialog */}
      {forkDialogOpen && (
        <DebateForkDialog
          open={forkDialogOpen}
          onClose={() => setForkDialogOpen(false)}
        />
      )}
    </div>
  );
}
