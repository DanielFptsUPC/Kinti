# ADR 0002 — Supabase, RAG y asistente multimodal (Fase 3)

- **Estado:** aceptado
- **Fecha:** 2026-08-13
- **Contexto:** `phases/KINTI_FASE_3_SUPABASE_IA_CODEX.md`
- **No modifica** `0001-arquitectura-fase-2.md`; lo extiende.

## Contexto

La Fase 2 dejó un piloto conectado con PostgreSQL local, sincronización offline
e idempotencia probada. Quedan tres brechas: no hay base administrada
reproducible, no hay conocimiento institucional versionado con recuperación por
fuentes, y la familia no puede conversar por texto, audio o imagen.

Esta fase las cierra **sin** convertir la IA en autoridad clínica y **sin** que
el cliente móvil toque datos sensibles directamente.

---

## 1. Supabase como PostgreSQL administrado de staging

Supabase reemplaza el **host** de PostgreSQL. No reemplaza el dominio, la API ni
los repositorios móviles.

*Por qué:* aporta base administrada, `pgvector`, Storage privado y respaldos sin
introducir un modelo de datos nuevo. El desarrollo local sigue con
`pgvector/pgvector:pg16`, la misma extensión y versión mayor, para que lo que se
prueba en local sea lo que corre en remoto.

*Compromiso:* dependencia de un proveedor. Se acota manteniendo Alembic como
fuente del esquema y evitando toda función propietaria de Supabase en el dominio.

## 2. Alembic es la única fuente de verdad del esquema

Nada se crea desde Table Editor ni SQL Editor. No hay migraciones paralelas de
Supabase CLI.

*Por qué:* dos fuentes de esquema divergen siempre, y la divergencia aparece en
producción. `test_migrations.py` ya compara metadatos SQLAlchemy contra el
esquema real; esa prueba pierde todo valor si alguien toca el dashboard.

## 3. Dos conexiones con finalidades distintas

```dotenv
KINTI_MIGRATION_DATABASE_URL=   # directa: Alembic, dumps, administración
KINTI_DATABASE_URL=             # runtime: FastAPI persistente
```

*Por qué:* Alembic toma locks de DDL y necesita una conexión directa y estable;
el runtime necesita pool. Además permite dar al rol de aplicación privilegios
menores que al de migración.

Para un FastAPI persistente se usa conexión directa (o Supavisor en *session
mode* si el entorno sólo tiene IPv4). *Transaction mode* sólo se justificaría en
un despliegue serverless, y obligaría a desactivar prepared statements en
asyncpg.

TLS obligatorio con verificación de certificado. `sslmode=disable` está prohibido.

*Compromiso:* dos variables que mantener sincronizadas. Se documentan juntas en
`.env.example` y el arranque falla ruidosamente si falta la de runtime.

## 4. FastAPI sigue siendo la única frontera del cliente móvil

La aplicación **nunca** se conecta a las tablas de Supabase, ni siquiera a las de
conocimiento. No recibe `service_role key` ni contraseña de base.

*Por qué:* toda la autorización por vínculo y asignación vive en el dominio. Un
acceso directo desde el cliente la puentearía por completo, y RLS tendría que
reimplementar reglas que ya existen y están probadas.

## 5. Permisos de base y Storage

- Rol de runtime con privilegios mínimos sobre los esquemas de Kinti.
- Rol de migración separado cuando el plan lo permita.
- `anon` y `authenticated` sin acceso a tablas operativas ni vectoriales.
- Buckets privados: `kinti-knowledge-sources` y `kinti-conversation-media`.
- URLs firmadas de corta duración; jamás URLs públicas permanentes.

## 6. Embeddings: dimensión 768, explícita y versionada

*Por qué:* equilibrio entre calidad y almacenamiento para un corpus institucional
pequeño. El identificador de modelo y la dimensión se guardan **en cada chunk**.

*Compromiso:* cambiar de modelo o dimensión exige reindexado versionado. Mezclar
vectores de dimensiones distintas es un error de datos, no una degradación
elegante — por eso la columna es `vector(768)` y la incompatibilidad falla al
insertar, no en silencio.

## 7. Búsqueda híbrida con fusión RRF

Léxica (`tsvector` en español) + semántica (`pgvector`), fusionadas con
Reciprocal Rank Fusion.

*Por qué:* la léxica acierta en términos institucionales exactos («SIS»,
«consentimiento») y falla ante paráfrasis; la semántica hace lo contrario. RRF
combina rangos sin necesidad de calibrar puntajes entre dos escalas que no son
comparables.

Filtros **obligatorios y no negociables** antes de cualquier ranking: estado
`published`, vigencia, audiencia, idioma. Un documento retirado o en borrador no
puede aparecer, y eso se comprueba en el repositorio, no en el prompt.

## 8. RAG y datos operativos son fuentes separadas

RAG contiene conocimiento institucional general. **Nunca** hitos, barreras,
sentimientos, notas ni conversaciones.

*Por qué:* dos razones. Un embedding no sabe de permisos: indexar datos de un
paciente los volvería recuperables por similitud desde otra sesión. Y los datos
operativos cambian —una cita se reprograma— mientras un índice vectorial refleja
el momento en que se generó.

«¿Cuándo es mi próxima cita?» se responde con el servicio de dominio autorizado.

## 9. Puertos para todo lo sustituible

```python
MultimodalModel · EmbeddingProvider · DocumentExtractor
KnowledgeRetriever · MediaStorage
```

*Por qué:* el proveedor de IA es la pieza más volátil del sistema. Detrás de un
puerto se reemplaza sin tocar rutas, casos de uso ni dominio, y las pruebas
corren con implementaciones determinísticas sin red.

## 10. Modelo multimodal: fake por defecto, Vertex como real

`KINTI_AI_PROVIDER=fake` es el valor por defecto. La implementación real es
Vertex AI con un modelo GA, identificador explícito y región registrada.

*Por qué el fake por defecto:* que un despliegue mal configurado no empiece a
gastar dinero ni a enviar datos a un tercero por omisión. Activar el proveedor
real es una decisión consciente.

Prohibido el alias `latest`: un modelo que cambia bajo los pies invalida toda
evaluación previa.

## 11. Retención

- Medios conversacionales: retención corta, borrado programado.
- Fuentes aprobadas: retención versionada, no se borran al publicar una versión
  nueva — la anterior se **retira**, para que la evidencia histórica siga siendo
  explicable.
- No se persiste cadena de pensamiento.
- El texto conversacional no se duplica en auditoría ni en logs.

## 12. Seguridad, abstención y transferencia humana

- Sin evidencia suficiente → `insufficient_evidence` y abstención explícita.
  Nunca una respuesta improvisada.
- Toda respuesta informativa incluye citas verificables; sin citas válidas no se
  muestra.
- `clinical_or_safety_concern` activa un **texto institucional estático
  aprobado** y transferencia humana. Esa ruta es determinística: no la decide el
  modelo.
- El modelo **propone**; FastAPI valida autorización, esquema, confirmación e
  idempotencia. Ninguna escritura ocurre sin confirmación explícita del usuario.
- Nada de SQL generado por el modelo, ni acceso libre a repositorios.

*Por qué determinística la ruta clínica:* si la seguridad dependiera de que el
modelo se comporte, sería probabilística. Un clasificador con 0,95 de acierto
falla una de cada veinte veces, y aquí ese fallo es inaceptable.

## 13. Costos y resiliencia

Límites configurables de texto, imagen, audio, tokens y archivos diarios.
Timeout, reintentos acotados, backoff y circuit breaker.

Si el proveedor cae, **el mensaje se conserva** y se ofrece contacto humano.
Nunca se pierde una solicitud: es el mismo principio del outbox de Fase 2.

Los documentos se embeben una sola vez por checksum y versión.

## 14. Estrategia offline para mensajes conversacionales

Los mensajes se encolan en el outbox existente. Sin conexión se ofrece contenido
aprobado precargado y se encola la consulta.

**Jamás se simula que el modelo respondió.** Un mensaje pendiente se muestra como
pendiente.

---

## Consecuencias

- El desarrollo local necesita `pgvector/pgvector:pg16`, no `postgres:16-alpine`.
- El esquema crece con tablas de conocimiento, conversación, evidencia y
  seguridad, todas por Alembic.
- La aplicación gana una pantalla conversacional sin perder el modo local.
- Aparecen dos dependencias externas —Supabase y un proveedor de IA— y ambas
  quedan detrás de configuración y puertos.

## Fuera de alcance

Datos reales, diagnóstico, triaje, prescripción, interpretación de resultados
clínicos, historia clínica, FHIR, SSO, WhatsApp/SMS, fine-tuning con
conversaciones, agentes autónomos, SQL generado por el modelo, microservicios,
video y voz en tiempo real. Este documento no afirma cumplimiento normativo.
