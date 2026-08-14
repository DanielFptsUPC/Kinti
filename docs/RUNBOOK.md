# Runbook — despliegue, migración, respaldo y reversión

Procedimientos operativos del piloto. Todo lo aquí descrito opera sobre **datos
sintéticos**; ninguno de estos pasos autoriza trabajar con información real.

> **Antes de datos reales** hace falta una evaluación institucional de privacidad
> y seguridad. Ver «Puertas institucionales» al final.

---

## 1. Entorno local

```bash
docker compose up -d db          # PostgreSQL 16 con pgvector
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Unix: .venv/bin/python
cp .env.example .env                              # ajusta KINTI_JWT_SECRET
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app.seed
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verificación: `curl http://localhost:8000/health` → `{"status":"ok",...}`

---

## 2. Despliegue en Supabase

> **Estado: no ejecutado.** Este procedimiento está escrito y validado contra
> PostgreSQL 16 local con la misma extensión, pero **no** se ha ejecutado contra
> un proyecto Supabase real por falta de credenciales. Ver
> `phases/BITACORA_FASE_3.md`.

### 2.1 Preparación

1. Crear un proyecto Supabase **exclusivamente de staging**. No reutilizar uno
   que contenga datos reales.
2. Elegir región documentando latencia, costo y requisitos institucionales de
   tratamiento de datos.
3. Registrar sólo `project_ref`, región y nombres lógicos. **Nunca** versionar
   contraseñas, tokens ni `service_role key`.

### 2.2 Dos conexiones

```dotenv
# Directa: Alembic, dumps, administración. Toma locks de DDL.
KINTI_MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:...@db.<ref>.supabase.co:5432/postgres

# Runtime: FastAPI persistente. Con pool.
KINTI_DATABASE_URL=postgresql+asyncpg://postgres:...@db.<ref>.supabase.co:5432/postgres
```

- TLS obligatorio con verificación de certificado. `sslmode=disable` **prohibido**.
- Si el entorno sólo tiene IPv4, usar Supavisor en **session mode** para runtime.
- *Transaction mode* sólo se justifica en despliegue serverless, y obliga a
  desactivar prepared statements en asyncpg.
- Ajustar `pool_size` y `max_overflow` al límite real del plan, no a un valor
  copiado.

### 2.3 Migración

```bash
# 1. Respaldo del estado previo
pg_dump "$LOCAL_URL" --format=custom --file=pre-supabase.dump

# 2. Esquema desde cero
KINTI_DATABASE_URL="$KINTI_MIGRATION_DATABASE_URL" \
  .venv/Scripts/python -m alembic upgrade head

# 3. Datos sintéticos (idempotente)
.venv/Scripts/python -m app.seed

# 4. Verificar que el esquema no derivó de los modelos
.venv/Scripts/python -m pytest tests/test_migrations.py
```

**Nunca** crear tablas desde Table Editor o SQL Editor. Toda alteración va en una
migración versionada: dos fuentes de esquema divergen siempre, y la divergencia
aparece en producción.

### 2.4 Permisos

- Rol de runtime con privilegios mínimos sobre los esquemas de Kinti.
- Rol de migración separado cuando el plan lo permita.
- Revocar acceso de `anon` y `authenticated` a las tablas operativas y
  vectoriales: Kinti no usa la Data API.
- Si alguna vez se habilita la Data API, incorporar RLS y pruebas de políticas
  **antes** de exponerla.

### 2.5 Buckets

```
kinti-knowledge-sources    documentos aprobables, retención versionada
kinti-conversation-media   audios e imágenes, retención corta (24 h)
```

Ambos **privados**. El backend emite URLs firmadas de corta duración. El cliente
nunca recibe la `service_role key`.

---

## 3. Respaldo y restauración

### Plan gratuito

No hay PITR. Programar dumps lógicos externos:

```bash
pg_dump "$KINTI_MIGRATION_DATABASE_URL" \
  --format=custom --file="kinti-$(date +%Y%m%d).dump"
```

### Plan con backups

Registrar RPO, RTO y el procedimiento del proveedor.

### Restauración

```bash
# Siempre sobre una base temporal primero, nunca sobre staging compartido
createdb kinti_restore_test
pg_restore --dbname=kinti_restore_test --clean --if-exists kinti-YYYYMMDD.dump
```

> **El backup de PostgreSQL no restaura los objetos de Storage.** Las fuentes
> aprobadas necesitan respaldo separado; si se pierden, los `knowledge_chunks`
> siguen existiendo pero su documento original no.

---

## 4. Reversión

**Preferir una migración correctiva sobre un downgrade.** Un `downgrade` que
elimina columnas destruye datos que quizá ya no estén en ningún respaldo.

```bash
# Sólo sobre base temporal
alembic downgrade -1
```

Sobre staging compartido: escribir una migración nueva que revierta el cambio.

### Reversión de la Fase 3

`c442feb4e762` sólo **añade** tablas e índices; su `downgrade` los elimina sin
tocar nada de Fase 2. La extensión `vector` no se elimina: otras bases del mismo
clúster podrían usarla.

---

## 5. Trabajo periódico

```bash
.venv/Scripts/python -m app.jobs.process_continuity
```

Idempotente: correrlo diez veces deja el mismo estado que una. Apto para cron.

El riesgo **no depende** de que haya corrido: las consultas lo derivan igual con
el reloj del servidor. El job materializa inasistencias y encola avisos.

---

## 6. Rotación del proveedor de IA

1. Registrar en el ADR el identificador **GA explícito**, la región y la fecha.
   El alias `latest` está rechazado en código: un modelo que cambia bajo los pies
   invalida toda evaluación previa.
2. Ejecutar la evaluación completa:
   ```bash
   .venv/Scripts/python -m pytest tests/test_evaluation.py -s
   ```
3. Las seis puertas técnicas deben pasar **antes** de activar el proveedor.
4. Cambiar `KINTI_AI_PROVIDER` y reiniciar. Ni las rutas ni el dominio cambian.

### Cambio de modelo de embeddings

Exige **reindexado versionado**. Mezclar vectores de dimensiones o modelos
distintos es un error de datos: la columna `vector(768)` lo rechaza al insertar.

```bash
# Reprocesar cada versión publicada con el modelo nuevo, y republicar
```

---

## 7. Incidentes

| Síntoma | Causa probable | Acción |
|---|---|---|
| `AmbiguousParameterError` | parámetro `NULL` sin cast en SQL crudo | revisar `CAST(... AS text)` |
| `DuplicateTableError` al migrar | base de pruebas con tablas previas | el `conftest` las descubre y borra; verificar conexión |
| Respuestas sin citas | corpus vacío o versión retirada | `GET /knowledge/documents` y republicar |
| Abstención en todo | anclaje léxico sin coincidencias | revisar idioma del `tsvector` y el corpus |
| El proveedor de IA falla | timeout o cuota | el mensaje **se conserva**; se ofrece contacto humano |

Ante fallo del proveedor, **nunca se pierde una solicitud**: es el mismo
principio del outbox de Fase 2.

---

## 8. Puertas institucionales antes de datos reales

Ninguna de estas es una decisión del equipo de software:

- [ ] Evaluación institucional de privacidad y seguridad.
- [ ] Autorización expresa para tratar datos de pacientes.
- [ ] Revisión clínica de los textos estáticos de seguridad y transferencia.
- [ ] Definición institucional de los canales de contacto reales.
- [ ] Acuerdo sobre tratamiento transfronterizo, región y retención del proveedor
      de IA.
- [ ] Revisión del corpus de conocimiento por el área responsable.
- [ ] Definición de responsable de publicación y de revisión de alertas.
- [ ] Plan de respuesta ante incidentes con datos personales.

Este repositorio **no afirma cumplimiento normativo ni certificación**.
