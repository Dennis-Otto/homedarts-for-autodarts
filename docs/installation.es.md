---
description: "Instala HomeDarts for Autodarts con HACS y añade tu diana por su dirección en tu red. Sin usuario de Autodarts, contraseña ni clave de API."
---

# Instalación y configuración

[← Documentación](README.md) · [English](installation.md)

Esta página describe la instalación y cómo añadir una diana. La reconfiguración, el paso a Board Manager 2, la actualización desde la versión 1.x, el cambio desde la integración original y la eliminación están en la [página en inglés](installation.md#reconfigure).

## Requisitos

| Requisito | Detalles |
| --- | --- |
| Home Assistant | **2026.8** o posterior ([por qué 2026.8](decisions/0022-home-assistant-2026-8-as-the-oldest-release.md), en inglés) |
| Diana Autodarts | Instalada y funcionando en el Board Manager de Autodarts: **Board Manager 2**, Autodarts 2 sin pantalla (headless, recomendado, probado hasta la versión 2.1.0), o el **Board Manager 1** clásico. Según un jugador, **Autodarts Desktop** 2.0.2 en Linux también funciona. Autodarts Desktop en Windows y los **dispositivos de Winmau** como Autodarts X o Lens aún no se han probado; [cuéntanos](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) cómo funciona con el tuyo |
| Red | Home Assistant accede al PC de la diana en la red local, por defecto en el puerto TCP **3180** |
| Sin Autodarts | Cualquier diana: introduces los dardos en un teclado numérico, consulta [Play without Autodarts](without-autodarts.md); no necesita ni un PC junto a la diana ni una red hasta ella |

La integración **no necesita usuario de Autodarts, contraseña ni clave de API**. Nunca cambia el registro de tu diana en Autodarts. Tampoco tiene enlace con la nube de Autodarts: Autodarts no da ID de cliente a integraciones de terceros ([decisión 0025](decisions/0025-no-cloud-link.md), en inglés).

## Instalar

### Con HACS (recomendado)

[![Abre tu Home Assistant y muestra este repositorio en HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

1. Selecciona el botón de arriba, o abre **HACS** en Home Assistant, busca **HomeDarts** y ábrela.
2. Selecciona **Download**.
3. Reinicia Home Assistant.

HACS muestra las versiones nuevas como una actualización en **Configuración → Actualizaciones**. La ventana de la actualización muestra las notas de la versión. HACS instala el paquete firmado `homedarts.zip`, el mismo archivo que en una [instalación manual](#manualmente).

La integración está entre los repositorios por defecto de HACS desde el 20 de octubre de 2026 ([hacs/default#11306](https://github.com/hacs/default/pull/11306)). Si antes la añadiste como repositorio personalizado, no tienes que hacer nada: HACS ya no la muestra entre los repositorios personalizados y conserva tu instalación y sus actualizaciones.

¿Quieres probar las betas? [Betas for testers](installation.md#betas-for-testers) explica cómo las ofrece HACS.

### Manualmente

1. Descarga `homedarts.zip` de la última versión en [GitHub](https://github.com/Dennis-Otto/homedarts-for-autodarts/releases). Contiene los archivos de la integración, sin una carpeta alrededor.
2. Crea la carpeta `custom_components/homedarts` en tu configuración de Home Assistant y descomprime allí el archivo. El resultado es `config/custom_components/homedarts/manifest.json`.
3. Reinicia Home Assistant.

El flujo de publicación firma cada paquete: `gh attestation verify homedarts.zip --repo Dennis-Otto/homedarts-for-autodarts` comprueba con la GitHub CLI que se construyó a partir de este repositorio, consulta [signed release packages](releases.md#signed-release-packages).

## Añadir tu diana

[![Abre tu Home Assistant y empieza a configurar HomeDarts for Autodarts.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

Hay tres formas de añadir una diana Autodarts. Todas terminan en la misma diana, totalmente local. Una cuarta añade una [diana sin Autodarts](#4-una-diana-sin-autodarts).

Qué forma encaja con tu diana:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/add-board-dark.png">
  <img src="images/en/add-board-light.png" alt="Which way to add a board: a dartboard without Autodarts gets the fourth way, Dartboard without Autodarts, and its darts are entered on the keypad. An Autodarts board with Board Manager 2 usually appears by itself as Autodarts board found under Discovered: select Add and confirm. Otherwise, enter the address of the board PC if you know it, or search for boards on this network, which opens the address form when it finds no board. Every way with Autodarts ends with the same local board, one device with all its entities" lang="en" width="480">
</picture>

<img src="images/en/setup-menu.png" alt="El menú de configuración de HomeDarts: buscar dianas en esta red, introducir la dirección de una diana o una diana sin Autodarts" width="520">

### 1. Descubrimiento automático (Board Manager 2)

Board Manager 2 se anuncia en la red (mDNS, `_autodarts-board._tcp`). Home Assistant muestra entonces **Diana Autodarts encontrada** en **Configuración → Dispositivos y servicios → Descubierto**. Selecciona **Añadir** y confirma. La ventana indica la dirección, la versión del Board Manager y el número de cámaras.

Si la diana recibe más tarde una nueva dirección IP, el anuncio actualiza automáticamente la dirección configurada.

### 2. Buscar dianas en esta red

Elige **Buscar dianas en esta red**. La integración pregunta al servicio público de descubrimiento de Autodarts, que también usa la aplicación Board Manager, qué dianas están registradas desde tu conexión a internet. Elige tu diana, y la integración se conecta a ella en local. La entrada y el dispositivo toman el nombre que la diana tiene en Autodarts.

> El servicio de descubrimiento ve tu dirección IP pública, como cualquier sitio web. No se envía nada más. Si el servicio no está disponible o no encuentra ninguna diana nueva, se abre en su lugar el formulario de la dirección.

### 3. Introducir la dirección de la diana

Elige **Introducir la dirección de la diana** e introduce la dirección IP o el nombre de host del PC de la diana, por ejemplo `192.0.2.10` o `autodarts.local`, sin `http://` y sin puerto. El puerto es normalmente **3180**.

<img src="images/en/setup-local.png" alt="El formulario para introducir la dirección y el puerto del Board Manager" width="520">

La integración lee el ID de la diana del Board Manager. Rechaza las direcciones a las que no llega o que aún no tienen una diana configurada.

> **Consejo:** dale al PC de la diana una dirección IP fija en tu router. Con Board Manager 2, el descubrimiento mantiene la dirección al día de todos modos.

### 4. Una diana sin Autodarts

Elige **Diana sin Autodarts: introduce tú cada dardo** y dale un nombre a la diana, como *Garaje*. Introduces sus dardos en el teclado numérico de la tarjeta en directo y del marcador, y los juegos, el entrenamiento y las estadísticas funcionan como con Autodarts; [Play without Autodarts](without-autodarts.md) lo explica todo. Puedes tener varias, junto a dianas Autodarts, y cada una puede [recibir más tarde su diana Autodarts](without-autodarts.md#autodarts-later).

<img src="images/en/setup-manual.png" alt="El formulario de una diana sin Autodarts, con el nombre Dartboard rellenado" width="520">

### Después de la configuración

Home Assistant crea un dispositivo, con el nombre de tu diana, con todas las [entidades](entities.md). Para un panel con todo, ve a **Configuración → Paneles de control → Añadir panel de control → HomeDarts**, como dice la ventana al final de la configuración: el [panel automático](cards.md#automatic-dashboard) construye sus vistas a partir de tus dianas. En un panel propio, **Añadir tarjeta** encuentra las tarjetas cuando buscas *HomeDarts*; consulta la [guía de las tarjetas](cards.md).

[De cero al marcador](getting-started.es.md) sigue con el marcador en una tableta y tu primera partida.
