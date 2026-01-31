'use client'

import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Sphere, Torus, Ring, Line } from '@react-three/drei'
import * as THREE from 'three'

function ChakraRing({ radius, color, opacity = 0.6, speed = 0.5 }: { radius: number; color: string; opacity?: number; speed?: number }) {
  const meshRef = useRef<THREE.Mesh>(null)
  
  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.elapsedTime * speed * 0.3
      meshRef.current.rotation.z = state.clock.elapsedTime * speed * 0.5
    }
  })

  return (
    <mesh ref={meshRef}>
      <torusGeometry args={[radius, 0.02, 16, 100]} />
      <meshStandardMaterial 
        color={color} 
        transparent 
        opacity={opacity}
        emissive={color}
        emissiveIntensity={0.5}
      />
    </mesh>
  )
}

function SacredGeometry() {
  const groupRef = useRef<THREE.Group>(null)
  
  const points = useMemo(() => {
    const pts = []
    const segments = 8
    for (let i = 0; i < segments; i++) {
      const angle = (i / segments) * Math.PI * 2
      pts.push(new THREE.Vector3(Math.cos(angle) * 2, Math.sin(angle) * 2, 0))
    }
    return pts
  }, [])

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = state.clock.elapsedTime * 0.2
      groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.3) * 0.1
    }
  })

  return (
    <group ref={groupRef}>
      {/* Outer ring */}
      <ChakraRing radius={2.5} color="#FFD700" opacity={0.4} speed={0.3} />
      
      {/* Middle ring */}
      <ChakraRing radius={2} color="#FFA726" opacity={0.5} speed={0.4} />
      
      {/* Inner ring */}
      <ChakraRing radius={1.5} color="#FF6B35" opacity={0.6} speed={0.5} />
      
      {/* Center sphere with glow */}
      <Sphere args={[0.8, 32, 32]}>
        <meshStandardMaterial 
          color="#FFD700"
          emissive="#FFA726"
          emissiveIntensity={0.8}
          transparent
          opacity={0.9}
        />
      </Sphere>
      
      {/* Outer glow sphere */}
      <Sphere args={[1.2, 32, 32]}>
        <meshStandardMaterial 
          color="#FFD700"
          transparent
          opacity={0.2}
          side={THREE.BackSide}
        />
      </Sphere>
      
      {/* Geometric lines */}
      {points.map((point, i) => (
        <Line
          key={i}
          points={[new THREE.Vector3(0, 0, 0), point]}
          color="#FFD700"
          opacity={0.3}
          transparent
          lineWidth={1}
        />
      ))}
      
      {/* Outer geometric pattern */}
      {Array.from({ length: 8 }, (_, i) => {
        const angle = (i / 8) * Math.PI * 2
        return (
          <mesh 
            key={`geo-${i}`}
            position={[
              Math.cos(angle) * 2.2,
              Math.sin(angle) * 2.2,
              0
            ]}
          >
            <octahedronGeometry args={[0.1, 0]} />
            <meshStandardMaterial 
              color="#FFA726"
              emissive="#FFD700"
              emissiveIntensity={0.5}
            />
          </mesh>
        )
      })}
    </group>
  )
}

function Particles() {
  const particlesRef = useRef<THREE.Points>(null)
  
  const particlePositions = useMemo(() => {
    const count = 200
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const theta = Math.random() * Math.PI * 2
      const phi = Math.random() * Math.PI
      const r = 3 + Math.random() * 2
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(phi)
    }
    return positions
  }, [])

  useFrame((state) => {
    if (particlesRef.current) {
      particlesRef.current.rotation.y = state.clock.elapsedTime * 0.05
      particlesRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.05
    }
  })

  return (
    <points ref={particlesRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={particlePositions.length / 3}
          array={particlePositions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        color="#FFD700"
        transparent
        opacity={0.6}
        sizeAttenuation
      />
    </points>
  )
}

function LightBeams() {
  const beamsRef = useRef<THREE.Group>(null)
  
  useFrame((state) => {
    if (beamsRef.current) {
      beamsRef.current.rotation.z = state.clock.elapsedTime * 0.1
    }
  })

  return (
    <group ref={beamsRef}>
      {Array.from({ length: 6 }, (_, i) => {
        const angle = (i / 6) * Math.PI * 2
        return (
          <mesh
            key={`beam-${i}`}
            position={[
              Math.cos(angle) * 1.5,
              Math.sin(angle) * 1.5,
              -0.5
            ]}
            rotation={[0, 0, angle + Math.PI / 2]}
          >
            <planeGeometry args={[0.1, 4]} />
            <meshBasicMaterial 
              color="#FFD700"
              transparent
              opacity={0.1}
              side={THREE.DoubleSide}
            />
          </mesh>
        )
      })}
    </group>
  )
}

export default function Chakra3DScene() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 60 }}
      className="w-full h-full"
      gl={{ 
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance'
      }}
    >
      <color attach="background" args={['#0D0D0D']} />
      
      {/* Ambient light */}
      <ambientLight intensity={0.2} />
      
      {/* Main lights */}
      <pointLight position={[10, 10, 10]} intensity={0.5} color="#FFD700" />
      <pointLight position={[-10, -10, -10]} intensity={0.3} color="#FF6B35" />
      <pointLight position={[0, 0, 5]} intensity={0.8} color="#FFD700" />
      
      {/* Sacred geometry */}
      <SacredGeometry />
      
      {/* Floating particles */}
      <Particles />
      
      {/* Light beams */}
      <LightBeams />
      
      {/* Controls */}
      <OrbitControls 
        enableZoom={false}
        enablePan={false}
        autoRotate
        autoRotateSpeed={0.5}
        maxPolarAngle={Math.PI / 1.5}
        minPolarAngle={Math.PI / 3}
      />
    </Canvas>
  )
}
