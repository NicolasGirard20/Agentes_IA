---
name: structured-query
description: >-
  Evalúa consultas del usuario o agente en formato JSON usando el modelo de decisión
  typesafe/jev-1.13 vía OpenRouter. Selecciona automáticamente si usar is_bug (noul),
  team/tema (choice) o urgency (score) según la pregunta.
---

# Skill: Structured Query (`typesafe/jev-1.13`)

Convierte la consulta del usuario o agente en un JSON válido para `https://openrouter.ai/api/alpha/decisions` con el modelo `typesafe/jev-1.13`.

La api OPENROUTER_API_KEY debe estar definida en la variable de entorno del proyecto (por ejemplo, en `.env`).

## 1. Qué estructura usar según la pregunta

Analiza la intención de la consulta y elige **solo** los bloques necesarios dentro de `"questions"`:

| Si la pregunta busca... | Clave a usar | Tipo (`type`) | Cuándo aplicarla |
| :--- | :--- | :--- | :--- |
| **Confirmar un hecho / Sí o No** | `is_bug` | `"noul"` | Saber si hay un fallo, defecto o si se cumple una condición (`true` / `false`). |
| **Clasificar / Asignar categoría o área** | `team` (o `tema`) | `"choice"` | Elegir a qué categoría, tema o equipo corresponde entre varias opciones. |
| **Medir prioridad / Nivel / Gravedad** | `urgency` | `"score"` | Evaluar qué tan urgente, grave o prioritario es en una escala ordenada. |

> Si la consulta requiere evaluar las tres cosas a la vez (ej. triaje completo de un ticket), incluye las tres claves en `"questions"`.

---

## 2. Plantilla en Python

Ejecuta o adapta [`structured_query.py`](file:///home/nico/.opencode/skills/structured-query/structured_query.py):

```python
import os
import requests

response = requests.post(
    "https://openrouter.ai/api/alpha/decisions",
    headers={
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "model": "typesafe/jev-1.13",
        "state": {
            "query": "Texto o contexto del usuario/agente a evaluar"
        },
        "questions": {
            # 1. Usar si pregunta Sí/No o si es un bug/defecto:
            "is_bug": {
                "type": "noul",
                "instructions": "Is the customer reporting a software defect?",
                "criteria": {
                    "true": "The customer describes broken or unexpected product behavior.",
                    "false": "The customer is asking a question or requesting a feature.",
                },
            },
            # 2. Usar si pregunta por tema, categoría o equipo responsable:
            "team": {
                "type": "choice",
                "instructions": "Which team should own this ticket?",
                "criteria": {
                    "payments": "Checkout, billing, or payment processing issues.",
                    "frontend": "Rendering, layout, or browser compatibility issues.",
                    "account": "Login, permissions, or profile issues.",
                },
            },
            # 3. Usar si pregunta por nivel de urgencia, severidad o prioridad:
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this ticket?",
                "criteria": [
                    "Can wait for the next release",
                    "Should be fixed this week",
                    "Blocking revenue right now",
                ],
            },
        },
    },
)

print(response.json()["answers"])
```

## 3. Pasos para el Agente

1. Coloca los datos del usuario o contexto en `"state"`.
2. Selecciona `is_bug`, `team` y/o `urgency` según lo que pida la pregunta, ajustando `instructions` y `criteria` al caso puntual.
3. Envía el JSON por POST y lee `response.json()["answers"]`.