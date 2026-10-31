---
description: "Wie die Integration mit dem Board Manager spricht, ihre Entitäten aktualisiert, Spiele und Training führt, Rekorde und Statistik speichert und Daten schützt."
---

# Funktionsweise

[← Dokumentation](README.de.md) · [English](how-it-works.md)

## Architektur

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/architecture-dark.png">
  <img src="images/de/architecture-light.png" alt="Architektur: Der Board Manager auf dem Board-PC sendet Echtzeitereignisse an HomeDarts in Home Assistant. Die Integration liest und steuert das Board per HTTP, speichert die Trainingssession lokal und stellt Entitäten, Board-Ereignisse, Karten und Automationen bereit." width="560">
</picture>

Ein Board ist ein Integrationseintrag mit einer Verbindung: direkt zum Board Manager in deinem Netzwerk. Sie braucht keine Anmeldung und liefert Steuerung, Echtzeitereignisse und Training. Eine Verknüpfung mit der Autodarts-Cloud gibt es nicht, weil Autodarts keine Client-IDs an Integrationen von Dritten vergibt ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch).

## Aktualisierung

| Quelle | Wie | Intervall |
| --- | --- | --- |
| Board-Zustand, Dart-Positionen, Bewegung, Kameras | WebSocket `/api/events` des Board Managers | Sofort |
| Bildraten | WebSocket `/api/events` und jedes HTTP-Lesen | Ihre Sensoren zeigen sie mit jedem Lesevorgang; einen Kameraalarm, den sie auslösen, sofort |
| Abgleich, solange Echtzeitereignisse ankommen | HTTP-Lesen | Alle 30 Sekunden; alle 10 Sekunden bei Board Manager 2, der Kameraänderungen nicht meldet |
| Ersatz ohne Echtzeitereignisse | HTTP-Lesen | Alle 2 Sekunden; alle 15 Sekunden, wenn das Board seit etwa einer halben Minute fehlt |
| Board Manager 2 | Ein gemeinsamer Aufruf von `/api/system` pro Intervall | Wie oben |
| Board Manager 2.1 | Sein Socket sendet nur den Zustand: Bewegung, Kameras und Bildraten kommen mit der Abfrage von `/api/system` | Alle 2 Sekunden, solange die Erkennung läuft, sonst alle 10 Sekunden |
| Board-PC-Details bei Board Manager 2 | HTTP-Lesen von `/api/host`; übernommen werden nur System, Prozessor und Softwareversionen | Beim Start, stündlich und nach einem Board-Manager-Update |
| Einstellungen und Version bei Board Manager 1 | HTTP-Lesen | Alle 30 Sekunden und nach jeder Aktion |

Jede Nachricht und jeder Lesevorgang aktualisiert nur die Entitäten, die zeigen, was sich geändert hat. Eine Hand am Board, die in jeder Aufnahme mehrmals kommt und geht, aktualisiert nur die Bewegungssensoren, nicht die über hundert Entitäten eines Boards mit seinen Spielen und Statistiken.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/entity-updates-dark.png">
  <img src="images/de/entity-updates-light.png" alt="Welche Entitäten eine Nachricht des Boards aktualisiert: Ein neuer Zustand, ein Dart, eine Einstellung oder ein Kameraalarm aktualisiert jede Entität des Boards. Eine Hand oder eine Entnahme aktualisiert nur die Bewegungssensoren, Kameras, die starten oder stoppen, nur Kameras aktiv. Bildraten und die Last des Board-PCs aktualisieren nur ihre Sensoren, mit dem nächsten Lesevorgang" width="560">
</picture>

## Verbindungsverhalten

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/connection-dark.png">
  <img src="images/de/connection-light.png" alt="Wie sich die Verbindung zum Board verhält: Beim Start wartet die Integration höchstens drei Sekunden auf das Board und lädt dann trotzdem; sie liest das Board alle 2 Sekunden. Mit der ersten gültigen Echtzeitnachricht kommen Darts sofort an, und ein Lesevorgang gleicht nur noch alle 30 Sekunden ab, mit Board Manager 2 alle 10 Sekunden. Bricht die Echtzeitverbindung ab, liest die Integration wieder alle 2 Sekunden und verbindet sich nach 1, 2, 4 bis 60 Sekunden neu, jede Wartezeit um bis zu ein Fünftel kürzer. Zwei verpasste Lesevorgänge in Folge behalten die letzten Werte; der dritte macht die Board-Entitäten nicht verfügbar, und jede Antwort bringt sie sofort zurück, mit schnellem Lesen und sofort einer neuen Verbindung. Ohne Antwort wird das Board nach etwa zehn verpassten Lesevorgängen alle 15 Sekunden gefragt. Seine erste Antwort bringt das schnelle Lesen und sofort eine neue Verbindung zurück" width="440">
</picture>

- **Echtzeit zuerst.** Das Lesen wird erst langsamer, wenn die erste gültige Nachricht ankommt, nicht schon, wenn die Verbindung steht. Eine Verbindung, über die nichts kommt, behält also das schnelle Lesen.
- **Wiederverbinden.** Bricht die Echtzeitverbindung ab, wechselt die Integration sofort auf schnelles Lesen. Sie verbindet sich nach 1, 2, 4 … bis 60 Sekunden neu; jede Wartezeit wird zufällig um bis zu ein Fünftel verkürzt. Eine Verbindung, die 30 Sekunden gehalten hat, beginnt wieder bei 1 Sekunde, und findet ein Lesevorgang das Board nach einem Ausfall wieder, verbindet sich die Integration sofort.
- **Kurze Aussetzer.** Zwei verpasste Lesevorgänge in Folge, also wenige Sekunden, behalten die letzten Werte; erst der dritte macht die Board-Entitäten nicht verfügbar. Solange Echtzeitereignisse ankommen, ist ein verpasster Lesevorgang gar kein Ausfall.
- **Ein Board, das länger fehlt**, etwa weil sein PC aus ist, wird nach etwa zehn verpassten Lesevorgängen alle 15 Sekunden gefragt. Mit der ersten Antwort geht es wieder schnell weiter.
- **Board beim Start aus.** Die Integration lädt trotzdem und wartet dafür höchstens drei Sekunden auf das Board. Training, Übungsspiele, persönliche Bestleistungen, ihre Entitäten und die Board-Ereignisse funktionieren ohne das Board; die Board-Entitäten folgen, sobald es antwortet, und die Geräteseite zeigt wieder die Version des Board Managers.
- **Aufnahmen über Unterbrechungen.** Solange das Board nicht erreichbar ist, bleibt die laufende Aufnahme erhalten. Zeigt das Board danach zuerst noch ihre Darts, geht die Aufnahme weiter, und neue Darts werden erkannt. Sonst wurden die Darts inzwischen gezogen: Die Aufnahme wird mit `visit_completed` abgeschlossen, und das Übungsspiel verbucht sie. Darts, die danach noch während der Unterbrechung geworfen wurden, zählen nicht, weil sie sich nicht von korrigierten Darts unterscheiden lassen. Eine Statusänderung während der Unterbrechung wird mit dem ersten Zustand danach gemeldet.
- **Ein Lesevorgang nach dem anderen.** Lesevorgänge überschneiden sich nie, eine ältere Antwort ersetzt also nie eine neuere, und ein langsames HTTP-Lesen überschreibt nie eine neuere Echtzeitnachricht.
- **Entladen.** Wird der Eintrag entladen, deaktiviert oder neu geladen, hält die Integration zuerst den Bot, ihre Timer und die Echtzeitverbindung an. Danach wartet sie auf einen noch laufenden Lesevorgang und verwirft seine Antwort; vom Board kommt also kein Reparaturhinweis, kein Board-Ereignis und kein Fehler mehr.
- **Schnell wechselnde Werte.** Die Bewegung, die Kameras, Bildraten und die Last des Board-PCs aktualisieren nur die Entitäten, die sie zeigen; Training und Übungsspiel werden dafür nie neu berechnet. Bildraten kommen mehrmals pro Sekunde, deshalb zeigen ihre Sensoren sie mit jedem Lesevorgang; einen Kameraalarm, den sie auslösen oder beenden, zeigt jede Entität sofort.
- **Fehler bleiben begrenzt.** Ein Fehler im Training oder in einer Spielregel wird einmal protokolliert und trennt nie die Verbindung zum Board.
- **Eine Entnahme, die nie endet.** Board Manager 2.0.2 bleibt manchmal bei leerem Board in einer Entnahme hängen und zählt bis zu einem Zurücksetzen keine Darts. Zehn Sekunden nach dem ersten Zustand, der eine Entnahme ohne Darts und ohne Hand am Board zeigt, setzt die Integration das Board zurück: höchstens einmal in zehn Sekunden und höchstens dreimal in Folge. Sie wartet dafür mit einem Timer, nicht mit häufigerem Lesen, und eine Änderung, eine Hand, ein fehlgeschlagener Lesevorgang oder der Schalter *Hängende Entnahme lösen* beendet das Warten ([Details](entities.de.md#eine-entnahme-die-das-board-nie-beendet)).
- **Unerwartete Antworten.** Eine Antwort in unbekanntem Format wird pro Abfrage einmal protokolliert. Antwortet eine nötige Abfrage (Zustand, Einstellungen oder `/api/system`) dreimal hintereinander so, bittet ein Reparaturhinweis um ein Update der Integration. Ein Board, das mit HTTP 401 oder 403 antwortet, bekommt einen eigenen Hinweis; der Board Manager braucht keine Anmeldung. Die Hinweise eines Boards verschwinden, wenn sein Eintrag entladen, deaktiviert oder neu geladen wird, und die nächste Einrichtung meldet die wieder, die noch zutreffen.
- **Nach einer Aktion.** Die Integration liest das Board direkt nach jeder Aktion; ein Schalter zeigt den neuen Zustand also nach etwa einer Sekunde.

## Board-Manager-Generationen

| Merkmal | Board Manager 1 (klassische App) | Board Manager 2 (Headless) |
| --- | --- | --- |
| Erkennung | Version beginnt mit `1.` | Version beginnt mit `2.` und `/api/system` existiert |
| Lesen | Einzelne Aufrufe für Zustand, Statistik, Kameras, Bewegung, Einstellungen und Version | Ein gemeinsamer Aufruf von `/api/system` |
| Extras | Schalter und Tasten für die Cloud-Verbindung | Cloud-Verbindung, CPU, Speicher, Betriebssystem, Prozessor und Erkennungssoftware des Board-PCs, Update-Hinweis, Kamera-Livestreams, mDNS-Erkennung |

Die Generation wird bei jedem Lesen geprüft. Nach einem Update des Boards lädt sich die Integration neu und ergänzt oder entfernt die generationsspezifischen Entitäten; sonst ändert sich nichts. Solange ein Board noch Board Manager 1 nutzt, empfiehlt ein Reparaturhinweis das Update. Solange die Generation noch unbekannt ist, etwa weil das Board beim ersten Start aus ist, werden keine Entitäten entfernt.

Ein Board, das Version 2 meldet, aber kein `/api/system` hat, gilt als Board Manager 1, sobald es fünf Minuten lang und mindestens dreimal hintereinander ohne diese Abfrage geantwortet hat; ein Board, das noch startet, kann sie eine Weile verpassen. Die Integration merkt sich das für diese Board-Manager-Version, damit ein Neustart nicht hin und her wechselt. Sie fragt `/api/system` bei jedem Start, einmal pro Stunde und bei einer anderen Version erneut ab und wechselt zurück zu Board Manager 2, sobald die Abfrage antwortet.

## Adresswechsel

- **Board Manager 2** meldet sich im Netzwerk (mDNS). Meldet er eine neue Adresse und antwortet das Board unter seiner eingerichteten nicht mehr mit seiner Board-ID, bietet ein Reparaturhinweis die neue Adresse an. Der Eintrag zieht erst um und die Integration lädt sich neu, wenn du bestätigst und das Board sich unter der neuen Adresse noch einmal ausgewiesen hat: Jedes Gerät im Netzwerk kann eine Board-ID melden. Genutzt werden nur die Adressen, von denen die Meldung kommt, und ein Board, das unter seiner eingerichteten Adresse noch antwortet, wird nie umgezogen.
- **Sonst** öffnest du die Integration, wählst **Neu konfigurieren** und suchst das Board oder gibst seine Adresse ein. Den Suchdienst von Autodarts fragt die Integration nie von sich aus.

## Trainingssession

Trainingssessions berechnet Home Assistant aus dem, was das Board erkennt. Sie folgen diesen Regeln:

- **Sessions bestimmen, was zählt.** Nur Darts, die während einer laufenden Session geworfen werden, zählen. Darts, die beim Start einer Session schon im Board stecken, gehören zu keiner Session; Darts, die beim Ende noch stecken, bleiben bei der beendeten Session.
- **Ereignisse hängen nicht von Sessions ab.** Dart-, Korrektur-, Entnahme- und Aufnahme-Ereignisse kommen mit und ohne laufende Session.
- **Pausen beenden Sessions.** Mit eingestellter Pause endet eine Session so viele Minuten nach ihrem letzten Dart; als Ende gilt die Zeit dieses Darts. Wurde das Ende fällig, während Home Assistant aus war, wird es beim nächsten Start nachgeholt.
- **Jeder Dart zählt einmal.** Wiederholte Nachrichten, Kamerazittern und Neuverbindungen zählen keinen Dart doppelt.
- **Korrekturen überarbeiten.** Korrigiert das Board einen Dart der aktuellen Aufnahme, folgen die Summen der Korrektur, etwa wenn aus einer 180 eine 140 wird.
- **Die Entnahme beendet die Aufnahme.** Die entfernten Darts behalten ihre Punkte. Dasselbe gilt, wenn neue Darts ohne leeres Board dazwischen erscheinen (verpasste Entnahme) und wenn die Erkennung stoppt.
- **Der dritte Dart meldet die Aufnahme früh.** Landet der dritte gemeldete Dart einer Aufnahme, meldet `visit_thrown` die Aufnahme sofort, solange die Darts noch im Board stecken. Das geschieht einmal pro Aufnahme, auch nach Korrekturen; `visit_completed` folgt, wenn die Aufnahme endet, mit den endgültigen Punkten und `thrown: true`.
- **Darts beim Start zählen nicht.** Darts, die beim Start von Home Assistant schon im Board stecken, werden nicht mitgezählt.
- **Unterbrechungen behalten die Aufnahme.** Nach einer Unterbrechung der Verbindung geht die Aufnahme weiter, wenn das Board noch ihre Darts zeigt; sonst wird sie abgeschlossen, siehe [Verbindungsverhalten](#verbindungsverhalten).
- **Zurückgezogene Erkennungen.** Nimmt das Board außerhalb einer Entnahme eine Erkennung zurück, verschwindet der Dart wieder aus den Summen.
- **Von Hand und der Bot.** Von Hand eingegebene Darts zählen wie erkannte, und die Session zählt sie in `manual_darts`; die Darts einer Aufnahme, die mit ihren Punkten eingegeben wurde, zählen für die Punkte und die Darts, aber für kein Feld, und die Session zählt sie zusätzlich in `total_darts`; eine Korrektur in Home Assistant ändert die Summen wie eine des Boards. Die Darts des Bots werden gemeldet, zählen aber für keine Session und starten auch keine. Siehe [Korrekturen und von Hand eingegebene Darts](#korrekturen-und-von-hand-eingegebene-darts).
- **Punktstufen.** 100+ zählt Aufnahmen mit 100–139 Punkten, 140+ mit 140–179, 180 genau drei Triple 20. Eine Aufnahme zählt in ihre Stufe, sobald sie abgeschlossen ist, wenn ihre Darts gezogen werden; zwei Triple 20 zählen also nie als 100+ auf dem Weg zur 180. Zusammengelegte Aufnahmen mit mehr als drei Darts (nach verpasster Entnahme) zählen in keine Stufe.
- **Statistik.** Die Summen sind Sensoren der Zustandsklasse *total*, deren `last_reset` der Start der Session ist. Die Langzeitstatistik von Home Assistant summiert sie pro Session, und eine Korrektur oder eine zurückgenommene Aufnahme kann sie senken.
- **Speicherung.** Session, Einstellungen, die letzten 20 Sessions und die letzten 10 Aufnahmen liegen im Ordner `.storage` von Home Assistant. Sie werden höchstens alle fünf Sekunden gespeichert, sofort beim Start oder Ende einer Session und beim Beenden von Home Assistant, und zusammen mit der Integration gelöscht.

Spieler und Spiele kennen die Sessions nicht. Eine laufende Session zählt jeden erkannten Dart, egal ob du X01, Cricket oder freies Training spielst.

## Übungsspiel

Das Übungsspiel folgt wie die Trainingssession den Darts der aktuellen Aufnahme, einschließlich Korrekturen. Wenn du die Darts ziehst, wird die Aufnahme verbucht. Wie jedes Spiel zählt, steht unten bei den [Regeln](#regeln).

- **Aufnahmen:** Eine Aufnahme hat drei Darts. Ein vierter Dart vor dem Ziehen zählt nicht. Darts, die das Board nicht erkennt, etwa Abpraller oder Darts auf dem Boden, zählen nicht; eine Aufnahme mit weniger Darts zählt nur die erkannten.
- **Checkout-Weg:** Die Integration probiert jede Kombination für die restlichen Darts der Aufnahme und wählt den Weg, den die Checkout-Tabellen der Profis wählen, nach diesen Grundsätzen in dieser Reihenfolge:
  1. Die wenigsten Darts, also das Bullseye bei 50 auch mit drei Darts in der Hand.
  2. Kein Double als Stellwurf, und ein Double statt des Bullseyes zum Checkout.
  3. Mit drei Darts in der Hand ein erstes Triple, dessen Single noch einen Checkout mit zwei Darts lässt: 129 beginnt mit T19, weil ein Single 20 den Rest 109 ließe.
  4. Das größte erste Triple, meist T20.
  5. Stellwürfe auf Triple 20 oder 19 oder auf ein Single zu D20, D16, D8, D18, D12, D10 oder D4. Mit zwei Darts übrig passt Triple 20 oder 19 zu jedem Double, wenn ihr Single noch einen Checkout mit einem Dart lässt: 70 mit zwei Darts ist T20 D5, mit dem Bull hinter einer Single 20.
  6. Dann jeder Stellwurf zu den guten Doubles D20, D16, D8, D18 oder D12, dann alles andere; weniger Triples, größere Triples und das Checkout-Double in der Reihenfolge D20, D16, D8, D18, D12, D10, D4, D14, D6, D2 und die ungeraden Doubles.

  So wird 144 zu T20 T20 D12, 136 zu T20 T20 D8, 130 zu T20 T20 D5, 127 zu T20 T17 D8, 73 zu T19 D8 und 64 zu T16 D8. Für 159, 162, 163, 165, 166, 168, 169 und alles über 170 gibt es mit Double-Out keinen Weg. Ohne Double-Out checkt das größte Feld: ein Single vor einem Double oder Triple.

  Mit Master-Out kommt ein Weg auf einem Double zuerst, wo einer mit ebenso wenigen Darts auskommt, nach den Grundsätzen oben; ein Triple checkt nur, wo es einen Dart spart, ohne Double zum Stellen, mit weniger und größeren Triples davor und dem größten Triple zuletzt: 60 ist T20, 117 T20 T19, 171 T20 T20 T17 und 100 weiter T20 D20. Mit dem Bull-Modus 50/50 zählt das Bull auch außerhalb des Bullseyes 50: Ein Dart darauf stellt ein Double wie ein Single, also ist 90 BULL D20 und 70 BULL D10, während nur das Bullseye checkt. Ein Test probiert jeden Rest von 1 bis 190 mit einem bis drei Darts in jedem Out-Modus und Bull-Modus: Ein Weg besteht genau dort, wo die Darts checken können, geht auf, endet auf einem Feld, das der Out-Modus nimmt, und braucht die wenigsten Darts.
- **Stellwurf:** Wo die übrigen Darts nicht checken können, schlägt das Spiel stattdessen einen [Stellwurf](#stellwürfe) vor.
- **Persönliche Wege:** Mit *Übungsspiel persönliche Checkout-Wege* gewinnen die starken Doubles des Spielers am Board, die beste Quote zuerst, gegen den üblichen Weg, sobald ein Weg mit gleich vielen Darts sie ohne Double als Stellwurf erreicht; zwischen Wegen zum selben Double entscheiden die Grundsätze oben. Stark ist ein Double mit mindestens 10 Darts darauf und einer Quote mindestens so hoch wie die des Spielers auf alle Doubles; ein nie getroffenes Double wird nie bevorzugt.
- **Übungsspiel neues Leg** startet das Leg neu; die Darts des abgebrochenen Legs verlassen die Match-Averages und die Match-Zusammenfassung.
- **Statistik:** Jedes beendete X01-Leg ergibt einen Eintrag für alle am Board: Punkte und Darts der ersten neun Darts, Darts aufs Double und den Checkout. Darts aufs Double und Checkouts zählen mit Double-Out; ein Leg, das die Rundengrenze entschieden hat, hat keinen Checkout. Überworfene Aufnahmen zählen keine Punkte, auch nicht in den ersten neun. Die Statistik-Sensoren nutzen die letzten 10 Einträge, ihr Verlauf zeigt deine Entwicklung. *Übungsspiel gespielte Legs* zählt jedes beendete Leg von X01, den Cricket-Spielen und den Partyspielen.
- **Speicher:** Spiel, Regeln, Teams und Startpunkte, Spieler mit ihren Ständen und Marks, Matchformat, die letzten 10 Legs und die [Match-Zusammenfassung](#match-zusammenfassung) mit den Zahlen, die sie zählt, werden zusammen mit der Trainingssession gespeichert, ebenso der [Fortschritt](#fortschritt-der-spieler) jedes Spielers, *Übungsspiel manuelle Eingabe* sowie Stärke und Pause des Bots.

### Stellwürfe

Können die übrigen Darts einer Aufnahme nicht mit Double-Out checken, über 170, bei 159, 162, 163, 165, 166, 168 oder 169 mit drei Darts oder mit zu wenigen übrigen Darts, sucht das Spiel einen Stellwurf: Darts, die für die nächste Aufnahme einen guten Rest stellen. Es probiert jede Kombination für die übrigen Darts und wählt nach diesen Grundsätzen, in dieser Reihenfolge:

1. **Nur ein lohnender Rest.** Über 170 mit drei Darts muss der Stellwurf ein Double stellen; sonst darf er auch ein Finish mit zwei Darts oder das Bull stellen.
2. **Die beste Art von Rest.** Zuerst ein bevorzugtes Double: mit *Übungsspiel persönliche Checkout-Wege* die stärksten Doubles des Spielers, dann 32, 40, 36 und 16. 32 halbiert sich bis D1, wenn ein Dart im Single des Doubles landet, 40 und 36 zweimal. Dann jedes andere Double, dann ein Finish mit zwei Darts oder das Bull.
3. **Keine kleinen Felder.** So wenige Darts wie möglich auf ein kleines Feld: eine andere Triple als T20 und T19 oder das äußere Bull.
4. **Der bessere Rest.** Bei Doubles die Reihenfolge oben und dann D12, D10, D4, D14, D6, D2 und die ungeraden Doubles; bei Finishes mit zwei Darts der kleinere Rest.
5. **Weniger und größere Triples.**

Stellwürfe gehen auf Singles, Triples und das äußere Bull, nie auf ein Double; die Triples kommen zuerst, das Single, das das Double stellt, zuletzt. So ist 169 T20 T20 S17 mit Rest 32, 180 T20 T20 S20 mit Rest 40, 200 T20 T20 T16 mit Rest 32, 220 dreimal Triple 20 mit Rest 40; mit einem Dart ist 100 T20 mit Rest 40, 80 T16 mit Rest 32, 41 S9 mit Rest 32 und 99 T20 mit Rest 39. Über 220 kann nichts ein Double stellen, und es erscheint kein Stellwurf. Wo selbst Darts, die alle in der Triple 20 landen, zu viel übrig ließen, über 220 mit drei Darts, über 230 mit zweien und über 170 mit einem, weiß das Spiel das ohne Suche, so wartet kein Dart und kein Zug des Bots auf eine, die nichts finden kann. Ohne Double-Out gibt es keinen Stellwurf. Der Bot zielt auf dieselben Stellwürfe.

### Korrekturen und von Hand eingegebene Darts

- **Die Aufnahme, wie Home Assistant sie kennt.** Übungsspiel und Trainingssession folgen den Darts des Boards zusammen mit den Korrekturen, den von Hand eingegebenen Darts und den Darts des Bots, in der Reihenfolge, in der sie kamen: Ein Dart, der nach dem zweiten Dart des Boards eingegeben wird, ist der dritte Dart der Aufnahme.
- **Korrekturen** gelten für Darts der aktuellen Aufnahme. Ein korrigierter Dart zählt überall in seinem neuen Feld: Restpunkte, Überwerfen und Sieg, Cricket-Marks, die Statistik und der Aufnahme-Sensor. Das Board behält seine Erkennung; korrigiert es den Dart später selbst, zählt wieder seine neue Erkennung, und eine Korrektur zurück auf die Erkennung des Boards hebt die Korrektur auf. Ein Dart, der in ein anderes Feld korrigiert wird, verliert die Position des Boards, weil das Board auch die Stelle falsch gesehen hat: Er hat keine Position, wie ein von Hand eingegebener Dart, außer die Korrektur gibt die Stelle an, an der er steckt; daraus ergibt sich dann auch das Feld. Die Darts des Bots lassen sich nicht korrigieren. Eine Korrektur zählt für die Korrekturquote der Erkennung wie eine am Board.
- **Von Hand eingegebene Darts** brauchen *Übungsspiel manuelle Eingabe* und eine Aufnahme mit weniger als drei Darts. Sie zählen wie erkannte Darts, für das Spiel, die Trainingssession, die Darts des Tages und die Bestleistungen, aber nicht für die Korrekturquote. Ohne Position messen sie beim Ausbullen nach Abstand nichts und zählen beim Golf als äußeres Single. Solange die Erkennung nicht läuft, bilden die eingegebenen Darts die Aufnahme allein; das Stoppen der Erkennung beendet eine Aufnahme wie immer.
- **Nächster Spieler** beendet die Aufnahme wie eine Entnahme. Darts, die noch im Board stecken, bleiben aus jeder Aufnahme heraus, bis sie gezogen sind, auch wenn sie in beliebiger Reihenfolge gezogen werden; neue Darts daneben zählen für den nächsten Spieler. Ohne Darts in der Aufnahme setzt der Spieler am Board in X01, den Cricket- und den Partyspielen aus, und die Aufnahme zählt keine Darts. Das Aussetzen wird wie jede Aufnahme verbucht: Beendet es die letzte Runde eines Partyspiels, zählen Leg und Match für die Profile, den Fortschritt, den Wochenbericht und den Trainingskalender. Ein neues Spiel, geänderte Einstellungen oder eine neue Trainingssession beenden ebenfalls eine Aufnahme mit Darts, die von Hand oder vom Bot kamen.
- **Zurücknehmen** nimmt die letzte Aufnahme eines Spielers zurück, zusammen mit den Aufnahmen des Bots danach. Das Spiel kehrt zum Stand zurück, bevor diese Aufnahme verbucht wurde, mit Legs, Sätzen, dem Leg-Verlauf, den Spielerprofilen und dem Match-Verlauf; die Darts der Aufnahme verlassen die Summen der Session, die Treffer, die höchste Aufnahme und die letzten Aufnahmen und werden wieder die aktuelle Aufnahme. Der [Fortschritt](#fortschritt-der-spieler) der Spieler am Board mit seinen Erfolgen, der [Wochenbericht](#wochenbericht) und der [Trainingskalender](#trainingskalender-und-exporte) kehren ebenfalls zurück, damit die Aufnahme einmal zählt, wenn sie erneut verbucht wird; ein Wochenbericht, der dazwischen gemeldet wurde, bleibt, wie er war. Auch die Bestleistungen kehren zu den Werten vor der Aufnahme zurück, während ihre Darts Darts des Tages, der Serie und des Tagesziels bleiben. Was die Aufnahme gemeldet hat, bleibt gemeldet. Eine Aufnahme lässt sich zurücknehmen, solange kein Dart im Board steckt und sich weder das Spiel, seine Einstellungen noch die Trainingssession seitdem geändert haben; eine Aufnahme, die ein Turniermatch entschieden hat, lässt sich nicht zurücknehmen, und ein Neustart vergisst sie.
- **Speicher:** Korrekturen, von Hand eingegebene Darts und die zurücknehmbare Aufnahme gelten, bis die Aufnahme endet, und werden nicht gespeichert; nach einem Neustart beginnt die laufende Aufnahme wieder mit den Darts des Boards.

### Bot

- **Platz:** Ist *Übungsspiel Bot-Stärke* über 0, nimmt der Bot in X01 und den Cricket-Spielen den Platz nach den Spielern; bis zu drei Spieler spielen mit ihm, auch als vierter Spieler zweier Teams. Partyspiele, Trainingsspiele und Turniere laufen ohne ihn; ein Turnier setzt die Stärke auf 0, und das Übungsspiel bekommt sie mit seinen übrigen Einstellungen zurück, wenn das Turnier endet.
- **Zug:** Ist er dran, wirft der Bot seinen ersten Dart *Übungsspiel Bot-Pause* Sekunden, nachdem die Darts davor gezogen wurden, dann Dart für Dart mit derselben Pause, und beendet seine Aufnahme nach einer letzten Pause: nach drei Darts, einem Überwerfen oder einem Sieg, beim Ausbullen nach einem Dart. Wirft ein Spieler, während der Bot am Board ist, endet sein Zug: Der Bot wirft den Rest seiner Aufnahme sofort, und die neuen Darts zählen für den Spieler. *Nächster Spieler* beendet die Aufnahme des Bots vorzeitig. Nach einem Neustart macht der Bot weiter.
- **Ziel bei X01:** der Checkout-Weg für die übrigen Darts, wie die Karten ihn zeigen, wo es einen gibt; sonst der [Stellwurf](#stellwürfe); sonst das Triple 20. Ohne Double-Out zielt er unter 60 auf das größte Feld, das nicht überwirft. Vor dem öffnenden Double bei Double-In zielt er auf ein Double, das gewinnt oder seinen übrigen Darts ein Finish lässt, sonst auf das Double 20 oder das größte Double, das nicht überwirft.
- **Ziel bei Cricket:** Zuerst schließt er eine Zahl, die ein anderer Spieler geschlossen hat und er nicht, weil jener darauf punktet, außer er liegt zurück und kann selbst punkten. Liegt er zurück, punktet er auf der ersten Zahl, die er geschlossen hat und ein anderer Spieler offen hat. Sonst schließt er die nächste offene Zahl, 20 abwärts bis 15 (bei Tactics bis 10) und zuletzt das Bull. Bei Cut-Throat heißt zurückliegen, dass ein anderer Spieler weniger Punkte hat, und er punktet auf einer Zahl, die dieser Spieler offen hat. Bei Wild Mouse schließt er nach den Zahlen Doubles und Triples und zuletzt das Bull; er zielt dafür auf das Double oder Triple der höchsten Zahl, die er geschlossen hat oder die kein Cricket-Spiel zählt, damit der Dart dafür zählt, und für 3 in a Bed auf die große Single 20 und danach auf das Feld seines ersten Darts. Bei Hidden Cricket spielt er nur die aufgedeckten Zahlen, die höchste zuerst; hat er alle außer dem Bull geschlossen, während noch Zahlen verdeckt sind, sucht er: das Triple einer noch verdeckten Zahl, mit jedem Dart des Legs eine andere, sodass er jede Zahl einmal versucht. Beim Ausbullen wirft er aufs Bullseye.
- **Wo seine Darts landen:** Der Bot zielt auf die Mitte des Felds, den Triple- oder Double-Ring, den äußeren Single-Bereich für ein Single, 12 mm neben die Mitte für das äußere Bull und die Mitte für das Bullseye, und jeder Dart landet mit einer normalverteilten (Gaußschen) Streuung von σ Millimetern in beide Richtungen. Das Feld ergibt sich aus dem Landepunkt mit der Geometrie der Karten: Bullseye 7 mm, äußeres Bull 17 mm, Triple-Ring 97–107 mm, Double-Ring 160–170 mm; über 170 mm ist ein Fehlwurf.
- **Kalibrierung:** σ einer Stärke wurde gemessen, indem der Bot allein Legs 501 mit Double-Out spielte, 600 bis 1.500 Legs pro Streuung in Schritten von 0,2 bis 5 mm, und wird zwischen diesen Stärken interpoliert: 20 → 48,1 mm, 40 → 22,9 mm, 60 → 14,9 mm, 80 → 10,7 mm, 100 → 7,9 mm, 120 → 5,6 mm. Mit neuen Zufallszahlen über 1.000 Legs spielte jede Stärke von 20 bis 120 in Fünferschritten innerhalb von 1,5 % ihres Averages; die Tests spielen einige hundert Legs mit festen Zufallszahlen nach und erlauben 5 %. Der Average enthält die Darts aufs Double, wie der eines Spielers. Für die Cricket-Spiele wurde eine eigene Streuung genauso gemessen, über 6.000 Legs pro Streuung, sodass eine Stärke die Marks pro Runde eines Spielers mit diesem Average spielt, ein Vierundzwanzigstel davon: 2,5 bei Stärke 60, 3,3 bei 80, 4,2 bei 100 und 5 bei 120.
- **Was zählt:** Die Darts des Bots werden wie erkannte Darts gemeldet, mit `bot: true`, und zählen für keine Trainingssession, Statistik, Bestleistung, kein Spielerprofil, keinen Erfolg, keine Doppelanalyse und keinen Wochenbericht; eine Trainingssession starten sie auch nicht. Sein Platz hat keinen Namen, und der Trainingskalender nennt ihn *Bot*. Das Matchergebnis der Spieler gegen den Bot zählt in ihren Profilen und im Match-Verlauf, wo der Eintrag des Bots `bot: true` trägt; ein Leg, das der Bot auscheckt, zählt keinen Checkout für die Statistik des Übungsspiels.

## Regeln

Die Regeln jedes Spiels, von X01 und dem Ausbullen bis zu den Party- und Trainingsspielen, stehen in der [Anleitung zu Spielen und Regeln](games.de.md). Die Grundsätze der Checkout-Wege oben und die Bestleistungen unten zeigen, wie die Integration sie anwendet.

## Match-Zusammenfassung

Endet ein Match mehrerer Spieler, fasst das Übungsspiel es für jeden Spieler zusammen. `match_won` meldet die Zahlen im Moment des entscheidenden Darts so, wie sie nach dem Buchen der Aufnahme sind; das Attribut `summary` behält sie, bis das nächste Match endet.

- **Legs, Sätze und Darts:** die im ganzen Match gewonnenen Legs, die Sätze und jeder im Match geworfene Dart.
- **3-Dart-Average:** Punkte pro drei Darts des ganzen Matches; Darts einer überworfenen Aufnahme zählen, ihre Punkte nicht.
- **First-9-Average:** Punkte pro drei Darts der ersten neun Darts jedes Legs; eine überworfene Aufnahme zählt auch hier nichts.
- **Checkout-Quote:** mit einem Double ausgecheckte Legs pro Dart aufs Double, mit beiden Zahlen. Ein Dart zählt als Wurf aufs Double wie bei der [Statistik](#bestleistungen-und-statistik). Ohne Double-Out gibt es keine Checkout-Quote.
- **Höchster Checkout:** der höchste Rest, mit dem ein Spieler ein Leg beendet hat, auch in einem Leg ohne Double-Out.
- **100+, 140+ und 180:** Aufnahmen mit 100 bis 139, 140 bis 179 und 180 Punkten, die gezählt haben; Überwerfen zählt nichts.
- **Bestes Leg:** die wenigsten Darts eines Legs, das der Spieler gewonnen hat.
- **Cricket:** Marks pro Runde und die Marks, die gezählt haben, wie bei den [Cricket-Regeln](games.de.md#cricket), und das beste Leg.
- **Partyspiele:** Legs, Sätze und Darts.
- **Teams:** Beide Partner gewinnen die Legs, und ihr bestes Leg zählt die Darts beider; ein Checkout zählt für den Spieler, der ihn geworfen hat.

## Bestleistungen und Statistik

- **Höchste Aufnahme:** Der Sensor *Training höchste Aufnahme* und die Bestleistung `highest_visit` nehmen die Punkte der Darts im Board in einer Aufnahme mit bis zu drei Darts, egal in welchem Spiel: Eine überworfene Aufnahme oder eine Cricket-Aufnahme zählt mit ihren Board-Punkten, wie bei den Stufen 100+, 140+ und 180. Die `highest_visit` eines [Spielerprofils](entities.de.md#spielerprofile) ist dagegen die höchste X01-Aufnahme dieses Spielers: Überwerfen zählt nichts, und mit Double-In auch keine Darts vor dem öffnenden Double.
- **Höchster Checkout und wenigste Darts:** Die Bestleistungen `highest_checkout` und `fewest_darts_*` und dieselben Werte der Spielerprofile kommen nur aus gewonnenen X01-Legs mit Double-Out, mit oder ohne Double-In. Ein Leg ohne Double-Out ist leichter zu beenden und setzt keine Bestleistung; Double-In macht ein Leg nur schwerer.
- **Startpunkte und Teams:** Die wenigsten Darts zählen für die Punkte, mit denen ein Leg wirklich begonnen hat: Ein Leg ab 301 Startpunkten zählt für `fewest_darts_301`, ein Leg ab 401 für keine Bestleistung, weil 401 kein X01-Spiel ist. Ein Team-Leg setzt keine Bestleistung für die wenigsten Darts und für Marks pro Runde; sein Checkout und höchster Checkout zählen für den Partner, der ihn geworfen hat.
- **Verbuchte Legs:** Die Bestleistungen eines Legs sowie die Legs und Matches des Wochenberichts zählen, wenn das Übungsspiel das Leg verbucht, also wenn die Darts gezogen werden. `leg_won` und `match_won` werden schon mit dem Siegdart gemeldet; eine Korrektur, die den Sieg zurücknimmt, bevor die Darts gezogen werden, hinterlässt keine Bestleistung.
- **Cricket-Spiele:** Die Marks pro Runde der Profile und `best_cricket_mpr` kommen aus Cricket; Cut-Throat, Tactics, Wild Mouse, Random und Hidden Cricket zählen ihre Legs und Matches.
- **Trainingsspiele:** `checkout_121` hält den höchsten Rest, der im 121-Checkout gecheckt wurde; `catch_40`, `jdc_challenge` und `singles` halten die höchste Punktzahl eines beendeten Spiels.
- **Darts aufs Double:** Mit Double-Out zählt ein Dart als Wurf aufs Double, wenn ein Double den Rest checken könnte: 2 bis 40 bei geraden Zahlen oder 50. Bei 50 zählt also jeder Dart als Versuch aufs Bullseye, auch wenn ein Spieler stattdessen mit einer Single 10 stellt.

## Wochenbericht

Der Wochenbericht zählt, was das Board erkennt, wie bei den Darts des Tages, und folgt diesen Regeln:

- **Jeder Dart zählt.** Darts zählen mit oder ohne Session, im Spiel oder ohne. Der 3-Dart-Average umfasst jede abgeschlossene Aufnahme der Woche, auch zusammengelegte Aufnahmen nach einer verpassten Entnahme; höchste Aufnahme und 180er zählen Aufnahmen mit bis zu drei Darts.
- **Trainingszeit** ist die Zeit von einem Dart zum nächsten. Eine Pause von mehr als fünf Minuten zwischen zwei Darts zählt nicht, eine Pause zwischen zwei Sessions ist also kein Training.
- **Sessions** zählen, wenn sie enden: Eine Session über das Wochenende hinaus zählt für die nächste Woche.
- **Checkout-Quote** folgt den X01-Übungslegs, die in der Woche verbucht wurden: ausgecheckte Legs pro Dart aufs Double, wie bei *Übungsspiel Checkout-Quote*.
- **Legs und Matches** zählen, wie das Übungsspiel sie verbucht, wenn die Darts der entscheidenden Aufnahme gezogen werden; auch die Legs des Bots zählen.
- **Gelöschte Spieler** verschwinden aus den Bestleistungen der laufenden und der letzten Woche, wie aus den persönlichen Bestleistungen.
- **Die Woche** reicht vom Berichtstag und der Uhrzeit bis zum selben Tag und derselben Uhrzeit eine Woche später, in der Zeitzone von Home Assistant. Eine Woche mit Zeitumstellung ist eine Stunde länger oder kürzer; eine Uhrzeit, die die Uhr überspringt, zählt in der Zeit vor der Umstellung.
- **Ein neuer Berichtstag oder eine neue Uhrzeit** beendet die laufende Woche bei ihrem nächsten Eintreten; diese Woche kann also kürzer oder länger sein.
- **Verpasste Berichte.** Ein Bericht, der fällig wurde, während Home Assistant aus war, folgt beim nächsten Start; Wochen dazwischen hatten keine Darts und entfallen.
- **Speicherung.** Die laufende Woche und der letzte Bericht liegen in einem eigenen Speicher im Ordner `.storage` von Home Assistant. Sie werden höchstens alle zehn Sekunden gespeichert, sofort am Ende einer Woche und beim Beenden von Home Assistant, und zusammen mit der Integration gelöscht.

## Trainingskalender und Exporte

- **Journal.** Der Trainingskalender behält jede beendete Session und jedes Match mehrerer Spieler 365 Tage lang, höchstens je 3.000, in einem eigenen Speicher in `.storage`. Er wird gespeichert, wenn eine Session oder ein Match endet, und mit der Integration gelöscht. Beim ersten Start übernimmt er die Sessions und Matches, die die Integration schon gespeichert hat. Ein Match hat bis zu acht Spieler, wie Partyspiele; bei jedem Start übernimmt das Journal außerdem die letzten Matches der Spielerprofile, die ihm fehlen, etwa die Partymatches mit mehr als vier Spielern, die Versionen bis 1.12.2 ausgelassen haben.
- **Erster Dart.** Ein Match beginnt mit seinem ersten Dart, das Ausbullen eingeschlossen; das Übungsspiel merkt sich diesen Moment mit dem Match. Ein neues Match, auch desselben Spiels, beginnt von vorn, ein abgebrochenes Match verlängert also nie das nächste.
- **Titel** folgen der Sprache von Home Assistant: Deutsch, Niederländisch, Französisch und Spanisch haben eigene Wörter und das Dezimalkomma, etwa *Training · 312 Darts · Ø 54,2*; andere Sprachen lesen sich wie Englisch. Der Bot heißt *Bot*, und ein Team-Match nennt beide Teams, etwa *501 · Alex & Kim 1:0 Sam & Lea*. Der Kalender kennt jedes Cricket- und Partyspiel mit seinem Namen.
- **Exporte** schreibt nur die Aktion `homedarts.export`, die Administratoren und Automationen ausführen, höchstens 20 pro Stunde. Standardmäßig landen sie in `homedarts/exports` im Medienordner; ein eigener Ordner muss einer sein, in den Home Assistant schreiben darf: `www`, ein Medienordner oder ein Ordner aus `allowlist_external_dirs`. Der Ordner wird vor dem Schreiben aufgelöst, sodass weder `..` noch ein symbolischer Link woandershin führt; versteckte Ordner wie `.storage` und Namen mit Steuerzeichen werden abgelehnt. Jeder Export bekommt einen neuen Namen mit einem zufälligen Teil und ersetzt nie eine Datei. Eine CSV der Matches hat die Spalten von acht Spielern, `player_1_name` bis `player_8_points`; neue Spalten kommen immer nur hinter die anderen. In CSV bekommt ein Text, der wie eine Tabellenformel beginnt (`=`, `+`, `-`, `@`), einen Apostroph vorangestellt, damit ein Spielername nicht als Formel läuft.
- **Downloads.** Administratoren können die seit dem Start von Home Assistant geschriebenen Exporte unter `/api/homedarts/export/<Name>` herunterladen; die Spielerkarte nutzt diese Adresse mit einem signierten Link, der nach einer Minute abläuft. Exporte in `www` liefert Home Assistant außerdem unter `/local/` aus, ohne Anmeldung.

## Highlight-Galerie

Die Medienquelle *HomeDarts* zeigt die Fotos, die der [Highlight-Foto-Blueprint](automations.de.md#highlight-galerie) mit [`homedarts.save_highlight`](entities.de.md#highlight-foto-speichern-homedartssave_highlight) speichert, und die [Clips](automations.de.md#highlight-clips), die er mit `camera.record` aufnimmt:

- **Ordner:** `homedarts/highlights` im Medienordner von Home Assistant. Das ist der Medienordner `local`: `/media` unter Home Assistant OS und im Container, sonst der Ordner `media` im Konfigurationsordner. Hast du `media_dirs` ohne `local` gesetzt, der erste davon.
- **Namen:** `JJJJ-MM-TT_HH-MM-SS_<Spieler>_<Punkte>.jpg`; Uhrzeit und Spieler sind optional, ein Checkout heißt `checkout-121`, und ein zweites Foto derselben Sekunde mit demselben Namen endet mit einem Leerzeichen und `(2)`. Ein Clip hat den Namen seines Fotos mit `.mp4`. Andere Bilder (`.jpg`, `.jpeg`, `.png`, `.webp`) und Clips (`.mp4`) erscheinen mit ihrem Dateinamen und der Zeit, zu der sie gespeichert wurden.
- **Reihenfolge:** die Monate, die neuesten zuerst, jeder mit seinem neuesten Foto als Titelbild; die Fotos und Clips eines Monats, die neuesten zuerst, ein Clip vor seinem Foto.
- **Clips:** Die Galerie zeigt einen Clip mit dem Vorschaubild des Fotos seines Namens, oder ohne eines, und der Browser spielt ihn als MP4 ab.
- **Titel:** in der Sprache des Home-Assistant-Servers, etwa *September 2026* und *180 · Alex · 26.09.* oder *Clip · 180 · Alex · 26.09.* auf Deutsch, *Sep 26* auf Englisch, *26-09* auf Niederländisch und *26/09* auf Französisch und Spanisch.
- **Sicherheit:** Nur einfache Dateinamen dieses Ordners öffnen sich, und nur Bilder und Clips; versteckte Dateien, Unterordner und Verknüpfungen aus dem Ordner hinaus werden ignoriert. Die Fotos liefert die Medienansicht von Home Assistant selbst aus, an angemeldete Benutzer oder mit einer signierten Adresse.

## Fortschritt der Spieler

Jeder benannte Spieler eines Übungs- oder Trainingsspiels hat neben dem [Spielerprofil](entities.de.md#spielerprofile) einen eigenen Fortschritt. Er zählt die Darts jeder Aufnahme, die das Spiel für den Spieler am Board bucht, wenn die Darts gezogen werden; Trainingsspiele zählen für Spieler 1. Ein Spieler ohne Namen zählt für niemanden.

- **Wochen.** Summen jeder Woche ab Montag für die letzten 12 Wochen: Darts, X01-Darts und -Punkte, die ersten neun Darts jedes Legs und ihre Punkte, Darts aufs Double und Checkouts, Darts auf Doubles und Treffer in allen Spielen, Cricket-Darts und -Marks, gespielte und gewonnene Legs und 180er, dazu der höchste Checkout, die wenigsten Darts eines 501-Legs und die beste Cricket-MPR der Woche. Wie bei den Bestleistungen zählen die wenigsten Darts nur für ein Leg ab 501, und weder sie noch die beste MPR für ein Team-Leg. Legs und die Zahlen eines Legs zählen in der Woche, in der das Leg endet. Averages und Quoten entstehen aus den Summen, mehrere Wochen addieren sich also genau. Ältere Wochen fallen weg.
- **Treffer pro Feld** jedes Darts des Spielers, wie das Trefferbild der Session.
- **Tagesserie:** Tage in Folge mit mindestens einem Dart in einem Übungs- oder Trainingsspiel. Sie bleibt, bis ein ganzer Tag ohne Darts vergeht.
- **Zähler für die Erfolge:** geworfene Darts, X01-Aufnahmen mit 100 oder mehr, 140 oder mehr und 180 Punkten, Hattricks, Cricket-Aufnahmen mit neun Marks, Shanghai-Siege, das beste Finish im Checkout-Training, die wenigsten Darts bei Around the Clock und das beste abgeschlossene Bob's 27. Alles andere kommt aus dem Spielerprofil.

Eine Aufnahme zählt für die Erfolge so, wie das Spiel sie zählt: Überwerfen bringt nichts, ebenso Darts vor dem öffnenden Double bei Double-In. Die Erfolge werden nach jeder gebuchten Aufnahme geprüft; die [Übersicht der Erfolge](entities.de.md#erfolge) nennt, woran jeder gemessen wird.

### Dart-Positionen

Der Board Manager meldet, wo jeder Dart gelandet ist, relativ zum äußeren Rand des Doppelrings. Home Assistant behält die Positionen der letzten 1000 Darts jedes benannten Spielers und die Darts der laufenden Trainingssession, höchstens 5000; eine neue Session beginnt leer, und Darts ohne Position, etwa Abpraller, fehlen. Ebenso Darts, die in ein anderes Feld korrigiert wurden, außer die Korrektur gibt ihre Stelle an; von Hand eingegebene Darts werden dort gespeichert, wo die Eingabe sie hinlegt. Jede Position wird mit dem Feld gespeichert, auf das der Dart gezielt war, wo das Spiel es kennt:

- **X01:** das Double, wenn ein Dart den Rest checken kann, also 2 bis 40 bei geraden Zahlen oder das Bullseye bei 50. Sonst das erste Feld des Checkout-Wegs, wenn es mit den verbleibenden Darts einen gibt, oder die Triple 20, wenn kein Checkout möglich ist, wie bei einer Punkteaufnahme. Darts auf ein Single oder das Single-Bull, Darts bis zum öffnenden Double bei Double-In und Darts nach dem Überwerfen oder dem Finish haben kein Ziel.
- **Doppeltraining und Bob's 27:** das Double der Runde. **Checkout-Training:** der Weg wie bei X01. **Ausbullen:** das Bullseye.
- **Around the Clock, Cricket und die Partyspiele:** kein Ziel, weil dort jedes Feld einer Zahl zählt.

Positionen werden auf ein Zehntel Millimeter mit dem Training gespeichert. Sie sagen nur, wo Darts landen, und verlassen Home Assistant nie; die Diagnosedaten zählen sie nur. Die Karten lesen sie bei Bedarf über den WebSocket-Befehl `homedarts/positions` (`device_id`, optional `player` und `aim`), weil Tausende Positionen zu viele für Attribute von Entitäten sind. Eine Aufnahme wird gespeichert, wenn sie gebucht wird, also beim Ziehen der Darts; bis dahin zeichnet die Trainingskarte die Darts der aktuellen Aufnahme aus dem Aufnahme-Sensor.

### Streuung

Für jedes Zielfeld mit mindestens 10 gespeicherten Darts beschreibt die Streuung, wo diese Darts um die Mitte des Felds gelandet sind:

1. Jede Position wird zur Abweichung in Millimetern von der Mitte des Felds, x nach rechts und y nach oben, so wie der Spieler auf die Scheibe blickt. Die Mitte eines Triples liegt 102 mm von der Scheibenmitte entfernt, die Mitte eines Doubles 165 mm, das Bullseye in der Mitte.
2. Die **Abweichung** ist der Mittelwert dieser Abweichungen: wo die Darts im Schnitt landen. *6 mm links der Mitte, 3 mm zu hoch* beschreibt diesen Mittelpunkt.
3. Die **Streuung** ist der Radius um den Mittelpunkt, in dem die Hälfte der Darts liegt, der kleinste Abstand mit mindestens 50 % der Darts innerhalb; der zweite Radius umfasst 80 %. *Streuung 38 mm* heißt, dass jeder zweite Dart innerhalb von 38 mm um den Mittelpunkt landet.
4. Der **Trend** vergleicht die Streuung der neueren Hälfte der gespeicherten Darts mit der älteren, sobald es 20 sind: *4 mm enger* heißt, dass die neueren Darts 4 mm enger beieinander liegen.

Die Abweichung zeigt die Treffsicherheit eines Spielers, die Streuung seine Gleichmäßigkeit. Beide beruhen auf den Positionen, die das Board meldet, und die Streuung eines Spielers umfasst seine letzten 1000 Darts. Das Profil nennt die sechs Felder mit den meisten Darts, die Karten die ersten drei.

### Zielkarte

Die Zielkarte zeigt, wo ein Spieler mit seiner eigenen Streuung die meisten Punkte pro Dart macht. Sie folgt Tibshirani, Price und Taylor, *A statistician plays darts* (Journal of the Royal Statistical Society, Series A 174, 2011): Ein Dart landet am Zielpunkt plus einem Fehler aus einer zweidimensionalen Normalverteilung, die gleich ist, wohin auf der Scheibe der Spieler auch zielt, und die Punkte pro Dart eines Zielpunkts sind die Punkte der Scheibe um ihn herum, gewichtet mit dieser Verteilung.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/aim-map-dark.png">
  <img src="images/de/aim-map-light.png" alt="Wie die Zielkarte entsteht: Die gespeicherten Darts eines Spielers, die auf ein Triple gezielt waren, werden zu Abweichungen von der Mitte ihres Triples, in den Richtungen der Scheibe. Ab 30 davon ist das Fehlermodell ihre mittlere Abweichung und Streuung, ohne die Darts jenseits von 99 % einer Normalverteilung. Home Assistant sucht den Zielpunkt mit den meisten Punkten pro Dart, für das Spielerprofil und die Karten; im Browser berechnet die Trainingskarte die Punkte pro Dart jedes Zielpunkts und zeichnet die Karte mit dem besten Zielpunkt" width="460">
</picture>

1. **Fehlermodell.** Jeder gespeicherte Dart, der auf ein Triple gezielt war, wird zu seiner Abweichung in Millimetern von der Mitte dieses Triples, x nach rechts und y nach oben, wie bei der [Streuung](#streuung). Ein Fehlwurf nach links bleibt einer nach links, auch an der Triple 19 oder der Triple 6, also zählen die Darts aller Triples zusammen. Das Modell ist die mittlere Abweichung und die Streuung um sie herum: eine Standardabweichung zur Seite, eine in der Höhe und ihre Korrelation. Es braucht 30 solche Darts unter den letzten 1000 gespeicherten Darts des Spielers oder unter den Darts der Session.
2. **Darts mit anderem Ziel.** Das Spiel kennt nur das Feld, das es annimmt: Wer in einer Aufnahme zum Punkten auf die Triple 19 geht, hat für das Spiel auf die Triple 20 geworfen. Solche Darts liegen weit von den anderen entfernt, und das Modell lässt sie weg. Es beginnt beim Medianpunkt und dem mittleren Abstand davon und behält viermal die Darts innerhalb des Abstands, der 99 % einer Normalverteilung umfasst (ein quadrierter Mahalanobis-Abstand von 9,2), misst sie neu und gleicht das abgeschnittene 1 % aus. Das Modell wird auf einen halben Millimeter genau gehalten und seine Korrelation auf 0,05, feiner, als es einige hundert Darts zeigen können.
3. **Punkte pro Dart.** An einem Zielpunkt sind die Punkte pro Dart der mittlere Wert von 1000 festen Würfen des Fehlers. Die Würfe verteilen sich gleichmäßig über die Normalverteilung, ein Fibonacci-Gitter, abgebildet mit der Box-Muller-Transformation, sodass dasselbe Modell immer dieselben Zahlen ergibt. Jeder Landepunkt wird auf den Millimeter gerundet und mit der Geometrie des Board Managers gewertet, wie die Karten die Scheibe zeichnen: das Bull bis 7 mm, das äußere Bull bis 17 mm, das Triple von 97 bis 107 mm und das Double von 160 bis 170 mm.
4. **Bester Zielpunkt.** Home Assistant sucht den Punkt eines 2-mm-Rasters mit den meisten Punkten pro Dart: 144 Würfe ordnen die Punkte eines 10-mm-Rasters, und das 2-mm-Raster bis 4 mm um seine besten vier Punkte und um die beste Mitte eines Triples oder des Bullseyes wird mit allen 1000 Würfen geprüft. Der beste Zielpunkt schlägt immer jedes Triple und das Bullseye; bei Gleichstand gewinnt der Punkt näher an der Mitte. Nach jeder Aufnahme rechnet Home Assistant das Modell des Spielers neu, in etwa 10 bis 25 Millisekunden für 1000 bis 5000 Darts auf einem Desktop-PC und einem Mehrfachen davon auf einem Raspberry Pi, und sucht seinen besten Zielpunkt nur, wenn sich das Modell geändert hat, in etwa 20 bis 40 Millisekunden. Beides läuft in einem Executor-Thread neben der Ereignisschleife, so dass die Scheibe, die Sensoren und die Automationen nie darauf warten; bis es fertig ist, behält das Profil den vorigen besten Zielpunkt. Das Modell der Session wird nur gerechnet, wenn die Zielkarte danach fragt. Wo mehrere Stellen fast gleich viel bringen, etwa bei weiter Streuung, ist der beste Zielpunkt eine davon.
5. **Die Karte.** Die Trainingskarte berechnet die Punkte pro Dart jedes Punkts des 2-mm-Rasters, etwa 22.700 Punkte mit je 1000 Würfen, in einem Web Worker des Browsers, damit die Seite flüssig bleibt; ihre Zahlen sind die von Home Assistant bis auf die letzte Stelle. Wo der Browser der Karte keinen Worker erlaubt, etwa bei einer strengen Content Security Policy, rechnet die Karte selbst. Die Farben reichen von 60 % der meisten Punkte pro Dart bis zu den meisten.

Das Spielerprofil nennt das Feld des besten Zielpunkts als `best_aim`, etwa `T19` oder `S16`, und seine Punkte pro Dart, auf ein Zehntel, als `expected_ppd`; ohne Modell sind beide leer. Der WebSocket-Befehl `homedarts/positions` ergänzt das Modell als `aim`, wenn er mit `aim: true` gefragt wird: `darts` auf ein Triple, die nötigen 30 als `needed`, `offset_x`, `offset_y`, `sd_x`, `sd_y` und `correlation` sowie den besten Zielpunkt als `best` mit `bed`, `x` und `y` in Millimetern, `expected` Punkten pro Dart und den Punkten pro Dart der Triple 20, der Triple 19 und des Bulls als `compared`.

## Kamerazustand

Eine Kamera gilt als gestört, wenn sie bei laufender Erkennung **15 Sekunden** lang keine Bilder liefert. Gestoppte Erkennung, Kalibrierung und Kamera-Standby sind keine Störung. Der gemeinsame Sensor *Kamerastörung* ist an, sobald eine Kamera gestört ist. Mit Echtzeitereignissen erscheint der Alarm, sobald die Bildraten ihn zeigen.

Die Kamera-Entitäten geben den Livestream von Board Manager 2 an höchstens zwei Zuschauer pro Kamera weiter; weitere Zuschauer bekommen Standbilder. Das schont den Board-PC, auf dem auch die Erkennung läuft.

## Datenschutz

- **Lokaler Betrieb:** Die Integration spricht nur mit dem Board Manager in deinem Netzwerk; ins Internet geht nichts.
- **Boards im Netzwerk suchen:** Fragt einmalig bei Benutzung `discover.autodarts.com`, den öffentlichen Suchdienst von Autodarts. Er sieht deine öffentliche IP-Adresse und liefert die von dort registrierten Boards.
- **Die optionale Online-Brücke** empfängt nur: Die Browser-Erweiterung Tools for Autodarts ruft Home Assistant mit den Momenten eines Online-Matches auf, standardmäßig nur aus deinem Heimnetz. Sie sendet nirgendwohin. [Online-Matches](online-matches.de.md).
- **Board-Geheimnisse** wie der API-Schlüssel des Boards, TLS-Schlüssel, Kamerapfade und ähnliche Konfiguration werden direkt beim Lesen verworfen. Sie werden nie gespeichert, protokolliert oder angezeigt.
- **Diagnosedaten** schwärzen Board-ID, Adresse und Spielernamen. Der Verbindungsverlauf darin enthält Zähler, Fehlerarten und Dauern, aber keine Adressen oder Fehlermeldungen.
- **Exporte** enthalten Spielernamen. Die Aktion schreibt sie nur auf Anforderung; Dateien in `www` liefert Home Assistant unter `/local/` ohne Anmeldung aus, siehe [Exporte](#trainingskalender-und-exporte).
- **Highlight-Fotos** bleiben in deinem Medienordner; die Galerie liest nichts anderes.
- **Personen:** Ein mit einer Person verknüpfter Spieler behält nur die Entitäts-ID der Person; Bild und Anwesenheit liest die Karte aus Home Assistant.
- **Der Caller der Anzeigetafel** spricht mit der Stimme des Browsers auf dem Bildschirm am Board. Welche Stimme das ist, hängt von Browser und Betriebssystem ab: Die Stimmen des Betriebssystems arbeiten offline, manche Browser bieten Online-Stimmen an, die den Text der Ansagen an ihren Anbieter schicken. Wähle eine Offline-Stimme in den Einstellungen des Geräts, wenn dir das wichtig ist.

### Gespeicherte Daten

Alles, was die Integration speichert, liegt im Ordner `.storage` von Home Assistant, nie in der Cloud, und wird mit dem Board gelöscht, nach einem [Backup](statistics.de.md#backups). Ein Speicher, der sich nicht lesen lässt, stoppt die Einrichtung des Boards, statt es leer zu starten, damit nichts ihn überschreibt: Nach einem Lesefehler versucht Home Assistant es erneut; ein Speicher einer neueren Version der Integration oder einer, der sich nicht wiederherstellen lässt, hält das Board an, bis du diese Version wieder installierst oder ein Backup wiederherstellst. Teile, die eine neuere Version gespeichert hat, bleiben, wenn eine ältere speichert.

| Speicher | Inhalt |
| --- | --- |
| `homedarts.<entry>.training` | Die Trainingssession mit ihren Einstellungen, die letzten 20 Sessions und die letzten 10 Aufnahmen; das Übungsspiel mit Regeln, Teams, Startpunkten, Spielernamen und den letzten 10 Legs; die Bestleistungen, die Trainingsserie und die Darts des Tages; die Spielerprofile mit Statistik, Bestleistungen, Doubles und verknüpften Personen, die letzten 20 Matches und die direkten Vergleiche; der Fortschritt jedes Spielers mit Wochensummen, Erfolgen und den Positionen seiner letzten 1000 Darts; die Doppelanalyse; das Turnier mit seinen Ergebnissen |
| `homedarts.<entry>.report` | Die laufende Woche und der letzte Wochenbericht |
| `homedarts.<entry>.journal` | Sessions und Matches des Trainingskalenders, 365 Tage, höchstens je 3.000 |

Bevor ein Board gelöscht wird, kommen seine drei Speicher in ein Backup in `homedarts/backups/<Board-ID>` im Medienordner, die neuesten fünf je Board, das ein wieder hinzugefügtes Board mit derselben Board-ID zum Wiederherstellen anbietet. Highlight-Fotos, Exporte und Backups sind Dateien. Sie bleiben im Medienordner und im Exportordner, wenn die Integration gelöscht wird.

### Vom früheren Namen übernommen

Bis Version 1.18 hieß die Integration Autodarts, mit der Domain `autodarts` und Speichern wie `autodarts.<entry>.training`. Wenn HomeDarts [ein Board übernimmt](new-name.de.md), das unter diesem Namen eingerichtet ist, geschieht alles in Home Assistant, ohne Anmeldung, ohne Token und ohne Verbindung ins Internet:

- **Speicher.** Die drei Speicher des alten Eintrags, mit Training, Spielen, Berichten und Kalender, werden geladen und als Speicher des neuen Eintrags gesichert, `homedarts.<entry>.…`; danach wird der alte Eintrag entfernt.
- **Verwaltung.** Die Entitäten und das Gerät des Boards wechseln in der Entitäts- und Geräteverwaltung von Home Assistant zum neuen Eintrag, mit ihren IDs, Namen, Bereichen und Anpassungen, sodass Verlauf und Statistiken bei ihnen bleiben.
- **Medien.** Die Highlights, Exporte und Voice-Packs ziehen im Medienordner vom Ordner `autodarts` nach `homedarts`; eine Datei, die dort schon liegt, bleibt.
- **Dashboards.** Die Karten und die Strategie in den Dashboards, die Home Assistant verwaltet, bekommen ihre neuen Typen, und aus `board_style: autodarts` wird `flat`; Dashboards in YAML, Automationen und Skripte bleiben, wie sie sind, und eine Reparatur listet die, die noch den alten Namen nutzen.
- **Alte Dateien.** Mit dem letzten Board löscht die Übernahme den Ordner der Integration unter ihrem früheren Namen, `autodarts` in `custom_components`, erkannt an ihrem Manifest. Andere Integrationen mit der Domain `autodarts` und ihre Boards bleiben unberührt.

## Sicherheit

- Die lokale API des Board Managers verlangt keine Anmeldung. Jeder, der Port 3180 in deinem Netzwerk erreicht, kann sie nutzen, mit oder ohne Home Assistant. Betreibe den Board-PC in einem vertrauenswürdigen Netzwerk.
- Aktionen werden nur gesendet, wenn du oder eine Automation sie auslöst, und nie automatisch wiederholt.
