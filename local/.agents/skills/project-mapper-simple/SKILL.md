---
name: project-mapper-simple
description: Genera un mapa estructural liviano del proyecto en formato JSON (archivos, clases, funciones, imports y dependencias).
---

# Project Mapper Simple

> [!WARNING]
> **Límite de eficiencia y consumo de tokens en proyectos grandes:**
> Esta skill vuelca la estructura completa en un solo JSON sin filtrar. En proyectos grandes, leer este JSON en el contexto del modelo resulta ineficiente:
> - **Umbral crítico:** Más de **150-200 archivos**, tamaño JSON **> 40-50 KB** o **> 4.000 tokens estimados**.
> - **Impacto:** Cargar este JSON completo satura la ventana de contexto del agente, reduce el espacio para código/instrucciones y eleva costos y latencia.
> - **Recomendaciones ante proyectos grandes:**
>   1. Usar el flag `--light` para omitir detalles de métodos/clases y reducir el tamaño entre un 50% y 70%.
>   2. Excluir carpetas no críticas con `--exclude "<patron>"` (ej. `--exclude "tests/**"`, `--exclude "docs/**"`).
>   3. Si el proyecto sigue superando los 4.000 tokens, usar la skill **`rag-json`** (búsqueda vectorial).

## Objetivo

Escanear la raíz de un proyecto y generar un único archivo JSON estructurado (`project_map.json`) que contenga el mapa completo de archivos, símbolos (clases, funciones), imports/exports y grafo de dependencias, sin pasos intermedios ni dependencias externas.

---

## Cuándo activar

- Al iniciar una sesión o tarea que involucre múltiples archivos o módulos del proyecto.
- Cuando se necesite consultar la arquitectura, estructura de carpetas o dependencias en un formato JSON fácil de parsear.
- Para ubicar rápidamente qué archivos existen y qué símbolos declaran sin necesidad de explorar el sistema de archivos manualmente.

---

## Generación del JSON

Ejecutar desde la raíz del proyecto:

**Linux / macOS:**

```bash
python3 <skill>/scripts/generate_map.py \
  --project . \
  --output <skill>/resources/project_map.json
```

**Windows:**

```powershell
python <skill>\scripts\generate_map.py `
  --project . `
  --output <skill>\resources\project_map.json
```

### Opciones de ejecución

- `--force`, `-f`: Fuerza la regeneración del mapa ignorando el tiempo de caché.
- `--light`: Genera un mapa resumido que incluye únicamente `path`, `summary`, `imports`, `exports` y `complexity`.
- `--include-lines`: Agrega los números de línea exactos donde se definen clases y funciones.
- `--exclude "<patron>"`: Agrega patrones glob adicionales para excluir archivos o carpetas (ej. `--exclude "docs/**"`).

---

## Estructura del JSON generado

El archivo `project_map.json` contiene la siguiente estructura:

```json
{
  "project_name": "nombre-del-proyecto",
  "generated_at": "2026-10-25T11:00:00+00:00",
  "total_files": 42,
  "total_symbols": 128,
  "architecture": {
    "entry_points": ["main.py"],
    "core_modules": ["src"],
    "utils": ["utils"],
    "tests": ["tests"],
    "config": ["config"],
    "infrastructure": [],
    "all_directories": ["src", "tests", "utils"]
  },
  "files": [
    {
      "path": "src/app.py",
      "language": "python",
      "size_lines": 85,
      "summary": "Módulo Python con 2 clases y 3 funciones",
      "imports": ["os", "sys"],
      "exports": ["AppService"],
      "classes": [
        {
          "name": "AppService",
          "docstring": "Servicio principal...",
          "methods": ["run", "stop"]
        }
      ],
      "functions": [
        {
          "name": "init_app",
          "args": ["config"],
          "is_async": false
        }
      ],
      "complexity": "medium"
    }
  ],
  "dependency_graph": {
    "src/app.py": ["src/utils/logger.py"]
  },
  "metadata": {
    "mapper_version": "3.0.0",
    "languages_found": ["python", "typescript"]
  }
}
```

---

## Reutilización y Caché

- **Reutilización:** Si `project_map.json` existe y tiene menos de 2 horas (`--max-age-hours 2.0`), el script no lo regenera a menos que se use `--force`.
- **Regeneración forzada:** Usar `--force` tras un cambio estructural importante en el código (git pull, refactors o reorganización de carpetas).
