#!/usr/bin/env python3
"""
Stack preflight: technologies discovered from project manifests + Context7 overrides.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from manifest_index import index_npm_packages, npm_engines_node_floors
from stack_discover import (
    discover_technologies,
    load_advisory_config,
    merge_with_advisory,
    read_pyproject,
    write_discovery_report,
)


def emit(kind: str, message: str, tech_id: str = "", tech_name: str = "") -> None:
    if kind == "CTX7":
        print(f"@CTX7|{tech_id}|{tech_name}|{message}", flush=True)
    else:
        print(f"@{kind}|{message}", flush=True)


def parse_min_version(spec: str) -> tuple[int, int] | None:
    m = re.search(r"(\d+)\.(\d+)", spec or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def version_gte(have: tuple[int, int], need: tuple[int, int]) -> bool:
    return have[0] > need[0] or (have[0] == need[0] and have[1] >= need[1])


def read_node_floor_from_manifests(root: Path) -> int:
    best = 20
    for spec, _ in npm_engines_node_floors(root):
        m = re.search(r"(\d+)", spec or "")
        if m:
            best = max(best, int(m.group(1)))
    return best


def read_pyproject_deps(root: Path) -> dict[str, str]:
    data = read_pyproject(root)
    deps = dict(data.get("dependencies") or {})
    deps.update(data.get("dev_dependencies") or {})
    return deps


def npm_version_in_index(index: dict[str, tuple[str, str]], name: str) -> tuple[str, str] | None:
    hit = index.get(name)
    if hit:
        return hit
    return None


def find_python_candidates() -> list[tuple[str, list[str]]]:
    candidates: list[tuple[str, list[str]]] = []
    if shutil.which("py"):
        for tag in ("3.13", "3.12", "3.11", "3.10", "3.9"):
            candidates.append((f"py -{tag}", ["py", f"-{tag}"]))
    for name in ("python3.13", "python3.12", "python3.11", "python3", "python"):
        if shutil.which(name):
            candidates.append((name, [name]))
    return candidates


def probe_python(cmd: list[str]) -> tuple[int, int] | None:
    code = "import sys; print(sys.version_info.major, sys.version_info.minor)"
    try:
        out = subprocess.run(
            [*cmd, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode != 0:
            return None
        parts = out.stdout.strip().split()
        return int(parts[0]), int(parts[1])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None


def best_python() -> tuple[tuple[int, int] | None, str]:
    best_ver: tuple[int, int] | None = None
    best_label = ""
    for label, cmd in find_python_candidates():
        ver = probe_python(cmd)
        if ver is None:
            continue
        if best_ver is None or version_gte(ver, best_ver):
            best_ver = ver
            best_label = label
    return best_ver, best_label


def read_node_floor(pkg: dict) -> int:
    engines = pkg.get("engines") or {}
    node = engines.get("node", ">=20")
    m = re.search(r"(\d+)", str(node))
    return int(m.group(1)) if m else 20


def emit_context7_status(tech: dict) -> bool:
    c7 = tech.get("context7") or {}
    status = (c7.get("status") or "pending").lower()
    name = tech.get("name") or tech.get("id", "unknown")
    tid = tech.get("id", "unknown")
    reason = c7.get("failure_reason") or ""

    if status == "pending":
        emit(
            "INFO",
            f"[Context7 pending] {name}: discovered from {tech.get('source', 'project')}. "
            f"Run stack-governance skill to fetch current/recommended versions.",
        )
        return False
    if status == "unresolved":
        msg = (
            f"Could not identify current/recommended versions via Context7 for {name}. "
            f"Investigate official sources before confirming deployment. {reason}".strip()
        )
        emit("CTX7", msg, tid, name)
        return True
    if status == "manual":
        msg = (
            f"{name}: manual verification required (not fully covered by Context7). "
            f"Confirm before deploy. {reason}".strip()
        )
        emit("INFO", f"[manual] {msg}")
        return False
    if status == "skipped":
        emit("INFO", f"[skipped Context7] {name}: {reason or 'verify locally'}")
        return False
    if status == "resolved" and not c7.get("library_id"):
        msg = (
            f"Context7 marked resolved for {name} but library_id is missing. "
            f"Re-run stack-governance skill."
        )
        emit("CTX7", msg, tid, name)
        return True
    return False


def check_technology(
    root: Path,
    tech: dict,
    *,
    ci_mode: bool,
    py_floor: str | None,
    req_py: tuple[int, int] | None,
    best_py: tuple[int, int] | None,
    best_py_label: str,
    node_floor: int,
    npm_index: dict[str, tuple[str, str]],
    py_deps: dict,
) -> tuple[list[str], list[str], bool]:
    errors: list[str] = []
    warnings: list[str] = []
    ctx7_unresolved = emit_context7_status(tech)

    check = tech.get("check", "manual")
    name = tech.get("name") or tech.get("id", "?")
    recommended = tech.get("recommended", "")
    installed = tech.get("installed_spec", "")

    if check == "python_runtime":
        if not py_floor:
            errors.append(f"{name}: cannot read requires-python from pyproject.toml")
        else:
            emit("INFO", f"{name} floor {py_floor} ({tech.get('source', '')})")
        if best_py is None:
            errors.append(f"{name}: no Python interpreter found on PATH")
        elif req_py and not version_gte(best_py, req_py):
            warnings.append(
                f"{name}: best {best_py[0]}.{best_py[1]} ({best_py_label}) below floor {py_floor}"
            )
        else:
            emit("OK", f"{name} {best_py[0]}.{best_py[1]} ({best_py_label}) meets floor {py_floor}")
        adv = parse_min_version(str(recommended))
        if best_py and adv and not version_gte(best_py, adv):
            warnings.append(
                f"{name}: advisory recommends {recommended}; installed {best_py[0]}.{best_py[1]}"
            )

    elif check == "node_runtime":
        emit("INFO", f"{name} floor min major {node_floor}")
        if not shutil.which("node"):
            errors.append(f"{name}: not found on PATH")
        else:
            try:
                out = subprocess.run(
                    ["node", "-v"], capture_output=True, text=True, timeout=5
                )
                ver = out.stdout.strip().lstrip("v")
                major = int(ver.split(".")[0])
                if major < node_floor:
                    warnings.append(f"{name}: v{ver} below floor (min major {node_floor})")
                else:
                    emit("OK", f"{name} v{ver} meets floor (manifest {installed})")
                adv = parse_min_version(str(recommended))
                if adv and major < adv[0]:
                    warnings.append(
                        f"{name}: advisory recommends {recommended}; installed v{ver}"
                    )
            except (OSError, ValueError, subprocess.TimeoutExpired):
                errors.append(f"{name}: could not read version")

    elif check == "cli":
        cli = tech.get("cli", "")
        if ci_mode and cli in ("docker",):
            return errors, warnings, ctx7_unresolved
        if shutil.which(cli):
            emit("OK", f"{name} ({cli}) found on PATH")
        else:
            warnings.append(f"{name}: {cli} not on PATH (project expects it: {tech.get('source', '')})")

    elif check == "py_package":
        pkg_name = tech.get("package", "")
        spec = py_deps.get(pkg_name)
        if not spec:
            warnings.append(f"{name}: {pkg_name} not in pyproject.toml (discovered from {tech.get('source')})")
        else:
            rec = f" advisory {recommended}" if recommended else ""
            emit("OK", f"{name} {pkg_name}{spec} in pyproject{rec}")

    elif check == "npm_package":
        pkg_name = tech.get("package", "")
        hit = npm_version_in_index(npm_index, pkg_name)
        if not hit:
            warnings.append(
                f"{name}: {pkg_name} missing from any package.json (discovered from {tech.get('source')})"
            )
        else:
            ver, src = hit
            rec = f" advisory {recommended}" if recommended else ""
            emit("OK", f"{name} {pkg_name}@{ver} ({src}){rec}")

    elif check == "sqlite_module":
        found = False
        for label, cmd in find_python_candidates():
            try:
                out = subprocess.run(
                    [*cmd, "-c", "import sqlite3; print(sqlite3.sqlite_version)"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if out.returncode == 0:
                    emit(
                        "OK",
                        f"{name} sqlite3 {out.stdout.strip()} (advisory {recommended or 'n/a'})",
                    )
                    found = True
                    break
            except (OSError, subprocess.TimeoutExpired):
                continue
        if not found:
            warnings.append(f"{name}: could not probe sqlite3 (need Python on PATH)")

    elif check == "dockerfile_from":
        line = tech.get("docker_line")
        ref = tech.get("docker_ref", "")
        if line:
            rec = f" advisory {recommended}" if recommended else ""
            emit("OK", f"{name}: {line}{rec}")
        else:
            warnings.append(f"{name}: no Dockerfile FROM for {ref}")

    elif check == "env_secret":
        if ci_mode:
            return errors, warnings, ctx7_unresolved
        env_path = root / ".env"
        var = tech.get("env_var", "")
        if not env_path.is_file():
            warnings.append(f"{name}: .env missing ({var})")
        elif not re.search(
            rf"{re.escape(var)}\s*=\s*\S+", env_path.read_text(encoding="utf-8")
        ):
            warnings.append(f"{name}: {var} not set in .env")
        else:
            emit("OK", f"{name}: {var} present in .env")

    elif check == "manual":
        emit("INFO", f"{name}: {tech.get('source', 'manual')} - {installed or recommended or 'verify standards'}")

    return errors, warnings, ctx7_unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Stack environment preflight")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument(
        "--write-discovery",
        action="store_true",
        help="Write docs/stack-discovered.json report",
    )
    args = parser.parse_args()

    ci_mode = args.ci or os.environ.get("CI") == "true" or os.environ.get("CHECK_ENV_CI") == "1"
    root = Path(__file__).resolve().parents[2]

    emit("INFO", "=== Stack preflight (dynamic discovery) ===")
    emit("INFO", "Technologies inferred from manifests; Context7 metadata from stack-advisory.json")

    advisory = load_advisory_config(root)
    discovered = discover_technologies(root, advisory)
    technologies, orphaned = merge_with_advisory(discovered, advisory)

    if args.write_discovery:
        report_path = write_discovery_report(root, discovered, orphaned)
        emit("INFO", f"Wrote discovery report: {report_path.relative_to(root)}")

    emit("INFO", f"Discovered {len(discovered)} technologies from project files")

    errors: list[str] = []
    warnings: list[str] = []
    ctx7_unresolved_ids: list[str] = []

    py_data = read_pyproject(root)
    py_floor = py_data.get("requires_python")
    req_py = parse_min_version(py_floor or "")
    best_py, best_py_label = best_python()
    npm_index = index_npm_packages(root)
    node_floor = read_node_floor_from_manifests(root)
    py_deps = read_pyproject_deps(root)

    if not advisory:
        warnings.append("docs/stack-advisory.json missing - run stack-governance for Context7 metadata")
    else:
        reviewed = advisory.get("last_reviewed")
        stale_days = int(advisory.get("stale_after_days", 90))
        if reviewed:
            try:
                dt = datetime.fromisoformat(reviewed).replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - dt).days
                if age > stale_days:
                    warnings.append(
                        f"Stack advisory stale ({reviewed}, {age} days). Run stack-governance + Context7."
                    )
                else:
                    emit("OK", f"Context7 overrides fresh ({reviewed})")
            except ValueError:
                warnings.append("stack-advisory.json: invalid last_reviewed")

    for oid in orphaned:
        warnings.append(
            f"Advisory override '{oid}' not in current project - remove or add dependency"
        )

    pending = sum(
        1
        for t in technologies
        if (t.get("context7") or {}).get("status") == "pending"
    )
    if pending:
        emit("INFO", f"{pending} technologies have no Context7 review yet (stack-governance skill)")

    emit("INFO", f"Checking {len(technologies)} technologies...")
    for tech in technologies:
        e, w, u = check_technology(
            root,
            tech,
            ci_mode=ci_mode,
            py_floor=py_floor,
            req_py=req_py,
            best_py=best_py,
            best_py_label=best_py_label,
            node_floor=node_floor,
            npm_index=npm_index,
            py_deps=py_deps,
        )
        errors.extend(e)
        warnings.extend(w)
        if u:
            ctx7_unresolved_ids.append(tech.get("id", "?"))

    if ctx7_unresolved_ids:
        emit(
            "CTX7",
            "Technologies lack Context7 version guidance. Investigate before production deploy.",
            "summary",
            "Deploy caution",
        )

    for e in errors:
        emit("ERR", e)
    for w in warnings:
        emit("WARN", w)

    if errors:
        emit("ERR", "Fix errors above before continuing.")
        return 1

    if warnings:
        if args.strict:
            emit("ERR", "Strict mode: warnings treated as errors.")
            return 1
        if args.yes:
            emit("WARN", "Continuing despite warnings (-Yes).")
            return 0
        if sys.stdin.isatty():
            try:
                answer = input("Continue anyway? [y/N] ").strip()
            except EOFError:
                answer = ""
            if answer.lower() not in ("y", "yes"):
                emit("WARN", "Stopped. Fix warnings or run with -y / -Yes.")
                return 2
            return 0
        return 0

    emit("OK", f"Environment OK - {len(technologies)} technologies checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
