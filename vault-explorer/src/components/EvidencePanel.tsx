import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { VaultNode, GraphData } from '../types'
import { GROUP_META } from '../lib/colors'

interface Props {
  node: VaultNode
  graphData: GraphData
  onClose: () => void
  onNodeSelect: (node: VaultNode) => void
}

export default function EvidencePanel({ node, graphData, onClose, onNodeSelect }: Props) {
  const meta = GROUP_META[node.group] ?? GROUP_META.other
  const color = node.color

  // Find connected nodes
  const connectedNodes: VaultNode[] = []
  for (const link of graphData.links) {
    const src = typeof link.source === 'string' ? link.source : (link.source as VaultNode).id
    const tgt = typeof link.target === 'string' ? link.target : (link.target as VaultNode).id

    let otherId: string | null = null
    if (src === node.id) otherId = tgt
    else if (tgt === node.id) otherId = src

    if (otherId) {
      const found = graphData.nodes.find(n => n.id === otherId)
      if (found && !connectedNodes.find(n => n.id === found.id)) {
        connectedNodes.push(found)
      }
    }
  }

  // Sort by degree
  connectedNodes.sort((a, b) => b.degree - a.degree)

  // Clean markdown: replace WikiLinks with bold text
  const cleanContent = (node.content || '')
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, '**$2**')
    .replace(/\[\[([^\]]+)\]\]/g, '**$1**')
    .replace(/^---[\s\S]*?---\n/, '') // remove frontmatter if present

  return (
    <motion.div
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      className="absolute top-0 right-0 h-full z-50 flex flex-col glass"
      style={{
        width: 'min(520px, 42vw)',
        borderLeft: `1px solid ${color}33`,
        boxShadow: `-20px 0 60px ${color}11`,
      }}
    >
      {/* Header */}
      <div
        className="flex items-start justify-between p-4 border-b"
        style={{ borderColor: `${color}22` }}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span
              className="badge"
              style={{ color, borderColor: `${color}55`, background: `${color}15` }}
            >
              {meta.icon} {meta.label}
            </span>
            {node.status && (
              <span className="font-mono text-xs text-ghost/60 uppercase tracking-widest">
                {node.status.replace(/-/g, ' ')}
              </span>
            )}
          </div>
          <h2
            className="text-xl font-bold leading-tight"
            style={{ color, textShadow: `0 0 20px ${color}44` }}
          >
            {node.name}
          </h2>
          {node.summary && (
            <p className="text-ghost text-xs mt-2 leading-relaxed line-clamp-3">
              {node.summary}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="ml-3 mt-1 text-ghost hover:text-white transition-colors font-mono text-lg flex-shrink-0"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      {/* Tags */}
      {node.tags.length > 0 && (
        <div className="px-4 py-2 border-b border-border flex flex-wrap gap-1">
          {node.tags.map(tag => (
            <span
              key={tag}
              className="font-mono text-xs px-2 py-0.5 rounded text-ghost/60 border border-border"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* Connections */}
      {connectedNodes.length > 0 && (
        <div className="px-4 py-3 border-b border-border">
          <div className="font-mono text-xs text-ghost/50 uppercase tracking-wider mb-2">
            {connectedNodes.length} Connections
          </div>
          <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
            {connectedNodes.map(n => (
              <button
                key={n.id}
                onClick={() => onNodeSelect(n)}
                className="font-mono text-xs px-2 py-1 rounded border transition-all hover:opacity-100"
                style={{
                  color: n.color,
                  borderColor: `${n.color}33`,
                  background: `${n.color}0d`,
                  opacity: 0.85,
                }}
              >
                {GROUP_META[n.group]?.icon} {n.name.split(' ').slice(0, 3).join(' ')}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Degree bar */}
      <div className="px-4 py-2 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <span className="font-mono text-xs text-ghost/50 uppercase tracking-wider">Network Centrality</span>
          <span className="font-mono text-xs" style={{ color }}>{node.degree} links</span>
        </div>
        <div className="w-full h-1 bg-surface rounded overflow-hidden">
          <div
            className="h-full rounded transition-all"
            style={{
              width: `${Math.min(100, (node.degree / 20) * 100)}%`,
              background: `linear-gradient(90deg, ${color}, ${color}88)`,
              boxShadow: `0 0 8px ${color}`,
            }}
          />
        </div>
      </div>

      {/* Markdown content */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {cleanContent ? (
          <div className="vault-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanContent}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="text-ghost/40 font-mono text-xs text-center mt-8">
            NO CONTENT AVAILABLE
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        className="px-4 py-2 border-t flex items-center justify-between"
        style={{ borderColor: `${color}22` }}
      >
        <span className="font-mono text-xs text-ghost/30">
          {node.id}
        </span>
        {node.date && (
          <span className="font-mono text-xs" style={{ color: `${color}88` }}>
            {node.date}
          </span>
        )}
      </div>
    </motion.div>
  )
}
