#!/usr/bin/env python3
"""
Verify docs/approved-pins.json against manifests found in the repo.

Flat pins only. Uses manifest_index (same as discover/check).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from manifest_index import build_manifest_index


def load_pins(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "pins" in data and isinstance(data["pins"], dict):
        return {k: str(v) for k, v in data["pins"].items()}
    if all(isinstance(v, str) for v in data.values()):
        return dict(data)
    raise ValueError("approved-pins.json must be { pins: {...} } or a flat map")


def check_contract(
    repo: Path, approved_path: Path, *, strict: bool = False
) -> tuple[int, list[str]]:
    pins = load_pins(approved_path)
    index, pkg_files, pom_files = build_manifest_index(repo)

    if not index:
        return 0, ["[contract] pending: no package.json or pom.xml under repo"]

    drift: list[str] = []
    missing: list[str] = []

    for key, want in pins.items():
        hit = index.get(key)
        if not hit:
            missing.append(f"[contract] MISSING {key}={want}")
            continue
        got, where = hit
        if got != want:
            drift.append(f"[contract] DRIFT {key}: approved {want}, found {got} ({where})")

    lines = [
        f"[contract] checked {len(pins)} pins — "
        f"{len(index)} keys from {pkg_files} package.json, {pom_files} pom.xml",
    ]
    lines.extend(drift)
    lines.extend(missing)

    if drift:
        return 1, lines
    if strict and missing:
        return 1, lines
    return 0, lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repo root")
    parser.add_argument(
        "approved",
        nargs="?",
        default="",
        help="Path to approved-pins.json (default: docs/approved-pins.json under repo)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any pin is MISSING (use after npm install / mvn)",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    approved = Path(args.approved).resolve() if args.approved else repo / "docs" / "approved-pins.json"

    if not approved.is_file():
        print("[contract] no approved-pins file; nothing to check")
        return 0

    code, lines = check_contract(repo, approved, strict=args.strict)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
