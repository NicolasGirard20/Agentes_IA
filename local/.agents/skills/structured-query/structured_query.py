import os
import requests

# Plantillas predefinidas según el tipo de pregunta
QUESTION_TEMPLATES = {
    "is_bug": {
        "type": "noul",
        "instructions": "Is the customer reporting a software defect?",
        "criteria": {
            "true": "The customer describes broken or unexpected product behavior.",
            "false": "The customer is asking a question or requesting a feature.",
        },
    },
    "team": {
        "type": "choice",
        "instructions": "Which team should own this ticket?",
        "criteria": {
            "payments": "Checkout, billing, or payment processing issues.",
            "frontend": "Rendering, layout, or browser compatibility issues.",
            "account": "Login, permissions, or profile issues.",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is this ticket?",
        "criteria": [
            "Can wait for the next release",
            "Should be fixed this week",
            "Blocking revenue right now",
        ],
    },
}


def ask_decision(state: dict | str, questions: dict | list[str] = None, model: str = "typesafe/jev-1.13") -> dict:
    """
    Envía el estado y las preguntas seleccionadas ('is_bug', 'team', 'urgency' o dict personalizado)
    a OpenRouter Decisions API.
    """
    if questions is None:
        selected_questions = QUESTION_TEMPLATES
    elif isinstance(questions, list):
        # Permite pasar ej. ["is_bug", "urgency"]
        selected_questions = {k: QUESTION_TEMPLATES[k] for k in questions if k in QUESTION_TEMPLATES}
    else:
        selected_questions = questions

    response = requests.post(
        "https://openrouter.ai/api/alpha/decisions",
        headers={
            "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "state": state,
            "questions": selected_questions,
        },
    )
    response.raise_for_status()
    return response.json()["answers"]


if __name__ == "__main__":
    answers = ask_decision(
        state={
            "customer_tier": "enterprise",
            "ticket": "My checkout page shows a blank screen after I click Pay. I have tried two browsers.",
        },
        questions=["is_bug", "team", "urgency"],
    )
    print(answers)
