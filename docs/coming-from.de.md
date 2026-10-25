---
description: "Umstieg auf HomeDarts von Autodarts Local, einer anderen Integration für Autodarts, einer MQTT-Brücke oder darts-caller: was ersetzt was, und wie du umsteigst."
---

# Umstieg von anderen Werkzeugen

[← Dokumentation](README.de.md) · [English](coming-from.md)

Andere Projekte bringen ein Autodarts-Board nach Home Assistant oder daneben. Diese Seite vergleicht sie mit HomeDarts und zeigt für jedes, welche Entitäten, Ereignisse und Blueprints seinen Platz einnehmen und wie du umsteigst, während es installiert bleibt. Die Angaben haben den Stand Oktober 2026 und stammen aus der Dokumentation und dem Code des jeweiligen Projekts, zu denen die Links führen. Hat sich ein Projekt seitdem geändert, [sag uns Bescheid](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions), damit diese Seite fair bleibt.

Du hast HomeDarts bis Version 1.18 genutzt, als es noch Autodarts hieß? Das ist kein anderes Werkzeug: HomeDarts übernimmt deine Boards mit allem, was dazugehört, wie [Von Autodarts zu HomeDarts](new-name.de.md) zeigt.

**Schnell zu:** [Auf einen Blick](#auf-einen-blick) · [Darf es bleiben?](#darf-es-bleiben) · [Autodarts Local](#autodarts-local) · [Integration von Quevinsta](#autodarts-for-home-assistant-von-quevinsta) · [Integration von belese](#autodarts-von-belese) · [Autodarts Connect Online](#autodarts-connect-online) · [Darts Hub](#darts-hub) · [MQTT-Brücken](#mqtt-brücken) · [darts-caller und darts-wled](#darts-caller-und-darts-wled) · [Tools for Autodarts](#tools-for-autodarts) · [Die ursprüngliche Integration](#die-ursprüngliche-integration)

## Auf einen Blick

<!-- --8<-- [start:compare] -->

| Merkmal | HomeDarts | Autodarts-App mit [Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) | [darts-caller](https://github.com/Peschi90/darts-caller) und [darts-wled](https://github.com/Peschi90/darts-wled) | Andere Home-Assistant-Integrationen |
| --- | --- | --- | --- | --- |
| **Läuft ohne Cloud** | Ja, mit der [lokalen Schnittstelle](how-it-works.de.md#datenschutz) des Board Managers | Nein, mit einem [Autodarts-Konto](https://autodarts.com/) | Nein, darts-caller [meldet sich bei Autodarts an](https://github.com/Peschi90/darts-caller#autodarts-login) | Manche ([Einzelheiten](coming-from.de.md#darf-es-bleiben)) |
| **Entitäten und Ereignisse in Home Assistant** | Ja, ein [Ereignis](entities.de.md#board-ereignisse) für jeden Dart, jede Aufnahme, Entnahme, jedes Überwerfen, Leg und Match | Nein | Nein | Sensoren der aktuellen Aufnahme oder des Spiels |
| **Blueprints** | [Sechzehn Blueprints](automations.de.md#blueprints) | Nein | Nein | Nein |
| **Lichtshow** | Blueprint [Light show](automations.de.md#light-show), für WLED oder jedes Licht | WLED, mit Tools | WLED, mit darts-wled | Eigene Automationen |
| **Caller** | Auf der [Anzeigetafel](scoreboard.de.md#der-caller) oder deinen [Lautsprechern](automations.de.md#welcher-caller) | In der App, mit einer Premium-Stimme in [Plus](https://autodarts.com/); mehr mit Tools | Sprachpakete, mit darts-caller | Nein |
| **Statistik bleibt zu Hause** | [Ja](statistics.de.md): Averages, Trefferbilder, Profile und ein Jahr Verlauf | Nein, im Autodarts-Konto | Nein | Nein |
| **Ohne Autodarts-Board** | Ja, auf einem [Tastenfeld](without-autodarts.de.md) oder einem [Granboard über Bluetooth](granboard.de.md) *(experimentell)* | Ja, auf einem Tastenfeld oder mit [Lens](https://autodarts.com/) | Nein | Nein |
| **Online-Matches** | Deine Darts, und die Momente des Matches über die [Online-Brücke](online-matches.de.md) *(experimentell)* | Ja | Ja | Manche, über die Cloud |
| **Lizenz und Kosten** | [MIT](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), kostenlos | Autodarts: ein kostenloser Tarif und das bezahlte [Plus](https://autodarts.com/); Tools: [CC BY-NC 4.0](https://github.com/creazy231/tools-for-autodarts/blob/main/LICENSE) | Kostenlos, ohne angegebene Lizenz | MIT, Apache 2.0 oder ohne Lizenzdatei |

<!-- --8<-- [end:compare] -->

*Stand Oktober 2026, aus der Dokumentation und dem Code jedes Projekts. Die Abschnitte unten haben die Einzelheiten und die Quellen.*

## Darf es bleiben?

Ja, jedes davon. Home Assistant lädt eine Integration pro Domain, und HomeDarts hat eine eigene Domain, `homedarts`. Deshalb darf jedes andere daneben installiert bleiben, während du deine Automationen umstellst, und gehen, wenn nichts es mehr nutzt. HomeDarts lässt ihre Einträge, wie sie sind: Es übernimmt nur die Boards, die es unter seinem früheren Namen Autodarts eingerichtet hat.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/coming-from-dark.png">
  <img src="images/de/coming-from-light.png" alt="Umstieg von einer anderen Integration für Autodarts: Die Integration unter ihrem früheren Namen Autodarts, bis Version 1.18, ist kein anderes Werkzeug: Aktualisiere sie, und HomeDarts übernimmt ihre Boards. Jede andere Integration, etwa das ursprüngliche HACSAutodarts, die von Quevinsta oder belese, Autodarts Local, Autodarts Connect Online, Darts Hub oder eine MQTT-Brücke, darf während des Umstiegs bleiben, weil HomeDarts eine eigene Domain hat, homedarts. Installiere HomeDarts daneben und füge das Board hinzu, stell die Automationen auf die Ereignisse und Blueprints von HomeDarts um, lösche dann die Einträge der alten Integration, entferne sie in HACS und starte Home Assistant neu" width="520">
</picture>

| Projekt | Domain | Liest das Board über | Neben HomeDarts |
| --- | --- | --- | --- |
| [Ursprüngliche Integration](#die-ursprüngliche-integration) von Trkal | `autodarts` | Die Autodarts-Cloud und den Board Manager für die Darts | Darf bleiben |
| [Autodarts for Home Assistant](#autodarts-for-home-assistant-von-quevinsta) von Quevinsta | `autodarts` | Den Board Manager, lokal | Darf bleiben |
| [autodarts](#autodarts-von-belese) von belese | `autodarts` | Die Autodarts-Cloud | Darf bleiben |
| [Autodarts Local](#autodarts-local) | `autodarts_local` | Den Board Manager, lokal | Darf bleiben |
| [Autodarts Connect Online](#autodarts-connect-online) | `autodarts_connect` | Die Autodarts-Cloud | Darf bleiben |
| [Darts Hub](#darts-hub) | `darts_hub` | darts-hub oder darts-caller und den Board Manager | Darf bleiben |
| [MQTT-Brücken](#mqtt-brücken) | `mqtt` | Ein eigenes Programm und einen MQTT-Broker | Darf bleiben |
| [darts-caller und darts-wled](#darts-caller-und-darts-wled) | Außerhalb von Home Assistant | Die Autodarts-Cloud | Darf bleiben; lass einen Caller sprechen |
| [Tools for Autodarts](#tools-for-autodarts) | Im Browser | Die Web-App von Autodarts | Bleibt; die Online-Brücke nutzt es |

### Schritt für Schritt umsteigen

1. **Installiere HomeDarts daneben** und füge dein Board hinzu, wie die [Installationsanleitung](installation.de.md#board-hinzufügen) es beschreibt. Beide folgen demselben Board.
2. **Stell deine Automationen um,** eine nach der anderen, mit den Tabellen unten. Der Dialog einer Entität listet unter **Verwandt** die Automationen und Skripte, die sie nutzen.
3. **Lösche die Einträge der alten Integration** unter **Einstellungen → Geräte & Dienste**, sobald nichts sie mehr nutzt: Öffne die Integration und wähle bei jedem Eintrag im Menü (⋮) **Löschen**.
4. **Entferne ihren Code.** Öffne die Integration in HACS, dann ihr Menü (⋮) → **Entfernen**. Hast du sie als benutzerdefiniertes Repository hinzugefügt, lösche es auch unter dem Menü (⋮) → **Benutzerdefinierte Repositories**. Bei einer manuellen Installation löschst du ihren Ordner in `config/custom_components`, etwa `config/custom_components/autodarts`.
5. **Starte Home Assistant neu.**

Die Entitäts-IDs unten gehören zu einem Board namens *Autodarts Board* in einem deutschsprachigen Home Assistant, wie in den [Beispielen der Automationen](automations.de.md#beispiele). Deine findest du auf der Geräteseite des Boards.

## Autodarts Local

[Autodarts Local](https://github.com/Mastershort/ha-autodarts-local) von Mastershort, Domain `autodarts_local`, liest jede Sekunde den Zustand des Board Managers: ob das Board online ist, seinen Status, die Darts der Aufnahme und ihre Summe, dazu drei Tasten für die Erkennung.

| Autodarts Local | Hier |
| --- | --- |
| *Verbindung*: `Online` oder `Offline` | Der Binärsensor *Lokale Verbindung*, unter [Zustand und Verbindungen](entities.de.md#zustand-und-verbindungen) |
| *Status*, etwa `Throw` oder `Takeout` | *Erkennungsstatus*: `throw`, `takeout`, `takeout_in_progress` und die anderen der [aktuellen Aufnahme](entities.de.md#aktuelle-aufnahme), mit dem Ereignis `status_changed`; für die Entnahme die Ereignisse `takeout_started` und `takeout_finished` |
| *Aktuelle Aufnahme* | *Erkannte Aufnahmepunkte*, und das Ereignis `visit_thrown` in dem Moment, in dem der dritte Dart landet |
| *Anzahl Würfe* | *Darts in der Aufnahme* |
| *Wurf 1*, *Wurf 2*, *Wurf 3* | Das Attribut `throws` von *Erkannte Aufnahmepunkte*, der Sensor *Letzter Dart* und das Ereignis `dart_detected` mit `dart_index` und `segment` |
| Die Tasten *Erkennung Starten*, *Erkennung Stoppen* und *Erkennung Zurücksetzen* | Die Tasten *Erkennung starten*, *Erkennung stoppen* und *Erkennung zurücksetzen* und der Schalter *Erkennung*, unter [Steuerung](entities.de.md#steuerung) |
| Die Beispiel-Automation *Takeout Light* | Der Blueprint [Takeout actions](automations.de.md#takeout-actions) oder das Beispiel [Boardlicht bei der Entnahme](automations.de.md#boardlicht-bei-der-entnahme) |

**Darf bleiben.** Beide nennen das Gerät *Autodarts Board*, so wie HomeDarts ein Board, das du über seine Adresse hinzufügst. Solange beide installiert sind, bekommen die Tasten hier IDs mit `_2` am Ende, etwa `button.autodarts_board_erkennung_starten_2`. Entfernst du Autodarts Local, bevor du das Board hier hinzufügst, bekommen die Tasten die IDs, die deine Automationen schon nutzen, etwa `button.autodarts_board_erkennung_starten`.

## Autodarts for Home Assistant von Quevinsta

[Autodarts for Home Assistant](https://github.com/Quevinsta/autodarts-for-home-assistant) von Quevinsta, Domain `autodarts`, ist für X01 gemacht und liest alle zehn Sekunden den Zustand des Board Managers: die drei Darts und ihre Werte, die Aufnahme, die Restpunkte, ob ein Checkout möglich ist, und das Ergebnis des Legs.

| Integration von Quevinsta | Hier |
| --- | --- |
| *Dart 1*, *Dart 2*, *Dart 3* und ihre Werte | Das Attribut `throws` von *Erkannte Aufnahmepunkte* und das Ereignis `dart_detected` |
| *Throw Summary*, *Turn Total* | *Erkannte Aufnahmepunkte*, und `segments` und `score` des Ereignisses `visit_thrown` |
| *Remaining*, *Checkout Possible* | *Übungsspiel Restpunkte* und *Übungsspiel Checkout-Weg*, der *unbekannt* ist, wenn es keinen Weg gibt, in einem [Übungsspiel](entities.de.md#übungsspiel) |
| *Leg Won*, *Leg Lost*, *Leg Result* | Die Ereignisse `leg_won` und `match_won`, mit dem `name` des Gewinners |
| *Autodarts Status* | Der Binärsensor *Lokale Verbindung* |

Hier zählt Home Assistant das Übungsspiel selbst: X01 von 101 bis 1001, die Cricket-Spiele, die Partyspiele und die Trainingsspiele. Ein Spiel auf play.autodarts.io zählt der Browser, und seine Punkte kommen nicht nach Home Assistant: Autodarts vergibt keine Client-IDs an Integrationen von Dritten, deshalb gibt es keine Cloud-Verknüpfung ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch).

**Darf bleiben.** Seine Domain ist `autodarts`, die von HomeDarts `homedarts`, deshalb steigst du [Schritt für Schritt um](#schritt-für-schritt-umsteigen).

## autodarts von belese

[autodarts](https://github.com/belese/ha_integrations) von belese, Domain `autodarts`, folgt dem Board über die Autodarts-Cloud, mit der E-Mail-Adresse und dem Passwort deines Autodarts-Kontos. Es zeigt den Zustand des Boards, die Spieler, den Spieler am Board und den Gewinner. Seine letzte Änderung war im Februar 2025.

| Integration von belese | Hier |
| --- | --- |
| Zustand des Boards | *Erkennungsstatus*, lokal und ohne Konto |
| Spieler, aktueller Spieler | `players`, `player` und `name` von *Übungsspiel Restpunkte* in einem Übungsspiel, und das Ereignis `turn_changed` |
| Gewinner | Das Ereignis `match_won` und das Attribut `winner` von *Übungsspiel Restpunkte* |

HomeDarts braucht kein Autodarts-Konto und speichert kein Passwort.

**Darf bleiben.** Seine Domain ist `autodarts`, die von HomeDarts `homedarts`, deshalb steigst du [Schritt für Schritt um](#schritt-für-schritt-umsteigen). Lösche seinen Eintrag am Ende: Er enthält das Passwort deines Kontos.

## Autodarts Connect Online

[Autodarts Connect Online](https://github.com/casef007/HA-autodarts-connect-online) von casef007, Domain `autodarts_connect`, ist eine Beta, die dem Board über die Autodarts-Cloud folgt, mit der E-Mail-Adresse, dem Passwort und der Board-ID deines Kontos. Laut seiner README meldet es sich vorerst mit den öffentlichen Zugangsdaten von darts-caller an. Es sieht Online-Matches und Bot-Spiele, mit Name, Punkten, Average und Cricket-Marks von bis zu vier Spielern, und feuert für jeden Dart das Ereignis `autodarts_throw`.

| Autodarts Connect Online | Hier |
| --- | --- |
| Das Ereignis `autodarts_throw` | Das Ereignis `dart_detected`, lokal, für jeden Dart auf deinem Board |
| Name, Punkte und Average von bis zu vier Spielern | `scores` von *Übungsspiel Restpunkte* für ein Match von bis zu vier Spielern, bis zu acht Spieler in den [Partyspielen](entities.de.md#partyspiele) und 32 in den [Turnieren](entities.de.md#turniere) |
| Cricket-Marks | `marks`, `points` und `mpr` jedes Spielers in den `scores` von *Übungsspiel Restpunkte*, in den [Cricket-Spielen](entities.de.md#cricket) |
| Online-Matches | Deine Darts wie gewohnt, und Überwerfen, gewonnene Legs und Matches über die [Online-Brücke](online-matches.de.md) *(experimentell)* |

**Darf bleiben.** Es sieht heute mehr von einem Online-Match als HomeDarts, etwa die Darts und Punkte deiner Gegner. Spielst du vor allem online, behalte es neben HomeDarts.

## Darts Hub

[Darts Hub](https://github.com/etienne72230/ha-darts-hub) von etienne72230, Domain `darts_hub`, braucht darts-hub oder darts-caller in deinem Netzwerk, auf Port 8079, und den Board Manager auf Port 3180. Es zeigt das Match, bis zu sechs Spieler mit ihren Punkten, die Einzelheiten jedes Darts mit seiner Position und Tasten zum Zurücksetzen und Kalibrieren des Boards.

| Darts Hub | Hier |
| --- | --- |
| Board-Status, aktuelles Ereignis | *Erkennungsstatus* und die [Board-Ereignisse](entities.de.md#board-ereignisse) |
| Spieler und Punkte des Matches | *Übungsspiel Restpunkte* mit seinen `scores`, für das Übungsspiel, das Home Assistant zählt |
| Dart 1 bis 3 und der letzte Dart, mit Wert, Multiplikator, Feld und Position | Das Attribut `throws` von *Erkannte Aufnahmepunkte*, mit `segment`, `multiplier`, `score`, `bed` und der Position `x`/`y` |
| Die Tasten *Reset Board* und *Calibrate Board* | *Erkennung zurücksetzen* und *Automatische Kalibrierung starten* |

**Darf bleiben.** HomeDarts braucht weder darts-hub noch darts-caller.

## MQTT-Brücken

MQTT-Brücken wie [Autodarts MQTT](https://github.com/Quevinsta/autodarts-mqtt) von Quevinsta sind Programme, die du selbst startest. Sie veröffentlichen den Board-Status, die Zahl der Darts und Averages an einen MQTT-Broker, und Home Assistant legt ihre Entitäten über MQTT Discovery an.

| Autodarts MQTT | Hier |
| --- | --- |
| Board Status | *Erkennungsstatus* |
| Number of Throws | *Darts in der Aufnahme* |
| 3-Dart Average | *Training 3-Dart-Average* der [Trainingssession](entities.de.md#trainingssession) |
| Leg Average | Das `average` des Ereignisses `leg_won` |

**Darf bleiben.** HomeDarts braucht weder einen Broker noch ein eigenes Programm. Um eine Brücke zu entfernen, stoppst du sie und löschst ihr Gerät unter **Einstellungen → Geräte & Dienste → MQTT**.

## darts-caller und darts-wled

[darts-caller](https://github.com/Peschi90/darts-caller) spielt die Tondateien eines Sprachpakets zum Stand eines Autodarts-Spiels und gibt das Spiel an andere Programme weiter, etwa an [darts-wled](https://github.com/Peschi90/darts-wled), das damit WLED-Lichter steuert. [darts-hub](https://github.com/lbormann/darts-hub) lädt sie herunter, richtet sie ein und startet sie. Sie laufen auf einem PC, und darts-caller meldet sich bei deinem Autodarts-Konto an und folgt dessen Spielen.

Was Home Assistant jetzt übernimmt:

| darts-caller und darts-wled | Hier |
| --- | --- |
| Ansagen von Punkten und Checkouts | Der [Caller der Anzeigetafel](scoreboard.de.md#der-caller), über den Bildschirm am Board, oder die Blueprints [Dart caller](automations.de.md#dart-caller) und [Practice caller](automations.de.md#practice-caller) auf deinen Lautsprechern; beide spielen auch die [Voice-Packs](scoreboard.de.md#voice-packs) von darts-caller |
| WLED-Effekte für eine 180, ein Überwerfen oder einen Game shot | Der Blueprint [Light show](automations.de.md#light-show) mit deinen [WLED-Presets oder anderem Licht](automations.de.md#lichtshow-mit-wled-und-anderem-licht) |
| Spielereignisse für andere Programme | [Board-Ereignisse](entities.de.md#board-ereignisse) für jeden Dart, jede Aufnahme, Entnahme, jedes Überwerfen, gewonnene Leg und Match, für jede Automation von Home Assistant |

**Darf bleiben.** darts-caller folgt der Cloud und HomeDarts dem Board, deshalb funktionieren beide zugleich. Zwei Caller reden aber durcheinander, und zwei Programme, die dieselben WLED-Lichter steuern, kommen sich in die Quere: Lass von beidem nur eines sprechen und leuchten. In Online-Matches sagt darts-caller auch die Punkte deiner Gegner an, die HomeDarts nicht sieht.

## Tools for Autodarts

[Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) ist eine Browser-Erweiterung für die Web-App von Autodarts, mit weiteren Caller-Stimmen, Soundeffekten, WLED-Effekten, Animationen und vielen Einstellungen für Lobby und Match.

**Bleibt.** Die [Online-Brücke](online-matches.de.md) nutzt seine WLED-Funktion: Sie ruft Home Assistant mit den Momenten eines Online-Matches auf, die zu `online_*`-[Board-Ereignissen](entities.de.md#board-ereignisse) werden. Wie bei darts-caller gilt: Lass im Raum einen Caller sprechen, den der Autodarts-App, den von Tools oder den von Home Assistant.

## Die ursprüngliche Integration

HomeDarts begann als Fork von [Trkal/HACSAutodarts](https://github.com/Trkal/HACSAutodarts), einem Prototyp vom April 2026 mit der Domain `autodarts`. Er folgt dem Board über die Autodarts-Cloud, angemeldet mit deinem Autodarts-Konto, und mit der Adresse des Boards liest er die Darts auch vom Board Manager. Er zeigt den Zustand des Boards, das letzte Ereignis der Erkennung, Modus, Zustand und Runde des Matches, die Aufnahmepunkte und die Darts.

| Ursprüngliche Integration | Hier |
| --- | --- |
| *Board Status* | Der Binärsensor *Lokale Verbindung* |
| *Board Event*, etwa *Throw* oder *Takeout* | *Erkennungsstatus*, mit dem Ereignis `status_changed` |
| *Last Throw*, *Throws in Turn* | Der Sensor *Letzter Dart*, *Darts in der Aufnahme* und das Ereignis `dart_detected` |
| *Visit Score* | *Erkannte Aufnahmepunkte*, und das Ereignis `visit_thrown` in dem Moment, in dem der dritte Dart landet |
| *Game Mode*, *Match State*, *Round*, *Total Turns* | *Übungsspiel* und `game`, `round` und `winner` von *Übungsspiel Restpunkte*, in einem [Übungsspiel](entities.de.md#übungsspiel), das Home Assistant selbst zählt, mit den Ereignissen `leg_won` und `match_won` |

Ein Spiel auf play.autodarts.io kommt hier nicht nach Home Assistant, wie der [Abschnitt zur Integration von Quevinsta](#autodarts-for-home-assistant-von-quevinsta) erklärt.

**Darf bleiben.** Bis Version 1.18 hatte HomeDarts ebenfalls die Domain `autodarts`; seit 2.0 hat es `homedarts`, deshalb laufen beide nebeneinander, und HomeDarts lässt den Eintrag der ursprünglichen Integration, wie er ist. [Von der ursprünglichen Integration umsteigen](installation.de.md#von-der-ursprünglichen-integration-umsteigen) hat die Schritte.
