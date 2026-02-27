---
tags: [hub, index]
created: 2026-02-27
---

# Home

> Central hub for this research vault. Start here.

---

## Navigation

| Section | Description |
|---------|-------------|
| [[Investigations/README\|Investigations]] | Active and closed case files |
| [[Timeline]] | Chronological event log |
| [[Findings/README\|Findings]] | Evidence and research notes |
| [[People/README\|People]] | Person profiles |
| [[Locations/README\|Locations]] | Location notes |
| [[SOPs/README\|SOPs]] | Standard Operating Procedures |
| [[vault]] | Vault structure reference |
| [[obsidian]] | Setup guide & plugin config |

---

## Quick Add

- `osint-investigation` — Start a new case
- `osint-person` — New person of interest
- `osint-domain-ip` — Domain / IP investigation
- `osint-person` — Detailed person intel note
- [[Templates/finding-template]] — Log a finding
- [[Templates/timeline-entry]] — Add timeline entry

---

## Active Investigations

```dataview
TABLE status, priority, date AS "Opened"
FROM "Investigations"
WHERE (status = "active" OR status = "open") AND file.name != "README"
SORT priority DESC, date DESC
```

---

## Recent Activity

```dataview
TABLE file.mtime AS "Modified", tags
FROM ""
WHERE file.name != "Home"
SORT file.mtime DESC
LIMIT 10
```

---

## People of Interest

```dataview
LIST FROM #poi
SORT file.name ASC
```

## All Findings

```dataview
TABLE date, summary, tags FROM "Findings"
SORT date DESC
```
