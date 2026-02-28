#!/usr/bin/env python3
"""
vault_scout.py — Active intelligence extractor for the Epstein OSINT Vault.

Where vault_logger.py routes ONE piece of known info,
vault_scout.py feeds a SOURCE DOCUMENT to ALL specialist agents simultaneously.
Each specialist independently extracts what's relevant to their branch.

This is the "little agents collecting info" mode:
  - PeopleAgent   → extracts all people mentions, builds/updates profiles
  - FindingsAgent → extracts evidence, document references, legal facts
  - LocationsAgent → extracts properties, addresses, flight routes
  - TimelineAgent → extracts all dated events for chronology
  - SopsAgent     → extracts any methodology/technique mentions
  - CoordinatorAgent → extracts open questions, leads, new tasks

Each agent runs independently (parallel via threads) then writes its
findings to the correct vault branch. The coordinator agent also
generates cross-links between new entries.

USAGE
-----
  # Feed a raw text document (article, DOJ file excerpt, court transcript)
  python vault_scout.py --source article.txt

  # Pipe text directly
  cat doj_release.txt | python vault_scout.py

  # Scout specific branches only
  python vault_scout.py --source doc.txt --branches people findings timeline

  # Use Opus for highest-quality extraction
  python vault_scout.py --source doc.txt --opus

  # Batch API mode — submit all agents simultaneously, 50% cheaper, async
  python vault_scout.py --source doc.txt --batch

  # Dry run — see what each agent would extract, no vault writes
  python vault_scout.py --source doc.txt --dry-run
"""

import sys
import os
import json
import time
import argparse
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed.\nRun: pip install anthropic")
    sys.exit(1)

VAULT_ROOT = Path(__file__).parent.parent.resolve()
UTILS_DIR = Path(__file__).parent.resolve()
LOG_DIR = UTILS_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-6"

ALL_BRANCHES = ["people", "findings", "locations", "timeline", "sops", "coordinator"]

CONTENT_POLICY = """CONTENT POLICY — NON-NEGOTIABLE:
- Only extract facts from: DOJ files (justice.gov/epstein), PACER, congressional records, DOJ press releases, established major journalism
- Tag #claim on ANY unverified allegation against a living non-convicted person
- SKIP: Pizzagate references, celebrity deaths (no Epstein court connection), organ harvesting (no docs), unrelated historical events
- NEVER fabricate EFTA codes, PACER case numbers, or document identifiers
- If a fact cannot be verified from the source: tag #claim"""

VAULT_FORMAT = """OBSIDIAN VAULT FORMAT:
- YAML frontmatter between --- (tags, date, source, verified, case-ref)
- WikiLinks: [[People/Name]] [[Locations/Place]] [[Findings/Document]]
- Tables: | Field | Value | with header + separator rows
- #claim inline after unverified assertions
- Source: (DOJ, PACER 19-CR-490, NYT 2019-07-08)
- Dates: YYYY-MM-DD
- Bold status: **Status: Convicted** / **Status: Active**"""


def build_extractor_system(branch: str, vault_context: str) -> str:
    """Build the system prompt for a branch's extraction agent."""
    branch_roles = {
        "people": (
            "Extract ALL people mentioned: names, roles, relationships, dates of "
            "arrest/resignation/conviction, aliases, nationalities. "
            "For each person: determine if they already exist in vault (update) or are new (create). "
            "Generate one vault entry per NEW or UPDATED person."
        ),
        "findings": (
            "Extract ALL evidence, documents, legal records, email references, "
            "court filings, DOJ file numbers (EFTA codes), FBI reports, bank records, "
            "flight logs, and wire transfers mentioned. "
            "Generate a vault finding entry for each significant piece of evidence."
        ),
        "locations": (
            "Extract ALL locations: properties, addresses, islands, ranches, apartments, "
            "flight routes, and any geographic data. "
            "Note which people are connected to each location and when."
        ),
        "timeline": (
            "Extract ALL events with specific dates. Every dated event goes on the timeline. "
            "Format each as a timeline table row: | YYYY-MM-DD | Event description | People | Source |"
        ),
        "sops": (
            "Extract any OSINT methodology, investigative techniques, tools, or research "
            "procedures described or implied. Only extract if genuinely methodologically useful."
        ),
        "coordinator": (
            "Extract open questions, unresolved leads, pending tasks, and cross-branch connections. "
            "Identify what further investigation is needed and generate task items."
        ),
    }

    role = branch_roles.get(branch, "Extract relevant information for your branch.")

    return f"""You are the {branch.upper()} extraction specialist for the Epstein OSINT Vault.

{CONTENT_POLICY}

{VAULT_FORMAT}

YOUR VAULT (current knowledge — use to identify what's new vs. already known):
{vault_context}

YOUR EXTRACTION TASK:
{role}

OUTPUT FORMAT — respond ONLY with valid JSON, no markdown fences:
{{
  "branch": "{branch}",
  "extractions": [
    {{
      "classification": "NEW|UPDATE|CONFIRMED|CLAIM|SKIP",
      "confidence": 0.0,
      "target_file": "Filename.md or null",
      "summary": "One-line description of what was extracted",
      "vault_entry": "Complete formatted vault markdown or null",
      "cross_links": ["[[People/Name]]", "[[Findings/Doc]]"],
      "warnings": []
    }}
  ],
  "extraction_notes": "Overall notes about what you found in this document"
}}

If nothing relevant to your branch is found: return extractions as empty array [].
Do NOT fabricate information not present in the source document."""


# ── Per-branch extractor ──────────────────────────────────────────────────────

class BranchExtractor:
    """Runs one branch's extraction pass over a source document."""

    def __init__(self, branch: str, vault_root: Path):
        self.branch = branch
        self.vault_root = vault_root
        self.result: Optional[dict] = None
        self.error: Optional[str] = None

    def _load_vault_context(self) -> str:
        """Load this branch's vault files as context."""
        from agents.specialists import get_agent
        agent = get_agent(self.branch, self.vault_root)
        return agent.vault_context

    def _read_file(self, path: Path, max_chars: int = 2000) -> str:
        try:
            content = path.read_text(encoding="utf-8")
            return content[:max_chars] + ("..." if len(content) > max_chars else "")
        except Exception:
            return ""

    def extract(
        self,
        client: anthropic.Anthropic,
        source_text: str,
        model: str,
    ) -> dict:
        vault_context = self._load_vault_context()
        system = build_extractor_system(self.branch, vault_context)

        user_msg = (
            f"Extract all {self.branch}-relevant information from this source document:\n\n"
            f"---SOURCE BEGIN---\n{source_text}\n---SOURCE END---\n\n"
            f"Current date: {datetime.now().strftime('%Y-%m-%d')}"
        )

        print(f"  [{self.branch.upper():12}] Streaming {model}...", end="", flush=True)
        full_response = ""

        try:
            with client.messages.stream(
                model=model,
                max_tokens=8192,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    print(".", end="", flush=True)
        except anthropic.APITimeoutError:
            print(" TIMEOUT")
            return {"branch": self.branch, "extractions": [], "extraction_notes": "TIMEOUT"}
        except anthropic.APIError as e:
            print(f" API ERROR: {e}")
            return {"branch": self.branch, "extractions": [], "extraction_notes": str(e)}

        print(" done")

        # Parse JSON
        text = full_response.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"  [{self.branch.upper():12}] WARNING: JSON parse failed")
            return {"branch": self.branch, "extractions": [], "extraction_notes": "PARSE_ERROR"}


# ── Vault writer ──────────────────────────────────────────────────────────────

def write_extractions(branch: str, extractions: list[dict], vault_root: Path) -> list[str]:
    """Write all extracted vault entries to the correct branch directory."""
    from agents.specialists import get_agent

    written = []
    branch_dirs = {
        "people":      vault_root / "People",
        "findings":    vault_root / "Findings",
        "locations":   vault_root / "Locations",
        "sops":        vault_root / "SOPs",
        "coordinator": vault_root / "Investigations" / "Epstein",
        "timeline":    vault_root,  # Timeline.md is at root
    }
    branch_dir = branch_dirs.get(branch, vault_root)

    for extraction in extractions:
        classification = extraction.get("classification", "SKIP")
        if classification == "SKIP" or not extraction.get("vault_entry"):
            continue

        target = extraction.get("target_file")
        if not target:
            slug = extraction.get("summary", "entry")[:30].replace(" ", "-")
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            target = f"{slug}-{ts}.md" if branch != "timeline" else "Timeline.md"

        entry = extraction["vault_entry"]
        summary = extraction.get("summary", "")

        if branch == "timeline":
            # Special handling: append to Timeline.md
            timeline_path = vault_root / "Timeline.md"
            if timeline_path.exists():
                existing = timeline_path.read_text(encoding="utf-8")
                # Insert after table header
                lines = existing.split("\n")
                insert_at = 0
                for i, line in enumerate(lines):
                    if line.startswith("|---") or line.startswith("| ---"):
                        insert_at = i + 1
                        break
                lines.insert(insert_at, entry)
                timeline_path.write_text("\n".join(lines), encoding="utf-8")
                print(f"    [{branch.upper():12}] Timeline entry: {summary[:60]}")
                written.append(str(timeline_path))
        else:
            target_path = branch_dir / target
            if target_path.exists() and classification in ("UPDATE", "CONFIRMED"):
                existing = target_path.read_text(encoding="utf-8")
                update = f"\n\n---\n\n## Scout Update — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}"
                target_path.write_text(existing + update, encoding="utf-8")
                print(f"    [{branch.upper():12}] Updated: {target}")
            else:
                target_path.write_text(entry, encoding="utf-8")
                print(f"    [{branch.upper():12}] Created: {target}")
            written.append(str(target_path))

    return written


# ── Batch API mode ────────────────────────────────────────────────────────────

def submit_batch_extractions(
    client: anthropic.Anthropic,
    branches: list[str],
    source_text: str,
    vault_root: Path,
    model: str,
) -> str:
    """Submit all branch extractions to Batch API simultaneously."""
    requests = []
    for branch in branches:
        extractor = BranchExtractor(branch, vault_root)
        vault_context = extractor._load_vault_context()
        system = build_extractor_system(branch, vault_context)
        requests.append({
            "custom_id": f"branch_{branch}",
            "params": {
                "model": model,
                "max_tokens": 3000,
                "system": system,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Extract all {branch}-relevant information from this source document:\n\n"
                        f"---SOURCE BEGIN---\n{source_text}\n---SOURCE END---\n\n"
                        f"Current date: {datetime.now().strftime('%Y-%m-%d')}"
                    ),
                }],
            },
        })

    print(f"  Submitting {len(requests)} branch agents to Batch API (50% cost reduction)...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}")
    print(f"  All {len(branches)} agents submitted simultaneously.")
    print(f"\n  Check status: python vault_scout.py --batch-status {batch.id}")
    print(f"  Collect:      python vault_scout.py --batch-collect {batch.id}")

    # Save state
    state_file = LOG_DIR / f"scout_batch_{batch.id}.json"
    state_file.write_text(json.dumps({
        "batch_id": batch.id,
        "submitted": datetime.now().isoformat(),
        "branches": branches,
        "model": model,
        "source_preview": source_text[:500],
    }, indent=2), encoding="utf-8")
    print(f"  State saved → {state_file.name}")

    return batch.id


def collect_batch_results(
    client: anthropic.Anthropic,
    batch_id: str,
    vault_root: Path,
    dry_run: bool,
) -> None:
    """Poll and collect results from a submitted batch, then write to vault."""
    # Load state
    state_file = LOG_DIR / f"scout_batch_{batch_id}.json"
    if not state_file.exists():
        print(f"ERROR: No state file for batch {batch_id}")
        sys.exit(1)

    print(f"\nPolling batch {batch_id}...")
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        print(
            f"  [{datetime.now().strftime('%H:%M:%S')}] {batch.processing_status} | "
            f"processing: {counts.processing} | succeeded: {counts.succeeded} | errored: {counts.errored}"
        )
        if batch.processing_status == "ended":
            break
        time.sleep(30)

    print("\nCollecting results...")
    all_results = {}
    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            print(f"  WARN: {result.custom_id} failed")
            continue

        branch = result.custom_id.replace("branch_", "")
        text = result.result.message.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            print(f"  [{branch.upper():12}] JSON parse error")
            continue

        extractions = data.get("extractions", [])
        notes = data.get("extraction_notes", "")
        print(f"  [{branch.upper():12}] {len(extractions)} extraction(s) — {notes[:80]}")
        all_results[branch] = data

    # Write to vault
    if not dry_run:
        print("\nWriting to vault...")
        for branch, data in all_results.items():
            written = write_extractions(branch, data.get("extractions", []), vault_root)
            if written:
                print(f"  [{branch.upper():12}] {len(written)} file(s) written")

    # Log
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"scout_results_{ts}.json"
    log_file.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"\n[DONE] Results logged → {log_file.name}")


# ── Interactive (streaming, parallel threads) ─────────────────────────────────

def run_parallel_extraction(
    client: anthropic.Anthropic,
    source_text: str,
    branches: list[str],
    model: str,
    dry_run: bool,
) -> None:
    """
    Run all branch extractors in parallel threads.
    Each agent works independently on the same source document.
    """
    results: dict[str, dict] = {}
    lock = threading.Lock()

    def run_branch(branch: str):
        extractor = BranchExtractor(branch, VAULT_ROOT)
        data = extractor.extract(client, source_text, model)
        with lock:
            results[branch] = data

    print(f"\n  Spawning {len(branches)} specialist agents in parallel...\n")

    threads = [threading.Thread(target=run_branch, args=(b,)) for b in branches]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"\n  All agents done. Writing to vault...\n")

    all_written = []
    for branch in branches:
        data = results.get(branch, {})
        extractions = data.get("extractions", [])
        notes = data.get("extraction_notes", "")
        print(f"  [{branch.upper():12}] {len(extractions)} extraction(s)")
        if notes:
            print(f"               Notes: {notes[:100]}")

        if not dry_run and extractions:
            written = write_extractions(branch, extractions, VAULT_ROOT)
            all_written.extend(written)

    # Summary
    print(f"\n  Total files written: {len(all_written)}")
    for f in all_written:
        print(f"    {Path(f).relative_to(VAULT_ROOT)}")

    # Log
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"scout_{ts}.json"
    log_file.write_text(json.dumps({
        "timestamp": ts,
        "source_preview": source_text[:500],
        "branches": branches,
        "model": model,
        "results": results,
        "files_written": all_written,
    }, indent=2, default=str), encoding="utf-8")
    print(f"\n  Session logged → {log_file.name}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Vault Scout — extract & route intel from source documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--source", "-s", metavar="FILE",
                   help="Source document file to extract from")
    p.add_argument("--branches", "-b", nargs="+", choices=ALL_BRANCHES, default=ALL_BRANCHES,
                   help=f"Branches to run (default: all). Choices: {ALL_BRANCHES}")
    p.add_argument("--opus", action="store_true",
                   help=f"Use {OPUS_MODEL} (higher quality, higher cost)")
    p.add_argument("--model", "-m", default=DEFAULT_MODEL)
    p.add_argument("--batch", action="store_true",
                   help="Submit all agents to Batch API (50%% cheaper, async)")
    p.add_argument("--batch-status", metavar="BATCH_ID",
                   help="Check status of a submitted batch")
    p.add_argument("--batch-collect", metavar="BATCH_ID",
                   help="Collect and write results from a completed batch")
    p.add_argument("--dry-run", "-n", action="store_true",
                   help="Show extractions without writing to vault")
    args = p.parse_args()

    model = OPUS_MODEL if args.opus else args.model

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"  VAULT SCOUT  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Model  : {model}")
    print(f"  Agents : {args.branches}")
    if args.dry_run:
        print(f"  MODE   : DRY RUN")
    print(f"{'='*60}")

    # Status check
    if args.batch_status:
        from vault_logger import check_batch_status
        check_batch_status(client, args.batch_status)
        return

    # Collect batch results
    if args.batch_collect:
        collect_batch_results(client, args.batch_collect, VAULT_ROOT, args.dry_run)
        return

    # Read source document
    if args.source:
        source_text = Path(args.source).read_text(encoding="utf-8").strip()
    elif not sys.stdin.isatty():
        source_text = sys.stdin.read().strip()
    else:
        print("ERROR: Provide a source document with --source FILE or pipe text.")
        p.print_help()
        sys.exit(1)

    print(f"\n  Source: {len(source_text)} chars")
    print(f"  Preview: {source_text[:120]}...\n")

    if args.batch:
        submit_batch_extractions(client, args.branches, source_text, VAULT_ROOT, model)
    else:
        run_parallel_extraction(client, source_text, args.branches, model, args.dry_run)

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
