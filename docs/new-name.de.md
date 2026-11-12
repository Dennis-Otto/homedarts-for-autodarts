---
description: "Die Integration Autodarts heißt jetzt HomeDarts for Autodarts: warum, und wie du deine Boards mit Entitäten, Statistiken und Dashboards übernimmst."
---

# Von Autodarts zu HomeDarts

[← Dokumentation](README.de.md) · [English](new-name.md)

Bis Version 1.18 hieß diese Integration *Autodarts*. Autodarts, der Hersteller der Boards, hat das Projekt gebeten, seinen Namen und sein Logo nicht mehr zu verwenden, weil es sonst wie ein Angebot von Autodarts wirkt. Deshalb heißt sie seit Version 2.0 **HomeDarts for Autodarts**, mit einem eigenen Symbol, und sie funktioniert wie bisher: lokal mit deinem Autodarts-Board, einem Granboard oder jeder Dartscheibe per Hand.

Der neue Name reicht bis in Home Assistant hinein: Die Integration hat die neue Domain `homedarts`, deshalb haben auch ihre Aktionen, ihre Karten und ihre Ordner neue Namen. Beim Update übernimmt HomeDarts die Boards, die du unter dem alten Namen eingerichtet hast, mit allem, was dazugehört.

**Auf dieser Seite:** [Was sich ändert](#was-sich-ändert) · [Umsteigen](#umsteigen) · [Was die Übernahme behält](#was-die-übernahme-behält) · [Was du selbst änderst](#was-du-selbst-änderst) · [Fragen](#fragen)

## Was sich ändert

| Vorher | Jetzt |
| --- | --- |
| Autodarts | HomeDarts for Autodarts |
| Aktionen wie `autodarts.start_game` | `homedarts.start_game` |
| Karten wie `custom:autodarts-scoreboard-card` | `custom:homedarts-scoreboard-card` |
| Dashboard-Strategie `custom:autodarts` | `custom:homedarts` |
| Board-Stil `autodarts` der Live- und der Heatmap-Karte | `flat` |
| Medienordner `autodarts/highlights`, `autodarts/exports`, `autodarts/voices` | `homedarts/highlights`, `homedarts/exports`, `homedarts/voices` |
| github.com/Dennis-Otto/ha-autodarts | github.com/Dennis-Otto/homedarts-for-autodarts |

Die Entitäts-IDs bleiben, und damit auch dein Verlauf und deine Statistiken.

## Umsteigen

1. Aktualisiere die Integration in HACS und starte Home Assistant neu. HACS installiert HomeDarts neben der alten Integration, die bis zur Übernahme weiterläuft. Meldet HACS *No manifest.json file found 'custom_components/autodarts/manifest.json'*, starte Home Assistant zuerst neu und aktualisiere dann noch einmal: Den neuen Ordner der Integration findet HACS erst bei einem Start.
2. Öffne **Einstellungen → Geräte & Dienste**. Ein Board mit Board Manager 2 erscheint als gefunden: Wähle **Hinzufügen**. Sonst wähle **Integration hinzufügen → HomeDarts for Autodarts**.
3. Wähle **Boards der Integration Autodarts übernehmen** und bestätige. HomeDarts übernimmt alle Boards auf einmal.
4. Starte Home Assistant noch einmal neu: Die Reparatur *Home Assistant neu starten, um den Wechsel zu HomeDarts abzuschließen* erledigt das für dich. Der Neustart entlädt die alte Integration, deren Dateien die Übernahme entfernt hat.

## Was die Übernahme behält

- Die Einstellungen und Optionen jedes Boards.
- Die Entitäten mit ihren IDs, Namen, Bereichen und Anpassungen und damit ihren Verlauf und ihre Langzeitstatistiken.
- Das Gerät jedes Boards.
- Die Trainingseinheiten, die Übungsspiele, die Spieler, Rekorde und Berichte.
- Die Highlights, Exporte und Sprachpakete im Medienordner.
- Die Karten und die Dashboard-Strategie in jedem Dashboard, das Home Assistant verwaltet: Ihre Typen werden umbenannt, und der Board-Stil `autodarts` wird zu `flat`.
- Die Blueprints: Home Assistant bekommt die der neuen Version an derselben Stelle, deshalb laufen deine Automationen daraus weiter.

## Was du selbst änderst

Was du selbst geschrieben hast, kann die Übernahme nicht ändern. Eine Reparatur, *Einige Automationen, Skripte oder Dashboards nutzen noch den alten Namen*, listet es auf:

- **Automationen und Skripte**, die eine Aktion der alten Integration aufrufen: Ersetze `autodarts.` durch `homedarts.`, zum Beispiel `homedarts.next_player`.
- **Dashboards in YAML**: Ersetze bei den Typen der Karten und der Strategie `custom:autodarts` durch `custom:homedarts` und `board_style: autodarts` durch `board_style: flat`.

Ignoriere die Reparatur danach.

## Fragen

**Ist HomeDarts ein Angebot von Autodarts?** Nein. HomeDarts for Autodarts ist ein inoffizielles Community-Projekt ohne Verbindung zu Autodarts. Es arbeitet mit Autodarts-Boards über die Schnittstelle, die der Board Manager in deinem Netzwerk anbietet.

**Was, wenn sich eine Mediendatei nicht verschieben lässt oder Home Assistant während der Übernahme stoppt?** HomeDarts verschiebt alles andere und lässt die Datei, wo sie ist, mit einer Warnung im Protokoll, die sie nennt; verschiebe sie selbst. Eine Übernahme, die vor ihrem Ende anhält, mit einem Fehler im Protokoll oder weil Home Assistant neu startet, geht beim nächsten Start von Home Assistant weiter; das Board funktioniert solange.

**Muss ich etwas neu einrichten?** Nein. Die Übernahme behält jedes Board mit seinen Entitäten und Statistiken. Nur Automationen, Skripte und YAML-Dashboards, die die alten Aktionen oder Karten nutzen, brauchen die neuen Namen.

**Kommt die Cloud-Anbindung?** Nein: Autodarts vergibt keine Client-IDs an Dritte, deshalb arbeitet HomeDarts lokal. Online-Matches erreichen Home Assistant weiterhin über [Tools for Autodarts](online-matches.de.md).
