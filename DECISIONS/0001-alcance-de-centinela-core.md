# ADR-0001 — Alcance de centinela-core

**Estado:** ACEPTADO (2026-10-15)

## Decisión
`centinela-core` contiene solo piezas con al menos dos usuarios reales en el ecosistema. v0.1.0:
- `test_credentials` (centinela-ai: auditorías multi-rol, credenciales de pruebas; centinela-smart-tests: inicio de sesión de cada perfil).
- `api_login` (centinela-ai: auditoría de autorización; centinela-smart-tests).
- `browser` (centinela-ai: auditoría de sesión y accesibilidad renderizada; centinela-smart-tests).
- `results` (centinela-smart-tests: resultado por caso; centinela-ai: valida los resultados que recibe por su endpoint de ingesta).

## Fuera de alcance
El modelo de hallazgos de Centinela (`vulnerability_log`, deduplicación por huella, SLA, CRS, correlación de incidentes). Un caso de prueba pasa o falla en una ejecución; no es un hallazgo que se resuelve con una huella persistente.

## Cambio respecto al origen
`test_credentials.update_authz()` es nuevo: actualiza solo endpoints/modelo de acceso. En `centinela-ai` un script que usó `set_app_config()` solo para cambiar endpoints borró `app_login` y `login_ui` (reemplazo completo por diseño, pensado para un formulario que envía todos los campos).

## Consumo
- `centinela-ai`: submódulo en `libs/centinela-core` con URL relativa (`../centinela-core.git`, resuelve en GitLab y en GitHub) y `PYTHONPATH`. Sus módulos originales quedan como capa fina que reexporta, para no tocar a sus llamadores ni a sus pruebas.
- Otros: `pip install` desde la etiqueta de versión.
