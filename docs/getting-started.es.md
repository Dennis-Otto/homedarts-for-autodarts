---
description: "De cero al marcador en una tableta junto a tu diana Autodarts en una hora: Home Assistant, HACS, la integración y el panel."
---

# De cero al marcador

[← Documentación](README.md) · [English](getting-started.md)

¿Juegas en una diana Autodarts y nunca has usado Home Assistant? Esta guía te lleva de cero al marcador en una tableta junto a tu diana. Home Assistant, HACS y la integración son gratis. Calcula una hora más o menos; la mayor parte se va en instalar Home Assistant.

<img src="images/en/scoreboard-lobby.png" alt="La pantalla de nueva partida en una tableta en horizontal: los juegos por grupo con 501 elegido, Alex y Sam con su foto, Sam empieza desde 301, tres legs por set, double out y el botón de inicio" width="760">

**En esta página:** [Qué necesitas](#qué-necesitas) · [1. Instalar Home Assistant](#1-instalar-home-assistant) · [2. Instalar HACS](#2-instalar-hacs) · [3. Instalar la integración](#3-instalar-la-integración) · [4. Añadir tu diana](#4-añadir-tu-diana) · [5. Crear el panel](#5-crear-el-panel) · [6. Poner el marcador junto a la diana](#6-poner-el-marcador-junto-a-la-diana) · [7. Jugar tu primera partida](#7-jugar-tu-primera-partida) · [Y después](#y-después) · [Si algo no funciona](#si-algo-no-funciona)

## Qué necesitas

- **Tu diana Autodarts,** instalada y funcionando. [Dispositivos compatibles](index.es.md#dispositivos-compatibles) enumera los equipos probados. ¿Sin Autodarts? [Juega sin Autodarts](without-autodarts.md) en cualquier diana e introduce tus dardos en un teclado numérico.
- **Un dispositivo para Home Assistant** que esté siempre encendido, en la misma red que la diana: una Raspberry Pi 4 o 5, un mini PC o una máquina virtual en un ordenador que esté siempre en marcha. Home Assistant también vende dispositivos listos para usar. Usa un dispositivo aparte: el PC de la diana necesita su potencia para la detección.
- **Una cuenta gratuita de GitHub,** que HACS usa para descargar integraciones.
- **Una pantalla para el marcador,** si quieres una: una tableta, un televisor con navegador o un teléfono viejo.

## 1. Instalar Home Assistant

Sigue la [guía de instalación](https://www.home-assistant.io/installation/) oficial para tu dispositivo; muestra cada paso con imágenes. En una Raspberry Pi, elige **Home Assistant OS** ([guía para la Raspberry Pi](https://www.home-assistant.io/installation/raspberrypi)).

Al final, abre Home Assistant en un navegador, normalmente en `http://homeassistant.local:8123`, y crea tu cuenta. La [guía de la primera configuración](https://www.home-assistant.io/getting-started/onboarding/) explica las preguntas.

## 2. Instalar HACS

HACS es la tienda de integraciones y tarjetas de la comunidad, como esta. Sigue la guía oficial para [descargar HACS](https://www.hacs.xyz/docs/use/download/download/) y [configurarlo](https://www.hacs.xyz/docs/use/configuration/basic/) con tu cuenta de GitHub. Después, **HACS** aparece en la barra lateral de Home Assistant.

## 3. Instalar la integración

[![Abre tu Home Assistant y muestra este repositorio en HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

1. Selecciona el botón de arriba y confirma la dirección de tu Home Assistant. HACS abre esta integración. Sin el botón: abre **HACS**, busca **HomeDarts** y ábrela.
2. Selecciona **Download**.
3. Reinicia Home Assistant: **Configuración → Sistema**, el botón de encendido arriba a la derecha, **Reiniciar Home Assistant**.

## 4. Añadir tu diana

[![Abre tu Home Assistant y empieza a configurar HomeDarts for Autodarts.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

Con Board Manager 2, Home Assistant suele encontrar la diana por sí solo: **Configuración → Dispositivos y servicios** muestra **Diana Autodarts encontrada** en *Descubierto*. Selecciona **Añadir** y confirma. La animación muestra el camino desde aquí hasta el marcador, en menos de un minuto.

<img src="images/en/setup.webp" alt="Animación: la configuración en cinco pasos con leyendas, en inglés, en la pantalla de un teléfono. 1: Home Assistant muestra la diana encontrada en Descubierto. 2: añadir y confirmar en la ventana Diana Autodarts encontrada; la diana queda configurada y se abre su página de dispositivo. 3: configuración, paneles de control, añadir panel de control. 4: la búsqueda encuentra HomeDarts, el título HomeDarts, crear. 5: el panel nuevo se abre en la vista en directo y después en el marcador, que cuenta tres triples 20 hasta 180" width="100%">

Si no, selecciona el botón de arriba y elige **Buscar dianas en esta red**, o **Introducir la dirección de la diana** con la dirección IP del PC de la diana. No necesitas una cuenta de Autodarts.

<img src="images/en/setup-menu.png" alt="El menú de configuración de HomeDarts: buscar dianas en esta red, introducir la dirección de una diana o una diana sin Autodarts" width="520">

La [guía de instalación](installation.es.md#añadir-tu-diana) explica cada forma en detalle. Sin Autodarts, elige **Diana sin Autodarts: introduce tú cada dardo** y dale un nombre a la diana; [Play without Autodarts](without-autodarts.md) muestra el resto.

## 5. Crear el panel

Ve a **Configuración → Paneles de control → Añadir panel de control → HomeDarts**. Dale un título y selecciona **Crear**: así se crea un panel completo para tu diana, con vistas para la partida en directo, el marcador, el entrenamiento, los jugadores y la diana. Se actualiza solo cuando añades una diana o una versión posterior trae vistas nuevas.

<img src="images/en/dashboard-strategy.png" alt="La vista de entrenamiento del panel automático" width="760">

## 6. Poner el marcador junto a la diana

1. En la tableta, abre Home Assistant en el navegador o en la [aplicación de Home Assistant](https://companion.home-assistant.io/) e inicia sesión. Un usuario aparte sin derechos de administrador evita que la pantalla cambie tu configuración.
2. Abre el panel de HomeDarts y su vista *Marcador*.
3. Toca el botón de pantalla completa arriba a la derecha del marcador: llena la pantalla y la mantiene encendida. Donde el navegador no pueda mantenerla encendida, como en una dirección con `http://`, desactiva el apagado automático de la pantalla de la tableta; consulta [pantalla completa](scoreboard.md#full-screen).

La [guía del marcador](scoreboard.md#set-up-the-screen) tiene los detalles y las opciones, como el locutor.

## 7. Jugar tu primera partida

Toca **Nueva partida** en el marcador. Elige 501, añádete, añade el **bot** con **+ Bot** si juegas solo y toca **Empezar 501**. Lanza tus dardos: el marcador cuenta, muestra tu ruta de cierre y pasa el turno después de cada tirada.

Si la diana lee mal un dardo, tócalo en la tirada y corrígelo. La [guía de los juegos](games.md#start-a-game) muestra cada juego y las otras formas de empezar uno.

## Y después

- **Luz y sonido:** los [blueprints](automations.md#blueprints) hacen parpadear tus luces con un 180, cantan las puntuaciones o hacen una foto destacada. Vienen con la integración y te esperan en la página de planos de Home Assistant.
- **Tu progreso:** los récords personales, un mapa de calor de tus dardos, las tendencias y los logros están en la [guía de las estadísticas](statistics.md).
- **Amigos en casa:** los equipos, los hándicaps y los torneos de hasta 32 jugadores están en la [guía de los juegos](games.md).

## Si algo no funciona

- La [guía de solución de problemas](troubleshooting.md) explica cada mensaje de la configuración y cada aviso de reparación.
- Pregunta en [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/categories/q-a). Allí se responden las preguntas, así que cada respuesta ayuda también al siguiente jugador. Las preguntas en inglés o alemán reciben respuesta más rápido.
- Si tu equipo no está en la lista de [dispositivos compatibles](index.es.md#dispositivos-compatibles), un [informe de compatibilidad](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) nos ayuda, funcione o no.
