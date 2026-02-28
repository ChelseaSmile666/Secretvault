import { useRef, useEffect, useCallback, useMemo } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import type { GraphData, VaultNode, VaultLink } from '../types'
import { GROUP_META, LINK_COLORS } from '../lib/colors'

interface Props {
  data: GraphData
  selectedNode: VaultNode | null
  highlightNodes: Set<string>
  highlightLinks: Set<string>
  onNodeClick: (node: VaultNode) => void
  onNodeHover: (node: VaultNode | null) => void
}

// Star field background particles
function createStarField(): THREE.Points {
  const geometry = new THREE.BufferGeometry()
  const count = 3000
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    positions[i * 3]     = (Math.random() - 0.5) * 4000
    positions[i * 3 + 1] = (Math.random() - 0.5) * 4000
    positions[i * 3 + 2] = (Math.random() - 0.5) * 4000

    const rand = Math.random()
    if (rand > 0.98) { colors[i*3]=0; colors[i*3+1]=0.8; colors[i*3+2]=1 }      // cyan star
    else if (rand > 0.96) { colors[i*3]=1; colors[i*3+1]=0.84; colors[i*3+2]=0 } // gold star
    else { const b = 0.2 + Math.random() * 0.3; colors[i*3]=b; colors[i*3+1]=b; colors[i*3+2]=b+0.1 }
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.PointsMaterial({
    size: 1.2,
    vertexColors: true,
    transparent: true,
    opacity: 0.7,
    sizeAttenuation: true,
  })

  return new THREE.Points(geometry, material)
}

export default function NetworkGraph({ data, selectedNode, highlightNodes, highlightLinks, onNodeClick, onNodeHover }: Props) {
  const graphRef = useRef<any>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<number>(0)
  const nodeObjectsRef = useRef<Map<string, THREE.Group>>(new Map())
  const timeRef = useRef<number>(0)

  // Scene setup: stars + ambient nebula
  useEffect(() => {
    if (!graphRef.current) return
    const scene = graphRef.current.scene()
    if (!scene) return

    // Remove default background
    scene.background = new THREE.Color(0x000008)

    // Star field
    const stars = createStarField()
    stars.name = 'starfield'
    scene.add(stars)

    // Ambient light (soft purple/blue)
    const ambient = new THREE.AmbientLight(0x0022ff, 0.4)
    scene.add(ambient)

    // Directional light (cyan tint from above)
    const dir = new THREE.DirectionalLight(0x00aaff, 0.8)
    dir.position.set(0, 1, 0.5)
    scene.add(dir)

    // Point light (golden center glow)
    const point = new THREE.PointLight(0xffd700, 0.3, 2000)
    point.position.set(0, 0, 0)
    scene.add(point)

    return () => {
      const sf = scene.getObjectByName('starfield')
      if (sf) scene.remove(sf)
    }
  }, [graphRef.current])

  // Slow auto-rotation
  useEffect(() => {
    if (!graphRef.current) return
    const animate = () => {
      frameRef.current = requestAnimationFrame(animate)
      timeRef.current += 0.005

      // Rotate stars slowly
      try {
        const scene = graphRef.current?.scene?.()
        const stars = scene?.getObjectByName('starfield')
        if (stars) {
          stars.rotation.y = timeRef.current * 0.02
          stars.rotation.x = Math.sin(timeRef.current * 0.01) * 0.1
        }

        // Pulse arrested/convicted nodes
        nodeObjectsRef.current.forEach((group, nodeId) => {
          const node = data.nodes.find(n => n.id === nodeId)
          if (!node) return
          const isAlert = node.group === 'convicted' || node.group === 'arrested'
          const isSelected = selectedNode?.id === nodeId
          const isHighlighted = highlightNodes.size > 0 && highlightNodes.has(nodeId)
          const isDimmed = highlightNodes.size > 0 && !highlightNodes.has(nodeId)

          // Pulse ring for convicted/arrested
          const ring = group.getObjectByName('ring') as THREE.Mesh | undefined
          if (ring && isAlert) {
            const s = 1 + Math.sin(timeRef.current * 3) * 0.3
            ring.scale.set(s, s, s)
            ;(ring.material as THREE.MeshBasicMaterial).opacity = 0.4 + Math.sin(timeRef.current * 3) * 0.3
          }

          // Glow pulse
          const glow = group.getObjectByName('glow') as THREE.Mesh | undefined
          if (glow) {
            const baseOpacity = isDimmed ? 0.03 : isSelected ? 0.35 : isHighlighted ? 0.25 : 0.12
            const pulse = Math.sin(timeRef.current * 2 + (node.degree || 0)) * 0.05
            ;(glow.material as THREE.MeshPhongMaterial).opacity = baseOpacity + pulse
          }

          // Core sphere opacity when dimmed
          const core = group.getObjectByName('core') as THREE.Mesh | undefined
          if (core) {
            ;(core.material as THREE.MeshPhongMaterial).opacity = isDimmed ? 0.15 : 0.95
          }

          // Label visibility
          const label = group.getObjectByName('label') as any
          if (label) {
            label.visible = !isDimmed && (node.degree > 3 || isSelected || isHighlighted)
          }
        })
      } catch {
        // Graph not ready
      }
    }
    frameRef.current = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frameRef.current)
  }, [data.nodes, selectedNode, highlightNodes])

  // Custom 3D node objects — the visual heart of the explorer
  const nodeThreeObject = useCallback((node: VaultNode) => {
    const group = new THREE.Group()
    const color = new THREE.Color(node.color)
    const isAlert = node.group === 'convicted' || node.group === 'arrested'
    const size = Math.max(3, Math.min(16, 3 + (node.degree || 0) * 1.2))

    // ── Core sphere ──────────────────────────────────────────────────────
    const coreGeo = new THREE.SphereGeometry(size * 0.5, 16, 16)
    const coreMat = new THREE.MeshPhongMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.5,
      shininess: 100,
      transparent: true,
      opacity: 0.95,
    })
    const core = new THREE.Mesh(coreGeo, coreMat)
    core.name = 'core'
    group.add(core)

    // ── Glow sphere ──────────────────────────────────────────────────────
    const glowGeo = new THREE.SphereGeometry(size * 1.4, 12, 12)
    const glowMat = new THREE.MeshPhongMaterial({
      color,
      transparent: true,
      opacity: 0.12,
      side: THREE.BackSide,
    })
    const glow = new THREE.Mesh(glowGeo, glowMat)
    glow.name = 'glow'
    group.add(glow)

    // ── Alert ring for convicted/arrested ────────────────────────────────
    if (isAlert) {
      const ringGeo = new THREE.TorusGeometry(size * 1.8, size * 0.12, 8, 32)
      const ringMat = new THREE.MeshBasicMaterial({
        color: node.group === 'convicted' ? 0xff2244 : 0xff6600,
        transparent: true,
        opacity: 0.6,
      })
      const ring = new THREE.Mesh(ringGeo, ringMat)
      ring.name = 'ring'
      ring.rotation.x = Math.PI / 4
      group.add(ring)
    }

    // ── Special shapes for non-person types ──────────────────────────────
    if (node.type === 'location') {
      // Diamond shape
      const diamondGeo = new THREE.OctahedronGeometry(size * 0.4, 0)
      const diamondMat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.8, wireframe: true })
      const diamond = new THREE.Mesh(diamondGeo, diamondMat)
      group.add(diamond)
    } else if (node.type === 'finding') {
      // Hexagonal prism wireframe overlay
      const hexGeo = new THREE.CylinderGeometry(size * 0.55, size * 0.55, size * 0.3, 6)
      const hexMat = new THREE.MeshPhongMaterial({ color, emissive: color, emissiveIntensity: 0.6, wireframe: true, transparent: true, opacity: 0.6 })
      const hex = new THREE.Mesh(hexGeo, hexMat)
      group.add(hex)
    }

    // ── Label ────────────────────────────────────────────────────────────
    const label = new SpriteText(node.name.split(' ').slice(0, 3).join(' '))
    label.color = node.color
    label.textHeight = Math.max(2.5, size * 0.5)
    label.position.y = size + 4
    label.backgroundColor = 'rgba(0,0,8,0.7)'
    label.padding = 1
    ;(label as any).name = 'label'
    label.visible = node.degree > 3
    group.add(label)

    nodeObjectsRef.current.set(node.id, group)
    return group
  }, [])

  // Link particle count based on relationship type
  const linkParticles = useCallback((link: VaultLink) => {
    const type = link.type
    if (type === 'financial' || type === 'intelligence') return 4
    if (type === 'network' || type === 'evidence') return 2
    return 0
  }, [])

  const linkParticleColor = useCallback((link: VaultLink) => {
    return LINK_COLORS[link.type as keyof typeof LINK_COLORS]?.particle ?? '#ffffff'
  }, [])

  const linkColor = useCallback((link: VaultLink) => {
    const src = typeof link.source === 'string' ? link.source : link.source.id
    const tgt = typeof link.target === 'string' ? link.target : link.target.id
    const key = [src, tgt].sort().join('||')

    if (highlightLinks.size > 0) {
      return highlightLinks.has(key) ? (LINK_COLORS[link.type as keyof typeof LINK_COLORS]?.stroke ?? '#ffffff44') : '#ffffff08'
    }
    return LINK_COLORS[link.type as keyof typeof LINK_LINKS]?.stroke ?? '#ffffff22'
  }, [highlightLinks])

  const linkWidth = useCallback((link: VaultLink) => {
    const src = typeof link.source === 'string' ? link.source : link.source.id
    const tgt = typeof link.target === 'string' ? link.target : link.target.id
    const key = [src, tgt].sort().join('||')
    if (highlightLinks.has(key)) return 2.5
    return link.type === 'financial' || link.type === 'intelligence' ? 1.2 : 0.5
  }, [highlightLinks])

  const handleClick = useCallback((node: object) => {
    onNodeClick(node as VaultNode)
    // Fly camera to node
    const n = node as VaultNode
    if (graphRef.current && n.x !== undefined) {
      const dist = 120
      const distRatio = 1 + dist / Math.hypot(n.x || 0.01, n.y || 0.01, n.z || 0.01)
      graphRef.current.cameraPosition(
        { x: (n.x || 0) * distRatio, y: (n.y || 0) * distRatio, z: (n.z || 0) * distRatio },
        { x: n.x || 0, y: n.y || 0, z: n.z || 0 },
        2000
      )
    }
  }, [onNodeClick])

  const handleHover = useCallback((node: object | null) => {
    onNodeHover(node as VaultNode | null)
    if (containerRef.current) {
      containerRef.current.style.cursor = node ? 'pointer' : 'default'
    }
  }, [onNodeHover])

  return (
    <div ref={containerRef} className="absolute inset-0">
      <ForceGraph3D
        ref={graphRef}
        graphData={data as any}
        backgroundColor="#000008"
        nodeThreeObject={nodeThreeObject as any}
        nodeThreeObjectExtend={false}
        onNodeClick={handleClick}
        onNodeHover={handleHover}
        linkDirectionalParticles={linkParticles as any}
        linkDirectionalParticleSpeed={0.004}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleColor={linkParticleColor as any}
        linkColor={linkColor as any}
        linkWidth={linkWidth as any}
        linkOpacity={0.6}
        linkCurvature={0.15}
        enableNodeDrag={true}
        enableNavigationControls={true}
        showNavInfo={false}
        nodeLabel=""
        cooldownTicks={150}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
        warmupTicks={30}
      />
    </div>
  )
}

// Suppress TS error for undefined reference
const LINK_LINKS = LINK_COLORS
