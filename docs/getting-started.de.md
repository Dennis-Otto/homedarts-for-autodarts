---
description: "Von null bis zur Anzeigetafel auf einem Tablet an deinem Autodarts-Board in etwa einer Stunde: Home Assistant, HACS, die Integration und das Dashboard."
---

# Von null bis zur Anzeigetafel

[← Dokumentation](README.de.md) · [English](getting-started.md)

Du spielst auf einem Autodarts-Board und hast noch nie Home Assistant benutzt? Diese Anleitung bringt dich von null bis zur Anzeigetafel auf einem Tablet neben deinem Board. Home Assistant, HACS und die Integration sind kostenlos. Rechne mit etwa einer Stunde; das meiste davon ist die Einrichtung von Home Assistant selbst.

<img src="images/de/scoreboard-lobby.png" alt="Die Spielauswahl auf einem Tablet im Querformat: die Spiele nach Gruppen mit gewähltem 501, Alex und Sam mit ihren Bildern, Sam startet mit 301, drei Legs pro Satz, Double-Out und die Starttaste" width="760">

**Auf dieser Seite:** [Was du brauchst](#was-du-brauchst) · [1. Home Assistant installieren](#1-home-assistant-installieren) · [2. HACS installieren](#2-hacs-installieren) · [3. Die Integration installieren](#3-die-integration-installieren) · [4. Board hinzufügen](#4-board-hinzufügen) · [5. Dashboard anlegen](#5-dashboard-anlegen) · [6. Anzeigetafel neben das Board](#6-anzeigetafel-neben-das-board) · [7. Das erste Spiel](#7-das-erste-spiel) · [Wie es weitergeht](#wie-es-weitergeht) · [Wenn etwas nicht klappt](#wenn-etwas-nicht-klappt)

## Was du brauchst

- **Dein Autodarts-Board,** eingerichtet und funktionsfähig. Die getesteten Setups stehen unter [Unterstützte Geräte](README.de.md#unterstützte-geräte). Kein Autodarts? [Spiele ohne Autodarts](without-autodarts.de.md) an jeder Dartscheibe und gib deine Darts auf einem Tastenfeld ein.
- **Ein Gerät für Home Assistant,** das ständig läuft, im selben Netzwerk wie das Board: ein Raspberry Pi 4 oder 5, ein Mini-PC oder eine virtuelle Maschine auf einem Rechner, der immer an ist. Home Assistant verkauft auch fertige Geräte. Nimm ein eigenes Gerät: Der Board-PC braucht seine Leistung für die Erkennung.
- **Ein kostenloses GitHub-Konto,** über das HACS Integrationen herunterlädt.
- **Einen Bildschirm für die Anzeigetafel,** wenn du einen möchtest: ein Tablet, einen Fernseher mit Browser oder ein altes Handy.

## 1. Home Assistant installieren

Folge der offiziellen [Installationsanleitung](https://www.home-assistant.io/installation/) für dein Gerät; sie zeigt jeden Schritt mit Bildern. Auf einem Raspberry Pi wählst du **Home Assistant OS** ([Anleitung für den Raspberry Pi](https://www.home-assistant.io/installation/raspberrypi)). Die Anleitungen sind auf Englisch, die Oberfläche von Home Assistant ist danach auf Deutsch.

Zum Schluss öffnest du Home Assistant im Browser, meist unter `http://homeassistant.local:8123`, und legst dein Konto an. Die [Anleitung zum Onboarding](https://www.home-assistant.io/getting-started/onboarding/) erklärt die Fragen.

## 2. HACS installieren

HACS ist der Store für Integrationen und Karten aus der Community, wie diese hier. Folge der offiziellen Anleitung, um [HACS herunterzuladen](https://www.hacs.xyz/docs/use/download/download/) und es mit deinem GitHub-Konto [einzurichten](https://www.hacs.xyz/docs/use/configuration/basic/). Danach steht **HACS** in der Seitenleiste von Home Assistant.

## 3. Die Integration installieren

[![Home Assistant öffnen und dieses Repository in HACS anzeigen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

1. Wähle die Schaltfläche oben und bestätige die Adresse deines Home Assistant. HACS öffnet diese Integration. Ohne die Schaltfläche: Öffne **HACS**, suche nach **HomeDarts** und öffne es.
2. Wähle **Download**.
3. Starte Home Assistant neu: **Einstellungen → System**, oben rechts die Ein-/Aus-Taste, **Home Assistant neu starten**.

## 4. Board hinzufügen

[![Home Assistant öffnen und HomeDarts for Autodarts einrichten.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

Mit Board Manager 2 findet Home Assistant das Board meist von selbst: **Einstellungen → Geräte & Dienste** zeigt unter *Entdeckt* **Autodarts-Board gefunden**. Wähle **Hinzufügen** und bestätige. Die Animation zeigt den Weg von hier bis zur Anzeigetafel, in unter einer Minute.

<img src="images/de/setup.webp" alt="Animation: die Einrichtung in fünf Schritten mit Untertiteln, auf dem Bildschirm eines Telefons. 1: Home Assistant zeigt das gefundene Board unter Entdeckt in Geräte & Dienste. 2: Hinzufügen, und OK im Dialog Autodarts-Board gefunden; das Board ist eingerichtet und seine Geräteseite öffnet sich. 3: Einstellungen, Dashboards, Dashboard hinzufügen. 4: Die Suche findet HomeDarts, der Titel HomeDarts, Erstellen. 5: Das neue Dashboard öffnet sich mit seiner Live-Ansicht, dann mit seiner Anzeigetafel, die drei Triple 20 bis 180 zählt" width="100%">

Sonst wählst du die Schaltfläche oben und dann **Boards im Netzwerk suchen** oder **Board-Adresse eingeben** mit der IP-Adresse des Board-PCs. Ein Autodarts-Konto brauchst du nicht.

<img src="images/de/setup-menu.png" alt="Das Einrichtungsmenü von HomeDarts: Boards im Netzwerk suchen, eine Board-Adresse eingeben oder eine Dartscheibe ohne Autodarts" width="520">

Die [Installationsanleitung](installation.de.md#board-hinzufügen) erklärt die Wege im Detail. Ohne Autodarts wählst du **Dartscheibe ohne Autodarts: jeden Dart selbst eingeben** und gibst dem Board einen Namen; [Spielen ohne Autodarts](without-autodarts.de.md) zeigt den Rest.

## 5. Dashboard anlegen

[![Home Assistant öffnen und deine Dashboards anzeigen.](https://my.home-assistant.io/badges/lovelace_dashboards.svg)](https://my.home-assistant.io/redirect/lovelace_dashboards/)

Die Schaltfläche öffnet **Einstellungen → Dashboards**. Wähle dort **Dashboard hinzufügen → HomeDarts**, gib ihm einen Titel und wähle **Erstellen**: Das legt ein komplettes Dashboard für dein Board an, mit Ansichten für das laufende Spiel, die Anzeigetafel, das Training, die Spieler und das Board. Es aktualisiert sich selbst, wenn du ein Board hinzufügst oder eine neue Version neue Ansichten bringt.

<img src="images/de/dashboard-strategy.png" alt="Die Trainingsansicht des automatischen Dashboards" width="760">

## 6. Anzeigetafel neben das Board

1. Öffne Home Assistant auf dem Tablet im Browser oder in der [Home-Assistant-App](https://companion.home-assistant.io/) und melde dich an. Ein eigener Benutzer ohne Administratorrechte verhindert, dass der Bildschirm deine Einstellungen ändert.
2. Öffne das HomeDarts-Dashboard und dort die Ansicht *Anzeigetafel*.
3. Tippe auf die Vollbild-Taste oben rechts auf der Anzeigetafel: Sie füllt den Bildschirm und lässt ihn an. Wo der Browser ihn nicht anlassen kann, etwa unter einer Adresse mit `http://`, schalte die automatische Bildschirmabschaltung des Tablets aus; siehe [Vollbild](scoreboard.de.md#vollbild).

Die [Anleitung zur Anzeigetafel](scoreboard.de.md#den-bildschirm-einrichten) beschreibt die Einzelheiten und die Optionen, etwa den Caller.

## 7. Das erste Spiel

Tippe auf der Anzeigetafel auf **Neues Spiel**. Wähle 501, füge dich hinzu, setze mit **+ Bot** den Bot dazu, wenn du allein spielst, und tippe auf **501 starten**. Wirf deine Darts: Die Anzeigetafel zählt, zeigt deinen Checkout-Weg und gibt nach jeder Aufnahme an den nächsten Spieler ab.

Erkennt das Board einen Dart falsch, tippst du ihn in der Aufnahme an und korrigierst ihn. Die [Anleitung zu den Spielen](games.de.md#ein-spiel-starten) zeigt alle Spiele und die anderen Wege, eines zu starten.

## Wie es weitergeht

- **Licht und Ton:** Die [Blueprints](automations.de.md#blueprints) lassen dein Licht beim 180er aufblitzen, sagen die Punkte an oder machen ein Foto vom Highlight. Sie kommen mit der Integration und warten auf der Blueprint-Seite von Home Assistant.
- **Dein Fortschritt:** Bestleistungen, ein Trefferbild deiner Darts, Trends und Erfolge stehen in der [Anleitung zur Statistik](statistics.de.md).
- **Freunde zu Besuch:** Teams, Handicaps und Turniere für bis zu 32 Spieler stehen in der [Anleitung zu den Spielen](games.de.md).

## Wenn etwas nicht klappt

- Die [Fehlerbehebung](troubleshooting.de.md) erklärt jede Meldung der Einrichtung und jede Reparaturmeldung.
- Frag in den [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/categories/q-a). Fragen werden dort beantwortet, damit jede Antwort auch dem nächsten Spieler hilft. Deutsch und Englisch sind willkommen.
- Steht dein Setup nicht unter den [unterstützten Geräten](README.de.md#unterstützte-geräte), hilft ein [Kompatibilitätsbericht](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml), ob es klappt oder nicht.
