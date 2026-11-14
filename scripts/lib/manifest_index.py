"""Shared manifest discovery — one indexer for contract, discover, and check."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

SKIP_DIRS = frozenset({"node_modules", ".next", "dist", "build", ".turbo", ".git", "target"})

NPM_SECTIONS = ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")


def normalize_id(name: str) -> str:
    key = name.lstrip("@")
    return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def iter_manifests(root: Path, name: str) -> Iterable[Path]:
    for path in root.rglob(name):
        if SKIP_DIRS & set(path.parts):
            continue
        yield path


def iter_package_json(root: Path) -> Iterable[Path]:
    yield from iter_manifests(root, "package.json")


def index_npm_packages(root: Path) -> dict[str, tuple[str, str]]:
    """packageName -> (versionSpec, sourceRelPath:section). First file wins per key."""
    out: dict[str, tuple[str, str]] = {}
    for pj in iter_package_json(root):
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        src = rel(root, pj)
        for section in NPM_SECTIONS:
            block = data.get(section)
            if not isinstance(block, dict):
                continue
            for name, spec in block.items():
                if isinstance(spec, str) and name not in out:
                    out[name] = (spec, f"{src}:{section}")
    return out


def npm_engines_node_floors(root: Path) -> list[tuple[str, str]]:
    """All engines.node specs found in any package.json."""
    floors: list[tuple[str, str]] = []
    for pj in iter_package_json(root):
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        node = (data.get("engines") or {}).get("node")
        if node:
            floors.append((str(node), rel(root, pj)))
    return floors


def _local_tag(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def index_one_pom(pom: Path, root: Path) -> dict[str, tuple[str, str]]:
    try:
        proj = ET.parse(str(pom)).getroot()
    except ET.ParseError:
        return {}

    src = rel(root, pom)
    out: dict[str, tuple[str, str]] = {}

    parent = proj.find("{*}parent")
    if parent is not None:
        aid = parent.find("{*}artifactId")
        ver = parent.find("{*}version")
        if aid is not None and aid.text and ver is not None and ver.text:
            out[aid.text.strip()] = (ver.text.strip(), f"{src}:parent")

    props = proj.find("{*}properties")
    if props is not None:
        for child in props:
            if child.text and child.text.strip():
                key = _local_tag(child.tag)
                out[key] = (child.text.strip(), f"{src}:properties.{key}")

    for dep in proj.findall(".//{*}dependency"):
        ver_el = dep.find("{*}version")
        aid_el = dep.find("{*}artifactId")
        if ver_el is None or aid_el is None or not ver_el.text or not aid_el.text:
            continue
        out[aid_el.text.strip()] = (ver_el.text.strip(), f"{src}:dependency")

    return out


def index_pom_xml(root: Path) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for pom in iter_manifests(root, "pom.xml"):
        for key, val in index_one_pom(pom, root).items():
            if key not in out:
                out[key] = val
    return out


def build_manifest_index(root: Path) -> tuple[dict[str, tuple[str, str]], int, int]:
    pkg = index_npm_packages(root)
    pom = index_pom_xml(root)
    merged: dict[str, tuple[str, str]] = dict(pkg)
    for key, val in pom.items():
        if key not in merged:
            merged[key] = val
    pkg_files = sum(1 for _ in iter_package_json(root))
    pom_files = sum(1 for _ in iter_manifests(root, "pom.xml"))
    return merged, pkg_files, pom_files
