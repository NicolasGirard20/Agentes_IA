# Flujo actual de agentes

Diagrama construido a partir de los archivos actuales en
`general/opencode/.opencode/agent/`.

```mermaid
flowchart TD
    IN([Solicitud del usuario]) --> ROUTE{Ruta de trabajo}

    ROUTE -->|Flujo especializado| PO[product-owner\nDefine alcance y requisitos]
    ROUTE -->|Tarea general| GEN[general\nAnaliza, busca, implementa o delega]
    ROUTE -->|Pruebas independientes| TEST[tester\nPrueba en .tester/tests/ e informa riesgos]

    PO --> PO_STATUS{Estado de requisitos}
    PO_STATUS -->|NEEDS_CLARIFICATION| ASK[Orquestador muestra preguntas]
    ASK --> ANSWER([Respuesta del usuario])
    ANSWER --> PO
    PO_STATUS -->|READY| PDR{Persistir PDR?}
    PDR -->|Sí, con aprobación| PO_PERSIST[product-owner\nActualiza PRODUCT_REQUIREMENTS.md]
    PDR -->|No| PLAN
    PO_PERSIST --> PLAN[planificador\nEjecuta project-mapper y analiza]

    GEN --> GEN_GIT{Necesita Git?}
    GEN_GIT -->|Solo lectura\nsegún general.md actual| GEN_READ[Ejecuta Git de lectura]
    GEN_GIT -->|Escritura, remoto o historial| ORCH_GIT[Informa al orquestador]
    GEN -->|No| GEN_WORK[Resuelve la tarea general]
    GEN_READ --> GEN_WORK
    GEN_WORK --> OUT([Resultado])

    TEST --> TEST_OUT[Reporte: APROBADO, APROBADO CON RIESGOS o FALLA]
    TEST_OUT --> OUT

    PROPOSAL([Propuesta de implementación]) --> BO[build-orquestor\nPlanifica y divide]
    BO --> BC[build-constructor\nConstruye la tarea asignada]
    BC --> BC_VERIFY[Verificaciones de cada tarea]
    BC_VERIFY --> OUT

    PLAN --> PLAN_OUT[Diagnóstico + plan + contexto]
    PLAN_OUT --> APPROVE{¿Usuario aprueba el plan?}
    APPROVE -->|No: pide cambios| PLAN
    APPROVE -->|Sí| ARCH_DEC{Decisión arquitectónica}

    ARCH_DEC -->|ARQUITECTO: NECESARIO| ARCH[arquitecto\nValida diseño y riesgos]
    ARCH_DEC -->|ARQUITECTO: NO_NECESARIO| SEARCH_DEC
    ARCH --> SEARCH_DEC{¿Hace falta investigación externa?}

    SEARCH_DEC -->|Sí: API, librería, best practices o trade-off actual| WEB[buscador\nInvestiga fuentes externas]
    SEARCH_DEC -->|No| BUILD
    WEB --> BUILD[constructor\nImplementa y ejecuta verificaciones]

    BUILD --> GIT_DEC{¿Se solicitó una acción Git?}

    GIT_DEC -->|Sí, o un agente la necesita| GIT[control-versiones\nInspecciona y ejecuta Git]
    GIT --> GIT_RISK{¿Comando Git riesgoso?}
    GIT_RISK -->|Sí| CONF[Consulta al usuario con comando y efecto]
    CONF -->|Confirma| GIT_EXEC[Ejecuta comando]
    CONF -->|No confirma| GIT_STOP[Detiene la operación]
    GIT_RISK -->|No| GIT_EXEC
    GIT_EXEC --> GIT_VERIFY[Verifica resultado con Git de lectura]
    GIT_VERIFY --> SYNTH
    GIT_STOP --> SYNTH
    GIT_DEC -->|No| SYNTH[Sintetiza resultado para el usuario]

    ORCH_GIT --> GIT
    SYNTH --> OUT

    classDef agent fill:#e8f1fb,stroke:#2563eb,color:#111827;
    classDef decision fill:#fff7ed,stroke:#ea580c,color:#111827;
    class PO,GEN,PLAN,ARCH,WEB,BUILD,TEST,GIT,PO_PERSIST,BO,BC agent;
    class ROUTE,PO_STATUS,PDR,GEN_GIT,APPROVE,ARCH_DEC,SEARCH_DEC,GIT_DEC,GIT_RISK decision;
```

## Lectura fiel del flujo

- `orquestador` coordina seis subagentes (`product-owner`, `planificador`,
  `arquitecto`, `buscador`, `constructor` y `control-versiones`) y no ejecuta
  comandos directamente.
- `product-owner` siempre precede a `planificador` en el flujo especializado.
- `planificador` exige `project-mapper` antes del análisis.
- El usuario debe aprobar el plan antes de arquitectura, búsqueda o construcción.
- `arquitecto` solo participa cuando el planificador marca
  `ARQUITECTO: NECESARIO`.
- `buscador` solo participa cuando se necesita información externa.
- `constructor` (`implementador.md`) implementa y verifica, pero no gestiona Git.
- `tester` es un agente primario independiente que valida la implementación en
  la carpeta aislada `.tester/tests/`; no forma parte del flujo del
  `orquestador`.
- `control-versiones` es el agente que puede ejecutar Git. Consulta al usuario
  antes de comandos que cambien índice, historial, ramas, archivos o remotos.
- `general` es un agente primario con una ruta independiente para tareas de
  análisis, implementación, diagnóstico y validación autónomas. Permite Git de
  lectura y bloquea Git de escritura.

## Fuentes

- `general/opencode/.opencode/agent/orquestador.md`
- `general/opencode/.opencode/agent/general.md`
- `general/opencode/.opencode/agent/product-owner.md`
- `general/opencode/.opencode/agent/planificador.md`
- `general/opencode/.opencode/agent/arquitecto.md`
- `general/opencode/.opencode/agent/buscador.md`
- `general/opencode/.opencode/agent/implementador.md`
- `general/opencode/.opencode/agent/build-orquestor.md`
- `general/opencode/.opencode/agent/build-constructor.md`
- `general/opencode/.opencode/agent/tester.md`
- `general/opencode/.opencode/agent/control-versiones.md`
