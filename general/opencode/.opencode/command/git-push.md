---
description: Valida seguridad, rama actual y upstream antes de hacer push.
agent: git
---

Corré primero la validación de GIT.md (sección 2 y 3) sobre el estado actual del repo. Si detectás archivos sensibles sin resolver, DETENÉ y avisá.

Si está todo bien, mostrame la rama actual, si tiene upstream configurado, y cuántos commits de diferencia hay con el remoto. Después esperá mi confirmación explícita antes de correr `git push`.
