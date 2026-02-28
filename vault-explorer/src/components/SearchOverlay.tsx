import { useState, useRef, useEffect } from 'react'
import { motion } from 'framer-motion'
import type { VaultNode } from '../types'
import { GROUP_META } from '../lib/colors'

interface Props {
  nodes: VaultNode[]
  onSelect: (node: VaultNode) => void
  onClose: () => void
}

export default function SearchOverlay({ nodes, onSelect, onClose }: Props) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  const q = query.toLowerCase().trim()
  const results = q.length < 1
    ? nodes.slice(0, 20)
    : nodes
        .filter(n =>
          n.name.toLowerCase().includes(q) ||
          n.summary.toLowerCase().includes(q) ||
          n.tags.some(t => t.toLowerCase().includes(q)) ||
          n.group.toLowerCase().includes(q) ||
          n.status.toLowerCase().includes(q)
        )
        .slice(0, 30)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh]"
      onClick={onClose}
    >
      <div
        className="glass w-full max-w-2xl mx-4 rounded-lg overflow-hidden shadow-2xl"
        onClick={e => e.stopPropagation()}
        style={{ borderColor: 'rgba(0,212,255,0.2)', boxShadow: '0 0 60px rgba(0,212,255,0.1)' }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <span className="text-cyan font-mono text-sm">⌕</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search persons, evidence, locations, status..."
            className="flex-1 bg-transparent text-white placeholder-ghost/40 font-mono text-sm outline-none"
          />
          <span className="text-ghost/40 font-mono text-xs">ESC to close</span>
        </div>

        {/* Results */}
        <div className="max-h-[50vh] overflow-y-auto">
          {results.length === 0 ? (
            <div className="text-ghost/40 font-mono text-sm text-center py-8">NO MATCHES</div>
          ) : (
            results.map(node => {
              const meta = GROUP_META[node.group] ?? GROUP_META.other
              return (
                <button
                  key={node.id}
                  onClick={() => onSelect(node)}
                  className="w-full text-left px-4 py-3 hover:bg-white/5 transition-colors border-b border-border/50 flex items-start gap-3"
                >
                  <span style={{ color: node.color, fontSize: 16, flexShrink: 0 }}>{meta.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span style={{ color: node.color }} className="font-semibold text-sm">
                        {node.name}
                      </span>
                      <span
                        className="font-mono text-xs px-1.5 py-0.5 rounded border"
                        style={{ color: `${node.color}99`, borderColor: `${node.color}33`, background: `${node.color}11` }}
                      >
                        {meta.label}
                      </span>
                      <span className="font-mono text-xs text-ghost/40">
                        {node.degree}↔
                      </span>
                    </div>
                    <div className="text-ghost/60 text-xs line-clamp-1">
                      {node.summary}
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-border flex items-center justify-between">
          <span className="font-mono text-xs text-ghost/30">
            {results.length} results
          </span>
          <span className="font-mono text-xs text-ghost/30">
            {nodes.length} total nodes indexed
          </span>
        </div>
      </div>
    </motion.div>
  )
}
