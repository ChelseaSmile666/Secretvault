import type { VaultNode, FilterGroup, NodeGroup } from '../types'
import { GROUP_META } from '../lib/colors'

interface Props {
  nodes: VaultNode[]
  activeFilter: FilterGroup
  onFilterChange: (f: FilterGroup) => void
}

export default function FilterBar({ nodes, activeFilter, onFilterChange }: Props) {
  // Count by group
  const counts = new Map<string, number>()
  for (const n of nodes) {
    counts.set(n.group, (counts.get(n.group) || 0) + 1)
  }

  // Only show groups with nodes, ordered by priority
  const priority: NodeGroup[] = [
    'convicted', 'arrested', 'banned', 'immunity',
    'political', 'financial', 'intelligence',
    'victim', 'academic', 'journalist',
    'location', 'finding', 'deceased', 'person_other',
  ]

  const visibleGroups = priority.filter(g => (counts.get(g) || 0) > 0)

  return (
    <div className="absolute left-3 top-16 z-50 flex flex-col gap-1.5 max-h-[calc(100vh-120px)] overflow-y-auto py-2">
      {/* All filter */}
      <button
        onClick={() => onFilterChange('all')}
        className="filter-btn text-left"
        style={{
          color: activeFilter === 'all' ? '#00d4ff' : '#666688',
          borderColor: activeFilter === 'all' ? '#00d4ff44' : 'transparent',
          background: activeFilter === 'all' ? '#00d4ff15' : 'rgba(8,8,24,0.7)',
        }}
      >
        ◈ ALL  <span style={{ color: '#ffffff44' }}>{nodes.length}</span>
      </button>

      <div className="w-full h-px bg-border my-1" />

      {visibleGroups.map(group => {
        const meta = GROUP_META[group]
        const count = counts.get(group) || 0
        const active = activeFilter === group
        return (
          <button
            key={group}
            onClick={() => onFilterChange(active ? 'all' : group)}
            className="filter-btn text-left"
            style={{
              color: active ? meta.color : '#555577',
              borderColor: active ? `${meta.color}44` : 'transparent',
              background: active ? `${meta.color}15` : 'rgba(8,8,24,0.7)',
              boxShadow: active ? `0 0 12px ${meta.color}22` : 'none',
            }}
          >
            {meta.icon} {meta.label.toUpperCase()}
            <span style={{ color: active ? `${meta.color}99` : '#33334a', marginLeft: 4 }}>
              {count}
            </span>
          </button>
        )
      })}
    </div>
  )
}
