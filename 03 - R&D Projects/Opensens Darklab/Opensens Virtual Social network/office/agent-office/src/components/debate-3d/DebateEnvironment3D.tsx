/**
 * DebateEnvironment3D — Arena floor, lighting, and format-specific furniture
 *
 * Renders different layouts depending on the debate format:
 * - conference: semicircular arc with podium
 * - peer_review: two facing rows with divider table
 * - adversarial: two opposing sides with center divider
 * - workshop/longitudinal: round table circle
 */

import { useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import type { ThemeMode } from "@/gateway/types";
import type { DiscussionFormat } from "@/gateway/ossr-debate-types";

const LIGHT_PARAMS = {
  ambient: { intensity: 0.6, color: new THREE.Color("#f5f0e8") },
  main: { intensity: 1.4, color: new THREE.Color("#fff8ee") },
  fill: { intensity: 0.35, color: new THREE.Color("#dde4f0") },
} as const;

const DARK_PARAMS = {
  ambient: { intensity: 0.2, color: new THREE.Color("#1a1a2e") },
  main: { intensity: 0.5, color: new THREE.Color("#8899bb") },
  fill: { intensity: 0.15, color: new THREE.Color("#2a2a4a") },
} as const;

function DebateLighting({ theme }: { theme: ThemeMode }) {
  const ambientRef = useRef<THREE.AmbientLight>(null);
  const mainRef = useRef<THREE.DirectionalLight>(null);
  const fillRef = useRef<THREE.DirectionalLight>(null);

  const target = theme === "light" ? LIGHT_PARAMS : DARK_PARAMS;

  useFrame((_, delta) => {
    const t = Math.min(delta * 4, 1);
    if (ambientRef.current) {
      ambientRef.current.intensity = THREE.MathUtils.lerp(ambientRef.current.intensity, target.ambient.intensity, t);
      ambientRef.current.color.lerp(target.ambient.color, t);
    }
    if (mainRef.current) {
      mainRef.current.intensity = THREE.MathUtils.lerp(mainRef.current.intensity, target.main.intensity, t);
      mainRef.current.color.lerp(target.main.color, t);
    }
    if (fillRef.current) {
      fillRef.current.intensity = THREE.MathUtils.lerp(fillRef.current.intensity, target.fill.intensity, t);
      fillRef.current.color.lerp(target.fill.color, t);
    }
  });

  return (
    <>
      <ambientLight ref={ambientRef} intensity={0.6} color="#f5f0e8" />
      <directionalLight
        ref={mainRef}
        position={[8, 14, 8]}
        intensity={1.4}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-far={40}
        shadow-camera-left={-12}
        shadow-camera-right={12}
        shadow-camera-top={12}
        shadow-camera-bottom={-12}
        shadow-bias={-0.001}
        color="#fff8ee"
      />
      <directionalLight ref={fillRef} position={[-6, 8, -4]} intensity={0.35} color="#dde4f0" />
      <hemisphereLight args={["#e0e8f5", "#b0a090", 0.35]} />
      {theme === "dark" && (
        <pointLight position={[0, 3, 0]} intensity={0.8} color="#ffd599" distance={12} decay={2} />
      )}
    </>
  );
}

/** Circular ground platform */
function ArenaFloor({ theme }: { theme: ThemeMode }) {
  const isDark = theme === "dark";
  return (
    <group>
      {/* Outer ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <circleGeometry args={[7, 64]} />
        <meshStandardMaterial color={isDark ? "#1e293b" : "#cbd5e1"} roughness={0.9} />
      </mesh>
      {/* Inner floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.0, 0]} receiveShadow>
        <circleGeometry args={[6, 64]} />
        <meshStandardMaterial color={isDark ? "#0f172a" : "#e2e8f0"} roughness={0.7} metalness={0.02} />
      </mesh>
      {/* Grid */}
      <gridHelper args={[12, 12, isDark ? "#334155" : "#c0c8d4", isDark ? "#1e293b" : "#d4dbe6"]} position={[0, 0.01, 0]} />
    </group>
  );
}

/** Conference podium at center-front */
function ConferencePodium({ theme }: { theme: ThemeMode }) {
  const isDark = theme === "dark";
  return (
    <group position={[0, 0, 1.5]}>
      {/* Podium base */}
      <mesh position={[0, 0.2, 0]} castShadow>
        <boxGeometry args={[0.8, 0.4, 0.5]} />
        <meshStandardMaterial color={isDark ? "#475569" : "#94a3b8"} roughness={0.6} />
      </mesh>
      {/* Podium top */}
      <mesh position={[0, 0.42, 0]} castShadow>
        <boxGeometry args={[0.9, 0.04, 0.55]} />
        <meshStandardMaterial color={isDark ? "#334155" : "#64748b"} roughness={0.4} metalness={0.2} />
      </mesh>
    </group>
  );
}

/** Round table for workshop / longitudinal */
function RoundTable({ theme }: { theme: ThemeMode }) {
  const isDark = theme === "dark";
  return (
    <group position={[0, 0, 0]}>
      {/* Table top */}
      <mesh position={[0, 0.4, 0]} castShadow>
        <cylinderGeometry args={[1.2, 1.2, 0.06, 32]} />
        <meshStandardMaterial color={isDark ? "#475569" : "#94a3b8"} roughness={0.5} metalness={0.1} />
      </mesh>
      {/* Table leg */}
      <mesh position={[0, 0.2, 0]} castShadow>
        <cylinderGeometry args={[0.15, 0.2, 0.37, 16]} />
        <meshStandardMaterial color={isDark ? "#334155" : "#64748b"} roughness={0.5} metalness={0.3} />
      </mesh>
    </group>
  );
}

/** Rectangular table for peer review */
function LongTable({ theme }: { theme: ThemeMode }) {
  const isDark = theme === "dark";
  return (
    <group position={[0, 0, 0]}>
      {/* Table top */}
      <mesh position={[0, 0.38, 0]} castShadow>
        <boxGeometry args={[4, 0.06, 1]} />
        <meshStandardMaterial color={isDark ? "#475569" : "#94a3b8"} roughness={0.5} metalness={0.1} />
      </mesh>
      {/* Legs */}
      {[[-1.7, 0, -0.35], [-1.7, 0, 0.35], [1.7, 0, -0.35], [1.7, 0, 0.35]].map((pos, i) => (
        <mesh key={i} position={[pos[0], 0.19, pos[2]]} castShadow>
          <boxGeometry args={[0.08, 0.38, 0.08]} />
          <meshStandardMaterial color={isDark ? "#334155" : "#64748b"} roughness={0.5} metalness={0.3} />
        </mesh>
      ))}
    </group>
  );
}

/** Center divider line for adversarial format */
function AdversarialDivider({ theme }: { theme: ThemeMode }) {
  const isDark = theme === "dark";

  return (
    <group>
      {/* Floor divider line (thin box) */}
      <mesh position={[0, 0.03, 0]}>
        <boxGeometry args={[0.04, 0.02, 8]} />
        <meshStandardMaterial color={isDark ? "#475569" : "#94a3b8"} />
      </mesh>
      {/* VS marker */}
      <mesh position={[0, 0.15, 0]}>
        <boxGeometry args={[0.6, 0.3, 0.6]} />
        <meshStandardMaterial
          color={isDark ? "#dc2626" : "#ef4444"}
          emissive={isDark ? "#dc2626" : "#ef4444"}
          emissiveIntensity={0.3}
          transparent
          opacity={0.8}
        />
      </mesh>
    </group>
  );
}

interface DebateEnvironment3DProps {
  theme?: ThemeMode;
  format: DiscussionFormat;
}

export function DebateEnvironment3D({ theme = "dark", format }: DebateEnvironment3DProps) {
  return (
    <group>
      <DebateLighting theme={theme} />
      <ArenaFloor theme={theme} />

      {/* Format-specific furniture */}
      {format === "conference" && <ConferencePodium theme={theme} />}
      {(format === "workshop" || format === "longitudinal") && <RoundTable theme={theme} />}
      {format === "peer_review" && <LongTable theme={theme} />}
      {format === "adversarial" && <AdversarialDivider theme={theme} />}
    </group>
  );
}
