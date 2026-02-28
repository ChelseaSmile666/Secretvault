#!/usr/bin/env python3
"""
vault_writer.py — Autonomous document writer for the Epstein Investigation Vault.

Uses the Anthropic API directly (bypasses Claude Code plan limits entirely).
Each task calls the API with a specialist prompt and writes the result straight
to the correct vault path.  All 22 pending deep-research documents are baked in
as tasks — just run the script and they all get written.

USAGE
-----
  python vault_writer.py                        # write all pending docs (sonnet)
  python vault_writer.py --opus                 # use opus-4-6 (higher quality)
  python vault_writer.py --task timeline        # single task by ID
  python vault_writer.py --list                 # show all task IDs and status
  python vault_writer.py --dry-run              # preview paths/prompts, no writes
  python vault_writer.py --force                # overwrite existing files
  python vault_writer.py --sequential           # no threads, one at a time
  python vault_writer.py --task people          # write all people profiles

SCHEDULING (Windows Task Scheduler)
-------------------------------------
  schtasks /create /tn "VaultWriter" /tr "python C:\\...\\vault_writer.py --opus"
            /sc DAILY /st 00:05 /f
"""

import sys
import os
import time
import threading
import argparse
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic")
    sys.exit(1)

# ── Paths ──────────────────────────────────────────────────────────────────────

UTILS_DIR  = Path(__file__).parent.resolve()
VAULT_ROOT = UTILS_DIR.parent.resolve()
LOG_DIR    = UTILS_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL    = "claude-opus-4-6"

DATE = "2026-02-28"

# ── Shared writer system prompt ────────────────────────────────────────────────

WRITER_SYSTEM = f"""You are a world-class investigative researcher, intelligence analyst, and legal scholar
writing for the definitive Epstein Investigation Vault.

MANDATORY STANDARDS for every document:
1. APA 7th edition in-text citations (Author, Year) and full reference list at end
2. Confidence ratings on every substantive claim:
   [CONFIRMED]   = court conviction / DOJ statement / regulatory finding
   [CORROBORATED]= multiple independent credible sources
   [SINGLE SOURCE]= one credible outlet or document
   [UNVERIFIED]  = alleged but unconfirmed
3. Tag #claim on ALL negative characterisations of living non-convicted persons
4. Mermaid diagrams (```mermaid blocks) for network/process visualisations
5. YAML frontmatter block at top: tags, date: {DATE}, summary, verified, source
6. Intelligence-style precision: no sensationalism, no speculation beyond rated confidence
7. Minimum length per task as specified — write fully, do not truncate
8. Sources: DOJ files (justice.gov/epstein), PACER, court records, established major journalism only

Today's date is {DATE}. All content reflects the evidentiary record as of this date.
"""

# ── Task definitions ───────────────────────────────────────────────────────────
# Each task: id, description, output_path (relative to VAULT_ROOT), prompt

TASKS = [

    # ── People profiles ─────────────────────────────────────────────────────

    dict(
        id="sultan",
        group="people",
        description="Sultan bin Sulayem — DP World CEO profile",
        output="People/Sultan-bin-Sulayem.md",
        prompt=f"""Write a comprehensive vault profile for Sultan Ahmed bin Sulayem.

YAML frontmatter: tags: [person, financial, political, doj-2026, documented], date: {DATE},
name: Sultan Ahmed bin Sulayem, group: financial, status: departed,
summary: DP World Chairman/CEO identified in DOJ file EFTA00666117; departed position Feb 2026.

Sections to cover (minimum 200 lines total):
1. Background — Who is he: DP World Chairman & CEO, UAE state-linked port operator in 80+ countries,
   Dubai Ports World, history of the role and his tenure
2. Connection to Epstein — EFTA00666117: an Epstein email identifying him in the context of a "torture video"
   (DOJ, 2026 release, justice.gov/epstein). Confidence: CONFIRMED (document exists in DOJ release).
   Do NOT assert criminal conduct — describe what the document shows. #claim on any allegation beyond
   the document content.
3. Departure from DP World — replaced/stepped down February 2026 following the DOJ file release
   (CNN Business 2026; Newsweek 2026). CONFIRMED.
4. DP World strategic significance — port operations in 80+ countries, global logistics infrastructure,
   strategic security implications of leadership with Epstein connections
5. Current legal/regulatory status — no confirmed criminal charges as of {DATE}
6. Mermaid diagram: Sultan ↔ EFTA00666117 ↔ Epstein ↔ DOJ release → departure
7. APA references

Use #claim throughout for any allegation of personal criminal conduct beyond what EFTA00666117 documents.""",
    ),

    dict(
        id="black",
        group="people",
        description="Leon Black — Apollo CEO $158M profile",
        output="People/Leon-Black.md",
        prompt=f"""Write a comprehensive vault profile for Leon Black.

YAML frontmatter: tags: [person, financial, documented, apollo], date: {DATE},
name: Leon Black, group: financial, status: departed-apollo,
summary: Apollo Global Management co-founder; paid Epstein ~$158M per Dechert LLP independent review (2021).

Sections (minimum 200 lines):
1. Background — Apollo Global Management co-founder and CEO; private equity career; net worth
2. The $158 million — Dechert LLP independent review commissioned by Apollo's board found
   Black paid Epstein approximately $158M for financial and tax advisory services (2021).
   CORROBORATED: NYT 2021, Dechert review 2021. The review characterised payments as
   "extraordinarily large" relative to work product.
3. What services were claimed — the Dechert review's characterisation of the advisory work
4. Apollo board response and Black's resignation — resigned CEO March 2021; timeline relative
   to public disclosure. CONFIRMED.
5. Civil scrutiny and legal status — no criminal charges; civil scrutiny documented #claim
6. The wealth / leverage question — analytical assessment of whether $158M reflects genuine
   advisory fees, network access, or other consideration (rate SINGLE SOURCE / UNVERIFIED)
7. Post-Apollo activities
8. Mermaid diagram: Black → $158M → Epstein → JPMorgan → enterprise
9. Full APA references""",
    ),

    dict(
        id="mandelson",
        group="people",
        description="Peter Mandelson — UK diplomat, arrested 2026",
        output="People/Peter-Mandelson.md",
        prompt=f"""Write a comprehensive vault profile for Peter Mandelson (Lord Mandelson).

YAML frontmatter: tags: [person, political, uk, arrested-2026, documented], date: {DATE},
name: Peter Mandelson, group: political, status: arrested-2026,
summary: Former UK Ambassador to US; arrested c.Feb 23 2026 after DOJ files showed classified UK material forwarded to Epstein.

Sections (minimum 200 lines):
1. Background — Blair/Brown-era political architect; Secretary of State; EU Trade Commissioner;
   UK Ambassador to the United States; now Lord Mandelson
2. Relationship with Epstein — acknowledged knowing Epstein; documented meetings; denied knowledge
   of criminal activity. Confidence: CORROBORATED (his own public statements plus multiple journalism sources)
3. The classified document — DOJ 2026 file release contained evidence Mandelson forwarded a classified
   UK government report to Epstein. CONFIRMED as basis for arrest (NPR 2026b).
4. 2026 arrest — arrested by UK police approximately February 23 2026 following the DOJ release.
   Suspected offence: Official Secrets Act / information security violation. CONFIRMED (NPR 2026b).
5. Legal framework — Official Secrets Act 1989 elements; potential penalties; his former diplomatic status
6. Political fallout — institutional responses, Labour Party position, public reaction
7. No confirmed trafficking allegation — make clear no allegation of personal trafficking conduct exists
8. Mermaid: Mandelson ↔ Epstein ↔ classified doc → DOJ release → arrest
9. APA references""",
    ),

    dict(
        id="brende",
        group="people",
        description="Borge Brende — WEF President resigned 2026",
        output="People/Borge-Brende.md",
        prompt=f"""Write a vault profile for Borge Brende.

YAML frontmatter: tags: [person, political, wef, departed-2026], date: {DATE},
name: Borge Brende, group: political, status: departed-wef,
summary: WEF President; resigned February 2026 following DOJ Epstein file release revealing post-2008 correspondence.

Sections (minimum 150 lines):
1. Background — Norwegian politician; former Foreign Minister of Norway; President of World Economic Forum
2. Connection to Epstein — post-2008 conviction correspondence documented in DOJ release.
   Confidence: CORROBORATED (NBC News 2026, Time 2026). No allegation of criminal conduct. #claim on any.
3. WEF resignation — resigned WEF presidency February 2026 following release. CONFIRMED.
4. WEF institutional significance — what Davos/WEF represents; implications of its president's departure
5. Legal status — no criminal charges or allegations as of {DATE}
6. APA references""",
    ),

    dict(
        id="karp",
        group="people",
        description="Brad Karp — Paul Weiss Chair resigned 2026",
        output="People/Brad-Karp.md",
        prompt=f"""Write a vault profile for Brad Karp.

YAML frontmatter: tags: [person, legal, paul-weiss, departed-2026], date: {DATE},
name: Brad Karp, group: financial, status: departed-paul-weiss,
summary: Paul Weiss Chair who led JPMorgan's Epstein defense; resigned February 2026 following DOJ file release.

Sections (minimum 150 lines):
1. Background — Chair of Paul Weiss Rifkind Wharton & Garrison (one of US's most prestigious law firms)
2. Role in Epstein case — Paul Weiss represented JPMorgan Chase in the Epstein-related civil proceedings
   (USVI v. JPMorgan; Jane Doe v. JPMorgan). Karp led the defense team. CONFIRMED.
3. Resignation — resigned from Paul Weiss in February 2026 following the DOJ file release. CONFIRMED.
4. Legal/ethical questions — the professional responsibility dimensions of defending JPMorgan in these proceedings;
   no personal misconduct allegations; #claim on any
5. Significance — Paul Weiss is one of the most prominent Democratic-aligned law firms; the departure signals
   the breadth of institutional fallout from the 2026 release
6. APA references""",
    ),

    # ── Timeline ─────────────────────────────────────────────────────────────

    dict(
        id="timeline",
        group="core",
        description="Definitive chronological timeline 1953–2026",
        output="Timeline.md",
        prompt=f"""Rewrite the vault's Timeline.md as the definitive granular chronology of the Epstein enterprise
from 1953 through February 28 2026.

YAML frontmatter: tags: [timeline, key, comprehensive, 2026], date: {DATE},
summary: Definitive day-by-day chronology of the Epstein enterprise 1953–2026.

Structure:
- Opening Mermaid timeline diagram covering the 5 major phases:
  Phase 1 (1953–1991): Origins / Robert Maxwell era
  Phase 2 (1991–2004): Enterprise construction and operation
  Phase 3 (2005–2008): PBPD investigation through NPA
  Phase 4 (2008–2019): Post-conviction operations through death
  Phase 5 (2019–2026): Maxwell conviction through DOJ release

Then year-by-year entries with month/day where known. Minimum 350 lines.
Bold the most significant events. Confidence ratings on each entry.
#claim on allegations against living non-convicted persons.

Key dates to include (all CONFIRMED unless noted):
- 1953-01-20: Epstein born, Brooklyn
- 1974: Joined Dalton School as teacher (no math degree — [CORROBORATED])
- 1976: Joined Bear Stearns
- 1981: Made partner at Bear Stearns
- 1987: Left Bear Stearns; founded J. Epstein & Co.
- 1989: Wexner purchases 9 E 71st St; Epstein begins managing Wexner finances
- 1991: Robert Maxwell dies Nov 5; Mossad-connected funeral (Thomas 1999) [CORROBORATED]
- Early 1990s: Ghislaine Maxwell meets Epstein (shortly after father's death)
- 1993: Zorro Ranch acquired (~10,000 acres, Stanley NM)
- 1994–2004: Core trafficking operation period (per SDNY 19-CR-490 indictment)
- 1996: Maria Farmer FBI complaint — not acted upon [CONFIRMED]
- 1998: Little Saint James acquired; JPMorgan banking begins
- 2002: New York magazine article — Trump "terrific guy, likes his women young" quote
- 2003: Vicky Ward Vanity Fair investigation — abuse allegations removed by editor Graydon Carter
- 2005-03: PBPD complaint from 14-year-old's family [CONFIRMED]
- 2005–2006: PBPD Detective Recarey investigation — 36 victims identified [CONFIRMED]
- 2006–2007: FBI enters investigation
- 2007: Trump bans Epstein from Mar-a-Lago [CORROBORATED]
- 2008-06-30: NPA signed by Acosta [CONFIRMED]
- 2008: Epstein pleads to FL state charges — 13 months work release
- 2009-11: Released from Florida custody
- 2013: First MIT Media Lab donation (anonymous) [CONFIRMED — Goodwin Procter 2019]
- 2013: JPMorgan exits Epstein relationship; Deutsche Bank takes over
- 2015: Amy Robach ABC News documentary killed [CONFIRMED]
- 2016: Great Saint James purchased [CONFIRMED]
- 2018-11-28: Miami Herald "Perversion of Justice" published (Brown) [CONFIRMED]
- 2019-02: Judge Marra rules NPA violated CVRA (Does 1-6 v. US) [CONFIRMED]
- 2019-07-06: Epstein arrested at Teterboro Airport [CONFIRMED]
- 2019-07-08: SDNY indictment filed 19-CR-490 [CONFIRMED]
- 2019-07-10: Bail denied [CONFIRMED]
- 2019-07-23: Found semi-conscious in MCC cell; suicide watch placed [CONFIRMED]
- 2019-08-09: Cellmate transferred out; suicide watch removed [CONFIRMED]
- 2019-08-10: Found dead at MCC ~06:30; pronounced dead ~07:30 [CONFIRMED]
- 2019-10-30: Dr. Baden press conference — homicidal strangulation more consistent [CONFIRMED]
- 2019-11: Goodwin Procter MIT review published [CONFIRMED]
- 2019-09-06: New Yorker MIT investigation published (Farrow & Lepore) [CONFIRMED]
- 2019-09-07: Joi Ito resigns MIT [CONFIRMED]
- 2020-07: Deutsche Bank fined $150M by NYDFS [CONFIRMED]
- 2020-12-02: Ghislaine Maxwell arrested in Bradford, NH [CONFIRMED]
- 2021-03: Leon Black resigns Apollo CEO [CONFIRMED]
- 2021-12-29: Maxwell convicted on 6 counts [CONFIRMED]
- 2022-02-15: Giuffre v. Andrew settled ~£12M equivalent [CONFIRMED]
- 2022-02-19: Jean-Luc Brunel found dead La Santé — suicide ruling [CONFIRMED]
- 2022-06-28: Maxwell sentenced 20 years [CONFIRMED]
- 2023-06: JPMorgan settles USVI suit $290M [CONFIRMED]
- 2023-10: JPMorgan settles Jane Doe class action $75M [CONFIRMED]
- 2024-05: FCA bans Jes Staley from UK financial services [CONFIRMED]
- 2025-11: Epstein Files Transparency Act enacted [CONFIRMED]
- 2025-12-19: DOJ missed first release deadline [CONFIRMED]
- 2026-01-30: DOJ releases ~3M pages justice.gov/epstein [CONFIRMED]
- 2026-02-19: Prince Andrew arrested (UK) [CONFIRMED]
- 2026-02-19: New Mexico criminal proceedings reopened [CONFIRMED]
- 2026-02-23: Peter Mandelson arrested (UK) [CONFIRMED]
- 2026-02: Sultan bin Sulayem replaced at DP World [CONFIRMED]
- 2026-02: Borge Brende resigns WEF [CONFIRMED]
- 2026-02: Brad Karp resigns Paul Weiss [CONFIRMED]
- 2026-02-28: Current date

Full APA references at end.""",
    ),

    # ── Findings — Legal ─────────────────────────────────────────────────────

    dict(
        id="prosecution-brief",
        group="findings",
        description="Model federal prosecution brief for co-conspirators",
        output="Findings/Model-Prosecution-Brief-2026.md",
        prompt=f"""Write a model federal prosecution memorandum for surviving Epstein enterprise co-conspirators.
This is a research document drafted for educational and analytical purposes.

YAML frontmatter: tags: [finding, legal, prosecution, rico, sdny, 2026], date: {DATE}

Structure (minimum 400 lines):

## I. EXECUTIVE SUMMARY
Who should be charged, on what counts, why now (2026).

## II. JURISDICTIONAL ANALYSIS
- Why SDNY over SDFL — United States v. Epstein (2019) precedent proves NY conduct not immunised by FL NPA
- Does 1-6 v. US (2019) — NPA ruled to violate CVRA — weakens NPA as shield
- The CVRA violation: does it create grounds to challenge unnamed co-conspirator immunity?

## III. TARGET PROFILES
For each of Sarah Kellen (now Vickers), Adriana Ross, Lesley Groff, Nadia Marcinkova (now Marcinko):
- Role in enterprise (per Maxwell trial testimony and NPA documents)
- Evidence available
- NPA immunity scope and its limits for NY conduct
- Proposed charges and mandatory minimums
- Cooperation value (what each could testify to)
- Estimated sentencing range under USSG

## IV. PROPOSED CHARGES — COUNT ANALYSIS
For each count:
- 18 U.S.C. § 1591(a) — sex trafficking of minors (10-15 yr mandatory minimum)
- 18 U.S.C. § 1594(c) — sex trafficking conspiracy (same as substantive)
- 18 U.S.C. § 2422(b) — enticement of minors (10 yr to life)
- 18 U.S.C. § 2423(a) — transportation of minors (10 yr to life)
For each: elements, evidence satisfying each element, anticipated defenses, counter-arguments

## V. RICO THEORY
Full RICO enterprise charging theory under 18 U.S.C. §§ 1961-1968:
- Enterprise definition (association-in-fact per Turkette)
- Pattern of racketeering (predicate acts per § 1961(1))
- Nexus to interstate commerce
- Conduct of enterprise (Reves v. Ernst & Young standard)
- Forfeiture prayer (§ 1963)
- Why RICO adds value: 20 yr per count, mandatory forfeiture, civil treble damages (§ 1964)

## VI. FINANCIAL CRIMES — INDIVIDUAL OFFICER EXPOSURE
- JPMorgan and Deutsche Bank officers: 18 U.S.C. § 1956 money laundering analysis
- "Willful blindness" doctrine application (Global-Tech Appliances v. SEB SA, 2011)
- Why institutional settlements don't bar individual prosecutions

## VII. EVIDENTIARY ANALYSIS
- Maxwell conviction as collateral estoppel basis for enterprise findings
- FBI 2019 photographs — admissibility as direct evidence
- Flight logs — authentication, hearsay exceptions
- EFTA documents — authentication via DOJ production
- "Carolyn" / "Jane" / "Kate" / Annie Farmer testimony — prior testimony admissibility

## VIII. PROSECUTION FLOWCHART
```mermaid
flowchart TD
    A[2019 Maxwell Conviction] --> B[Enterprise established]
    B --> C[NY conduct not NPA-immunised per SDNY 2019]
    C --> D[Kellen / Ross / Groff / Marcinkova — SDNY exposure]
    D --> E[§1591 + §1594 + RICO charges]
    E --> F[10-20yr mandatory minimum exposure each]
```

## IX. NOVEL LEGAL THEORY — NPA IMMUNITY CHALLENGE
Post-Does 1-6: can the CVRA violation be used to reopen NPA immunity grants?
The argument: an agreement procured in violation of statutory victim rights is voidable.

## X. CONCLUSION AND RECOMMENDATION

## XI. FULL APA REFERENCES""",
    ),

    dict(
        id="maxwell-legal",
        group="findings",
        description="Maxwell conviction deep legal analysis",
        output="Findings/Maxwell-Conviction-Legal-Analysis.md",
        prompt=f"""Write a deep legal analysis of the Ghislaine Maxwell conviction and its ongoing implications.

YAML frontmatter: tags: [finding, legal, maxwell, conviction, sdny, 2026], date: {DATE}

Structure (minimum 300 lines):

## I. THE SIX COUNTS — WHAT THE JURY FOUND
Table: Count | Statute | Verdict | Key Element Proved
All 6 counts: sex trafficking conspiracy (§1594c), sex trafficking of a minor (§1591),
enticement of a minor (§2422b), transportation of a minor for criminal sexual activity (§2423a),
conspiracy to entice (§2422b conspiracy), conspiracy to transport (§2423a conspiracy)

## II. WHAT THE JURY'S VERDICT LEGALLY ESTABLISHES
- Collateral estoppel: Maxwell's conviction binds her and creates factual findings that
  can be used in subsequent proceedings against co-conspirators
- The enterprise was real: jury found a conspiracy existed (§1594c)
- Victims were minors: jury found victims were under 18 at time of abuse
- Maxwell's role was active: jury found she actively participated, not merely aware

## III. SENTENCING ANALYSIS — 20 YEARS
- USSG calculation: offense level, criminal history
- Departure analysis: upward departures argued; Judge Nathan's reasoning
- Comparison to similar cases: how does 20 years compare to other trafficking convictions?
- Parole: no parole in federal system; expected release date
- Maxwell's cooperation: did she cooperate? what did she disclose?

## IV. MAXWELL'S APPEALS — STATUS AND PROSPECTS
- Grounds raised on appeal
- Second Circuit analysis
- Prospects for success (analytical assessment with confidence ratings)

## V. IMPLICATIONS FOR CO-CONSPIRATORS
For each of Kellen, Ross, Groff, Marcinkova:
- The Maxwell verdict as evidence of the enterprise in which they participated
- Co-conspirator hearsay exception (FRE 801(d)(2)(E)): Maxwell's statements now admissible against them
- Collateral estoppel doctrine: findings cannot be re-litigated

## VI. THE UNNAMED CO-CONSPIRATORS QUESTION
- Maxwell trial introduced evidence of other participants not charged
- What was disclosed about additional co-conspirators
- Why they were not charged alongside Maxwell

## VII. WHAT THE CONVICTION DID NOT ESTABLISH
- No finding on named high-profile individuals
- Temporal limits of the charged conspiracy (2002-2004 per indictment)
- Geographic limits

## VIII. MERMAID DIAGRAM — MAXWELL CONVICTION CASCADE
```mermaid
graph TD
    MV["Maxwell Conviction\nSDNY 20-CR-330\nDec 29 2021"] --> CE["Collateral Estoppel\nEnterprise proved"]
    CE --> K["Kellen exposure"]
    CE --> R["Ross exposure"]
    CE --> G["Groff exposure"]
    CE --> M["Marcinkova exposure"]
    MV --> HA["Hearsay exception\nMaxwell statements\nadmissible vs. co-conspirators"]
```

## IX. FULL APA REFERENCES""",
    ),

    # ── Findings — Intelligence & Financial ──────────────────────────────────

    dict(
        id="intelligence-dossier",
        group="findings",
        description="Deep intelligence network dossier",
        output="Findings/Intelligence-Dossier-Deep-Analysis.md",
        prompt=f"""Write the deepest possible intelligence-analyst assessment of the intelligence dimension
of the Epstein enterprise. Go substantially further than any existing analysis.

YAML frontmatter: tags: [finding, intelligence, counterintelligence, deep, mossad, cia], date: {DATE}

Structure (minimum 400 lines):

## I. ANALYTICAL FRAMEWORK — HYPOTHESIS TESTING
Structured Analytic Technique: competing hypotheses for Epstein's intelligence connections.
H1: Active witting intelligence asset (Mossad / CIA / other)
H2: Unwitting useful instrument (intelligence exploited his network without his knowledge)
H3: No intelligence connection — coincidence and pattern-matching
Apply evidence to each hypothesis systematically.

## II. ROBERT MAXWELL — THE OPERATIONAL ANCESTOR
- Documented Mossad/intelligence relationships (Hersh 1991; Thomas 1999) [CORROBORATED]
- The PROMIS software affair: Robert Maxwell's alleged role in distributing backdoored software
  to foreign intelligence agencies [SINGLE SOURCE — Inslaw claims, not fully proven]
- The 1991 funeral: six intelligence chiefs attending a private individual's funeral —
  what this signals about the depth of the relationship [CORROBORATED — multiple accounts]
- The disputed death: intelligence community parallels and what they might suggest
- How this structural inheritance could pass to Ghislaine Maxwell

## III. THE ACOSTA STATEMENT — FULL DISSECTION
- Exact words as reported by Julie K. Brown (Miami Herald, 2018) [SINGLE SOURCE]
- What "belonged to intelligence" means in operational terms — three possible readings
- Historical precedents: cases where intelligence community connections influenced prosecutions
- Why there is NO documented legal basis for such a protection (USAM analysis)
- The intelligence community declination: how it would work procedurally if real
- Acosta's subsequent silence on this point — analytical significance

## IV. THE BLACKMAIL APPARATUS — INTELLIGENCE OPERATIONAL LENS
Compare to known state-run kompromat operations:
- KGB "honey trap" operations (documented Cold War cases) — structural comparison
- How the Epstein operation differs from personal criminal conduct
- The hidden camera network: who would have technical access to extracted material?
- The flight log paradox: why maintain meticulous passenger records that incriminate guests?
  (Answer: the records ARE the leverage — you need documentation to exert control)
- Scale assessment: a private individual running this-scale operation without protection is
  implausible historically — what institutional backing would be required?

## V. EHUD BARAK — FULL DOSSIER
- Career: IDF Chief of Staff, PM, Defence Minister, head of Sayeret Matkal (special forces)
- Post-2008 conviction documented visits to Epstein properties [CONFIRMED — his own admission]
- Carbyne911 investment: what is it, who are the co-investors, intelligence community nexus [CORROBORATED]
- The Aviv Rosen connection: Israeli tech/intelligence community orbit
- What his continued engagement post-conviction suggests operationally
- Confidence: HIGH (documented visits); LOW (operational significance)

## VI. STRUCTURED ASSESSMENT — THE MOSSAD HYPOTHESIS
Evidence FOR: (list minimum 8 data points with confidence ratings)
Evidence AGAINST: (list minimum 4 counter-points)
Evidence NEUTRAL/AMBIGUOUS: (list minimum 4 points)
Net probability assessment with explicit reasoning.

## VII. STRUCTURED ASSESSMENT — THE CIA HYPOTHESIS
Same structure.
Additional consideration: Epstein's access to foreign officials via his US address book
would have made him a valuable human intelligence source from a US perspective.

## VIII. THE MI6 / UK DIMENSION
- Prince Andrew and the classified document forwarding: intelligence significance vs. personal recklessness
- Ghislaine Maxwell's British background and MI6 cultural proximity
- The Mandelson classified report: what level of classification? what intelligence value?
- Did UK intelligence know about Epstein's network before the 2026 arrests?

## IX. NOVEL INTELLIGENCE ANALYSIS
- DP World / Sultan bin Sulayem: port intelligence implications of EFTA00666117
- Scopolamine from an intelligence tradecraft perspective — it is standard HUMINT pharmacology
- The eugenics/transhumanism agenda: cover story, personal ideology, or something else?
- The modelling agency pipeline: structural parallel to intelligence "talent spotting" operations

## X. THE COUNTER-INTELLIGENCE QUESTION
- What foreign intelligence services would have wanted Epstein's blackmail data?
- Could multiple intelligence services have been running competing operations through Epstein?
- The "double asset" possibility

## XI. CONFIDENCE MATRIX
Table: Sub-hypothesis | Evidence for | Evidence against | Net confidence | Key uncertainties

## XII. WHAT WOULD RESOLVE THE HYPOTHESIS
Specific documents, if declassified, that would confirm or refute each hypothesis.

## XIII. FULL APA REFERENCES""",
    ),

    dict(
        id="financial-forensics",
        group="findings",
        description="Financial forensics deep analysis",
        output="Findings/Financial-Forensics-Deep-Analysis.md",
        prompt=f"""Write the definitive forensic financial analysis of the Epstein enterprise.

YAML frontmatter: tags: [finding, financial, forensic, deep, jpmorgan, deutsche-bank, wexner], date: {DATE}

Structure (minimum 400 lines):

## I. THE $1 BILLION MYSTERY — HOW DID EPSTEIN GET RICH?
Known legitimate income: Bear Stearns (1976-1981 partner-track), J. Epstein & Co. advisory fees
The Wexner period: what managing a billionaire's finances could yield (legitimately and not)
The $158M from Black: when did this occur? was it his primary wealth event?
The unexplained gap: what Bear Stearns-level advisory work produces vs. $1B net worth
Analytical framework: working backward from estate valuation

## II. THE WEXNER-EPSTEIN RELATIONSHIP — FORENSIC VIEW
Timeline of relationship: late 1980s through c.2007 (Wexner's own statement)
The power of attorney scope: what it permitted legally
The 9 East 71st St transfer mechanics: $13.2M Wexner purchase → Epstein ownership (how?)
L Brands financial profile 1989-2007: revenue, profits, what advisory would be worth
The "misled and betrayed" admission: what it legally acknowledges and denies
Third-party liability analysis: could Wexner estate have trafficking-related civil exposure?

## III. JPMORGAN — TRANSACTION TYPOLOGY
18-year banking relationship: what transaction patterns triggered (and didn't trigger) SARs
Cash withdrawal patterns: the USVI civil proceedings revealed regular large cash withdrawals
"Eastern European women" payments: documented in NYDFS consent order for Deutsche Bank;
  similar patterns in JPMorgan period?
Internal escalations overruled: documented in USVI civil proceedings
Jes Staley's personal correspondence: what the FCA investigation found about his Epstein emails
The $365M total liability: $290M USVI settlement + $75M Jane Doe class action [CONFIRMED]
Individual officer criminal exposure: 18 U.S.C. § 1956 "willful blindness" analysis

## IV. DEUTSCHE BANK — THE CONSENT ORDER IN DETAIL
NYDFS consent order specifics: what transactions were flagged (2020) [CONFIRMED]
Cash payments to "women with Eastern European names": direct quote from consent order
Wire transfers to foreign accounts: which accounts? which countries?
The 5-year gap: took over 2013, fined 2020 — 7 years of documented failures
Why Deutsche Bank agreed to take Epstein post-JPMorgan: compliance culture, revenue calculation
$150M fine compared to profit generated: was the fine a deterrent?

## V. THE $158 MILLION — FORENSIC DISSECTION
Timeline: when were the payments made? (Dechert review years breakdown)
Tax advisory specifically: what structures would justify $158M in legitimate fees?
Apollo's carried interest and potential Epstein role in structuring
The "extraordinarily large" characterisation: Dechert's own words
Alternative hypothesis: network access / blackmail insurance payment [UNVERIFIED — rate carefully]
Post-resignation: what happened to Apollo's performance after Black left?

## VI. THE ESTATE VALUATION — $634M
Primary components: Manhattan townhouse ($51M), USVI islands ($60M), NM ranch ($13.4M reassessed)
What accounts for the remaining ~$510M: offshore structures, investment accounts, art
Co-executors Darren Indyke and Richard Kahn: their prior relationship to Epstein
USVI settlement terms: how much actually reached victims
The Lex Wexner funds: did any estate funds derive from Wexner?

## VII. OFFSHORE STRUCTURES
Virgin Islands Economic Development Authority: tax benefits Epstein used
Known offshore entities (from court filings): list and describe
BVI / Cayman / Channel Islands potential: what forensic indicators exist
French accounts connected to Paris apartment

## VIII. MERMAID — COMPLETE MONEY FLOW DIAGRAM
```mermaid
graph LR
    WEX["Les Wexner\nPOA source\n$B+ L Brands wealth"] -->|"advisory fees\nproperty transfer"| JE
    JE["Jeffrey Epstein\n~$1B estate"] -->|"1998-2013"| JPM["JPMorgan Chase\n$365M liability"]
    JE -->|"2013-2018"| DB["Deutsche Bank\n$150M fine"]
    BLACK["Leon Black\nApollo\n$158M paid"] --> JE
    JE -->|"property purchases"| PROP["7-property network\n~$200M+"]
    PROP -->|"post-death estate"| EST["Epstein Estate\n~$634M"]
    EST -->|"victim settlements"| VICTI["Victim compensation\n(partial)"]
    JPM -->|"USVI + Jane Doe"| VICTI
```

## IX. WHAT A FORENSIC AUDIT WOULD FIND
If forensic auditor had full access 1988-2019:
- Priority transaction review targets
- Hidden account indicators
- What FinCEN SARs might reveal (if ever released)
- Foreign bank record targets (French, Virgin Islands, Swiss)

## X. TAX DIMENSION
USVI EDA tax incentives: what Epstein qualified for
IRS exposure for estate: unpaid taxes on offshore income?
The Black advisory fees: were they reported properly?

## XI. FULL APA REFERENCES""",
    ),

    # ── Findings — Research ──────────────────────────────────────────────────

    dict(
        id="brunel-mc2",
        group="findings",
        description="Jean-Luc Brunel and MC2 modelling pipeline",
        output="Findings/Brunel-MC2-Modelling-Pipeline.md",
        prompt=f"""Write the definitive account of Jean-Luc Brunel's MC2 Model Management agency
and its role as a trafficking pipeline for the Epstein enterprise.

YAML frontmatter: tags: [finding, brunel, mc2, modelling, trafficking, pipeline, france], date: {DATE}

Structure (minimum 300 lines):

## I. JEAN-LUC BRUNEL — BACKGROUND
Paris modelling world career: Elite agency, Karin Models, others
The 1980s rape allegations: documented in Carre Otis's memoir and other sources [SINGLE SOURCE / CORROBORATED — check]
Why he retained prominence despite prior allegations: the structural protection of the modelling industry
Meeting Epstein: when and how the relationship began

## II. MC2 MODEL MANAGEMENT
Founding: when, where (Miami-based), with what funding
Epstein as documented financial backer [CONFIRMED — Maxwell trial evidence; civil proceedings]
The business model: Eastern European and foreign model recruitment, visa sponsorship, US placement
Why this created structural trafficking vulnerability: power over visa/housing/income
The "booker" role: how models were introduced to Epstein

## III. THE TRAFFICKING PIPELINE — OPERATIONAL MECHANICS
Recruitment in Eastern Europe: documented sourcing regions (France, Brazil, Eastern Europe)
Visa sponsorship as control mechanism: model financially and legally dependent on agency
The "introduction" to Epstein: how it was framed, what actually happened
The sub-recruitment parallel: some models (like some victims) became recruiters themselves
Maxwell's interface with MC2: documented coordination

## IV. DOCUMENTED VICTIMS THROUGH BRUNEL / MC2
Named in Maxwell trial testimony or civil proceedings
The "Jean-Luc" references in Giuffre deposition
Victims who came through Brunel's network specifically

## V. THE FRENCH INVESTIGATION
Timeline: when French authorities opened investigation; what triggered it
Charges: rape of a minor; what evidence supported this
Arrest: December 2020 at Charles de Gaulle Airport (returning from Senegal) [CONFIRMED]
La Santé Prison: conditions of detention; co-defendants if any

## VI. DEATH AT LA SANTÉ — FEBRUARY 19, 2022
Official ruling: suicide by hanging [CONFIRMED — French authorities]
No independent autopsy commissioned [CONFIRMED]
The Epstein parallel: both key witnesses, both apparent hanging in custody, both pre-trial
What testimony was permanently lost: what Brunel knew that will never be heard
The French investigation's status after his death

## VII. THE COVER-UP DIMENSION
Prior knowledge by modelling industry insiders: documented complaints against Brunel pre-2019
Elite modelling world's protection of Brunel despite known allegations
Media handling: fashion journalism's failure to investigate Brunel prior to Epstein exposure
What the modelling industry has reformed (or not) since 2019

## VIII. MERMAID — BRUNEL/MC2 NETWORK
```mermaid
graph TD
    JLB["Jean-Luc Brunel"] -->|"founded/ran"| MC2["MC2 Model Management\nMiami-based"]
    JE["Epstein"] -->|"financial backer\n(CONFIRMED)"| MC2
    GM["Ghislaine Maxwell"] -->|"coordination"| JLB
    MC2 -->|"Eastern European\nrecruitment pipeline"| V["Victims via modelling\npretext"]
    V --> JE
    JLB -->|"French arrest Dec 2020"| FRCH["French investigation\nRape of minor charges"]
    FRCH -->|"Feb 19 2022\nhanging in custody"| DEAD["Brunel deceased\nno trial, no testimony"]
```

## IX. FULL APA REFERENCES""",
    ),

    dict(
        id="international-law",
        group="findings",
        description="International law and extradition analysis",
        output="Findings/International-Law-Analysis.md",
        prompt=f"""Write a comprehensive international law analysis of the Epstein case.

YAML frontmatter: tags: [finding, international-law, extradition, uk, france, echr, 2026], date: {DATE}

Structure (minimum 300 lines):

## I. UK PROCEEDINGS — ANDREW AND MANDELSON
Official Secrets Act 1989: elements, penalties, relevant precedents
Prince Andrew: post-royal-duties-stripping status; whether any immunity applies; what the arrest covers
Peter Mandelson: former diplomatic status; does it confer any protection for this conduct?
The evidence threshold: what UK law requires for charging vs. arrest
The ECHR dimension: Article 6 fair trial rights in a case of this public profile

## II. FRENCH JUDICIAL INVESTIGATION
The juge d'instruction system vs. US grand jury: comparative procedural analysis
Status of French investigation into Epstein's Paris operations (Avenue Foch) post-Brunel death
What charges remained open; what the investigation can still produce without Brunel
Mutual Legal Assistance Treaty (MLAT) US-France: what evidence has been or can be shared
Maxwell conviction use in French proceedings: comity doctrine

## III. USVI JURISDICTION — WHAT WAS ACHIEVED AND WHAT REMAINS
USVI AG proceedings: strategic choice of USVI jurisdiction, what it accomplished
JPMorgan $290M settlement: terms, what USVI law enabled that federal law might not have
USVI criminal jurisdiction: what offences remain potentially chargeable under USVI law
The Economic Development Authority angle: tax benefits + trafficking = RICO in USVI context?

## IV. INTERNATIONAL HUMAN TRAFFICKING LAW
UN Palermo Protocol (2000): trafficking definition, state obligations
How the Epstein enterprise maps onto Palermo Protocol elements: purpose, means, act
Universal jurisdiction: in principle, any state can prosecute. In practice: why haven't they?
ICC jurisdiction: why sex trafficking of this scale almost certainly doesn't reach ICC threshold
(ICC requires state policy or widespread systematic attack on civilian population)

## V. THE UAE DIMENSION
UAE legal system: what accountability is realistically possible for Sultan bin Sulayem? #claim
FATF-UAE relationship: UAE on FATF grey list 2022-2024; implications for financial accountability
DP World's international contracts: can information security concerns affect port contracts?
Diplomatic complications: UAE is a major US security partner

## VI. MLAT LANDSCAPE — WHAT'S BEEN USED
Known MLAT activity in the case (from press reports and court filings)
What foreign banking records have been subpoenaed
What remains potentially obtainable: Cayman Islands, British Virgin Islands, Channel Islands, Swiss
The 5-year MLAT limitation periods in various jurisdictions

## VII. NOVEL INTERNATIONAL LAW ANALYSIS
The "transnational organized crime" designation: could the Epstein enterprise be certified as such
under UNTOC? What remedies would flow from that designation?
Cross-border trafficking regulation post-2019: what law changes occurred that would now apply?
The International Criminal Court vs. hybrid tribunal model: could a hybrid tribunal for
transnational trafficking accountability be created? What precedent exists (ECCC, SCSL)?

## VIII. REFORM RECOMMENDATIONS — INTERNATIONAL FRAMEWORK
Specific treaty amendments or new instruments that the Epstein case argues for
MLAT modernisation
Trafficking survivor rights under international law

## IX. FULL APA REFERENCES""",
    ),

    dict(
        id="zorro-ranch",
        group="findings",
        description="Zorro Ranch New Mexico complete analysis",
        output="Findings/Zorro-Ranch-Complete-Analysis.md",
        prompt=f"""Write the definitive account of Epstein's Zorro Ranch property in New Mexico.

YAML frontmatter: tags: [finding, locations, zorro-ranch, new-mexico, eugenics, 2026], date: {DATE}

Structure (minimum 300 lines):

## I. THE PROPERTY
Acquisition: c.1993, ~10,000 acres near Stanley, New Mexico (Torrance County)
Physical description: main house, guest facilities, airstrip (documented in flight logs)
How it connected to the broader property network: TEB→SAF/TCS flights documented
Sale: 2023, $13.4M (reassessed valuation; initial estate valuation $21.1M)

## II. THE EUGENICS PROGRAMME
The New York Times investigation (Stewart, Goldstein, Silver-Greenberg, August 12 2019):
Epstein told multiple prominent scientists of plan to impregnate "up to 20 women at a time"
at Zorro Ranch with his own DNA — goal: "seed the human race" with superior genetic material.
CORROBORATED: multiple named scientists confirmed the account.
The ideological basis: transhumanism, evolutionary biology, "cryonics" (also mentioned)
Connection to funding of Martin Nowak's Harvard Program for Evolutionary Dynamics
Connection to George Church meetings (Harvard geneticist, gene editing)
Analytical assessment: was this delusional grandiosity, genuine ideology, or cover for something else?

## III. SCIENTISTS HOSTED AT ZORRO RANCH
Stephen Hawking visit: documented for a physics conference at the ranch [CONFIRMED — multiple sources]
Other documented visitors: who attended ranch conferences, what was discussed
How these visits were used: social validation, introductions, donor recruitment
The Edge Foundation connection: Brockman's salon participants hosted at ranch

## IV. ANNIE FARMER — MAXWELL TRIAL TESTIMONY
Annie Farmer testified under her own name (not a pseudonym) — acknowledged courage
What she described: visit to the ranch at age 16; Maxwell groped her; Epstein inappropriate conduct
Geographic and operational significance: abuse documented at New Mexico location specifically
Her testimony under own name: what this meant for the prosecution and for survivor advocacy

## V. THE 2026 REOPENED INVESTIGATION
Which office: New Mexico AG or local DA (specify if known from reporting)
Reopened: February 19 2026 [CONFIRMED — NBC News 2026]
What conduct under investigation: post-2008 conviction activity at the ranch?
What evidence potentially survives: property records, employee records, flight logs for SAF/TCS
The 2023 sale chain of custody: what forensic preservation occurred before sale?

## VI. THE EVIDENCE DIMENSION
Underground facilities: reports of tunnels or underground structures [LOW confidence — UNVERIFIED;
assess carefully and rate honestly; do not assert if not confirmed]
Physical evidence preservation: what was collected before/during the 2019 FBI investigation?
Flight log evidence: who flew to the ranch and when
Visitor records: guest books, security logs if any

## VII. THE SULFURIC ACID QUESTION (for LSJ — note connection to NM)
The documented industrial sulfuric acid order at Little Saint James [SINGLE SOURCE]
Whether similar industrial chemical orders exist for New Mexico property [UNVERIFIED]
What evidence destruction at a remote ranch would look like operationally

## VIII. MERMAID — ZORRO RANCH NETWORK
```mermaid
graph TD
    NM["Zorro Ranch\nStanley NM\n~10,000 acres"] -->|"hosted"| SCI["Scientists\n(Hawking, others)"]
    NM -->|"eugenics plan site\n(NYT 2019)"| EUG["DNA seeding plan\n[CORROBORATED]"]
    NM -->|"abuse documented\n(Annie Farmer testimony)"| ABUSE["Maxwell trial\nevidence site"]
    NM -->|"flight log route\nTEB-SAF/TCS"| FLIGHT["Aircraft connections"]
    NM -->|"reopened 2026-02-19"| INV["NM criminal investigation\n[CONFIRMED]"]
```

## IX. FULL APA REFERENCES""",
    ),

    dict(
        id="wexner-analysis",
        group="findings",
        description="Wexner-Epstein financial relationship complete analysis",
        output="Findings/Wexner-Epstein-Complete-Analysis.md",
        prompt=f"""Write the definitive analysis of the Les Wexner — Jeffrey Epstein financial relationship.

YAML frontmatter: tags: [finding, financial, wexner, power-of-attorney, l-brands, documented], date: {DATE}

Structure (minimum 300 lines):

## I. WHO IS LES WEXNER
L Brands founder: Victoria's Secret, Bath & Body Works, Lane Bryant, Abercrombie & Fitch (early)
Net worth: Forbes billionaire; Columbus OH power base
Philanthropic record: Wexner Foundation, Jewish community leadership
How Epstein entered his orbit: late 1980s (first documented contact c.1987-1988)

## II. THE POWER OF ATTORNEY — LEGAL ANATOMY
What a broad POA permits: acting as principal in all financial matters
The specific scope granted to Epstein: what documents/filings describe its extent
Comparison to normal financial advisory: this is radically beyond standard arrangements
What transactions a POA of this scope could authorise without Wexner's explicit consent
Legal doctrine: a principal is bound by their agent's actions within scope of authority
The liability question: is Wexner potentially liable for Epstein's use of the POA?

## III. THE 9 EAST 71ST STREET TRANSFER — THE CENTRAL MYSTERY
Wexner purchased the 6-storey Manhattan townhouse in 1989 for ~$13.2M [CONFIRMED]
The transfer: the property appears in Epstein's name by the mid-1990s
What the transfer documents say: what has been made public in court filings
Three theories: (1) gift, (2) sale below market, (3) POA-executed transfer without explicit consent
Tax implications of each theory
Wexner's "misled and betrayed" statement: what it admits (a transfer occurred) and denies
(that he authorised it in the manner described by Epstein)

## IV. L BRANDS FINANCIAL FLOWS DURING THE EPSTEIN PERIOD
L Brands revenue and profits 1989-2007 during Epstein's management involvement
Victoria's Secret expansion: was Epstein involved in sourcing decisions? [investigate, rate carefully]
The Columbus OH connection: Wexner's base, L Brands HQ, Epstein's Ohio operations
What financial records show about the Wexner-Epstein business relationship
Any L Brands corporate accounts or payments documented in civil proceedings

## V. THE WEALTH CREATION QUESTION
From Bear Stearns partner to managing Wexner to $1B: the wealth accumulation timeline
What managing a billionaire's assets legitimately produces in fees
What managing them with a broad POA could produce beyond legitimate fees
The "misappropriation" theory: [SINGLE SOURCE / UNVERIFIED — rate carefully]
Why Wexner did not press criminal misappropriation claims publicly

## VI. WEXNER'S POST-2008 CONDUCT
Did Wexner maintain contact with Epstein after the 2008 conviction? [investigate sources]
What the 2026 DOJ file release reveals about Wexner, if anything
Wexner's 2019 letter to Wexner Foundation: full analysis of what it said
Civil scrutiny: what civil proceedings have involved Wexner?

## VII. LEGAL LIABILITY ANALYSIS
Civil RICO exposure: as a knowing beneficiary of an enterprise? [UNVERIFIED — rate LOW]
Fiduciary duty to victims: does the source of Epstein's wealth create third-party duties?
Statute of limitations on any civil claims against Wexner
The "inquiry notice" doctrine: when did Wexner have sufficient reason to investigate Epstein?

## VIII. MERMAID — WEXNER-EPSTEIN FINANCIAL ARCHITECTURE
```mermaid
graph LR
    WEX["Les Wexner\nL Brands billionaire"] -->|"POA granted\nlate 1980s"| JE["Jeffrey Epstein\nJ. Epstein & Co."]
    WEX -->|"purchased 1989"| NYC["9 E 71st St\n(transferred to Epstein mid-1990s)"]
    JE -->|"advisory fees\nwealth accumulation"| WEALTH["~$1B estate"]
    WEALTH -->|"funded"| PROP["7-property network\ntrafficking infrastructure"]
    JE -->|"1998"| JPM["JPMorgan banking"]
```

## IX. FULL APA REFERENCES""",
    ),

    dict(
        id="legitimacy-analysis",
        group="findings",
        description="How Epstein constructed and maintained social legitimacy",
        output="Findings/Legitimacy-Construction-Analysis.md",
        prompt=f"""Write a sociological and investigative analysis of how Epstein constructed and maintained
elite social legitimacy despite being a convicted sex offender.

YAML frontmatter: tags: [finding, analysis, legitimacy, social-network, elite, cover-story], date: {DATE}

Structure (minimum 300 lines):

## I. THE LAYERED LEGITIMACY ARCHITECTURE
The Financier cover: constructed mystery around his wealth; "I only take clients with $1B+";
the deliberate opacity that reads as exclusivity
The Philanthropist cover: MIT ($7.5M), Harvard ($9.1M), Edge Foundation — documented
The Intellectual cover: hosting scientists, Edge salon attendance, "I'm funding human evolution"
The Connector cover: his role as introducer between elites — the social value proposition
How these four covers reinforced each other (table: Cover → Who it persuaded → Evidence)

## II. SOCIAL CAPITAL THEORY — APPLIED
Bourdieu's field theory: Epstein operated simultaneously in financial, academic, political, and
social fields; converting capital between them
The "Matthew effect": early elite connections legitimated later ones (Harvard invited because MIT;
MIT invited because Bear Stearns; Bear Stearns because Wexner)
Why prominent people failed to ask hard questions: social cost of skepticism in these circles
The "status shield": sufficiently high-status actors are assumed to have passed someone else's vetting

## III. THE MEDIA MANAGEMENT OPERATION
Known publicists and PR management
The 2002 New York magazine profile: "I'm a collector of people" — Epstein-friendly framing
The 2003 Vanity Fair "Talented Mr. Epstein" piece: Vicky Ward's investigation and what Carter removed
Why the Ward piece was important: it would have changed the legitimacy calculus entirely
The ABC/Robach 2015 story: what would have happened to Epstein's network had it aired
Asymmetry: critical journalism suppressed, flattering profiles published — who benefits?

## IV. THE 2008 CONVICTION — WHY IT DIDN'T STICK SOCIALLY
13 months work release is socially legible as "minor crime" — the NPA did this deliberately
Sex offender registration: how is this normally treated in elite circles vs. how it was treated here
The "work release" framing by Epstein himself: "I served my time"
Who continued relationships knowing he was a convicted sex offender:
- Joi Ito (MIT) — documented; he acknowledges it [CONFIRMED]
- Harvard — continued relationship post-2008 [CONFIRMED]
- Bill Gates — meetings post-conviction [CONFIRMED — his own admission]
- Leon Black — payments continued post-conviction [CONFIRMED]
What does this density of continued elite engagement tell us? It tells us the legitimacy
architecture was strong enough to survive a sex offender conviction.

## V. THE POST-2008 LEGITIMACY REBUILD
Which venues re-accepted Epstein after 2008 and which didn't
The Edge Foundation as primary vehicle: intellectual access, no formal institutional gatekeeping
Why academic institutions were the most vulnerable to penetration post-conviction
The "redemption narrative": was Epstein presenting himself as having paid his debt?

## VI. COMPARATIVE ANALYSIS
Harvey Weinstein: similar mechanisms, different failure point (multiple accusers speaking simultaneously)
Bernie Madoff: financial legitimacy covering criminal operation; very different crime type
Robert Durst: wealth as protection; geographic mobility
What distinguishes Epstein: the explicit intelligence hypothesis adds a layer Weinstein lacked

## VII. WHAT BROKE THROUGH — THE MIAMI HERALD MODEL
What was structurally different about Julie K. Brown's position:
- Regional newspaper: less Manhattan social entanglement
- No major advertiser relationships with Epstein's network
- Focused on victim testimony rather than elite source access
- Published without elite gatekeeping that stopped ABC and Vanity Fair
The role of #MeToo: changed the media environment's willingness to publish
The role of survivor courage: Giuffre, Farmer going public before Brown published

## VIII. INSTITUTIONAL REFORM RECOMMENDATIONS
How academic institutions should screen major donors (MIT now has explicit reforms)
How media organisations should manage conflicts of interest with elite subjects
How elite social networks could self-police (and why they structurally won't without external pressure)

## IX. FULL APA REFERENCES""",
    ),

    dict(
        id="congressional-reform",
        group="findings",
        description="Congressional oversight and institutional reform analysis",
        output="Findings/Congressional-Oversight-Reform.md",
        prompt=f"""Write a comprehensive analysis of congressional investigations into the Epstein enterprise
and priority recommendations for institutional reform.

YAML frontmatter: tags: [finding, congress, oversight, reform, policy, 2026], date: {DATE}

Structure (minimum 300 lines):

## I. CONGRESSIONAL RECORD TO DATE
Senate Judiciary Committee hearings: what was held, subpoenaed, produced (with dates and outcomes)
House Judiciary / Oversight committee activity
The Epstein Files Transparency Act (2025): sponsors, legislative history, what it requires
The bipartisan investigation into withheld files (NPR 2026): what it has found so far
What Congress has actually learned vs. what it has missed or avoided

## II. THE WITHHELD FILES CONTROVERSY
NPR reporting: files in DOJ portal index with missing content [CORROBORATED]
The executive privilege question: what the Trump administration has claimed and what applies
Congressional subpoena power: what can be compelled from DOJ and what can be withheld
Historical precedent: Senate Watergate Committee vs. executive privilege
What the missing files might contain: analytical assessment

## III. DOJ ACCOUNTABILITY — WHAT HASN'T HAPPENED
OPR review of Acosta NPA: status, whether publicly released
CVRA violation: what congressional remedy is available — amendment to CVRA to create
stronger enforcement mechanism?
The intelligence community declination claim: congressional intelligence oversight (Gang of Eight)
Inspector General investigations: FBI inaction on 1996 Farmer complaint
What subcommittees have jurisdiction over what pieces

## IV. BANKING REGULATORY REFORM
What JPMorgan and Deutsche Bank failures reveal about Bank Secrecy Act / AML gaps
Whether SARs filed by either bank were actually shared with law enforcement — if not, why not?
FinCEN reform: enhanced due diligence, personal liability for compliance officers
The "de-risking" paradox: how to prevent deliberate blindness
Proposed legislation: trafficking-specific AML requirements

## V. PROSECUTION REFORM — CLOSING THE NPA LOOPHOLE
Statutory reform requiring victim notification in all NPA/DPA negotiations
The secret immunity problem: legislative proposal for court approval of unnamed co-conspirator immunity
Mandatory minimum reform: ensuring sex trafficking minimums cannot be bargained away
Victim compensation fund: ensuring civil settlements actually reach identified survivors
The CVRA enhancement: strengthening § 3771 enforcement mechanisms

## VI. ACADEMIC DONATION TRANSPARENCY REFORM
Post-MIT Media Lab reforms: what MIT actually changed
Federal research institution donor disclosure requirements (proposed)
The dark money philanthropy problem: how to require transparency
IRS 990 reform: what additional disclosure nonprofits should be required to make

## VII. INTELLIGENCE COMMUNITY OVERSIGHT REFORM
If Epstein had intelligence connections, what oversight mechanism failed?
The interface problem: FISA court / NSD / prosecution decision chain
Proposed reform: explicit statutory prohibition on intelligence community declination of
trafficking prosecutions without court-approved national security review
Inspector General mandate expansion

## VIII. PRIORITY REFORM TABLE
| Reform | Jurisdiction | Legislative vehicle | Priority (1-5) | Current status |
(Minimum 15 rows covering all major reform recommendations)

## IX. MERMAID — OVERSIGHT GAP DIAGRAM
```mermaid
graph TD
    F1996["1996: Farmer FBI complaint"] -->|"inaction: 9 years"| G1["OVERSIGHT GAP 1\nNo IG review"]
    F2008["2008: NPA — secret immunity"] -->|"no victim notification"| G2["OVERSIGHT GAP 2\nCVRA violation unchecked"]
    F2013["2013-2018: Deutsche Bank\nprocessing trafficking payments"] -->|"no criminal referral"| G3["OVERSIGHT GAP 3\nAML enforcement gap"]
    F2015["2015: ABC kills Robach story"] -->|"no editorial accountability"| G4["OVERSIGHT GAP 4\nMedia self-regulation failure"]
    G1 & G2 & G3 & G4 -->|"combine"| OUTCOME["30+ years of impunity\n80-150+ victims"]
```

## X. FULL APA REFERENCES""",
    ),

    dict(
        id="victim-advocacy",
        group="findings",
        description="Victim-centred advocacy and trauma report",
        output="Findings/Victim-Advocacy-Report.md",
        prompt=f"""Write a comprehensive victim-centred analysis of the Epstein enterprise's impact on survivors.
Apply deep compassion, clinical rigour, and a trauma-informed lens throughout.
Survivors are the central subjects of this investigation, not witnesses or evidence sources.

YAML frontmatter: tags: [finding, victims, advocacy, trauma, compensation, 2026], date: {DATE}

Structure (minimum 300 lines):

## I. THE SURVIVOR LANDSCAPE AS OF 2026
Named survivors in public record: Virginia Giuffre, Maria Farmer, Annie Farmer — their current status
The anonymous majority: victims who remain identified only by pseudonym (Jane, Kate, Carolyn, others)
Survivors who cannot be located or whose status is unknown
The psychological trajectory: what does long-term recovery look like for trafficking survivors?
(Cite clinical literature: Herman 1992 Trauma and Recovery; van der Kolk 2014 The Body Keeps the Score)

## II. THE RECRUITMENT TRAUMA
Clinical analysis of grooming: the escalation mechanism documented in this case (APA DSM-5 framework)
The $200/referral peer-recruitment system: how it creates secondary trauma, survivor guilt,
and complex perpetrator-victim positioning
Developmental vulnerability: average age 14-17 — the adolescent brain's susceptibility to
authority manipulation (Steinberg 2014 adolescent development research)
Substance facilitation (scopolamine evidence): clinical impact of chemically-mediated sexual assault —
disruption of memory formation, long-term consequences of not remembering

## III. INSTITUTIONAL RE-TRAUMATISATION
The 2008 NPA as institutional betrayal: Herman's concept of "betrayal trauma" by trusted institutions
Judge Marra's 2019 ruling: when survivors learned they had been secretly bargained away by DOJ —
the legal confirmation of institutional betrayal
Maria Farmer's 1996 FBI complaint: 9 years of FBI inaction — abandonment by the state
The media suppression: what it means when your story is silenced (ABC, Vanity Fair) —
the "no one will believe you" dynamic externally confirmed
Epstein's 2019 death: how the primary perpetrator dying before trial affected survivor healing
(cf. O'Callaghan et al. 2018 on unresolved trauma when offender dies before accountability)

## IV. THE LITIGATION EXPERIENCE
What survivors experienced in civil depositions: the re-traumatisation of cross-examination
NDA apparatus: how silence was purchased; the psychological impact of being paid to stay silent
The Maxwell trial 2021: what testifying required from "Jane," "Kate," "Carolyn," Annie Farmer
The dignity dimension: Judge Nathan's protective orders for pseudonymous testimony — what this meant
The JPMorgan and Deutsche Bank settlements: whether money reached identifiable survivors

## V. COMPENSATION ANALYSIS
Virginia Giuffre settlements: Epstein estate (2017) and Prince Andrew (~£12M, 2022) [CONFIRMED]
JPMorgan $290M settlement class: distribution mechanism; whether identified survivors received shares
The estate dissolution: $634M estate; how much went to victims vs. co-executors vs. legal fees
International comparison: ECHR trafficking compensation awards; EU Anti-Trafficking Directive standards
The compensation gap: what survivors received vs. what international standards recommend

## VI. WHAT SURVIVORS HAVE PUBLICLY SAID THEY NEED
Virginia Giuffre's public statements and advocacy work
Maria Farmer's published interviews: what she has said about accountability and healing
Annie Farmer's testimony and subsequent advocacy
The common themes: truth, accountability, being believed, systemic change
What "justice" means to survivors (Strang & Braithwaite 2001 restorative justice in sexual offence cases)

## VII. CLINICAL RECOMMENDATIONS — WHAT THESE SURVIVORS NEED
Immediate: survivor-specific counselling, legal support, economic restoration
Medium-term: formal acknowledgment and apology from institutional perpetrators
Long-term: policy reform, anti-trafficking survivor rights legislation
The "victim-centred prosecution" model: how future cases should be handled differently

## VIII. A NOTE ON METHODOLOGY AND LANGUAGE
This document uses "survivor" not "victim" except in legal contexts where "victim" is the term of art.
Survivors are not described by their abuse; they are described as whole persons whose lives were
interrupted and damaged by the enterprise, and who have shown extraordinary courage in coming forward.
The investigative record is built on their testimony. This vault exists because they spoke.

## IX. FULL APA REFERENCES
(Include clinical psychology literature, not just legal sources)""",
    ),

    dict(
        id="global-impact",
        group="findings",
        description="Global institutional impact and policy recommendations",
        output="Findings/Global-Impact-Policy-Recommendations.md",
        prompt=f"""Write a comprehensive analysis of the Epstein case's global institutional impact
and priority policy recommendations for the international community.

YAML frontmatter: tags: [finding, policy, global, reform, institutions, wef, dp-world, 2026], date: {DATE}

Structure (minimum 300 lines):

## I. GLOBAL INSTITUTIONAL DAMAGE ASSESSMENT
Direct institutional casualties of 2026 release:
- WEF: Borge Brende departure — implications for Davos-style global governance
- DP World: Sultan bin Sulayem departure — port operations in 80+ countries; what this means
- Paul Weiss: Brad Karp departure — elite US law firm; implications for legal industry
- Norwegian diplomatic community: Juul/Rod-Larsen departures
Aggregate damage: map which institutions and their global function

## II. THE TRAFFICKING ECOSYSTEM — SYSTEMIC GLOBAL ANALYSIS
The Epstein case as case study in "elite trafficking impunity"
Global trafficking statistics context: ILO 2022 — 4.8M people in forced sexual exploitation worldwide
How wealth + institutional access + jurisdictional arbitrage create impunity at the elite level
What the case reveals about trafficking networks that survive in elite environments
The global pattern: where similar operations have been documented (compare carefully, rate honestly)

## III. FINANCIAL SYSTEM REFORM — GLOBAL
FATF recommendations on trafficking-linked AML: current standard vs. what the Epstein case reveals
Correspondent banking and cross-border enablement
Whether current FATF standards would have caught JPMorgan/Deutsche Bank failures
Proposed: FATF Recommendation 15 extension to require enhanced due diligence for
 clients with sex offender convictions (currently not explicitly required)
Offshore jurisdiction reform: USVI, BVI, Cayman — what treaty changes would improve transparency

## IV. DIPLOMATIC IMMUNITY AND ELITE ACCOUNTABILITY
The Andrew/Mandelson cases: how diplomatic/royal status interacts with criminal accountability
The general problem: how institutional status shields elites globally
Vienna Convention on Diplomatic Relations: can it be amended for serious crimes?
The universal jurisdiction doctrine: why it hasn't been used more aggressively

## V. UN FRAMEWORK — MULTILATERAL RESPONSE
Palermo Protocol review: 25 years on — what needs updating based on cases like Epstein
UNODC trafficking reporting: incorporating elite network trafficking as a distinct category
Special Rapporteur on Trafficking in Persons: what mandate expansion is needed
Human Rights Council: could the Epstein case generate a UN resolution or mechanism?

## VI. MEDIA FREEDOM AND INVESTIGATIVE JOURNALISM
Global suppression pattern: what the ABC/Vanity Fair case means for journalism worldwide
Press freedom organisations' response to the suppression
Anti-SLAPP legislation: global status and why it matters for Epstein-type investigations
Protecting investigative journalists who pursue elite networks
The "public interest" defence in defamation law — strengthening it internationally

## VII. THE DP WORLD SECURITY DIMENSION
What Sultan bin Sulayem's identification in EFTA00666117 means for DP World's governance
Port security and intelligence implications: 80+ countries of logistics infrastructure
International port security standards (ISPS Code) and whether they address leadership integrity
Recommendation: enhanced vetting for senior leadership of critical infrastructure operators

## VIII. SURVIVOR RIGHTS — INTERNATIONAL MINIMUM STANDARD
EU Anti-Trafficking Directive 2011/36/EU: what it requires
Council of Europe Convention on Action against Trafficking in Human Beings: current standards
The compensation gap as an international human rights issue
Proposed: Optional Protocol to the Palermo Protocol on trafficking survivor rights

## IX. PRIORITY REFORM TABLE
| Reform | Mechanism | Jurisdiction | Priority | Precedent |
(Minimum 15 rows)

## X. HISTORICAL ASSESSMENT
How this case will be understood in 20 years
What institutional changes are already occurring
What the 2026 DOJ release permanently changed about elite accountability
The moral lesson for global governance

## XI. FULL APA REFERENCES""",
    ),

    dict(
        id="evidence-inventory",
        group="findings",
        description="Master evidence inventory and source index",
        output="Findings/Evidence-Inventory-Master.md",
        prompt=f"""Write the definitive evidence inventory for the Epstein investigation — a master index
of every piece of evidence, its location, evidentiary value, and current accessibility.

YAML frontmatter: tags: [finding, evidence, inventory, index, doj, court-records, 2026], date: {DATE}

Structure (minimum 350 lines):

## I. PRIMARY COURT DOCUMENTS
Table with columns: Document | Case | Court | Date | Key Content | Public Access | Evidentiary Value

Cover ALL of: SDFL 08-80736 (NPA + Does 1-6 ruling), SDNY 19-CR-490 (Epstein indictment),
SDNY 20-CR-330 (Maxwell — indictment, verdict, sentencing), SDNY 21-CV-06702 (Giuffre v. Andrew),
USVI v. JPMorgan (SDNY), Jane Doe v. JPMorgan (SDNY), NYDFS v. Deutsche Bank consent order,
FCA v. Jes Staley (UK), French investigation (Brunel), NM state proceedings (2026)

## II. DOJ EFTA DOCUMENT INVENTORY
Table: EFTA Number | Content Description | Dataset | Access Level | Significance | Connected Persons

Cover all known documents:
- EFTA00000226, 326, 2503, 3821, 8436 (age-gated)
- EFTA00008744 (scopolamine emails) [CONFIRMED — PUBLIC]
- EFTA00666117 (Sultan bin Sulayem) [CONFIRMED — PUBLIC]
- Trade envoy email chain (Andrew) [CONFIRMED — arrest basis]
- Mandelson classified report [CONFIRMED — arrest basis]
- Note: gap numbers likely represent withheld or redacted materials

## III. PHYSICAL EVIDENCE RECOVERED
"Thousands of sexually explicit photographs" — FBI 2019 search warrant, 9 E 71st St [CONFIRMED]
Flight logs — N908JE (Boeing 727-200) and associated Gulfstreams [CONFIRMED]
The "little black book" — original, published excerpt (Nick Bryant 2015), full status
Electronic devices recovered from Manhattan search — forensic analysis status
The safe contents — what was in the locked safe beyond photographs?
Physical evidence at Palm Beach property — PBPD 2005 evidence collection

## IV. FINANCIAL RECORDS
JPMorgan transaction records produced in USVI civil discovery — what's public
Deutsche Bank NYDFS consent order Exhibit A — transaction descriptions
Epstein estate probate records (USVI superior court) — public filings
Leon Black / Apollo internal Dechert review — full text publicly available
Bear Stearns employment and departure records — status
L Brands financial records — what has been subpoenaed or produced

## V. INDEPENDENT INVESTIGATION REPORTS
Goodwin Procter LLP — MIT Media Lab (Nov 2019): PUBLIC — full report available
Dechert LLP — Apollo / Leon Black (2021): PUBLIC
PBPD investigation records (2005-2006): partially released via civil proceedings
FBI FOIA releases — what has been released, what remains pending

## VI. WITNESS TESTIMONY ON THE RECORD
Table: Witness | Proceeding | Date | Key Testimony | Access (public/sealed)

Cover: "Jane" (Maxwell trial), "Kate" (Maxwell trial), "Carolyn" (Maxwell trial),
Annie Farmer (Maxwell trial — own name), Virginia Giuffre (multiple depositions),
Maria Farmer (civil depositions), Maxwell trial government witnesses,
USVI v. JPMorgan depositions, Jane Doe v. JPMorgan depositions

## VII. JOURNALISM AS PRIMARY SOURCE
Julie K. Brown / Miami Herald (2018): victim interviews + documentary evidence cited [source]
Ronan Farrow + Jill Lepore / New Yorker (2019): MIT internal emails [primary documents obtained]
James B. Stewart / NYT (Aug 2019): scientist interviews on eugenics plan
Vicky Ward: original Vanity Fair draft (unpublished) vs. published version — status?
Amy Robach / ABC (2015 package): killed; Robach confirmed its existence on hot mic 2019

## VIII. WITHHELD AND INACCESSIBLE EVIDENCE
DOJ portal directory files with missing content (NPR 2026) [CORROBORATED]
Sealed court records: list by case and docket number where known
Intelligence community classified materials: what agency, what classification likely
Foreign government records: UK classified documents (Andrew/Mandelson), French investigation files
Maxwell co-operation debriefing: did she provide names? what's classified?

## IX. EVIDENCE ACCESSIBILITY MATRIX
Table: Evidence Type | Current Location | Access Mechanism | Analytical Value | Priority
(Minimum 20 rows covering all major categories)

## X. EVIDENCE COLLECTION GAPS — WHAT REMAINS
Congressional subpoena priority targets (ranked)
FOIA priority targets (ranked)
MLAT request opportunities (which countries, which records)
Whistleblower solicitation: what types of insiders could have relevant evidence

## XI. FULL APA REFERENCES""",
    ),

    # ── Writing / SOPs ───────────────────────────────────────────────────────

    dict(
        id="narrative-prologue",
        group="writing",
        description="Literary narrative prologue for the vault",
        output="Investigations/Epstein/Narrative-Prologue.md",
        prompt=f"""Write the opening narrative chapter of the Epstein Investigation Vault.
This is literary non-fiction at the highest level — Pulitzer-calibre investigative writing.
Not a dry report. The opening of the publication of the century.

YAML frontmatter: tags: [narrative, prologue, literary, investigation], date: {DATE},
summary: Literary narrative prologue — the opening chapter of the Epstein investigation vault.

Minimum 300 lines of narrative prose. Structure:

SCENE 1 — Open in a specific moment, present tense, visceral detail.
Choose: Palm Beach, March 2005. A 14-year-old girl walks into the PBPD. Or:
New York, August 10, 2019. A federal corrections officer approaches a cell door at MCC.
Or: Vienna, January 30, 2026. The DOJ server logs show the download counter hitting 1,000,000 at 11:47 AM.
Whichever opening you choose — make it cinematic, specific, and true to the record.

SCENE 2 — Pull back: the enterprise at its height. 2002-2004. The Boeing 727 over the Atlantic.
Who is on board. What the flight log shows. What it doesn't show.
Use present tense for historical scenes to create immediacy.

SCENE 3 — The system that protected it. Thirty seconds in a room where decisions were made.
The NPA. The journalists told to stand down. The compliance officer whose flag was overruled.
Name no one who is not on the public record. Let the documented facts carry the weight.

SCENE 4 — The reckoning. 2018-2026. Julie K. Brown in a Miami Herald conference room.
A courtroom in Manhattan. A DOJ server at midnight. Two British officials in handcuffs.

CODA — What this vault is. What it demands. Written as a declaration:
The purpose of this vault is not to narrate — it is to prevent forgetting.
Power protects itself through silence, through delay, through complexity.
This vault is the counter-measure.

STYLE REQUIREMENTS:
- Lawrence Wright precision
- Katherine Boo compassion for subjects
- Bryan Stevenson moral clarity
- Zero speculation beyond the documented record
- Every specific fact in the narrative must be [CONFIRMED] or [CORROBORATED]
- No gratuitous detail — only what illuminates
- End each scene with a sentence that opens into the next

No references section needed — this is narrative, not analysis.""",
    ),

    dict(
        id="style-guide",
        group="writing",
        description="Vault writing and editorial style guide",
        output="SOPs/Writing-Style-Guide.md",
        prompt=f"""Write the definitive writing and editorial style guide for the Epstein Investigation Vault.

YAML frontmatter: tags: [sop, style, writing, editorial, standards], date: {DATE}

Structure (minimum 150 lines):

## I. VAULT PURPOSE AND VOICE
What this vault is: an intelligence-style investigative archive, not journalism, not memoir
Primary voice: analytical, precise, confident where evidence warrants, openly uncertain where it doesn't
Secondary voice: the narrative prologue and profile sections may use literary non-fiction style

## II. CONFIDENCE RATING SYSTEM — PRECISE USAGE
Define each level with examples drawn from this investigation:
[CONFIRMED]: must cite specific court record, DOJ statement, or regulatory finding. NOT: "widely reported"
[CORROBORATED]: minimum 2 independent credible sources, both named. NOT: "multiple sources report"
[SINGLE SOURCE]: one credible established outlet. Name the outlet and article. NOT: "one source says"
[UNVERIFIED]: must explain why it's included despite not meeting higher standard (context, leads)

## III. THE #CLAIM TAG — RULES
Apply #claim to EVERY negative characterisation of a living non-convicted person
Apply it in-line: "met with victims #claim" — not at the end of a paragraph
Do NOT use #claim for: CONFIRMED court findings, documentary evidence, regulatory findings
Special cases: how to handle convicted persons, deceased persons, organisations

## IV. APA 7TH EDITION STANDARDS
In-text citations: (Author, Year) or (Author, Year, p. X) for quotes
Reference list format for: journal articles, news articles, court documents, government publications,
books, websites, DOJ portal documents (EFTA format)
Example citations for the most common source types in this vault

## V. YAML FRONTMATTER REQUIRED FIELDS
tags: [category, subcategory, key-if-important]
date: YYYY-MM-DD
summary: one sentence
verified: true / partial / false
source: primary sources used
case-refs: [case numbers if applicable]
Optional: author-note, confidence-overall

## VI. MERMAID DIAGRAM CONVENTIONS
When to use: network relationships, timelines, process flows, hierarchies
Node labels: keep under 40 characters; use newlines for multi-line
Edge labels: brief verb phrases ("paid $158M", "convicted 6 counts")
Subgraphs: use for geographic or institutional groupings
Direction: TD (top-down) for hierarchies; LR (left-right) for flows; TB for timelines

## VII. PROHIBITED PRACTICES
Never present speculation as fact (downgrade to [UNVERIFIED] and explain why included)
Never use loaded language without evidence ("orchestrated", "masterminded" — only if court-found)
Never omit confidence ratings on significant claims
Never cite conspiracy sites, tabloids, or unverified social media
Never combine #claim persons with unqualified assertions about them

## VIII. HANDLING CONFLICTING SOURCES
When two reliable sources disagree: document both, explain the conflict, assign confidence to each
When documentary evidence conflicts with testimony: note both, note which is primary
Never resolve a conflict by picking the more dramatic version

## IX. CROSS-REFERENCING CONVENTIONS
WikiLinks: [[People/Full-Name]], [[Findings/Filename-Without-Extension]], [[Locations/Name]]
Use WikiLinks liberally — they make the vault navigable and connective
When creating a new profile: check whether one already exists before writing

## X. DOCUMENT STRUCTURE STANDARDS
Every finding document: YAML → title → summary box → ToC → sections → APA references
Every person profile: YAML → header → background → Epstein connection → evidence → status → links → refs
Every location profile: YAML → header → property facts → operational role → evidence recovered → disposal

## XI. WHAT THIS VAULT IS NOT
Not a platform for unverified conspiracy theories
Not a forum for naming people without evidentiary basis
Not journalism (it doesn't break stories; it synthesises the public record)
Not legal advice
Not a replacement for primary sources — always cite, always link where possible""",
    ),

]

# ── Build task ID lookup ───────────────────────────────────────────────────────

TASK_MAP = {t["id"]: t for t in TASKS}
GROUP_MAP: dict[str, list] = {}
for t in TASKS:
    GROUP_MAP.setdefault(t["group"], []).append(t)


# ── Writer class ──────────────────────────────────────────────────────────────

class DocumentWriter:
    """Writes one vault document via the Anthropic API."""

    def __init__(self, task: dict, vault_root: Path):
        self.task = task
        self.vault_root = vault_root
        self.output_path = vault_root / task["output"]
        self.result: dict = {}

    def run(
        self,
        client: anthropic.Anthropic,
        model: str,
        dry_run: bool,
        force: bool,
    ) -> None:
        tid = self.task["id"]
        desc = self.task["description"]
        out  = self.task["output"]

        # Skip existing unless --force
        if not force and self.output_path.exists():
            print(f"  [{tid:22}] SKIP (already exists) — use --force to overwrite")
            self.result = {"id": tid, "status": "skipped", "path": str(self.output_path)}
            return

        if dry_run:
            print(f"  [{tid:22}] DRY  -> {out}")
            print(f"               prompt: {self.task['prompt'][:120].strip()}...")
            self.result = {"id": tid, "status": "dry-run", "path": str(self.output_path)}
            return

        print(f"  [{tid:22}] Writing: {desc}...")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                system=WRITER_SYSTEM,
                messages=[{"role": "user", "content": self.task["prompt"]}],
            )
            content = response.content[0].text.strip()

            # Ensure output directory exists
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text(content, encoding="utf-8")

            lines = content.count("\n") + 1
            words = len(content.split())
            print(f"  [{tid:22}] DONE  -> {out}  ({lines} lines, {words:,} words)")
            self.result = {
                "id": tid,
                "status": "written",
                "path": str(self.output_path),
                "lines": lines,
                "words": words,
            }

        except anthropic.RateLimitError as e:
            print(f"  [{tid:22}] RATE LIMIT: {e}")
            self.result = {"id": tid, "status": "rate_limit", "error": str(e)}
        except Exception as e:
            print(f"  [{tid:22}] ERROR: {e}")
            self.result = {"id": tid, "status": "error", "error": str(e)}


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_writer(
    client: anthropic.Anthropic,
    tasks: list[dict],
    model: str,
    dry_run: bool,
    force: bool,
    sequential: bool,
    delay: float = 1.0,
) -> list[dict]:
    """Run all tasks, parallel by default, sequential if --sequential."""

    results: list[dict] = []
    lock = threading.Lock()

    def run_one(task: dict) -> None:
        writer = DocumentWriter(task, VAULT_ROOT)
        writer.run(client, model, dry_run, force)
        with lock:
            results.append(writer.result)

    if sequential:
        for t in tasks:
            run_one(t)
            time.sleep(delay)
    else:
        threads = []
        for i, t in enumerate(tasks):
            th = threading.Thread(target=run_one, args=(t,), name=t["id"])
            threads.append(th)
            th.start()
            time.sleep(delay)  # stagger to avoid 429
        for th in threads:
            th.join()

    return results


# ── Summary and logging ───────────────────────────────────────────────────────

def print_summary(results: list[dict], model: str, elapsed: float) -> None:
    written   = [r for r in results if r.get("status") == "written"]
    skipped   = [r for r in results if r.get("status") == "skipped"]
    errors    = [r for r in results if r.get("status") in ("error", "rate_limit")]
    dry       = [r for r in results if r.get("status") == "dry-run"]

    total_lines = sum(r.get("lines", 0) for r in written)
    total_words = sum(r.get("words", 0) for r in written)

    print(f"\n{'='*64}")
    print(f"  VAULT WRITER COMPLETE  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Model    : {model}")
    print(f"  Elapsed  : {elapsed:.0f}s")
    print(f"  Written  : {len(written)}  ({total_lines:,} lines, {total_words:,} words)")
    print(f"  Skipped  : {len(skipped)}")
    print(f"  Dry-run  : {len(dry)}")
    print(f"  Errors   : {len(errors)}")

    if errors:
        print(f"\n  ERRORS:")
        for r in errors:
            print(f"    [{r['id']}] {r.get('error', '?')[:80]}")

    if written:
        print(f"\n  FILES WRITTEN:")
        for r in sorted(written, key=lambda x: x.get("words", 0), reverse=True):
            p = Path(r["path"]).relative_to(VAULT_ROOT)
            print(f"    {str(p):55}  {r.get('lines',0):4} lines  {r.get('words',0):6,} words")

    print(f"{'='*64}\n")


def log_session(results: list[dict], log_dir: Path) -> Path:
    import json
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"writer_{ts}.json"
    log_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return log_file


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="vault_writer.py — autonomous document writer for the Epstein vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--task", "-t", nargs="+", metavar="ID",
        help="Task IDs to run (default: all pending). Use --list to see IDs.",
    )
    p.add_argument(
        "--group", "-g", nargs="+", metavar="GROUP",
        choices=list(GROUP_MAP.keys()),
        help=f"Run all tasks in a group. Groups: {list(GROUP_MAP.keys())}",
    )
    p.add_argument("--opus",       action="store_true", help=f"Use {OPUS_MODEL}")
    p.add_argument("--sonnet",     action="store_true", help=f"Use {DEFAULT_MODEL} (default)")
    p.add_argument("--model", "-m", default=DEFAULT_MODEL, help="Model override")
    p.add_argument("--dry-run", "-n", action="store_true", help="Preview — no writes")
    p.add_argument("--force", "-f",   action="store_true", help="Overwrite existing files")
    p.add_argument("--sequential",    action="store_true", help="One at a time (no threads)")
    p.add_argument("--list", "-l",    action="store_true", help="List all tasks and exit")
    p.add_argument("--delay",  type=float, default=1.5, metavar="SECS",
                   help="Seconds between thread starts (default: 1.5)")
    args = p.parse_args()

    # --list
    if args.list:
        print(f"\n  {'ID':22}  {'GROUP':10}  {'EXISTS':6}  DESCRIPTION")
        print(f"  {'-'*22}  {'-'*10}  {'-'*6}  {'-'*40}")
        for t in TASKS:
            path = VAULT_ROOT / t["output"]
            exists = "YES" if path.exists() else "no"
            print(f"  {t['id']:22}  {t['group']:10}  {exists:6}  {t['description']}")
        print(f"\n  Total: {len(TASKS)} tasks\n")
        return

    # Resolve model
    model = OPUS_MODEL if args.opus else (DEFAULT_MODEL if args.sonnet else args.model)

    # Resolve tasks
    if args.task:
        unknown = [tid for tid in args.task if tid not in TASK_MAP]
        if unknown:
            p.error(f"Unknown task ID(s): {unknown}. Use --list to see valid IDs.")
        selected = [TASK_MAP[tid] for tid in args.task]
    elif args.group:
        selected = [t for g in args.group for t in GROUP_MAP.get(g, [])]
    else:
        selected = TASKS  # all

    # API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Count existing
    existing = sum(1 for t in selected if (VAULT_ROOT / t["output"]).exists())
    pending  = len(selected) - existing

    print(f"\n{'='*64}")
    print(f"  VAULT WRITER  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Model   : {model}")
    print(f"  Tasks   : {len(selected)} selected  ({pending} pending, {existing} existing)")
    print(f"  Mode    : {'DRY RUN' if args.dry_run else 'WRITE'}"
          f"  {'(force overwrite)' if args.force else ''}")
    print(f"  Threads : {'sequential' if args.sequential else 'parallel'}")
    print(f"{'='*64}\n")

    start = time.time()
    results = run_writer(
        client=client,
        tasks=selected,
        model=model,
        dry_run=args.dry_run,
        force=args.force,
        sequential=args.sequential,
        delay=args.delay,
    )
    elapsed = time.time() - start

    print_summary(results, model, elapsed)

    if not args.dry_run:
        log_file = log_session(results, LOG_DIR)
        print(f"  Session logged -> {log_file.name}\n")


if __name__ == "__main__":
    main()
