# Flujo actual de agentes

Diagrama construido a partir de los archivos actuales en
`general/gemini/.gemini/config/agents/`.

```mermaid
flowchart TD
    IN(["Solicitud del usuario"]) --> ENTRY{"Punto de entrada"}

    ENTRY -->|"Flujo orquestado (principal)"| ORCH["orchestrator\nCoordina el ciclo completo e inicializa workers-status.md"]
    ENTRY -->|"Suite de pruebas independiente"| TEST["test\nMapea con project-mapper-simple / rag-json y consulta ui-skills"]

    %% Ruta independiente: test
    TEST --> TEST_SCOPE{"¿Alcance claro?"}
    TEST_SCOPE -->|"No"| TEST_ASK["ask_question al usuario"]
    TEST_ASK --> TEST
    TEST_SCOPE -->|"Sí"| TEST_BUILD["Crea y ejecuta tests\ntest/unit-test/ y test/e2e/ (playwright@latest)"]
    TEST_BUILD --> TEST_OUT(["Resultados en test/results/ y reporte"])

    %% Flujo principal: orchestrator -> planner
    ORCH -->|"1. Invoca (inherit)"| PLAN["planner\nPre-flight obligatorio: rag-json (fallback project-mapper-simple)"]
    PLAN --> PLAN_GATE{"¿Skills OK y mapa dentro de umbral?\n(<=150 archivos y <=40 KB)"}
    PLAN_GATE -->|"No"| PLAN_BLOCK(["🚫 BLOCKED: aborta sin planificar"])
    PLAN_GATE -->|"Sí"| PLAN_AMB{"¿Ambigüedades críticas?"}
    PLAN_AMB -->|"Sí"| CLARIFY["orchestrator pregunta al usuario\ny reenvía respuestas a planner"]
    CLARIFY --> PLAN
    PLAN_AMB -->|"No"| PLAN_OUT["Plan dividido en tareas\n(Depends on, Writable files, Complexity, Commit, UI Verification)"]

    PLAN_OUT --> APPROVE{"3. ¿Usuario aprueba el plan?"}
    APPROVE -->|"No: pide cambios"| PLAN
    APPROVE -->|"Sí"| BUILD_INIT["4. orchestrator inicializa workers-status.md (⏳ PENDING)\ne invoca build-orquestor-cli (flash)"]

    %% Ejecución: build-orquestor-cli -> workers agy
    BUILD_INIT --> BO["build-orquestor-cli\nDespacha waves en paralelo (máx. 5, archivos disjuntos)"]
    BO --> AGY["Workers headless agy CLI (--sandbox)\nModelo según Complexity"]
    AGY --> TASK_RES{"Resultado de tarea"}
    TASK_RES -->|"FAILED (1er intento)"| RETRY["Reintenta 1 vez con modelo superior\n(gemini-4-argon-low / gemini-4-hydrogen-high)"]
    RETRY --> TASK_RES
    TASK_RES -->|"BLOCKED o FAILED x2"| SKIP_DEP["Marca dependientes ⏭️ SKIPPED\ny omite Final Checks"]
    TASK_RES -->|"Todas ✅ DONE"| FINAL_CHK["Ejecuta Final Checks del plan"]

    FINAL_CHK --> BUILD_OK{"5. ¿Build y Final Checks OK?"}
    BUILD_OK -->|"No"| BUILD_FAIL_ASK{"orchestrator pregunta al usuario"}
    SKIP_DEP --> BUILD_FAIL_ASK
    BUILD_FAIL_ASK -->|"Retry failed tasks"| BO
    BUILD_FAIL_ASK -->|"Re-plan with planner (incremental)"| PLAN
    BUILD_FAIL_ASK -->|"Stop here"| END_STOP(["Fin sin commit"])

    %% Verificación en navegador: verifier
    BUILD_OK -->|"Sí"| UI_DEC{"6. ¿UI Verification != none?"}
    UI_DEC -->|"No (none)"| COMMIT_ASK
    UI_DEC -->|"Sí"| VER["verifier\nLevanta server si falta y valida flujos con playwright-cli (-s=verify)\nRevisa snapshot, console y requests; limpia sesión y server"]

    VER --> VER_RES{"Resultado de verifier"}
    VER_RES -->|"VERIFIED / SKIPPED"| COMMIT_ASK
    VER_RES -->|"BLOCKED (entorno/server)"| VER_BLOCK_ASK{"orchestrator pregunta al usuario\n(no reenvía a planner)"}
    VER_BLOCK_ASK -->|"Re-run verifier"| VER
    VER_BLOCK_ASK -->|"Ignore and continue to commit"| COMMIT_ASK
    VER_BLOCK_ASK -->|"Stop here"| END_STOP

    VER_RES -->|"FAILED (UI/consola/red)"| VER_FAIL_ASK{"orchestrator pregunta al usuario\n(tope: 1 ciclo de re-plan por defecto)"}
    VER_FAIL_ASK -->|"Re-plan with planner\n(reporte + baseline modificado)"| PLAN
    VER_FAIL_ASK -->|"Re-run verifier"| VER
    VER_FAIL_ASK -->|"Ignore and continue to commit"| COMMIT_ASK
    VER_FAIL_ASK -->|"Stop here"| END_STOP

    %% Commit: version-control
    COMMIT_ASK{"7. ¿Usuario aprueba commit?\n(Commit and push / Commit only / Skip)"}
    COMMIT_ASK -->|"Skip commit"| END_OK(["Fin sin commit"])
    COMMIT_ASK -->|"Aprobado"| VC["version-control (flash_lite)\nValida rutas sensibles e índice limpio (git diff --cached)"]
    VC --> VC_GATE{"¿Pre-checks OK?"}
    VC_GATE -->|"No"| VC_BLOCK(["STATUS: BLOCKED / ERROR"])
    VC_GATE -->|"Sí"| VC_EXEC["git add -- files + git commit por tarea\n(+ git push si PUSH: yes)"]
    VC_EXEC --> END_DONE(["Resultado final al usuario"])

    classDef agent fill:#e8f1fb,stroke:#2563eb,color:#111827;
    classDef decision fill:#fff7ed,stroke:#ea580c,color:#111827;
    classDef stop fill:#fef2f2,stroke:#dc2626,color:#111827;
    class ORCH,PLAN,BO,AGY,VER,VC,TEST,TEST_BUILD,VC_EXEC agent;
    class ENTRY,PLAN_GATE,PLAN_AMB,APPROVE,TASK_RES,BUILD_OK,BUILD_FAIL_ASK,UI_DEC,VER_RES,VER_BLOCK_ASK,VER_FAIL_ASK,COMMIT_ASK,VC_GATE,TEST_SCOPE decision;
    class PLAN_BLOCK,END_STOP,VC_BLOCK stop;
```

## Lectura fiel del flujo

- **`orchestrator`** es el único coordinador principal (`mainAgent: true`, `subagent: false`): no inspecciona código, no escribe planes ni edita archivos del proyecto (solo inicializa `<artifact-dir>/workers-status.md`). Coordina a `planner`, `build-orquestor-cli`, `verifier` y `version-control`, y vigila demoras sin respuesta mediante un watchdog (`schedule` de `300s`/`780s` + `manage_subagents`).
- **`planner`** exige pre-flight con `rag-json` (o `project-mapper-simple` como fallback solo si `rag-json` no está disponible y el mapa tiene `<= 150` archivos y `<= 40 KB`); si no, aborta con `🚫 BLOCKED`. Divide el plan en tareas con `Writable files` disjuntos, `Depends on`, `Complexity`, `Commit` y `UI Verification`. Ante fallos de build o de `verifier`, hace **re-planificación incremental** sobre los archivos ya modificados.
- **`build-orquestor-cli`** (`model: flash`) nunca edita código directamente: lanza hasta 5 workers `agy` CLI en paralelo (`--sandbox`, `--output-format json`) para tareas independientes, vigila progreso re-armando `schedule` (`600s`) + `manage_task` mientras queden workers corriendo, reintenta una vez en `FAILED` con un modelo superior y solo ejecuta `Final Checks` si todas las tareas terminan `✅ DONE`.
- **`verifier`** valida flujos web/UI en vivo con `playwright-cli` (`playwright-cli.cmd` en PowerShell de Windows, sesión `-s=verify`), revisando `snapshot`, `console` y `requests`, guardando capturas en `<artifact-dir>` y cerrando siempre sesión y servidor al finalizar. Es de solo lectura sobre el código del repositorio y distingue `FAILED` (re-planificable en `planner` con tope de 1 ciclo por defecto) de `BLOCKED` (problema de entorno/servidor que resuelve el usuario).
- **`version-control`** (`control-versiones.md`, `model: flash_lite`) solo actúa tras aprobación explícita del usuario y recibe un manifiesto `COMMITS` + `PUSH`. Bloquea si detecta archivos sensibles o cambios ya en staging (`git diff --cached --name-only`).
- **`test`** es un agente independiente (no forma parte del pipeline de `orchestrator`) especializado en diseñar, configurar y ejecutar suites permanentes en `test/unit-test/`, `test/e2e/` (`playwright@latest`) y `test/results/`, apoyado en `project-mapper-simple`, `rag-json` y el MCP `ui-skills`.

## Fuentes

- `general/gemini/.gemini/config/agents/orchestrator.md`
- `general/gemini/.gemini/config/agents/planner.md`
- `general/gemini/.gemini/config/agents/build-orquestor-cli.md`
- `general/gemini/.gemini/config/agents/verifier.md`
- `general/gemini/.gemini/config/agents/control-versiones.md`
- `general/gemini/.gemini/config/agents/test.md`
