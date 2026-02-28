/**
 * build-graph-data.mjs
 * Parses the Epstein vault markdown files into a graph JSON
 * for the neural network visualization.
 */

import { readFileSync, readdirSync, statSync, writeFileSync, existsSync } from 'fs'
import { join, relative, basename, extname, dirname } from 'path'
import { fileURLToPath } from 'url'
import matter from 'gray-matter'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const VAULT_ROOT = join(__dirname, '../../vault')
const OUTPUT_FILE = join(__dirname, '../public/vault-data.json')

// ── Node type detection ────────────────────────────────────────────────────

function getNodeType(relPath, frontmatter) {
  const tags = frontmatter.tags || []
  if (relPath.startsWith('People/')) return 'person'
  if (relPath.startsWith('Findings/')) return 'finding'
  if (relPath.startsWith('Locations/')) return 'location'
  if (relPath.startsWith('Timeline')) return 'event'
  if (relPath.startsWith('Investigations/')) return 'investigation'
  if (tags.includes('finding')) return 'finding'
  if (tags.includes('person')) return 'person'
  return 'other'
}

function getNodeGroup(frontmatter, type) {
  const tags = frontmatter.tags || []
  const status = frontmatter.status || ''

  if (tags.includes('convicted') || status === 'incarcerated') return 'convicted'
  if (tags.includes('deceased') || status === 'deceased') return 'deceased'
  if (status === 'arrested-released-under-investigation') return 'arrested'
  if (tags.includes('fca-banned') || status === 'banned-from-uk-finance') return 'banned'
  if (tags.includes('npa-immunity')) return 'immunity'
  if (tags.includes('victim') || tags.includes('plaintiff')) return 'victim'
  if (tags.includes('journalist')) return 'journalist'
  if (tags.includes('intelligence') || tags.includes('intel')) return 'intelligence'
  if (tags.includes('financial') || tags.includes('banker')) return 'financial'
  if (tags.includes('political') || tags.includes('public-official')) return 'political'
  if (tags.includes('academic')) return 'academic'
  if (type === 'location') return 'location'
  if (type === 'finding') return 'finding'
  if (type === 'person') return 'person_other'
  return 'other'
}

// ── Color mapping ──────────────────────────────────────────────────────────

const GROUP_COLORS = {
  convicted:    '#ff2244',  // hot red
  deceased:     '#8888aa',  // muted gray-blue
  arrested:     '#ff6600',  // urgent orange
  banned:       '#ffaa00',  // amber
  immunity:     '#cc44ff',  // purple
  victim:       '#ff88aa',  // soft pink
  journalist:   '#44ddff',  // light cyan
  intelligence: '#00ffff',  // full cyan
  financial:    '#ffd700',  // gold
  political:    '#9944ff',  // violet
  academic:     '#44ff88',  // mint
  location:     '#00ff88',  // emerald
  finding:      '#ff8800',  // orange
  person_other: '#5588ff',  // blue
  investigation:'#ffffff',  // white
  other:        '#666688',  // dim
}

// ── WikiLink extraction ────────────────────────────────────────────────────

function extractWikiLinks(content) {
  const links = []
  // Match [[Target]] and [[Target|Label]] and [[Target#Section]]
  const regex = /\[\[([^\]|#]+)(?:[|#][^\]]*)?]]/g
  let match
  while ((match = regex.exec(content)) !== null) {
    const raw = match[1].trim()
    // Normalize: remove leading slashes, fix separators
    const normalized = raw.replace(/\\/g, '/').replace(/^\//, '')
    links.push(normalized)
  }
  return [...new Set(links)]
}

// ── File walker ────────────────────────────────────────────────────────────

function walkVault(dir, baseDir = dir) {
  const files = []
  const entries = readdirSync(dir)
  for (const entry of entries) {
    const fullPath = join(dir, entry)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      // Skip SOPs, Templates, Media
      const skip = ['SOPs', 'Templates', 'Media', '__pycache__', '.git']
      if (!skip.includes(entry)) {
        files.push(...walkVault(fullPath, baseDir))
      }
    } else if (entry.endsWith('.md') && !entry.startsWith('README') && entry !== 'obsidian.md' && entry !== 'vault.md' && entry !== 'Home.md') {
      files.push({ fullPath, relPath: relative(baseDir, fullPath).replace(/\\/g, '/') })
    }
  }
  return files
}

// ── Node name extraction ───────────────────────────────────────────────────

function extractName(frontmatter, relPath) {
  if (frontmatter.title) return frontmatter.title
  // Derive from filename
  const fname = basename(relPath, '.md')
  // Convert hyphen-case to spaces
  return fname.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function extractSummary(content, frontmatter) {
  if (frontmatter.summary) return frontmatter.summary
  // First non-empty line after frontmatter that isn't a heading or HR
  const lines = content.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed && !trimmed.startsWith('#') && !trimmed.startsWith('---') && !trimmed.startsWith('>') && trimmed.length > 20) {
      return trimmed.substring(0, 200)
    }
  }
  // Blockquote (vault uses > for status summaries)
  for (const line of lines) {
    const trimmed = line.trim()
    if (trimmed.startsWith('> ')) {
      return trimmed.substring(2, 220)
    }
  }
  return ''
}

// ── Relationship type inference ────────────────────────────────────────────

function inferLinkType(sourceType, sourceGroup, targetId) {
  const t = targetId.toLowerCase()
  if (t.includes('findings/financial') || t.includes('financial-network') || t.includes('financial-institution')) return 'financial'
  if (t.includes('findings/intelligence') || t.includes('intelligence')) return 'intelligence'
  if (t.includes('locations/')) return 'location'
  if (t.includes('people/')) {
    if (sourceGroup === 'financial' || sourceGroup === 'convicted') return 'network'
    return 'associates'
  }
  if (t.includes('findings/')) return 'evidence'
  return 'mentions'
}

// ── Main build ─────────────────────────────────────────────────────────────

function build() {
  console.log(`\n🔍 Parsing vault at: ${VAULT_ROOT}\n`)

  if (!existsSync(VAULT_ROOT)) {
    console.error(`❌ Vault not found at ${VAULT_ROOT}`)
    process.exit(1)
  }

  const files = walkVault(VAULT_ROOT)
  console.log(`📄 Found ${files.length} markdown files`)

  const nodeMap = new Map()
  const rawLinks = []

  // ── Pass 1: Build nodes ──────────────────────────────────────────────────
  for (const { fullPath, relPath } of files) {
    const raw = readFileSync(fullPath, 'utf-8')
    let parsed
    try {
      parsed = matter(raw)
    } catch {
      console.warn(`  ⚠ Could not parse: ${relPath}`)
      continue
    }

    const { data: fm, content } = parsed
    const type = getNodeType(relPath, fm)
    const group = getNodeGroup(fm, type)
    const name = extractName(fm, relPath)
    const summary = extractSummary(content, fm)
    const id = relPath.replace(/\.md$/, '')

    // Extract wiki links for edge building
    const links = extractWikiLinks(content)

    const node = {
      id,
      name,
      type,
      group,
      status: fm.status || '',
      tags: fm.tags || [],
      date: fm.date || null,
      summary,
      content: content.substring(0, 6000), // cap at 6KB per node
      color: GROUP_COLORS[group] || GROUP_COLORS.other,
      val: 1, // will be updated with degree
      links, // temporary, used for edge building
    }

    nodeMap.set(id, node)

    // Also register common WikiLink variants
    const variants = [
      id,
      basename(id), // just the filename
      relPath.replace(/\.md$/, ''),
    ]
    for (const v of variants) {
      if (!nodeMap.has(v)) nodeMap.set(v, node)
    }

    rawLinks.push({ sourceId: id, targets: links })
  }

  console.log(`✅ Built ${nodeMap.size} node entries`)

  // ── Pass 2: Build edges ──────────────────────────────────────────────────
  const linkSet = new Set()
  const links = []

  for (const { sourceId, targets } of rawLinks) {
    const sourceNode = nodeMap.get(sourceId)
    if (!sourceNode) continue

    for (const target of targets) {
      // Try various normalizations to find the target node
      const candidates = [
        target,
        target + '.md'.replace('.md.md', '.md'),
        target.replace(/^.*\//, ''), // basename only lookup
      ]

      let targetNode = null
      for (const c of candidates) {
        // Search all nodes for matching id
        for (const [nid, n] of nodeMap) {
          if (nid === c || n.id === c || basename(nid) === c) {
            targetNode = n
            break
          }
        }
        if (targetNode) break
      }

      if (!targetNode || targetNode.id === sourceNode.id) continue

      // Canonical edge key (undirected dedup)
      const edgeKey = [sourceNode.id, targetNode.id].sort().join('||')
      if (linkSet.has(edgeKey)) continue
      linkSet.add(edgeKey)

      const linkType = inferLinkType(sourceNode.type, sourceNode.group, targetNode.id)

      links.push({
        source: sourceNode.id,
        target: targetNode.id,
        type: linkType,
        color: getLinkColor(linkType),
      })
    }
  }

  // ── Pass 3: Compute degree (node size) ────────────────────────────────────
  const degree = new Map()
  for (const link of links) {
    degree.set(link.source, (degree.get(link.source) || 0) + 1)
    degree.set(link.target, (degree.get(link.target) || 0) + 1)
  }

  // Get unique nodes (deduplicated by id)
  const seenIds = new Set()
  const nodes = []
  for (const [, node] of nodeMap) {
    if (seenIds.has(node.id)) continue
    seenIds.add(node.id)
    const deg = degree.get(node.id) || 0
    nodes.push({
      ...node,
      links: undefined, // remove temp field
      val: Math.max(1, deg),
      degree: deg,
    })
  }

  // Sort nodes by degree descending (most connected first)
  nodes.sort((a, b) => b.degree - a.degree)

  const output = {
    nodes,
    links,
    metadata: {
      generatedAt: new Date().toISOString(),
      nodeCount: nodes.length,
      linkCount: links.length,
      vaultRoot: VAULT_ROOT,
      groups: [...new Set(nodes.map(n => n.group))],
    }
  }

  writeFileSync(OUTPUT_FILE, JSON.stringify(output, null, 2))
  console.log(`\n✅ Graph written to: ${OUTPUT_FILE}`)
  console.log(`   Nodes: ${nodes.length}`)
  console.log(`   Links: ${links.length}`)
  console.log(`   Top nodes by degree:`)
  nodes.slice(0, 10).forEach(n => {
    console.log(`     ${n.name.padEnd(40)} ${n.degree} connections  [${n.group}]`)
  })
  console.log()
}

function getLinkColor(type) {
  const colors = {
    financial:    '#ffd70088',
    intelligence: '#00ffff88',
    location:     '#00ff8888',
    associates:   '#5588ff55',
    network:      '#ff224455',
    evidence:     '#ff880055',
    mentions:     '#ffffff22',
  }
  return colors[type] || '#ffffff22'
}

build()
