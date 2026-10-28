# Skill: Writing Plans

**Origen:** Adaptado de [obra/superpowers](https://github.com/obra/superpowers) — MIT License  
**Aplica a:** Cualquier feature o cambio que requiera más de 1 archivo o 15 min de trabajo

---

## Para qué sirve

Un plan convierte un objetivo en tareas independientes, verificables y de 2-5 minutos cada una. Elimina la ambigüedad antes de escribir código y permite que subagentes ejecuten con contexto mínimo.

---

## Cuándo crear un plan

- Feature nueva con múltiples capas (DB + backend + frontend)
- Refactor que toca más de 3 archivos
- Migración de datos o esquema
- Integración de servicio externo
- Cualquier cambio donde no es obvio el orden de pasos

---

## Estructura del plan

Guardar en `docs/plans/YYYY-MM-DD-<nombre-feature>.md`:

```markdown
# Plan: [Nombre del Feature]
**Fecha:** YYYY-MM-DD
**Objetivo:** [Una oración de qué se va a construir y por qué]
**Arquitectura:** [Qué capas toca: DB / backend / frontend / infra]
**Stack:** [Python 3.12, FastAPI, Angular 18, PostgreSQL 18, Valkey]
**Restricciones:** [UUID v7, audit triggers, OIDC auth, etc.]

---

## Mapa de archivos

| Archivo | Acción | Propósito |
|---------|--------|-----------|
| `backend/app/models/nuevo.py` | crear | Modelo SQLAlchemy |
| `backend/app/routers/nuevo.py` | crear | Endpoints FastAPI |
| `db/migrations/NNN_nuevo.sql` | crear | Migración |
| `frontend/src/app/nuevo/` | crear | Componente Angular |

---

## Tarea 1: [Nombre corto]
**Archivos:** `backend/app/models/nuevo.py`
**Input:** ninguno
**Output:** clase `NuevoModel` con campos X, Y, Z

**Pasos:**
- [ ] Escribir test: `pytest tests/test_nuevo.py::test_modelo` → FAIL
- [ ] Implementar modelo con UUID v7 PK
- [ ] Verificar: `pytest tests/test_nuevo.py::test_modelo` → PASS
- [ ] Commit: `feat(models): add NuevoModel with uuid v7 pk`

---

## Tarea 2: ...
```

---

## Principios de granularidad

- Cada tarea: **1 unidad de trabajo verificable** (un test que pasa = tarea completa)
- Cada tarea: máximo **2-5 minutos** de implementación
- Cada tarea incluye: **comando exacto de verificación**
- Las tareas son **independientes** o tienen dependencias explícitas

---

## Restricciones mandatorias en planes

Todo plan debe contemplar las restricciones del proyecto (las de abajo son un ejemplo: cámbialas por las vuestras y, si tienen verificador, cítalo, ver `verifiers/`):
1. **PKs UUID v7** en tablas nuevas
2. **Audit triggers** en tablas con mutaciones
3. **Auth middleware** en endpoints sensibles
4. **Test antes de código** (TDD obligatorio)
5. **Verificación de salud** al final del plan

---

## Modos de ejecución

Al guardar el plan, proponer al usuario:

**A) Subagent-Driven (recomendado para planes >5 tareas)**  
→ Un subagente fresco por tarea, con review entre tareas  
→ Ver `agents/architect.md` para el workflow

**B) Inline (para planes ≤5 tareas simples)**  
→ El agente ejecuta las tareas en secuencia en la misma sesión  
→ Checkpoint de verificación entre cada tarea

---

## Skills relacionados

- **test-driven-development**: Cada tarea del plan sigue el ciclo RED-GREEN-REFACTOR
- **verification-before-completion**: Verificar antes de marcar cada tarea como completada
- **opsx-propose**: Crear el spec formal antes de escribir el plan
