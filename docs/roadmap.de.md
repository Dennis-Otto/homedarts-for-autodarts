---
description: "Was jede Version von HomeDarts for Autodarts gebracht hat, was das nächste Release bringt, was später kommt und was die Integration nicht tun wird."
---

# Roadmap

[← Dokumentation](README.de.md) · [English](roadmap.md)

Diese Roadmap zeigt, was jede Version gebracht hat, was das nächste Release bringt und was danach kommt. *Als Nächstes* und *Später* blicken mindestens ein Jahr voraus, bis Oktober 2027, *Nicht geplant* sagt, was die Integration nicht tun wird, und *Reichweite*, wie viele Menschen sie finden. Sie ist eine Richtung, kein Versprechen: Die Prioritäten richten sich nach den Rückmeldungen der Spieler, die Termine nach der verfügbaren Freizeit. Ideen und Stimmen sind als [Funktionswunsch](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose) willkommen.

## Version 1.0: das lokale Fundament

Enthalten, alles ohne Autodarts-Cloud:

- Lokale Echtzeitverbindung zu Board Manager 1 und 2 mit automatischer Erkennung.
- Steuerung, Board-Einstellungen, Kamerazustand und Board-Manager-Updates.
- Trainingsanalyse mit Treffern pro Feld, Aufnahmeverlauf und dem Ereignis `visit_completed`.
- Drei Dashboard-Karten, ein automatisches Dashboard und sechs Blueprints.
- Dokumentation auf Englisch und Deutsch.

## Version 1.1: Trainingssessions

- Trainingssessions, die mit dem ersten Dart oder bewusst beginnen, nach einer Pause enden und eine Übersicht der letzten 20 Sessions behalten.
- Die Ereignisse `session_started` und `session_ended` und ein siebter Blueprint, der Licht, Erkennung und Kalibrierung an die Session koppelt.
- Die letzten Aufnahmen in der Live-Karte, Sessionstatus und vergangene Sessions in der Trainingskarte.
- Details zum Board-PC aus Board Manager 2: Betriebssystem, Prozessor und Erkennungssoftware.

## Version 1.2: Übungsspiele und Live-Kameras

- X01-Übungsspiele (301, 501, 701) am lokalen Board: Restpunkte, Überwerfen, Double-Out, Checkout-Wege und die letzten 10 Legs, mit den Ereignissen `bust` und `leg_won`.
- Ein Übungsspiel-Bereich in der Live-Karte mit Checkout-Weg und nächstem Zielfeld sowie die Steuerung des Übungsspiels im automatischen Dashboard.
- Live-Kamerastreams von Board Manager 2 statt Standbildern.
- Kamerazustand direkt nach dem Start oder Stopp der Erkennung statt erst nach der nächsten Abfrage.

## Version 1.3: Matches, Trainingsspiele und Statistik

- X01-Matches für zwei bis vier Spieler an einem Board: Nach dem Ziehen der Darts ist der Nächste dran, mit Legs, Sätzen, Spielernamen und Anzeigetafel in der Live-Karte.
- Trainingsspiele: Around the Clock, Doppeltraining, Checkout-Training und Bob's 27, mit umrandetem Ziel auf der Scheibe.
- Übungsstatistik: First-9-Average, Checkout-Quote, Doppelquote und Legs pro Tag.
- Zwei Blueprints: ein Übungs-Caller und ein Highlight-Foto nach einer 180 oder einem Checkout.

## Version 1.4: Cricket, Anzeigetafel und Bestleistungen

- Cricket für einen bis vier Spieler mit Marks, geschlossenen Zahlen, Punkten und Marks pro Runde sowie einer Kreidetafel in der Live-Karte.
- Eine Anzeigetafel als Karte und als Vollbild-Ansicht für einen Bildschirm am Board, lesbar vom Abwurf aus.
- Bestleistungen mit einem Ereignis, sobald eine fällt, eine Trainingsserie in Tagen und ein Tagesziel.
- `homedarts.start_game` startet X01, Cricket oder ein Trainingsspiel mit Spielern, Namen und Format in einer Aktion.
- Erkennungsqualität: der Anteil korrigierter Darts, mit einer Reparatur, die das Board nachkalibriert, wenn er steigt.

## Version 1.5: Partyspiele, Spielerprofile, Doubles und ein Caller

- Shanghai, Halve-It und Killer für einen bis vier Spieler; X01 von 101 bis 1001 mit Double-In und Ausbullen.
- Spielerprofile mit Statistik und Bestleistungen pro Name, Match-Verlauf und direkten Vergleichen sowie eine Spielerkarte.
- Eine Doppelanalyse mit der Quote jedes Doubles, eine Doubles-Karte und persönliche Checkout-Wege.
- Ein Caller in der Anzeigetafel, der das Spiel über den Browser ansagt, standardmäßig aus.
- `homedarts.delete_player` löscht ein Spielerprofil, etwa nach einem Tippfehler im Namen.

## Version 1.6: mehr Spiele, eine Spielauswahl, Berichte und Online-Matches

Erschienen als 1.6.0 am 27. September 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#160) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Mehr Spiele** | Cut-Throat Cricket, Tactics, Golf, Baseball und Count-Up; die Trainingsspiele 121-Checkout, Catch 40, JDC Challenge und Singles-Training | Fertig |
| **Handicap und Teams** | Unterschiedliche X01-Startpunkte pro Spieler im selben Match, etwa 501 gegen 301, und zwei Teams zu zwei bei X01 und den Cricket-Spielen | Fertig |
| **Offizielle Regeln** | Satzfolge der PDC, Match-Ergebnisse wie 3:2, Checkout-Wege wie in den Tabellen der Profis, Ausbullen nach den Regeln von WDF und PDC | Fertig |
| **Eine Anzeigetafel, die Spiele startet** | Eine Spielauswahl am Board, ein Ruhemodus mit Bestenliste und die Bilder von Spielern, die mit Personen von Home Assistant verknüpft sind | Fertig |
| **Berichte** | Ein Wochenbericht mit Blueprint, ein Trainingskalender über ein Jahr und Exporte als CSV oder JSON | Fertig |
| **Highlights und Licht** | Eine Highlight-Galerie in der Medienansicht und ein Blueprint für Lichtshows | Fertig |
| **Online-Matches** *(experimentell)* | Überwerfen, gewonnene Legs und Matches von Online-Matches über die Browser-Erweiterung Tools for Autodarts | Fertig |
| **Turniermodus** | Jeder gegen jeden oder K.-o. für drei bis acht benannte Spieler an einem Board: Tabelle oder Turnierbaum auf der Anzeigetafel, das nächste Match startet von selbst, und die Ergebnisse fließen in die Spielerprofile | Fertig |
| **Match-Zusammenfassung** | Averages, Checkout-Quote, höchster Checkout, 180er und bestes Leg jedes Spielers nach einem Match, auf der Anzeigetafel, der Live-Karte und in `match_won` | Fertig |
| **Erfolge** | Meilensteine pro Spieler in Stufen, etwa die erste 180, ein Checkout ab 100, ein Neun-Darter oder eine Serie von zehn Tagen, jeweils mit einem Ereignis und als Abzeichen | Fertig |
| **Trends und Trefferbilder pro Spieler** | Average, Checkout-Quote und Doppelquote pro Woche als Verlauf, das eigene Trefferbild jedes Spielers und eine Bestenliste mit den Rekorden aller Spieler | Fertig |
| **Trefferbild der Dart-Positionen** | Ein Trefferbild, das zeigt, wo jeder Dart gelandet ist, aus den Positionen, die das Board meldet, mit der Streuung in Millimetern; die Karte wechselt zwischen Feldern, Zahlen und Positionen | Fertig |
| **Ein Bot und Korrekturen** | Ein Bot mit Stärke 20 bis 120 bei X01 und den Cricket-Spielen, Korrekturen mit einem Tipp, von Hand eingegebene Darts per Tastenfeld, das Zurücknehmen der letzten Aufnahme und Stellwürfe, wo kein Checkout möglich ist | Fertig |
| **Niederländisch, Französisch und Spanisch** | Die Integration, die Karten und der Caller in drei weiteren Sprachen, mit Tests, die jede Sprache vollständig halten | Fertig |
| **Dokumentation** | Bebilderte Anleitungen zu Spielen, zur Anzeigetafel und zur Statistik, ein Glossar und ein Abschnitt zur Barrierefreiheit | Fertig |

## Version 1.7: Dart-Positionen, auf die du dich verlassen kannst

Erschienen als 1.7.0 am 28. September 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#170) (auf Englisch).

- Das Positionen-Trefferbild der Trainingskarte folgt jedem Dart live.
- Korrigierte Darts verlieren die falsch erkannte Position des Boards, oder sie bekommen die Stelle, die du auf der Scheibe der Anzeigetafel antippst, und damit gleich das Feld.

## Version 1.8: jede Karte auf jedem Bildschirm

Erschienen als 1.8.0 am 28. September 2026 und 1.8.1 am 29. September 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#180) (auf Englisch).

- Jede Karte passt vom 360-Pixel-Handy bis zum 27-Zoll-Touch-Monitor, hoch und quer, mit Bedienelementen von mindestens 40 Pixeln für den Finger.
- Korrekturen auch auf der Live-Karte, mit Lupe und Zoom auf jedem Touch-Bildschirm.
- Ein Stift zeigt, was ein Tipp bearbeitet, ein Pfeil, was er öffnet; Zustände wechseln mit ruhigen Animationen.
- Die Doppel-Karte zählt jeden Doppel-Treffer, in jedem Spiel.
- Nichts auf den Karten ändert seine Höhe, solange ein Spiel läuft.

## Version 1.9: Spiele per Sprache

Erschienen als 1.9.0 am 29. September 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#190) (auf Englisch).

- Ein Blueprint, der ein Spiel startet, wenn du es Assist sagst, zum Beispiel „Starte 501 für Alex und Sam“ oder „Starte das Spiel Cricket für Alex“, auf Deutsch und Englisch, mit einer Antwort in Worten.
- Was die Maus als Tooltip zeigt, zeigt auch ein Tipp.
- Die Spieleinstellungen des automatischen Dashboards in einer eigenen Ansicht.

## Version 1.10: wie am Dartautomaten

Erschienen als 1.10.0 am 8. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1100-2026-10-08) (auf Englisch).

- Wild Mouse, auch als Minnesota Cricket bekannt: Cricket plus Doubles, Triples und Three in a Bed.
- Zielhilfen auf der Kreidetafel jedes Cricket-Spiels, und Darts ohne Wirkung werden durchgestrichen.
- Konfetti und ein goldenes Leuchten bei 180, Game Shot und Match auf der Anzeigetafel.
- So wird gespielt: jedes Spiel kurz erklärt auf dem Bildschirm für ein neues Spiel.
- Partyspiele für bis zu acht Spieler.
- Eine Entnahme, die Board Manager 2.0.2 nie beendet, löst sich von selbst.
- Animationen und Diagramme der neuen Spiele, und was sich beim Umstieg von Autodarts 1.x auf 2.x ändert.

## Version 1.11: Spielen ohne Autodarts

Erschienen als 1.11.0 am 9. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1110-2026-10-09) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Dartscheibe ohne Autodarts** | Jede Dartscheibe als eigenes Board, jeder Dart auf dem Tastenfeld der Live-Karte und der Anzeigetafel eingegeben, mit allen Spielen, dem Training und den Statistiken ([Anleitung](without-autodarts.de.md)) | Fertig |
| **Autodarts später** | Eine Dartscheibe ohne Autodarts wird zum Autodarts-Board, wenn eins kommt, und behält ihre Statistiken ([wie](without-autodarts.de.md#autodarts-später)) | Fertig |
| **Die Punkte einer Aufnahme** | X01-Aufnahmen als Punktzahl eingegeben, etwa 140, mit den Darts auf ein Doppel beim Checkout ([wie](without-autodarts.de.md#darts-eingeben)) | Fertig |
| **Das Tastenfeld auf der Live-Karte** | Das Tastenfeld der Anzeigetafel unter den Darts der Live-Karte, mit *Nächster Spieler* und *Letzte Aufnahme zurück*, solange *Übungsspiel manuelle Eingabe* an ist ([Live-Karte](cards.de.md#live-karte)) | Fertig |

## Version 1.12: Darts per Sprache

Erschienen als 1.12.0 am 9. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1120-2026-10-09) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Darts per Sprache** | „Alex hat 140“, „Checkout mit zwei Darts“, „Triple 20“, „Nächster Spieler“ und „Rückgängig“ zu Assist, auf Deutsch und Englisch, mit einer Antwort in den Worten des Callers ([Blueprint](automations.de.md#enter-darts-by-voice)) | Fertig |
| **Antworten der Aktionen am Board** | `homedarts.enter_visit`, `homedarts.throw_dart`, `homedarts.next_player` und `homedarts.undo_visit` antworten in Worten: was eine Aufnahme gebracht und übrig gelassen hat, wer als Nächstes wirft oder warum sie abgelehnt haben ([Aktionen](entities.de.md#aufnahmepunkte-eingeben-homedartsenter_visit)) | Fertig |

## Version 1.13: die Regeln von play.autodarts.io

Erschienen als 1.13.0 am 14. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1130-2026-10-14) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **X01 wie auf play.autodarts.io** | In- und Out-Modus *Straight*, *Double* und *Master*, der Bull-Modus *50/50*, in dem das Single-Bull 50 zählt, und eine Rundengrenze von 1 bis 50, nach der die niedrigste Restpunktzahl das Leg gewinnt; auf dem Bildschirm für ein neues Spiel, mit vier neuen Entitäten und in `homedarts.start_game`, auch gegen den Bot ([X01](games.de.md#x01)) | Fertig |

## Version 1.14: das beste Ziel aus der eigenen Streuung

Erschienen als 1.14.0 am 14. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1140-2026-10-14) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Wohin zielen** | Ein vierter Modus des Trefferbilds, die Zielkarte, färbt die Scheibe nach den Punkten pro Dart, die die Streuung deiner eigenen Darts an jeder Stelle bringt, und zieht einen Ring um den besten Zielpunkt, verglichen mit der Triple 20, der Triple 19 und dem Bull, ab 30 Darts auf ein Triple; das Spielerprofil hat ihn für Automationen und Assist ([Wohin zielen](statistics.de.md#wohin-zielen)) | Fertig |
| **Sprachsteuerung auf Spanisch, Französisch und Niederländisch** | Spiele per Sprache starten und Darts per Sprache eingeben auch auf Spanisch, Französisch und Niederländisch, nicht nur auf Deutsch und Englisch, etwa „Juega 501 para Alex y Sam“, „Alex a fait 140“ oder „Dubbel 16“, mit Zahlen als Ziffern oder als Wörter ([Blueprint](automations.de.md#start-a-game-by-voice)) | Fertig |

## Version 1.15: drei Partyspiele, Voice-Packs und eine Live-Demo

Erschienen als 1.15.0 am 18. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1150-2026-10-18) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Bermuda, Round the World und Gotcha** | Drei weitere Partyspiele für einen bis acht Spieler, wie auf play.autodarts.io, vom Bildschirm für ein neues Spiel, per Sprache oder mit `homedarts.start_game` ([Partyspiele](games.de.md#partyspiele)) | Fertig |
| **Voice-Packs** | Die Caller spielen aufgenommene Ansagen ab, und ein Voice-Pack von darts-caller funktioniert, wie es ist; *Voice-Pack erzeugen* nimmt ein vollständiges Pack mit jeder Text-to-Speech-Engine von Home Assistant auf, etwa Piper ([Voice-Packs](scoreboard.de.md#voice-packs)) | Fertig |
| **Live-Demo** | Die [Live-Demo](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html?lang=de) spielt ein 501 gegen den Bot, ein Cricket-Spiel und ein Turnier mit den Karten im Browser, auch auf dem Handy und in fünf Sprachen, ohne dass du etwas installierst | Fertig |

## Version 1.16: Pixelanzeigen, Chromecast und Caller in deiner Sprache

Erschienen als 1.16.0 am 18. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1160-2026-10-18) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Der Spielstand auf einer Pixelanzeige** | Der Blueprint *Autodarts: score display* zeigt das Übungsspiel auf einer AWTRIX 3, etwa der Ulanzi TC001, oder auf einem PixelIt am Board: die Restpunkte nach jedem Dart, den Checkout-Weg, eine 180, ein Überwerfen und den Sieger ([Spielstand](automations.de.md#spielstand-auf-einer-awtrix-oder-einem-pixelit)) | Fertig |
| **Die Anzeigetafel über Chromecast** | Home Assistant Cast zeigt die Karten und das automatische Dashboard auf einem Fernseher mit Chromecast oder auf einem Google Nest Hub ([Home Assistant Cast](scoreboard.de.md#auf-dem-fernseher-mit-home-assistant-cast)) | Fertig |
| **Ansagen in der Sprache von Home Assistant** | Der Dart-Caller, der Übungs-Caller, der Trainings- und der Wochenbericht sprechen die Sprache von Home Assistant, auf Deutsch, Englisch, Niederländisch, Französisch und Spanisch, ohne eigene Nachricht ([Ansagen](automations.de.md#ansagen-in-der-sprache-von-home-assistant)) | Fertig |
| **Ein Caller für blinde und sehbehinderte Spieler** | Der Caller der Anzeigetafel sagt jeden Dart an, sobald er landet, den Checkout-Weg nach jedem Dart und das nächste Ziel eines Trainings- oder Partyspiels, auch aus einem Voice-Pack ([Für blinde und sehbehinderte Spieler](scoreboard.de.md#für-blinde-und-sehbehinderte-spieler)) | Fertig |
| **Die Cloud-Verknüpfung** | Vorbereitet und verborgen: die Momente von Online-Matches aus der Autodarts-Cloud, ohne Browser-Erweiterung, als dieselben Board-Ereignisse wie von der Online-Brücke, auch für Boards ohne Board Manager in deinem Netzwerk wie Lens | Entfernt, weil Autodarts keine Client-IDs an Dritte vergibt ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch; siehe [Nicht geplant](#nicht-geplant)) |
| **Schneller auf einem Raspberry Pi** | Jede Aktion speichert das Training einmal statt zweimal, Stellwürfe sind in einem Zehntel der Zeit gefunden, und Home Assistant lädt die Integration bis zu einer halben Sekunde schneller ([Stellwürfe](how-it-works.de.md#stellwürfe)) | Fertig |

## Version 1.17: große Turniere, Streaming und Granboard

Erschienen als 1.17.0 am 19. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1170-2026-10-19) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Turniere bis 32 Spieler** | Ein K.-o.-System mit bis zu 32 Spielern, ein Doppel-K.-o.-System und Gruppen mit K.-o.-System, mit den Tabellen der Gruppen und der Verliererrunde auf der Anzeigetafel ([Turniere](games.de.md#turniere)) | Fertig |
| **Ein Turnier auf mehreren Boards** | Ein Turnier auf zwei oder mehr Boards zugleich, Autodarts-Boards und Dartscheiben ohne Autodarts gleichermaßen, mit dem voraussichtlichen Ende des Turniers auf jeder Anzeigetafel ([Ein Turnier auf mehreren Boards](games.de.md#ein-turnier-auf-mehreren-boards)) | Fertig |
| **Random Cricket und Hidden Cricket** | Cricket auf sechs Zahlen von 1 bis 20, für jedes Leg neu gezogen, und dem Bull, wie bei Scolia, Granboard und Dartsmind; Hidden Cricket hält die Zahlen verborgen, bis ein Dart eine findet, und beide spielen auch gegen den Bot und in Turnieren ([Random Cricket](games.de.md#random-cricket), [Hidden Cricket](games.de.md#hidden-cricket)) | Fertig |
| **Stream-Overlay und Highlight-Clips** | Die Anzeigetafel allein über dem Bild eines Streams in OBS Studio oder Streamlabs, und jeder große Moment als MP4-Clip neben seinem Highlight-Foto ([Stream-Overlay](scoreboard.de.md#stream-overlay), [Highlight-Clips](automations.de.md#highlight-clips)) | Fertig |
| **Fragen an Assist** | „Wie ist mein Schnitt heute?“, „Wie viele 180er diese Woche?“, „Was ist mein höchster Checkout?“, „Wer führt die Bestenliste an?“ und „Wohin soll ich zielen?“ an Assist, auf Deutsch, Englisch, Spanisch, Französisch und Niederländisch, beantwortet aus den Statistiken des Boards ([Blueprint](automations.de.md#ask-assist-about-your-darts)) | Fertig |
| **Blueprints, die mit der Integration kommen** | Alle fünfzehn Blueprints auf der Blueprint-Seite, ohne sie zu importieren, und jedes Update bringt ihre neuen Versionen; ein Blueprint, den du geändert hast, bleibt deiner ([Updates der Blueprints](automations.de.md#updates-der-blueprints)) | Fertig |
| **Granboard über Bluetooth** *(experimentell)* | Ein Granboard schickt seine Darts über Bluetooth, auch über einen ESPHome-Bluetooth-Proxy, für jedes Spiel, das Training und die Statistiken, ohne dass jemand einen Dart eingibt ([Granboard über Bluetooth](granboard.de.md)) | Fertig; an einem echten Board noch nicht geprüft (siehe [Als Nächstes](#als-nächstes)) |

## Version 1.18: Gruppen und Aufsteiger beim Turnierstart

Erschienen als 1.18.0 am 19. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#1180-2026-10-19) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Gruppen und Aufsteiger** | *Turniergruppen* und *Turnier Weiter je Gruppe* kommen zu den Turnier-Einstellungen: *Turnier starten* und `homedarts.start_tournament` spielen mit ihnen Gruppen und K.-o.-System, und der Bildschirm für ein neues Spiel übernimmt sie als Vorgabe ([Turniere](entities.de.md#turniere)) | Fertig |
| **Im HACS-Standardkatalog** | In HACS nach *Autodarts* suchen und herunterladen, ohne vorher ein benutzerdefiniertes Repository hinzuzufügen ([Installieren](installation.de.md#mit-hacs-empfohlen)) | Fertig am 20. Oktober 2026 ([hacs/default#11306](https://github.com/hacs/default/pull/11306)) |

## Version 2.0: HomeDarts for Autodarts

Erschienen als 2.0.0 am 21. Oktober 2026; die Details stehen im [Changelog](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md#200-2026-10-21) (auf Englisch).

| Thema | Was es bringt | Stand |
| --- | --- | --- |
| **Ein eigener Name** | Die Integration heißt auf Wunsch von Autodarts jetzt HomeDarts for Autodarts, mit der Domain `homedarts` und einem eigenen Symbol; ihre Aktionen, Karten und Ordner folgen der Domain, etwa `homedarts.start_game` ([Von Autodarts zu HomeDarts](new-name.de.md), [Entscheidung 0026](decisions/0026-a-name-of-its-own.md), auf Englisch) | Fertig |
| **Die Boards kommen mit** | HomeDarts übernimmt die Boards, die unter dem alten Namen eingerichtet sind: ihre Entitäten mit ihren IDs, Verlauf und Statistiken, die Speicher von Training, Spielen und Berichten, die Highlights, Exporte und Voice-Packs und die Karten in den Dashboards; eine Reparatur listet die Automationen auf, die noch die alten Aktionen aufrufen ([Umsteigen](new-name.de.md#umsteigen)) | Fertig |
| **Keine Cloud-Verknüpfung** | Die vorbereitete Verknüpfung mit der Autodarts-Cloud ist entfernt, weil Autodarts keine Client-IDs an Dritte vergibt; HomeDarts arbeitet lokal, und Online-Matches kommen über Tools for Autodarts ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch) | Fertig |

## Als Nächstes

Ideen für die Versionen nach 2.0. Stimmen und Reaktionen auf die [Feature-Wünsche](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose) bestimmen die Reihenfolge.

| Thema | Was es bringt | Voraussetzung |
| --- | --- | --- |
| **Granboard an einem echten Board** | Jedes Feld eines echten Granboards prüfen und die Kennzeichnung *experimentell* von der Granboard-Unterstützung aus 1.17 nehmen | Ein Spieler mit Granboard, der [jedes Feld prüft](granboard.de.md#jedes-feld-prüfen) und meldet, was falsch zählt |
| **Autodarts Desktop** | Boards mit Autodarts Desktop prüfen und dokumentieren, was funktioniert; ein Spieler hat 2.0.2 unter Linux als funktionierend gemeldet ([#105](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/105)) | Testberichte von Spielern, die es unter Windows nutzen |
| **Weitere Sprachen** | Integration und Karten in weiteren Sprachen, und die Fragen und Antworten von Assist auf Spanisch, Französisch und Niederländisch so, wie Muttersprachler sie sagen ([#380](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/380), auf Englisch) | Beiträge von Muttersprachlern ([so kommt eine Sprache dazu](development.de.md#übersetzungen)) |

## Später

| Thema | Voraussetzung |
| --- | --- |
| **Protokoll-Bibliothek auf PyPI** (`aioautodarts`) | Eine eigene Bibliothek für das Board-Manager-Protokoll, Voraussetzung für einen möglichen Weg in den Home-Assistant-Kern; zurückgestellt, bis das Protokoll sich gesetzt hat |

## Nicht geplant

- **Ein Cloud-Konto für das lokale Spiel.** Alles, was mit dem Board Manager in deinem Netzwerk funktioniert, funktioniert weiter ohne Autodarts-Konto.
- **Eine Verknüpfung mit der Autodarts-Cloud.** Autodarts vergibt keine Client-IDs an Integrationen von Dritten, deshalb bleiben Spieldaten aus der Cloud und Boards ohne Board Manager in deinem Netzwerk wie Lens außer Reichweite; die Momente von Online-Matches kommen über die [Online-Brücke](online-matches.de.md) ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch).
- **Telemetrie.** Die Integration sendet nichts über deine Spiele oder dein Zuhause irgendwohin, und im lokalen Betrieb verlässt nichts dein Netzwerk.
- **Brechende Änderungen ohne Weg nach vorn.** Bestehende Integrationseinträge, Entitäts-IDs und Automationen funktionieren weiter, oder ein Release migriert sie und seine Notes sagen, was sich ändert.

## Reichweite

Wie viele Menschen die Integration finden und installieren, einmal im Monat gezählt: aus den Zahlen, die GitHub für das Repository führt, und aus der [Statistik von Home Assistant](https://analytics.home-assistant.io/), die eine benutzerdefinierte Integration aufführt, sobald eine Installation sie hat, die ihre Nutzung teilt. Die Integration selbst zählt nichts (siehe [Nicht geplant](#nicht-geplant)). `bash scripts/reach.sh de` gibt die Zeile des Monats auf Deutsch aus. Die Statistik führt die Integration unter ihrer Domain, seit 2.0 `homedarts`; andere Integrationen für Autodarts behalten die Domain `autodarts`, die diese bis 1.18 hatte (siehe [Umstieg von anderen Werkzeugen](coming-from.de.md)), und das Skript zählt die Statistik nur für eine Version, die ein Release dieser Integration ist.

| Monat | Downloads der Releases | Besucher in 14 Tagen | Von Google | In der Statistik | Sterne |
| --- | --- | --- | --- | --- | --- |
| Oktober 2026 | 120 | 29 | 0 | Nein | 3 |

Die Downloads zählen jede Installation und jedes Update über HACS seit dem ersten Release, auch die der Betas. Wo die Integration zu finden ist, und die Beiträge, die auf sie zeigen:

| Wo | Stand |
| --- | --- |
| HACS-Standardkatalog | Aufgenommen am 20. Oktober 2026 ([hacs/default#11306](https://github.com/hacs/default/pull/11306)): Eine Suche nach *Autodarts* in HACS findet sie |
| [awesome-home-assistant](https://github.com/frenck/awesome-home-assistant) | Nimmt Projekte ab einem Alter von sechs Monaten auf, dieses also ab März 2027 |
| Home-Assistant-Forum, Reddit und der Autodarts-Discord | Die [Beiträge zum Start](creator-kit.de.md#beiträge-zum-start) sind fertig |
| Fotos von Boards, an denen sie läuft | [Show and tell](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/categories/show-and-tell) |

## So werden Prioritäten gesetzt

1. Alles, was bei Nutzern kaputtgeht, auch durch neue Board-Manager-Versionen, kommt zuerst.
2. Lokale Funktionen kommen vor Cloud-Funktionen.
3. Danach Wünsche mit den meisten Reaktionen auf GitHub.
