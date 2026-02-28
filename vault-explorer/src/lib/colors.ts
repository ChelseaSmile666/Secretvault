import type { NodeGroup, LinkType } from '../types'

export const GROUP_META: Record<string, { color: string; label: string; icon: string; description: string }> = {
  convicted:    { color: '#ff2244', label: 'Convicted',        icon: '⛓',  description: 'Federal conviction' },
  deceased:     { color: '#8888aa', label: 'Deceased',         icon: '†',   description: 'Died before or after investigation' },
  arrested:     { color: '#ff6600', label: 'Arrested 2026',    icon: '🚨',  description: 'Arrested in 2026 DOJ action' },
  banned:       { color: '#ffaa00', label: 'Sanctioned',       icon: '⛔',  description: 'Regulatory ban or sanction' },
  immunity:     { color: '#cc44ff', label: 'NPA Immunity',     icon: '🛡',  description: 'Protected under 2008 NPA' },
  victim:       { color: '#ff88aa', label: 'Victim/Accuser',   icon: '◉',   description: 'Documented victim or accuser' },
  journalist:   { color: '#44ddff', label: 'Journalist',       icon: '✎',   description: 'Investigative reporter' },
  intelligence: { color: '#00ffff', label: 'Intelligence',     icon: '◈',   description: 'Intelligence community connection' },
  financial:    { color: '#ffd700', label: 'Financial',        icon: '◆',   description: 'Financial institution or banker' },
  political:    { color: '#9944ff', label: 'Political',        icon: '✦',   description: 'Political figure or official' },
  academic:     { color: '#44ff88', label: 'Academic',         icon: '◎',   description: 'Academic or technology figure' },
  location:     { color: '#00ff88', label: 'Location',         icon: '◉',   description: 'Property or key location' },
  finding:      { color: '#ff8800', label: 'Evidence',         icon: '⬡',   description: 'Evidence or finding' },
  person_other: { color: '#5588ff', label: 'Associate',        icon: '○',   description: 'Known associate' },
  investigation:{ color: '#ffffff', label: 'Investigation',    icon: '◈',   description: 'Investigation record' },
  other:        { color: '#666688', label: 'Other',            icon: '·',   description: 'Other' },
}

export const LINK_COLORS: Record<LinkType, { stroke: string; particle: string; label: string }> = {
  financial:    { stroke: '#ffd70066', particle: '#ffd700', label: 'Financial' },
  intelligence: { stroke: '#00ffff66', particle: '#00ffff', label: 'Intelligence' },
  location:     { stroke: '#00ff8866', particle: '#00ff88', label: 'Location' },
  associates:   { stroke: '#5588ff44', particle: '#5588ff', label: 'Associates' },
  network:      { stroke: '#ff224444', particle: '#ff2244', label: 'Network' },
  evidence:     { stroke: '#ff880044', particle: '#ff8800', label: 'Evidence' },
  mentions:     { stroke: '#ffffff18', particle: '#ffffff', label: 'Mentions' },
}

export function getNodeColor(group: NodeGroup | string): string {
  return GROUP_META[group]?.color ?? '#666688'
}

export function getLinkParticleColor(type: LinkType | string): string {
  return LINK_COLORS[type as LinkType]?.particle ?? '#ffffff'
}

export function getStatusBadgeStyle(group: NodeGroup | string): string {
  const color = getNodeColor(group)
  return `color: ${color}; border-color: ${color}40; background: ${color}15;`
}
