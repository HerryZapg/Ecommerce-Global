#!/usr/bin/env python3
"""
Compare requirement-driven stack (docs/stack-requirements.json) vs discovered manifest stack.
Emits @GAP (yellow in wrappers), @REQ_OK, @WARN, @ERR, @INFO.
Exit: 0 ok, 1 required gaps, 2 missing requirements file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from stack_discover import discover_technologies, load_advisory_config, normalize_id


def emit(kind: str, message: str, tech_id: str = "", tech_name: str = "") -> None:
    if kind == "GAP":
        print(f"@GAP|{tech_id}|{tech_name}|{message}", flush=True)
    else:
        print(f"@{kind}|{message}", flush=True)


def parse_min_version(spec: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\.(\d+)", spec or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def version_gte(have: tuple[int, int], need: tuple[int, int]) -> bool:
    return have[0] > need[0] or (have[0] == need[0] and have[1] >= need[1])


def load_requirements(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_discovered_index(discovered: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for tech in discovered:
        tid = tech.get("id", "")
        if tid:
            index[tid] = tech
        pkg = tech.get("package")
        if pkg:
            index[pkg] = tech
            index[normalize_id(pkg)] = tech
    return index


def find_match(req: dict, index: dict[str, dict]) -> dict | None:
    rid = req.get("id", "")
    if rid in index:
        return index[rid]
    for alias in req.get("aliases") or []:
        if alias in index:
            return index[alias]
        nid = normalize_id(alias)
        if nid in index:
            return index[nid]
    pkg = req.get("package")
    if pkg and pkg in index:
        return index[pkg]
    nid = normalize_id(rid)
    if nid in index:
        return index[nid]
    return None


def compare_versions(req: dict, discovered: dict) -> str | None:
    """Return warning message if discovered spec seems below required advisory."""
    rec = req.get("recommended") or req.get("minimum") or ""
    need = parse_min_version(str(rec))
    if not need:
        return None
    installed = discovered.get("installed_spec") or ""
    have = parse_min_version(str(installed))
    if have and not version_gte(have, need):
        return (
            f"Manifest has {installed} but requirement asks {rec}. "
            f"Consider bumping pyproject.toml / package.json or install newer runtime."
        )
    return None


def compare_stacks(
    requirements: dict, discovered: list[dict]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (gaps, satisfied, optional_skipped)."""
    index = build_discovered_index(discovered)
    gaps: list[dict] = []
    satisfied: list[dict] = []
    skipped: list[dict] = []

    for req in requirements.get("required_technologies") or []:
        if not req.get("required", True):
            skipped.append(req)
            continue
        name = req.get("name") or req.get("id", "?")
        tid = req.get("id", "?")
        match = find_match(req, index)
        if not match:
            gaps.append(
                {
                    "id": tid,
                    "name": name,
                    "message": (
                        f"Required by spec but NOT in project manifests. "
                        f"Add dependency or document waiver. "
                        f"Rationale: {req.get('rationale', 'see requirement')}"
                    ),
                    "action": req.get("action", "add_to_manifest"),
                }
            )
            continue
        ver_warn = compare_versions(req, match)
        if ver_warn:
            gaps.append(
                {
                    "id": tid,
                    "name": name,
                    "message": ver_warn,
                    "action": "upgrade_version",
                }
            )
        else:
            satisfied.append(
                {
                    "id": tid,
                    "name": name,
                    "discovered_id": match.get("id"),
                    "source": match.get("source"),
                    "installed_spec": match.get("installed_spec"),
                }
            )

    return gaps, satisfied, skipped


def write_template(path: Path, summary: str = "") -> None:
    today = date.today().isoformat()
    template = {
        "schema_version": 1,
        "source": "Paste user story, PLAN.md section, or ticket URL",
        "requirement_summary": summary or "Describe the feature or change",
        "last_updated": today,
        "required_technologies": [
            {
                "id": "python",
                "name": "Python",
                "recommended": "3.12",
                "required": True,
                "rationale": "Example: backend runtime",
            }
        ],
    }
    path.write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare requirements vs discovered stack")
    parser.add_argument(
        "--requirements",
        "-r",
        default="docs/stack-requirements.json",
        help="Path to requirements JSON",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Write template docs/stack-requirements.json",
    )
    parser.add_argument(
        "--summary",
        default="",
        help="Summary text when using --init",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    req_path = root / args.requirements

    if args.init:
        if req_path.is_file():
            emit("WARN", f"{req_path.relative_to(root)} already exists; not overwriting")
            return 0
        write_template(req_path, args.summary)
        emit("OK", f"Created {req_path.relative_to(root)}")
        emit("INFO", "Edit required_technologies[], then run stack-requirements again")
        return 0

    if not req_path.is_file():
        emit("ERR", f"Missing {req_path.relative_to(root)}. Run with --init or use stack-from-requirements skill")
        return 2

    requirements = load_requirements(req_path)
    advisory = load_advisory_config(root)
    discovered = discover_technologies(root, advisory)

    emit("INFO", "=== Stack requirements vs discovered ===")
    emit("INFO", f"Requirement: {requirements.get('requirement_summary', '(no summary)')}")
    emit("INFO", f"Source: {requirements.get('source', 'n/a')}")
    emit("INFO", f"Discovered {len(discovered)} technologies in repo")

    gaps, satisfied, skipped = compare_stacks(requirements, discovered)

    for s in satisfied:
        emit(
            "REQ_OK",
            f"{s['name']}: covered by {s.get('discovered_id')} ({s.get('source')}) {s.get('installed_spec') or ''}".strip(),
        )

    for req in skipped:
        emit("INFO", f"Optional (skipped): {req.get('name', req.get('id'))}")

    has_required_gaps = False
    for g in gaps:
        has_required_gaps = True
        emit("GAP", g["message"], g["id"], g["name"])

    if has_required_gaps:
        emit(
            "GAP",
            "Requirement stack not fully reflected in project manifests. "
            "Add dependencies, run stack-governance for new ids, then check-env.",
            "summary",
            "Requirements gap",
        )
        emit("INFO", "Next: stack-governance skill (Context7) -> scripts/check-env.ps1 -Yes")
        return 1

    emit("OK", "All required technologies are present in project manifests")
    emit("INFO", "Next: scripts/check-env.ps1 (machine + Context7 advisory)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
