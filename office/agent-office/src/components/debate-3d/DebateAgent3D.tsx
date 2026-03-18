/**
 * DebateAgent3D — 3D character for debate participants
 *
 * Capsule body + sphere head (same geometry as AgentCharacter from office-3d).
 * Adds debate-specific visuals: speaking glow, pulsing ring, speech bubble via Html overlay.
 */

import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef, useState, useMemo } from "react";
import * as THREE from "three";
import type { Group, Mesh } from "three";
import { generateAvatar3dColor } from "@/lib/avatar-generator";
import { STATUS_COLORS } from "@/lib/constants";
import type { DebateVisualAgent } from "@/store/debate-store";
import { useDebateStore } from "@/store/debate-store";
import { useOfficeStore } from "@/store/office-store";

interface DebateAgent3DProps {
  agent: DebateVisualAgent;
  position: [number, number, number];
}

export function DebateAgent3D({ agent, position }: DebateAgent3DProps) {
  const groupRef = useRef<Group>(null);
  const bodyRef = useRef<Group>(null);
  const ringRef = useRef<Mesh>(null);
  const stanceRingRef = useRef<Mesh>(null);
  const [hovered, setHovered] = useState(false);

  const activeAgentId = useDebateStore((s) => s.activeAgentId);
  const status = useDebateStore((s) => s.status);
  const openChat = useDebateStore((s) => s.openChat);
  const theme = useOfficeStore((s) => s.theme);
  const orchestrated = useDebateStore((s) => s.orchestrated);
  const mirofishStances = useDebateStore((s) => s.mirofishStances);
  const currentRound = useDebateStore((s) => s.currentRound);

  const isActive = agent.id === activeAgentId;
  const isSpeaking = agent.status === "speaking";
  const baseColor = generateAvatar3dColor(agent.id);
  const statusColor = STATUS_COLORS[agent.status] ?? STATUS_COLORS.idle;

  // Compute dominant stance color for this agent (averaged across options)
  const stanceVisual = useMemo(() => {
    if (!orchestrated) return null;
    const agentStances = mirofishStances.filter(
      (s) => s.agent_id === agent.id && s.round_num <= currentRound,
    );
    if (agentStances.length === 0) return null;

    // Get latest stance per option
    const latest = new Map<string, { position: number; confidence: number; round_num: number }>();
    for (const s of agentStances) {
      const existing = latest.get(s.option_id);
      if (!existing || s.round_num > existing.round_num) {
        latest.set(s.option_id, s);
      }
    }

    // Average position and confidence
    let totalPos = 0;
    let totalConf = 0;
    let count = 0;
    for (const s of latest.values()) {
      totalPos += s.position;
      totalConf += s.confidence;
      count++;
    }
    if (count === 0) return null;

    const avgPos = totalPos / count;
    const avgConf = totalConf / count;
    // Map position to hue: -1=red(0), 0=yellow(55), +1=green(145)
    const hue = Math.round(((avgPos + 1) / 2) * 145);
    return {
      color: `hsl(${hue}, 70%, 45%)`,
      opacity: 0.2 + avgConf * 0.5,
    };
  }, [orchestrated, mirofishStances, currentRound, agent.id]);

  const canClick = status === "running" || status === "paused" || status === "completed";

  useFrame((state) => {
    const t = state.clock.elapsedTime;

    // Idle breathing
    if (bodyRef.current) {
      bodyRef.current.position.y = Math.sin(t * 2) * 0.015;
    }

    // Speaking: pulsing ring
    if (ringRef.current) {
      if (isActive) {
        ringRef.current.visible = true;
        const pulse = 0.5 + Math.sin(t * 4) * 0.15;
        ringRef.current.scale.setScalar(1 + Math.sin(t * 3) * 0.1);
        (ringRef.current.material as THREE.MeshStandardMaterial).opacity = pulse;
      } else {
        ringRef.current.visible = false;
      }
    }

    // Mirofish stance ring: slow rotate
    if (stanceRingRef.current && stanceVisual) {
      stanceRingRef.current.visible = true;
      stanceRingRef.current.rotation.z = t * 0.3;
      (stanceRingRef.current.material as THREE.MeshStandardMaterial).opacity =
        stanceVisual.opacity * (0.8 + Math.sin(t * 1.5) * 0.2);
    } else if (stanceRingRef.current) {
      stanceRingRef.current.visible = false;
    }

    // Active speaker slight bounce
    if (groupRef.current && isActive) {
      groupRef.current.position.y = position[1] + Math.sin(t * 3) * 0.03;
    } else if (groupRef.current) {
      groupRef.current.position.y = position[1];
    }
  });

  return (
    <group
      ref={groupRef}
      position={position}
      onClick={(e) => {
        e.stopPropagation();
        if (canClick) openChat(agent.id);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        if (canClick) {
          setHovered(true);
          document.body.style.cursor = "pointer";
        }
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = "auto";
      }}
    >
      {/* Ground ring — active speaker indicator */}
      <mesh
        ref={ringRef}
        position={[0, 0.02, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        visible={false}
      >
        <ringGeometry args={[0.3, 0.38, 32]} />
        <meshStandardMaterial
          color={statusColor}
          emissive={statusColor}
          emissiveIntensity={0.8}
          transparent
          opacity={0.6}
        />
      </mesh>

      {/* Mirofish stance ring — outer ring showing position color */}
      {stanceVisual && (
        <mesh
          ref={stanceRingRef}
          position={[0, 0.01, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
          visible={false}
        >
          <ringGeometry args={[0.42, 0.5, 32]} />
          <meshStandardMaterial
            color={stanceVisual.color}
            emissive={stanceVisual.color}
            emissiveIntensity={0.4}
            transparent
            opacity={stanceVisual.opacity}
          />
        </mesh>
      )}

      {/* Body group with breathing animation */}
      <group ref={bodyRef}>
        {/* Capsule body */}
        <mesh position={[0, 0.45, 0]} castShadow>
          <capsuleGeometry args={[0.18, 0.5, 8, 16]} />
          <meshStandardMaterial
            color={isSpeaking ? statusColor : baseColor}
            emissive={isSpeaking ? statusColor : "#000000"}
            emissiveIntensity={isSpeaking ? 0.3 : 0}
          />
        </mesh>

        {/* Sphere head */}
        <mesh position={[0, 0.88, 0]} castShadow>
          <sphereGeometry args={[0.15, 16, 16]} />
          <meshStandardMaterial
            color={isSpeaking ? statusColor : baseColor}
            emissive={isSpeaking ? statusColor : "#000000"}
            emissiveIntensity={isSpeaking ? 0.2 : 0}
          />
        </mesh>
      </group>

      {/* Name label (always visible) */}
      <Html position={[0, 1.2, 0]} center transform={false} style={{ pointerEvents: "none" }}>
        <div
          className="pointer-events-none whitespace-nowrap rounded px-1.5 py-0.5 text-center text-[10px] font-medium shadow"
          style={{
            backgroundColor: theme === "dark" ? "rgba(15,23,42,0.85)" : "rgba(255,255,255,0.9)",
            color: theme === "dark" ? "#e2e8f0" : "#1e293b",
            border: isActive ? `1px solid ${statusColor}` : "1px solid transparent",
          }}
        >
          {agent.name.length > 16 ? `${agent.name.slice(0, 14)}...` : agent.name}
        </div>
      </Html>

      {/* Tooltip on hover */}
      {hovered && (
        <Html position={[0, 1.5, 0]} center transform={false} style={{ pointerEvents: "none" }}>
          <div className="pointer-events-none whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-[11px] text-white shadow">
            <div className="font-semibold">{agent.name}</div>
            <div className="text-gray-300">{agent.role}</div>
            <div className="text-gray-400 text-[9px]">{agent.affiliation}</div>
          </div>
        </Html>
      )}
    </group>
  );
}
