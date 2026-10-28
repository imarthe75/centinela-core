---
name: clean-code-contract
description: Contrato de generación de código para agentes de IA: lo que se aplica antes de escribir, durante y antes de entregar para que el código no contenga errores ni vulnerabilidades detectables.
---

# Contrato de código limpio

**Cuándo aplicar:** siempre que generes o modifiques código de una aplicación.

## Antes de escribir
1. Identifica el stack (backend Java/Python, frontend Angular/React, SQL, Docker/CI) y aplica de memoria `rules/<stack>/` y `rules/common/`.
2. Escribe primero la prueba: un caso que debe fallar y otro que debe pasar (`skills/test-driven-development`).

## Qué no se escribe (resumen; el detalle está en `rules/common/security.md` y `rules/common/error-handling.md`)
| Evita | Haz esto |
|---|---|
| SQL por concatenación, f-string o `%` | parámetros enlazados |
| `eval`/`exec`, `os.system`, `shell=True` | lista de argumentos con `shell=False`; datos con `json`/`ast.literal_eval` |
| deserialización de datos no confiables (`pickle`, serialización JDK) | JSON con esquema |
| rutas de archivo del usuario sin normalizar | resolver la ruta y comprobar que queda bajo el directorio base |
| URL dada por el usuario sin validar | lista de hosts permitidos; bloquear rangos privados |
| secretos, tokens o contraseñas en el código | variables de entorno o gestor de secretos |
| endpoints o webhooks sin autenticación ni autorización | dependencia de autenticación; el permiso se valida en el servidor, no solo en la interfaz |
| `except Exception` que traga el error | registrar con traza o relanzar |
| `TODO`, `pass`, funciones vacías | implementar o declarar el componente como PARCIAL |
| contenedor como root, imagen `latest`, `curl \| sh` | `USER` no root, versión fija, descargar-verificar-ejecutar |
| HTML sin etiquetas accesibles (`alt`, `label`, `lang`) | texto alternativo, etiquetas y atributos de accesibilidad |
| `any` en TypeScript, `setTimeout` para sincronizar, métodos pesados en plantillas | tipos reales, señales/`computed` |
| pruebas que borran datos compartidos | base desechable y variables de prueba exclusivas |

## Antes de entregar
1. Corre las pruebas y `python verifiers/run.py`; lee el `git diff` real.
2. Si el proyecto cuenta con un escáner de seguridad, ejecútalo sobre tus cambios y corrige hasta cero hallazgos nuevos. Si no puedes ejecutarlo, escribe «no verificado por un escáner».
3. Declara los límites: lo que ese escáner no cubre (pruebas dinámicas, TLS, configuración de servidores) queda como no verificado.
4. Entrega con el formato de `rules/common/honesty.md` §5 (estado, matriz de evidencia, salida real, deuda).
