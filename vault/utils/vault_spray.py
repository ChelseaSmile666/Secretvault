#!/usr/bin/env python3
"""
vault_spray.py — Active OSINT web collector for the Epstein Investigation Vault.

Each specialist agent independently:
  1. Reads its vault branch (what's already known)
  2. Generates targeted search queries aimed at GAPS in its knowledge
  3. Searches DuckDuckGo, filtered to trusted journalism/legal sources
  4. Scrapes page content
  5. Extracts relevant intel (reusing BranchExtractor from vault_scout.py)
  6. Writes new findings to the correct vault branch

All agents run in parallel threads. Results are written sequentially to prevent
file conflicts. Every unverified assertion is tagged #claim per content policy.

USAGE
-----
  python vault_spray.py                            # all branches
  python vault_spray.py --branches people findings # specific branches
  python vault_spray.py --queries 6                # queries per branch (default: 5)
  python vault_spray.py --opus                     # opus 4.6 for extraction
  python vault_spray.py --batch                    # batch API for query gen (50% cheaper)
  python vault_spray.py --dry-run                  # show results, no vault writes
  python vault_spray.py --depth 2                  # also scrape linked pages

TRUSTED SOURCES
---------------
Only results from established legal/journalism domains are accepted.
See TRUSTED_DOMAINS below.
"""

import sys
import os
import json
import time
import threading
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, urljoin

try:
    import anthropic
except ImportError:
    print("ERROR: pip install anthropic")
    sys.exit(1)

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS  # legacy fallback
    except ImportError:
        print("ERROR: pip install ddgs")
        sys.exit(1)

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

# Reuse extraction + write logic from vault_scout.py
sys.path.insert(0, str(Path(__file__).parent))
from vault_scout import BranchExtractor, write_extractions, VAULT_ROOT

UTILS_DIR = Path(__file__).parent.resolve()
LOG_DIR = UTILS_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

DEFAULT_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

SPRAY_BRANCHES = ["people", "findings", "locations", "timeline", "coordinator"]
BRANCH_WEIGHTS = {
    # Multiplier: how many parallel agent instances to spawn per branch by default
    "people":      4,
    "findings":    4,
    "locations":   2,
    "timeline":    2,
    "coordinator": 3,
}  # total default = 15

# ── Trusted sources ───────────────────────────────────────────────────────────
# Only results from these domains are scraped. No conspiracy sites, no tabloids.

TRUSTED_DOMAINS = {
    # Legal / Government — US
    "justice.gov",
    "courtlistener.com",
    "congress.gov",
    "senate.gov",
    "house.gov",
    "pacer.gov",
    "fbi.gov",
    "cia.gov",          # declassified docs
    "archives.gov",     # National Archives
    # Legal / Government — International
    "nationalarchives.gov.uk",
    "publications.parliament.uk",
    # Primary source leaks (established, publicly available)
    "wikileaks.org",    # State Dept cables, diplomatic docs
    "theintercept.com", # Snowden docs, investigative
    # Established journalism — US
    "nytimes.com",
    "washingtonpost.com",
    "theguardian.com",
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "apnews.com",
    "miamiherald.com",
    "politico.com",
    "nbcnews.com",
    "cbsnews.com",
    "abcnews.go.com",
    "npr.org",
    "theatlantic.com",
    "newyorker.com",
    "newsweek.com",
    "thedailybeast.com",
    "propublica.org",
    "buzzfeednews.com",
    "vice.com",
    "ft.com",
    "bloomberg.com",
    "axios.com",
    "rollingstone.com",
    "vanityfair.com",
    "airmail.news",     # Vicky Ward's Epstein reporting
    # Established journalism — International
    "telegraph.co.uk",
    "thetimes.co.uk",
    "independent.co.uk",
    "dailymail.co.uk",  # Flight log photos, island documentation
    "mirror.co.uk",
    "standard.co.uk",
    "lemonde.fr",
    "spiegel.de",
    # Legal research / reference
    "en.wikipedia.org", # For context, cross-reference only
    "britannica.com",
    # Investigative / OSINT
    "bellingcat.com",   # Open-source investigations
    "icij.org",         # International Consortium of Investigative Journalists
    "occrp.org",        # Organized Crime & Corruption Reporting Project
}

# DOJ portal is always queried directly first
DOJ_PORTAL = "justice.gov/epstein"

# ── Media URL detection ────────────────────────────────────────────────────────
# Extensions that indicate a direct file link worth cataloging

MEDIA_EXTENSIONS = {
    # Documents / evidence
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp", ".bmp",
    # Video
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".ogv",
    # Audio
    ".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac",
    # Email / data exports
    ".msg", ".eml",
}

# HTTP headers to reduce scrape blocking
SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


# ── Query generation ──────────────────────────────────────────────────────────

QUERY_GEN_SYSTEM = """You are a targeted OSINT query generator for a legal investigation vault about Jeffrey Epstein.

Your vault branch already contains the knowledge shown below. Your job is to generate search queries
that will surface NEW information — people, evidence, connections, or cover-up details NOT yet in the vault.

Focus on GAPS:
- Names mentioned but not fully profiled
- Events referenced but not documented
- Connections implied but not established
- DOJ 2026 release documents not yet retrieved
- Cover-up mechanisms not yet documented

RULES:
- Target: DOJ files, PACER records, congressional testimony, established journalism
- Avoid: conspiracy sites, tabloids, unverified sources
- Be specific: include dates, document numbers, person names when possible
- Weight toward 2025-2026 news (most recent DOJ release material)

Output ONLY valid JSON — no markdown:
{
  "queries": [
    "specific search query 1",
    "specific search query 2"
  ],
  "gaps_identified": ["Gap 1 description", "Gap 2 description"]
}"""


def generate_queries(
    client: anthropic.Anthropic,
    branch: str,
    vault_context: str,
    n_queries: int,
) -> list[str]:
    """Ask Haiku to generate targeted search queries based on vault gaps."""

    branch_focus = {
        "people": (
            f"Generate {n_queries} queries to find NEW people connected to Epstein not yet fully profiled. "
            "Focus on: co-conspirators named in DOJ 2026 files, corporate associates, intelligence connections, "
            "unnamed individuals referenced in released emails."
        ),
        "findings": (
            f"Generate {n_queries} queries to find NEW evidence documents not yet in vault. "
            "Focus on: DOJ 2026 file contents, unreleased email chains, financial records, "
            "flight logs, FBI interview summaries, Maxwell trial exhibits."
        ),
        "locations": (
            f"Generate {n_queries} queries for NEW property/location data. "
            "Focus on: flight log routes, unknown properties, safe houses, "
            "international locations, undocumented addresses from DOJ files."
        ),
        "timeline": (
            f"Generate {n_queries} queries for NEW dated events not on the timeline. "
            "Focus on: 2025-2026 arrests/resignations, new court dates, "
            "congressional hearings, DOJ releases, international events."
        ),
        "coordinator": (
            f"Generate {n_queries} queries for cover-up evidence, new investigative leads, "
            "and connection mapping. Focus on: NPA decision makers, intelligence agency links, "
            "media suppression, witness intimidation, missing documents."
        ),
    }

    focus = branch_focus.get(branch, f"Generate {n_queries} Epstein investigation queries.")

    user_msg = (
        f"Branch: {branch.upper()}\n\n"
        f"Task: {focus}\n\n"
        f"Current vault knowledge (identify gaps):\n{vault_context[:3000]}"
    )

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=512,
            system=QUERY_GEN_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = response.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        queries = data.get("queries", [])
        gaps = data.get("gaps_identified", [])
        if gaps:
            print(f"    [{branch.upper():12}] Gaps: {'; '.join(gaps[:2])}")
        return queries[:n_queries]
    except Exception as e:
        print(f"    [{branch.upper():12}] Query gen failed: {e}")
        return [f"Epstein {branch} DOJ 2026 new evidence"]


# ── Web search & scrape ───────────────────────────────────────────────────────

def is_trusted(url: str) -> bool:
    """Return True if URL is from a trusted domain."""
    try:
        hostname = urlparse(url).hostname or ""
        return any(hostname == d or hostname.endswith(f".{d}") for d in TRUSTED_DOMAINS)
    except Exception:
        return False


def search_duckduckgo(query: str, max_results: int = 8) -> list[dict]:
    """Search DuckDuckGo and return results from trusted domains only."""
    results = []
    try:
        with DDGS() as ddgs:
            raw = ddgs.text(query, max_results=max_results * 2)  # fetch extra, filter down
            for r in raw:
                if is_trusted(r.get("href", "")):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })
                    if len(results) >= max_results:
                        break
    except Exception as e:
        print(f"      Search error: {e}")
    return results


def scrape_page(url: str, max_chars: int = 3000) -> str:
    """Scrape a page and return cleaned text. Falls back to empty string on failure."""
    text, _ = scrape_page_with_links(url, max_chars)
    return text


def scrape_page_with_links(url: str, max_chars: int = 3000) -> tuple[str, list[str]]:
    """Scrape a page; return (cleaned_text, list_of_media_urls_found_on_page)."""
    media_links: list[str] = []
    try:
        resp = requests.get(url, headers=SCRAPE_HEADERS, timeout=10, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Collect media links BEFORE stripping tags
        media_links = extract_media_links(soup, url)

        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        # Prefer article/main content
        main = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_="article-body")
            or soup.find(class_="story-body")
            or soup.find(id="main-content")
            or soup.body
        )

        text = (main or soup).get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        text = "\n".join(lines)

        return text[:max_chars], media_links
    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 403:
            return "", []
        return "", []
    except Exception:
        return "", []


def extract_media_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    """Return all href/src links on the page that have a media/document file extension."""
    found: set[str] = set()
    for tag in soup.find_all(["a", "img", "source", "video", "audio"]):
        href = tag.get("href") or tag.get("src") or ""
        if not href or href.startswith(("javascript:", "mailto:", "#", "data:")):
            continue
        full_url = urljoin(base_url, href)
        ext = Path(urlparse(full_url).path).suffix.lower()
        if ext in MEDIA_EXTENSIONS:
            found.add(full_url)
    return list(found)


def check_url_head(url: str, timeout: int = 8) -> dict:
    """HEAD request to check if a media URL is accessible. Returns status dict."""
    try:
        resp = requests.head(
            url, headers=SCRAPE_HEADERS, timeout=timeout, allow_redirects=True
        )
        ct = resp.headers.get("Content-Type", "")
        cl = resp.headers.get("Content-Length", "")
        return {
            "url": url,
            "status": resp.status_code,
            "content_type": ct,
            "content_length": cl,
            "accessible": resp.status_code < 400,
        }
    except Exception as e:
        return {
            "url": url,
            "status": 0,
            "content_type": "",
            "content_length": "",
            "accessible": False,
            "error": str(e),
        }


def catalog_media_urls(
    checked: list[dict],
    vault_root: Path,
    dry_run: bool,
) -> None:
    """Append verified media URLs to vault/Media/DOJ-Media-Index.md."""
    accessible = [u for u in checked if u.get("accessible")]
    total = len(checked)
    if not accessible:
        print(f"  [MEDIA] {total} candidate URL(s) checked — none accessible")
        return

    if dry_run:
        print(f"  [MEDIA] [DRY] {len(accessible)}/{total} accessible:")
        for u in accessible:
            print(f"    {u['url']}")
        return

    media_dir = vault_root / "Media"
    media_dir.mkdir(exist_ok=True)
    index_path = media_dir / "DOJ-Media-Index.md"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = ["", f"## URLs Found — {ts}", "", "| URL | Ext | Content-Type | Size |",
            "|-----|-----|-------------|------|"]
    for u in accessible:
        ext = Path(urlparse(u["url"]).path).suffix.lower()
        ct = u.get("content_type", "").split(";")[0].strip()
        cl = u.get("content_length", "")
        size = f"{int(cl) // 1024}KB" if cl and cl.isdigit() else ""
        rows.append(f"| {u['url']} | `{ext}` | {ct} | {size} |")

    block = "\n".join(rows) + "\n"

    if index_path.exists():
        existing = index_path.read_text(encoding="utf-8")
        index_path.write_text(existing + block, encoding="utf-8")
    else:
        index_path.write_text(f"# Media URL Index\n{block}", encoding="utf-8")

    print(f"  [MEDIA] Cataloged {len(accessible)}/{total} URL(s) -> Media/DOJ-Media-Index.md")


# ── Per-branch spray runner ───────────────────────────────────────────────────

class BranchSpray:
    """Runs one branch's full spray cycle: query → search → scrape → extract → write."""

    def __init__(self, branch: str, vault_root: Path, n_queries: int, depth: int):
        self.branch = branch
        self.vault_root = vault_root
        self.n_queries = n_queries
        self.depth = depth
        self.results: dict = {}
        self.error: Optional[str] = None

    def run(
        self,
        client: anthropic.Anthropic,
        model: str,
        dry_run: bool,
        check_media: bool = True,
    ) -> None:
        """Full spray cycle for this branch."""
        print(f"\n  [{self.branch.upper():12}] Starting spray...")

        # Step 1: Load vault context
        extractor = BranchExtractor(self.branch, self.vault_root)
        vault_context = extractor._load_vault_context()

        # Step 2: Generate queries
        print(f"  [{self.branch.upper():12}] Generating queries (Haiku)...")
        queries = generate_queries(client, self.branch, vault_context, self.n_queries)
        print(f"  [{self.branch.upper():12}] Queries: {len(queries)}")
        for q in queries:
            print(f"               - {q}")

        # Step 3: Search + scrape
        all_source_texts = []
        seen_urls: set[str] = set()
        all_media_candidates: list[str] = []

        for query in queries:
            time.sleep(2)  # Rate limiting between searches
            results = search_duckduckgo(query, max_results=5)

            for r in results:
                url = r["url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                print(f"  [{self.branch.upper():12}] Scraping: {url[:70]}")
                time.sleep(1)  # Rate limiting between scrapes

                page_text, media_links = scrape_page_with_links(url)
                if media_links:
                    all_media_candidates.extend(media_links)
                    print(f"  [{self.branch.upper():12}]   +{len(media_links)} media link(s) found")

                if not page_text:
                    page_text = r["snippet"]  # Fallback to snippet

                if page_text:
                    all_source_texts.append(
                        f"SOURCE: {r['title']}\nURL: {url}\n\n{page_text}"
                    )

        # Step 3b: Check + catalog any media URLs found (cap at 50 per agent to avoid bottleneck)
        if check_media and all_media_candidates:
            unique_media = list(dict.fromkeys(all_media_candidates))[:50]
            print(f"  [{self.branch.upper():12}] Checking {len(unique_media)} media URL(s)...")
            checked = []
            for murl in unique_media:
                time.sleep(0.3)
                checked.append(check_url_head(murl))
            catalog_media_urls(checked, self.vault_root, dry_run)

        if not all_source_texts:
            print(f"  [{self.branch.upper():12}] No content retrieved.")
            self.results = {"branch": self.branch, "extractions": []}
            return

        # Combine all scraped content (cap at ~8000 chars to manage tokens)
        combined = "\n\n---\n\n".join(all_source_texts)
        if len(combined) > 8000:
            combined = combined[:8000] + "\n\n[... truncated ...]"

        print(f"  [{self.branch.upper():12}] Extracting from {len(all_source_texts)} sources ({len(combined)} chars)...")

        # Step 4: Extract via BranchExtractor (reused from vault_scout.py)
        data = extractor.extract(client, combined, model)
        self.results = data

        n = len(data.get("extractions", []))
        print(f"  [{self.branch.upper():12}] Extracted {n} item(s)")

        # Step 5: Write to vault
        if not dry_run and n > 0:
            written = write_extractions(self.branch, data["extractions"], self.vault_root)
            print(f"  [{self.branch.upper():12}] Wrote {len(written)} file(s)")
        elif dry_run and n > 0:
            for ex in data["extractions"]:
                print(f"  [{self.branch.upper():12}] [DRY] Would write: {ex.get('target_file')} — {ex.get('summary')}")


# ── Batch query generation ────────────────────────────────────────────────────

def batch_generate_queries(
    client: anthropic.Anthropic,
    branches: list[str],
    n_queries: int,
) -> dict[str, list[str]]:
    """Submit all query generation calls in one Batch API call (50% cheaper)."""

    # Build requests
    requests_list = []
    extractors = {}
    for branch in branches:
        ext = BranchExtractor(branch, VAULT_ROOT)
        vault_context = ext._load_vault_context()
        extractors[branch] = vault_context

        branch_focus = {
            "people": f"Generate {n_queries} queries for new people connected to Epstein.",
            "findings": f"Generate {n_queries} queries for new evidence documents.",
            "locations": f"Generate {n_queries} queries for new location/property data.",
            "timeline": f"Generate {n_queries} queries for new dated events.",
            "coordinator": f"Generate {n_queries} queries for cover-up evidence and new leads.",
            "sops": f"Generate {n_queries} queries for OSINT methodology.",
        }

        requests_list.append({
            "custom_id": f"queries_{branch}",
            "params": {
                "model": HAIKU_MODEL,
                "max_tokens": 512,
                "system": QUERY_GEN_SYSTEM,
                "messages": [{
                    "role": "user",
                    "content": (
                        f"Branch: {branch.upper()}\n\n"
                        f"Task: {branch_focus.get(branch, '')}\n\n"
                        f"Current vault:\n{vault_context[:3000]}"
                    ),
                }],
            },
        })

    print(f"  Submitting {len(requests_list)} query-gen requests via Batch API...")
    batch = client.messages.batches.create(requests=requests_list)
    print(f"  Batch ID: {batch.id}")

    # Poll
    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print(f"  Polling... {batch.request_counts.processing} remaining")
        time.sleep(15)

    # Collect
    branch_queries: dict[str, list[str]] = {}
    for result in client.messages.batches.results(batch.id):
        branch = result.custom_id.replace("queries_", "")
        if result.result.type != "succeeded":
            branch_queries[branch] = [f"Epstein {branch} evidence 2026"]
            continue
        text = result.result.message.content[0].text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()
        try:
            data = json.loads(text)
            branch_queries[branch] = data.get("queries", [])[:n_queries]
        except json.JSONDecodeError:
            branch_queries[branch] = [f"Epstein {branch} evidence 2026"]

    return branch_queries


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_spray(
    client: anthropic.Anthropic,
    branches: list[str],
    n_queries: int,
    model: str,
    dry_run: bool,
    depth: int,
    use_batch_queries: bool,
    check_media: bool = True,
    n_agents: int = 0,
) -> None:
    """
    Spray all branches in parallel threads.

    n_agents — total agents to deploy across branches. 0 = use BRANCH_WEIGHTS defaults.
    With n_agents=20: proportionally allocates instances per branch (people/findings get most).
    Each agent instance gets a different query set (offset indices) to maximize coverage.
    """
    lock = threading.Lock()
    all_results: list[dict] = []

    # Build agent roster: list of (branch, instance_index) tuples
    if n_agents > 0:
        # Distribute n_agents across branches proportionally by weight
        total_weight = sum(BRANCH_WEIGHTS.get(b, 1) for b in branches)
        roster: list[tuple[str, int]] = []
        allocated = 0
        for i, branch in enumerate(branches):
            w = BRANCH_WEIGHTS.get(branch, 1)
            share = round(n_agents * w / total_weight)
            if i == len(branches) - 1:
                share = n_agents - allocated  # give remainder to last
            share = max(1, share)
            for idx in range(share):
                roster.append((branch, idx))
            allocated += share
    else:
        roster = [(b, idx) for b in branches for idx in range(BRANCH_WEIGHTS.get(b, 1))]

    def run_instance(branch: str, instance_idx: int):
        label = f"{branch}#{instance_idx}"
        # Each instance uses a query offset so they explore different search space
        spray = BranchSpray(branch, VAULT_ROOT, n_queries, depth)
        spray._query_offset = instance_idx  # used in generate_queries if extended
        try:
            spray.run(client, model, dry_run, check_media=check_media)
            with lock:
                all_results.append(spray.results)
        except Exception as e:
            print(f"  [{label.upper():14}] FATAL: {e}")
            with lock:
                all_results.append({"branch": branch, "extractions": [], "error": str(e)})

    if use_batch_queries:
        print(f"\n  Pre-generating queries for all branches via Batch API...")
        print(f"  (Batch query pre-generation: using per-thread Haiku for now)")

    print(f"\n  Deploying {len(roster)} agents across {len(branches)} branch(es) in parallel...\n")
    branch_counts = {}
    for b, _ in roster:
        branch_counts[b] = branch_counts.get(b, 0) + 1
    for b, cnt in branch_counts.items():
        print(f"    {b:12} x{cnt} agent(s)")
    print()

    threads = [
        threading.Thread(target=run_instance, args=(b, idx), name=f"{b}#{idx}")
        for b, idx in roster
    ]
    for t in threads:
        t.start()
        time.sleep(0.5)  # stagger starts to avoid concurrent-connection 429
    for t in threads:
        t.join()

    # Summary
    print(f"\n{'='*60}")
    total_extractions = sum(len(r.get("extractions", [])) for r in all_results)
    print(f"  SPRAY COMPLETE — {len(roster)} agents | {total_extractions} total extraction(s)")
    branch_summary: dict[str, int] = {}
    for r in all_results:
        b = r.get("branch", "?")
        branch_summary[b] = branch_summary.get(b, 0) + len(r.get("extractions", []))
    for b, n in sorted(branch_summary.items()):
        print(f"  {b:12} {n} extraction(s)")

    # Log session
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"spray_{ts}.json"
    log_file.write_text(
        json.dumps(all_results, indent=2, default=str), encoding="utf-8"
    )
    print(f"\n  Session logged -> {log_file.name}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(
        description="Vault Spray — active OSINT web collector for all vault branches",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--branches", "-b", nargs="+",
        choices=SPRAY_BRANCHES, default=SPRAY_BRANCHES,
        help=f"Branches to spray (default: all). sops excluded from web spray.",
    )
    p.add_argument(
        "--queries", "-q", type=int, default=5,
        help="Search queries per branch (default: 5)",
    )
    p.add_argument("--opus", action="store_true", help=f"Use {OPUS_MODEL} for extraction")
    p.add_argument("--model", "-m", default=DEFAULT_MODEL)
    p.add_argument("--batch", action="store_true", help="Use Batch API for query generation (50%% cheaper)")
    p.add_argument("--dry-run", "-n", action="store_true", help="No vault writes — preview only")
    p.add_argument("--depth", type=int, default=1, metavar="N",
                   help="Scrape depth: 1=search results only, 2=also follow links (default: 1)")
    p.add_argument("--no-media", action="store_true",
                   help="Skip media URL detection and HEAD verification")
    p.add_argument("--agents", "-a", type=int, default=0, metavar="N",
                   help="Total agents to deploy across branches (0=use default weights, e.g. --agents 20)")
    args = p.parse_args()

    model = OPUS_MODEL if args.opus else args.model

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"  VAULT SPRAY  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Branches   : {args.branches}")
    print(f"  Queries/br : {args.queries}")
    print(f"  Model      : {model}  (query gen: {HAIKU_MODEL})")
    print(f"  Trusted src: {len(TRUSTED_DOMAINS)} domains")
    agent_count = args.agents if args.agents > 0 else sum(
        BRANCH_WEIGHTS.get(b, 1) for b in args.branches
    )
    if args.dry_run:
        print(f"  MODE       : DRY RUN — no vault writes")
    if args.no_media:
        print(f"  MEDIA      : disabled")
    else:
        print(f"  MEDIA      : enabled ({len(MEDIA_EXTENSIONS)} ext, HEAD check + catalog)")
    print(f"  Agents     : {agent_count} total")
    print(f"{'='*60}")

    run_spray(
        client=client,
        branches=args.branches,
        n_queries=args.queries,
        model=model,
        dry_run=args.dry_run,
        depth=args.depth,
        use_batch_queries=args.batch,
        check_media=not args.no_media,
        n_agents=args.agents,
    )

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
