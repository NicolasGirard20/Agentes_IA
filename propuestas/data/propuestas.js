window.PROPUESTAS = {
  "temas": [
    {
      "id": "t1",
      "nombre": "Recomendaciones de skills",
      "items": [
        {
          "id": "p1",
          "titulo": "Validador de prompts",
          "descripcion": "Reglas y sanitizadores (longitud, incoherencias, instrucciones peligrosas) que alerten antes de enviar.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p2",
          "titulo": "Auto-refinador (iterative refinement)",
          "descripcion": "Genera y compara variantes de prompt, elige la mejor mediante métricas automáticas.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p4",
          "titulo": "Gestión de contexto y memoria",
          "descripcion": "Short/long-term memory, retriever vectorial (RAG) para incluir contexto relevante al prompt.",
          "consideracion": "",
          "hecho": true
        },
        {
          "id": "p5",
          "titulo": "Composer dinámico de prompts",
          "descripcion": "Motor que arma prompts condicionales (bloques, bucles, ramificaciones) según meta/rol.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p6",
          "titulo": "Evaluador automático",
          "descripcion": "Tests de calidad de salida (exactitud, coherencia, toxicidad) y dashboard de métricas.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p7",
          "titulo": "Simulador de interacción agentica",
          "descripcion": "Entorno para simular pasos, rollouts y validar estrategias (útil para entrenar políticas).",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p8",
          "titulo": "Controlador meta (planner)",
          "descripcion": "Descompone objetivos en sub-tasks y orquesta agentes especializados (`build-orquestor` → `build-constructor`).",
          "consideracion": "",
          "hecho": true
        },
        {
          "id": "p9",
          "titulo": "Verificador de acciones (safety & verification)",
          "descripcion": "Revisión automática de resultados/acciones propuestas contra reglas y sandboxed execution.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p10",
          "titulo": "Conectores multi-externos",
          "descripcion": "Skills para integrarse con web search, bases de datos, APIs y ejecutar código seguro.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p11",
          "titulo": "Aprendizaje desde feedback",
          "descripcion": "Registro de feedback humano + ajuste de prompts/ejemplos y ranking de mejores estrategias.",
          "consideracion": "",
          "hecho": false
        },
        {
          "id": "p12",
          "titulo": "Ensamble agentico",
          "descripcion": "Orquestrador de múltiples agentes especializados (explorador, experto, revisor) que cooperan en una tarea.",
          "consideracion": "",
          "hecho": true
        },
        {
          "id": "p13",
          "titulo": "Agregar skill de terceros",
          "descripcion": "Ejemplo de github.com/w7panel/w7panel/tree/main/.opencode/skills.",
          "consideracion": "",
          "hecho": true
        }
      ]
    },
    {
      "id": "t2",
      "nombre": "Plugins opencode",
      "items": [
        {
          "id": "p14",
          "titulo": "opendesign",
          "descripcion": "Herramienta de diseño para generar prototipos funcionales, interfaces, páginas web o presentaciones en archivos html.",
          "consideracion": "Se reemplazó solución por mcp de figma. CONSUME MUCHOS TOKENS",
          "hecho": true
        },
        {
          "id": "p15",
          "titulo": "opencode-snip",
          "descripcion": "Recortar salida de la terminal para evitar ruido que consume tokens.",
          "consideracion": "Sigue en prueba, tener en cuenta para el ahorro de tokens.",
          "hecho": true
        },
        {
          "id": "p16",
          "titulo": "envsitter-guard",
          "descripcion": "Evita que el agente filtre secretos a las LLMS.",
          "consideracion": "",
          "hecho": true
        },
        {
          "id": "p17",
          "titulo": "TokenScope",
          "descripcion": "Análisis detallado del uso de tokens y tracking de costes por sesión.",
          "consideracion": "comando es /tokenscope.",
          "hecho": true
        }
      ]
    },
    {
      "id": "t3",
      "nombre": "Model Context Protocol",
      "items": [
        {
          "id": "p18",
          "titulo": "figma-mcp",
          "descripcion": "Conectarse a plantillas de figma.",
          "consideracion": "hay que renovar la api",
          "hecho": true
        },
        {
          "id": "p19",
          "titulo": "ui-skills",
          "descripcion": "Decenas de skills de diseño y otros temas disponibles de manera remota.",
          "consideracion": "",
          "hecho": true
        },
        {
          "id": "p20",
          "titulo": "context7",
          "descripcion": "Documentación de herramientas, frameworks. Login.",
          "consideracion": "",
          "hecho": true
        },
        {
          "id": "p21",
          "titulo": "github",
          "descripcion": "Seguimiento de repos y demás.",
          "consideracion": "se necesita apikey",
          "hecho": false
        }
      ]
    },
    {
      "id": "mwdy81i1k0dq",
      "nombre": "Proyectos personales",
      "items": [
        {
          "id": "mwdyb730zcl9",
          "titulo": "Wallet",
          "descripcion": "Tranferencias, ahorros, inversiones, planes de gasto",
          "consideracion": "Falta conectar banco, mejorar estadísticas, agilizar botones más usados",
          "hecho": false
        },
        {
          "id": "mwdyc7diqzpj",
          "titulo": "Inmovación",
          "descripcion": "Gestión de inmobiliaria GBS",
          "consideracion": "Falta cargar datos reales",
          "hecho": false
        }
      ]
    }
  ]
};
