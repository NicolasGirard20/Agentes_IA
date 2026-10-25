# Project Mapper Simple

Versión resumida y liviana de la skill **Project Mapper**, orientada exclusivamente a generar un archivo `project_map.json` con la estructura completa del proyecto sin pasos de filtrado, inyección contextual ni compresión externa.

## 📁 Estructura

```text
project-mapper-simple/
├── SKILL.md                 # Definición de la skill e instrucciones para agentes
├── README.md                # Documentación de uso general
├── scripts/
│   └── generate_map.py      # Generador del mapa JSON (Python estándar, sin dependencias)
├── resources/
│   └── project_map.json     # Salida generada por el script
└── tests/
    └── test_generate_map.py # Pruebas unitarias básicas
```

## 🚀 Uso Rápido

```bash
# Generar el JSON
python local/.agents/skills/project-mapper-simple/scripts/generate_map.py \
  --project . \
  --output local/.agents/skills/project-mapper-simple/resources/project_map.json

# Forzar regeneración
python local/.agents/skills/project-mapper-simple/scripts/generate_map.py \
  --project . \
  --output local/.agents/skills/project-mapper-simple/resources/project_map.json \
  --force
```

## ⚠️ Advertencia de Consumo de Tokens (Proyectos Grandes)

Al no realizar filtrado heurístico ni compresión semántica, el archivo JSON resultante se traslada completo al contexto del modelo.

- **Cuándo se vuelve ineficiente:** Proyectos con **> 150-200 archivos**, tamaño JSON **> 40-50 KB** o **> 4.000 tokens estimados**.
- **Impacto:** Ocupa un porcentaje alto de la ventana de contexto del LLM, ralentizando respuestas y reduciendo el espacio útil para código o razonamiento.
- **Qué hacer:**
  1. **Modo ligero (`--light`):** Omite definiciones internas de clases y funciones, conservando únicamente paths, imports, exports y resumen. Reduce el JSON entre un 50% y 70%.
  2. **Exclusiones (`--exclude`):** Descartar carpetas secundarias (ej. `--exclude "tests/**"`).
  3. **Escalar a skills avanzadas:** Si el proyecto supera los 4.000 tokens, considerar la skill completa **`project-mapper`** (que filtra por consulta con `inject_relevant.py`) o **`rag-json`** (búsqueda vectorial).
