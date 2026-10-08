---
name: rag-json
description: Recupera con generación aumentada (RAG híbrido) la ubicación y contexto de archivos de interés consumiendo search_readme_openrouter.py sobre project_map.json con Qdrant y OpenRouter.
---

# RAG JSON

## Objetivo

Recuperar con **generación aumentada (RAG semántico + léxico)** la ubicación exacta y el contexto de los archivos de interés para responder a cualquier consulta sobre el proyecto, reduciendo exploraciones manuales del árbol de directorios y optimizando el consumo de tokens.

La búsqueda consume el mapa del proyecto (`project_map.json`) e indexa vectores densos (embeddings de OpenRouter) y vectores dispersos (BM25/IDF) en una base vectorial **Qdrant**.

---

## Cuándo activar esta skill

**Activar cuando:**
- Se desconoce qué archivos, módulos o capas implementan un comportamiento o funcionalidad.
- La consulta del usuario se formula en lenguaje natural o con conceptos funcionales que no coinciden con nombres exactos de archivos o funciones.
- Se necesita identificar dependencias, callers y responsabilidades antes de planificar o construir una solución.
- Se requiere contexto arquitectónico relevante para orientar la lectura de archivos clave.

**No activar cuando:**
- La tarea involucra un archivo ya conocido y abierto.
- La modificación es puntual (un string, estilo, variable local o fix menor).
- La búsqueda es un término exacto simple resoluble con una búsqueda textual directa en archivos ya localizados.

---

## Preparación y Activación del Entorno (Obligatorio)

Para asegurar la ejecución del script sin colisionar con el sistema global (PEP 668) ni depender de paquetes preinstalados en la máquina, el agente consumidor debe garantizar el entorno virtual y sus librerías.

### 1. Resolución de Rutas
Identificar la ubicación de la skill en este orden:
1. `.agents/skills/rag-json/`
2. `local/.agents/skills/rag-json/`

En los siguientes comandos, `<skill>` representa la ruta encontrada.

### 2. Crear y Activar el Entorno Virtual
Verificar si existe un entorno virtual en la carpeta de la skill o en el proyecto. Si no existe, crearlo:

```bash
# Crear entorno virtual si no existe
if [ ! -d "<skill>/.venv" ]; then
  python3 -m venv <skill>/.venv
fi
```

**Para ejecutar comandos o activar:**
- **Linux / macOS**:
  - Vía intérprete directo: `<skill>/.venv/bin/python`
  - Vía activación de shell: `source <skill>/.venv/bin/activate`
- **Windows**:
  - Vía intérprete directo: `<skill>\.venv\Scripts\python.exe`
  - Vía activación de shell: `<skill>\.venv\Scripts\activate`

### 3. Descarga e Instalación de Librerías
Comprobar si las librerías necesarias están disponibles. Si faltan o es la primera ejecución, instalarlas en el entorno virtual:

```bash
<skill>/.venv/bin/pip install -r <skill>/requirements.txt
```

*(O instalación directa si no se usa requirements.txt: `<skill>/.venv/bin/pip install qdrant-client numpy`)*

---

## Prerrequisitos de Ejecución y Gestión de Qdrant

Antes de ejecutar la búsqueda RAG, validar los siguientes requisitos:

### 1. Estado de Qdrant y Consulta al Usuario
El servicio de Qdrant debe estar activo y respondiendo en `http://localhost:6333` (HTTP) y `6334` (gRPC).

- **Comprobación de estado:**
  El agente debe verificar si el servicio o contenedor está respondiendo antes de lanzar la búsqueda:
  ```bash
  curl -s -f http://localhost:6333/healthz > /dev/null 2>&1
  ```

- **Acción si Qdrant NO está corriendo:**
  > [!IMPORTANT]
  > **El agente NO debe iniciar el contenedor automáticamente a ciegas.**
  > Si la comprobación falla, debe **preguntar explícitamente al usuario** si desea que active el contenedor de Qdrant.

  **Protocolo de consulta:**
  1. Informar al usuario: *"El servicio de Qdrant no está corriendo en localhost:6333, el cual es necesario para la recuperación vectorial de rag-json."*
  2. Preguntar al usuario: *"¿Querés que active el contenedor Docker de Qdrant ahora?"*
  3. **Si el usuario acepta / confirma:**
     - Si ya existe un contenedor previo (detenido):
       ```bash
       docker start qdrant-local || docker start qdrant
       ```
     - Si no existe ningún contenedor previo:
       ```bash
       docker run -d --name qdrant-local -p 6333:6333 -p 6334:6334 qdrant/qdrant
       ```
     - Verificar que el endpoint responda (`curl -s -f http://localhost:6333/healthz`) y continuar con la ejecución del script.
  4. **Si el usuario rechaza o no utiliza Docker:**
     - Suspender la ejecución de la skill informando que se requiere Qdrant activo en `localhost:6333` para proceder.

### 2. Variable de entorno `OPENROUTER_API_KEY`
- Debe estar definida en el entorno o en un archivo `.env` dentro de `<skill>/scripts/.env` o en la raíz.

### 3. Archivo `project_map.json`
- Debe existir el mapa del proyecto generado previamente (por ejemplo en `local/.agents/skills/project-mapper/resources/project_map.json` o en `.agents/skills/project-mapper/resources/project_map.json`).

---

## Flujo de Trabajo y Comandos

El motor principal de la skill es `<skill>/scripts/search_readme_openrouter.py`.

### 1. Búsqueda con Salida RAG en Markdown (Recomendado para LLMs)
Genera un bloque de contexto compacto listo para inyectar en el razonamiento del agente, listando los archivos por relevancia, sus resúmenes, símbolos y dependencias:

```bash
<skill>/.venv/bin/python <skill>/scripts/search_readme_openrouter.py \
  --map <ruta_a_project_map.json> \
  --rag \
  --top-k 5 \
  "<consulta en lenguaje natural>"
```

### 2. Búsqueda con Salida Estructurada JSON
Para procesar programáticamente la lista de archivos, scores y metadatos:

```bash
<skill>/.venv/bin/python <skill>/scripts/search_readme_openrouter.py \
  --map <ruta_a_project_map.json> \
  --json \
  --top-k 5 \
  "<consulta en lenguaje natural>"
```

### 3. Reindexación Forzada
Si el archivo `project_map.json` sufrió modificaciones estructurales recientes y se desea reconstruir la colección en Qdrant:

```bash
<skill>/.venv/bin/python <skill>/scripts/search_readme_openrouter.py \
  --map <ruta_a_project_map.json> \
  --reindex \
  "<consulta>"
```

---

## Parámetros del Script

| Opción | Tipo | Descripción | Defecto |
|---|---|---|---|
| `query` | Posicional | Consulta en lenguaje natural | Requerido |
| `--map` | String | Ruta al archivo `project_map.json` | `project_map.json` |
| `--rag` | Flag | Formatea la salida como bloque Markdown optimizado para LLMs | `False` |
| `--json` | Flag | Salida en formato JSON estructurado | `False` |
| `--top-k` | Entero | Cantidad de archivos a recuperar | `5` |
| `--min-score` | Float | Umbral mínimo de score combinado (0.0 a 1.0) | `0.2` |
| `--reindex` | Flag | Fuerza la reindexación de la colección vectorial | `False` |
| `--embed-model` | String | Modelo de embeddings en OpenRouter | `openai/text-embedding-3-small` |
| `--host` | String | Host de Qdrant | `localhost` |
| `--port` | Entero | Puerto HTTP de Qdrant | `6333` |

---

## Uso de los Resultados por el Agente

1. **Lectura orientada**: La salida de la skill provee rutas precisas (`file`), resumen y símbolos clave. Utilizar estas rutas como índice para leer únicamente los archivos relevantes con `view_file`.
2. **Evitar exploración ciega**: No ejecutar búsquedas recursivas ni listar directorios enteros si la skill ya localizó los archivos pertinentes.
3. **Presentación al usuario u otros agentes**: Al reportar hallazgos, incluir enlaces clicables a los archivos localizados (`[nombre](file:///ruta/al/archivo)`), explicando brevemente por qué son de interés para la consulta.
