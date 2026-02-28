import type { GraphData, VaultNode } from '../types'
import { GROUP_META } from '../lib/colors'

interface Props {
  data: GraphData
  selectedNode: VaultNode | null
}

const ALERT_GROUPS = ['convicted', 'arrested', 'banned']

export default function StatsHUD({ data, selectedNode }: Props) {
  const convicted = data.nodes.filter(n => n.group === 'convicted').length
  const arrested = data.nodes.filter(n => n.group === 'arrested').length
  const immunity = data.nodes.filter(n => n.group === 'immunity').length
  const deceased = data.nodes.filter(n => n.group === 'deceased').length
  const alertNodes = data.nodes.filter(n => ALERT_GROUPS.includes(n.group))

  return (
    <div className="absolute bottom-8 right-4 z-50 flex flex-col gap-2 items-end">
      {/* Alert indicators */}
      {alertNodes.map(n => (
        <div
          key={n.id}
          className="font-mono text-xs px-2 py-1 rounded flex items-center gap-2"
          style={{
            color: n.color,
            background: `${n.color}15`,
            border: `1px solid ${n.color}44`,
            boxShadow: `0 0 10px ${n.color}22`,
          }}
        >
          <span style={{ animation: 'pulse 1.5s infinite' }}>●</span>
          {n.name.toUpperCase()}
          <span className="text-ghost/50">{GROUP_META[n.group]?.label?.toUpperCase()}</span>
        </div>
      ))}

      {/* Stats block */}
      <div className="glass rounded-lg px-3 py-2 min-w-[160px]">
        <div className="font-mono text-xs text-ghost/40 uppercase tracking-wider mb-2 text-right">
          Network Status
        </div>
        <div className="space-y-1">
          {[
            { label: 'CONVICTED', value: convicted, color: '#ff2244' },
            { label: 'ARRESTED', value: arrested, color: '#ff6600' },
            { label: 'NPA IMMUNITY', value: immunity, color: '#cc44ff' },
            { label: 'DECEASED', value: deceased, color: '#8888aa' },
          ].map(({ label, value, color }) => (
            <div key={label} className="flex items-center justify-between gap-4">
              <span className="font-mono text-xs text-ghost/40">{label}</span>
              <span className="font-mono text-xs font-bold" style={{ color }}>
                {value}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 pt-2 border-t border-border">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-ghost/40">AS OF</span>
            <span className="font-mono text-xs text-cyan">2026-02-28</span>
          </div>
        </div>
      </div>
    </div>
  )
}
