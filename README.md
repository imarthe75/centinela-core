# centinela-core

Librería compartida del ecosistema Centinela (uso interno). Versión: ver `centinela_core/__init__.py`.

| Módulo | Qué hace |
|---|---|
| `centinela_core.results` | Modelo de resultado honesto: `PASSED`/`FAILED` exigen evidencia, `BLOCKED`/`NOT_EXECUTED` exigen motivo; `summarize()` calcula el % ejecutado sobre lo planeado y el % de éxito solo sobre lo ejecutado. |
| `centinela_core.test_credentials` | Credenciales de prueba por perfil en Vault (KV v2, `<namespace>/authz/<activo>`). `set_app_config()` reemplaza la configuración completa; `update_authz()` solo toca endpoints/modelo de acceso. |
| `centinela_core.api_login` | Inicio de sesión por API de un perfil; devuelve el token del cuerpo JSON o de una cabecera. Nunca registra el token ni la contraseña. |
| `centinela_core.browser` | Ejecuta un script de Playwright en un contenedor hermano; la configuración (credenciales incluidas) viaja por stdin, nunca en argv ni en variables de entorno. |

## Uso
```bash
pip install "centinela-core[vault] @ git+https://github.com/<owner>/centinela-core.git@v0.1.1"
```
`centinela-ai` lo consume como submódulo en `libs/centinela-core` (con `PYTHONPATH`), sin reconstruir imágenes.

Configuración opcional: `test_credentials.configure(namespace=..., client_factory=...)`. Por omisión: `$VAULT_NAMESPACE` (por omisión `centinela`), `$VAULT_ADDR`, `$VAULT_TOKEN`.

## Pruebas
```bash
scripts/run_tests.sh
```
Corre en un contenedor `python:3.12-slim` desechable con el repositorio montado en solo lectura. Las pruebas de credenciales usan un Vault falso en memoria (declarado en el propio archivo); las de inicio de sesión usan un servidor HTTP local real; las del navegador arrancan un contenedor hermano real y se omiten (visiblemente) si no hay Docker.

## Reglas
El repositorio sigue el marco `resident-agent-os` (ver `.agent/`, `rules/`, `verifiers/`). `python3 verifiers/run.py` revisa stubs, aislamiento de pruebas y excepciones silenciadas.
