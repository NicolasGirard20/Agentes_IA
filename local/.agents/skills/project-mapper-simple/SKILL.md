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
>   1. Si el mapa se usa para alimentar **`rag-json`**, generarlo **completo (sin `--light`)** para conservar `context`, `keywords`, `docstrings` y métodos.
>   2. Si se inyectará el JSON directo en el prompt, usar `--light` (conserva `path`, `summary`, `imports`, `exports`, `complexity`) o excluir carpetas no críticas con `--exclude "<patron>"`.
>   3. Si el proyecto sigue superando los 4.000 tokens, usar la skill **`rag-json`** (búsqueda vectorial híbrida).

## Objetivo

Escanear la raíz de un proyecto y generar un único archivo JSON estructurado (`project_map.json`) que contenga el mapa de archivos, rol arquitectónico, contexto semántico (`summary`, `context`, `keywords`), símbolos (clases, métodos, funciones, docstrings, atributos), imports/exports y grafo de dependencias cruzado, sin dependencias externas (Python stdlib puro).

Lenguajes soportados con extractores modulares (`scripts/extractors/`):
- **Python** (`.py`): AST completo, docstrings de módulo/clase/función, bases y argumentos.
- **JavaScript / TypeScript** (`.js`, `.ts`, `.jsx`, `.tsx`, `.mjs`, `.cjs`): clases, funciones/arrows, JSDoc y endpoints consumidos.
- **C#** (`.cs`): `namespace`, `using`, clases/interfaces/enums, herencia, atributos (`[HttpPost]`, `[Authorize]`, `[Route]`), comentarios XML `/// <summary>`, métodos y referencias a tipos/DbSet.
- **Razor / HTML** (`.cshtml`, `.html`, `.htm`): `@model`, `Layout`, `ViewBag.Title`, encabezados, parciales (`@Html.Partial`), acciones (`@Url.Action`, `BeginForm`), `<script src>` y funciones JS embebidas.
- **SQL / PowerShell / Markdown / Config** (`.sql`, `.ps1`, `.md`, `.config`, `.xml`, `.json`): tablas/SPs, funciones, títulos/secciones y claves estructurales (sin secretos).

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

## Reutilización y Caché

- **Reutilización:** Si `project_map.json` existe y tiene menos de 2 horas (`--max-age-hours 2.0`), el script no lo regenera a menos que se use `--force`.
- **Regeneración forzada:** Usar `--force` tras un cambio estructural importante en el código (git pull, refactors o reorganización de carpetas).
