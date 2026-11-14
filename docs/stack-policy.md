# Stack version policy

Two layers keep the project current without hard-coding versions in scripts.

## Layer 1 — Project floor (machine-enforced)

**Source of truth:** files in the repo, read at runtime by `scripts/check-env.*`

| File | What it defines |
|------|------------------|
| `pyproject.toml` | `requires-python` (minimum Python) |
| `frontend/package.json` | `engines.node` (minimum Node) |
| `Dockerfile` | Production runtime (must stay aligned with floor) |

`check-env` runs `scripts/lib/stack_check.py`, which parses manifests every run. It does **not** embed fixed versions in shell code.

**Enforcement:** `dev.*`, `start.*`, and CI must pass preflight before work continues.

**Scope:** Every technology **discovered** from the repo (see `scripts/lib/stack_discover.py`). Count changes when you add/remove dependencies — not a fixed list.

## Layer 2 — Advisory “what is optimal now?” (agent + Context7)

Technologies change. The advisory file records **recommended** versions after a deliberate review.

| File | Purpose |
|------|---------|
| `docs/stack-advisory.json` | `context7_overrides` only (metadata keyed by discovered id) |
| `docs/stack-discovered.json` | Auto-generated inventory (`--write-discovery`) |
| Skill `stack-governance` (global, `~/.cursor/skills/`) | Full workflow; Layer 3 = Context7 advisory |
| `scripts/lib/stack_discover.py` | Scans manifests and builds technology list |
| `scripts/lib/stack_check.py` | Runs discovery + checks + terminal output |

`check-env` **warns** (yellow highlight for Context7 gaps) when:

- `context7.status` is `unresolved` (could not identify current/recommended versions)
- `context7.status` is `manual` (user must verify before deploy)
- Advisory is older than `stale_after_days` (default 90)
- Installed runtime meets the floor but is below advisory

It does **not** call Context7 live (that requires the agent). It reads the last review recorded in JSON.

## Layer 3 — Requirements-driven stack (feature / user story)

| File | Purpose |
|------|---------|
| `docs/stack-requirements.json` | Technologies the **requirement** needs (agent-maintained) |
| `docs/stack-requirements.example.json` | Template |
| Skill `stack-governance` Layer 2 | Requirement → JSON → compare → gaps |
| `scripts/lib/stack_requirements.py` | Compare requirements vs discovered manifests |

Yellow **REQUIREMENTS GAP** = required by spec but missing from `pyproject.toml` / `package.json` / Dockerfile.

## When to use which

| Situation | Action |
|-----------|--------|
| Daily dev | `./scripts/check-env.sh` or `check-env.ps1` |
| New machine / new clone | Same |
| **New feature / architecture** | **stack-governance** skill Layer 2 → `stack-requirements.ps1` |
| Quarterly or before major upgrade | **stack-governance** skill Layer 3 (Context7) |
| New dependency or framework bump | Context7 for that library + update floor files if needed |
| User wants “simplest effective” stack | `stack-governance` (S1 audit) with user goals in the prompt |

## Principles

1. **Never silently downgrade** runtime below the project floor.
2. **Do not hard-code** advisory versions in shell scripts; read JSON + manifests.
3. **Prefer simple paths:** `uv` + Python from floor, Node from `engines`, Docker for prod parity.
4. **Context7** for current docs and version guidance; not for replacing `check-env`.
