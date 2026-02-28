#!/usr/bin/env python3
"""
vault_logger.py — Semantic routing utility for the Epstein OSINT Vault.

Automatically classifies incoming information into the correct vault branch,
fact-checks via a specialist agent, and writes formatted vault entries.

USAGE
-----
  # Single item, interactive (streaming, ~10s)
  python vault_logger.py "Peter Mandelson was arrested February 23 2026 by Thames Valley Police"

  # Read from file
  python vault_logger.py --file input.txt

  # Pipe from stdin
  echo "Some new info" | python vault_logger.py

  # Use Opus 4.6 for deep analysis (higher quality, higher cost)
  python vault_logger.py --opus "Complex multi-domain information..."

  # Batch mode — 50% cost reduction via Anthropic Batch API (async, minutes latency)
  python vault_logger.py --batch items.txt      # items.txt: entries separated by ---
  python vault_logger.py --batch-status BATCH_ID  # check a running batch

  # Dry run — shows routing without writing
  python vault_logger.py --dry-run "Test info"

  # Force to a specific branch (skip router)
  python vault_logger.py --branch people "New person info"

MODELS
------
  Router  : claude-haiku-4-5-20251001  (cheap, fast classification)
  Agents  : claude-sonnet-4-6          (default — balance of quality/cost)
  --opus  : claude-opus-4-6            (highest quality, 5x more expensive)
  --batch : 50% off via Batch API      (async — minutes to hours latency)
"""

import sys
import os
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed.\nRun: pip install anthropic")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────

VAULT_ROOT = Path(__file__).parent.parent.resolve()
UTILS_DIR = Path(__file__).parent.resolve()
LOG_DIR = UTILS_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Models ────────────────────────────────────────────────────────────────────

ROUTER_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-6"

# ── Router ────────────────────────────────────────────────────────────────────

ROUTER_SYSTEM = """You are a semantic router for an Epstein OSINT investigation vault.

Available branches:
  people      — Individual profiles (names, arrests, resignations, biographical data)
  findings    — Evidence, documents, court records, DOJ files, email analysis
  locations   — Properties, addresses, flight logs, geographic records
  timeline    — Any event with a specific date that belongs on the chronology
  sops        — OSINT research methodology, tools, procedures
  coordinator — Case management, open tasks, investigation priorities

Rules:
- Route to ALL applicable branches (one item can be both 'people' and 'timeline')
- 'timeline' always included when a specific date is present
- is_claim = true when the assertion is unverified or against a non-convicted living person
- confidence: 0.0–1.0

Respond ONLY with valid JSON — no markdown, no explanation:
{
  "branches": ["branch1", "branch2"],
  "entities": ["Name", "Organization", "Location"],
  "date": "YYYY-MM-DD or null",
  "is_claim": false,
  "confidence": 0.95,
  "reason": "One-line explanation"
}"""


def route(client: anthropic.Anthropic, info: str) -> dict:
    """Classify incoming info into vault branches using Haiku (fast, cheap)."""
    response = client.messages.create(
        model=ROUTER_MODEL,
        max_tokens=256,
        system=ROUTER_SYSTEM,
        messages=[{"role": "user", "content": f"Route this:\n\n{info}"}],
    )
    text = response.content[0].text.strip()
    # Strip code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


# ── Input helpers ─────────────────────────────────────────────────────────────

def get_single_input(args) -> str:
    if args.info:
        return " ".join(args.info)
    if args.file and not args.batch:
        return Path(args.file).read_text(encoding="utf-8").strip()
    if not sys.stdin.isatty():
        return sys.stdin.read().strip()
    print("No input. Use a positional argument, --file, or pipe text.")
    sys.exit(1)


def read_batch_items(path: str) -> list[str]:
    """Split a file into items using '---' as separator."""
    raw = Path(path).read_text(encoding="utf-8")
    items = [item.strip() for item in raw.split("---") if item.strip()]
    return items


# ── Single-item processing ────────────────────────────────────────────────────

def process_single(
    client: anthropic.Anthropic,
    info: str,
    model: str,
    dry_run: bool,
    force_branch: Optional[str] = None,
) -> dict:
    """Route and process one item. Returns summary dict."""
    from agents.specialists import get_agent

    # Step 1: Route
    if force_branch:
        routing = {
            "branches": [force_branch],
            "entities": [],
            "date": None,
            "is_claim": False,
            "confidence": 1.0,
            "reason": "Branch forced by --branch flag",
        }
        print(f"  [ROUTE] Forced → {force_branch}")
    else:
        print("  [ROUTE] Haiku classifying...", end="", flush=True)
        routing = route(client, info)
        print(f" {routing['branches']} (confidence {routing['confidence']})")
        print(f"         Entities: {routing.get('entities')}")
        print(f"         Date: {routing.get('date')}  |  Claim: {routing.get('is_claim')}")

    outputs = {}

    # Step 2: Specialist agents
    for branch in routing["branches"]:
        print(f"\n  [{branch.upper()} AGENT]")
        try:
            agent = get_agent(branch, VAULT_ROOT)
            written = agent.process(client, info, routing, model, dry_run)
            outputs[branch] = written or "no write (OFF_TOPIC or CONTRADICTS)"
        except Exception as e:
            print(f"    ERROR: {e}")
            outputs[branch] = f"ERROR: {e}"

    return {"routing": routing, "outputs": outputs}


# ── Batch processing ──────────────────────────────────────────────────────────

def submit_batch_routing(client: anthropic.Anthropic, items: list[str]) -> str:
    """
    Submit all items for routing via the Batch API (50% cheaper).
    Returns the batch ID for polling.
    """
    requests = [
        {
            "custom_id": f"item_{i}",
            "params": {
                "model": ROUTER_MODEL,
                "max_tokens": 256,
                "system": ROUTER_SYSTEM,
                "messages": [{"role": "user", "content": f"Route this:\n\n{item}"}],
            },
        }
        for i, item in enumerate(items)
    ]

    print(f"  Submitting {len(requests)} items to Batch API...")
    batch = client.messages.batches.create(requests=requests)
    print(f"  Batch ID: {batch.id}")
    print(f"  Status  : {batch.processing_status}")
    return batch.id


def poll_batch(client: anthropic.Anthropic, batch_id: str, timeout_s: int = 3600) -> list:
    """Poll until batch completes. Returns list of (custom_id, routing_dict)."""
    print(f"\n  Polling batch {batch_id}...")
    start = time.time()

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        status = batch.processing_status

        counts = batch.request_counts
        print(
            f"  [{datetime.now().strftime('%H:%M:%S')}] {status} — "
            f"processed: {counts.processing} / succeeded: {counts.succeeded} / errored: {counts.errored}"
        )

        if status == "ended":
            break

        if time.time() - start > timeout_s:
            print(f"  TIMEOUT after {timeout_s}s — use --batch-status {batch_id} to resume")
            sys.exit(1)

        time.sleep(30)  # Batch API recommends polling every 30s+

    # Collect results
    results = []
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            text = result.result.message.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:].strip()
            try:
                routing = json.loads(text)
            except json.JSONDecodeError:
                routing = {"branches": ["coordinator"], "entities": [], "date": None,
                           "is_claim": False, "confidence": 0.0, "reason": "parse error"}
            results.append((result.custom_id, routing))
        else:
            print(f"  WARN: {result.custom_id} failed: {result.result}")

    return results


def process_batch(
    client: anthropic.Anthropic,
    batch_file: str,
    model: str,
    dry_run: bool,
) -> None:
    """
    Batch mode:
    1. Read items from file (split by ---)
    2. Route all via Batch API (50% cheaper)
    3. Process each routing result with specialists (streaming, sequential)
    """
    from agents.specialists import get_agent

    items = read_batch_items(batch_file)
    print(f"\n[BATCH] {len(items)} items from {batch_file}")
    print(f"[BATCH] Router model : {ROUTER_MODEL} (Batch API — 50% cost reduction)")
    print(f"[BATCH] Agent model  : {model}")

    # Submit routing batch
    batch_id = submit_batch_routing(client, items)

    # Save batch ID so user can resume if needed
    batch_log = LOG_DIR / f"batch_{batch_id}.json"
    batch_log.write_text(json.dumps({
        "batch_id": batch_id,
        "submitted": datetime.now().isoformat(),
        "items_count": len(items),
        "items": items,
        "model": model,
    }, indent=2), encoding="utf-8")
    print(f"\n  Batch state saved → {batch_log.name}")
    print(f"  Check status: python vault_logger.py --batch-status {batch_id}")

    # Poll for results
    routing_results = poll_batch(client, batch_id)

    # Map back to original items
    item_map = {f"item_{i}": items[i] for i in range(len(items))}

    # Process each result with specialists (sequential to avoid vault write conflicts)
    all_outputs = []
    for custom_id, routing in routing_results:
        info = item_map.get(custom_id, "")
        if not info:
            continue

        print(f"\n[ITEM {custom_id}] {info[:80]}...")
        print(f"  Branches: {routing['branches']}")

        outputs = {}
        for branch in routing["branches"]:
            print(f"\n  [{branch.upper()} AGENT]")
            try:
                agent = get_agent(branch, VAULT_ROOT)
                written = agent.process(client, info, routing, model, dry_run)
                outputs[branch] = written or "no write"
            except Exception as e:
                print(f"    ERROR: {e}")
                outputs[branch] = f"ERROR: {e}"

        all_outputs.append({"id": custom_id, "info": info, "routing": routing, "outputs": outputs})

    # Final log
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_log = LOG_DIR / f"batch_results_{ts}.json"
    final_log.write_text(json.dumps(all_outputs, indent=2), encoding="utf-8")
    print(f"\n[BATCH DONE] Results → {final_log.name}")


def check_batch_status(client: anthropic.Anthropic, batch_id: str) -> None:
    """Print current status of a submitted batch."""
    batch = client.messages.batches.retrieve(batch_id)
    counts = batch.request_counts
    print(f"\nBatch ID : {batch_id}")
    print(f"Status   : {batch.processing_status}")
    print(f"Processing : {counts.processing}")
    print(f"Succeeded  : {counts.succeeded}")
    print(f"Errored    : {counts.errored}")
    if batch.processing_status == "ended":
        print("\nBatch complete — re-run with --batch-status to collect results,")
        print("or re-run original --batch command to process results.")


# ── Session logger ────────────────────────────────────────────────────────────

def log_session(info: str, result: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"session_{ts}.json"
    log_file.write_text(json.dumps({
        "timestamp": ts,
        "input": info,
        **result,
    }, indent=2, default=str), encoding="utf-8")
    return log_file


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Vault Logger — route incoming info to the correct vault branch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("info", nargs="*", help="Information to route (or use --file / pipe)")
    p.add_argument("--file", "-f", metavar="FILE", help="Read input from a text file")
    p.add_argument("--batch", metavar="FILE",
                   help="Batch mode: process all items in FILE (separated by ---). Uses Batch API.")
    p.add_argument("--batch-status", metavar="BATCH_ID",
                   help="Check status of a submitted batch job")
    p.add_argument("--opus", action="store_true",
                   help=f"Use {OPUS_MODEL} for agents (higher quality, higher cost)")
    p.add_argument("--model", "-m", default=DEFAULT_MODEL,
                   help=f"Agent model override (default: {DEFAULT_MODEL})")
    p.add_argument("--branch", "-b", metavar="BRANCH",
                   help="Force a specific branch (skip router)")
    p.add_argument("--dry-run", "-n", action="store_true",
                   help="Show routing and analysis without writing to vault")
    p.add_argument("--list-branches", action="store_true",
                   help="List available vault branches and exit")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    # Quick info commands
    if args.list_branches:
        from agents.specialists import list_branches
        print("Available vault branches:")
        for b in list_branches():
            print(f"  {b}")
        return

    model = OPUS_MODEL if args.opus else args.model

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"  VAULT LOGGER  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Router : {ROUTER_MODEL}")
    print(f"  Agents : {model}")
    if args.dry_run:
        print(f"  MODE   : DRY RUN (no vault writes)")
    print(f"{'='*60}")

    # ── Batch status check ────────────────────────────────────────────────────
    if args.batch_status:
        check_batch_status(client, args.batch_status)
        return

    # ── Batch processing ──────────────────────────────────────────────────────
    if args.batch:
        process_batch(client, args.batch, model, args.dry_run)
        return

    # ── Single item ───────────────────────────────────────────────────────────
    info = get_single_input(args)

    print(f"\nINPUT: {info[:120]}{'...' if len(info) > 120 else ''}\n")

    result = process_single(
        client=client,
        info=info,
        model=model,
        dry_run=args.dry_run,
        force_branch=args.branch,
    )

    # Log session
    if not args.dry_run:
        log_file = log_session(info, result)
        print(f"\n[LOG] {log_file.name}")

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
