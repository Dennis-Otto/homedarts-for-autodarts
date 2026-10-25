---
description: "Respuestas cortas sobre HomeDarts for Autodarts: cuenta, dispositivos, juego en línea, privacidad, varias dianas, pantallas, idiomas, actualizaciones y cambio."
---

# Preguntas frecuentes

[← Documentación](README.md) · [English](faq.md)

Respuestas cortas, cada una con la página que tiene los detalles; esas páginas están casi siempre en inglés. ¿Falta tu pregunta? Hazla en [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions).

**Ir a:** [Antes de empezar](#antes-de-empezar) · [Jugar](#jugar) · [Pantallas e idiomas](#pantallas-e-idiomas) · [Privacidad](#privacidad) · [Actualizaciones y cambio](#actualizaciones-y-cambio)

## Antes de empezar

### ¿Necesito una cuenta de Autodarts o una suscripción?

No. La integración habla con el Board Manager en el PC de tu diana a través de tu propia red, en el puerto TCP 3180. No necesita usuario de Autodarts, contraseña ni clave de API, ni una suscripción como Autodarts Plus, y nunca cambia el registro de tu diana en Autodarts. Una diana sin Autodarts no necesita nada de Autodarts. [Requisitos](installation.es.md#requisitos)

### ¿Qué necesito?

Home Assistant 2026.8 o posterior con [HACS](https://hacs.xyz), y una diana Autodarts en tu red o cualquier diana cuyos dardos introduces en un teclado numérico. ¿Nuevo en Home Assistant? [De cero al marcador](getting-started.es.md) te lleva de cero a la primera partida en el marcador.

### ¿Funciona con Autodarts Desktop, Autodarts X o Lens?

La integración necesita un Board Manager al que Home Assistant llegue en tu red. Board Manager 2 está probado hasta la versión 2.0.2, el Board Manager 1 clásico también funciona, y un jugador informa de que Autodarts Desktop 2.0.2 en Linux funciona. Autodarts Desktop en Windows y Autodarts X aún no se han probado. Un [informe de compatibilidad](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) nos cuenta cómo va con el tuyo, funcione o no. [Dispositivos compatibles](index.es.md#dispositivos-compatibles)

Lens puntúa con la cámara de un teléfono o una tableta dentro de la aplicación de Autodarts, sin Board Manager en tu red, así que la integración no puede leer sus dardos. Introdúcelos en el teclado numérico. Tampoco habrá un enlace a través de la nube de Autodarts: Autodarts no da ID de cliente a integraciones de terceros ([decisión 0025](decisions/0025-no-cloud-link.md)). [Play without Autodarts](without-autodarts.md)

### ¿Cuesta algo?

No. La integración es gratis y de código abierto con la [licencia MIT](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), sin nada que pagar y sin versión de pago. [Patrocinar](https://github.com/sponsors/Dennis-Otto) ayuda al proyecto y es totalmente opcional.

### ¿Es una integración oficial de Autodarts?

No. HomeDarts for Autodarts es un proyecto no oficial de la comunidad, sin relación con Autodarts, mantenido por [@Dennis-Otto](https://github.com/Dennis-Otto). Usa la interfaz local del Board Manager, que el equipo de Autodarts mantiene abierta. Hasta la versión 1.18 se llamaba Autodarts, hasta que Autodarts pidió un nombre propio. [From Autodarts to HomeDarts](new-name.md) · [Credits and license](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/README.md#credits-and-license)

## Jugar

### No tengo una diana Autodarts. ¿Puedo usarla?

Sí. Configura una diana sin Autodarts e introduce cada dardo en el teclado numérico del marcador, o por voz. Todos los juegos, el entrenamiento y las estadísticas funcionan. Si tu diana recibe Autodarts más tarde, conserva las partidas, los jugadores y las estadísticas. [Play without Autodarts](without-autodarts.md)

### ¿Puedo jugar partidos en línea?

Sí, en play.autodarts.io como antes. La integración ve entonces los dardos de tu propia diana: `dart_detected`, `visit_thrown` y la retirada de dardos llegan como siempre. Los busts, los legs y los partidos ganados ocurren en el navegador; el puente en línea opcional los lleva a Home Assistant con la extensión de navegador Tools for Autodarts *(experimental)*. [Online matches](online-matches.md)

### La diana leyó mal un dardo. ¿Cómo lo corrijo?

Toca el dardo en el marcador y elige dónde se clavó, en las teclas o en una imagen de la diana. En las automatizaciones, `homedarts.correct_dart` hace lo mismo, y `homedarts.undo_visit` deshace la última tirada. [Correct and enter darts](scoreboard.md#correct-and-enter-darts)

### ¿Puedo usar varias dianas?

Sí. Cada diana es una entrada y un dispositivo propios, con sus propias entidades, partidas y estadísticas, y el panel automático da a cada diana sus vistas, como `/scoreboard-1` y `/scoreboard-2`. Las acciones de la integración necesitan entonces el `config_entry_id` de la diana. [Several boards](without-autodarts.md#several-boards)

Una noche de club también puede jugar [un torneo en varias dianas a la vez](games.md#a-tournament-on-several-boards), cada diana con un partido propio.

Un jugador que lanza en dos dianas tiene un perfil en cada una. [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) con `mode: merge` añade la copia de seguridad de una diana a la otra, y los números del jugador se suman. [Backups](statistics.md#backups)

## Pantallas e idiomas

### ¿Puedo mostrar el marcador en un televisor o una tableta Fire?

Sí: en cualquier pantalla cuyo navegador abra tu Home Assistant, como una tableta en la pared, también una tableta Fire, un televisor con navegador, un PC pequeño o un teléfono viejo. No hay que instalar nada en ella. Dale a la pantalla un usuario propio de Home Assistant y abre la vista *Marcador* del panel automático, a pantalla completa o en un navegador de quiosco. Un televisor con Chromecast o un Google Nest Hub la muestra con Home Assistant Cast, sin navegador propio. [Set up the screen](scoreboard.md#set-up-the-screen) · [Home Assistant Cast](scoreboard.md#on-a-tv-with-home-assistant-cast)

### ¿Qué idiomas habla y qué voces tiene el locutor?

Español, inglés, alemán, neerlandés y francés, según el idioma de Home Assistant: la configuración, las entidades, las tarjetas y el locutor. El locutor del marcador habla con una voz del navegador de la pantalla para ese idioma, o con los sonidos grabados de un paquete de voz, como uno de darts-caller o uno que grabes con Piper. Los blueprints del locutor de dardos y del locutor de entrenamiento hablan en el idioma de Home Assistant, a través de la conversión de texto a voz y los altavoces de tu Home Assistant. [Idiomas](index.es.md#idiomas) · [Which caller?](automations.md#which-caller)

## Privacidad

### ¿Qué sale de mi red?

Nada, en el modo local. Solo lo que tú eliges habla con internet: la búsqueda de dianas pregunta una vez al servicio público de descubrimiento de Autodarts, y el puente en línea solo recibe las llamadas de Tools for Autodarts. Los secretos de la diana nunca se guardan, y los diagnósticos ocultan los ID de las dianas, las direcciones y los nombres de los jugadores. Algunos navegadores dicen los cantos del marcador con voces en línea; una voz sin conexión del dispositivo los mantiene en casa. [Privacy](how-it-works.md#privacy) · [Security design](security.md)

### ¿Dónde se guardan mis estadísticas?

En el almacenamiento propio de Home Assistant, nunca en la nube: las sesiones de entrenamiento, la partida de práctica, los récords personales, los perfiles de los jugadores con sus partidos y el calendario de entrenamiento con un año de sesiones y partidos. Borrar la diana las borra, después de una [copia de seguridad](statistics.md#backups), y [`homedarts.export`](entities.md#export-training-data-homedartsexport) las exporta para una hoja de cálculo. [Stored data](how-it-works.md#stored-data)

### Borré mi diana. ¿Se han perdido mis estadísticas?

No. Antes de borrar una diana, HomeDarts escribe una copia de seguridad de todo lo que guardó en `homedarts/backups` de la carpeta multimedia. Añade la diana otra vez, y la reparación *A backup of … is available* lo recupera todo; [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) restaura cualquier copia. [Backups](statistics.md#backups)

## Actualizaciones y cambio

### ¿Cómo actualizo el Board Manager?

En el PC de la diana, como lo describe Autodarts. Home Assistant te avisa cuando toca una actualización: con Board Manager 2, la entidad de actualización *Software* muestra la versión instalada y la más reciente, y una diana con Board Manager 1 recibe un aviso de reparación para pasar a Board Manager 2. La integración se actualiza por HACS. [Update to Board Manager 2](installation.md#update-from-board-manager-1-to-board-manager-2) · [Health and connections](entities.md#health-and-connections)

### La integración se llamaba Autodarts. ¿Qué cambia para mí?

Desde la versión 2.0 se llama HomeDarts for Autodarts, con el dominio `homedarts`. Después de la actualización, añade **HomeDarts for Autodarts** y elige **Transferir las dianas de la integración Autodarts**: tus dianas conservan sus entidades, historial, estadísticas y paneles. Las automatizaciones y los scripts que llaman a las acciones antiguas, como `autodarts.start_game`, necesitan los nombres nuevos, como `homedarts.start_game`; una reparación los enumera. [From Autodarts to HomeDarts](new-name.md)

### Uso el HACSAutodarts original. ¿Cómo cambio?

Instala HomeDarts a su lado: el original tiene el dominio `autodarts`, HomeDarts el dominio `homedarts`, así que los dos funcionan a la vez. Añade tu diana a HomeDarts, mueve tus automatizaciones, luego borra la entrada de HACSAutodarts y quítalo en HACS. HomeDarts no transfiere esa entrada. [Switch from the original integration](installation.md#switch-from-the-original-integration)

### Uso otra herramienta para Autodarts. ¿Cómo cambio?

[Coming from another tool](coming-from.md) trata Autodarts Local, las otras integraciones de Home Assistant, los puentes MQTT, darts-caller y darts-wled, y Tools for Autodarts: lo que ofrece cada uno, las entidades, los eventos y los blueprints que ocupan su lugar, y cómo cambiar mientras sigue instalado. HomeDarts tiene un dominio propio, así que ninguno tiene que irse antes.

### Algo no funciona. ¿Dónde consigo ayuda?

[Troubleshooting](troubleshooting.md) explica los mensajes, las reparaciones y los diagnósticos. Haz tus preguntas en [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions) e informa de los errores en una [incidencia](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), con los diagnósticos de tu diana; [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) explica dónde preguntar qué.
