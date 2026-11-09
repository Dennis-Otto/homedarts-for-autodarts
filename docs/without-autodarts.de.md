---
description: "Spiele an jeder Steeldartscheibe ohne Autodarts: Gib jeden Dart auf einem Tastenfeld, Tablet oder Handy ein, mit allen Spielen, Training und Statistik."
---

# Spielen ohne Autodarts

[← Dokumentation](README.de.md) · [English](without-autodarts.md)

Kein Autodarts an deinem Board? Die Integration funktioniert mit jeder Steeldartscheibe: Du gibst jeden Dart selbst auf einem Tastenfeld ein, auf einem Tablet neben dem Board oder auf deinem Handy, und bekommst alle Spiele, die Trainingseinheiten und alle Statistiken, genau wie mit automatischer Erkennung.

<img src="images/de/manual-entry.webp" alt="Animation: die Anzeigetafel einer Dartscheibe ohne Autodarts auf einem Tablet. Alex tippt zweimal T und 20 und dann T und 19, die Aufnahme zeigt 177 und der Status Aufnahme komplett; zwei Tipps auf Nächster Spieler geben an Sam weiter" width="760">

**Auf dieser Seite:** [Für wen](#für-wen) · [Einrichten](#einrichten) · [Darts eingeben](#darts-eingeben) · [Was alles funktioniert](#was-alles-funktioniert) · [Was anders ist](#was-anders-ist) · [Ein Granboard](#ein-granboard) · [Mehrere Boards](#mehrere-boards) · [Autodarts später](#autodarts-später)

## Für wen

- **Eine Dartscheibe ohne Kameras.** Spiele X01 mit Anzeigetafel und Checkout-Weg, Cricket auf einer Kreidetafel, Partyspiele für bis zu acht und Turniere, und verfolge deine Averages, ohne eine automatische Erkennung zu kaufen.
- **Ein zweites Board,** etwa im Keller oder bei Freunden, neben einem Autodarts-Board im Wohnzimmer. Jedes Board führt eigene Statistiken.
- **Zum Ausprobieren,** bevor ein Autodarts-System kommt. Nichts davon braucht ein Konto oder das Internet.

## Einrichten

Installiere zuerst die Integration: Die Schritte 1 bis 3 von [Vom Start bis zur Anzeigetafel](getting-started.de.md) zeigen, wie es mit Home Assistant und HACS geht.

[![Öffne deine Home-Assistant-Instanz und beginne mit der Einrichtung von HomeDarts for Autodarts.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

1. Wähle den Knopf oben, oder öffne **Einstellungen → Geräte & Dienste → Integration hinzufügen → HomeDarts for Autodarts**.
2. Wähle **Dartscheibe ohne Autodarts: jeden Dart selbst eingeben**.
3. Gib dem Board einen Namen, etwa *Keller*, und wähle **Übermitteln**. Die Integration legt ein Gerät mit diesem Namen an, mit den Entitäten der Spiele, des Trainings und der Statistiken.
4. Lege das Dashboard an: **Einstellungen → Dashboards → Dashboard hinzufügen → HomeDarts**. Seine Ansichten *Live* und *Anzeigetafel* haben das Tastenfeld.

<img src="images/de/setup-manual.png" alt="Das Formular der Einrichtung für eine Dartscheibe ohne Autodarts, mit dem eingetragenen Namen Dartboard" width="580">

## Darts eingeben

An einer Dartscheibe ohne Autodarts zeigen die Live-Karte und die Anzeigetafel das Tastenfeld unter der Aufnahme, ohne dass du eine Option einschalten musst:

- **Ein Dart:** Tippe **S**, **D** oder **T**, dann die Zahl. **25**, **Bull** und **Fehlwurf** haben eigene Tasten. Jeder Dart beginnt wieder als Single.
- **Wo er steckt:** **Scheibe** oben im Tastenfeld zeigt die Scheibe statt der Tasten. Tippe, wo der Dart steckt, und das Feld ergibt sich aus der Stelle. So eingegebene Darts zählen auch für die [Dart-Positionen und ihre Streuung](statistics.de.md#trefferbild-und-dart-positionen). Auf dem Handy zielt ein Finger mit einer Lupe, und zwei Finger zoomen, wie beim [Korrigieren eines Darts](scoreboard.de.md#darts-korrigieren-und-eingeben).
- **Die Punkte einer Aufnahme:** In X01 nimmt **Punkte** oben im Tastenfeld die Aufnahme mit ihrer Punktzahl statt mit ihren Darts, wie am Dartautomaten: Tippe 140 und **OK**. Das Tastenfeld sagt, welchen Rest die Punkte lassen. Ein Checkout fragt nach seinen Darts und den Darts auf ein Doppel, und eine Aufnahme, die ein Doppel in Reichweite ließ, fragt nach den Darts darauf, für die Checkout-Quote; ein Tipp antwortet. Mehr Punkte, als der Spieler noch hat, sind überworfen, ebenso der Rest, wo kein Doppel ihn checkt, etwa 159; das Tastenfeld sagt es, bevor die Punkte zählen. Punkte, die keine Aufnahme vom Rest des Spielers aus ergibt, etwa 179, oder 180 vor dem Eröffnungs-Double mit Double-In, lassen **OK** aus. Die Felder einer solchen Aufnahme bleiben unbekannt, deshalb zählt sie für die Averages, die 180er, die Checkouts und die Bestleistungen, aber nicht für das Trefferbild, die Doppel oder die Triple.

  <img src="images/de/manual-score.webp" alt="Animation: die Anzeigetafel einer Dartscheibe ohne Autodarts in einem 101-Leg; Alex hat noch 40, tippt Punkte, 4, 0 und OK; das Tastenfeld fragt nach den Darts für den Checkout, 2, und den Darts auf ein Doppel, 1; Alex gewinnt das Match gegen Sam, und die Match-Zusammenfassung zählt den Checkout und einen Dart auf ein Doppel" width="760">

- **Die Aufnahme:** Nach dem dritten Dart sagt der Status *Aufnahme komplett*. **Nächster Spieler** beendet die Aufnahme; er braucht einen zweiten Tipp, damit ein versehentlicher Tipp nie weitergibt. Ohne Dart gibt er weiter, was als Aufnahme mit drei Fehlwürfen zählt.
- **Ein Fehler:** Tippe auf einen Dart der Aufnahme, um ihn in ein anderes Feld zu legen. Solange kein Dart der nächsten Aufnahme eingegeben ist, nimmt der gebogene Pfeil von **Letzte Aufnahme zurück** die letzte Aufnahme zurück, samt dem Spiel, wie es war.

<img src="images/de/manual-live.png" alt="Die Live-Karte der Dartscheibe ohne Autodarts namens Garage: Sam hat T20 und S19 für 79 eingegeben, in einem 501-Match gegen Alex, der noch 324 braucht; die Scheibe zeigt beide Felder, das Tastenfeld steht unter den Darts, und es gibt keine Fußzeile mit Verbindungen oder Erkennung" width="760">

Die [Aktionen](entities.de.md#dart-eingeben-homedartsthrow_dart) `homedarts.throw_dart`, [`homedarts.enter_visit`](entities.de.md#aufnahmepunkte-eingeben-homedartsenter_visit), `homedarts.next_player` und `homedarts.undo_visit` tun dasselbe aus einer Automation, einem Skript oder einem eigenen Knopf; bei mehreren Boards nennst du die `config_entry_id` des Boards.

**Per Sprache:** Mit dem Blueprint [Enter darts by voice](automations.de.md#enter-darts-by-voice) sagst du Assist deine Darts, wie am Dartautomaten: „Alex hat 140“, „Checkout mit zwei Darts“, „Triple 20“, „Nächster Spieler“ oder „Rückgängig“, auf Deutsch, Englisch, Spanisch, Französisch oder Niederländisch. Assist antwortet in den Worten des Callers der Anzeigetafel, etwa „140 für Alex, noch 361. Sam, du brauchst 501.“, und lehnt eine Aufnahme für einen Spieler ab, der nicht am Board ist.

<img src="images/de/manual-voice.webp" alt="Animation: die Anzeigetafel einer Dartscheibe ohne Autodarts mit Assist darüber; Alex hat 140, Triple 20 und Single Bull werden Assist eingetippt, das 140 für Alex, noch 361. Sam, du brauchst 501 antwortet, dann Triple 20, noch 441, und 25, noch 416; der Dialog schließt bei Alex mit 361 und Sam mit 416, mit Triple 20 und 25 in seiner Aufnahme" width="760">

## Was alles funktioniert

Alles, was die Integration mit Darts macht, denn dafür hat sie die Kameras nie gebraucht:

- **Jedes Spiel:** X01 von 101 bis 1001 mit Legs, Sätzen, Double-In und -Out, dem Checkout-Weg und Stellwürfen, dem Ausbullen, Teams und Handicaps; die sechs Cricket-Spiele; die neun Partyspiele für bis zu acht; die acht Trainingsspiele; der [Bot](games.de.md#gegen-den-bot-spielen) und [Turniere](games.de.md#turniere).
- **Jede Statistik:** Trainingseinheiten, Bestleistungen, das Tagesziel und die Serie, Spielerprofile mit ihren Abzeichen, Erfolge, Trends, Doppel, die Bestenliste, der Wochenbericht, der Trainingskalender und der Export. Von Hand eingegebene Darts zählen für alles wie erkannte.
- **Der Bildschirm am Board:** die [Anzeigetafel](scoreboard.de.md) mit dem Bildschirm für ein neues Spiel, dem Caller, den Feiern und dem Ruhemodus.
- **Automationen:** Die Board-Ereignisse, etwa `visit_completed` oder `leg_won`, kommen wie mit einem Board, mit `manual: true` und der Quelle `manual`, daher funktionieren die [Blueprints](automations.de.md#blueprints) für Lichtshow, Caller und Berichte unverändert.

## Was anders ist

| Merkmal | Mit Autodarts | Ohne Autodarts |
| --- | --- | --- |
| Darts | Von den Kameras erkannt, mit einem Tipp korrigiert | Auf dem Tastenfeld eingegeben |
| Status | Bereit, Entnahme, Erkennung gestoppt und mehr | *Darts eingeben* und *Aufnahme komplett*; der Sensor *Erkennungsstatus* zeigt *Eingabe von Hand* |
| Tastenfeld | Eine Option, solange *Übungsspiel manuelle Eingabe* an ist | Immer da, außer `keypad: false` einer Karte blendet es aus |
| Darts der Aufnahme | Von Hand eingegebene Darts bekommen einen gestrichelten Rahmen | Kein Rahmen, weil jeder Dart von Hand kommt; Korrekturen behalten ihren Stift |
| Entitäten | Spiele, Training und Statistiken, dazu Erkennung, Verbindung, Bewegung, Kameras, Board-Einstellungen und der Board-PC | Spiele, Training und Statistiken |
| Automatisches Dashboard | Ansichten *Live*, *Anzeigetafel*, *Training*, *Spieler*, *Spieleinstellungen* und *Board* | Keine Ansicht *Board*: Es gibt keine Erkennung, Kamera oder Board-PC |
| Board-Status-Karte | Erkennung, Verbindungen, Board-PC, Kameras und Wartung | Ein Hinweis, dass das Board nichts davon hat |
| Dart-Positionen | Für jeden erkannten Dart | Für Darts, die auf der Scheibe des Tastenfelds eingegeben sind |
| Punkte einer Aufnahme | Mit *Übungsspiel manuelle Eingabe*, solange kein Dart der Aufnahme im Board steckt | In jedem X01-Leg |
| Erkennungsqualität, Kalibrierung, Online-Matches | Ja | Nein |

Ein Bildschirm, der nur die Anzeigetafel zeigt, etwa ein Fernseher ohne Touch, blendet das Tastenfeld mit der Option `keypad: false` der Karte aus; siehe [Dashboard-Karten](cards.de.md#darts-korrigieren-und-eingeben).

## Ein Granboard

Ein Granboard sendet seine Darts über Bluetooth an Home Assistant, also gibt sie niemand ein: Home Assistant findet das Board und richtet es als Dartscheibe ohne Autodarts ein, die sie empfängt, mit allem auf dieser Seite. Siehe [Granboard über Bluetooth](granboard.de.md) *(experimentell)*.

## Mehrere Boards

Jede Dartscheibe ohne Autodarts ist ein eigener Eintrag und ein eigenes Gerät, mit eigenen Entitäten, Spielen und Statistiken, ebenso jedes Autodarts-Board daneben. Das automatische Dashboard gibt jedem Board seine Ansichten. Die Aktionen der Integration brauchen dann die `config_entry_id` des Boards, wie bei mehreren Autodarts-Boards. Ein [Turnier auf mehreren Boards](games.de.md#ein-turnier-auf-mehreren-boards) spielt auf Dartscheiben mit und ohne Autodarts nebeneinander.

Um ein Board samt seinen Statistiken zu entfernen, lösche seinen Eintrag unter **Einstellungen → Geräte & Dienste → HomeDarts for Autodarts**.

## Autodarts später

Bekommt deine Dartscheibe Autodarts, schließe das Board an sie an, statt ein neues hinzuzufügen, und alles bleibt: die Spiele, die Trainingseinheiten, die Spieler, ihre Abzeichen und jede Statistik, die Entitäts-IDs und deine Dashboards.

1. Richte das Autodarts-Board wie gewohnt in seinem Board Manager ein.
2. Öffne **Einstellungen → Geräte & Dienste → HomeDarts for Autodarts**, das Menü (⋮) der Dartscheibe → **Neu konfigurieren**.
3. Wähle **Boards im Netzwerk suchen** oder **Board-Adresse eingeben**, wie beim [Hinzufügen eines Boards](installation.de.md#board-hinzufügen).

Die Dartscheibe hat danach die ID des Boards, die Erkennung, die Kameras, die Board-Einstellungen und die Steuerung, und das automatische Dashboard ihre Ansicht *Board*. *Übungsspiel manuelle Eingabe* bleibt an, sodass die Darts des Tastenfelds weiter zählen; schaltest du sie aus, zählen die Kameras. Findet Home Assistant das Board von selbst und bietet *Autodarts-Board gefunden* an, ignoriere das Angebot und konfiguriere die Dartscheibe neu: Als neuer Eintrag hinzugefügt, finge das Board mit eigenen Statistiken an.
