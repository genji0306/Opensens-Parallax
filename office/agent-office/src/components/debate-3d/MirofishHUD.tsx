/**
 * MirofishHUD — 3D Html overlay showing scoreboard + analyst feed
 *
 * Rendered inside the R3F <Canvas> via @react-three/drei Html.
 * Shows option confidence bars, consensus meter, agent influence,
 * and latest analyst narrative when Mirofish orchestration is active.
 */

import { Html } from "@react-three/drei";
import { useMemo } from "react";
import { useDebateStore } from "@/store/debate-store";
import { useOfficeStore } from "@/store/office-store";

// ── Color helpers ──────────────────────────────────────────────────

function trendArrow(trend: string): string {
  if (trend === "rising" || trend === "converging") return "\u25B2";
  if (trend === "falling" || trend === "diverging") return "\u25BC";
  return "\u25CF";
}

function trendColor(trend: string): string {
  if (trend === "rising" || trend === "converging") return "#22c55e";
  if (trend === "falling" || trend === "diverging") return "#ef4444";
  return "#94a3b8";
}

function stanceColor(position: number): string {
  // -1 red → 0 yellow → +1 green
  const hue = Math.round(((position + 1) / 2) * 145);
  return `hsl(${hue}, 70%, 45%)`;
}

// ── Scoreboard Panel ───────────────────────────────────────────────

function ScoreboardOverlay({ isDark }: { isDark: boolean }) {
  const scoreboard = useDebateStore((s) => s.mirofishScoreboard);

  if (!scoreboard) return null;

  const bg = isDark ? "rgba(15,23,42,0.9)" : "rgba(255,255,255,0.92)";
  const text = isDark ? "#e2e8f0" : "#1e293b";
  const textMuted = isDark ? "#94a3b8" : "#64748b";
  const border = isDark ? "#334155" : "#e2e8f0";
  const barBg = isDark ? "#1e293b" : "#f1f5f9";

  return (
    <div
      className="w-56 rounded-lg p-3 shadow-lg"
      style={{ backgroundColor: bg, border: `1px solid ${border}`, color: text }}
    >
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[9px] font-semibold uppercase tracking-wider" style={{ color: textMuted }}>
          Scoreboard
        </span>
        <span className="text-[9px]" style={{ color: textMuted }}>
          R{scoreboard.round_num}
        </span>
      </div>

      {/* Options */}
      <div className="mb-2 flex flex-col gap-1.5">
        {scoreboard.options.map((opt) => (
          <div key={opt.option_id}>
            <div className="flex items-center justify-between text-[10px]">
              <span className="truncate" style={{ maxWidth: "110px" }}>
                {opt.label}
              </span>
              <span className="flex items-center gap-1">
                <span style={{ color: trendColor(opt.trend), fontSize: "8px" }}>
                  {trendArrow(opt.trend)}
                </span>
                <span className="font-semibold">{Math.round(opt.confidence * 100)}%</span>
              </span>
            </div>
            <div className="mt-0.5 h-1.5 overflow-hidden rounded-full" style={{ backgroundColor: barBg }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${opt.confidence * 100}%`,
                  backgroundColor: opt.confidence > 0.6 ? "#3b82f6" : opt.confidence > 0.3 ? "#f59e0b" : "#94a3b8",
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {/* Consensus */}
      <div className="mb-2 flex items-center justify-between" style={{ borderTop: `1px solid ${border}`, paddingTop: "6px" }}>
        <span className="text-[9px]" style={{ color: textMuted }}>Consensus</span>
        <span className="flex items-center gap-1 text-[10px] font-semibold">
          <span style={{ color: trendColor(scoreboard.consensus_trend), fontSize: "8px" }}>
            {trendArrow(scoreboard.consensus_trend)}
          </span>
          {Math.round(scoreboard.consensus_pct * 100)}%
        </span>
      </div>

      {/* Top influencers (max 3) */}
      {scoreboard.agent_influence.length > 0 && (
        <div style={{ borderTop: `1px solid ${border}`, paddingTop: "6px" }}>
          <div className="mb-1 text-[9px] font-semibold uppercase tracking-wider" style={{ color: textMuted }}>
            Influence
          </div>
          {scoreboard.agent_influence.slice(0, 3).map((ai) => (
            <div key={ai.agent_id} className="flex items-center justify-between text-[10px]">
              <span className="truncate" style={{ maxWidth: "100px" }}>
                {ai.name || ai.agent_id.slice(0, 12)}
              </span>
              <div className="flex items-center gap-1">
                <div className="h-1 w-10 overflow-hidden rounded-full" style={{ backgroundColor: barBg }}>
                  <div
                    className="h-full rounded-full bg-blue-400"
                    style={{ width: `${ai.score * 100}%` }}
                  />
                </div>
                <span className="w-7 text-right text-[9px]" style={{ color: textMuted }}>
                  {ai.score.toFixed(1)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Analyst Feed ───────────────────────────────────────────────────

function AnalystOverlay({ isDark }: { isDark: boolean }) {
  const analystFeed = useDebateStore((s) => s.mirofishAnalystFeed);
  const currentRound = useDebateStore((s) => s.currentRound);

  const latest = useMemo(() => {
    // Show analyst entry for current round (or most recent)
    const sorted = [...analystFeed].sort((a, b) => b.round_num - a.round_num);
    return sorted.find((e) => e.round_num <= currentRound) ?? sorted[0] ?? null;
  }, [analystFeed, currentRound]);

  if (!latest) return null;

  const bg = isDark ? "rgba(15,23,42,0.9)" : "rgba(255,255,255,0.92)";
  const text = isDark ? "#cbd5e1" : "#475569";
  const textMuted = isDark ? "#94a3b8" : "#64748b";
  const border = isDark ? "#334155" : "#e2e8f0";

  return (
    <div
      className="w-56 rounded-lg p-3 shadow-lg"
      style={{ backgroundColor: bg, border: `1px solid ${border}` }}
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="text-[9px] font-semibold uppercase tracking-wider" style={{ color: textMuted }}>
          Analyst
        </span>
        <span className="text-[9px]" style={{ color: textMuted }}>
          R{latest.round_num}
        </span>
      </div>
      <div className="text-[10px] leading-relaxed" style={{ color: text, maxHeight: "100px", overflow: "auto" }}>
        {latest.narrative.length > 250 ? `${latest.narrative.slice(0, 247)}...` : latest.narrative}
      </div>
      {latest.key_events.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {latest.key_events.slice(0, 3).map((ev, i) => (
            <span
              key={i}
              className="rounded-full px-1.5 py-0.5 text-[8px]"
              style={{ backgroundColor: isDark ? "#1e293b" : "#f1f5f9", color: textMuted }}
            >
              {ev.length > 20 ? `${ev.slice(0, 18)}..` : ev}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Stance Mini-Map ────────────────────────────────────────────────

function StanceMiniMap({ isDark }: { isDark: boolean }) {
  const stances = useDebateStore((s) => s.mirofishStances);
  const currentRound = useDebateStore((s) => s.currentRound);
  const frame = useDebateStore((s) => s.mirofishFrame);
  const agents = useDebateStore((s) => s.debateAgents);

  // Get latest stance per agent per option
  const latestStances = useMemo(() => {
    const map = new Map<string, { position: number; confidence: number }>();
    for (const s of stances) {
      if (s.round_num > currentRound) continue;
      const key = `${s.agent_id}|${s.option_id}`;
      const existing = map.get(key);
      if (!existing || s.round_num > (existing as any)._round) {
        map.set(key, { position: s.position, confidence: s.confidence, _round: s.round_num } as any);
      }
    }
    return map;
  }, [stances, currentRound]);

  const options = frame?.options ?? [];
  const agentList = useMemo(() => Array.from(agents.values()), [agents]);

  if (options.length === 0 || agentList.length === 0 || latestStances.size === 0) return null;

  const bg = isDark ? "rgba(15,23,42,0.9)" : "rgba(255,255,255,0.92)";
  const textMuted = isDark ? "#94a3b8" : "#64748b";
  const border = isDark ? "#334155" : "#e2e8f0";
  const cellBg = isDark ? "#1e293b" : "#f1f5f9";

  return (
    <div
      className="w-56 rounded-lg p-3 shadow-lg"
      style={{ backgroundColor: bg, border: `1px solid ${border}` }}
    >
      <div className="mb-2 text-[9px] font-semibold uppercase tracking-wider" style={{ color: textMuted }}>
        Stance Map
      </div>
      <div
        className="grid gap-px"
        style={{ gridTemplateColumns: `50px repeat(${options.length}, 1fr)` }}
      >
        {/* Header */}
        <div />
        {options.map((opt) => (
          <div key={opt.option_id} className="truncate text-center text-[8px]" style={{ color: textMuted }}>
            {opt.label.length > 6 ? `${opt.label.slice(0, 5)}.` : opt.label}
          </div>
        ))}

        {/* Rows */}
        {agentList.map((agent) => (
          <React.Fragment key={agent.id}>
            <div className="truncate text-[8px]" style={{ color: textMuted }}>
              {agent.name.split(" ")[0]?.slice(0, 6) ?? agent.id.slice(0, 6)}
            </div>
            {options.map((opt) => {
              const s = latestStances.get(`${agent.id}|${opt.option_id}`);
              const bg = s ? stanceColor(s.position) : cellBg;
              const opacity = s ? 0.3 + s.confidence * 0.7 : 0.3;
              return (
                <div
                  key={opt.option_id}
                  className="h-3 rounded-sm"
                  style={{ backgroundColor: bg, opacity }}
                  title={s ? `${agent.name}: ${s.position.toFixed(2)}` : "no data"}
                />
              );
            })}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

// ── Main HUD Export ────────────────────────────────────────────────

import React from "react";

export function MirofishHUD() {
  const orchestrated = useDebateStore((s) => s.orchestrated);
  const visible = useDebateStore((s) => s.mirofishHudVisible);
  const theme = useOfficeStore((s) => s.theme);

  if (!orchestrated || !visible) return null;

  const isDark = theme === "dark";

  return (
    <Html fullscreen style={{ pointerEvents: "none" }}>
      {/* Left panel — Scoreboard */}
      <div className="pointer-events-auto absolute left-3 top-16 flex flex-col gap-2">
        <ScoreboardOverlay isDark={isDark} />
        <StanceMiniMap isDark={isDark} />
      </div>

      {/* Bottom-right — Analyst feed */}
      <div className="pointer-events-auto absolute bottom-16 right-3">
        <AnalystOverlay isDark={isDark} />
      </div>
    </Html>
  );
}
