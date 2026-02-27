---
tags: [investigation, case]
date: {{date}}
status: open       # open | active | closed | on-hold
priority: medium   # low | medium | high | critical
---

# {{case-name}} — Investigation

## Overview
> One paragraph summary of what this investigation is about.

---

## Objectives
1.
2.
3.

---

## Key Subjects

| Name | Role | Note |
|------|------|------|
| [[]] | | |

---

## Key Domains / IPs

| Target | Type | Note |
|--------|------|------|
| [[]] | domain / ip | |

---

## Timeline

| Date | Event | Source |
|------|-------|--------|
| {{date}} | Investigation opened | |

---

## Findings

```dataview
LIST FROM "Investigations/{{case-name}}"
WHERE contains(tags, "finding")
SORT date DESC
```

---

## Tasks
- [ ] Initial reconnaissance
- [ ] Identify key subjects
- [ ] Map infrastructure

---

## Notes

---

## Sources
1.

---

*Related: [[Investigations/README]] · [[Timeline]] · [[vault]]*
