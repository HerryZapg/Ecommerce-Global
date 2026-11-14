# Stack governance — ritual mínimo (ROI)

Una vez por repo (PowerShell):

```powershell
cd "REPO_PATH"
& "$env:USERPROFILE\.cursor\skills\stack-governance\scripts\install_toolchain.ps1" `
  -Target (Get-Location).Path `
  -InstallGate
```

Comprueba: `.cursor/rules/stack-governance-gate.mdc` y `scripts/lib/stack_contract.py`.

---

## Mensaje 1 — pegar antes del mega/medium spec

```
@stack-governance

Repo: REPO_PATH
Feature: <nombre del epic>

Audita el pin-set del spec (MODE B o HYBRID, profundidad standard).
Gate activo: no package.json ni código de app hasta stack approved.

Si falta cupo Context7 → paro con [C7-BUDGET]; espero: continuar stack
Cuando el audit esté listo → stack approved — opción A|B (o with risks: …)

Tras stack approved, en el mismo turno (G-STACK-CLOSE):
  py -3 "$env:USERPROFILE\.cursor\skills\stack-governance\scripts\stack_close.py" `
    --repo "REPO_PATH" `
    --pins docs/approved-pins.json `
    --scaffold-if-missing
Luego plan bootstrap numerado (S6) antes de implementar features.
```

Sustituye `REPO_PATH` por la ruta absoluta (ej. `D:\...\Creacion Ecommerce m6`).

---

## Tras scaffold + install de deps (checkpoint ROI)

Cuando existan `package.json` / `pom.xml` en el repo:

```powershell
py -3 scripts/lib/stack_contract.py
```

O desde cualquier cwd:

```powershell
py -3 scripts/lib/stack_contract.py "REPO_PATH" "REPO_PATH\docs\approved-pins.json"
```

| Salida | Acción |
|--------|--------|
| exit 0, sin DRIFT | Seguir implementación |
| `DRIFT` | Corregir manifests o nueva aprobación — no “optimizar” stack en silencio |
| `MISSING` | Pin aún no en manifests (pre-bootstrap OK; post-install revisar) |
| `pending` | Aún no hay manifests |

No re-auditar con Context7 en “implementa el MVP”.

---

## Frases (solo tres)

| Frase | Cuándo |
|-------|--------|
| *(spec inicial)* | S0–S1 |
| `continuar stack` | S2 si `[C7-BUDGET]` |
| `stack approved` / `stack approved with risks: …` | S3 → S4–S6 |
