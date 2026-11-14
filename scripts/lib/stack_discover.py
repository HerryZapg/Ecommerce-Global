"""
Discover technologies required by the project from manifests (not a fixed list).
Merges with docs/stack-advisory.json context7_overrides for Context7 metadata only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from manifest_index import iter_package_json, normalize_id, npm_engines_node_floors, rel

# Display names for common packages (fallback: title-case id)
DISPLAY_NAMES: dict[str, str] = {
    "python": "Python",
    "node": "Node.js",
    "uv": "uv (Python package manager)",
    "docker": "Docker",
    "fastapi": "FastAPI",
    "uvicorn": "Uvicorn",
    "pydantic": "Pydantic",
    "httpx": "HTTPX",
    "passlib": "Passlib",
    "pytest": "pytest",
    "pytest-cov": "pytest-cov",
    "next": "Next.js",
    "react": "React",
    "react-dom": "React DOM",
    "typescript": "TypeScript",
    "tailwindcss": "Tailwind CSS",
    "eslint": "ESLint",
    "vitest": "Vitest",
    "@playwright/test": "Playwright",
    "html": "HTML (living standard)",
    "css": "CSS",
    "sqlite": "SQLite",
    "openrouter": "OpenRouter API",
    "python-dotenv": "python-dotenv",
    "python-multipart": "python-multipart",
}

TESTING_IDS = frozenset(
    {
        "pytest",
        "pytest-cov",
        "vitest",
        "@playwright/test",
        "@testing-library/jest-dom",
        "@testing-library/react",
        "@testing-library/user-event",
        "@vitest/coverage-v8",
    }
)

FRONTEND_IDS = frozenset(
    {
        "next",
        "react",
        "react-dom",
        "typescript",
        "tailwindcss",
        "eslint",
        "eslint-config-next",
        "@tailwindcss/postcss",
        "clsx",
        "@dnd-kit/core",
        "@dnd-kit/sortable",
        "@dnd-kit/utilities",
        "@vitejs/plugin-react",
        "jsdom",
    }
)


def _node_major(spec: str) -> int:
    m = re.search(r"(\d+)", spec or "")
    return int(m.group(1)) if m else 0


def display_name(tech_id: str, package: str | None = None) -> str:
    key = package or tech_id
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    if key.startswith("@"):
        return key
    return key.replace("-", " ").title()


def infer_category(tech_id: str, check: str, package: str | None = None) -> str:
    pkg = package or tech_id
    if check in ("python_runtime", "node_runtime"):
        return "runtime"
    if check == "cli":
        return "tool"
    if check in ("dockerfile_from",):
        return "deploy"
    if check in ("env_secret",):
        return "ai" if "openrouter" in tech_id else "config"
    if check in ("manual",) and tech_id in ("html", "css"):
        return "web-platform"
    if check == "sqlite_module":
        return "database"
    if pkg in TESTING_IDS or tech_id in TESTING_IDS:
        return "testing"
    if pkg in FRONTEND_IDS or tech_id in FRONTEND_IDS:
        return "frontend"
    return "backend"


def parse_toml_dependency_lines(text: str, section_marker: str) -> dict[str, str]:
    deps: dict[str, str] = {}
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(section_marker):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("[") and not stripped.startswith("["):
                break
            if stripped == "]":
                in_section = False
                continue
            if stripped.startswith("[") and "]" in stripped:
                in_section = False
                continue
            m = re.match(r'"([^"]+)"', stripped)
            if m:
                raw = m.group(1)
                base = re.split(r"[<>=!~]", raw, maxsplit=1)[0]
                name = base.split("[")[0].strip()
                spec = raw[len(base) :] if base else ""
                deps[name] = spec or "pinned"
    return deps


def read_pyproject(root: Path) -> dict[str, Any]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    requires = None
    m = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
    if m:
        requires = m.group(1)
    main = parse_toml_dependency_lines(text, "dependencies = [")
    dev = parse_toml_dependency_lines(text, "dev = [")
    uses_uv = "uv " in text or "astral-sh/uv" in text
    return {"requires_python": requires, "dependencies": main, "dev_dependencies": dev, "uses_uv": uses_uv}


def read_npm_package(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_dockerfile_images(root: Path) -> list[dict[str, str]]:
    dockerfile = root / "Dockerfile"
    if not dockerfile.is_file():
        return []
    images: list[dict[str, str]] = []
    for line in dockerfile.read_text(encoding="utf-8").splitlines():
        if line.strip().upper().startswith("FROM"):
            ref = line.strip().split(None, 1)[1].split()[0]
            images.append({"line": line.strip(), "ref": ref})
    return images


def read_env_vars(root: Path) -> list[str]:
    vars_found: list[str] = []
    for name in (".env.example", ".env"):
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=", line)
            if m and m.group(1) not in vars_found:
                vars_found.append(m.group(1))
    return vars_found


def read_ci_versions(root: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return versions
    for yml in workflows.glob("*.yml"):
        text = yml.read_text(encoding="utf-8")
        py = re.search(r'python-version:\s*["\']?([^"\'\s]+)', text)
        if py:
            versions["ci_python"] = py.group(1)
        node = re.search(r'node-version:\s*["\']?([^"\'\s]+)', text)
        if node:
            versions["ci_node"] = node.group(1)
    return versions


def uses_sqlite(root: Path) -> bool:
    env = root / ".env.example"
    if env.is_file() and "DATABASE_PATH" in env.read_text(encoding="utf-8"):
        return True
    backend = root / "backend"
    if not backend.is_dir():
        return False
    for py in backend.rglob("*.py"):
        try:
            if "sqlite" in py.read_text(encoding="utf-8", errors="ignore").lower():
                return True
        except OSError:
            continue
    return False


def _item(
    tech_id: str,
    *,
    check: str,
    source: str,
    package: str | None = None,
    section: str | None = None,
    installed_spec: str | None = None,
    cli: str | None = None,
    env_var: str | None = None,
    docker_line: str | None = None,
    docker_ref: str | None = None,
    floor_source: str | None = None,
) -> dict[str, Any]:
    pkg = package or tech_id
    return {
        "id": tech_id,
        "name": display_name(tech_id, pkg),
        "category": infer_category(tech_id, check, pkg),
        "check": check,
        "source": source,
        "package": package,
        "section": section,
        "installed_spec": installed_spec,
        "cli": cli,
        "env_var": env_var,
        "docker_line": docker_line,
        "docker_ref": docker_ref,
        "floor_source": floor_source,
        "discovered": True,
    }


def discover_technologies(root: Path, config: dict | None = None) -> list[dict[str, Any]]:
    """Build technology list from project files. Grows/shrinks with the repo."""
    config = config or {}
    discovery_cfg = config.get("discovery") or {}
    items: dict[str, dict[str, Any]] = {}

    def add(tech: dict[str, Any]) -> None:
        tid = tech["id"]
        if tid not in items:
            items[tid] = tech
            return
        # Prefer richer source (keep first discovery source, merge spec if missing)
        if not items[tid].get("installed_spec") and tech.get("installed_spec"):
            items[tid]["installed_spec"] = tech["installed_spec"]

    pyproject = read_pyproject(root)
    if pyproject.get("requires_python"):
        add(
            _item(
                "python",
                check="python_runtime",
                source="pyproject.toml:requires-python",
                installed_spec=pyproject["requires_python"],
                floor_source="pyproject.toml",
            )
        )

    for name, spec in (pyproject.get("dependencies") or {}).items():
        tid = normalize_id(name)
        add(
            _item(
                tid,
                check="py_package",
                source="pyproject.toml:dependencies",
                package=name,
                installed_spec=spec,
            )
        )

    for name, spec in (pyproject.get("dev_dependencies") or {}).items():
        tid = normalize_id(name)
        add(
            _item(
                tid,
                check="py_package",
                source="pyproject.toml:optional-dependencies.dev",
                package=name,
                section="dev",
                installed_spec=spec,
            )
        )

    node_best: tuple[int, str, str] | None = None
    for pj in iter_package_json(root):
        pkg_data = read_npm_package(pj)
        if not pkg_data:
            continue
        src = rel(root, pj)
        engines = (pkg_data.get("engines") or {}).get("node")
        if engines:
            major = _node_major(str(engines))
            if node_best is None or major > node_best[0]:
                node_best = (major, str(engines), f"{src}:engines.node")
        for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
            for name, spec in (pkg_data.get(section) or {}).items():
                tid = normalize_id(name)
                add(
                    _item(
                        tid,
                        check="npm_package",
                        source=f"{src}:{section}",
                        package=name,
                        section=section,
                        installed_spec=spec,
                    )
                )

    if node_best:
        _, spec, source = node_best
        add(
            _item(
                "node",
                check="node_runtime",
                source=source,
                installed_spec=spec,
                floor_source=source.split(":")[0],
            )
        )

    for img in read_dockerfile_images(root):
        ref = img["ref"]
        tid = "dockerimg-" + normalize_id(ref.replace(":", "-"))
        add(
            {
                **_item(
                    tid,
                    check="dockerfile_from",
                    source="Dockerfile:FROM",
                    docker_line=img["line"],
                    docker_ref=ref,
                    installed_spec=ref,
                ),
                "name": f"Docker image ({ref})",
            }
        )

    if (root / "Dockerfile").is_file():
        add(
            _item(
                "docker",
                check="cli",
                source="Dockerfile (deploy)",
                cli="docker",
            )
        )

    docker_text = ""
    if (root / "Dockerfile").is_file():
        docker_text = (root / "Dockerfile").read_text(encoding="utf-8")
    if pyproject.get("uses_uv") or "uv" in docker_text:
        add(_item("uv", check="cli", source="Dockerfile/pyproject (uv)", cli="uv"))

    for var in read_env_vars(root):
        if var == "OPENROUTER_API_KEY":
            add(
                _item(
                    "openrouter",
                    check="env_secret",
                    source=".env.example",
                    env_var=var,
                )
            )

    if uses_sqlite(root):
        add(_item("sqlite", check="sqlite_module", source="backend/.env DATABASE_PATH"))

    implicit = discovery_cfg.get("implicit_when_frontend") or ["html", "css"]
    has_web_app = any(
        pj.parent.name in ("frontend", "web") or "apps" in pj.parts
        for pj in iter_package_json(root)
        if read_npm_package(pj).get("dependencies")
    )
    if has_web_app:
        for tid in implicit:
            add(
                _item(
                    tid,
                    check="manual",
                    source="discovery:web app package.json present",
                    installed_spec="project uses HTML/CSS output",
                )
            )

    # CI pins (informational entries)
    ci = read_ci_versions(root)
    if ci.get("ci_python"):
        add(
            _item(
                "ci-python",
                check="manual",
                source=".github/workflows (CI pin)",
                installed_spec=ci["ci_python"],
            )
        )
    if ci.get("ci_node"):
        add(
            _item(
                "ci-node",
                check="manual",
                source=".github/workflows (CI pin)",
                installed_spec=ci["ci_node"],
            )
        )

    return sorted(items.values(), key=lambda t: (t.get("category", ""), t.get("name", "")))


def migrate_v2_technologies_to_overrides(data: dict) -> dict[str, Any]:
    overrides: dict[str, Any] = dict(data.get("context7_overrides") or {})
    for tech in data.get("technologies") or []:
        tid = tech.get("id")
        if not tid:
            continue
        overrides.setdefault(tid, {})
        if tech.get("recommended"):
            overrides[tid]["recommended"] = tech["recommended"]
        if tech.get("context7"):
            overrides[tid]["context7"] = tech["context7"]
    return overrides


def load_advisory_config(root: Path) -> dict[str, Any]:
    path = root / "docs" / "stack-advisory.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    schema = data.get("schema_version", 1)
    if schema < 3:
        data["context7_overrides"] = migrate_v2_technologies_to_overrides(data)
        data["schema_version"] = 3
    # legacy v1 stack{}
    if not data.get("context7_overrides") and data.get("stack"):
        for tid, item in data["stack"].items():
            if isinstance(item, dict):
                c7id = item.get("context7_library_id")
                data.setdefault("context7_overrides", {})[tid] = {
                    "recommended": item.get("recommended"),
                    "context7": {
                        "status": "resolved" if c7id else "manual",
                        "library_id": c7id,
                    },
                }
    return data


def merge_with_advisory(
    discovered: list[dict[str, Any]], advisory: dict[str, Any]
) -> list[dict[str, Any]]:
    overrides = advisory.get("context7_overrides") or {}
    merged: list[dict[str, Any]] = []

    for tech in discovered:
        tid = tech["id"]
        out = dict(tech)
        ov = overrides.get(tid) or overrides.get(tech.get("package", "")) or {}
        if ov.get("recommended"):
            out["recommended"] = ov["recommended"]
        if ov.get("name"):
            out["name"] = ov["name"]
        c7 = dict(ov.get("context7") or {})
        if not c7:
            c7 = {
                "status": "pending",
                "library_id": None,
                "failure_reason": "Not yet reviewed; run stack-governance skill with Context7",
            }
        out["context7"] = c7
        merged.append(out)

    discovered_ids: set[str] = set()
    for t in discovered:
        discovered_ids.add(t["id"])
        pkg = t.get("package")
        if pkg:
            discovered_ids.add(pkg)
            discovered_ids.add(normalize_id(pkg))

    orphaned = [k for k in overrides if k not in discovered_ids]
    return merged, orphaned


def write_discovery_report(root: Path, discovered: list[dict], orphaned: list[str]) -> Path:
    path = root / "docs" / "stack-discovered.json"
    report = {
        "generated_by": "scripts/lib/stack_discover.py",
        "count": len(discovered),
        "technologies": [
            {
                "id": t["id"],
                "name": t["name"],
                "category": t["category"],
                "check": t["check"],
                "source": t["source"],
                "installed_spec": t.get("installed_spec"),
                "package": t.get("package"),
            }
            for t in discovered
        ],
        "orphaned_advisory_overrides": orphaned,
    }
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path
