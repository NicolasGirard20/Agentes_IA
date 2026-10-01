# Propuestas

## Pendientes

### Recomendaciones de skills
- [ ] **Plantillas de prompts**: Biblioteca de templates parametrizables + variables y ejemplos; implementarlo como archivos .md/.json reutilizables.
- [ ] **Validador de prompts**: Reglas y sanitizadores (longitud, incoherencias, instrucciones peligrosas) que alerten antes de enviar.
- [ ] **Auto-refinador (iterative refinement)**: Genera y compara variantes de prompt, elige la mejor mediante métricas automáticas.
- [ ] **Banco de ejemplos (few-shot)**: Colección etiquetada de ejemplos por dominio/estilo para inserción dinámica en prompts.
- [ ] **Gestión de contexto y memoria**: Short/long-term memory, retriever vectorial (RAG) para incluir contexto relevante al prompt.
- [ ] **Composer dinámico de prompts**: Motor que arma prompts condicionales (bloques, bucles, ramificaciones) según meta/rol.
- [ ] **Evaluador automático**: Tests de calidad de salida (exactitud, coherencia, toxicidad) y dashboard de métricas.
- [ ] **Simulador de interacción agentica**: Entorno para simular pasos, rollouts y validar estrategias (útil para entrenar políticas).
- [ ] **Controlador meta (planner)**: Descompone objetivos en sub-tasks y orquesta agentes especializados (planner → worker → verifier).
- [ ] **Verificador de acciones (safety & verification)**: Revisión automática de resultados/acciones propuestas contra reglas y sandboxed execution.
- [ ] **Conectores multi-externos**: Skills para integrarse con web search, bases de datos, APIs y ejecutar código seguro.
- [ ] **Aprendizaje desde feedback**: Registro de feedback humano + ajuste de prompts/ejemplos y ranking de mejores estrategias.
- [x] **Ensamble agentico**: Orquestrador de múltiples agentes especializados (explorador, experto, revisor) que cooperan en una tarea.
- [x] **Agregar skill de terceros**: Ejemplo de github.com/w7panel/w7panel/tree/main/.opencode/skills.

### Plugins opencode
- [] *opendesign**: Herramienta de diseño para generar prototipos funcionales, interfaces, páginas web o presentaciones en archivos html.
     *Consideración*: importa /skill predefinidas de opendesign.
- [x] **opencode-snip**: Recortar salida de la terminal para evitar ruido que cosume tokens.
     *Consideración*: Sigue en prueba, tener en cuenta para el ahorro de tokens.
- [x] **envsitter-guard**: Evita que el agente filtre secretos a las LLMS.
- [x] *TokenScope**: Análisis detallado del uso de tokens y tracking de costes por sesión.
     *Consideración*: comando es /tokenscope.
