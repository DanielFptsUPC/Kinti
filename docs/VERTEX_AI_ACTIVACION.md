# Activación de Vertex AI (modelo y embeddings reales)

## Estado de partida

`app/modules/assistant/vertex.py` está **escrito pero no verificado**: nunca
corrió contra el servicio real porque este entorno no tiene credenciales de
GCP. Lo que sí está probado, con un SDK simulado (`tests/test_vertex.py`), es
todo lo que lo rodea: construcción de la petición, validación de la salida,
manejo de JSON malformado, filtrado de citas inventadas. Conectar el proveedor
real no debería tocar nada fuera de ese archivo.

**Este documento no activa nada por sí solo.** Prepara el código y deja la
lista exacta de lo que falta, que es trabajo tuyo: crear el proyecto de GCP,
generar la credencial y decidir el modelo. Ese último paso — decidir qué
modelo usar — no se puede dejar en `latest`: el código lo rechaza a propósito
(`ValueError` en el arranque), porque un modelo que cambia bajo los pies
invalida cualquier evaluación previa.

## Resultado esperado

Hoy el chat de cuidadores responde con `FakeMultimodalModel`: sin inferencia
real, cita literalmente la primera oración del fragmento mejor rankeado. Tras
activar Vertex, Gemini genera la respuesta a partir de las fuentes aprobadas
—con las mismas reglas de seguridad, el mismo esquema de salida validado y la
misma exigencia de cita—, y los embeddings dejan de ser un hash determinístico
para ser semánticos de verdad.

```text
Pregunta del cuidador → orquestador → PostgresKnowledgeRetriever (sin cambios)
                                              ↓
                              VertexGeminiModel / VertexEmbeddingProvider
                                              ↓
                                    Vertex AI (proyecto de GCP)
```

## Lo que debes preparar

- un proyecto de GCP con facturación activa;
- la API de Vertex AI habilitada en ese proyecto;
- una service account con el rol `roles/aiplatform.user` (no uses una cuenta
  con más permisos de los necesarios);
- la clave JSON de esa service account, descargada una sola vez;
- decidir un modelo Gemini **GA** (no `-latest`, no vista previa) y una región;
- decidir un modelo de embeddings de Vertex AI compatible con salida de 768
  dimensiones (la columna `vector(768)` de `knowledge_chunks` es fija).

Nunca compartas el contenido de la clave JSON por chat, captura o repositorio.
Va directo al panel de Render, como con `TWILIO_AUTH_TOKEN`.

## Paso 1 — proyecto, API y service account

1. Crea o elige un proyecto de GCP y activa facturación.
2. Habilita la API: **Vertex AI API** (`aiplatform.googleapis.com`).
3. IAM → Service Accounts → crear una nueva, con rol **Vertex AI User**
   (`roles/aiplatform.user`). No le des `Owner` ni `Editor`.
4. En esa cuenta → Keys → Add key → JSON. Descarga el archivo una vez; Google
   no permite volver a descargarlo, sólo revocar y crear una nueva clave.
5. Anota el `project_id` (aparece dentro del propio JSON, campo
   `"project_id"`) y elige una región donde Vertex AI esté disponible para el
   modelo que quieras (`us-central1` es la más ampliamente soportada si no
   tienes una razón para elegir otra, por ejemplo residencia de datos).

## Paso 2 — elegir el modelo

Verifica en el **Model Garden** de Vertex AI cuáles son los modelos Gemini
**GA** disponibles en tu región al momento de activar esto — la disponibilidad
cambia con el tiempo y no se puede fijar aquí. Como punto de partida razonable
para este caso de uso (respuestas cortas, salida JSON estructurada, sin
necesidad de razonamiento profundo): la familia **Gemini Flash** más reciente
en estado GA. Evita cualquier identificador que termine en `-latest`,
`-preview` o `-exp`: el código los rechaza si terminan en `latest`, y los
`-preview` no dan la estabilidad que exige haber corrido una evaluación una
vez y confiar en que siga significando lo mismo después.

Para embeddings: un modelo `text-embedding-*` de Vertex AI con
`output_dimensionality` configurable a 768 (el código ya lo pide
explícitamente en cada llamada).

## Paso 3 — cargar los secretos en Render

En el dashboard de `kinti-api` → Environment, añade:

```text
KINTI_AI_PROJECT=<project_id del JSON>
KINTI_AI_MODEL_ID=<identificador GA exacto>
KINTI_AI_REGION=<región elegida>
KINTI_EMBEDDING_MODEL_ID=<modelo de embeddings elegido>
GOOGLE_APPLICATION_CREDENTIALS_JSON=<pega aquí el JSON completo, tal cual>
```

`render.yaml` ya declara estas cinco claves con `sync: false` — el archivo
reserva el nombre, el valor lo pones tú en el panel. `docker-entrypoint.sh`
escribe `GOOGLE_APPLICATION_CREDENTIALS_JSON` a `/tmp/gcp-credentials.json` y
apunta `GOOGLE_APPLICATION_CREDENTIALS` ahí antes de arrancar — Render no tiene
un mecanismo nativo de "montar secreto como archivo".

Mantén `KINTI_AI_PROVIDER=fake` y `KINTI_EMBEDDING_PROVIDER=fake` mientras
cargas y confirmas estos cinco valores. Cambiarlos a `vertex` es el último
paso, no el primero — si falta uno solo, `providers.py` se niega a construir
el proveedor con un mensaje explícito en vez de arrancar a medias.

## Paso 4 — activar y reindexar

1. Cambia `KINTI_AI_PROVIDER=vertex` y `KINTI_EMBEDDING_PROVIDER=vertex`.
   Desplegar con una variable faltante debe fallar el arranque, no servir con
   el proveedor equivocado — eso ya está probado.
2. Tras el despliegue, **reindexa el corpus**:

   ```text
   python -m app.seed_knowledge --reindex
   ```

   Es un paso obligatorio, no cosmético: los `knowledge_chunks` ya publicados
   tienen vectores del proveedor `fake` (un hash del texto, no un embedding
   semántico). El texto de los documentos no cambia sólo porque cambie quién
   los embebe, así que sin `--reindex` la deduplicación por checksum saltaría
   el reprocesamiento y las búsquedas semánticas seguirían comparando contra
   vectores viejos indefinidamente.

## Paso 5 — evaluar antes de declarar «integrado»

El documento de Fase 3 (§1.7) lo prohíbe explícitamente: un modelo no puede
llamarse «integrado» sólo porque el código compila contra el SDK real. Antes
de eso:

1. Corre la evaluación del §20 (`tests/test_evaluation.py`) con
   `KINTI_AI_PROVIDER=vertex` apuntando al proyecto real, no al proveedor fake.
2. Registra en `docs/adr/0002-supabase-rag-multimodal.md` (o una entrada nueva)
   el identificador exacto del modelo, la región y la fecha de la evaluación.
3. Sólo entonces se puede decir que el modelo está integrado y evaluado, no
   sólo conectado.

## Costos

Vertex AI cobra por token de entrada/salida (Gemini) y por token de entrada
(embeddings); no hay un nivel gratuito indefinido más allá del crédito inicial
de GCP. Antes de activar en producción, fija un presupuesto y una alerta de
facturación en el proyecto de GCP — el mismo principio que ya se aplicó a
Twilio en Kinti Voz: nada con costo variable se activa sin un límite explícito.
