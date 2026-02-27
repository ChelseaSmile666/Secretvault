---
tags: [investigations, meta]
---

# Investigations

> Active and closed case files. Each investigation has its own subfolder.

---

## Active Cases

```dataview
TABLE status, priority, date AS "Opened"
FROM "Investigations"
WHERE status = "active" OR status = "open"
SORT priority DESC, date DESC
```

---

## All Cases

```dataview
TABLE status, priority, date AS "Opened"
FROM "Investigations"
WHERE file.name != "README"
SORT date DESC
```

---

## Starting a New Investigation

1. Create subfolder: `Investigations/Case-Name/`
2. Create index note from template: `Ctrl/Cmd+P` → *Insert template* → `osint-investigation`
3. Add people to `People/` using `osint-person` template
4. Add domains/IPs to `Findings/` using `osint-domain-ip` template
5. Log all events in `Timeline.md`
6. Run relevant [[SOPs/README]] for each selector found

---

*[[Home]] · [[vault]] · [[SOPs/README]]*
