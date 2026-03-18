/**
 * DebateFloorPlan — SVG debate visualization
 *
 * Renders agents in format-specific seating arrangements on a 1200x700 SVG canvas.
 * Active speaker gets enlarged avatar + speech bubble with turn content.
 */

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { SVG_WIDTH, SVG_HEIGHT, STATUS_COLORS } from "@/lib/constants";
import { useDebateStore, type DebateVisualAgent } from "@/store/debate-store";
import { useOfficeStore } from "@/store/office-store";
import { AgentAvatar } from "@/components/office-2d/AgentAvatar";

// ── Layout Constants ────────────────────────────────────────────────────

const STAGE = {
  cx: SVG_WIDTH / 2,
  cy: SVG_HEIGHT / 2 - 20,
  radiusSmall: 150,
  radiusLarge: 220,
} as const;

const AVATAR_R = 22;
const ACTIVE_R = 28;

// ── Seat Calculation ────────────────────────────────────────────────────

interface Seat {
  x: number;
  y: number;
}

function calculateSeats(
  format: string,
  count: number,
): Seat[] {
  const seats: Seat[] = [];
  const r = count > 6 ? STAGE.radiusLarge : STAGE.radiusSmall;

  switch (format) {
    case "conference": {
      // Semicircular arc facing center
      for (let i = 0; i < count; i++) {
        const angle = Math.PI + (Math.PI * (i + 1)) / (count + 1);
        seats.push({
          x: STAGE.cx + r * Math.cos(angle),
          y: STAGE.cy + r * 0.7 * Math.sin(angle),
        });
      }
      break;
    }
    case "peer_review": {
      // Two rows facing each other: reviewers (top) vs authors (bottom)
      const half = Math.ceil(count / 2);
      for (let i = 0; i < count; i++) {
        const row = i < half ? -1 : 1;
        const idx = i < half ? i : i - half;
        const rowCount = row === -1 ? half : count - half;
        const spacing = 100;
        const startX = STAGE.cx - ((rowCount - 1) * spacing) / 2;
        seats.push({
          x: startX + idx * spacing,
          y: STAGE.cy + row * 100,
        });
      }
      break;
    }
    case "adversarial": {
      // Two opposing sides: left vs right
      const half2 = Math.ceil(count / 2);
      for (let i = 0; i < count; i++) {
        const side = i < half2 ? -1 : 1;
        const idx = i < half2 ? i : i - half2;
        const sideCount = side === -1 ? half2 : count - half2;
        const spacing = 80;
        const startY = STAGE.cy - ((sideCount - 1) * spacing) / 2;
        seats.push({
          x: STAGE.cx + side * 160,
          y: startY + idx * spacing,
        });
      }
      break;
    }
    case "workshop":
    case "longitudinal":
    default: {
      // Circular arrangement (round table)
      for (let i = 0; i < count; i++) {
        const angle = (2 * Math.PI * i) / count - Math.PI / 2;
        seats.push({
          x: STAGE.cx + r * Math.cos(angle),
          y: STAGE.cy + r * 0.7 * Math.sin(angle),
        });
      }
      break;
    }
  }

  return seats;
}

// ── Format Labels ───────────────────────────────────────────────────────

const FORMAT_LABELS: Record<string, string> = {
  conference: "Conference Panel",
  peer_review: "Peer Review",
  workshop: "Workshop Brainstorm",
  adversarial: "Adversarial Debate",
  longitudinal: "Longitudinal Colloquium",
};

// ── Component ───────────────────────────────────────────────────────────

export function DebateFloorPlan() {
  const { t } = useTranslation("debate");
  const theme = useOfficeStore((s) => s.theme);
  const isDark = theme === "dark";

  const format = useDebateStore((s) => s.format);
  const topic = useDebateStore((s) => s.topic);
  const debateAgents = useDebateStore((s) => s.debateAgents);
  const activeAgentId = useDebateStore((s) => s.activeAgentId);
  const transcript = useDebateStore((s) => s.transcript);
  const currentRound = useDebateStore((s) => s.currentRound);
  const maxRounds = useDebateStore((s) => s.maxRounds);
  const status = useDebateStore((s) => s.status);
  const openChat = useDebateStore((s) => s.openChat);

  const agentList = useMemo(
    () => Array.from(debateAgents.values()),
    [debateAgents],
  );

  const seats = useMemo(
    () => calculateSeats(format, agentList.length),
    [format, agentList.length],
  );

  // Last turn for speech bubble
  const lastTurn = transcript.length > 0 ? transcript[transcript.length - 1] : null;

  const bgColor = isDark ? "#0f172a" : "#f1f5f9";
  const stageColor = isDark ? "#1e293b" : "#e2e8f0";
  const textColor = isDark ? "#e2e8f0" : "#1e293b";
  const subtextColor = isDark ? "#94a3b8" : "#64748b";

  return (
    <div className="relative h-full w-full">
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        className="h-full w-full"
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Background */}
        <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill={bgColor} rx={16} />

        {/* Stage area */}
        <ellipse
          cx={STAGE.cx}
          cy={STAGE.cy}
          rx={STAGE.radiusLarge + 60}
          ry={STAGE.radiusLarge * 0.7 + 40}
          fill={stageColor}
          opacity={0.5}
          rx2={24}
        />

        {/* Center table / podium indicator */}
        {(format === "workshop" || format === "longitudinal") && (
          <circle
            cx={STAGE.cx}
            cy={STAGE.cy}
            r={40}
            fill={isDark ? "#334155" : "#cbd5e1"}
            stroke={isDark ? "#475569" : "#94a3b8"}
            strokeWidth={2}
          />
        )}
        {format === "adversarial" && (
          <line
            x1={STAGE.cx}
            y1={STAGE.cy - 140}
            x2={STAGE.cx}
            y2={STAGE.cy + 140}
            stroke={isDark ? "#475569" : "#94a3b8"}
            strokeWidth={2}
            strokeDasharray="8 4"
          />
        )}

        {/* Agent seats */}
        {agentList.map((agent, i) => {
          const seat = seats[i];
          if (!seat) return null;
          const isActive = agent.id === activeAgentId;
          const r = isActive ? ACTIVE_R : AVATAR_R;
          const statusColor = STATUS_COLORS[agent.status] ?? STATUS_COLORS.idle;

          return (
            <g
              key={agent.id}
              transform={`translate(${seat.x}, ${seat.y})`}
              style={{
                cursor:
                  status === "running" ||
                  status === "paused" ||
                  status === "completed"
                    ? "pointer"
                    : "default",
              }}
              onClick={() =>
                (status === "running" ||
                  status === "paused" ||
                  status === "completed") &&
                openChat(agent.id)
              }
            >
              {/* Pulsing ring for active speaker */}
              {isActive && (
                <circle r={r + 6} fill="none" stroke={statusColor} strokeWidth={2} opacity={0.6}>
                  <animate
                    attributeName="r"
                    values={`${r + 4};${r + 10};${r + 4}`}
                    dur="2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.6;0.2;0.6"
                    dur="2s"
                    repeatCount="indefinite"
                  />
                </circle>
              )}

              {/* Avatar circle */}
              <circle
                r={r}
                fill={statusColor}
                opacity={0.15}
                stroke={statusColor}
                strokeWidth={isActive ? 3 : 2}
              />
              <circle r={r - 4} fill={statusColor} opacity={0.3} />

              {/* Agent initial */}
              <text
                y={1}
                textAnchor="middle"
                dominantBaseline="central"
                fill={textColor}
                fontSize={isActive ? 16 : 13}
                fontWeight={700}
              >
                {agent.name.charAt(0)}
              </text>

              {/* Name label */}
              <text
                y={r + 16}
                textAnchor="middle"
                fill={textColor}
                fontSize={11}
                fontWeight={isActive ? 600 : 400}
              >
                {agent.name.length > 14
                  ? `${agent.name.slice(0, 12)}...`
                  : agent.name}
              </text>

              {/* Role label */}
              <text
                y={r + 30}
                textAnchor="middle"
                fill={subtextColor}
                fontSize={9}
              >
                {agent.role}
              </text>
            </g>
          );
        })}

        {/* Speech bubble for active speaker */}
        {lastTurn && activeAgentId && (() => {
          const agentIdx = agentList.findIndex(a => a.id === activeAgentId);
          const seat = seats[agentIdx];
          if (!seat) return null;

          // Position bubble above the agent
          const bubbleX = Math.max(160, Math.min(seat.x, SVG_WIDTH - 160));
          const bubbleY = Math.max(40, seat.y - 80);
          const bubbleW = 280;
          const bubbleH = 80;

          const truncated = lastTurn.content.length > 180
            ? lastTurn.content.slice(0, 177) + "..."
            : lastTurn.content;

          return (
            <g>
              {/* Bubble background */}
              <rect
                x={bubbleX - bubbleW / 2}
                y={bubbleY - bubbleH}
                width={bubbleW}
                height={bubbleH}
                rx={12}
                fill={isDark ? "#1e293b" : "#ffffff"}
                stroke={isDark ? "#334155" : "#e2e8f0"}
                strokeWidth={1}
                filter="url(#bubble-shadow)"
              />
              {/* Pointer */}
              <polygon
                points={`${bubbleX - 8},${bubbleY} ${bubbleX + 8},${bubbleY} ${bubbleX},${bubbleY + 10}`}
                fill={isDark ? "#1e293b" : "#ffffff"}
                stroke={isDark ? "#334155" : "#e2e8f0"}
                strokeWidth={1}
              />
              {/* Turn type badge */}
              <text
                x={bubbleX - bubbleW / 2 + 10}
                y={bubbleY - bubbleH + 18}
                fill={STATUS_COLORS.speaking}
                fontSize={9}
                fontWeight={600}
              >
                {lastTurn.turn_type.toUpperCase()}
              </text>
              {/* Content */}
              <foreignObject
                x={bubbleX - bubbleW / 2 + 8}
                y={bubbleY - bubbleH + 24}
                width={bubbleW - 16}
                height={bubbleH - 30}
              >
                <div
                  // @ts-expect-error xmlns is valid for foreignObject children
                  xmlns="http://www.w3.org/1999/xhtml"
                  style={{
                    fontSize: "10px",
                    lineHeight: "1.4",
                    color: isDark ? "#cbd5e1" : "#475569",
                    overflow: "hidden",
                  }}
                >
                  {truncated}
                </div>
              </foreignObject>
            </g>
          );
        })()}

        {/* Round progress bar */}
        <rect
          x={40}
          y={SVG_HEIGHT - 40}
          width={SVG_WIDTH - 80}
          height={6}
          rx={3}
          fill={isDark ? "#334155" : "#e2e8f0"}
        />
        {maxRounds > 0 && (
          <rect
            x={40}
            y={SVG_HEIGHT - 40}
            width={((SVG_WIDTH - 80) * currentRound) / maxRounds}
            height={6}
            rx={3}
            fill="#3b82f6"
          >
            <animate
              attributeName="width"
              to={((SVG_WIDTH - 80) * currentRound) / maxRounds}
              dur="0.5s"
              fill="freeze"
            />
          </rect>
        )}

        {/* Round label */}
        <text
          x={SVG_WIDTH / 2}
          y={SVG_HEIGHT - 50}
          textAnchor="middle"
          fill={subtextColor}
          fontSize={11}
        >
          {status === "running"
            ? `Round ${currentRound} / ${maxRounds}`
            : status === "completed"
              ? t("completed", "Debate Completed")
              : t("waiting", "Waiting to start...")}
        </text>

        {/* Format + Topic header */}
        <text
          x={SVG_WIDTH / 2}
          y={28}
          textAnchor="middle"
          fill={textColor}
          fontSize={14}
          fontWeight={600}
        >
          {FORMAT_LABELS[format] ?? format}
        </text>
        <text
          x={SVG_WIDTH / 2}
          y={46}
          textAnchor="middle"
          fill={subtextColor}
          fontSize={11}
        >
          {topic.length > 80 ? `${topic.slice(0, 77)}...` : topic}
        </text>

        {/* PAUSED overlay */}
        {status === "paused" && (
          <g>
            <rect x={0} y={0} width={1200} height={700} fill={isDark ? "rgba(0,0,0,0.3)" : "rgba(255,255,255,0.3)"} />
            <text
              x={600}
              y={350}
              textAnchor="middle"
              dominantBaseline="central"
              fill={isDark ? "#f59e0b" : "#d97706"}
              fontSize={48}
              fontWeight="bold"
              opacity={0.8}
            >
              {t("status.paused", "PAUSED")}
            </text>
          </g>
        )}

        {/* Shadow filter for speech bubbles */}
        <defs>
          <filter id="bubble-shadow" x="-5%" y="-5%" width="110%" height="120%">
            <feDropShadow dx="0" dy="2" stdDeviation="4" floodOpacity={isDark ? 0.4 : 0.1} />
          </filter>
        </defs>
      </svg>
    </div>
  );
}
