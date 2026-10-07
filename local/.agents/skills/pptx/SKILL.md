---
name: pptx
description: Genera presentaciones PowerPoint modernas desde cero (usando Node/pnpm y pptxgenjs) o inspecciona y modifica archivos .pptx existentes (usando Python y python-pptx).
---

# PowerPoint (PPTX) Skill

## 1. Matriz de Decisión: ¿Crear o Modificar?

| Tarea a realizar | Motor recomendado | Herramienta | Script listo en la skill |
|---|---|---|---|
| **Crear presentación nueva desde cero** | Node.js / `pnpm` / `npm` | `pptxgenjs` | `scripts/create_deck.js` |
| **Inspeccionar contenido de un PPTX existente** | Python 3 | `python-pptx` | `scripts/inspect_deck.py` |
| **Modificar / reemplazar textos en PPTX existente** | Python 3 | `python-pptx` | `scripts/modify_deck.py` |

> [!IMPORTANT]
> `pptxgenjs` está diseñado exclusivamente para **generar** archivos nuevos con layout 16:9 y estilos modernos; **NO puede leer ni modificar archivos .pptx existentes**.  
> Para leer slides o reemplazar textos en plantillas ya existentes, utilizá obligatoriamente el motor de **Python (`python-pptx`)**.

---

## 2. Preparación y Detección del Entorno

La skill incluye dependencias aisladas para no contaminar el entorno global ni el proyecto principal.

### A. Entorno Node / pnpm (Para Creación)

1. **Detección del gestor:**
   Verificar si `pnpm` está disponible:
   ```bash
   which pnpm || which npm
   ```
2. **Instalación de dependencias aisladas en la skill:**
   ```bash
   # Con pnpm (recomendado si está en la máquina):
   pnpm --dir .agents/skills/pptx install

   # Con npm alternativo:
   npm --prefix .agents/skills/pptx install
   ```

### B. Entorno Python (Para Inspección y Modificación)

En sistemas Linux modernos (PEP 668), `pip` puede restringir instalaciones globales. Usar un entorno virtual aislado dentro de la carpeta de la skill:

```bash
# 1. Crear entorno virtual si no existe
python3 -m venv .agents/skills/pptx/.venv

# 2. Instalar python-pptx en el venv aislado
.agents/skills/pptx/.venv/bin/pip install python-pptx
```

---

## 3. Flujo de Trabajo: Crear Presentaciones Nuevas

Para generar presentaciones atractivas y consistentes, utilizá `create_deck.js` pasando un archivo de configuración JSON.

### Comando de ejecución:
```bash
node .agents/skills/pptx/scripts/create_deck.js \
  --config <ruta_a_config.json> \
  --output <ruta_de_salida.pptx>
```

Para generar una presentación de demostración rápida:
```bash
node .agents/skills/pptx/scripts/create_deck.js --demo --output demo.pptx
```

### Estructura del JSON de configuración:

```json
{
  "title": "Título de la Presentación",
  "theme": "dark-modern", 
  "slides": [
    {
      "type": "title",
      "title": "Estrategia de Agentes de IA",
      "subtitle": "Arquitectura Multi-Agente en OpenCode",
      "footer": "Q4 Roadmap • Tech Team"
    },
    {
      "type": "cards",
      "title": "Pilares del Ecosistema",
      "subtitle": "Especialización de responsabilidades",
      "cards": [
        {
          "badge": "PRODUCTO",
          "title": "Product Owner",
          "desc": "Convierte requerimientos en opciones cerradas para el usuario."
        },
        {
          "badge": "ANÁLISIS",
          "title": "Planificador",
          "desc": "Mapea dependencias y define el plan de trabajo."
        },
        {
          "badge": "CALIDAD",
          "title": "Tester",
          "desc": "Valida la implementación antes de subir cambios."
        }
      ]
    },
    {
      "type": "split",
      "title": "Métricas de Impacto",
      "subtitle": "Resultados observados en producción",
      "left": {
        "header": "Puntos Destacados",
        "points": [
          "Reducción drástica de rondas de aclaración con opciones [A], [B].",
          "Trazabilidad de consumo de tokens por subagente."
        ]
      },
      "right": {
        "badge": "RESULTADO",
        "title": "85% Más Rápido",
        "desc": "Menor tiempo de feedback y mayor precisión en requisitos."
      }
    },
    {
      "type": "bullets",
      "title": "Próximos Pasos",
      "points": [
        "Despliegue de skills automáticas en proyectos nuevos.",
        "Monitoreo continuo de latencia y costos."
      ]
    },
    {
      "type": "quote",
      "title": "Conclusión",
      "quote": "La especialización de agentes elimina la ambigüedad y acelera el desarrollo.",
      "author": "Equipo de Arquitectura"
    }
  ]
}
```

### Temas visuales disponibles:
* `"minimal-light"`: Fondo gris claro, tarjetas blancas, acento azul clásico.
* `"dark-modern"`: Fondo slate oscuro (#0F172A), tarjetas oscuras (#1E293B), acento cyan/celeste.
* `"emerald-corporate"`: Fondo menta claro, acento esmeralda (#059669), estilo corporativo fresco.
* `"indigo-future"`: Fondo lavanda claro, acento índigo (#6366F1), estilo tecnológico moderno.

---

## 4. Flujo de Trabajo: Inspeccionar y Modificar PPTX Existente

### Paso 1: Inspeccionar la estructura
Permite al agente conocer títulos, números de slides, cajas de texto y tablas antes de tocar el archivo:

```bash
.agents/skills/pptx/.venv/bin/python .agents/skills/pptx/scripts/inspect_deck.py \
  --input presentacion.pptx
```
*(Para obtener la salida procesable en JSON, agregar `--json`)*

### Paso 2: Reemplazar textos o actualizar datos
Reemplaza cadenas de texto preservando tipografía, tamaños y colores:

```bash
# Reemplazo directo por línea de comandos:
.agents/skills/pptx/.venv/bin/python .agents/skills/pptx/scripts/modify_deck.py \
  --input original.pptx \
  --output modificada.pptx \
  --replace-json '{"Texto Antiguo": "Texto Nuevo", "2024": "2026"}'
```

O utilizando un archivo JSON de mapeo:
```bash
.agents/skills/pptx/.venv/bin/python .agents/skills/pptx/scripts/modify_deck.py \
  --input original.pptx \
  --output modificada.pptx \
  --replace-file mapeo_reemplazos.json
```

---

## 5. Reglas de Diseño y Calidad

1. **Aspect Ratio 16:9 Obligatorio:** Todas las presentaciones generadas deben utilizar formato panorámico 16:9 (`LAYOUT_16x9`), el estándar actual para pantallas y monitores modernos.
2. **Jerarquía Tipográfica Clara:**
   * Título principal: 28pt – 36pt (Negrita).
   * Subtítulos: 18pt – 22pt.
   * Contenido / Cards: 13pt – 16pt.
   * Badges / Metadatos: 9pt – 12pt (Mayúsculas, fondo contrastante).
3. **Agrupación en Tarjetas (Card UI):** No colocar bloques de texto sueltos flotando sobre fondos planos. Agrupar la información en contenedores rectangulares con bordes sutiles y bordes redondeados.
4. **Densidad de Información:**
   * Máximo 1 idea central por diapositiva.
   * Entre 2 y 4 tarjetas por slide de tipo `cards`.
   * Máximo 40 palabras por tarjeta o punto clave.
5. **Aislamiento de Archivos:** No commitear `.venv` ni `node_modules` de la skill; las dependencias se gestionan localmente en `.agents/skills/pptx/`.
