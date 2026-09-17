---
description: Valida archivos sensibles y arma un commit con mensaje conventional commit.
agent: git
---

Primero corré la validación de seguridad de GIT.md (sección 2 y 3). Si hay archivos sensibles sin resolver, DETENÉ acá y avisá, no sigas con el resto de este comando.

Si todo está limpio, mostrame el `git status` y `git diff` staged/unstaged, proponeme un mensaje de commit siguiendo Conventional Commits (`feat:`, `fix:`, `chore:`, etc.) basado en los cambios reales, y esperá mi confirmación antes de ejecutar `git commit`.
