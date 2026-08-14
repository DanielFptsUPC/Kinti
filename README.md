# Kinti — piloto conectado de continuidad hematológica

**Kinti es el compañero digital de la ruta hematológica pediátrica.** Muestra a
cada familia cuál es su siguiente paso, permite avisar si no podrá cumplirlo y
ayuda al equipo asistencial a intervenir antes de que se pierda la continuidad.

> **Prototipo — datos ficticios.** No usa información real de pacientes, no se
> conecta a sistemas del INSNSB y no diagnostica, prescribe ni realiza triaje.
> El semáforo representa **riesgo operativo de interrupción de la ruta**, nunca
> gravedad clínica.

- **Fase 1** (`phases/KINTI_FASE_1_CODEX.md`): prototipo navegable en un solo
  dispositivo. Sigue funcionando como **modo local**.
- **Fase 2** (`phases/KINTI_FASE_2_CODEX.md`): piloto conectado con API,
  PostgreSQL, sesión, caché offline y sincronización entre dispositivos.
- **Fase 3** (`phases/KINTI_FASE_3_SUPABASE_IA_CODEX.md`): base de conocimiento
  versionada con `pgvector`, búsqueda híbrida con citas y asistente
  conversacional con política de seguridad determinística.

| Documento | Qué contiene |
|---|---|
| [`docs/adr/0001`](docs/adr/0001-arquitectura-fase-2.md) | Decisiones de la Fase 2 |
| [`docs/adr/0002`](docs/adr/0002-supabase-rag-multimodal.md) | Decisiones de Supabase, RAG y multimodalidad |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Despliegue, migración, respaldo, reversión e incidentes |
| [`phases/BITACORA_FASE_2.md`](phases/BITACORA_FASE_2.md) | Comandos y resultados de la Fase 2 |
| [`phases/BITACORA_FASE_3.md`](phases/BITACORA_FASE_3.md) | Comandos, resultados y bloqueos de la Fase 3 |

---

## Los dos modos de ejecución

La misma aplicación corre en dos modos, elegidos por variable de entorno. No hay
pantallas duplicadas: la diferencia se resuelve detrás de un repositorio.

| | Modo local | Modo conectado |
|---|---|---|
| Variable | `EXPO_PUBLIC_DATA_MODE=local` (por defecto) | `EXPO_PUBLIC_DATA_MODE=remote` |
| Backend | no necesita | FastAPI + PostgreSQL |
| Acceso | selector de perfil de demostración | inicio de sesión; el rol lo decide el servidor |
| Datos | AsyncStorage (estado de Fase 1) | SQLite (caché + outbox) sincronizado con la API |
| Uso | respaldo de la demostración | piloto técnico y guion de Fase 2 |

---

## Instalación y ejecución

### Modo local (sin backend)

Requiere Node.js 20+ y la app **Expo Go**.

```bash
npm ci
npm start
```

Escanea el QR con Expo Go. La app abre en el selector de perfil de demostración.

### Modo conectado (piloto completo)

Necesita además **Docker** (para PostgreSQL) y **Python 3.12+**.

```bash
# 1. Base de datos
docker compose up -d db

# 2. Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"    # Linux/macOS: .venv/bin/python
cp .env.example .env                                # ajusta KINTI_JWT_SECRET
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m app.seed
.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. Aplicación, en otra terminal
cd ..
EXPO_PUBLIC_DATA_MODE=remote EXPO_PUBLIC_API_URL=http://TU_IP_LOCAL:8000 npm start
```

`TU_IP_LOCAL` debe ser la IP de tu máquina en la red (no `localhost`): el celular
tiene que poder alcanzarla. Añádela también a `KINTI_CORS_ORIGINS` si usas web.

Documentación interactiva de la API: <http://localhost:8000/api/v1/docs>.

### Al cambiar de modo, limpia la caché de Metro

Las variables `EXPO_PUBLIC_*` **no se leen en tiempo de ejecución**: Expo CLI
sustituye cada `process.env.EXPO_PUBLIC_*` por su valor al transformar el código,
y Metro guarda el resultado en caché.

Si defines las variables en un archivo `.env`, Expo detecta el cambio y basta con
recargar la app. Pero si las pasas por la **línea de comandos** —como en los
ejemplos de arriba— no hay archivo que vigilar: Metro reutiliza el módulo ya
transformado con el valor anterior, y la aplicación arranca en el modo
equivocado. El síntoma típico es ver el inicio de sesión cuando esperabas el
selector de perfil.

Al alternar entre modos por línea de comandos, añade `--clear`:

```bash
npx expo start --clear           # local
npx expo start --tunnel --clear  # local, por túnel
```

Sólo hace falta la primera vez tras el cambio. Si prefieres evitarlo del todo,
define las variables en un `.env` en la raíz del proyecto.

### Cuentas sintéticas

Creadas por `python -m app.seed`. Contraseña común: `Kinti.Demo.2026`
(configurable con `KINTI_SEED_PASSWORD`).

| Correo | Rol | Ve |
|---|---|---|
| `cuidador.mateo@kinti.demo` | cuidador | sólo a Mateo |
| `cuidador.lucia@kinti.demo` | cuidador | sólo a Lucía |
| `equipo@kinti.demo` | equipo asistencial | los tres pacientes asignados |

El niño **no tiene credenciales propias**: entra a su experiencia desde la sesión
del cuidador vinculado.

---

## Variables de entorno

### Aplicación (`EXPO_PUBLIC_*`, incrustadas en el bundle)

| Variable | Por defecto | Para qué |
|---|---|---|
| `EXPO_PUBLIC_DATA_MODE` | `local` | `local` o `remote` |
| `EXPO_PUBLIC_API_URL` | `http://localhost:8000` | raíz del backend |

Nunca pongas secretos aquí: cualquier valor `EXPO_PUBLIC_*` viaja dentro de la
aplicación y es legible.

### Backend (prefijo `KINTI_`, ver `backend/.env.example`)

| Variable | Por defecto | Para qué |
|---|---|---|
| `KINTI_DATABASE_URL` | `postgresql+asyncpg://kinti:kinti@localhost:5433/kinti` | PostgreSQL |
| `KINTI_JWT_SECRET` | valor de desarrollo | firma de tokens — **cámbialo** |
| `KINTI_ACCESS_TOKEN_MINUTES` | `30` | vida del token de acceso |
| `KINTI_REFRESH_TOKEN_DAYS` | `14` | vida del token de refresco |
| `KINTI_BARRIER_RESPONSE_WINDOW_HOURS` | `48` | antes de que una barrera abierta escale a rojo |
| `KINTI_MISSED_TOLERANCE_HOURS` | `6` | tolerancia antes de marcar inasistencia |
| `KINTI_CORS_ORIGINS` | `http://localhost:8081,…` | orígenes permitidos |
| `KINTI_SEED_PASSWORD` | `Kinti.Demo.2026` | contraseña de las cuentas sintéticas |
| `KINTI_ENVIRONMENT` | `local` | habilita utilidades de desarrollo |

---

## Arquitectura

```
kinti-mobile/
├── app/                        Rutas de Expo Router
│   ├── index.tsx                 Selector de perfil (local) o redirección (conectado)
│   ├── login.tsx                 Inicio de sesión del piloto
│   ├── notifications.tsx         Centro de avisos interno
│   ├── caregiver/                Inicio · Mi ruta · Ayuda · Perfil
│   ├── child/                    Mi aventura · Cómo me siento
│   └── care-team/                Resumen · Pacientes · Alertas
│
├── src/
│   ├── config/env.ts             Modo de datos y URL de la API
│   ├── domain/
│   │   ├── entities/             Entidades y tipos del dominio
│   │   └── repositories/         Puerto `KintiRepository` y `SyncPort`
│   ├── application/
│   │   ├── ports/                Interfaces que consumen los casos de uso
│   │   └── use-cases/            Sesión y migración desde Fase 1
│   ├── infrastructure/
│   │   ├── api/                  Cliente HTTP + contrato OpenAPI
│   │   ├── auth/                 Tokens en SecureStore
│   │   ├── database/             Esquema SQLite, migraciones, caché y outbox
│   │   ├── repositories/         LocalRepository · RemoteRepository
│   │   ├── sync/                 Motor de sincronización
│   │   └── container.ts          Único punto que elige el modo
│   ├── logic/                    Reglas de riesgo y alertas (referencia probada)
│   ├── state/store.ts            Fachada de presentación (Zustand)
│   ├── components/               Componentes reutilizables
│   └── testing/                  SQLite en memoria para las pruebas
│
├── backend/
│   ├── app/
│   │   ├── api/v1/               Rutas HTTP y esquemas del contrato
│   │   ├── modules/              identity · patients · care_routes · milestones
│   │   │                         alerts · interventions · feelings · audit
│   │   │                         notifications · sync
│   │   ├── core/                 Configuración, base de datos, seguridad, tiempo
│   │   ├── jobs/                 Trabajo periódico de continuidad
│   │   ├── seed.py               Datos sintéticos reproducibles
│   │   └── main.py
│   ├── alembic/                  Migraciones
│   └── tests/                    Pytest contra PostgreSQL real
│
├── docker-compose.yml            PostgreSQL local (puerto 5433)
└── docs/adr/                     Decisiones de arquitectura
```

### El servidor manda sobre lo derivado

`operational_risk` y `route_status` **no se guardan en la base**. Se calculan en
cada consulta, con el reloj del servidor, a partir de los hitos y las alertas.
Lo que el cliente mande se ignora.

- **Verde:** hito confirmado y sin barreras.
- **Amarillo:** hito pendiente de confirmación, o barrera abierta o en gestión.
- **Rojo:** inasistencia registrada, o barrera abierta que superó las 48 horas
  configuradas.

Las mismas reglas viven en `src/logic/risk.ts` (cliente) y
`backend/app/modules/care_routes/rules.py` (servidor), y
`backend/tests/test_rules_parity.py` traduce caso por caso las pruebas de
TypeScript para que no puedan divergir.

### Cómo sobrevive una solicitud sin conexión

1. El comando se valida localmente y se aplica **optimistamente** a la caché, así
   que la interfaz responde de inmediato.
2. Se encola en `outbox_operations` con un `operationId` UUID.
3. Al recuperar conexión, el lote se envía en orden a `POST /sync/operations`.
4. El servidor responde por operación: `applied`, `already_applied` o `rejected`.
5. El cliente recupera la instantánea canónica y reemplaza su caché completa.

**Nada se pierde y nada se duplica.** La unicidad de `operation_id` en
`processed_operations` es lo que garantiza que un reenvío no aplique nada dos
veces. Borrar la caché nunca borra el outbox: una solicitud de ayuda que el
servidor todavía no conoce no se descarta jamás en silencio.

Una operación rechazada por permisos o validación deja de reintentarse sola pero
**queda visible**, para que nadie crea que su solicitud fue registrada.

### Contrato de la API

Todo bajo `/api/v1`, documentado en OpenAPI.

```
POST /auth/login          POST /auth/refresh        POST /auth/logout    GET /me
GET  /patients/{id}/route
POST /milestones/{id}/confirmations                 POST /milestones/{id}/barriers
POST /patients/{id}/feelings
GET  /care-team/overview  GET  /care-team/patients  GET  /care-team/alerts
GET  /alerts/{id}         POST /alerts/{id}/contact POST /alerts/{id}/resolve
POST /patients/{id}/milestones                      POST /milestones/{id}/reschedule
GET  /notifications       POST /notifications/{id}/read
GET  /sync/bootstrap      POST /sync/operations
```

`src/infrastructure/api/openapi.json` es el contrato congelado que verifica
`src/infrastructure/api/__tests__/contract.test.ts`. Regenéralo con
`npm run api:contract` cada vez que cambie un DTO del backend.

---

## Datos de demostración

Definidos en `backend/app/seed.py` (conectado) y `src/data/seed.ts` (local), con
entre 4 y 6 hitos por paciente.

| Paciente | Edad | Semáforo | Situación |
|---|---|---|---|
| Lucía | 8 | 🟢 Verde | Próximo control confirmado |
| Mateo | 11 | 🟡 Amarillo | Próximo control pendiente de confirmación |
| Valentina | 6 | 🔴 Rojo | Control vencido, inasistencia pendiente de contacto |

Mateo arranca **sin** barrera precargada, a propósito: así reportar "Transporte"
durante el guion crea la alerta en vivo y se ve el circuito completo.

`python -m app.seed` es idempotente: si los usuarios ya existen, no duplica nada.

En **modo local**, *Perfil → Restaurar datos de demostración* reinicia el estado.
Esa opción **no existe en modo conectado**: nunca se expone un reinicio general
contra un backend.

---

## Trabajo periódico de continuidad

```bash
cd backend
.venv/Scripts/python -m app.jobs.process_continuity
```

Marca hitos vencidos como inasistencia, encola avisos y detecta barreras que
superaron la ventana de respuesta. Es **idempotente**: correrlo diez veces deja
el mismo estado que correrlo una. Pensado para cron o un programador externo.

El riesgo **no depende de que este trabajo haya corrido**: las consultas lo
derivan igual con el reloj del servidor. El job materializa la inasistencia y
avisa, no hace funcionar el semáforo.

---

## Asistente conversacional (Fase 3)

La pestaña **Kinti** del cuidador permite preguntar por texto, grabar un mensaje
de voz o enviar un documento administrativo.

### Cómo decide qué responder

```text
seguridad → datos operativos → RAG → abstención
```

1. **La política de seguridad corre primero** y puede cortocircuitar todo lo
   demás. Es determinística: si dependiera de que un modelo se comporte, sería
   probabilística, y un clasificador con 0,95 de acierto falla una de cada veinte
   veces. Aquí ese fallo significa responder sobre una dosis.
2. **Datos personales desde el dominio autorizado**, nunca desde embeddings.
   «¿Cuándo es mi próxima cita?» lee la fuente viva: una cita se reprograma, un
   vector conserva el momento en que se generó.
3. **Preguntas informativas por RAG**, siempre con citas verificables. Sin citas
   válidas, la respuesta no se muestra.
4. **Sin evidencia, abstención explícita.** Nunca una respuesta improvisada.

### Lo que el asistente no hace

- No diagnostica, no prescribe, no indica dosis, no interpreta resultados.
- No evalúa urgencias ni decide gravedad.
- **No escribe nada por su cuenta**: propone una acción y espera confirmación.
- No muestra cadena de pensamiento, puntajes ni «porcentajes de diagnóstico».
- No se presenta como médico ni como servicio de emergencia.

Recetas, hemogramas y lesiones se **derivan sin interpretar**, y la imagen se
corta en el propio teléfono antes de subirse.

### Base de conocimiento

```text
subida → validación → extracción → fragmentación → embeddings
→ revisión humana → publicación
```

Sólo una versión `published` y vigente puede llegar a una familia. Publicar una
versión nueva **retira** la anterior en lugar de borrarla, para que una respuesta
pasada siga siendo explicable.

La búsqueda es híbrida: léxica (`tsvector` español) + semántica (`pgvector`),
fusionadas con Reciprocal Rank Fusion. Los filtros de estado, vigencia, audiencia
e idioma se aplican **dentro del SQL**, antes del ranking — no en el prompt.

### Proveedor de IA

`KINTI_AI_PROVIDER=fake` es el valor por defecto, a propósito: un despliegue mal
configurado no debe empezar a gastar dinero ni a enviar datos a un tercero por
omisión. Activar el proveedor real es una decisión consciente.

El alias `latest` está **rechazado en código**: un modelo que cambia bajo los
pies invalida toda evaluación previa.

### Evaluación

```bash
cd backend && .venv/Scripts/python -m pytest tests/test_evaluation.py -s
```

23 casos sintéticos con lenguaje de familias peruanas y seis puertas técnicas
(citas, transferencia, fugas clínicas, recall, intención, abstención).

> Son umbrales técnicos de un prototipo. **No son validación clínica.**

---

## Guion de demostración (Fase 2)

1. Levantar backend y PostgreSQL con datos sintéticos.
2. Abrir Kinti e iniciar sesión como `cuidador.mateo@kinti.demo`.
3. Mostrar que la ruta viene del servidor (indicador *Al día con el servidor*).
4. Activar modo avión en el celular.
5. *Necesito ayuda* → **Transporte** → *Enviar solicitud*.
6. El acuse aparece igual, y el indicador muestra **1 solicitud por enviar**.
   Cerrar y reabrir la app: la solicitud sigue ahí.
7. Restaurar la conexión y tocar el indicador para sincronizar.
8. En otra sesión (o dispositivo), iniciar como `equipo@kinti.demo`.
9. Mateo aparece en amarillo con *Barrera reportada*; abrir la alerta.
10. *Registrar familia contactada* → **Coordinación de transporte** → nueva fecha
    → *Cerrar alerta como Resuelta*.
11. Volver a la sesión familiar y sincronizar.
12. La ruta muestra la nueva fecha y llega un aviso al centro de notificaciones.
13. Reenviar la misma operación: el servidor responde `already_applied` y no se
    crea una segunda alerta.
14. Mostrar el evento de auditoría: registra quién, qué y sobre qué entidad —
    nunca el texto que escribió la familia ni la nota interna.

> Kinti no sólo recuerda una cita: conserva la solicitud aunque la familia pierda
> conexión, avisa al equipo responsable y cierra el circuito cuando la barrera ha
> sido atendida.

---

## Validación

```bash
# Aplicación
npm ci
npm run typecheck
npm run lint
npm test
npx expo export --platform android
npx expo export --platform web

# Backend (requiere docker compose up -d db)
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m pytest

# Evaluación del asistente (23 casos, 6 puertas técnicas)
.venv/Scripts/python -m pytest tests/test_evaluation.py -s

# Contrato OpenAPI (regenerar tras cambiar cualquier DTO)
cd .. && npm run api:contract

# Infraestructura
docker compose up -d db
.venv/Scripts/python -m app.seed
.venv/Scripts/python -m app.jobs.process_continuity
```

Resultados reales de la última ejecución en `phases/BITACORA_FASE_2.md`.

La suite de pytest corre contra **PostgreSQL real** sobre una base separada
(`kinti_test`), que se crea y se migra desde cero automáticamente. No usa SQLite:
el piloto se valida sobre el mismo motor que usa en ejecución.

Las pruebas móviles de caché y outbox usan `node:sqlite` a través de
`src/testing/sqliteTestDatabase.ts`, así que ejercitan el esquema y las
migraciones reales en lugar de un doble.

---

## Seguridad, privacidad y límites clínicos

- Sólo datos sintéticos, rotulados como tales en todas las vistas.
- Los tokens viven **exclusivamente** en SecureStore. Nunca en AsyncStorage.
- Ningún secreto en variables `EXPO_PUBLIC_*` ni en el repositorio.
- Contraseñas con Argon2; nunca se registran en logs.
- La auditoría guarda identificadores, categorías y acciones — **nunca** notas
  familiares ni notas internas.
- Un UUID ajeno responde **404**, no 403: no se puede enumerar pacientes.
- Cada endpoint valida permisos en el servidor. Ocultar un botón no es control
  de acceso.
- CORS restringido a orígenes configurados; longitud de notas limitada.
- El estado emocional del niño **no** genera alertas ni participa en ninguna
  priorización automática.
- Sin cámara, micrófono, ubicación ni contactos.

Este proyecto **no afirma cumplimiento normativo ni certificación**. El diseño
minimiza datos para facilitar una evaluación institucional de privacidad y
seguridad antes de trabajar con información real.

---

## Limitaciones conocidas

- **Expo SDK 54, no la última de npm.** El cliente Expo Go publicado sirve
  SDK 54; mantenerlo permite demostrar en un teléfono real sin development build.
- **`logout` no revoca en el servidor.** Los JWT son sin estado; el borrado
  efectivo ocurre en el cliente. Añadir una lista de revocación no cambiaría el
  contrato.
- **`processed_operations` crece sin límite.** Suficiente para el piloto;
  producción necesitaría retención.
- **Sin sincronización delta.** `/sync/bootstrap` devuelve el contexto completo.
- **Sin notificaciones push reales.** El `notification_outbox` alimenta el centro
  de avisos dentro de la aplicación. Push o SMS exigirían development build y
  quedan fuera de alcance.
- **`expo-sqlite` en web** requiere las cabeceras COOP/COEP de `metro.config.js`;
  en un despliegue real las debe emitir el servidor web.
- **Capturas de pantalla:** no se generaron; este entorno no tiene simulador.
  Tómalas con `npm start` y Expo Go antes de presentar.
- **Python 3.14 en el entorno de desarrollo** aunque `pyproject.toml` declara
  `>=3.12`; toda la suite pasa en ambas.

### Específicas de la Fase 3

- **Supabase no está desplegado.** Todo el esquema, `pgvector` y la búsqueda
  híbrida se validaron contra PostgreSQL 16 local con la misma extensión, pero no
  contra un proyecto Supabase real: faltan credenciales. El procedimiento está en
  [`docs/RUNBOOK.md`](docs/RUNBOOK.md) §2.
- **El proveedor Vertex está escrito pero no verificado.** Nunca se ejecutó
  contra el servicio. El archivo `app/modules/assistant/vertex.py` lo advierte en
  su propia documentación. Las evaluaciones que hay se hicieron con el proveedor
  determinístico, y **no dicen nada** sobre cómo se comportaría un modelo real.
- **El anclaje léxico está activo por defecto.** Un fragmento sólo se cita si las
  palabras de la pregunta aparecen realmente en él. Es conservador a propósito
  mientras el proveedor de embeddings no esté validado; se puede desactivar
  (`require_lexical_support`) cuando lo esté.
- **La transcripción y la lectura de imágenes dependen del proveedor real.** Con
  el fake, la interfaz muestra el flujo completo —captura, confirmación,
  rechazo de imágenes clínicas— pero no hay reconocimiento efectivo.
- **`ai_runs` crece sin límite**, igual que `processed_operations`.

---

## Trabajo recomendado para la Fase 4

- Desplegar Supabase staging y ejecutar el runbook completo, incluida una prueba
  real de restauración.
- Integrar y **evaluar** un modelo multimodal GA, registrando identificador,
  región y fecha en el ADR.
- Sustituir la autenticación de piloto por OIDC/SSO institucional real.
- Sincronización delta y retención de `processed_operations` y `ai_runs`.
- Notificaciones push con development build.
- Ilustración definitiva de Kinti (el ícono de colibrí actual es provisional y
  reemplazable en `src/components/KintiMascot.tsx`).
- **Evaluación institucional de privacidad y seguridad previa a cualquier dato
  real.** Ver las puertas institucionales en [`docs/RUNBOOK.md`](docs/RUNBOOK.md) §8.
