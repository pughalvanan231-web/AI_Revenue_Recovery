import React, { Suspense, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line, Text, Float } from "@react-three/drei";
import * as THREE from "three";

function Node({ position, label, activeSeed = 0, color = "#6366f1" }) {
  const core = useRef();
  const shell = useRef();
  
  useFrame(({ clock }) => {
    const t = clock.getElapsedTime() + activeSeed;
    if (core.current) {
      core.current.rotation.x = t * 0.5;
      core.current.rotation.y = t * 0.8;
      // Pulse the glowing core
      core.current.material.emissiveIntensity = 2 + Math.sin(t * 4) * 1.5;
    }
    if (shell.current) {
      // Gentle floating animation
      shell.current.position.y = position[1] + Math.sin(t * 1.5) * 0.15;
    }
  });

  return (
    <group position={[position[0], 0, position[2]]}>
      <group ref={shell}>
        {/* Glowing Core */}
        <mesh ref={core}>
          <icosahedronGeometry args={[0.45, 1]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={3}
            wireframe={true}
          />
        </mesh>
      </group>

      <Text
        position={[0, -1.2, 0]}
        fontSize={0.22}
        color="#e4e4e7"
        anchorX="center"
        anchorY="middle"
        letterSpacing={0.05}
        fontWeight="bold"
      >
        {label}
      </Text>
    </group>
  );
}

function FlowLine({ from, to, phase = 0, color = "#6366f1" }) {
  const ref = useRef();
  const points = useMemo(() => {
    const start = new THREE.Vector3(...from);
    const end = new THREE.Vector3(...to);
    const mid = start.clone().lerp(end, 0.5);
    mid.y += 0.8; // arch height
    const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
    return curve.getPoints(50);
  }, [from, to]);

  useFrame(({ clock }) => {
    if (ref.current) {
      // Fast moving dash lines to simulate data transfer
      const t = (clock.getElapsedTime() * 0.8 + phase) % 1;
      ref.current.material.dashOffset = -t * 2;
    }
  });

  return (
    <Line
      ref={ref}
      points={points}
      color={color}
      lineWidth={3}
      dashed
      dashSize={0.25}
      gapSize={0.15}
      transparent
      opacity={0.8}
    />
  );
}

function Particles({ count = 100 }) {
  const ref = useRef();
  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 15;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 10;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 10;
    }
    return arr;
  }, [count]);
  
  useFrame(({ clock }) => {
    if (ref.current) {
      // Slow rotation of the entire particle field
      ref.current.rotation.y = clock.getElapsedTime() * 0.02;
    }
  });
  
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial color="#ffffff" size={0.04} transparent opacity={0.3} sizeAttenuation={true} />
    </points>
  );
}

function Scene() {
  const llm = [-3.0, 0.6, 0];
  const policy = [0, 0.6, 0];
  const executor = [3.0, 0.6, 0];
  
  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[5, 8, 5]} intensity={2} color="#ffffff" />
      <pointLight position={[-4, 2, 2]} intensity={1.5} color="#8b5cf6" />
      <pointLight position={[4, 2, 2]} intensity={1.5} color="#10b981" />
      
      <Particles />
      
      {/* 
        Colors map to the components:
        LLM (Purple) -> Policy Gate (Blue) -> Executor (Emerald)
      */}
      <FlowLine from={llm} to={policy} phase={0} color="#8b5cf6" />
      <FlowLine from={policy} to={executor} phase={0.5} color="#ffffff" />
      
      <Node position={llm} label="LLM DIAGNOSIS" activeSeed={0} color="#8b5cf6" />
      <Node position={policy} label="POLICY GATE" activeSeed={1.6} color="#ffffff" />
      <Node position={executor} label="RAZORPAY EXECUTOR" activeSeed={3.2} color="#10b981" />
    </>
  );
}

export default function Hero3D() {
  return (
    <div className="w-full h-[420px] lg:h-[520px] relative">
      <Canvas
        camera={{ position: [0, 1.5, 10], fov: 45 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <Suspense fallback={null}>
          <Scene />
          <OrbitControls
            enableZoom={false}
            enablePan={false}
            autoRotate
            autoRotateSpeed={0.5}
            minPolarAngle={Math.PI / 2.6}
            maxPolarAngle={Math.PI / 2}
          />
        </Suspense>
      </Canvas>
      {/* Dark mode overlay fade */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#09090b] via-transparent to-transparent" />
    </div>
  );
}
