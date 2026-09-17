---
description: Corre solo la validación de archivos sensibles (.env, claves, etc.), sin ejecutar ninguna acción de git.
agent: git
---

Ejecutá `git status --porcelain` y `git diff --cached --name-only`. Aplicá la validación de la sección 2 de GIT.md. Reportá qué archivos sensibles (si los hay) están sin resolver, sin ejecutar ningún comando que escriba en el repo.
