/**
 * DebateAgent3D — 3D character for debate participants
 *
 * Capsule body + sphere head (same geometry as AgentCharacter from office-3d).
 * Adds debate-specific visuals: speaking glow, pulsing ring, speech bubble via Html overlay.
 */

import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useRef, useState } from "react";
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
  const [hovered, setHovered] = useState(false);

  const activeAgentId = useDebateStore((s) => s.activeAgentId);
  const status = useDebateStore((s) => s.status);
  const openChat = useDebateStore((s) => s.openChat);
  const theme = useOfficeStore((s) => s.theme);

  const isActive = agent.id === activeAgentId;
  const isSpeaking = agent.status === "speaking";
  const baseColor = generateAvatar3dColor(agent.id);
  const statusColor = STATUS_COLORS[agent.status] ?? STATUS_COLORS.idle;

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
