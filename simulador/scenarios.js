// Escenarios Golden Suite y esquema base compatible con futuro runner CLI (Opción A)
(function (global) {
  'use strict';

  function clone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  const DEFAULT_TASKS = [
    {
      id: 't1',
      dependsOn: [],
      complexity: 'low',
      objective: 'Crear esquema y helpers de validación de sesión',
      writableFiles: ['src/auth/schema.ts'],
      commit: 'feat(auth): add session validation schema',
      behavior: 'DONE', // DONE | FAILED_ONCE | FAILED_TWICE | BLOCKED | OUT_OF_SCOPE | STALL
      checks: 'npm test -- schema'
    },
    {
      id: 't2',
      dependsOn: [],
      complexity: 'medium',
      objective: 'Implementar formulario de login en UI',
      writableFiles: ['src/components/LoginForm.tsx'],
      commit: 'feat(ui): build login form component',
      behavior: 'DONE',
      checks: 'npm test -- LoginForm'
    },
    {
      id: 't3',
      dependsOn: ['t1', 't2'],
      complexity: 'high',
      objective: 'Conectar ruta /login con manejo de sesión y redirección',
      writableFiles: ['src/pages/login.tsx'],
      commit: 'feat(login): wire login page with session flow',
      behavior: 'DONE',
      checks: 'npm test -- login'
    }
  ];

  const BASE_CONFIG = {
    schemaVersion: '1.0',
    request: 'Implementar pantalla de login con validación y redirección al dashboard',
    uiVerification: 'web', // 'web' | 'none'
    uiTarget: 'http://localhost:3000/login',
    interactiveUser: true,
    planner: {
      ragJsonAvailable: true,
      projectMapperAvailable: true,
      mapFilesCount: 48,
      mapSizeKb: 18,
      hasCriticalAmbiguity: false,
      clarifyingQuestion: '¿La sesión debe persistir en cookie HttpOnly o en localStorage?',
      clarifyingAnswer: 'Cookie HttpOnly con expiración de 7 días.'
    },
    build: {
      agyAvailable: true,
      finalChecksResult: 'passed', // 'passed' | 'failed'
      watchdogTimeoutTriggered: false
    },
    verifier: {
      firstRunStatus: 'VERIFIED', // 'VERIFIED' | 'FAILED' | 'BLOCKED'
      secondRunStatus: 'VERIFIED', // usado tras re-run o re-plan
      failReason: 'Console: TypeError reading user.name; Network: POST /api/login -> 500',
      blockedReason: 'playwright-cli / dev server no responde en puerto 3000 (ECONNREFUSED)'
    },
    versionControl: {
      preCheck: 'clean', // 'clean' | 'sensitive_file' | 'pre_staged'
      commitBehavior: 'ok', // 'ok' | 'error_mid_sequence'
      pushBehavior: 'ok' // 'ok' | 'no_upstream_ok' | 'detached_head' | 'push_error'
    },
    userScript: {
      approvePlan: 'approve', // 'approve' | 'request_change'
      onBuildFailure: 'Retry failed tasks',
      postBuildOrder: 'Verifier primero (Recomendado)',
      onVerifierBlocked: 'Re-run verifier',
      onVerifierFailed: 'Re-plan with planner',
      commitAction: 'Commit and push',
      postVcVerifier: 'Ejecutar verifier ahora (Recomendado)'
    },
    tasks: clone(DEFAULT_TASKS)
  };

  function makeScenario(id, name, badge, summary, overrides) {
    const cfg = clone(BASE_CONFIG);
    if (overrides.request !== undefined) cfg.request = overrides.request;
    if (overrides.uiVerification !== undefined) cfg.uiVerification = overrides.uiVerification;
    if (overrides.interactiveUser !== undefined) cfg.interactiveUser = overrides.interactiveUser;
    if (overrides.planner) Object.assign(cfg.planner, overrides.planner);
    if (overrides.build) Object.assign(cfg.build, overrides.build);
    if (overrides.verifier) Object.assign(cfg.verifier, overrides.verifier);
    if (overrides.versionControl) Object.assign(cfg.versionControl, overrides.versionControl);
    if (overrides.userScript) Object.assign(cfg.userScript, overrides.userScript);
    if (overrides.tasks) cfg.tasks = clone(overrides.tasks);
    return { id, name, badge, summary, config: cfg };
  }

  const SIM_SCENARIOS = [
    makeScenario(
      'happy-ui',
      '1. Happy Path con UI (Verifier primero)',
      'OK',
      'Wave 1 paralela (t1 + t2) → Wave 2 (t3) → Final Checks → Verifier VERIFIED → Version Control Commit & Push.',
      {}
    ),
    makeScenario(
      'planner-blocked',
      '2. Planner Hard Stop (>150 archivos sin rag-json)',
      'BLOCKED',
      'rag-json falla y el mapa supera 150 archivos / 40 KB. Planner debe abortar con 🚫 BLOCKED sin usar grep/find.',
      {
        planner: {
          ragJsonAvailable: false,
          projectMapperAvailable: true,
          mapFilesCount: 240,
          mapSizeKb: 68
        }
      }
    ),
    makeScenario(
      'clarify-and-retry',
      '3. Clarificación + Worker FAILED x1 (Retry escalado)',
      'RETRY',
      'Planner pide aclaración al usuario, t2 falla en 1.º intento y build-orquestor-cli reintenta una vez con gemini-4-argon-low.',
      {
        planner: { hasCriticalAmbiguity: true },
        tasks: DEFAULT_TASKS.map(t => t.id === 't2' ? { ...t, behavior: 'FAILED_ONCE' } : t)
      }
    ),
    makeScenario(
      'cascade-skip',
      '4. FAILED x2 en t1 → Cascada SKIPPED',
      'FAIL',
      't1 falla dos veces. t2 (paralela) completa, pero t3 (dependiente) queda ⏭️ SKIPPED y Final Checks se omiten.',
      {
        userScript: { onBuildFailure: 'Stop here' },
        tasks: DEFAULT_TASKS.map(t => t.id === 't1' ? { ...t, behavior: 'FAILED_TWICE' } : t)
      }
    ),
    makeScenario(
      'watchdog-stall',
      '5. Watchdog Timeout en Worker (600s)',
      'WATCHDOG',
      't2 queda colgado sin progreso; el timer de 600s dispara manage_task(kill) y aplica la política de retry FAILED.',
      {
        build: { watchdogTimeoutTriggered: true },
        tasks: DEFAULT_TASKS.map(t => t.id === 't2' ? { ...t, behavior: 'STALL' } : t)
      }
    ),
    makeScenario(
      'commit-first-replan',
      '6. Commit primero → Verifier FAILED → Re-plan delta',
      'DELTA',
      'El usuario commitea t1..t3 primero; verifier falla; planner genera t4 (fix); el 2.º commit solo incluye t4 gracias a committedTasks.',
      {
        verifier: { firstRunStatus: 'FAILED', secondRunStatus: 'VERIFIED' },
        userScript: {
          postBuildOrder: 'Control-versiones primero',
          postVcVerifier: 'Ejecutar verifier ahora (Recomendado)',
          onVerifierFailed: 'Re-plan with planner',
          commitAction: 'Commit and push'
        }
      }
    ),
    makeScenario(
      'vc-blocked-env',
      '7. Version Control BLOCKED (.env / staging sucio)',
      'SEC',
      'Flujo sin UI donde una tarea intenta incluir .env; version-control bloquea el commit antes de ejecutar git add.',
      {
        uiVerification: 'none',
        versionControl: { preCheck: 'sensitive_file' },
        tasks: [
          {
            id: 't1',
            dependsOn: [],
            complexity: 'low',
            objective: 'Actualizar configuración de entorno local',
            writableFiles: ['.env', 'src/config.ts'],
            commit: 'chore(env): update local configuration',
            behavior: 'DONE',
            checks: 'npm test -- config'
          }
        ]
      }
    )
  ];

  function validateScenarioConfig(raw) {
    const errors = [];
    if (!raw || typeof raw !== 'object') {
      return { valid: false, errors: ['El JSON raíz debe ser un objeto.'] };
    }
    if (!Array.isArray(raw.tasks) || raw.tasks.length === 0) {
      errors.push('Se requiere al menos una tarea en "tasks".');
    } else {
      const ids = new Set();
      raw.tasks.forEach((t, idx) => {
        if (!t.id) errors.push(`Tarea #${idx + 1} sin "id".`);
        if (ids.has(t.id)) errors.push(`ID duplicado: ${t.id}.`);
        ids.add(t.id);
        if (!Array.isArray(t.writableFiles) || t.writableFiles.length === 0) {
          errors.push(`Tarea ${t.id || idx + 1} requiere "writableFiles".`);
        }
      });
      // Detectar dependencias inexistentes
      raw.tasks.forEach(t => {
        (t.dependsOn || []).forEach(dep => {
          if (!ids.has(dep)) errors.push(`Tarea ${t.id} depende de "${dep}" inexistente.`);
        });
      });
    }
    return { valid: errors.length === 0, errors };
  }

  global.SIM_SCENARIOS = SIM_SCENARIOS;
  global.SIM_BASE_CONFIG = BASE_CONFIG;
  global.validateScenarioConfig = validateScenarioConfig;
})(window);
