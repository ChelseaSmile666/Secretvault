"""
Base class for all vault specialist agents.

Each specialist:
- Loads only its own vault directory as context (small context window)
- Fact-checks incoming info against its knowledge base
- Generates properly formatted Obsidian vault entries
- Tags #claim on ALL unverified allegations
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

import anthropic


CONTENT_POLICY = """CONTENT POLICY — NON-NEGOTIABLE:
- Sources: DOJ files (justice.gov/epstein), PACER, congressional records, DOJ press releases, established major journalism only
- Tag #claim inline on ANY unverified allegation against a living non-convicted person
- DECLINE and return OFF_TOPIC for: Pizzagate (pizza/pasta references), celebrity deaths with no Epstein court connection, organ harvesting without documentation, unrelated historical events, speculative missing-children links
- NEVER fabricate document reference numbers (EFTA codes, PACER case numbers, etc.)
- When uncertain about a fact: tag #claim, lower confidence score"""

VAULT_FORMAT = """OBSIDIAN VAULT FORMAT:
- YAML frontmatter between --- delimiters (tags, status, date, source, verified, case-ref)
- WikiLinks: [[People/Name]] [[Locations/Place]] [[Findings/Document]]
- Tables: | Field | Value | format with header row and separator row
- #claim tag inline immediately after unverified assertions
- Source citations: (DOJ, PACER 19-CR-490, NYT 2019-07-08)
- Dates: ISO 8601 YYYY-MM-DD
- Status badges bold: **Status: Convicted** / **Status: Deceased** / **Status: Active**
- Section headers: ## for major sections, ### for subsections"""


class BaseVaultAgent:
    """
    Base specialist agent — trained with context from its vault branch.

    Subclasses define:
    - _load_vault_context(): loads branch-specific files
    - _write_to_vault(): handles writing to the correct location
    """

    def __init__(self, name: str, vault_root: Path):
        self.name = name
        self.vault_root = vault_root
        self.vault_context = self._load_vault_context()

    def _load_vault_context(self) -> str:
        """Override in subclasses to load branch-specific vault files."""
        return ""

    def _read_file(self, path: Path, max_chars: int = 3000) -> str:
        """Read a vault file with truncation for context efficiency."""
        try:
            content = path.read_text(encoding="utf-8")
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[... truncated at {max_chars} chars ...]"
            return content
        except FileNotFoundError:
            return f"[File not found: {path.name}]"
        except Exception as e:
            return f"[Error reading {path.name}: {e}]"

    def _build_system_prompt(self) -> str:
        return f"""You are the {self.name} specialist agent for the Epstein OSINT Investigation Vault.

{CONTENT_POLICY}

{VAULT_FORMAT}

YOUR VAULT KNOWLEDGE BASE (your memory — use this to fact-check):
{self.vault_context}

YOUR TASKS:
1. Fact-check the incoming information against your vault knowledge base
2. Classify it as one of:
   - CONFIRMED: Matches existing vault records
   - NEW: New credible information not yet in vault
   - CLAIM: Unverified allegation — must be tagged #claim throughout
   - CONTRADICTS: Conflicts with verified vault records (explain conflict)
   - OFF_TOPIC: Does not belong in your branch

3. If CONFIRMED or NEW: generate a properly formatted vault entry
4. If CLAIM: generate entry with #claim on every unverified assertion
5. If CONTRADICTS: explain the conflict, do not write conflicting data
6. If OFF_TOPIC: return null for vault_entry

OUTPUT — respond ONLY with valid JSON, no markdown fences:
{{
  "classification": "NEW|CONFIRMED|CLAIM|CONTRADICTS|OFF_TOPIC",
  "confidence": 0.0,
  "fact_check_notes": "Brief explanation of what was checked and how",
  "target_file": "Filename.md or null (null = don't write)",
  "vault_entry": "Complete formatted vault markdown or null",
  "warnings": ["Any content policy flags or concerns"]
}}"""

    def process(
        self,
        client: anthropic.Anthropic,
        info: str,
        routing: dict,
        model: str,
        dry_run: bool,
    ) -> Optional[str]:
        """
        Fact-check info and write to vault if warranted.
        Uses streaming to avoid session timeouts.
        Returns path of written file or None.
        """
        system = self._build_system_prompt()

        user_msg = (
            f"Process this incoming information for the {self.name} branch:\n\n"
            f"---\n{info}\n---\n\n"
            f"Routing metadata: {json.dumps(routing, indent=2)}\n"
            f"Current date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"Fact-check against your vault knowledge base and generate the appropriate entry."
        )

        print(f"    Streaming {model}...", end="", flush=True)
        full_response = ""

        try:
            with client.messages.stream(
                model=model,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            ) as stream:
                for text in stream.text_stream:
                    full_response += text
                    print(".", end="", flush=True)
        except anthropic.APITimeoutError:
            print("\n    TIMEOUT — try shorter input or --model sonnet")
            return None
        except anthropic.APIError as e:
            print(f"\n    API ERROR: {e}")
            return None

        print(" done")

        # Parse JSON response
        text = full_response.strip()
        if text.startswith("```"):
            # Strip code fences if model wrapped output anyway
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            print(f"    WARNING: Could not parse JSON. Raw response saved to log.")
            return None

        # Print summary
        print(f"    Classification : {result.get('classification')}")
        print(f"    Confidence     : {result.get('confidence')}")
        notes = result.get("fact_check_notes", "")
        if notes:
            print(f"    Notes          : {notes[:120]}")
        for warning in result.get("warnings", []):
            print(f"    WARNING        : {warning}")

        # Write to vault
        if (
            result.get("vault_entry")
            and result.get("target_file")
            and result.get("classification") in ("NEW", "CONFIRMED", "CLAIM")
            and not dry_run
        ):
            return self._write_to_vault(result, routing)

        if dry_run and result.get("vault_entry"):
            print(f"    [DRY RUN] Would write to: {result.get('target_file')}")

        return None

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        """Override in subclasses."""
        raise NotImplementedError
