export type NodeType = 'person' | 'finding' | 'location' | 'event' | 'investigation' | 'other'

export type NodeGroup =
  | 'convicted' | 'deceased' | 'arrested' | 'banned' | 'immunity'
  | 'victim' | 'journalist' | 'intelligence' | 'financial' | 'political'
  | 'academic' | 'location' | 'finding' | 'person_other' | 'investigation' | 'other'

export type LinkType = 'financial' | 'intelligence' | 'location' | 'associates' | 'network' | 'evidence' | 'mentions'

export interface VaultNode {
  id: string
  name: string
  type: NodeType
  group: NodeGroup
  status: string
  tags: string[]
  date: string | null
  summary: string
  content: string
  color: string
  val: number
  degree: number
  // ForceGraph3D runtime position fields
  x?: number
  y?: number
  z?: number
  vx?: number
  vy?: number
  vz?: number
  fx?: number | null
  fy?: number | null
  fz?: number | null
}

export interface VaultLink {
  source: string | VaultNode
  target: string | VaultNode
  type: LinkType
  color: string
}

export interface GraphData {
  nodes: VaultNode[]
  links: VaultLink[]
  metadata: {
    generatedAt: string
    nodeCount: number
    linkCount: number
    groups: string[]
  }
}

export type FilterGroup = NodeGroup | 'all'
