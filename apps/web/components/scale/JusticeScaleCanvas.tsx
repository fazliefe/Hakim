"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, OrbitControls, Sparkles, Text } from "@react-three/drei";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

type DragSide = "left" | "right" | "beam" | null;

type Props = {
  size?: "hero" | "compact";
  onBiasChange?: (bias: number) => void;
  scrollProgress?: number;
};

const GOLD = "#d4af37";
const orbitGate = { allowed: true };

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
  return (
    <meshStandardMaterial
      color={GOLD}
      metalness={metalness}
      roughness={roughness}
      envMapIntensity={1.25}
    />
  );
}

function SteelMaterial() {
  return <meshStandardMaterial color="#c5cdd8" metalness={0.92} roughness={0.28} envMapIntensity={1} />;
}

function StoneMaterial({ color = "#171a22" }: { color?: string }) {
  return <meshStandardMaterial color={color} roughness={0.72} metalness={0.18} envMapIntensity={0.45} />;
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
  const ref = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (reducedMotion || !ref.current) return;
    ref.current.rotation.z += dt * 0.025;
  });
  return (
    <group ref={ref} position={[-0.45, 1.2, -4.6]}>
      <mesh>
        <torusGeometry args={[1.9, 0.012, 12, 96]} />
        <meshStandardMaterial color={GOLD} metalness={1} roughness={0.22} envMapIntensity={1.5} />
      </mesh>
      <mesh>
        <torusGeometry args={[1.52, 0.006, 12, 96]} />
        <meshStandardMaterial color={GOLD} metalness={1} roughness={0.28} transparent opacity={0.5} />
      </mesh>
      <mesh>
        <ringGeometry args={[0.35, 0.72, 48]} />
        <meshBasicMaterial color={GOLD} transparent opacity={0.07} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </group>
  );
}

function ChamberBackdrop({ reducedMotion }: { reducedMotion: boolean }) {
  return (
    <group>
      <mesh position={[0, 2.8, 0]}>
        <cylinderGeometry args={[12.5, 12.5, 8.4, 48, 1, true]} />
        <meshStandardMaterial color="#0a0c13" roughness={0.92} metalness={0.08} side={THREE.BackSide} />
      </mesh>
      <Column position={[-3.15, 0, -2.55]} />
      <Column position={[2.55, 0, -2.9]} />
      <Column position={[-1.7, 0, -4.1]} />
      <mesh position={[-1.4, 4.4, -3.2]} rotation={[0.55, 0.15, -0.18]}>
        <planeGeometry args={[1.6, 7.5]} />
        <meshBasicMaterial color="#e8c56a" transparent opacity={0.05} depthWrite={false} />
      </mesh>
      <mesh position={[1.1, 4.2, -3.6]} rotation={[0.5, -0.2, 0.12]}>
        <planeGeometry args={[1.2, 6.8]} />
        <meshBasicMaterial color="#c9d4ee" transparent opacity={0.04} depthWrite={false} />
      </mesh>
      {[1.55, 2.35, 3.35].map((radius) => (
        <mesh key={radius} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.014, 0]}>
          <torusGeometry args={[radius, 0.01, 8, 80]} />
          <GoldMaterial roughness={0.32} />
        </mesh>
      ))}
      <DistantHalo reducedMotion={reducedMotion} />
      {!reducedMotion ? (
        <Sparkles
          count={36}
          scale={[11, 4.5, 7]}
          size={1.6}
          speed={0.12}
          opacity={0.28}
          color="#e8c56a"
          position={[-0.4, 1.7, -2.2]}
        />
      ) : null}
    </group>
  );
}

function HallLantern({ position }: { position: [number, number, number] }) {
  return (
    <group position={position}>
      <mesh position={[0, 0.42, 0]}>
        <cylinderGeometry args={[0.007, 0.007, 0.72, 8]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.048, 16, 16]} />
        <meshBasicMaterial color="#f4e4bc" transparent opacity={0.9} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.16, 16, 16]} />
        <meshBasicMaterial color="#e8c56a" transparent opacity={0.07} depthWrite={false} />
      </mesh>
      <mesh position={[0, -0.07, 0]}>
        <coneGeometry args={[0.055, 0.08, 8]} />
        <GoldMaterial roughness={0.26} />
      </mesh>
    </group>
  );
}

function WallTablet({
  position,
  rotation,
  opacity,
}: {
  position: [number, number, number];
  rotation: [number, number, number];
  opacity: number;
}) {
  return (
    <group position={position} rotation={rotation}>
      <mesh castShadow>
        <boxGeometry args={[0.52, 0.74, 0.04]} />
        <meshStandardMaterial color="#161922" roughness={0.7} metalness={0.2} />
      </mesh>
      <mesh position={[0, 0, 0.024]}>
        <planeGeometry args={[0.4, 0.58]} />
        <meshStandardMaterial
          color={GOLD}
          metalness={0.9}
          roughness={0.28}
          transparent
          opacity={opacity}
          envMapIntensity={1.2}
        />
      </mesh>
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
  return (
    <group position={position} rotation={rotation}>
      <mesh>
        <planeGeometry args={[0.92, 2.15]} />
        <meshStandardMaterial
          color="#10131a"
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
        <meshStandardMaterial color="#2a2418" roughness={0.68} metalness={0.2} />
      </mesh>
      <mesh position={[0.01, 0.275, -0.01]} rotation={[0, 0.08, 0]} castShadow>
        <boxGeometry args={[0.2, 0.032, 0.13]} />
        <meshStandardMaterial color="#1e2430" roughness={0.62} metalness={0.25} />
      </mesh>
    </group>
  );
}

function Urn({ position }: { position: [number, number, number] }) {
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
        <meshBasicMaterial color="#f3e0b8" transparent opacity={0.55} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.14, 14, 14]} />
        <meshBasicMaterial color="#e8c56a" transparent opacity={0.06} depthWrite={false} />
      </mesh>
    </group>
  );
}

function RevealHall({ progress, reducedMotion }: { progress: number; reducedMotion: boolean }) {
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
        <meshStandardMaterial
          color={GOLD}
          metalness={1}
          roughness={0.22}
          transparent
          opacity={0.2 + deep * 0.75}
        />
      </mesh>
      <mesh position={[-0.3, 3.52, -8.38]} rotation={[Math.PI / 2, 0, Math.PI]}>
        <coneGeometry args={[1.62, 0.1, 3]} />
        <StoneMaterial color="#161a22" />
      </mesh>
      <mesh position={[-0.3, 2.72, -8.32]}>
        <ringGeometry args={[0.55, 1.55, 64]} />
        <meshBasicMaterial
          color={GOLD}
          transparent
          opacity={0.03 + far * 0.14}
          side={THREE.DoubleSide}
          depthWrite={false}
        />
      </mesh>
      <Text
        position={[-0.3, 3.42, -8.18]}
        fontSize={0.13}
        color={GOLD}
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
          color="#2c2416"
          metalness={0.35}
          roughness={0.48}
          transparent
          opacity={0.22 + deep * 0.45}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.3, 0.019, -4.9]}>
        <planeGeometry args={[0.055, 7.4]} />
        <meshStandardMaterial
          color={GOLD}
          metalness={1}
          roughness={0.28}
          transparent
          opacity={0.18 + deep * 0.55}
        />
      </mesh>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.3, 0.02, -5.7]}>
        <circleGeometry args={[0.95, 48]} />
        <meshStandardMaterial color="#12151c" roughness={0.55} metalness={0.35} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.3, 0.022, -5.7]}>
        <ringGeometry args={[0.38, 0.92, 48]} />
        <meshStandardMaterial
          color={GOLD}
          metalness={1}
          roughness={0.28}
          transparent
          opacity={0.2 + mid * 0.7}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-0.3, 0.024, -5.7]}>
        <ringGeometry args={[0.12, 0.22, 32]} />
        <GoldMaterial roughness={0.24} />
      </mesh>

      {[0, 1, 2].map((step) => (
        <mesh key={step} position={[-0.3, 0.05 + step * 0.075, -7.15 + step * 0.32]} castShadow receiveShadow>
          <boxGeometry args={[2.9 - step * 0.35, 0.08, 0.36]} />
          <StoneMaterial color="#141820" />
        </mesh>
      ))}
      <mesh position={[-0.3, 0.085, -7.15]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[2.7, 0.04]} />
        <meshStandardMaterial color={GOLD} metalness={1} roughness={0.3} transparent opacity={0.35 + far * 0.5} />
      </mesh>

      {[4.15, 5.35, 6.7].map((radius) => (
        <mesh key={radius} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.016, -1.4]}>
          <torusGeometry args={[radius, 0.01, 8, 96]} />
          <meshStandardMaterial
            color={GOLD}
            metalness={1}
            roughness={0.32}
            transparent
            opacity={0.15 + mid * 0.7}
          />
        </mesh>
      ))}

      <WallTablet position={[-3.55, 1.62, -5.85]} rotation={[0, 0.52, 0]} opacity={0.2 + mid * 0.7} />
      <WallTablet position={[3.05, 1.68, -6.05]} rotation={[0, -0.48, 0]} opacity={0.2 + mid * 0.7} />
      <WallTablet position={[-3.85, 1.72, -7.55]} rotation={[0, 0.38, 0]} opacity={0.15 + deep * 0.75} />
      <WallTablet position={[3.25, 1.78, -7.7]} rotation={[0, -0.34, 0]} opacity={0.15 + deep * 0.75} />

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
        <meshBasicMaterial color="#f0d48a" transparent opacity={0.03 + deep * 0.09} depthWrite={false} />
      </mesh>
      <mesh position={[1.9, 5.25, -5.8]} rotation={[0.58, -0.18, 0.1]}>
        <planeGeometry args={[1.9, 9]} />
        <meshBasicMaterial color="#c5d4f0" transparent opacity={0.025 + deep * 0.07} depthWrite={false} />
      </mesh>

      <pointLight position={[-0.3, 3.4, -6.2]} color="#f0d7a0" intensity={deep * 2.8} distance={14} />
      <spotLight position={[-0.3, 5.6, -3.8]} intensity={far * 3.2} angle={0.46} penumbra={0.92} color="#f3e0b8" />

      {!reducedMotion && deep > 0.12 ? (
        <Sparkles
          count={48}
          scale={[12, 5, 9]}
          size={1.8}
          speed={0.14}
          opacity={0.16 + deep * 0.28}
          color="#e8c56a"
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
        <meshStandardMaterial color="#0c0b10" metalness={0.72} roughness={0.28} envMapIntensity={1.1} />
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
                color={GOLD}
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
                color={GOLD}
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

export function JusticeScaleCanvas({ size = "hero", onBiasChange, scrollProgress = 0 }: Props) {
  const compact = size === "compact";
  const reducedMotion = usePrefersReducedMotion();
  const journey = compact ? 0 : scrollProgress;
  return (
    <div className={`scale-canvas ${size}`}>
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
        <color attach="background" args={["#07090f"]} />
        <fog attach="fog" args={["#07090f", 11, 22]} />
        <ambientLight intensity={0.32} />
        <directionalLight
          castShadow
          position={[2.8, 4.6, 3.2]}
          intensity={1.55}
          color="#fff3dc"
          shadow-mapSize={[1024, 1024]}
        />
        <directionalLight position={[-3.4, 1.8, 1.2]} intensity={0.45} color="#9aacd0" />
        <spotLight position={[0.6, 3.4, 2.4]} intensity={2.2} angle={0.5} penumbra={0.85} color="#f3e0b8" />
        <spotLight position={[-2.2, 5.2, -3.4]} intensity={3.4} angle={0.35} penumbra={0.9} color="#f0d7a0" />

        <ChamberBackdrop reducedMotion={reducedMotion} />
        <RevealHall progress={journey} reducedMotion={reducedMotion} />

        <group position={compact ? [0, 0, 0] : [-0.55, 0, 0]}>
          <ScaleModel onBiasChange={onBiasChange} />
        </group>

        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
          <circleGeometry args={[11, 64]} />
          <meshStandardMaterial color="#0b0d14" metalness={0.35} roughness={0.55} />
        </mesh>
        <ContactShadows position={[0, 0.012, 0]} opacity={0.45} scale={8} blur={2.6} far={2.8} />

        <Environment resolution={256} frames={1}>
          <Lightformer intensity={2.6} position={[0, 5, 1]} scale={[10, 1.4, 1]} />
          <Lightformer intensity={1.1} position={[-4, 2, 2]} scale={[4, 4, 1]} color="#a8b8d4" />
          <Lightformer intensity={1.6} position={[4, 3, -1]} scale={[5, 1.8, 1]} color="#e8d5a4" />
        </Environment>

        <AtmosphereDirector progress={journey} compact={compact} />
        <ScrollDirector progress={journey} compact={compact} />
        <SceneOrbit compact={compact} reducedMotion={reducedMotion} scrollProgress={journey} />
      </Canvas>
    </div>
  );
}
