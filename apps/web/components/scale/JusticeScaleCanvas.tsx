"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment, Lightformer, Sparkles, Text } from "@react-three/drei";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import * as THREE from "three";

type DragSide = "left" | "right" | "beam" | null;

type Props = {
  size?: "hero" | "compact";
  onBiasChange?: (bias: number) => void;
};

const GOLD = "#d4af37";

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

function GoldMaterial({ roughness = 0.16, metalness = 1 }: { roughness?: number; metalness?: number }) {
  return (
    <meshStandardMaterial
      color={GOLD}
      metalness={metalness}
      roughness={roughness}
      envMapIntensity={1.7}
    />
  );
}

function SteelMaterial() {
  return <meshStandardMaterial color="#c9d2de" metalness={0.95} roughness={0.28} envMapIntensity={1.1} />;
}

function CameraRig({ compact }: { compact: boolean }) {
  const { camera } = useThree();
  const mouse = useRef({ x: 0, y: 0 });
  const goal = useRef(new THREE.Vector3(compact ? 0.4 : 0.05, compact ? 1.2 : 1.22, compact ? 2.2 : 3.15));
  const look = useRef(new THREE.Vector3(compact ? 0 : -0.55, compact ? 0.85 : 0.92, 0));

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mouse.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.current.y = (e.clientY / window.innerHeight) * -2 + 1;
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  useFrame(() => {
    const px = mouse.current.x;
    const py = mouse.current.y;
    if (compact) {
      goal.current.set(0.4 + px * 0.18, 1.18 + py * 0.06, 2.2);
    } else {
      goal.current.set(0.08 + px * 0.38, 1.22 + py * 0.08, 3.12);
    }
    camera.position.lerp(goal.current, 0.028);
    camera.lookAt(look.current);
  });
  return null;
}

function OrbitingKeyLight() {
  const ref = useRef<THREE.Group>(null);
  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime * 0.22;
    ref.current.position.set(Math.cos(t) * 3.4, 3.2 + Math.sin(t * 0.6) * 0.25, Math.sin(t) * 3.4);
  });
  return (
    <group ref={ref}>
      <spotLight intensity={7.5} angle={0.42} penumbra={0.85} color="#ffe3a3" distance={14} />
    </group>
  );
}

function Bowl({ onGrab }: { onGrab?: (e: { clientY: number; clientX: number }) => void }) {
  const points = useMemo(() => {
    const pts: THREE.Vector2[] = [];
    for (let i = 0; i <= 24; i++) {
      const t = i / 24;
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
        <latheGeometry args={[points, 48]} />
        <GoldMaterial roughness={0.18} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0.155, 0]} castShadow>
        <torusGeometry args={[0.365, 0.018, 10, 48]} />
        <GoldMaterial roughness={0.12} />
      </mesh>
    </group>
  );
}

function Chain({ length = 0.52 }: { length?: number }) {
  return (
    <group>
      <mesh position={[-0.035, -length / 2, 0]} castShadow>
        <cylinderGeometry args={[0.007, 0.007, length, 8]} />
        <SteelMaterial />
      </mesh>
      <mesh position={[0.035, -length / 2, 0]} rotation={[0, 0, 0.12]} castShadow>
        <cylinderGeometry args={[0.007, 0.007, length, 8]} />
        <SteelMaterial />
      </mesh>
      <mesh position={[0, -0.02, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.045, 0.01, 8, 16]} />
        <GoldMaterial />
      </mesh>
    </group>
  );
}

function ScaleModel({ onBiasChange, reducedMotion }: { onBiasChange?: (bias: number) => void; reducedMotion: boolean }) {
  const rootRef = useRef<THREE.Group>(null);
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
      tilt.current += Math.sin(state.clock.elapsedTime * 0.85) * 0.0014;
    }
    const angle = THREE.MathUtils.clamp(tilt.current, -1, 1) * 0.38;
    if (beamRef.current) beamRef.current.rotation.z = angle;
    if (leftHang.current) leftHang.current.rotation.z = -angle;
    if (rightHang.current) rightHang.current.rotation.z = -angle;
    if (rootRef.current && !reducedMotion) {
      rootRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.16) * 0.16;
    }
  });

  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!drag.current) return;
      if (drag.current === "beam") {
        tilt.current = THREE.MathUtils.clamp(startTilt.current + (e.clientX - startX.current) / 240, -1, 1);
      } else {
        const dy = (e.clientY - startY.current) / 170;
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
    startX.current = clientX;
    startY.current = clientY;
    startTilt.current = tilt.current;
    vel.current = 0;
    document.body.style.cursor = "grabbing";
  }

  const arm = 1.05;

  return (
    <group ref={rootRef}>
      <mesh position={[0, 0.05, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[0.52, 0.58, 0.1, 48]} />
        <GoldMaterial roughness={0.3} />
      </mesh>
      <mesh position={[0, 0.13, 0]} castShadow>
        <cylinderGeometry args={[0.38, 0.42, 0.08, 48]} />
        <GoldMaterial roughness={0.2} />
      </mesh>
      <mesh position={[0, 0.72, 0]} castShadow>
        <cylinderGeometry args={[0.048, 0.07, 1.12, 32]} />
        <GoldMaterial roughness={0.2} />
      </mesh>
      <mesh position={[0, 1.28, 0]} castShadow>
        <cylinderGeometry args={[0.11, 0.11, 0.06, 32]} />
        <GoldMaterial roughness={0.14} />
      </mesh>
      <mesh position={[0, 1.28, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.13, 0.016, 12, 32]} />
        <GoldMaterial roughness={0.12} />
      </mesh>

      <group ref={beamRef} position={[0, 1.34, 0]}>
        <mesh
          castShadow
          onPointerDown={(e) => {
            e.stopPropagation();
            begin("beam", e.clientX, e.clientY);
          }}
        >
          <boxGeometry args={[2.2, 0.055, 0.08]} />
          <GoldMaterial roughness={0.16} />
        </mesh>
        <mesh position={[-1.1, 0, 0]} castShadow>
          <sphereGeometry args={[0.045, 20, 20]} />
          <GoldMaterial roughness={0.12} />
        </mesh>
        <mesh position={[1.1, 0, 0]} castShadow>
          <sphereGeometry args={[0.045, 20, 20]} />
          <GoldMaterial roughness={0.12} />
        </mesh>
        <mesh position={[0, 0.02, 0]} castShadow>
          <sphereGeometry args={[0.07, 24, 24]} />
          <GoldMaterial roughness={0.1} />
        </mesh>

        <group position={[-arm, 0, 0]}>
          <group ref={leftHang}>
            <Chain />
            <group position={[0, -0.58, 0]}>
              <Bowl onGrab={(e) => begin("left", e.clientX, e.clientY)} />
              <Text position={[0, -0.3, 0.02]} fontSize={0.075} color={GOLD} anchorX="center" anchorY="middle" letterSpacing={0.12}>
                KANUN
              </Text>
            </group>
          </group>
        </group>

        <group position={[arm, 0, 0]}>
          <group ref={rightHang}>
            <Chain />
            <group position={[0, -0.58, 0]}>
              <Bowl onGrab={(e) => begin("right", e.clientX, e.clientY)} />
              <Text position={[0, -0.3, 0.02]} fontSize={0.075} color={GOLD} anchorX="center" anchorY="middle" letterSpacing={0.12}>
                VİCDAN
              </Text>
            </group>
          </group>
        </group>
      </group>
    </group>
  );
}

export function JusticeScaleCanvas({ size = "hero", onBiasChange }: Props) {
  const compact = size === "compact";
  const reducedMotion = usePrefersReducedMotion();
  return (
    <div className={`scale-canvas ${size}`}>
      <Canvas
        shadows
        dpr={[1, 1.6]}
        camera={{
          fov: compact ? 36 : 26,
          position: compact ? [0.4, 1.2, 2.2] : [0.05, 1.22, 3.15],
          near: 0.1,
          far: 30,
        }}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: "high-performance",
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.12,
        }}
        resize={{ scroll: false, debounce: 50 }}
      >
        <color attach="background" args={["#03040a"]} />
        <fog attach="fog" args={["#03040a", 5.5, 13]} />
        <ambientLight intensity={0.12} />
        <directionalLight
          castShadow
          position={[2.6, 4.6, 2.4]}
          intensity={1.55}
          color="#fff6e0"
          shadow-mapSize={[1024, 1024]}
        />
        <directionalLight position={[-3.4, 1.4, 1.8]} intensity={0.7} color="#8ea8ff" />
        <spotLight position={[-2.1, 3.8, -2.4]} intensity={5.2} angle={0.5} penumbra={0.82} color="#ffd27a" />
        <pointLight position={[0, 1.6, 0.5]} intensity={0.28} color="#f3e0a6" />
        {!reducedMotion ? <OrbitingKeyLight /> : null}

        <CameraRig compact={compact} />
        <group position={compact ? [0, 0, 0] : [-0.72, -0.04, 0]}>
          <ScaleModel onBiasChange={onBiasChange} reducedMotion={reducedMotion} />
        </group>

        {!reducedMotion ? (
          <Sparkles
            count={compact ? 18 : 48}
            scale={compact ? [3.2, 2.2, 2.2] : [7.5, 3.6, 4.5]}
            size={2.4}
            speed={0.22}
            opacity={0.38}
            color="#e8c56a"
            position={compact ? [0, 1.1, 0] : [-0.7, 1.15, 0]}
          />
        ) : null}

        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
          <circleGeometry args={[10, 64]} />
          <meshStandardMaterial color="#07080f" metalness={0.82} roughness={0.18} envMapIntensity={0.9} />
        </mesh>
        <ContactShadows position={[0, 0.01, 0]} opacity={0.62} scale={9} blur={2.8} far={3.2} />

        <Environment resolution={256} frames={1}>
          <Lightformer intensity={4.1} position={[0, 5.2, 1]} scale={[10, 1.6, 1]} />
          <Lightformer intensity={1.8} position={[-5, 2.2, 2]} scale={[5, 5, 1]} color="#9bb7ff" />
          <Lightformer intensity={2.6} position={[5, 3.2, -2]} scale={[6, 2.2, 1]} color="#ffd978" />
          <Lightformer intensity={1.2} position={[0, 1, -5]} scale={[8, 4, 1]} color="#ffffff" />
        </Environment>

        <EffectComposer enableNormalPass={false} multisampling={0}>
          <Bloom luminanceThreshold={0.78} intensity={0.55} mipmapBlur radius={0.62} />
        </EffectComposer>
      </Canvas>
    </div>
  );
}
