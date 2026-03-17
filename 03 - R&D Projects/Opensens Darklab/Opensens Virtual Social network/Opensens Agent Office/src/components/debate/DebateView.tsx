/**
 * DebateView — Layout wrapper for the visual debate mode
 *
 * Combines DebateFloorPlan (2D) or DebateScene3D (3D)
 * + DebateTranscriptPanel + DebateControlBar + DebateChatPanel
 *
 * Toggle between 2D / 3D via a button in the top-right corner.
 */

import { useEffect, useState, lazy, Suspense } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { DebateFloorPlan } from "@/components/debate-2d/DebateFloorPlan";
import { DebateTranscriptPanel } from "./DebateTranscriptPanel";
import { DebateControlBar } from "./DebateControlBar";
import { DebateChatPanel } from "./DebateChatPanel";
import { useDebateStore } from "@/store/debate-store";

// Lazy-load 3D scene to avoid R3F bundle cost when not needed
const DebateScene3D = lazy(() =>
  import("@/components/debate-3d/DebateScene3D").then((m) => ({ default: m.DebateScene3D })),
);

export function DebateView() {
  const { t } = useTranslation("debate");
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const simulationId = useDebateStore((s) => s.simulationId);

  const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");

  // If user navigates directly to /debate/:id without having created a debate,
  // redirect to setup
  useEffect(() => {
    if (!simulationId && id) {
      navigate("/debate");
    }
  }, [simulationId, id, navigate]);

  if (!simulationId) {
    return (
      <div className="flex h-screen items-center justify-center bg-gray-50 dark:bg-gray-950">
        <p className="text-sm text-gray-500">{t("view.loading", "Loading debate...")}</p>
      </div>
    );
  }

  return (
    <div className="relative flex h-screen flex-col bg-gray-50 dark:bg-gray-950">
      {/* Main content: Visualization + TranscriptPanel side by side */}
      <div className="flex flex-1 overflow-hidden">
        {/* Visualization */}
        <div className="relative flex-1">
          {viewMode === "2d" ? (
            <DebateFloorPlan />
          ) : (
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center">
                  <p className="text-sm text-gray-400">
                    {t("view.loading3d", "Loading 3D scene...")}
                  </p>
                </div>
              }
            >
              <DebateScene3D />
            </Suspense>
          )}

          {/* 2D / 3D Toggle */}
          <div className="absolute top-3 right-3 z-10">
            <button
              onClick={() => setViewMode(viewMode === "2d" ? "3d" : "2d")}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white/80 px-2.5 py-1.5 text-xs font-medium text-gray-700 shadow-sm backdrop-blur transition-colors hover:bg-white dark:border-gray-600 dark:bg-gray-800/80 dark:text-gray-200 dark:hover:bg-gray-700"
              title={viewMode === "2d"
                ? t("view.switchTo3d", "Switch to 3D view")
                : t("view.switchTo2d", "Switch to 2D view")}
            >
              {viewMode === "2d" ? (
                <>
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z" />
                    <path d="M12 12l8-4.5" />
                    <path d="M12 12v9" />
                    <path d="M12 12L4 7.5" />
                  </svg>
                  3D
                </>
              ) : (
                <>
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                  </svg>
                  2D
                </>
              )}
            </button>
          </div>
        </div>

        {/* Transcript sidebar */}
        <DebateTranscriptPanel />
      </div>

      {/* Bottom control bar */}
      <DebateControlBar />

      {/* Chat panel (overlay on right side) */}
      <DebateChatPanel />
    </div>
  );
}
