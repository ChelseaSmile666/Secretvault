"""
Specialist agents — one per vault branch.

Each agent loads ONLY its own vault directory as context (small, focused window).
This keeps each specialist lean and prevents context bleed between domains.

Agents:
  PeopleAgent       → vault/People/
  FindingsAgent     → vault/Findings/
  LocationsAgent    → vault/Locations/
  TimelineAgent     → vault/Timeline.md
  SopsAgent         → vault/SOPs/
  CoordinatorAgent  → vault/Investigations/Epstein/
"""

from pathlib import Path
from typing import Optional
from datetime import datetime

from .base_agent import BaseVaultAgent


# ── People ────────────────────────────────────────────────────────────────────

class PeopleAgent(BaseVaultAgent):
    """Specialist for vault/People/ — individual profiles."""

    def __init__(self, vault_root: Path):
        super().__init__("People Network", vault_root)

    def _load_vault_context(self) -> str:
        people_dir = self.vault_root / "People"
        parts = ["## PEOPLE BRANCH — EXISTING PROFILES\n"]

        readme = people_dir / "README.md"
        if readme.exists():
            parts.append(f"### INDEX\n{self._read_file(readme, 800)}\n")

        parts.append("### PROFILE SUMMARIES (frontmatter + opening block)\n")
        for md_file in sorted(people_dir.glob("*.md")):
            if md_file.name == "README.md":
                continue
            # Load just enough to identify status, charges, relationships
            parts.append(f"\n#### {md_file.stem}\n{self._read_file(md_file, 700)}\n---")

        return "\n".join(parts)

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        people_dir = self.vault_root / "People"
        target = result.get("target_file")

        if not target:
            entities = routing.get("entities", [])
            name = entities[0] if entities else f"Unknown-{datetime.now().strftime('%Y%m%d')}"
            target = f"{name.replace(' ', '-')}.md"

        target_path = people_dir / target
        entry = result["vault_entry"]

        if target_path.exists():
            existing = target_path.read_text(encoding="utf-8")
            update = f"\n\n---\n\n## Update — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}"
            target_path.write_text(existing + update, encoding="utf-8")
            print(f"    Appended update → People/{target}")
        else:
            target_path.write_text(entry, encoding="utf-8")
            print(f"    Created profile → People/{target}")

        return str(target_path)


# ── Findings ──────────────────────────────────────────────────────────────────

class FindingsAgent(BaseVaultAgent):
    """Specialist for vault/Findings/ — evidence, documents, court records."""

    def __init__(self, vault_root: Path):
        super().__init__("Evidence & Findings", vault_root)

    def _load_vault_context(self) -> str:
        findings_dir = self.vault_root / "Findings"
        parts = ["## FINDINGS BRANCH — EVIDENCE INDEX\n"]

        readme = findings_dir / "README.md"
        if readme.exists():
            parts.append(f"### INDEX\n{self._read_file(readme, 1200)}\n")

        # Load key reference documents in full
        key_files = [
            "2026-DOJ-Epstein-Files-Release.md",
            "Intelligence-Connections.md",
            "Scopolamine-Drugging-Evidence.md",
            "Epstein-Financial-Network.md",
        ]
        parts.append("### KEY DOCUMENTS (excerpts for fact-checking)\n")
        for fname in key_files:
            fpath = findings_dir / fname
            if fpath.exists():
                parts.append(f"\n#### {fname}\n{self._read_file(fpath, 900)}\n---")

        # List remaining files so agent knows what exists
        parts.append("\n### ALL FINDINGS FILES\n")
        for md_file in sorted(findings_dir.glob("*.md")):
            if md_file.name not in (["README.md"] + key_files):
                parts.append(f"- {md_file.stem}")

        return "\n".join(parts)

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        findings_dir = self.vault_root / "Findings"
        target = result.get("target_file")

        if not target:
            date_str = routing.get("date") or datetime.now().strftime("%Y-%m-%d")
            entities = routing.get("entities", [])
            slug = entities[0].replace(" ", "-")[:30] if entities else "New-Finding"
            target = f"{date_str}-{slug}.md"

        target_path = findings_dir / target
        entry = result["vault_entry"]

        if target_path.exists():
            existing = target_path.read_text(encoding="utf-8")
            update = f"\n\n---\n\n## Update — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}"
            target_path.write_text(existing + update, encoding="utf-8")
            print(f"    Appended update → Findings/{target}")
        else:
            target_path.write_text(entry, encoding="utf-8")
            print(f"    Created finding → Findings/{target}")

        return str(target_path)


# ── Locations ─────────────────────────────────────────────────────────────────

class LocationsAgent(BaseVaultAgent):
    """Specialist for vault/Locations/ — properties, addresses, flight routes."""

    def __init__(self, vault_root: Path):
        super().__init__("Locations & Properties", vault_root)

    def _load_vault_context(self) -> str:
        locations_dir = self.vault_root / "Locations"
        parts = ["## LOCATIONS BRANCH — ALL PROPERTIES\n"]

        for md_file in sorted(locations_dir.glob("*.md")):
            if md_file.name == "README.md":
                continue
            # Location files are small — load fully
            parts.append(f"\n### {md_file.stem}\n{self._read_file(md_file, 2000)}\n---")

        return "\n".join(parts)

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        locations_dir = self.vault_root / "Locations"
        target = result.get("target_file")

        if not target:
            entities = routing.get("entities", [])
            slug = entities[0].replace(" ", "-")[:40] if entities else "New-Location"
            target = f"{slug}.md"

        target_path = locations_dir / target
        entry = result["vault_entry"]

        if target_path.exists():
            existing = target_path.read_text(encoding="utf-8")
            update = f"\n\n---\n\n## Update — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}"
            target_path.write_text(existing + update, encoding="utf-8")
            print(f"    Appended update → Locations/{target}")
        else:
            target_path.write_text(entry, encoding="utf-8")
            print(f"    Created location → Locations/{target}")

        return str(target_path)


# ── Timeline ──────────────────────────────────────────────────────────────────

class TimelineAgent(BaseVaultAgent):
    """Specialist for vault/Timeline.md — chronological event record."""

    def __init__(self, vault_root: Path):
        super().__init__("Timeline & Chronology", vault_root)

    def _load_vault_context(self) -> str:
        timeline_path = self.vault_root / "Timeline.md"
        # Timeline is the primary source — load generously
        return f"## CURRENT TIMELINE\n\n{self._read_file(timeline_path, 6000)}"

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        timeline_path = self.vault_root / "Timeline.md"
        entry = result.get("vault_entry")
        if not entry:
            return None

        existing = timeline_path.read_text(encoding="utf-8")
        date = routing.get("date")

        if date:
            # Find an existing section for this date or insert chronologically
            idx = existing.find(f"| {date}")
            if idx > -1:
                # Append after the existing row for this date
                end = existing.find("\n", idx) + 1
                new_content = existing[:end] + entry + "\n" + existing[end:]
                timeline_path.write_text(new_content, encoding="utf-8")
                print(f"    Inserted at {date} → Timeline.md")
                return str(timeline_path)

        # Prepend after the first table header row
        lines = existing.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("|---") or line.startswith("| ---"):
                insert_at = i + 1
                break

        lines.insert(insert_at, entry)
        timeline_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"    Prepended → Timeline.md")
        return str(timeline_path)


# ── SOPs ──────────────────────────────────────────────────────────────────────

class SopsAgent(BaseVaultAgent):
    """Specialist for vault/SOPs/ — OSINT research methodology."""

    def __init__(self, vault_root: Path):
        super().__init__("OSINT Methods & SOPs", vault_root)

    def _load_vault_context(self) -> str:
        sops_dir = self.vault_root / "SOPs"
        parts = ["## SOPs BRANCH — RESEARCH PROCEDURES\n"]

        readme = sops_dir / "README.md"
        if readme.exists():
            parts.append(f"### INDEX\n{self._read_file(readme, 2000)}\n")

        parts.append("### AVAILABLE SOP FILES\n")
        for md_file in sorted(sops_dir.glob("*.md")):
            if md_file.name != "README.md":
                parts.append(f"- {md_file.stem}")

        return "\n".join(parts)

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        sops_dir = self.vault_root / "SOPs"
        target = result.get("target_file")

        if not target:
            entities = routing.get("entities", [])
            slug = entities[0].replace(" ", "-")[:40] if entities else "New-SOP"
            target = f"{slug}.md"

        target_path = sops_dir / target
        entry = result["vault_entry"]

        if target_path.exists():
            existing = target_path.read_text(encoding="utf-8")
            update = f"\n\n---\n\n## Update — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}"
            target_path.write_text(existing + update, encoding="utf-8")
            print(f"    Appended update → SOPs/{target}")
        else:
            target_path.write_text(entry, encoding="utf-8")
            print(f"    Created SOP → SOPs/{target}")

        return str(target_path)


# ── Coordinator ───────────────────────────────────────────────────────────────

class CoordinatorAgent(BaseVaultAgent):
    """Specialist for vault/Investigations/Epstein/ — case management & open tasks."""

    def __init__(self, vault_root: Path):
        super().__init__("Investigation Coordinator", vault_root)

    def _load_vault_context(self) -> str:
        epstein_md = self.vault_root / "Investigations" / "Epstein" / "Epstein.md"
        return f"## MAIN INVESTIGATION INDEX\n\n{self._read_file(epstein_md, 5000)}"

    def _write_to_vault(self, result: dict, routing: dict) -> Optional[str]:
        epstein_md = self.vault_root / "Investigations" / "Epstein" / "Epstein.md"
        entry = result.get("vault_entry")
        if not entry:
            return None

        existing = epstein_md.read_text(encoding="utf-8")
        update = f"\n\n---\n\n## Coordinator Update — {datetime.now().strftime('%Y-%m-%d')}\n\n{entry}"
        epstein_md.write_text(existing + update, encoding="utf-8")
        print(f"    Appended → Investigations/Epstein/Epstein.md")
        return str(epstein_md)


# ── Factory ───────────────────────────────────────────────────────────────────

_REGISTRY: dict[str, type[BaseVaultAgent]] = {
    "people":      PeopleAgent,
    "findings":    FindingsAgent,
    "locations":   LocationsAgent,
    "timeline":    TimelineAgent,
    "sops":        SopsAgent,
    "coordinator": CoordinatorAgent,
}


def get_agent(branch: str, vault_root: Path) -> BaseVaultAgent:
    """Factory — return the correct specialist agent for a branch."""
    cls = _REGISTRY.get(branch)
    if not cls:
        raise ValueError(
            f"Unknown branch: '{branch}'. Valid branches: {sorted(_REGISTRY.keys())}"
        )
    return cls(vault_root)


def list_branches() -> list[str]:
    return sorted(_REGISTRY.keys())
