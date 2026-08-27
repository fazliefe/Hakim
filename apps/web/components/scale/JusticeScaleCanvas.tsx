"use client";

import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, OrbitControls, Sparkles, Text } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

type DragSide = "left" | "right" | "beam" | null;
export type SceneTheme = "dark" | "light";

type Props = {
  size?: "hero" | "compact";
  onBiasChange?: (bias: number) => void;
  scrollProgress?: number;
  theme?: SceneTheme;
};

const orbitGate = { allowed: true };

// ---------------------------------------------------------------------------
// Tema paleti
//
// Gece: mumla/meşaleyle aydınlanmış, mermer bir adalet salonu — koyu lacivert-
// siyah taş, altın yaldız, sıcak/soğuk kontrast spot ışıkları, tozlu karanlık.
// Gündüz: AYNI salon — aynı sütunlar, aynı terazi, aynı ADALET kemeri — ama
// öğle güneşiyle dolu: sıcak traverten/fildişi taş, bronzlaşmış altın, tek
// baskın güneş ışığı + sıcak dolgu (soğuk mavi ton YOK, gece'deki ay ışığı
// hissi yerine gün ışığının netliği/şeffaflığı).
// ---------------------------------------------------------------------------

type ScenePalette = {
  bg: string;
  gold: string;
  goldWarm: string;
  goldPale: string;
  goldMuted: string;
  steel: string;
  sun: string;
  fill: string;
  spot1: string;
  spot2: string;
  hazeWarm: string;
  hazeCool: string;
  envA: string;
  envB: string;
  sparkle: string;
  shadowColor: string;
  ambientIntensity: number;
  fillIntensity: number;
  bloomThreshold: number;
  bloomIntensity: number;
  bloomSmoothing: number;
};

const PALETTE: Record<SceneTheme, ScenePalette> = {
  dark: {
    bg: "#07090f",
    gold: "#d4af37",
    goldWarm: "#e8c56a",
    goldPale: "#f4e4bc",
    goldMuted: "#c9b37a",
    steel: "#c5cdd8",
    sun: "#fff3dc",
    fill: "#9aacd0",
    spot1: "#f3e0b8",
    spot2: "#f0d7a0",
    hazeWarm: "#f0d48a",
    hazeCool: "#c5d4f0",
    envA: "#a8b8d4",
    envB: "#e8d5a4",
    sparkle: "#e8c56a",
    shadowColor: "#000000",
    ambientIntensity: 0.32,
    fillIntensity: 0.45,
    bloomThreshold: 0.22,
    bloomIntensity: 0.65,
    bloomSmoothing: 0.3,
  },
  light: {
    bg: "#ece1c9",
    gold: "#a8781f",
    goldWarm: "#c99a3c",
    goldPale: "#fff3da",
    goldMuted: "#8f7038",
    steel: "#97a0a6",
    sun: "#fff8ea",
    fill: "#e9d9b8",
    spot1: "#fff0d2",
    spot2: "#ffe9bd",
    hazeWarm: "#fff2d6",
    hazeCool: "#f3e6c8",
    envA: "#e6d6ae",
    envB: "#f2e2b8",
    sparkle: "#fff2d6",
    shadowColor: "#5c4526",
    ambientIntensity: 0.62,
    fillIntensity: 0.3,
    bloomThreshold: 0.78,
    bloomIntensity: 0.35,
    bloomSmoothing: 0.25,
  },
};

// Taş/mermer yüzeylerin tek tek ayarlanmış tonları — gece'deki koyu
// lacivert-siyah varyasyonların her biri, gündüz'de aynı bağıl derinlik
// hissini koruyan bir traverten/fildişi tonuna eşleniyor.
const STONE_MAP: Record<string, string> = {
  "#171a22": "#d8c9a5",
  "#14171f": "#d3c39a",
  "#1b1f28": "#e0d2b0",
  "#0a0c13": "#d9c9a4",
  "#151820": "#cdbd90",
  "#141820": "#d0c093",
  "#1b202b": "#e3d5b5",
  "#12151c": "#c9b98b",
  "#171b24": "#d4c49a",
  "#10131a": "#c6b586",
  "#151821": "#cebe91",
  "#2a2418": "#b9995c",
  "#1e2430": "#c7ad78",
  "#161a22": "#c3b384",
  "#0c0b10": "#cfbf94",
  "#0b0d14": "#d6c6a0",
  "#2c2416": "#b28f52",
};

const ScenePaletteContext = createContext<{ theme: SceneTheme; palette: ScenePalette; stone: (hex: string) => string }>(
  {
    theme: "dark",
    palette: PALETTE.dark,
    stone: (hex) => hex,
  }
);

function useScenePalette() {
  return useContext(ScenePaletteContext);
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(media.matches);
    sync();
    media.addEventListener("change", sync);
    return () => media.removeEventListener("change", sync);
  }, []);
  return reduced;
}

function GoldMaterial({ roughness = 0.22, metalness = 1 }: { roughness?: number; metalness?: number }) {
  const { palette } = useScenePalette();
  return (
    <meshStandardMaterial color={palette.gold} metalness={metalness} roughness={roughness} envMapIntensity={1.25} />
  );
}

function SteelMaterial() {
  const { palette } = useScenePalette();
  return <meshStandardMaterial color={palette.steel} metalness={0.92} roughness={0.28} envMapIntensity={1} />;
}

function StoneMaterial({ color = "#171a22" }: { color?: string }) {
  const { stone } = useScenePalette();
  return <meshStandardMaterial color={stone(color)} roughness={0.72} metalness={0.18} envMapIntensity={0.45} />;
}

function Column({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.1, 0]} castShadow>
        <cylinderGeometry args={[0.3, 0.34, 0.2, 20]} />
        <StoneMaterial color="#14171f" />
      </mesh>
      <mesh position={[0, 1.55, 0]} castShadow>
        <cylinderGeometry args={[0.155, 0.175, 2.7, 20]} />
        <StoneMaterial />
      </mesh>
      <mesh position={[0, 2.95, 0]} castShadow>
        <cylinderGeometry args={[0.26, 0.2, 0.16, 20]} />
        <StoneMaterial color="#1b1f28" />
      </mesh>
      <mesh position={[0, 0.22, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.22, 0.012, 10, 28]} />
        <GoldMaterial roughness={0.28} />
      </mesh>
      <mesh position={[0, 2.86, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.2, 0.01, 10, 28]} />
        <GoldMaterial roughness={0.28} />
      </mesh>
    </group>
  );
}

function DistantHalo({ reducedMotion }: { reducedMotion: boolean }) {
  const { palette } = useScenePalette();
  const ref = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (reducedMotion || !ref.current) return;
    ref.current.rotation.z += dt * 0.025;
  });
  return (
    <group ref={ref} position={[-0.45, 1.2, -4.6]}>
      <mesh>
        <torusGeometry args={[1.9, 0.012, 12, 96]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.22} envMapIntensity={1.5} />
      </mesh>
      <mesh>
        <torusGeometry args={[1.52, 0.006, 12, 96]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.28} transparent opacity={0.5} />
      </mesh>
      <mesh>
        <ringGeometry args={[0.35, 0.72, 48]} />
        <meshBasicMaterial color={palette.gold} transparent opacity={0.07} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}

function ChamberBackdrop({ reducedMotion }: { reducedMotion: boolean }) {
  const { palette, stone } = useScenePalette();
  return (
    <group>
      <mesh position={[0, 2.8, 0]}>
        <cylinderGeometry args={[12.5, 12.5, 8.4, 48, 1, true]} />
        <meshStandardMaterial color={stone("#0a0c13")} roughness={0.92} metalness={0.08} side={THREE.BackSide} />
      </mesh>
      <Column position={[-3.15, 0, -2.55]} />
      <Column position={[2.55, 0, -2.9]} />
      <Column position={[-1.7, 0, -4.1]} />
      <InscribedPanel position={[-3.55, 1.55, -3.15]} rotation={[0, 0.55, 0]} title="ANAYASA" opacity={0.92} />
      <InscribedPanel position={[2.95, 1.58, -3.45]} rotation={[0, -0.48, 0]} title="HUKUK" opacity={0.92} />
      <mesh position={[-1.4, 4.4, -3.2]} rotation={[0.55, 0.15, -0.18]}>
        <planeGeometry args={[1.6, 7.5]} />
        <meshBasicMaterial color={palette.goldWarm} transparent opacity={0.05} depthWrite={false} />
      </mesh>
      <mesh position={[1.1, 4.2, -3.6]} rotation={[0.5, -0.2, 0.12]}>
        <planeGeometry args={[1.2, 6.8]} />
        <meshBasicMaterial color={palette.hazeCool} transparent opacity={0.04} depthWrite={false} />
      </mesh>
      {[1.55, 2.35, 3.35].map((radius) => (
        <mesh key={radius} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.014, 0]}>
          <torusGeometry args={[radius, 0.01, 8, 80]} />
          <GoldMaterial roughness={0.32} />
        </mesh>
      ))}
      {Array.from({ length: 12 }, (_, index) => {
        const angle = (index / 12) * Math.PI * 2;
        return (
          <mesh
            key={`tick-${index}`}
            position={[Math.cos(angle) * 3.35, 0.02, Math.sin(angle) * 3.35]}
            rotation={[0, -angle, 0]}
          >
            <boxGeometry args={[0.12, 0.012, 0.04]} />
            <GoldMaterial roughness={0.3} />
          </mesh>
        );
      })}
      <mesh position={[0, 2.12, 0]}>
        <cylinderGeometry args={[12.42, 12.42, 0.22, 48, 1, true]} />
        <meshStandardMaterial color={stone("#151820")} roughness={0.8} metalness={0.12} side={THREE.BackSide} />
      </mesh>
      <mesh position={[0, 2.0, 0]}>
        <cylinderGeometry args={[12.38, 12.38, 0.02, 48, 1, true]} />
        <meshStandardMaterial color={palette.gold} roughness={0.3} metalness={1} side={THREE.BackSide} />
      </mesh>
      <DistantHalo reducedMotion={reducedMotion} />
      {!reducedMotion ? (
        <Sparkles
          count={36}
          scale={[11, 4.5, 7]}
          size={1.6}
          speed={0.12}
          opacity={0.28}
          color={palette.sparkle}
          position={[-0.4, 1.7, -2.2]}
        />
      ) : null}
    </group>
  );
}

function HallLantern({ position }: { position: [number, number, number] }) {
  const { palette } = useScenePalette();
  return (
    <group position={position}>
      <mesh position={[0, 0.42, 0]}>
        <cylinderGeometry args={[0.007, 0.007, 0.72, 8]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.048, 16, 16]} />
        <meshBasicMaterial color={palette.goldPale} transparent opacity={0.9} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.16, 16, 16]} />
        <meshBasicMaterial color={palette.goldWarm} transparent opacity={0.07} depthWrite={false} />
      </mesh>
      <mesh position={[0, -0.07, 0]}>
        <coneGeometry args={[0.055, 0.08, 8]} />
        <GoldMaterial roughness={0.26} />
      </mesh>
    </group>
  );
}

function InscribedPanel({
  position,
  rotation,
  title,
  opacity = 1,
  width = 0.78,
  height = 1.12,
}: {
  position: [number, number, number];
  rotation: [number, number, number];
  title: string;
  opacity?: number;
  width?: number;
  height?: number;
}) {
  const { palette, stone } = useScenePalette();
  const lines = [0.82, 0.7, 0.76, 0.52, 0.68, 0.44, 0.6];
  return (
    <group position={position} rotation={rotation}>
      <mesh castShadow>
        <boxGeometry args={[width + 0.08, height + 0.1, 0.05]} />
        <meshStandardMaterial color={stone("#141820")} roughness={0.74} metalness={0.16} />
      </mesh>
      <mesh position={[0, 0, 0.028]}>
        <planeGeometry args={[width, height]} />
        <meshStandardMaterial color={stone("#1b202b")} roughness={0.62} metalness={0.22} transparent opacity={opacity} />
      </mesh>
      <mesh position={[0, height * 0.28, 0.032]}>
        <planeGeometry args={[width * 0.72, 0.012]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.28} transparent opacity={opacity} />
      </mesh>
      <Text
        position={[0, height * 0.36, 0.034]}
        fontSize={0.078}
        color={palette.gold}
        anchorX="center"
        anchorY="middle"
        letterSpacing={0.18}
        fillOpacity={0.35 + opacity * 0.55}
      >
        {title}
      </Text>
      {lines.map((span, index) => (
        <mesh key={index} position={[-(width * 0.32) + span * width * 0.18, height * 0.12 - index * 0.085, 0.034]}>
          <planeGeometry args={[width * span * 0.55, 0.012]} />
          <meshStandardMaterial
            color={palette.goldMuted}
            metalness={0.45}
            roughness={0.4}
            transparent
            opacity={0.25 + opacity * 0.45}
          />
        </mesh>
      ))}
    </group>
  );
}

function MiniScale({ opacity }: { opacity: number }) {
  const { palette } = useScenePalette();
  return (
    <group>
      <mesh position={[0, 0.028, 0]} rotation={[0, 0, Math.PI / 2]}>
        <cylinderGeometry args={[0.01, 0.01, 0.5, 8]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.25} transparent opacity={opacity} />
      </mesh>
      <mesh position={[0, 0.028, 0.01]}>
        <boxGeometry args={[0.02, 0.014, 0.14]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.25} transparent opacity={opacity} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.25, 0.026, 0]}>
        <circleGeometry args={[0.065, 16]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.28} transparent opacity={opacity} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0.25, 0.026, 0]}>
        <circleGeometry args={[0.065, 16]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.28} transparent opacity={opacity} />
      </mesh>
    </group>
  );
}

function FloorCompass({ opacity }: { opacity: number }) {
  const { palette, stone } = useScenePalette();
  const labels = [
    { text: "HUKUK", angle: 0 },
    { text: "KANUN", angle: Math.PI / 2 },
    { text: "ADALET", angle: Math.PI },
    { text: "VİCDAN", angle: (Math.PI * 3) / 2 },
  ];
  return (
    <group position={[-0.3, 0.02, -5.7]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[1.15, 48]} />
        <meshStandardMaterial color={stone("#12151c")} roughness={0.52} metalness={0.32} />
      </mesh>
      {[0.42, 0.72, 1.08].map((radius) => (
        <mesh key={radius} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.004, 0]}>
          <ringGeometry args={[radius, radius + 0.025, 64]} />
          <meshStandardMaterial
            color={palette.gold}
            metalness={1}
            roughness={0.26}
            transparent
            opacity={opacity * (radius === 0.72 ? 0.85 : 0.55)}
          />
        </mesh>
      ))}
      {Array.from({ length: 8 }, (_, index) => {
        const angle = (index / 8) * Math.PI * 2;
        return (
          <mesh
            key={index}
            rotation={[-Math.PI / 2, 0, angle]}
            position={[Math.cos(angle) * 0.75, 0.006, Math.sin(angle) * 0.75]}
          >
            <planeGeometry args={[0.018, 0.55]} />
            <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.28} transparent opacity={opacity * 0.7} />
          </mesh>
        );
      })}
      {Array.from({ length: 16 }, (_, index) => {
        const angle = (index / 16) * Math.PI * 2;
        return (
          <mesh
            key={`key-${index}`}
            position={[Math.cos(angle) * 1.05, 0.008, Math.sin(angle) * 1.05]}
            rotation={[0, -angle, 0]}
          >
            <boxGeometry args={[0.07, 0.012, 0.07]} />
            <GoldMaterial roughness={0.3} />
          </mesh>
        );
      })}
      <MiniScale opacity={opacity} />
      {labels.map((item) => (
        <Text
          key={item.text}
          position={[Math.sin(item.angle) * 0.88, 0.03, Math.cos(item.angle) * 0.88]}
          rotation={[-Math.PI / 2, 0, item.angle]}
          fontSize={0.07}
          color={palette.gold}
          anchorX="center"
          anchorY="middle"
          letterSpacing={0.16}
          fillOpacity={opacity * 0.85}
        >
          {item.text}
        </Text>
      ))}
    </group>
  );
}

function Frieze({ position, width, opacity }: { position: [number, number, number]; width: number; opacity: number }) {
  const { palette } = useScenePalette();
  const count = 9;
  const words = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"];
  return (
    <group position={position}>
      {Array.from({ length: count }, (_, index) => {
        const x = (index - (count - 1) / 2) * (width / count);
        return (
          <group key={index} position={[x, 0, 0]}>
            <mesh>
              <boxGeometry args={[0.22, 0.16, 0.06]} />
              <StoneMaterial color="#171b24" />
            </mesh>
            <Text
              position={[0, 0, 0.04]}
              fontSize={0.05}
              color={palette.gold}
              anchorX="center"
              anchorY="middle"
              fillOpacity={0.3 + opacity * 0.55}
            >
              {words[index]}
            </Text>
          </group>
        );
      })}
    </group>
  );
}

function Drape({
  position,
  rotation = [0, 0, 0],
  opacity,
}: {
  position: [number, number, number];
  rotation?: [number, number, number];
  opacity: number;
}) {
  const { palette, stone } = useScenePalette();
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <planeGeometry args={[0.92, 2.15]} />
        <meshStandardMaterial
          color={stone("#10131a")}
          roughness={0.92}
          metalness={0.08}
          transparent
          opacity={opacity}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh position={[0, 1.08, 0]}>
        <boxGeometry args={[0.96, 0.03, 0.03]} />
        <GoldMaterial roughness={0.28} />
      </mesh>
      <mesh position={[0, -1.06, 0]}>
        <boxGeometry args={[0.9, 0.018, 0.018]} />
        <GoldMaterial roughness={0.32} />
      </mesh>
      <mesh position={[0, 0.18, 0.01]}>
        <circleGeometry args={[0.11, 24]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.28} transparent opacity={opacity * 0.7} />
      </mesh>
      <Text
        position={[0, -0.22, 0.02]}
        fontSize={0.055}
        color={palette.gold}
        anchorX="center"
        anchorY="middle"
        letterSpacing={0.2}
        fillOpacity={opacity * 0.7}
      >
        HÂKİM
      </Text>
    </group>
  );
}

function BookPlinth({
  position,
  rotation = [0, 0, 0],
}: {
  position: [number, number, number];
  rotation?: [number, number, number];
}) {
  const { stone } = useScenePalette();
  return (
    <group position={position} rotation={rotation}>
      <mesh castShadow>
        <boxGeometry args={[0.42, 0.28, 0.32]} />
        <StoneMaterial color="#151820" />
      </mesh>
      <mesh position={[0, 0.155, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.14, 0.008, 8, 24]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <mesh position={[0.03, 0.18, 0.01]} rotation={[0, 0.12, 0]} castShadow>
        <boxGeometry args={[0.24, 0.045, 0.16]} />
        <GoldMaterial roughness={0.36} />
      </mesh>
      <mesh position={[-0.04, 0.23, 0.02]} rotation={[0, -0.22, 0]} castShadow>
        <boxGeometry args={[0.22, 0.038, 0.15]} />
        <meshStandardMaterial color={stone("#2a2418")} roughness={0.68} metalness={0.2} />
      </mesh>
      <mesh position={[0.01, 0.275, -0.01]} rotation={[0, 0.08, 0]} castShadow>
        <boxGeometry args={[0.2, 0.032, 0.13]} />
        <meshStandardMaterial color={stone("#1e2430")} roughness={0.62} metalness={0.25} />
      </mesh>
    </group>
  );
}

function Urn({ position }: { position: [number, number, number] }) {
  const { palette } = useScenePalette();
  return (
    <group position={position}>
      <mesh position={[0, 0.08, 0]} castShadow>
        <cylinderGeometry args={[0.13, 0.16, 0.16, 16]} />
        <StoneMaterial color="#171b24" />
      </mesh>
      <mesh position={[0, 0.2, 0]} castShadow>
        <cylinderGeometry args={[0.07, 0.11, 0.12, 16]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.32, 0]}>
        <sphereGeometry args={[0.055, 14, 14]} />
        <meshBasicMaterial color={palette.goldPale} transparent opacity={0.55} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.14, 14, 14]} />
        <meshBasicMaterial color={palette.goldWarm} transparent opacity={0.06} depthWrite={false} />
      </mesh>
    </group>
  );
}

function RevealHall({ progress, reducedMotion }: { progress: number; reducedMotion: boolean }) {
  const { palette, stone } = useScenePalette();
  const mid = THREE.MathUtils.smoothstep(progress, 0.05, 0.36);
  const deep = THREE.MathUtils.smoothstep(progress, 0.28, 0.72);
  const far = THREE.MathUtils.smoothstep(progress, 0.55, 0.92);
  if (mid < 0.02) return null;

  return (
    <group>
      <Column position={[-4.15, 0, -4.55]} />
      <Column position={[3.55, 0, -4.75]} />
      <Column position={[-4.55, 0, -6.35]} />
      <Column position={[3.95, 0, -6.55]} />
      <Column position={[-3.35, 0, -8.05]} />
      <Column position={[2.75, 0, -8.2]} />
      <Column position={[-0.35, 0, -8.55]} />

      <mesh position={[-0.3, 3.08, -6.45]}>
        <boxGeometry args={[8.6, 0.16, 0.32]} />
        <StoneMaterial color="#151821" />
      </mesh>
      <mesh position={[-0.3, 2.98, -6.45]}>
        <boxGeometry args={[8.6, 0.028, 0.34]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <Frieze position={[-0.3, 2.82, -6.28]} width={6.4} opacity={mid} />
      <mesh position={[-0.3, 3.18, -8.05]}>
        <boxGeometry args={[6.8, 0.14, 0.28]} />
        <StoneMaterial color="#14171f" />
      </mesh>
      <mesh position={[-2.4, 3.12, -5.4]} rotation={[0, 0.12, 0.18]}>
        <boxGeometry args={[0.05, 0.05, 3.6]} />
        <GoldMaterial roughness={0.28} />
      </mesh>
      <mesh position={[1.85, 3.16, -5.55]} rotation={[0, -0.1, -0.16]}>
        <boxGeometry args={[0.05, 0.05, 3.4]} />
        <GoldMaterial roughness={0.28} />
      </mesh>

      <mesh position={[-0.3, 2.62, -8.35]} rotation={[0, 0, 0]}>
        <torusGeometry args={[1.85, 0.04, 12, 64, Math.PI]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.22} transparent opacity={0.2 + deep * 0.75} />
      </mesh>
      <mesh position={[-0.3, 3.52, -8.38]} rotation={[Math.PI / 2, 0, Math.PI]}>
        <coneGeometry args={[1.62, 0.1, 3]} />
        <StoneMaterial color="#161a22" />
      </mesh>
      <mesh position={[-0.3, 2.72, -8.32]}>
        <ringGeometry args={[0.55, 1.55, 64]} />
        <meshBasicMaterial
          color={palette.gold}
          transparent
          opacity={0.03 + far * 0.14}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <Text
        position={[-0.3, 3.42, -8.18]}
        fontSize={0.13}
        color={palette.gold}
        anchorX="center"
        anchorY="middle"
        letterSpacing={0.42}
        fillOpacity={0.15 + far * 0.7}
      >
        ADALET
      </Text>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.3, 0.017, -4.9]}>
        <planeGeometry args={[0.38, 7.4]} />
        <meshStandardMaterial
          color={stone("#2c2416")}
          metalness={0.35}
          roughness={0.48}
          transparent
          opacity={0.22 + deep * 0.45}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.3, 0.019, -4.9]}>
        <planeGeometry args={[0.055, 7.4]} />
        <meshStandardMaterial
          color={palette.gold}
          metalness={1}
          roughness={0.28}
          transparent
          opacity={0.18 + deep * 0.55}
        />
      </mesh>

      <FloorCompass opacity={0.35 + mid * 0.65} />

      {[0, 1, 2].map((step) => (
        <mesh key={step} position={[-0.3, 0.05 + step * 0.075, -7.15 + step * 0.32]} castShadow receiveShadow>
          <boxGeometry args={[2.9 - step * 0.35, 0.08, 0.36]} />
          <StoneMaterial color="#141820" />
        </mesh>
      ))}
      <mesh position={[-0.3, 0.085, -7.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[2.7, 0.04]} />
        <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.3} transparent opacity={0.35 + far * 0.5} />
      </mesh>

      {[4.15, 5.35, 6.7].map((radius) => (
        <mesh key={radius} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.016, -1.4]}>
          <torusGeometry args={[radius, 0.01, 8, 96]} />
          <meshStandardMaterial color={palette.gold} metalness={1} roughness={0.32} transparent opacity={0.15 + mid * 0.7} />
        </mesh>
      ))}

      <InscribedPanel position={[-3.55, 1.62, -5.85]} rotation={[0, 0.52, 0]} title="CEZA" opacity={0.45 + mid * 0.55} />
      <InscribedPanel position={[3.05, 1.68, -6.05]} rotation={[0, -0.48, 0]} title="MEDENİ" opacity={0.45 + mid * 0.55} />
      <InscribedPanel position={[-3.85, 1.72, -7.55]} rotation={[0, 0.38, 0]} title="İDARE" opacity={0.4 + deep * 0.6} />
      <InscribedPanel position={[3.25, 1.78, -7.7]} rotation={[0, -0.34, 0]} title="USUL" opacity={0.4 + deep * 0.6} />
      <InscribedPanel
        position={[-0.3, 1.55, -8.72]}
        rotation={[0, 0, 0]}
        title="ANAYASA"
        opacity={0.35 + far * 0.65}
        width={1.15}
        height={1.55}
      />

      <Drape position={[-3.85, 1.55, -5.35]} rotation={[0, 0.55, 0]} opacity={0.35 + mid * 0.55} />
      <Drape position={[3.35, 1.58, -5.55]} rotation={[0, -0.5, 0]} opacity={0.35 + mid * 0.55} />
      <BookPlinth position={[-2.55, 0.14, -4.85]} rotation={[0, 0.35, 0]} />
      <BookPlinth position={[2.15, 0.14, -5.05]} rotation={[0, -0.4, 0]} />
      <Urn position={[-1.55, 0.28, -7.85]} />
      <Urn position={[0.95, 0.28, -8.0]} />

      <HallLantern position={[-2.15, 2.55, -5.2]} />
      <HallLantern position={[1.75, 2.62, -5.45]} />
      <HallLantern position={[-2.45, 2.7, -7.15]} />
      <HallLantern position={[1.95, 2.74, -7.35]} />
      <HallLantern position={[-1.15, 2.82, -8.05]} />
      <HallLantern position={[0.55, 2.84, -8.15]} />

      <mesh position={[-2.4, 5.4, -5.4]} rotation={[0.62, 0.1, -0.14]}>
        <planeGeometry args={[2.4, 10]} />
        <meshBasicMaterial color={palette.hazeWarm} transparent opacity={0.03 + deep * 0.09} depthWrite={false} />
      </mesh>
      <mesh position={[1.9, 5.25, -5.8]} rotation={[0.58, -0.18, 0.1]}>
        <planeGeometry args={[1.9, 9]} />
        <meshBasicMaterial color={palette.hazeCool} transparent opacity={0.025 + deep * 0.07} depthWrite={false} />
      </mesh>

      <pointLight position={[-0.3, 3.4, -6.2]} color={palette.spot2} intensity={deep * 2.8} distance={14} />
      <spotLight position={[-0.3, 5.6, -3.8]} intensity={far * 3.2} angle={0.46} penumbra={0.92} color={palette.spot1} />

      {!reducedMotion && deep > 0.12 ? (
        <Sparkles
          count={48}
          scale={[12, 5, 9]}
          size={1.8}
          speed={0.14}
          opacity={0.16 + deep * 0.28}
          color={palette.sparkle}
          position={[-0.3, 2.4, -5.4]}
        />
      ) : null}
    </group>
  );
}

function AtmosphereDirector({ progress, compact }: { progress: number; compact: boolean }) {
  const { scene } = useThree();
  useFrame((_, dt) => {
    const fog = scene.fog;
    if (!(fog instanceof THREE.Fog)) return;
    const t = compact ? 0 : progress;
    fog.near = THREE.MathUtils.damp(fog.near, 11 - t * 4.5, 3.2, dt);
    fog.far = THREE.MathUtils.damp(fog.far, 22 + t * 16, 3.2, dt);
  });
  return null;
}

function ScrollDirector({ progress, compact }: { progress: number; compact: boolean }) {
  const { camera } = useThree();
  const smoothed = useRef(0);
  const look = useRef(new THREE.Vector3(-0.55, 0.72, 0));
  const cam = camera as THREE.PerspectiveCamera;
  const camPath = useMemo(
    () =>
      new THREE.CatmullRomCurve3(
        [
          new THREE.Vector3(1.7, 1.35, 5.0),
          new THREE.Vector3(2.2, 1.58, 6.25),
          new THREE.Vector3(0.45, 2.25, 7.55),
          new THREE.Vector3(-2.55, 2.7, 6.85),
          new THREE.Vector3(0.15, 3.15, 8.55),
        ],
        false,
        "catmullrom",
        0.32
      ),
    []
  );
  const lookPath = useMemo(
    () =>
      new THREE.CatmullRomCurve3(
        [
          new THREE.Vector3(-0.55, 0.72, 0),
          new THREE.Vector3(-0.4, 0.98, -1.9),
          new THREE.Vector3(-0.2, 1.38, -4.4),
          new THREE.Vector3(0.1, 1.58, -6.1),
          new THREE.Vector3(-0.2, 1.78, -7.2),
        ],
        false,
        "catmullrom",
        0.32
      ),
    []
  );

  useFrame((_, dt) => {
    const goal = compact ? 0 : progress;
    smoothed.current = THREE.MathUtils.damp(smoothed.current, goal, 3.2, dt);
    const heroFov = compact ? 36 : 30;
    if (smoothed.current < 0.012) {
      cam.fov = THREE.MathUtils.damp(cam.fov, heroFov, 4, dt);
      cam.updateProjectionMatrix();
      return;
    }
    const t = THREE.MathUtils.clamp(smoothed.current, 0, 1);
    cam.position.lerp(camPath.getPoint(t), 0.16);
    look.current.lerp(lookPath.getPoint(t), 0.16);
    cam.lookAt(look.current);
    cam.fov = THREE.MathUtils.lerp(heroFov, 34, t);
    cam.updateProjectionMatrix();
  });
  return null;
}

function SceneOrbit({
  compact,
  reducedMotion,
  scrollProgress,
}: {
  compact: boolean;
  reducedMotion: boolean;
  scrollProgress: number;
}) {
  const controls = useRef<OrbitControlsImpl>(null);
  useFrame(() => {
    if (!controls.current) return;
    const browsing = scrollProgress > 0.04;
    controls.current.enabled = orbitGate.allowed && !browsing;
    controls.current.autoRotate = !reducedMotion && !browsing;
  });
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enablePan={false}
      enableZoom={false}
      minPolarAngle={Math.PI / 2.85}
      maxPolarAngle={Math.PI / 2.2}
      minAzimuthAngle={compact ? -0.5 : -0.65}
      maxAzimuthAngle={compact ? 0.75 : 0.9}
      minDistance={compact ? 3.2 : 4.6}
      maxDistance={compact ? 4.2 : 5.8}
      autoRotate={!reducedMotion}
      autoRotateSpeed={0.12}
      enableDamping
      dampingFactor={0.08}
      rotateSpeed={0.35}
      target={compact ? [0, 0.72, 0] : [-0.55, 0.72, 0]}
    />
  );
}

function Bowl({ onGrab }: { onGrab?: (e: { clientY: number; clientX: number }) => void }) {
  const points = useMemo(() => {
    const pts: THREE.Vector2[] = [];
    for (let i = 0; i <= 28; i++) {
      const t = i / 28;
      pts.push(new THREE.Vector2(0.02 + Math.sin(t * Math.PI * 0.5) * 0.36, t * t * 0.16));
    }
    pts.push(new THREE.Vector2(0.38, 0.168));
    return pts;
  }, []);

  return (
    <group
      position={[0, -0.17, 0]}
      onPointerDown={(e) => {
        e.stopPropagation();
        onGrab?.({ clientX: e.clientX, clientY: e.clientY });
      }}
    >
      <mesh castShadow receiveShadow>
        <latheGeometry args={[points, 64]} />
        <GoldMaterial roughness={0.2} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.155, 0]} castShadow>
        <torusGeometry args={[0.365, 0.014, 12, 64]} />
        <GoldMaterial roughness={0.08} />
      </mesh>
    </group>
  );
}

function Rod({
  from,
  to,
  radius = 0.012,
}: {
  from: [number, number, number];
  to: [number, number, number];
  radius?: number;
}) {
  const { position, quaternion, length } = useMemo(() => {
    const start = new THREE.Vector3(...from);
    const end = new THREE.Vector3(...to);
    const direction = end.clone().sub(start);
    const length = Math.max(direction.length(), 0.01);
    const mid = start.clone().add(end).multiplyScalar(0.5);
    const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
    return { position: mid.toArray() as [number, number, number], quaternion, length };
  }, [from, to]);

  return (
    <mesh position={position} quaternion={quaternion} castShadow>
      <cylinderGeometry args={[radius, radius, length, 12]} />
      <GoldMaterial roughness={0.24} />
    </mesh>
  );
}

function HangAssembly() {
  const rim = 0.35;
  const bottom = -0.58;
  const points: [number, number, number][] = [
    [rim, bottom, 0],
    [-rim * 0.5, bottom, rim * 0.866],
    [-rim * 0.5, bottom, -rim * 0.866],
  ];

  return (
    <group>
      <mesh position={[0, 0.02, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <torusGeometry args={[0.048, 0.011, 12, 28]} />
        <GoldMaterial roughness={0.2} />
      </mesh>
      <mesh position={[0, -0.03, 0]} castShadow>
        <sphereGeometry args={[0.018, 16, 16]} />
        <GoldMaterial roughness={0.2} />
      </mesh>
      {points.map((point, index) => (
        <Rod key={index} from={[0, -0.04, 0]} to={point} radius={0.011} />
      ))}
    </group>
  );
}

function ScaleModel({ onBiasChange }: { onBiasChange?: (bias: number) => void }) {
  const { palette, stone } = useScenePalette();
  const beamRef = useRef<THREE.Group>(null);
  const leftHang = useRef<THREE.Group>(null);
  const rightHang = useRef<THREE.Group>(null);
  const tilt = useRef(0);
  const vel = useRef(0);
  const drag = useRef<DragSide>(null);
  const startY = useRef(0);
  const startTilt = useRef(0);
  const startX = useRef(0);
  const bias = useRef(onBiasChange);
  bias.current = onBiasChange;

  useFrame((state, dt) => {
    const clampedDt = Math.min(dt, 0.033);
    if (!drag.current) {
      vel.current += -tilt.current * 10 * clampedDt;
      vel.current *= Math.exp(-5 * clampedDt);
      tilt.current += vel.current * clampedDt;
      tilt.current += Math.sin(state.clock.elapsedTime * 0.55) * 0.0008;
    }
    const angle = THREE.MathUtils.clamp(tilt.current, -1, 1) * 0.32;
    if (beamRef.current) beamRef.current.rotation.z = angle;
    if (leftHang.current) leftHang.current.rotation.z = -angle;
    if (rightHang.current) rightHang.current.rotation.z = -angle;
  });

  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!drag.current) return;
      if (drag.current === "beam") {
        tilt.current = THREE.MathUtils.clamp(startTilt.current + (e.clientX - startX.current) / 260, -1, 1);
      } else {
        const dy = (e.clientY - startY.current) / 180;
        tilt.current = THREE.MathUtils.clamp(
          drag.current === "left" ? startTilt.current + dy : startTilt.current - dy,
          -1,
          1
        );
      }
    }
    function onUp() {
      if (!drag.current) return;
      drag.current = null;
      orbitGate.allowed = true;
      document.body.style.cursor = "";
      bias.current?.(tilt.current);
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);

  function begin(side: Exclude<DragSide, null>, clientX: number, clientY: number) {
    drag.current = side;
    orbitGate.allowed = false;
    startX.current = clientX;
    startY.current = clientY;
    startTilt.current = tilt.current;
    vel.current = 0;
    document.body.style.cursor = "grabbing";
  }

  const arm = 1.08;

  return (
    <group>
      <mesh position={[0, 0.045, 0]} receiveShadow>
        <cylinderGeometry args={[0.64, 0.7, 0.09, 64]} />
        <meshStandardMaterial color={stone("#0c0b10")} metalness={0.72} roughness={0.28} envMapIntensity={1.1} />
      </mesh>
      <mesh position={[0, 0.092, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.58, 0.006, 12, 64]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.16, 0]} castShadow>
        <cylinderGeometry args={[0.36, 0.4, 0.07, 48]} />
        <GoldMaterial roughness={0.32} />
      </mesh>
      <mesh position={[0, 0.76, 0]} castShadow>
        <cylinderGeometry args={[0.055, 0.078, 1.16, 32]} />
        <GoldMaterial roughness={0.26} />
      </mesh>
      <mesh position={[0, 1.32, 0]} castShadow>
        <cylinderGeometry args={[0.07, 0.07, 0.12, 24]} />
        <GoldMaterial roughness={0.22} />
      </mesh>
      <mesh position={[-0.055, 1.34, 0]} rotation={[0, 0, Math.PI / 2]} castShadow>
        <cylinderGeometry args={[0.028, 0.028, 0.14, 16]} />
        <SteelMaterial />
      </mesh>
      <mesh position={[0, 1.46, 0]} castShadow>
        <coneGeometry args={[0.028, 0.16, 4]} />
        <GoldMaterial roughness={0.2} />
      </mesh>

      <group ref={beamRef} position={[0, 1.34, 0]}>
        <mesh
          rotation={[0, 0, Math.PI / 2]}
          castShadow
          onPointerDown={(e) => {
            e.stopPropagation();
            begin("beam", e.clientX, e.clientY);
          }}
        >
          <cylinderGeometry args={[0.036, 0.036, 2.28, 24]} />
          <GoldMaterial roughness={0.22} />
        </mesh>
        <mesh position={[-1.14, 0, 0]} castShadow>
          <sphereGeometry args={[0.048, 24, 24]} />
          <GoldMaterial roughness={0.18} />
        </mesh>
        <mesh position={[1.14, 0, 0]} castShadow>
          <sphereGeometry args={[0.048, 24, 24]} />
          <GoldMaterial roughness={0.18} />
        </mesh>
        <mesh position={[0, 0, 0]} castShadow>
          <sphereGeometry args={[0.055, 24, 24]} />
          <GoldMaterial roughness={0.16} />
        </mesh>
        <mesh position={[-1.08, -0.06, 0]} castShadow>
          <cylinderGeometry args={[0.014, 0.014, 0.08, 12]} />
          <GoldMaterial roughness={0.22} />
        </mesh>
        <mesh position={[1.08, -0.06, 0]} castShadow>
          <cylinderGeometry args={[0.014, 0.014, 0.08, 12]} />
          <GoldMaterial roughness={0.22} />
        </mesh>

        <group position={[-arm, 0, 0]}>
          <group ref={leftHang}>
            <HangAssembly />
            <group position={[0, -0.58, 0]}>
              <Bowl onGrab={(e) => begin("left", e.clientX, e.clientY)} />
              <Text
                position={[0, -0.28, 0.02]}
                fontSize={0.052}
                color={palette.gold}
                anchorX="center"
                anchorY="middle"
                letterSpacing={0.22}
                fillOpacity={0.78}
              >
                KANUN
              </Text>
            </group>
          </group>
        </group>

        <group position={[arm, 0, 0]}>
          <group ref={rightHang}>
            <HangAssembly />
            <group position={[0, -0.58, 0]}>
              <Bowl onGrab={(e) => begin("right", e.clientX, e.clientY)} />
              <Text
                position={[0, -0.28, 0.02]}
                fontSize={0.052}
                color={palette.gold}
                anchorX="center"
                anchorY="middle"
                letterSpacing={0.22}
                fillOpacity={0.78}
              >
                VİCDAN
              </Text>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}

function SceneContent({
  compact,
  reducedMotion,
  journey,
  onBiasChange,
}: {
  compact: boolean;
  reducedMotion: boolean;
  journey: number;
  onBiasChange?: (bias: number) => void;
}) {
  const { theme, palette, stone } = useScenePalette();
  return (
    <>
      <color attach="background" args={[palette.bg]} />
      <fog attach="fog" args={[palette.bg, 11, 22]} />
      <ambientLight intensity={palette.ambientIntensity} />
      <directionalLight
        castShadow
        position={[2.8, 4.6, 3.2]}
        intensity={theme === "light" ? 2.1 : 1.55}
        color={palette.sun}
        shadow-mapSize={[1024, 1024]}
      />
      <directionalLight position={[-3.4, 1.8, 1.2]} intensity={palette.fillIntensity} color={palette.fill} />
      <spotLight position={[0.6, 3.4, 2.4]} intensity={theme === "light" ? 1.3 : 2.2} angle={0.5} penumbra={0.85} color={palette.spot1} />
      <spotLight position={[-2.2, 5.2, -3.4]} intensity={theme === "light" ? 2.0 : 3.4} angle={0.35} penumbra={0.9} color={palette.spot2} />

      <ChamberBackdrop reducedMotion={reducedMotion} />
      <RevealHall progress={journey} reducedMotion={reducedMotion} />

      <group position={compact ? [0, 0, 0] : [-0.55, 0, 0]}>
        <ScaleModel onBiasChange={onBiasChange} />
      </group>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <circleGeometry args={[11, 64]} />
        <meshStandardMaterial color={stone("#0b0d14")} metalness={0.35} roughness={0.55} />
      </mesh>
      <ContactShadows position={[0, 0.012, 0]} opacity={0.45} scale={8} blur={2.6} far={2.8} color={palette.shadowColor} />

      <Environment resolution={256} frames={1}>
        <Lightformer intensity={2.6} position={[0, 5, 1]} scale={[10, 1.4, 1]} />
        <Lightformer intensity={1.1} position={[-4, 2, 2]} scale={[4, 4, 1]} color={palette.envA} />
        <Lightformer intensity={1.6} position={[4, 3, -1]} scale={[5, 1.8, 1]} color={palette.envB} />
      </Environment>

      {/* Altın yaldızın gerçekten ışık saçıyormuş gibi görünmesi için —
          @react-three/postprocessing zaten bağımlılıktı, hiç kullanılmıyordu.
          Eşik/yoğunluk temaya göre ayarlı: gündüzde zemin zaten parlak,
          yalnızca en parlak vurgular (altın, fener alevleri) parlamalı. */}
      <EffectComposer>
        <Bloom
          luminanceThreshold={palette.bloomThreshold}
          luminanceSmoothing={palette.bloomSmoothing}
          intensity={palette.bloomIntensity}
          mipmapBlur
        />
      </EffectComposer>
    </>
  );
}

export function JusticeScaleCanvas({ size = "hero", onBiasChange, scrollProgress = 0, theme = "dark" }: Props) {
  const compact = size === "compact";
  const reducedMotion = usePrefersReducedMotion();
  const journey = compact ? 0 : scrollProgress;
  const ctxValue = useMemo(
    () => ({
      theme,
      palette: PALETTE[theme],
      stone: (hex: string) => (theme === "light" ? STONE_MAP[hex] ?? hex : hex),
    }),
    [theme]
  );
  return (
    <div className={`scale-canvas ${size}`}>
      <ScenePaletteContext.Provider value={ctxValue}>
        <Canvas
          shadows
          dpr={[1, 1.6]}
          camera={{
            fov: compact ? 36 : 30,
            position: compact ? [1.1, 1.25, 3.4] : [1.7, 1.35, 5.0],
            near: 0.1,
            far: compact ? 24 : 42,
          }}
          gl={{
            antialias: true,
            alpha: false,
            powerPreference: "high-performance",
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: 1.08,
          }}
          resize={{ scroll: false, debounce: 50 }}
        >
          <SceneContent compact={compact} reducedMotion={reducedMotion} journey={journey} onBiasChange={onBiasChange} />
          <AtmosphereDirector progress={journey} compact={compact} />
          <ScrollDirector progress={journey} compact={compact} />
          <SceneOrbit compact={compact} reducedMotion={reducedMotion} scrollProgress={journey} />
        </Canvas>
      </ScenePaletteContext.Provider>
    </div>
  );
}
