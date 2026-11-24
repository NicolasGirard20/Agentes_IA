# agents-orchest-git

Flujo de agentes con **aislamiento por ramas Git + `git worktree`** y manejo determinista de Git mediante script PowerShell (`scripts/orq-git.ps1`), sin gastar tokens de LLM en operaciones rutinarias de Git.

## Qué cambia respecto a `agents/`

| Aspecto | `agents/` (original) | `agents-orchest-git/` |
|---|---|---|
| Carpeta de trabajo | Todos los workers comparten la misma carpeta | 1 copia aislada (`git worktree`) por tarea + 1 worktree `_int` para integración |
| Copia principal del usuario | Se modifica directamente durante el build | Queda intacta hasta que aprobás hacer `merge` a tu rama base |
| Paralelismo | Prohibido compartir archivos entre tareas paralelas | Pueden editar distintas zonas del mismo archivo; si chocan las mismas líneas, se detecta en el merge |
| Commits | Manual al final vía agente `control-versiones` (LLM) | Commit atómico por tarea vía `orq-git.ps1` (cero tokens extra), con validación estricta de `WRITABLE FILES` |
| Reintento tras fallo | Sobre archivos a medio editar | Limpia worktree/rama (`cleanup -Force`) y recrea desde integración limpia |
| Conflictos de merge | No aplica (se evitaban secuenciando) | `integrate` aborta limpio (exit 4) y lanza un worker en worktree `spawn-conflict` (`<tid>-fix`) |
| Verifier y Test | Corren sobre la copia principal | Corren aislados sobre el worktree de integración `_int` |

> **Nota:** `control-versiones.md` se reemplaza intencionalmente por `scripts/orq-git.ps1` para ahorrar tokens y garantizar salidas JSON deterministas.

---

## Jerarquía de ramas y carpetas

```mermaid
flowchart LR
  base["main / base (intacta)"] --> int["orq/<slug>/integration (_int)"]
  int --> t1["orq/<slug>/t1 (worktree t1)"]
  int --> t2["orq/<slug>/t2 (worktree t2)"]
  t1 -->|"commit + merge --no-ff"| int2["orq/<slug>/integration (+t1)"]
  t2 -->|"commit + merge --no-ff"| int2
  int2 --> t3["orq/<slug>/t3 (depende de t1, t2)"]
  t3 -->|"commit + merge --no-ff"| int3["orq/<slug>/integration (final)"]
  int3 -->|"push (PR) o merge local"| base
```

Ubicación de worktrees por defecto (fuera del repo para evitar rutas largas en Windows y ruido en `git status` / mappers):
- Integración del pedido: `C:\wt\<repo>\<slug>\_int` (configurable con `-WtRoot` o variable de entorno `ORQ_WT_ROOT`).
- Cada tarea: `C:\wt\<repo>\<slug>\<task-id>`.
- Tag de checkpoint inicial: `orq/<slug>/base`.

---

## Flujo completo

```mermaid
sequenceDiagram
  participant U as Usuario
  participant O as orchestrator
  participant P as planner
  participant S as orq-git.ps1
  participant B as build-orquestor-cli
  participant W as workers (agy)
  participant V as verifier / test

  O->>S: list (detectar pedidos orq/* activos)
  O->>P: pedido del usuario
  P-->>O: Plan + Git Branch Plan (slug, LinkDeps, hotspots)
  O->>U: Confirmar plan
  O->>S: init -Slug -Base [-LinkDeps]
  O->>B: Plan + _int + ruta orq-git.ps1
  loop Por cada ola del DAG
    B->>S: spawn -Slug -Task tN
    B->>W: agy en worktree tN
    W-->>B: Worker report (DONE)
    B->>S: commit tN (valida WRITABLE FILES)
    B->>S: integrate tN (merge --no-ff a _int)
    opt Si hay conflicto (exit 4)
      B->>S: spawn-conflict tN-fix -FromTask tN
      B->>W: agy resuelve marcadores en tN-fix
      B->>S: commit + integrate tN-fix
    end
  end
  B->>B: Final Checks en _int
  B-->>O: Reporte + workers-status.md
  O->>V: verificar/testear en _int
  O->>U: ¿Push PR / Merge local / Dejar rama / Descartar?
  O->>S: finalize + cleanup
```

---

## Archivos de esta carpeta

| Archivo | Rol |
|---|---|
| [orchestrator.md](orchestrator.md) | Coordina `planner`, inicializa/cierra el pedido con `orq-git.ps1`, lanza `build-orquestor-cli`, `verifier` y `test` en `_int`, y pide confirmación antes de `push`, `merge` o `discard`. |
| [planner.md](planner.md) | Agrega la sección **Git Branch Plan** (`Slug`, `Base branch`, `LinkDeps`, `Conflict hotspots`) y soporta re-planificación incremental leyendo `_int`. |
| [build-orquestor-cli.md](build-orquestor-cli.md) | Orquesta olas DAG: `spawn`, worker `agy` en worktree aislado, `commit` con chequeo de scope, `integrate` (`--no-ff`), retry limpio y resolución de conflictos con `spawn-conflict`. |
| [verifier.md](verifier.md) | Valida UI con `playwright-cli.cmd` levantando el servidor desde el worktree `_int`. |
| [test.md](test.md) | Diseña y corre tests unitarios/E2E dentro de `_int` sin tocar la copia principal. |
| [scripts/orq-git.ps1](scripts/orq-git.ps1) | Script determinista de Git y worktrees para Windows (PowerShell) con salida JSON en una línea. |
| [scripts/orq-git.sh](scripts/orq-git.sh) | Equivalente para Linux / macOS (Bash puro, sin dependencias externas) con las mismas acciones y códigos de salida. |

---

## Referencia rápida de `orq-git.ps1` / `orq-git.sh`

```powershell
# Windows (PowerShell)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\orq-git.ps1 <accion> ...
```

```bash
# Linux / macOS (Bash)
bash scripts/orq-git.sh <accion> --slug <slug> ...
```

| Acción | Parámetros clave | Qué hace |
|---|---|---|
| `init` | `-Slug -Base [-LinkDeps node_modules] [-CopyFiles .env,...] [-WtRoot]` | Crea rama `orq/<slug>/integration`, worktree `_int`, tag `orq/<slug>/base` y enlaza/copia extras. |
| `spawn` | `-Slug -Task` | Crea rama `orq/<slug>/<task>` y worktree desde `integration`. |
| `spawn-conflict` | `-Slug -Task <fixId> -FromTask <task>` | Crea worktree desde `integration` e inicia `merge --no-commit` de `<FromTask>` dejando los conflictos listos para resolver. |
| `commit` | `-Slug -Task -Message -Files` | Verifica que todos los cambios estén dentro de `-Files` y sin secretos; hace `git add` + `commit`. Soporta commits de merge y `-Task integration`. |
| `integrate` | `-Slug -Task` | Hace `merge --no-ff` de `orq/<slug>/<task>` en `_int`. Si hay conflicto, hace `merge --abort` y sale con código `4`. |
| `status` | `-Slug` | Muestra estado de `integration`, tareas, SHAs, commits pendientes y rutas de worktrees. |
| `list` | — | Lista pedidos `orq/*` activos en el repo. |
| `finalize` | `-Slug -Mode none\|push\|merge` | Muestra log o hace `push -u origin` de `integration` o `merge --no-ff` hacia `-Base`. |
| `cleanup` | `-Slug (-Task \| -All) [-Force] [-Discard]` | Elimina worktrees y ramas ya mergeadas (`-Force` fuerza tarea no mergeada; `-Discard` con `-All` descarta incluso `integration` sin mergear). |

### Códigos de salida
- `0`: `OK` / `EMPTY` / `NOOP`
- `2`: `BLOCKED` (precondición o parámetros inválidos; no modifica nada)
- `3`: `SCOPE_VIOLATION` (cambios fuera de `-Files` o archivos sensibles; no commitea)
- `4`: `CONFLICT` (conflicto abortado en `integrate`, o marcadores sin resolver en `commit`)
- `5`: `ERROR` (error de Git o remoto)

---

## Cómo activarlo y consejos en Windows

1. **Activación:** copiá el contenido de `agents-orchest-git\` en `%USERPROFILE%\.gemini\config\agents\` (o en `.agents\` de tu proyecto si querés usarlo por repo).
2. **Rutas largas en Windows:** recomendable activar una vez:
   ```powershell
   git config --global core.longpaths true
   ```
3. **Dependencias pesadas (`node_modules` / `.venv`):** usá `LinkDeps` cuando las tareas no agregan ni actualizan paquetes (crea un Junction de Windows instantáneo sin copiar gigas). Si una tarea modifica `package.json`/lockfiles, dejá `LinkDeps: none`.
4. **Archivos `.env`:** `init` y `spawn` copian automáticamente `.env`, `.env.local`, `.env.development`, `.env.development.local`, `.env.test` al worktree y los excluyen del staging para evitar commits accidentales.
