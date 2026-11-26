window.PROPUESTAS = {
  "temas": [
    {
      "id": "t1",
      "nombre": "Recomendaciones de skills",
      "items": [
        {
          "id": "p2",
          "titulo": "Auto-refinador (iterative refinement)",
          "descripcion": "Genera y compara variantes de prompt, elige la mejor mediante métricas automáticas.",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "p4",
          "titulo": "Gestión de contexto y memoria",
          "descripcion": "Short/long-term memory, retriever vectorial (RAG) para incluir contexto relevante al prompt.",
          "mejoras": [],
          "hecho": true
        },
        {
          "id": "p6",
          "titulo": "Evaluador automático",
          "descripcion": "Tests de calidad de salida (exactitud, coherencia, toxicidad) y dashboard de métricas.",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "p7",
          "titulo": "Simulador de interacción agentica",
          "descripcion": "Entorno para simular pasos, rollouts y validar estrategias (útil para entrenar políticas).",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "p8",
          "titulo": "Controlador meta (planner)",
          "descripcion": "Descompone objetivos en sub-tasks y orquesta agentes especializados (`build-orquestor` → `build-constructor`).",
          "mejoras": [],
          "hecho": true
        },
        {
          "id": "p9",
          "titulo": "Verificador de acciones (safety & verification)",
          "descripcion": "Revisión automática de resultados/acciones propuestas contra reglas y sandboxed execution.",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "p10",
          "titulo": "Conectores multi-externos",
          "descripcion": "Skills para integrarse con web search, bases de datos, APIs y ejecutar código seguro.",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "p11",
          "titulo": "Aprendizaje desde feedback",
          "descripcion": "Registro de feedback humano + ajuste de prompts/ejemplos y ranking de mejores estrategias.",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "p12",
          "titulo": "Ensamble agentico",
          "descripcion": "Orquestrador de múltiples agentes especializados (explorador, experto, revisor) que cooperan en una tarea.",
          "mejoras": [],
          "hecho": true
        },
        {
          "id": "p13",
          "titulo": "Agregar skill de terceros",
          "descripcion": "Ejemplo de github.com/w7panel/w7panel/tree/main/.opencode/skills.",
          "mejoras": [],
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
          "mejoras": [
            {
              "id": "mwy7b7d6jrvj",
              "texto": "Se reemplazó solución por mcp de figma. CONSUME MUCHOS TOKENS",
              "hecho": false
            }
          ],
          "hecho": true
        },
        {
          "id": "p15",
          "titulo": "opencode-snip",
          "descripcion": "Recortar salida de la terminal para evitar ruido que consume tokens.",
          "mejoras": [
            {
              "id": "mwy7b7d6iqjg",
              "texto": "Sigue en prueba, tener en cuenta para el ahorro de tokens.",
              "hecho": false
            }
          ],
          "hecho": true
        },
        {
          "id": "p16",
          "titulo": "envsitter-guard",
          "descripcion": "Evita que el agente filtre secretos a las LLMS.",
          "mejoras": [],
          "hecho": true
        },
        {
          "id": "p17",
          "titulo": "TokenScope",
          "descripcion": "Análisis detallado del uso de tokens y tracking de costes por sesión.",
          "mejoras": [
            {
              "id": "mwy7b7d68t6e",
              "texto": "comando es /tokenscope.",
              "hecho": false
            }
          ],
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
          "mejoras": [
            {
              "id": "mwy7b7d6g5n8",
              "texto": "hay que renovar la api",
              "hecho": false
            }
          ],
          "hecho": true
        },
        {
          "id": "p19",
          "titulo": "ui-skills",
          "descripcion": "Decenas de skills de diseño y otros temas disponibles de manera remota.",
          "mejoras": [],
          "hecho": true
        },
        {
          "id": "p20",
          "titulo": "context7",
          "descripcion": "Documentación de herramientas, frameworks. Login.",
          "mejoras": [],
          "hecho": true
        },
        {
          "id": "p21",
          "titulo": "github",
          "descripcion": "Seguimiento de repos y demás.",
          "mejoras": [
            {
              "id": "mwy7b7d6s73t",
              "texto": "se necesita apikey",
              "hecho": false
            }
          ],
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
          "mejoras": [
            {
              "id": "mwy7b7d6vy5q",
              "texto": "Falta conectar banco",
              "hecho": false
            },
            {
              "id": "mwy7fxm5vl6i",
              "texto": "Corregir tranferencia entre cuentas",
              "hecho": false
            },
            {
              "id": "mwy7ggt9nwd1",
              "texto": "Agregar tipo de moneda a cada tranferencia",
              "hecho": false
            }
          ],
          "hecho": false
        },
        {
          "id": "mwdyc7diqzpj",
          "titulo": "Inmovación",
          "descripcion": "Gestión de inmobiliaria GBS",
          "mejoras": [
            {
              "id": "mwy7b7d6g8cq",
              "texto": "Falta cargar datos reales",
              "hecho": false
            }
          ],
          "hecho": false
        },
        {
          "id": "mwfc6b8ot8nl",
          "titulo": "Armar portafolio",
          "descripcion": "No arranqué todavía",
          "mejoras": [],
          "hecho": false
        },
        {
          "id": "mwfc8jt9c9i5",
          "titulo": "Crear sitio web de gestión de proyectos",
          "descripcion": "Que se conecte al portafolio",
          "mejoras": [],
          "hecho": false
        }
      ]
    }
  ]
};
