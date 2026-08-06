# Uso de prompt-toolkit

Este ejemplo muestra el flujo básico para reutilizar un template y validarlo antes de enviarlo al modelo.

## 1. Elegir un template

Consulta `templates/index.json` y selecciona el prompt que necesitas. Por ejemplo:

- `coding/refactor.md` para refactorizar código
- `review/security-review.md` para auditorías de seguridad
- `meta/handoff.md` para transferencias entre agentes

## 2. Rellenar variables

Supón que quieres usar uno de los templates del catálogo.

### Ejemplo A: refactor de código

Template:

```text
Lenguaje: {{lang}}
Objetivo: {{goal}}

Código:
{{code}}
```

Valores de ejemplo:

- `lang`: `python`
- `goal`: `reducir duplicación y separar responsabilidades`
- `code`: bloque de código a refactorizar

### Ejemplo B: revisión de seguridad

```md
Archivo: {{file_path}}
Código a revisar:
{{code_snippet}}
```

Valores de ejemplo:

- `file_path`: `src/auth/login.py`
- `code_snippet`: bloque de código a revisar

### Ejemplo C: handoff entre agentes

Si agregas el template `meta/handoff.md`, el patrón esperado sería:

```md
Contexto:
{{context}}

Agente destino:
{{agent_target}}
```

Valores de ejemplo:

- `context`: resumen breve de lo ya hecho y lo que falta
- `agent_target`: `security-reviewer`

## 3. Validar el prompt

Antes de enviarlo, ejecuta los validadores del toolkit:

```json
{
  "prompt": "prompt renderizado",
  "rules": {
    "max_length": 8000,
    "max_tokens_estimate": 6000,
    "coherence": {
      "min_words": 3,
      "max_repetition_ratio": 0.4,
      "require_context": true
    }
  }
}
```

Orden recomendado:

1. `check_length.py`
2. `detect_injection.py`
3. `check_coherence.py`

## 4. Interpretar resultados

- `BLOCK`: no enviar el prompt.
- `WARN`: revisar manualmente y continuar solo si el contexto es correcto.
- Sin hallazgos: el prompt está listo para usar.

## 5. Regla práctica

Si el prompt no tiene contexto claro, variables concretas o una intención única, no lo envíes todavía. Añade contexto o divide la tarea en pasos más pequeños.