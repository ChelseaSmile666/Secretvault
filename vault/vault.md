---
tags: [meta, structure]
created: 2026-02-27
---

# Vault Structure

> Reference map of this vault — folders, files, conventions, and schema.

---

## Folder Map

```
vault/
├── Home.md                        ← Landing page (Obsidian opens this)
├── vault.md                       ← This file — structural reference
├── obsidian.md                    ← Setup guide & plugin config
├── Timeline.md                    ← Chronological event log
│
├── Investigations/
│   ├── README.md                  ← Case index (Dataview table)
│   └── <Case-Name>/               ← One subfolder per investigation
│       └── <Case-Name>.md         ← Investigation index note
│
├── Findings/
│   ├── README.md                  ← Findings index (Dataview table)
│   └── <finding-name>.md          ← One file per finding/evidence note
│
├── People/
│   ├── README.md                  ← People index (Dataview table)
│   └── <Firstname-Lastname>.md    ← One file per person
│
├── Locations/
│   ├── README.md                  ← Locations index (Dataview list)
│   └── <City-Venue>.md            ← One file per location
│
├── SOPs/
│   ├── README.md                  ← SOP index
│   ├── Email-Address.md           ← Email investigation steps
│   ├── Username.md                ← Username investigation steps
│   ├── Phone-Number.md            ← Phone investigation steps
│   ├── Domain-Name.md             ← Domain investigation steps
│   ├── IP-Address.md              ← IP investigation steps
│   ├── URL.md                     ← URL investigation steps
│   ├── Physical-Address.md        ← Address investigation steps
│   ├── Image-Analysis.md          ← Image OSINT steps
│   ├── Search-Engine.md           ← Search engine dorks + tips
│   ├── Breach-Data.md             ← Breach database lookups
│   ├── Business-Name.md           ← Company research steps
│   ├── Computer-Infrastructure.md ← Server/infra recon steps
│   ├── Encryption-Certificates.md ← TLS/cert research steps
│   ├── GPS-Coordinates.md         ← Geolocation steps
│   └── People-Search-Engine.md    ← People search tools
│
├── Templates/
│   ├── osint-person.md            ← OSINT person of interest
│   ├── osint-domain-ip.md         ← Domain/IP investigation
│   ├── osint-investigation.md     ← Case/investigation index
│   ├── person-template.md         ← General person profile
│   ├── finding-template.md        ← General finding note
│   └── timeline-entry.md          ← Timeline event entry
│
└── .obsidian/                     ← Obsidian config (auto-managed)
```

---

## File Naming

| Section | Convention | Example |
|---------|-----------|---------|
| People | `Firstname-Lastname.md` | `John-Smith.md` |
| Findings | `YYYY-MM-DD-short-title.md` | `2026-02-27-data-breach.md` |
| Locations | `City-Venue.md` | `London-Waterloo-Station.md` |
| Timeline entries | Added inline in `Timeline.md` | — |

---

## Tag Taxonomy

| Tag | Applied To | Meaning |
|-----|-----------|---------|
| `#person` | People/ | Individual profile |
| `#poi` | People/ | Person of interest (active subject) |
| `#location` | Locations/ | Place or venue |
| `#event` | Timeline entries | Dated occurrence |
| `#investigation` | Investigations/ | Case/investigation index |
| `#finding` | Findings/ | Verified — multiple independent sources |
| `#claim` | Findings/ | Unverified — single source or contested |
| `#myth` | Findings/ | Debunked or no credible sourcing |
| `#document` | Any | Primary source document reference |
| `#sop` | SOPs/ | Standard operating procedure |
| `#meta` | vault/, Home.md | Vault housekeeping notes |

---

## Frontmatter Schema

### People
```yaml
---
tags: [person]
role:
status: active        # active | inactive | unknown | deceased
aliases: []
---
```

### Findings
```yaml
---
tags: [finding]       # or claim / myth
date: YYYY-MM-DD
summary:
verified: false
---
```

### Timeline entries
```yaml
---
tags: [event]
date: YYYY-MM-DD
---
```

### Locations
```yaml
---
tags: [location]
coordinates:          # optional lat,lng
---
```

---

## Linking Convention

All cross-references use `[[WikiLinks]]`:

| Link | Target |
|------|--------|
| `[[Home]]` | Landing page |
| `[[Timeline]]` | Event log |
| `[[Findings/README]]` | Findings index |
| `[[People/README]]` | People index |
| `[[Locations/README]]` | Locations index |
| `[[People/John-Smith]]` | Specific person |
| `[[Findings/2026-02-27-title]]` | Specific finding |

Always link back to the section README from individual notes.

---

## Section Relationships

```
Home
 ├── Timeline ──────────────────> events reference People + Locations
 ├── Findings/README
 │    └── finding notes ────────> link to People + Locations
 ├── People/README
 │    └── person notes ─────────> link to Findings + Locations
 └── Locations/README
      └── location notes ───────> link to People + Findings
```

---

## Adding New Notes

1. Open template from `Templates/` (`Ctrl/Cmd+P` → *Insert template*)
2. Save into the correct section folder
3. Fill frontmatter fields
4. Link back to section README and relevant notes
5. Add entry to `Timeline.md` if date-relevant

## Starting an Investigation

1. Create `Investigations/<Case-Name>/` folder
2. Insert `osint-investigation` template → fill objectives and subjects
3. For each person: create `People/<Name>.md` using `osint-person` template
4. For each domain/IP: create `Findings/<target>.md` using `osint-domain-ip` template
5. Run the relevant [[SOPs/README]] for every selector found
6. Log all events in [[Timeline]]

---

*See [[Home]] for the live dashboard · [[obsidian]] for plugin setup*
