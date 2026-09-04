---
trigger: always_on
---

# Codificación de archivos frontend

- Guarda los archivos de texto del proyecto en UTF-8.
- Respeta la codificación exigida por el framework detectado; por ejemplo, usa UTF-8 con BOM (`utf-8-sig`) para vistas Razor cuando el proyecto lo requiera.
- Después de editar archivos con requisitos especiales de codificación, valida sus bytes y evita conversiones implícitas del sistema operativo.
