# GIT.md — Reglas del Agente de Git (OpenCode)

Este archivo define el comportamiento del agente al ejecutar comandos de Git y control de versiones. Debe ser respetado en **todas** las operaciones, sin excepción, salvo instrucción explícita y consciente del usuario en el momento (ver sección de overrides).

## 1. Rol del agente

El agente actúa como asistente de control de versiones. Puede:
- Crear ramas, hacer `add`, `commit`, `push`, `pull`, `merge`, `rebase`, `tag`, etc.
- Redactar mensajes de commit siguiendo Conventional Commits.
- Revisar el estado del repo antes de cada acción.

## 2. Validación obligatoria previa a CUALQUIER acción de escritura en git

Antes de ejecutar `git add`, `git commit`, `git push`, `git merge`, `git rebase --autostash`, o cualquier comando que modifique el historial o el remoto, el agente **DEBE**:

1. Ejecutar `git status --porcelain` y `git diff --cached --name-only`.
2. Verificar si alguno de los archivos detectados (nuevos, modificados o staged) coincide con alguno de estos patrones:
   - `.env`
   - `.env.*` (`.env.local`, `.env.production`, `.env.development`, etc.)
   - `*.pem`, `*.key`, `*.crt`, `*.p12`
   - `secrets.*`, `*secret*`, `*credentials*`
   - `id_rsa`, `id_ed25519` (y sus variantes `.pub` se permiten, la privada no)
   - Cualquier archivo listado en `.gitignore` que el usuario haya marcado como sensible
3. Si encuentra coincidencias:
   - **DETENER** la operación inmediatamente. No ejecutar `add`, `commit` ni `push`.
   - Informar al usuario cuáles archivos fueron detectados y por qué se bloqueó la acción.
   - Sugerir agregarlos a `.gitignore` y, si ya están trackeados, sugerir `git rm --cached <archivo>`.
   - No continuar con ninguna acción de la cadena de comandos original hasta que el usuario resuelva la situación.

## 3. Validación de contenido (no solo nombre de archivo)

Además de nombres de archivo, el agente debe hacer un chequeo rápido de contenido en los diffs staged buscando patrones típicos de secretos:
- `API_KEY=`, `SECRET=`, `TOKEN=`, `PASSWORD=`
- Cadenas que parezcan claves (`AKIA...`, `sk-...`, `ghp_...`, etc.)

Si se detecta este patrón en un archivo que **no** está en la lista de exclusión anterior, el agente debe advertir igualmente antes de commitear, mostrando la línea sospechosa (sin exponerla completa si es muy larga) y pidiendo confirmación explícita del usuario.

## 4. Nunca hacer commit automático de `.gitignore` faltante

Si detecta un archivo sensible sin trackear y sin estar en `.gitignore`, el agente debe:
1. Proponer la línea a agregar en `.gitignore`.
2. Preguntar si desea que la agregue.
3. Nunca decidir esto unilateralmente sin confirmación.

## 5. Excepción / Override

El bloqueo solo puede omitirse si el usuario lo indica de forma **explícita y en ese mismo turno**, por ejemplo:
> "sí, commitea igual el .env.example, sé lo que hago"

No se debe interpretar instrucciones genéricas previas ("hacé commit de todo") como autorización para saltear esta validación. La confirmación debe ser específica al archivo detectado.

## 6. Comandos personalizados sugeridos (OpenCode)

```
/git-status      → muestra status + diff resumido
/git-commit      → corre validación de seguridad, luego arma mensaje conventional commit
/git-push        → valida rama actual, upstream, y corre chequeo de seguridad antes de push
/git-branch <n>  → crea y cambia a una rama nueva con prefijo (feat/, fix/, chore/)
/git-safe-check  → corre solo la validación de archivos sensibles, sin ejecutar ninguna acción
```

Cada uno de estos comandos debe invocar internamente la validación de la sección 2 antes de cualquier paso que escriba en el repo o el remoto.

## 7. Resumen de la regla dura

> **Si hay un `.env` u otro archivo sensible sin resolver (sin ignorar y/o staged), el agente NO ejecuta commit, push, ni ninguna acción de git que persista cambios. Se detiene, avisa, y espera decisión del usuario.**
