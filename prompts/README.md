# Biblioteca de prompts

Cada prompt que el agente usa de forma recurrente vive aquí como archivo versionado, con dueño y con su origen. Reglas:

- **Un prompt se deriva de su fuente** (una guía de oficio, un estándar), nunca al revés: si cambia la guía, el prompt se vuelve a derivar y sube de versión.
- **Cabecera obligatoria** (validada por `python scripts/check_prompts.py`): `id`, `version` (semver), `owner`, `derived_from` (archivo que existe),
  `eval_set` (ruta a su conjunto de casos, o `none` dicho explícitamente) y `last_reviewed` (AAAA-MM-DD).
- **Un prompt sin conjunto de evaluación se declara así** (`eval_set: none`); no se finge que está probado.
- El texto del prompt no incluye datos de clientes ni secretos; los datos entran como variables `{{nombre}}` y se tratan como **datos no confiables**.
- La salida de un prompt que alimenta un entregable pasa por validación humana registrada (`agent/human_validation.py`).
