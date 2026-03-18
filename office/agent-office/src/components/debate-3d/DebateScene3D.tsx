/**
 * DebateScene3D — Full R3F debate arena
 *
 * Combines DebateEnvironment3D + DebateAgent3D with:
 * - Format-specific 3D seating layouts (adapted from 2D calculateSeats)
 * - Camera auto-pan to follow the active speaker
 * - Speech bubble overlay for current turn via @react-three/drei Html
 * - Paused overlay + round progress HUD
 */

import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { useMemo, useRef, useEffect } from "react";
import * as THREE from "three";
import { useTranslation } from "react-i18next";
import { useDebateStore } from "@/store/debate-store";
import { useOfficeStore } from "@/store/office-store";
import { STATUS_COLORS } from "@/lib/constants";
import { DebateAgent3D } from "./DebateAgent3D";
import { DebateEnvironment3D } from "./DebateEnvironment3D";
import { MirofishHUD } from "./MirofishHUD";

// ── 3D Seat Calculation ──────────────────────────────────────────────

type Seat3D = [number, number, number]; // [x, y, z]

function calculateSeats3D(format: string, count: number): Seat3D[] {
  const seats: Seat3D[] = [];
  const r = count > 6 ? 4.5 : 3.2;

  switch (format) {
    case "conference": {
      // Semicircular arc behind the podium (facing center)
      for (let i = 0; i < count; i++) {
        const angle = Math.PI + (Math.PI * (i + 1)) / (count + 1);
        seats.push([r * Math.cos(angle), 0, r * 0.8 * Math.sin(angle)]);
      }
      break;
    }
    case "peer_review": {
      // Two rows facing each other across a table
      const half = Math.ceil(count / 2);
      for (let i = 0; i < count; i++) {
        const row = i < half ? -1 : 1;
        const idx = i < half ? i : i - half;
        const rowCount = row === -1 ? half : count - half;
        const spacing = 1.5;
        const startX = -((rowCount - 1) * spacing) / 2;
        seats.push([startX + idx * spacing, 0, row * 1.8]);
      }
      break;
    }
    case "adversarial": {
      // Two opposing sides: left vs right of center divider
      const half = Math.ceil(count / 2);
      for (let i = 0; i < count; i++) {
        const side = i < half ? -1 : 1;
        const idx = i < half ? i : i - half;
        const sideCount = side === -1 ? half : count - half;
        const spacing = 1.4;
        const startZ = -((sideCount - 1) * spacing) / 2;
        seats.push([side * 2.8, 0, startZ + idx * spacing]);
      }
      break;
    }
    case "workshop":
    case "longitudinal":
    default: {
      // Circular arrangement around a round table
      for (let i = 0; i < count; i++) {
        const angle = (2 * Math.PI * i) / count - Math.PI / 2;
        seats.push([r * Math.cos(angle), 0, r * Math.sin(angle)]);
      }
      break;
    }
  }

  return seats;
}

// ── Camera Controller ────────────────────────────────────────────────

function CameraController({ targetPosition }: { targetPosition: Seat3D | null }) {
  const controlsRef = useRef<any>(null);
  const targetRef = useRef(new THREE.Vector3(0, 1, 0));

  useFrame(() => {
    if (!controlsRef.current) return;

    // Smoothly pan camera target toward active speaker
    const dest = targetPosition
      ? new THREE.Vector3(targetPosition[0] * 0.3, 1, targetPosition[2] * 0.3)
      : new THREE.Vector3(0, 1, 0);

    targetRef.current.lerp(dest, 0.03);
    controlsRef.current.target.copy(targetRef.current);
    controlsRef.current.update();
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enableRotate
      enablePan
      enableZoom
      minPolarAngle={Math.PI / 8}
      maxPolarAngle={Math.PI / 2.4}
      minDistance={6}
      maxDistance={20}
      target={[0, 1, 0]}
      enableDamping
      dampingFactor={0.08}
    />
  );
}

// ── Background Sync ──────────────────────────────────────────────────

const BG_LIGHT = new THREE.Color("#e8ecf2");
const BG_DARK = new THREE.Color("#0f1729");

function BackgroundSync() {
  const theme = useOfficeStore((s) => s.theme);
  const { gl } = useThree();
  const colorRef = useRef(new THREE.Color(BG_DARK));

  useEffect(() => {
    gl.setClearColor(colorRef.current);
  }, [gl]);

  useFrame(() => {
    const target = theme === "light" ? BG_LIGHT : BG_DARK;
    colorRef.current.lerp(target, 0.05);
    gl.setClearColor(colorRef.current);
  });

  return null;
}

// ── Speech Bubble ────────────────────────────────────────────────────

function SpeechBubble3D({ position, content, turnType, theme }: {
  position: Seat3D;
  content: string;
  turnType: string;
  theme: string;
}) {
  const isDark = theme === "dark";
  const truncated = content.length > 200 ? content.slice(0, 197) + "..." : content;

  return (
    <Html
      position={[position[0], 1.8, position[2]]}
      center
      transform={false}
      style={{ pointerEvents: "none" }}
    >
      <div
        className="pointer-events-none w-64 rounded-lg p-2.5 shadow-lg"
        style={{
          backgroundColor: isDark ? "rgba(30,41,59,0.95)" : "rgba(255,255,255,0.95)",
          border: `1px solid ${isDark ? "#334155" : "#e2e8f0"}`,
        }}
      >
        <div
          className="mb-1 text-[9px] font-semibold uppercase tracking-wide"
          style={{ color: STATUS_COLORS.speaking }}
        >
          {turnType}
        </div>
        <div
          className="text-[11px] leading-relaxed"
          style={{ color: isDark ? "#cbd5e1" : "#475569" }}
        >
          {truncated}
        </div>
      </div>
    </Html>
  );
}

// ── Status HUD ───────────────────────────────────────────────────────

function StatusHUD() {
  const { t } = useTranslation("debate");
  const status = useDebateStore((s) => s.status);
  const currentRound = useDebateStore((s) => s.currentRound);
  const maxRounds = useDebateStore((s) => s.maxRounds);
  const topic = useDebateStore((s) => s.topic);
  const theme = useOfficeStore((s) => s.theme);
  const isDark = theme === "dark";

  const label =
    status === "running"
      ? `Round ${currentRound} / ${maxRounds}`
      : status === "completed"
        ? t("completed", "Debate Completed")
        : status === "paused"
          ? t("status.paused", "PAUSED")
          : t("waiting", "Waiting to start...");

  return (
    <Html fullscreen style={{ pointerEvents: "none" }}>
      <div className="pointer-events-none absolute inset-x-0 top-0 flex flex-col items-center gap-1 pt-3">
        <div
          className="rounded-full px-3 py-1 text-xs font-medium shadow"
          style={{
            backgroundColor: isDark ? "rgba(15,23,42,0.8)" : "rgba(255,255,255,0.85)",
            color: isDark ? "#e2e8f0" : "#1e293b",
          }}
        >
          {topic.length > 60 ? `${topic.slice(0, 57)}...` : topic}
        </div>
        <div
          className="rounded-full px-2.5 py-0.5 text-[10px] font-semibold shadow"
          style={{
            backgroundColor:
              status === "paused"
                ? "rgba(245,158,11,0.9)"
                : isDark ? "rgba(15,23,42,0.7)" : "rgba(255,255,255,0.75)",
            color:
              status === "paused"
                ? "#ffffff"
                : isDark ? "#94a3b8" : "#64748b",
          }}
        >
          {label}
        </div>
        {/* Progress bar */}
        {maxRounds > 0 && (
          <div
            className="h-1 w-40 overflow-hidden rounded-full"
            style={{ backgroundColor: isDark ? "#334155" : "#e2e8f0" }}
          >
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-500"
              style={{ width: `${(currentRound / maxRounds) * 100}%` }}
            />
          </div>
        )}
      </div>

      {/* PAUSED overlay */}
      {status === "paused" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div
            className="rounded-2xl px-8 py-4 text-4xl font-bold"
            style={{
              backgroundColor: "rgba(0,0,0,0.3)",
              color: "#f59e0b",
            }}
          >
            {t("status.paused", "PAUSED")}
          </div>
        </div>
      )}
    </Html>
  );
}

// ── Scene Content ────────────────────────────────────────────────────

function DebateSceneContent() {
  const theme = useOfficeStore((s) => s.theme);
  const format = useDebateStore((s) => s.format);
  const debateAgents = useDebateStore((s) => s.debateAgents);
  const activeAgentId = useDebateStore((s) => s.activeAgentId);
  const transcript = useDebateStore((s) => s.transcript);

  const agentList = useMemo(() => Array.from(debateAgents.values()), [debateAgents]);
  const seats = useMemo(() => calculateSeats3D(format, agentList.length), [format, agentList.length]);

  const lastTurn = transcript.length > 0 ? transcript[transcript.length - 1] : null;

  // Find active agent seat for camera + speech bubble
  const activeIdx = activeAgentId ? agentList.findIndex((a) => a.id === activeAgentId) : -1;
  const activeSeat = activeIdx >= 0 ? seats[activeIdx] : null;

  return (
    <>
      <BackgroundSync />
      <CameraController targetPosition={activeSeat} />
      <DebateEnvironment3D theme={theme} format={format} />

      {/* Debate participants */}
      {agentList.map((agent, i) => {
        const seat = seats[i];
        if (!seat) return null;
        return <DebateAgent3D key={agent.id} agent={agent} position={seat} />;
      })}

      {/* Speech bubble for active speaker */}
      {lastTurn && activeSeat && (
        <SpeechBubble3D
          position={activeSeat}
          content={lastTurn.content}
          turnType={lastTurn.turn_type}
          theme={theme}
        />
      )}

      {/* Status HUD */}
      <StatusHUD />

      {/* Mirofish scoreboard + analyst HUD (orchestrated mode only) */}
      <MirofishHUD />

      {/* Bloom postprocessing */}
      <EffectComposer>
        <Bloom intensity={0.8} luminanceThreshold={0.7} luminanceSmoothing={0.4} mipmapBlur />
      </EffectComposer>
    </>
  );
}

// ── Exported Component ───────────────────────────────────────────────

export function DebateScene3D() {
  return (
    <div className="h-full w-full">
      <Canvas
        gl={{ antialias: true, alpha: false }}
        shadows
        camera={{
          fov: 45,
          position: [8, 8, 8],
          near: 0.1,
          far: 100,
        }}
      >
        <DebateSceneContent />
      </Canvas>
    </div>
  );
}
