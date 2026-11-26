// Motor de simulación paso a paso fiel a general/gemini/.gemini/config/agents_linux/
(function (global) {
  'use strict';

  function clone(v) {
    return JSON.parse(JSON.stringify(v));
  }

  function modelForComplexity(complexity, isRetry) {
    if (isRetry) return 'gemini-4-argon-low';
    if (complexity === 'low') return 'gemini-4-hydrogen-low';
    if (complexity === 'high') return 'gemini-4-argon-low';
    return 'gemini-4-hydrogen-medium';
  }

  class AgentSimEngine {
    constructor(config) {
      this.config = clone(config);
      this.reset();
    }

    reset() {
      this.stepCount = 0;
      this.virtualSeconds = 0;
      this.status = 'IDLE'; // IDLE | RUNNING | WAITING_USER | DONE | STOPPED | BLOCKED
      this.activeNode = 'user';
      this.activeEdge = null;
      this.phase = 'START';

      // Estado interno fiel a orchestrator.md y build-orquestor-cli.md
      this.committedTasks = [];
      this.verifierDone = false;
      this.replanCycles = 0;
      this.verifierRuns = 0;
      this.activeWatchdogs = []; // { id, owner, target, durationSec }
      this.dirtyFiles = [];
      this.outOfScopeFiles = [];
      this.planTasks = [];
      this.taskStates = {}; // id -> { status, attempts, model, files, checks, blockers, workerReport }
      this.finalChecks = '⏳ PENDING';
      this.pendingQuestion = null; // { id, title, options, handler }
      this.nextAction = null;

      this.messages = []; // Trace completo exportable a trace.json
      this.invariants = [];
      this._initInvariants();
    }

    _initInvariants() {
      this.invariants = [
        { id: 'disjoint-writable', label: 'Waves paralelas con writableFiles disjuntos', status: 'ok', detail: 'Sin verificar aún' },
        { id: 'no-retry-blocked', label: 'Sin reintentos en workers BLOCKED', status: 'ok', detail: 'Cumplido' },
        { id: 'single-retry-failed', label: 'Máx. 1 retry escalado en workers FAILED', status: 'ok', detail: 'Cumplido' },
        { id: 'skip-final-on-fail', label: 'Final Checks omitido si hay FAILED/BLOCKED', status: 'ok', detail: 'Cumplido' },
        { id: 'no-commit-unapproved', label: 'Nunca commitear sin aprobación explícita', status: 'ok', detail: 'Cumplido' },
        { id: 'blocked-no-replan', label: 'Verifier BLOCKED no reenvía a planner', status: 'ok', detail: 'Cumplido' },
        { id: 'replan-cap', label: 'Tope de 1 ciclo de re-plan por verifier', status: 'ok', detail: '0/1 usados' },
        { id: 'delta-commits', label: 'committedTasks excluye tareas ya commiteadas', status: 'ok', detail: 'Sin commits aún' }
      ];
    }

    _setInvariant(id, status, detail) {
      const inv = this.invariants.find(i => i.id === id);
      if (inv) {
        inv.status = status;
        inv.detail = detail;
      }
    }

    _log(from, to, kind, summary, payload, dtSec) {
      if (dtSec) this.virtualSeconds += dtSec;
      this.stepCount += 1;
      const entry = {
        step: this.stepCount,
        t: this.virtualSeconds,
        from,
        to,
        kind, // invoke | message | ask | schedule | tool | report | artifact
        summary,
        payload: payload || ''
      };
      this.messages.push(entry);
      return entry;
    }

    _armWatchdog(owner, target, durationSec) {
      this.activeWatchdogs = this.activeWatchdogs.filter(w => !(w.owner === owner && w.target === target));
      this.activeWatchdogs.push({ owner, target, durationSec });
      this._log(owner, 'runtime', 'schedule', `Timer watchdog ${durationSec}s → ${target}`, `schedule(DurationSeconds=${durationSec}, target=${target})`, 1);
    }

    _cancelWatchdog(owner, target) {
      this.activeWatchdogs = this.activeWatchdogs.filter(w => !(w.owner === owner && (target === '*' || w.target === target)));
    }

    getWorkersStatusMarkdown() {
      if (!this.planTasks.length) {
        return '# AGY CLI Workers Status\n\n_Todavía no se inicializó el plan._';
      }
      const mermaidLines = ['flowchart LR'];
      this.planTasks.forEach(t => {
        const st = this.taskStates[t.id]?.status || '⏳ PENDING';
        if (!t.dependsOn || t.dependsOn.length === 0) {
          mermaidLines.push(`  ${t.id}["${t.id}: ${st}"]`);
        } else {
          t.dependsOn.forEach(d => {
            const dst = this.taskStates[d]?.status || '⏳ PENDING';
            mermaidLines.push(`  ${d}["${d}: ${dst}"] --> ${t.id}["${t.id}: ${st}"]`);
          });
        }
      });

      const rows = this.planTasks.map(t => {
        const st = this.taskStates[t.id] || { status: '⏳ PENDING', checks: '-' };
        const deps = t.dependsOn?.length ? t.dependsOn.join(', ') : 'none';
        const files = (t.writableFiles || []).map(f => `\`${f}\``).join(', ');
        return `| \`${t.id}\` | \`${deps}\` | ${st.status} | ${files} | ${st.checks || '-'} |`;
      });

      return [
        '# AGY CLI Workers Status',
        '',
        '```mermaid',
        ...mermaidLines,
        '```',
        '',
        '| Task | Depends on | Status | Writable Files | Checks |',
        '|---|---|---|---|---|',
        ...rows,
        '',
        `**Final Checks:** ${this.finalChecks}`
      ].join('\n');
    }

    _askUser(title, options, handler, scriptKey) {
      this.status = 'WAITING_USER';
      this.activeNode = 'user';
      this.activeEdge = 'orchestrator->user';
      this._log('orchestrator', 'user', 'ask', `ask_question: ${title}`, `Opciones:\n- ${options.join('\n- ')}`, 1);
      if (!this.config.interactiveUser) {
        const autoChoice = this._pickAutoChoice(options, scriptKey);
        this.pendingQuestion = { title, options, handler };
        this.answerQuestion(autoChoice);
        return;
      }
      this.pendingQuestion = { title, options, handler };
    }

    _pickAutoChoice(options, scriptKey) {
      const s = this.config.userScript || {};
      if (scriptKey) {
        const mapped = scriptKey === 'approvePlan'
          ? (s.approvePlan === 'request_change' ? 'Pedir cambios al plan' : 'Aprobar plan')
          : s[scriptKey];
        if (mapped && options.includes(mapped)) return mapped;
      }
      return options[0];
    }

    answerQuestion(choice) {
      if (!this.pendingQuestion) return;
      const { handler } = this.pendingQuestion;
      this.pendingQuestion = null;
      this.status = 'RUNNING';
      this._log('user', 'orchestrator', 'message', `Respuesta: ${choice}`, choice, 2);
      handler(choice);
    }

    step() {
      if (this.status === 'DONE' || this.status === 'STOPPED' || this.status === 'BLOCKED') {
        return false;
      }
      if (this.status === 'WAITING_USER') {
        return false;
      }
      if (this.status === 'IDLE') {
        this.status = 'RUNNING';
        this.phase = 'USER_REQUEST';
      }

      switch (this.phase) {
        case 'USER_REQUEST':
          this._doUserRequest();
          break;
        case 'PLANNER_DISCOVERY':
          this._doPlannerDiscovery();
          break;
        case 'PLANNER_RESULT':
          this._doPlannerResult();
          break;
        case 'INIT_BUILD':
          this._doInitBuild();
          break;
        case 'BUILD_WAVE':
          this._doBuildWave();
          break;
        case 'BUILD_FINAL_CHECKS':
          this._doFinalChecks();
          break;
        case 'POST_BUILD_ROUTE':
          this._doPostBuildRoute();
          break;
        case 'VERIFIER_PREFLIGHT':
          this._doVerifierRun();
          break;
        case 'VC_EXECUTE':
          this._doVersionControl();
          break;
        default:
          this.status = 'DONE';
      }
      return true;
    }

    _doUserRequest() {
      this.activeNode = 'orchestrator';
      this.activeEdge = 'user->orchestrator';
      this._log('user', 'orchestrator', 'message', 'Solicitud recibida', this.config.request, 1);
      this.activeEdge = 'orchestrator->planner';
      this._log('orchestrator', 'planner', 'invoke', 'invoke_subagent(planner, model=inherit)', `Prompt: Planificar "${this.config.request}"`, 1);
      this._armWatchdog('orchestrator', 'planner', 300);
      this.activeNode = 'planner';
      this.phase = 'PLANNER_DISCOVERY';
    }

    _doPlannerDiscovery() {
      const p = this.config.planner;
      this.activeNode = 'planner';
      this.activeEdge = 'orchestrator->planner';

      if (p.ragJsonAvailable) {
        this._log('planner', 'planner', 'tool', 'rag-json query exitosa', `mapFiles=${p.mapFilesCount}, size=${p.mapSizeKb}KB`, 3);
        this.phase = 'PLANNER_RESULT';
        return;
      }

      const withinLimit = p.mapFilesCount <= 150 && p.mapSizeKb <= 40;
      if (p.projectMapperAvailable && withinLimit) {
        this._log('planner', 'planner', 'tool', 'rag-json no disponible → fallback project-mapper-simple OK', `${p.mapFilesCount} archivos (<=150), ${p.mapSizeKb} KB (<=40KB)`, 4);
        this.phase = 'PLANNER_RESULT';
        return;
      }

      this._cancelWatchdog('orchestrator', 'planner');
      const reason = !p.projectMapperAvailable
        ? 'rag-json y project-mapper-simple no ejecutables'
        : `rag-json falló y el mapa excede umbral (${p.mapFilesCount} archivos / ${p.mapSizeKb} KB > 150 / 40 KB)`;
      this._log('planner', 'orchestrator', 'report', '🚫 BLOCKED (Hard Stop Rule)', `🚫 BLOCKED: Execution stopped because required skills (rag-json / project-mapper-simple) could not be used safely. Cause: ${reason}.`, 2);
      this.activeNode = 'orchestrator';
      this.activeEdge = 'planner->orchestrator';
      this.status = 'BLOCKED';
    }

    _doPlannerResult() {
      const p = this.config.planner;
      this._cancelWatchdog('orchestrator', 'planner');

      if (p.hasCriticalAmbiguity && !this._clarifiedOnce) {
        this._clarifiedOnce = true;
        this.activeNode = 'orchestrator';
        this.activeEdge = 'planner->orchestrator';
        this._log('planner', 'orchestrator', 'report', 'Preguntas de aclaración', p.clarifyingQuestion, 2);
        this._askUser(
          `Planner necesita aclaración: ${p.clarifyingQuestion}`,
          [p.clarifyingAnswer, 'Usar opción estándar por defecto'],
          (ans) => {
            this._log('orchestrator', 'planner', 'message', 'send_message(planner) con respuesta', `Respuesta del usuario: ${ans}`, 1);
            this._armWatchdog('orchestrator', 'planner', 300);
            this.activeNode = 'planner';
            this.phase = 'PLANNER_RESULT';
          }
        );
        return;
      }

      // Construir plan (inicial o incremental)
      if (!this.planTasks.length) {
        this.planTasks = clone(this.config.tasks);
      }
      // Validar disjoint writable files en tareas paralelas (Depends on igual / none)
      this._checkParallelDisjointInvariant();

      const planSummary = this.planTasks.map(t =>
        `- ${t.id} (deps: ${t.dependsOn.length ? t.dependsOn.join(',') : 'none'}, complexity: ${t.complexity}): ${t.writableFiles.join(', ')}`
      ).join('\n');

      this.activeNode = 'orchestrator';
      this.activeEdge = 'planner->orchestrator';
      this._log('planner', 'orchestrator', 'report', `Plan listo (${this.planTasks.length} tareas, UI: ${this.config.uiVerification})`, planSummary, 3);

      this._askUser(
        `¿Aprobás el plan de ${this.planTasks.length} tareas (UI Verification: ${this.config.uiVerification})?`,
        ['Aprobar plan', 'Pedir cambios al plan', 'Cancelar'],
        (choice) => {
          if (choice === 'Aprobar plan') {
            this.phase = 'INIT_BUILD';
          } else if (choice === 'Pedir cambios al plan') {
            this._log('orchestrator', 'planner', 'message', 'send_message(planner): ajustar plan', 'Usuario solicitó ajustes menores en el plan.', 1);
            this.activeNode = 'planner';
            this.phase = 'PLANNER_RESULT';
          } else {
            this.status = 'STOPPED';
            this._log('orchestrator', 'user', 'report', 'Cancelado por el usuario antes de ejecutar', '', 1);
          }
        },
        'approvePlan'
      );
    }

    _checkParallelDisjointInvariant() {
      const roots = this.planTasks.filter(t =>
        (!t.dependsOn || t.dependsOn.length === 0) &&
        this.taskStates[t.id]?.status !== '✅ DONE'
      );
      const seen = new Map();
      const collisions = [];
      roots.forEach(t => {
        (t.writableFiles || []).forEach(f => {
          if (seen.has(f)) collisions.push(`${f} (${seen.get(f)} & ${t.id})`);
          seen.set(f, t.id);
        });
      });
      if (collisions.length) {
        this._setInvariant('disjoint-writable', 'warn', `Colisión en paralelas: ${collisions.join(', ')} (deben serializarse)`);
      } else {
        this._setInvariant('disjoint-writable', 'ok', 'Todas las tareas paralelas tienen archivos disjuntos');
      }
    }

    _doInitBuild() {
      this.activeNode = 'build-orquestor-cli';
      this.activeEdge = 'orchestrator->build';
      this.planTasks.forEach(t => {
        if (!this.taskStates[t.id]) {
          this.taskStates[t.id] = { status: '⏳ PENDING', attempts: 0, model: '-', files: [], checks: '-', blockers: 'none' };
        }
      });
      this.finalChecks = '⏳ PENDING';
      this._log('orchestrator', 'build-orquestor-cli', 'artifact', 'Inicializa <artifact-dir>/workers-status.md', this.getWorkersStatusMarkdown(), 1);
      this._log('orchestrator', 'build-orquestor-cli', 'invoke', 'invoke_subagent(build-orquestor-cli, model=flash)', 'Plan aprobado + Status Artifact Path', 1);
      this._armWatchdog('orchestrator', 'build-orquestor-cli', 780);
      this.phase = 'BUILD_WAVE';
    }

    _doBuildWave() {
      this.activeNode = 'workers';
      this.activeEdge = 'build->workers';

      if (!this.config.build.agyAvailable) {
        this.planTasks.forEach(t => {
          if (this.taskStates[t.id].status === '⏳ PENDING') {
            this.taskStates[t.id].status = '🚫 BLOCKED';
            this.taskStates[t.id].blockers = 'agy CLI no disponible en PATH';
          }
        });
        this._log('build-orquestor-cli', 'build-orquestor-cli', 'report', 'agy no pudo iniciar → 🚫 BLOCKED sin retry', '', 1);
        this.phase = 'BUILD_FINAL_CHECKS';
        return;
      }

      // Marcar dependientes de FAILED o BLOCKED como SKIPPED
      let changedSkip = false;
      this.planTasks.forEach(t => {
        const st = this.taskStates[t.id];
        if (st.status === '⏳ PENDING' && t.dependsOn?.length) {
          const badDep = t.dependsOn.find(d => ['❌ FAILED', '🚫 BLOCKED', '⏭️ SKIPPED'].includes(this.taskStates[d]?.status));
          if (badDep) {
            st.status = '⏭️ SKIPPED';
            st.checks = 'skipped (upstream failed)';
            changedSkip = true;
          }
        }
      });
      if (changedSkip) {
        this._log('build-orquestor-cli', 'build-orquestor-cli', 'artifact', 'Dependientes marcados ⏭️ SKIPPED', this.getWorkersStatusMarkdown(), 1);
      }

      // Buscar tareas listas (PENDING y todas sus dependencias DONE) - máx 5
      const ready = this.planTasks.filter(t => {
        const st = this.taskStates[t.id];
        if (st.status !== '⏳ PENDING') return false;
        return (t.dependsOn || []).every(d => this.taskStates[d]?.status === '✅ DONE');
      }).slice(0, 5);

      if (ready.length === 0) {
        this.phase = 'BUILD_FINAL_CHECKS';
        return;
      }

      // Lanzar wave
      ready.forEach(t => {
        this.taskStates[t.id].status = '🔄 RUNNING';
      });
      this._armWatchdog('build-orquestor-cli', 'workers-wave', 600);
      this._log(
        'build-orquestor-cli',
        'agy-workers',
        'invoke',
        `Lanza wave paralela (${ready.map(t => t.id).join(', ')}) con --sandbox --output-format json`,
        ready.map(t => `${t.id} → --model ${modelForComplexity(t.complexity, false)}`).join('\n'),
        2
      );

      // Resolver cada worker de la wave (incluyendo retry único en FAILED)
      ready.forEach(t => this._resolveWorker(t));

      this._cancelWatchdog('build-orquestor-cli', 'workers-wave');
      this._log('build-orquestor-cli', 'build-orquestor-cli', 'artifact', 'Actualiza workers-status.md tras wave', this.getWorkersStatusMarkdown(), 1);

      // ¿Quedan tareas PENDING?
      const stillPending = this.planTasks.some(t => this.taskStates[t.id].status === '⏳ PENDING');
      if (!stillPending) {
        this.phase = 'BUILD_FINAL_CHECKS';
      }
    }

    _resolveWorker(task) {
      const st = this.taskStates[task.id];
      st.attempts += 1;
      const beh = task.behavior || 'DONE';
      st.model = modelForComplexity(task.complexity, false);

      if (beh === 'STALL' || (this.config.build.watchdogTimeoutTriggered && beh === 'STALL')) {
        this._log('runtime', 'build-orquestor-cli', 'schedule', `Watchdog 600s disparado en ${task.id} → manage_task(kill)`, `Worker ${task.id} sin progreso reciente.`, 600);
        st.status = '❌ FAILED';
        st.checks = 'timeout (killed by watchdog)';
        this._retryWorker(task, 'Worker stalled and terminated after 600s watchdog.');
        return;
      }

      if (beh === 'BLOCKED') {
        st.status = '🚫 BLOCKED';
        st.checks = 'blocked';
        st.blockers = 'Dependencia o alcance insuficiente reportado por worker';
        this._log('agy-workers', 'build-orquestor-cli', 'report', `${task.id} → 🚫 BLOCKED (no reintenta)`, `## Worker report\n- Status: BLOCKED\n- Task ID: ${task.id}`, 12);
        return;
      }

      if (beh === 'OUT_OF_SCOPE') {
        st.files = [...task.writableFiles, 'package.json'];
        this.outOfScopeFiles.push('package.json');
        this.dirtyFiles.push(...st.files);
        st.status = '❌ FAILED';
        st.checks = 'scope violation (edited package.json outside WRITABLE FILES)';
        this._log('agy-workers', 'build-orquestor-cli', 'report', `${task.id} modificó archivo fuera de WRITABLE FILES → ❌ FAILED`, `git diff --name-only detectó package.json`, 15);
        return;
      }

      if (beh === 'FAILED_ONCE' || beh === 'FAILED_TWICE') {
        st.checks = `${task.checks} -> FAIL`;
        this._log('agy-workers', 'build-orquestor-cli', 'report', `${task.id} intento #1 → ❌ FAILED`, `Error en ${task.checks}`, 18);
        this._retryWorker(task, `1st attempt failed check: ${task.checks}`, beh === 'FAILED_TWICE');
        return;
      }

      // DONE normal
      st.status = '✅ DONE';
      st.files = [...task.writableFiles];
      st.checks = `${task.checks} -> passed`;
      this.dirtyFiles.push(...st.files);
      this._log('agy-workers', 'build-orquestor-cli', 'report', `${task.id} → ✅ DONE (${st.model})`, `Files: ${st.files.join(', ')}\nChecks: ${st.checks}`, 20);
    }

    _retryWorker(task, prevErr, forceSecondFail = false) {
      const st = this.taskStates[task.id];
      st.attempts += 1;
      const retryModel = modelForComplexity(task.complexity, true);
      st.model = retryModel;
      this._log('build-orquestor-cli', 'agy-workers', 'invoke', `Retry único ${task.id} escalado a ${retryModel}`, `CONTEXT += ${prevErr}`, 2);

      if (forceSecondFail) {
        st.status = '❌ FAILED';
        st.checks = `${task.checks} -> FAIL (x2)`;
        st.files = [...task.writableFiles]; // parcial/dirty
        this.dirtyFiles.push(...st.files);
        this._log('agy-workers', 'build-orquestor-cli', 'report', `${task.id} intento #2 → ❌ FAILED definitivo`, `Retry falló con ${retryModel}`, 22);
      } else {
        st.status = '✅ DONE';
        st.checks = `${task.checks} -> passed (retry)`;
        st.files = [...task.writableFiles];
        this.dirtyFiles.push(...st.files);
        this._log('agy-workers', 'build-orquestor-cli', 'report', `${task.id} retry → ✅ DONE (${retryModel})`, `Files: ${st.files.join(', ')}`, 18);
      }
    }

    _doFinalChecks() {
      this._cancelWatchdog('orchestrator', 'build-orquestor-cli');
      this.activeNode = 'orchestrator';
      this.activeEdge = 'build->orchestrator';

      const anyBad = this.planTasks.some(t => this.taskStates[t.id].status !== '✅ DONE');
      if (anyBad) {
        this.finalChecks = '⏭️ SKIPPED (upstream task failed/blocked)';
        this._log('build-orquestor-cli', 'orchestrator', 'report', 'Reporte Build con fallos (Final Checks omitido)', this.getWorkersStatusMarkdown(), 2);
        this._askUser(
          'Fallaron tareas en build-orquestor-cli. ¿Cómo querés continuar?',
          ['Retry failed tasks', 'Re-plan with planner', 'Stop here'],
          (choice) => {
            if (choice === 'Retry failed tasks') {
              this.planTasks.forEach(t => {
                if (['❌ FAILED', '⏭️ SKIPPED'].includes(this.taskStates[t.id].status)) {
                  this.taskStates[t.id].status = '⏳ PENDING';
                  if (t.behavior === 'FAILED_TWICE') t.behavior = 'DONE';
                }
              });
              this.phase = 'INIT_BUILD';
            } else if (choice === 'Re-plan with planner') {
              this.planTasks.forEach(t => {
                if (this.taskStates[t.id].status !== '✅ DONE') {
                  t.behavior = 'DONE';
                  this.taskStates[t.id].status = '⏳ PENDING';
                }
              });
              this.activeNode = 'planner';
              this.phase = 'PLANNER_RESULT';
            } else {
              this.status = 'STOPPED';
            }
          },
          'onBuildFailure'
        );
        return;
      }

      if (this.config.build.finalChecksResult === 'failed') {
        this.finalChecks = 'failed';
        this._log('build-orquestor-cli', 'orchestrator', 'report', 'Final Checks → failed', this.getWorkersStatusMarkdown(), 5);
        this._askUser(
          'Todas las tareas terminaron pero Final Checks falló. ¿Qué hacemos?',
          ['Re-plan with planner', 'Retry failed tasks', 'Stop here'],
          (choice) => {
            if (choice === 'Re-plan with planner') {
              this.config.build.finalChecksResult = 'passed';
              this.phase = 'PLANNER_RESULT';
            } else if (choice === 'Retry failed tasks') {
              this.config.build.finalChecksResult = 'passed';
              this.phase = 'BUILD_FINAL_CHECKS';
            } else {
              this.status = 'STOPPED';
            }
          },
          'onBuildFailure'
        );
        return;
      }

      this.finalChecks = 'passed';
      this._log('build-orquestor-cli', 'orchestrator', 'report', 'Build 100% ✅ DONE y Final Checks passed', this.getWorkersStatusMarkdown(), 5);
      this.phase = 'POST_BUILD_ROUTE';
    }

    _pendingCommitTasks() {
      return this.planTasks.filter(t => this.taskStates[t.id]?.status === '✅ DONE' && !this.committedTasks.includes(t.id));
    }

    _doPostBuildRoute() {
      this.activeNode = 'orchestrator';
      const pending = this._pendingCommitTasks();

      if (this.config.uiVerification === 'none') {
        this._log('orchestrator', 'orchestrator', 'message', 'UI Verification = none → salta directo a version-control', `Pendientes de commit: ${pending.map(t => t.id).join(', ')}`, 1);
        this._promptVersionControl();
        return;
      }

      const table = pending.map(t => `${t.id} → "${t.commit}" (${t.writableFiles.join(', ')})`).join('\n');
      this._askUser(
        `Build exitoso (${pending.length} tareas sin commitear). ¿Qué subagente invocamos primero?\n${table}`,
        ['Verifier primero (Recomendado)', 'Control-versiones primero', 'Finalizar sin verificar ni commitear'],
        (choice) => {
          if (choice === 'Verifier primero (Recomendado)') {
            this.phase = 'VERIFIER_PREFLIGHT';
          } else if (choice === 'Control-versiones primero') {
            this.phase = 'VC_EXECUTE';
          } else {
            this.status = 'DONE';
            this._log('orchestrator', 'user', 'report', 'Finalizado sin verificar ni commitear', '', 1);
          }
        },
        'postBuildOrder'
      );
    }

    _doVerifierRun() {
      this.activeNode = 'verifier';
      this.activeEdge = 'orchestrator->verifier';
      this._log('orchestrator', 'verifier', 'invoke', 'invoke_subagent(verifier)', `URL: ${this.config.uiTarget}`, 1);
      this._armWatchdog('orchestrator', 'verifier', 300);

      this.verifierRuns += 1;
      const v = this.config.verifier;
      const outcome = this.verifierRuns === 1 ? v.firstRunStatus : v.secondRunStatus;

      this._log('verifier', 'verifier', 'tool', 'playwright-cli -s=verify open/snapshot/console/requests + cleanup', 'Close session & kill daemon server', 10);
      this._cancelWatchdog('orchestrator', 'verifier');
      this.verifierDone = true;
      this.activeNode = 'orchestrator';
      this.activeEdge = 'verifier->orchestrator';

      if (outcome === 'VERIFIED' || outcome === 'SKIPPED') {
        this._log('verifier', 'orchestrator', 'report', `STATUS: ${outcome}`, `URL_TESTED: ${this.config.uiTarget}\nERRORS: none`, 2);
        const pending = this._pendingCommitTasks();
        if (pending.length > 0) {
          this._promptVersionControl();
        } else {
          this.status = 'DONE';
          this._log('orchestrator', 'user', 'report', '✅ Todo verificado y ya commiteado. Flujo completo.', '', 1);
        }
        return;
      }

      if (outcome === 'BLOCKED') {
        this._log('verifier', 'orchestrator', 'report', 'STATUS: BLOCKED (entorno/server)', v.blockedReason, 2);
        const pending = this._pendingCommitTasks();
        const opts = pending.length
          ? ['Re-run verifier', 'Ignore and continue to commit', 'Stop here']
          : ['Re-run verifier', 'Stop here'];
        this._askUser(
          `Verifier BLOCKED (${v.blockedReason}). No se enruta a planner.`,
          opts,
          (choice) => {
            if (choice === 'Re-run verifier') {
              this.phase = 'VERIFIER_PREFLIGHT';
            } else if (choice === 'Ignore and continue to commit') {
              this._promptVersionControl();
            } else {
              this.status = 'STOPPED';
            }
          },
          'onVerifierBlocked'
        );
        return;
      }

      // FAILED
      this._log('verifier', 'orchestrator', 'report', 'STATUS: FAILED (UI/consola/red)', v.failReason, 2);
      const pending = this._pendingCommitTasks();
      const atCap = this.replanCycles >= 1;
      const opts = pending.length
        ? (atCap ? ['Stop here', 'Re-run verifier', 'Ignore and continue to commit'] : ['Re-plan with planner', 'Re-run verifier', 'Ignore and continue to commit', 'Stop here'])
        : (atCap ? ['Stop here', 'Re-run verifier'] : ['Re-plan with planner', 'Re-run verifier', 'Stop here']);

      this._askUser(
        atCap
          ? `Verifier volvió a dar FAILED tras el ciclo correctivo (tope 1/1 alcanzado). Se recomienda Stop here.`
          : `Verifier reportó FAILED (${v.failReason}). ¿Cómo proceder?`,
        opts,
        (choice) => {
          if (choice === 'Re-plan with planner') {
            this.replanCycles += 1;
            this._setInvariant('replan-cap', this.replanCycles <= 1 ? 'ok' : 'fail', `${this.replanCycles}/1 usados`);
            this.verifierDone = false;
            const fixId = `t${this.planTasks.length + 1}`;
            this.planTasks.push({
              id: fixId,
              dependsOn: [],
              complexity: 'medium',
              objective: 'Corregir fallo detectado por verifier en flujo UI',
              writableFiles: ['src/pages/login.tsx'],
              commit: 'fix(login): resolve runtime error reported by verifier',
              behavior: 'DONE',
              checks: 'npm test -- login'
            });
            this.taskStates[fixId] = { status: '⏳ PENDING', attempts: 0, model: '-', files: [], checks: '-', blockers: 'none' };
            this._log('orchestrator', 'planner', 'message', `Re-plan incremental enviado (committedTasks: ${this.committedTasks.join(',') || 'none'})`, `Nueva tarea delta: ${fixId}`, 2);
            this.activeNode = 'planner';
            this.phase = 'PLANNER_RESULT';
          } else if (choice === 'Re-run verifier') {
            this.phase = 'VERIFIER_PREFLIGHT';
          } else if (choice === 'Ignore and continue to commit') {
            this._promptVersionControl();
          } else {
            this.status = 'STOPPED';
          }
        },
        'onVerifierFailed'
      );
    }

    _promptVersionControl() {
      const pending = this._pendingCommitTasks();
      if (pending.length === 0) {
        this.status = 'DONE';
        this._log('orchestrator', 'user', 'report', 'Todas las tareas ya están commiteadas.', '', 1);
        return;
      }
      const summary = pending.map(t => `${t.id}: "${t.commit}" → ${t.writableFiles.join(', ')}`).join('\n');
      this._askUser(
        `Aprobar commits para tareas pendientes (${pending.map(t => t.id).join(', ')}):\n${summary}`,
        ['Commit and push', 'Commit only', 'Skip commit'],
        (choice) => {
          if (choice === 'Skip commit') {
            this.status = 'DONE';
            this._log('orchestrator', 'user', 'report', 'Commits omitidos por el usuario. Cambios quedan locales.', '', 1);
          } else {
            this._pendingPush = choice === 'Commit and push';
            this.phase = 'VC_EXECUTE';
          }
        },
        'commitAction'
      );
    }

    _doVersionControl() {
      const pending = this._pendingCommitTasks();
      if (pending.length === 0) {
        this.status = 'DONE';
        return;
      }
      // Si entró por "Control-versiones primero", igual debe pedir aprobación explícita de commit/push
      if (this._pendingPush === undefined) {
        this._promptVersionControl();
        return;
      }
      const pushYes = this._pendingPush;
      this._pendingPush = undefined;

      const manifest = [
        'COMMITS:',
        ...pending.map((t, i) => `${i + 1}. msg: "${t.commit}"   files: ${t.writableFiles.join(', ')}`),
        `PUSH: ${pushYes ? 'yes' : 'no'}`
      ].join('\n');

      this.activeNode = 'version-control';
      this.activeEdge = 'orchestrator->vc';
      this._log('orchestrator', 'version-control', 'invoke', 'invoke_subagent(version-control, model=flash_lite)', manifest, 1);
      this._armWatchdog('orchestrator', 'version-control', 300);

      const vc = this.config.versionControl;
      const hasSensitive = pending.some(t => t.writableFiles.some(f => /(^\.env|\.key$|\.pem$|secret|credential)/i.test(f)));

      if (vc.preCheck === 'sensitive_file' || hasSensitive) {
        this._cancelWatchdog('orchestrator', 'version-control');
        this._log('version-control', 'orchestrator', 'report', 'STATUS: BLOCKED (archivo sensible en manifiesto)', 'Detectado archivo sensible (.env / *.key / *secret*). Abortado antes de git add.', 2);
        this.activeNode = 'orchestrator';
        this.status = 'BLOCKED';
        return;
      }

      if (vc.preCheck === 'pre_staged') {
        this._cancelWatchdog('orchestrator', 'version-control');
        this._log('version-control', 'orchestrator', 'report', 'STATUS: BLOCKED (git diff --cached no vacío)', 'Hay archivos staged previos sin relación.', 2);
        this.activeNode = 'orchestrator';
        this.status = 'BLOCKED';
        return;
      }

      const created = [];
      for (let i = 0; i < pending.length; i++) {
        const t = pending[i];
        if (vc.commitBehavior === 'error_mid_sequence' && i === pending.length - 1 && pending.length > 1) {
          this.committedTasks.push(...created.map(c => c.id));
          this._cancelWatchdog('orchestrator', 'version-control');
          this._log('version-control', 'orchestrator', 'report', `STATUS: ERROR en commit #${i + 1} (${created.length} creados localmente)`, `COMMITS creados: ${created.map(c => c.hash).join(', ')}\nPUSHED: no`, 3);
          this.activeNode = 'orchestrator';
          this.status = 'STOPPED';
          return;
        }
        const hash = Math.random().toString(16).slice(2, 9);
        created.push({ id: t.id, hash, msg: t.commit });
        this.committedTasks.push(t.id);
      }

      this._setInvariant('delta-commits', 'ok', `committedTasks = [${this.committedTasks.join(', ')}]`);

      let pushed = 'no';
      let pushNote = 'none';
      if (pushYes) {
        if (vc.pushBehavior === 'detached_head') {
          this._cancelWatchdog('orchestrator', 'version-control');
          this._log('version-control', 'orchestrator', 'report', 'STATUS: ERROR (Detached HEAD; cannot push safely)', `COMMITS:\n${created.map(c => `${c.hash} ${c.msg}`).join('\n')}\nPUSHED: no`, 2);
          this.activeNode = 'orchestrator';
          this.status = 'STOPPED';
          return;
        }
        if (vc.pushBehavior === 'push_error') {
          this._cancelWatchdog('orchestrator', 'version-control');
          this._log('version-control', 'orchestrator', 'report', 'STATUS: ERROR (git push rejected: non-fast-forward)', `COMMITS creados localmente.\nPUSHED: no`, 2);
          this.activeNode = 'orchestrator';
          this.status = 'STOPPED';
          return;
        }
        pushed = 'yes';
        pushNote = vc.pushBehavior === 'no_upstream_ok' ? 'Ejecutó git push -u origin HEAD' : 'Ejecutó git push';
      }

      this._cancelWatchdog('orchestrator', 'version-control');
      this._log(
        'version-control',
        'orchestrator',
        'report',
        `STATUS: OK (${created.length} commits, PUSHED: ${pushed})`,
        `${created.map(c => `${c.hash} ${c.msg}`).join('\n')}\nNOTES: ${pushNote}`,
        4
      );
      this.activeNode = 'orchestrator';
      this.activeEdge = 'vc->orchestrator';

      if (this.config.uiVerification !== 'none' && !this.verifierDone) {
        this._askUser(
          'Commits completados. Aún no corrió verifier para el estado actual. ¿Ejecutarlo ahora?',
          ['Ejecutar verifier ahora (Recomendado)', 'Finalizar aquí'],
          (choice) => {
            if (choice === 'Ejecutar verifier ahora (Recomendado)') {
              this.phase = 'VERIFIER_PREFLIGHT';
            } else {
              this.status = 'DONE';
              this._log('orchestrator', 'user', 'report', 'Finalizado tras commit (sin verifier).', '', 1);
            }
          },
          'postVcVerifier'
        );
        return;
      }

      this.status = 'DONE';
      this._log('orchestrator', 'user', 'report', '✅ Ciclo completo finalizado con éxito.', `Commits: ${this.committedTasks.join(', ')}`, 1);
    }

    exportTrace() {
      return {
        exportedAt: new Date().toISOString(),
        schemaVersion: '1.0',
        finalStatus: this.status,
        virtualSeconds: this.virtualSeconds,
        committedTasks: this.committedTasks,
        verifierDone: this.verifierDone,
        replanCycles: this.replanCycles,
        invariants: this.invariants,
        config: this.config,
        events: this.messages
      };
    }
  }

  global.AgentSimEngine = AgentSimEngine;
})(window);
