# Kinti — Fase 1: prototipo móvil de continuidad hematológica

> Documento de ejecución para Codex. Esta fase debe producir un prototipo móvil navegable y demostrable con datos sintéticos. No debe conectarse todavía con sistemas reales del INSNSB ni utilizar datos personales o clínicos reales.

## 1. Rol del agente

Actúa como diseñador de producto y desarrollador móvil senior. Construye la primera fase de **Kinti**, una aplicación móvil con interfaces diferenciadas para pacientes pediátricos, cuidadores y personal asistencial de la ruta hematológica del Instituto Nacional de Salud del Niño San Borja (INSNSB).

Antes de modificar archivos:

1. Inspecciona el repositorio y conserva todos los cambios existentes.
2. Crea la aplicación en una carpeta independiente llamada `kinti-mobile`.
3. No modifiques el backend ni los documentos de Kuska que no pertenezcan a Kinti.
4. Si una decisión menor no está definida, elige la alternativa más simple que permita demostrar el flujo de valor.
5. Usa exclusivamente información y pacientes ficticios.

## 2. Problema que debe resolver

Las familias que recorren la atención hematológica pediátrica pueden perder continuidad por una combinación de:

- falta de claridad sobre el siguiente paso;
- citas, exámenes o procedimientos no confirmados;
- barreras económicas, geográficas, familiares o administrativas;
- problemas de coordinación entre la familia y el equipo asistencial;
- detección tardía de una inasistencia o interrupción.

Estas situaciones generan demoras evitables, aumentan el riesgo de abandono y pueden prolongar la atención más allá de lo clínicamente necesario.

Kinti no busca acortar protocolos médicos ni reemplazar decisiones clínicas. Busca **reducir interrupciones y demoras evitables mediante acompañamiento, detección temprana de barreras y coordinación asistencial**.

## 3. Propuesta de valor

**Kinti es el compañero digital de la ruta hematológica pediátrica. Muestra a cada familia cuál es su siguiente paso, permite avisar si no podrá cumplirlo y ayuda al equipo asistencial a intervenir antes de que se pierda la continuidad.**

Lema provisional:

> Kinti: contigo en cada paso.

La mascota es un colibrí llamado Kinti. Debe comunicar agilidad, cercanía y acompañamiento. Su presencia debe ser cálida para el niño, pero la interfaz del cuidador y del personal debe conservar credibilidad institucional.

## 4. Objetivo de la Fase 1

Construir un prototipo funcional que demuestre de principio a fin este ciclo:

1. El médico o gestor registra el siguiente hito asistencial.
2. El cuidador visualiza el hito y confirma si podrá cumplirlo.
3. Si existe una barrera, el cuidador la reporta en pocos toques.
4. El sistema crea una alerta y asigna un nivel de prioridad operativo.
5. El personal visualiza la alerta, registra una acción y la resuelve.
6. La familia recibe el nuevo acuerdo y la ruta vuelve a estar activa.

La fase termina cuando este flujo puede demostrarse en un celular sin backend, utilizando persistencia local y datos simulados.

## 5. Usuarios de la aplicación

### Niño o adolescente

- Visualiza su avance mediante una ruta amigable.
- Conoce su próxima actividad en lenguaje sencillo.
- Interactúa con Kinti y registra cómo se siente emocionalmente.
- No recibe diagnósticos, interpretaciones de resultados ni responsabilidades por el cumplimiento familiar.

### Cuidador o apoderado

- Consulta el siguiente paso y las indicaciones operativas.
- Confirma asistencia o comunica una dificultad.
- Revisa la ruta, reprogramaciones y apoyos coordinados.
- Recibe información clara sin depender de un código QR.

### Médico o gestor de continuidad

- Registra o valida el siguiente hito.
- Visualiza pacientes ordenados por riesgo de interrupción.
- Revisa las barreras reportadas.
- Registra contacto, derivación, reprogramación o cierre de la alerta.

En la Fase 1, los roles se seleccionarán desde una pantalla de demostración. No implementar autenticación real.

## 6. Principios de experiencia

- **El siguiente paso siempre visible:** debe ser el elemento más importante de la pantalla familiar.
- **Tres toques como máximo para pedir ayuda:** la familia no debe completar formularios extensos.
- **Sin dependencia de QR:** el prototipo simulará una invitación realizada por el médico mediante un código corto o perfil ya vinculado.
- **Lenguaje simple:** evitar términos técnicos que no sean indispensables.
- **Diseño inclusivo:** botones grandes, contraste suficiente, tipografía legible y estados que no dependan solo del color.
- **Sin culpabilización:** no usar mensajes como “fallaste”, “perdiste” o “rompiste tu racha”.
- **Kinti acompaña, no diagnostica:** la mascota no da consejos médicos ni interpreta síntomas.
- **Privacidad desde el diseño:** datos mínimos, ficticios y claramente marcados como demostración.

## 7. Alcance funcional

### 7.1 Inicio y selección de perfil

Crear una pantalla inicial con:

- logotipo textual `Kinti`;
- representación provisional del colibrí;
- lema “Contigo en cada paso”;
- accesos de demostración: `Niño`, `Cuidador` y `Equipo asistencial`;
- aviso visible: “Prototipo con información ficticia”.

### 7.2 Inicio del cuidador

Mostrar prioritariamente:

- nombre ficticio y avatar del paciente;
- estado de la ruta: `Al día`, `Necesita confirmación` o `Requiere apoyo`;
- tarjeta “Tu siguiente paso” con actividad, fecha, hora, lugar y preparación;
- botones `Sí, podremos asistir` y `Necesito ayuda`;
- acceso secundario a la ruta completa y datos de contacto institucionales simulados.

### 7.3 Reporte de una barrera

Al pulsar `Necesito ayuda`, mostrar opciones grandes:

- transporte;
- alojamiento;
- dificultad económica;
- fecha u horario;
- no comprendí la indicación;
- no puedo comunicarme con el servicio;
- dificultad de salud del niño;
- otra dificultad.

Después de elegir:

- permitir una nota opcional breve;
- confirmar el número ficticio de contacto;
- crear una alerta local;
- mostrar el mensaje: “Recibimos tu solicitud. El equipo revisará tu caso”.

Si se elige `Dificultad de salud del niño`, mostrar además:

> Kinti no evalúa síntomas ni emergencias. Si el niño presenta una urgencia, acude al establecimiento de salud o comunícate con los canales oficiales indicados por el hospital.

No crear un triaje clínico automático.

### 7.4 Ruta asistencial familiar

Representar los hitos como una línea de progreso:

- completado;
- próximo;
- pendiente de programación;
- necesita apoyo;
- reprogramado.

Utilizar ejemplos como consulta hematológica, laboratorio, procedimiento y control. No mostrar resultados clínicos reales ni inventar recomendaciones médicas.

### 7.5 Experiencia del niño

Crear una pantalla diferenciada con:

- Kinti como acompañante;
- mensaje sencillo sobre la próxima estación;
- mapa visual de etapas;
- pequeñas insignias por conocer o completar etapas, nunca por resultados médicos;
- selector emocional: tranquilo, con dudas, preocupado o cansado;
- mensaje que anime a conversar con su cuidador o equipo.

El registro emocional puede guardarse localmente, pero no debe generar una decisión clínica.

### 7.6 Panel móvil del equipo asistencial

Mostrar:

- resumen de pacientes verdes, amarillos y rojos;
- lista ordenable por prioridad;
- nombre ficticio, próxima actividad, estado y motivo de alerta;
- filtros `Todos`, `Por confirmar`, `Con barrera` y `Inasistencia`;
- acceso al detalle del caso.

El semáforo representa **riesgo operativo de interrupción**, no gravedad médica.

Reglas simples para la demostración:

- verde: hito confirmado y sin barreras;
- amarillo: hito pendiente de confirmación o barrera reportada;
- rojo: hito vencido, inasistencia registrada o barrera sin respuesta en el plazo simulado.

Mostrar siempre la leyenda de estos estados.

### 7.7 Gestión de una alertae

En el detalle de la alerta, permitir:

- revisar el hito afectado y la barrera;
- registrar `Familia contactada`;
- seleccionar una acción: orientación, reprogramación, derivación a trabajo social, coordinación de alojamiento, coordinación de transporte u otra;
- agregar una nota interna ficticia;
- definir una nueva fecha cuando exista reprogramación;
- cerrar la alerta como `Resuelta`.

Cuando se cierre, actualizar automáticamente la vista del cuidador y el estado de la ruta.

### 7.8 Registro del siguiente hito

Desde el perfil asistencial, permitir crear un hito con:

- tipo de actividad;
- fecha y hora;
- lugar;
- indicación operativa breve;
- responsable o servicio;
- fecha límite de confirmación.

Al guardar, el hito debe aparecer inmediatamente en la vista del cuidador.

## 8. Navegación mínima

### Cuidador

`Inicio` — `Mi ruta` — `Ayuda` — `Perfil`

### Niño

`Mi aventura` — `Cómo me siento`

### Equipo asistencial

`Resumen` — `Pacientes` — `Alertas`

Se puede usar un selector de rol persistente y una opción `Cambiar perfil de demostración` dentro de configuración.

## 9. Datos sintéticos de demostración

Incluir al menos estos tres casos:

1. **Lucía, 8 años — verde:** próximo control confirmado.
2. **Mateo, 11 años — amarillo:** familia reportó dificultad de transporte.
3. **Valentina, 6 años — rojo:** actividad vencida e inasistencia pendiente de contacto.

Cada paciente debe tener entre cuatro y seis hitos que permitan mostrar estados diferentes.

No emplear DNI, teléfonos reales, números de historia clínica reales ni diagnósticos detallados atribuibles a personas.

## 10. Modelo de datos local mínimo

Definir tipos TypeScript equivalentes a:

```ts
type Role = "child" | "caregiver" | "care_team";
type RouteStatus = "on_track" | "confirmation_needed" | "support_needed";
type MilestoneStatus =
  | "completed"
  | "upcoming"
  | "unscheduled"
  | "support_needed"
  | "rescheduled"
  | "missed";
type OperationalRisk = "green" | "yellow" | "red";

interface Patient {
  id: string;
  displayName: string;
  age: number;
  avatarKey: string;
  routeStatus: RouteStatus;
  operationalRisk: OperationalRisk;
}

interface Milestone {
  id: string;
  patientId: string;
  type: "consultation" | "laboratory" | "procedure" | "treatment" | "follow_up";
  title: string;
  scheduledAt?: string;
  location?: string;
  preparation?: string;
  service?: string;
  confirmationDeadline?: string;
  status: MilestoneStatus;
  attendanceConfirmed: boolean;
}

interface BarrierAlert {
  id: string;
  patientId: string;
  milestoneId: string;
  category:
    | "transport"
    | "lodging"
    | "financial"
    | "schedule"
    | "instructions"
    | "communication"
    | "health_difficulty"
    | "other";
  note?: string;
  risk: OperationalRisk;
  status: "open" | "in_progress" | "resolved";
  actionTaken?: string;
  createdAt: string;
  resolvedAt?: string;
}
```

El agente puede ampliar estos tipos si lo necesita, pero debe conservar la separación entre estado clínico y riesgo operativo.

## 11. Stack técnico recomendado

- React Native con Expo.
- TypeScript en modo estricto.
- Expo Router para navegación.
- Persistencia local con AsyncStorage.
- Estado global ligero con Context + reducer o Zustand.
- Componentes propios reutilizables; evitar una dependencia pesada de UI.
- Íconos accesibles de una biblioteca compatible con Expo.
- Pruebas unitarias para la lógica de riesgo y actualización de alertas.

La aplicación debe funcionar en Expo Go. Si el repositorio ya contiene una alternativa móvil funcional, evalúa reutilizarla antes de crear una estructura duplicada.

## 12. Sistema visual inicial

- Color principal: turquesa o verde azulado asociado a acompañamiento y confianza.
- Acento: coral cálido para acciones y elementos infantiles.
- Fondo: marfil o gris muy claro.
- Estados: verde, ámbar y rojo acompañados siempre de texto e ícono.
- Bordes redondeados y tarjetas amplias.
- Tipografía sans serif legible.
- Áreas táctiles mínimas de 44 × 44 puntos.
- No usar más de dos familias tipográficas.

Crear tokens para colores, espaciado, radio y tipografía. No dispersar valores visuales sin nombre por las pantallas.

La ilustración definitiva de Kinti queda fuera de esta fase. Usar un recurso provisional original o un ícono de colibrí/ave claramente reemplazable, sin copiar personajes protegidos.

## 13. Accesibilidad

- Contraste compatible con WCAG AA cuando sea posible.
- Etiquetas accesibles en controles interactivos.
- Texto escalable sin romper las pantallas principales.
- No comunicar estados únicamente mediante colores.
- Lenguaje comprensible para cuidadores con distinta alfabetización digital.
- No incluir animaciones rápidas, destellos ni recompensas que generen presión.

## 14. Seguridad clínica y privacidad

- Añadir el rótulo `Prototipo — datos ficticios` en las vistas asistenciales.
- No diagnosticar, prescribir ni interpretar resultados.
- No presentar el semáforo como indicador de gravedad clínica.
- No guardar información real del paciente.
- No solicitar permisos de cámara, micrófono, ubicación o contactos en esta fase.
- No agregar chat médico abierto ni prometer respuesta inmediata.
- Mostrar canales ficticios como tales; no inventar teléfonos oficiales.
- La decisión y priorización clínica siempre corresponden al personal autorizado.

## 15. Fuera de alcance

No implementar en la Fase 1:

- integración con historia clínica electrónica;
- interoperabilidad con sistemas del INSNSB;
- autenticación institucional o biométrica;
- notificaciones push, SMS o WhatsApp reales;
- inteligencia artificial o predicción clínica;
- lectura de códigos QR;
- programación real de citas;
- teleconsulta;
- pagos, donaciones o gestión real de beneficios;
- almacenamiento en la nube;
- información médica real;
- panel web independiente.

Representar las integraciones futuras mediante interfaces o servicios simulados para facilitar su sustitución posterior.

## 16. Historias de usuario prioritarias

### HU-01 — Conocer el siguiente paso

Como cuidador, quiero ver inmediatamente la próxima actividad y cómo prepararnos, para evitar confusiones y retrasos.

**Aceptación:** la información aparece en el inicio sin navegar a otra sección.

### HU-02 — Confirmar asistencia

Como cuidador, quiero confirmar en un toque que podremos asistir, para que el equipo conozca nuestro estado.

**Aceptación:** la confirmación persiste después de cerrar y abrir la aplicación.

### HU-03 — Pedir ayuda

Como cuidador, quiero comunicar rápidamente una barrera, para recibir orientación antes de faltar.

**Aceptación:** crear la alerta requiere como máximo tres interacciones principales y aparece en el panel asistencial.

### HU-04 — Priorizar casos

Como gestor, quiero ver qué familias requieren atención primero, para actuar antes de una interrupción.

**Aceptación:** la lista muestra el riesgo operativo y puede filtrarse por estado.

### HU-05 — Resolver una alerta

Como gestor, quiero registrar la acción realizada, para cerrar el circuito y actualizar la ruta de la familia.

**Aceptación:** al resolver o reprogramar, la vista del cuidador cambia inmediatamente.

### HU-06 — Participación del niño

Como paciente pediátrico, quiero entender mi próxima etapa de forma amigable, para sentirme acompañado.

**Aceptación:** la pantalla infantil muestra la próxima estación sin exponer información clínica compleja.

### HU-07 — Registrar un nuevo hito

Como personal asistencial, quiero registrar el siguiente paso antes de cerrar la atención, para que la familia no salga sin una orientación clara.

**Aceptación:** el nuevo hito aparece como prioridad en el inicio del cuidador.

## 17. Orden de implementación para Codex

### Paso 1 — Preparación

- Inspeccionar el repositorio.
- Crear `kinti-mobile` sin alterar el proyecto existente.
- Configurar TypeScript, navegación, lint y pruebas.
- Documentar los comandos de instalación y ejecución.

### Paso 2 — Base visual y datos

- Crear tokens y componentes reutilizables.
- Definir tipos y repositorio local de datos.
- Cargar los tres pacientes ficticios.
- Implementar selector de rol para la demostración.

### Paso 3 — Flujo familiar

- Construir inicio del cuidador.
- Implementar confirmación de asistencia.
- Implementar reporte de barrera.
- Construir línea de ruta.

### Paso 4 — Flujo asistencial

- Construir resumen y lista priorizada.
- Implementar detalle y resolución de alertas.
- Implementar creación del siguiente hito.
- Sincronizar cambios entre roles mediante el estado local.

### Paso 5 — Experiencia infantil

- Construir mapa sencillo de etapas.
- Incorporar a Kinti de manera provisional.
- Implementar registro emocional local y mensajes de acompañamiento.

### Paso 6 — Validación

- Probar la persistencia local.
- Probar lógica de semáforo y resolución de alertas.
- Revisar accesibilidad básica.
- Ejecutar lint, comprobación de tipos y pruebas.
- Recorrer el guion completo de demostración.

No avances al siguiente paso si el flujo principal del paso actual no funciona.

## 18. Criterios de finalización

La Fase 1 está terminada cuando:

- la app inicia sin errores en Expo Go;
- los tres perfiles son navegables;
- el cuidador puede confirmar un hito o reportar una barrera;
- la barrera aparece en el panel del equipo;
- el equipo puede resolverla o reprogramar el hito;
- el cambio se refleja en la vista familiar;
- el personal puede registrar el siguiente hito;
- el niño puede visualizar su próxima estación;
- los datos persisten al reiniciar la app;
- no se utilizan datos reales ni se presentan funciones como consejo médico;
- lint, TypeScript y pruebas terminan correctamente;
- el README explica instalación, ejecución, arquitectura, datos de demostración y limitaciones.

## 19. Guion de demostración

La demostración debe durar entre dos y tres minutos:

1. Entrar como cuidador de Mateo.
2. Mostrar su próxima consulta y pulsar `Necesito ayuda`.
3. Elegir `Transporte` y enviar la solicitud.
4. Cambiar al perfil del equipo asistencial.
5. Mostrar que Mateo aparece en amarillo con la barrera reportada.
6. Abrir la alerta, registrar coordinación de transporte y confirmar la nueva fecha.
7. Regresar al perfil del cuidador y mostrar la ruta actualizada.
8. Entrar como niño y mostrar cómo Kinti presenta la próxima estación.
9. Cerrar explicando que el valor no es solo recordar citas, sino detectar y resolver interrupciones antes de que se conviertan en abandono.

## 20. Métricas que preparará el prototipo

Aunque la Fase 1 no realiza una evaluación clínica real, la arquitectura debe permitir medir posteriormente:

- porcentaje de hitos cumplidos dentro del plazo previsto;
- porcentaje de asistencias confirmadas;
- número de inasistencias y días de retraso;
- barreras reportadas por categoría;
- porcentaje de alertas atendidas y resueltas;
- tiempo desde la alerta hasta la primera acción;
- pacientes recuperados después de una interrupción;
- porcentaje de familias que identifican correctamente su siguiente paso.

La métrica principal será:

> Porcentaje de hitos asistenciales cumplidos dentro del plazo previsto.

## 21. Entregables del agente

Al finalizar, entregar:

1. Código funcional dentro de `kinti-mobile`.
2. README con instrucciones reproducibles.
3. Datos sintéticos y opción para restaurar la demostración.
4. Pruebas de la lógica principal.
5. Capturas de las pantallas clave.
6. Resumen breve de decisiones, limitaciones y trabajo recomendado para la Fase 2.

En el informe final, indicar los comandos ejecutados y sus resultados. No declarar terminada la fase si el flujo cuidador → alerta → equipo → resolución → cuidador no funciona de principio a fin.
