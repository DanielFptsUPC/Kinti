# Activación de la llamada real de Kinti

## Resultado esperado

El cuidador llama desde un teléfono, sin abrir la aplicación. Kinti verifica el
caso sintético, recoge las restricciones necesarias, presenta como máximo dos
alternativas y envía una solicitud. Si el flujo no puede continuar, deriva al
**Equipo asistencial**. La frase final no puede confundir una solicitud con una
cita confirmada.

```text
Teléfono del cuidador → número Twilio → HTTPS → kinti-api always-on
                                            ↓
                    Supabase ← solicitud/callback → Equipo asistencial
```

## Decisión de infraestructura

Los endpoints telefónicos son parte del mismo FastAPI que el resto del backend.
Durante el MVP no se crea un segundo microservicio: `kinti-api` completo pasa de
Render Free a Render Starter mediante `plan: starter` en `render.yaml`. Esto
elimina la suspensión por inactividad y evita un salto de red adicional.

## Lo que debe preparar una persona del equipo

- acceso de administrador al workspace de Render y un medio de pago;
- una cuenta Twilio y un teléfono del presentador verificado;
- autorización para actualizar Twilio, comprar un número y fijar el límite de
  gasto de la demo;
- un segundo teléfono como respaldo;
- disponibilidad del Equipo asistencial durante el ensayo y la presentación.

Nunca compartir `TWILIO_AUTH_TOKEN`, credenciales de Supabase ni claves de
Render por chat, captura, repositorio o aplicación móvil.

## Paso 1 — activar Render Starter

1. Hacer commit y push del `render.yaml` después de que la Fase 5 esté verde.
2. En Render, abrir `kinti-api` y confirmar que el Blueprint propone el cambio
   de `free` a `starter`.
3. Revisar el precio que muestra el dashboard y aprobar la facturación.
4. Sincronizar el Blueprint y esperar un deploy correcto.
5. Verificar:

   ```text
   GET https://kinti-api-9x9t.onrender.com/health
   GET https://kinti-api-9x9t.onrender.com/health/db
   ```

6. Esperar más de quince minutos y repetir ambas consultas. No debe existir un
   arranque en frío.

El cambio de archivo por sí solo no activa ni factura Starter: Render debe
aplicarlo mediante un deploy exitoso.

## Paso 2 — obtener una llamada telefónica real

### Smoke test sin compra

1. Crear la cuenta en Twilio y verificar el teléfono del presentador.
2. Abrir Voice → Try out Voice → Inbound.
3. Seleccionar el teléfono verificado y ejecutar primero una prueba de voz.
4. Usar después el webhook de Kinti para un recorrido corto.

El trial sólo permite llamadas desde números verificados y limita el TwiML
personalizado a diez saltos. Sirve para comprobar integración, no para ensayar
todo el recorrido actual de cita.

### Demo integral recomendada

1. Actualizar la cuenta Twilio y cargar únicamente el saldo que el equipo haya
   aprobado. Desactivar auto-recarga durante la hackathon.
2. Comprar un número local de EE. UU. con capacidad **Voice**. La consola debe
   mostrar el cargo mensual antes de confirmar.
3. Probar desde ambos teléfonos del equipo que pueden marcar ese número desde
   Perú. La llamada puede tener costo internacional para quien llama.
4. En Phone Numbers → Active numbers → Voice configuration, registrar:

   ```text
   A call comes in
   Webhook
   POST https://kinti-api-9x9t.onrender.com/api/v1/voice/incoming
   ```

5. No habilitar grabación. Conservar el método `POST`.

El número toll-free peruano no se usa en la hackathon: el precio de lista
consultado el 14 de agosto de 2026 es USD 135 al mes más USD 0.3986 por minuto
entrante. Un número local de EE. UU. parte de USD 1.15 al mes más uso, pero es
sólo una pieza de demostración y no el canal equitativo final.

## Paso 3 — cargar secretos en Render

Mantener `KINTI_TELEPHONY_PROVIDER=fake` mientras se cargan y verifican:

```text
TWILIO_ACCOUNT_SID=<secreto>
TWILIO_AUTH_TOKEN=<secreto>
TWILIO_PHONE_NUMBER=<E.164, por ejemplo +1...>
TWILIO_WEBHOOK_BASE_URL=https://kinti-api-9x9t.onrender.com
```

La URL base no lleva ruta ni barra final. Tras guardar secretos y superar el
smoke test fake, cambiar en Render:

```text
KINTI_TELEPHONY_PROVIDER=twilio
```

Desplegar de nuevo. Si falta una variable o la URL no usa HTTPS, Kinti debe
rechazar el arranque en vez de aceptar telefonía parcialmente configurada.

## Paso 4 — ensayo obligatorio

1. Llamar y completar el camino feliz con datos totalmente sintéticos.
2. Confirmar que la voz dice **solicitud enviada** y no **cita confirmada**.
3. Revisar que la solicitud aparezca en la bandeja del Equipo asistencial.
4. Repetir la selección y comprobar que no se duplique la operación.
5. Decir “no entiendo” dos veces y comprobar el handoff.
6. Pedir consejo clínico y comprobar que Kinti no responda, sino que derive.
7. Probar silencio, voz lenta y DTMF.
8. Ejecutar diez llamadas consecutivas y registrar latencia y resultado, sin
   almacenar audio ni transcripción.
9. Grabar un video de respaldo sin credenciales ni datos reales.

## Criterio de activación

La demo queda habilitada sólo si Render muestra Starter, los dos health checks
responden sin cold start, Twilio valida el webhook HTTPS, la llamada completa no
supera los límites del proveedor, la solicitud aparece una sola vez y el Equipo
asistencial puede atender el handoff.

## Fuentes oficiales

- [Twilio Trial Voice](https://www.twilio.com/docs/usage/trials/try-out-voice)
- [Twilio Voice — precios para Perú](https://www.twilio.com/en-us/voice/pricing/pe)
- [Twilio Voice — precios para EE. UU.](https://www.twilio.com/en-us/voice/pricing/us)
- [Twilio — seguridad de webhooks](https://www.twilio.com/docs/usage/webhooks/webhooks-security)
- [Render — servicios gratuitos y suspensión](https://render.com/docs/free)
- [Render — tipos de instancia](https://render.com/docs/compute-plans)
