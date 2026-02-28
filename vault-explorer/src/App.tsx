import { useState, useEffect, useCallback } from 'react'
import { AnimatePresence } from 'framer-motion'
import NetworkGraph from './components/NetworkGraph'
import EvidencePanel from './components/EvidencePanel'
import FilterBar from './components/FilterBar'
import SearchOverlay from './components/SearchOverlay'
import StatsHUD from './components/StatsHUD'
import type { GraphData, VaultNode, FilterGroup } from './types'

export default function App() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<VaultNode | null>(null)
  const [highlightNodes, setHighlightNodes] = useState<Set<string>>(new Set())
  const [highlightLinks, setHighlightLinks] = useState<Set<string>>(new Set())
  const [activeFilter, setActiveFilter] = useState<FilterGroup>('all')
  const [searchOpen, setSearchOpen] = useState(false)
  const [hoveredNode, setHoveredNode] = useState<VaultNode | null>(null)

  useEffect(() => {
    fetch('/vault-data.json')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status} — run "npm run parse" first`)
        return r.json()
      })
      .then((data: GraphData) => { setGraphData(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  const handleNodeClick = useCallback((node: VaultNode) => {
    setSelectedNode(node)

    if (!graphData) return
    const connected = new Set<string>([node.id])
    const connectedLinks = new Set<string>()

    for (const link of graphData.links) {
      const src = typeof link.source === 'string' ? link.source : link.source.id
      const tgt = typeof link.target === 'string' ? link.target : link.target.id
      if (src === node.id || tgt === node.id) {
        connected.add(src)
        connected.add(tgt)
        connectedLinks.add(`${src}||${tgt}`)
      }
    }
    setHighlightNodes(connected)
    setHighlightLinks(connectedLinks)
  }, [graphData])

  const handleNodeHover = useCallback((node: VaultNode | null) => {
    setHoveredNode(node)
  }, [])

  const handleClose = useCallback(() => {
    setSelectedNode(null)
    setHighlightNodes(new Set())
    setHighlightLinks(new Set())
  }, [])

  const handleSearchSelect = useCallback((node: VaultNode) => {
    setSearchOpen(false)
    handleNodeClick(node)
  }, [handleNodeClick])

  const filteredData = graphData ? {
    ...graphData,
    nodes: activeFilter === 'all'
      ? graphData.nodes
      : graphData.nodes.filter(n => n.group === activeFilter),
  } : null

  if (loading) return (
    <div className="flex items-center justify-center h-screen bg-void flex-col gap-4">
      <div className="text-cyan text-lg font-mono loading-pulse glow-cyan">
        INITIALIZING NEURAL NETWORK...
      </div>
      <div className="text-ghost text-sm font-mono">
        Loading vault intelligence graph
      </div>
    </div>
  )

  if (error) return (
    <div className="flex items-center justify-center h-screen bg-void flex-col gap-4 p-8">
      <div className="text-crimson text-xl font-mono glow-red">⚠ NETWORK FAILURE</div>
      <div className="text-ghost font-mono text-sm max-w-md text-center">{error}</div>
      <div className="text-ghost font-mono text-xs mt-4">
        Run: <span className="text-cyan">cd vault-explorer && npm run parse && npm run dev</span>
      </div>
    </div>
  )

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-void select-none">
      {/* Atmospheric overlays */}
      <div className="scanlines" />
      <div className="vignette" />

      {/* 3D Network Graph */}
      {filteredData && (
        <NetworkGraph
          data={filteredData}
          selectedNode={selectedNode}
          highlightNodes={highlightNodes}
          highlightLinks={highlightLinks}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
        />
      )}

      {/* Top header bar */}
      <div className="absolute top-0 left-0 right-0 z-50 flex items-center justify-between px-4 py-2 glass border-b border-border">
        <div className="flex items-center gap-3">
          <span className="text-crimson font-mono text-xs font-bold tracking-widest glow-red">
            ◈ CLASSIFIED
          </span>
          <span className="text-ghost font-mono text-xs">|</span>
          <span className="text-cyan font-mono text-sm font-bold tracking-wider glow-cyan">
            VAULT EXPLORER
          </span>
          <span className="text-ghost font-mono text-xs">|</span>
          <span className="text-ghost font-mono text-xs">
            EPSTEIN NETWORK INTELLIGENCE — 2026 DOJ FILES
          </span>
        </div>
        <div className="flex items-center gap-4">
          {graphData && (
            <span className="text-ghost font-mono text-xs">
              <span className="text-cyan">{graphData.nodes.length}</span> NODES •{' '}
              <span className="text-gold">{graphData.links.length}</span> CONNECTIONS
            </span>
          )}
          <button
            onClick={() => setSearchOpen(true)}
            className="font-mono text-xs text-cyan border border-cyan/30 px-3 py-1 rounded hover:bg-cyan/10 transition-colors"
          >
            ⌕ SEARCH
          </button>
        </div>
      </div>

      {/* Filter bar */}
      {graphData && (
        <FilterBar
          nodes={graphData.nodes}
          activeFilter={activeFilter}
          onFilterChange={setActiveFilter}
        />
      )}

      {/* Stats HUD */}
      {graphData && (
        <StatsHUD data={graphData} selectedNode={selectedNode} />
      )}

      {/* Evidence panel */}
      <AnimatePresence>
        {selectedNode && (
          <EvidencePanel
            node={selectedNode}
            graphData={graphData!}
            onClose={handleClose}
            onNodeSelect={handleNodeClick}
          />
        )}
      </AnimatePresence>

      {/* Search overlay */}
      <AnimatePresence>
        {searchOpen && graphData && (
          <SearchOverlay
            nodes={graphData.nodes}
            onSelect={handleSearchSelect}
            onClose={() => setSearchOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Hover tooltip */}
      {hoveredNode && !selectedNode && (
        <div
          className="node-tooltip pointer-events-none"
          style={{ bottom: 80, left: '50%', transform: 'translateX(-50%)' }}
        >
          <div style={{ color: hoveredNode.color }} className="font-bold text-xs mb-1">
            {hoveredNode.name}
          </div>
          <div className="text-ghost text-xs mb-1">{hoveredNode.summary?.substring(0, 120)}</div>
          <div className="text-ghost/60 text-xs">{hoveredNode.degree} connections · {hoveredNode.group}</div>
        </div>
      )}

      {/* Bottom legend */}
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-50 flex items-center gap-1 font-mono text-xs text-ghost/50">
        CLICK NODE TO REVEAL EVIDENCE · DRAG TO EXPLORE · SCROLL TO ZOOM
      </div>
    </div>
  )
}
