---
description: "Probleme von HomeDarts lösen: Einrichtung, Reparaturen, ein Board, das fehlt oder nicht aktualisiert, der Wechsel vom alten Namen, Autodarts 2 und Logs."
---

# Fehlerbehebung

[← Dokumentation](README.de.md) · [English](troubleshooting.md)

## Schnelle Prüfung

1. **Läuft der Board Manager?** Öffne `http://<Board-IP>:3180` im Browser eines Geräts im selben Netzwerk. Board Manager 1 zeigt seine App; Board Manager 2 antwortet unter `http://<Board-IP>:3180/api/state`.
2. **Ist die Entität *Lokale Verbindung* an?** Wenn nicht, erreicht Home Assistant das Board nicht. Prüfe Adresse, Port und das Netzwerk dazwischen: VLANs, Firewall, Docker-Netzwerk.
3. **Ist die Entität *Echtzeitverbindung* an?** Wenn nicht, kommen Änderungen trotzdem alle 2 Sekunden an, nur nicht sofort. Siehe [Echtzeitverbindung](#keine-echtzeitaktualisierung).

## Einrichtung

| Meldung | Ursache und Lösung |
| --- | --- |
| *Gib nur eine IP-Adresse oder einen Hostnamen ein.* | Die Adresse enthält mehr als den Host, etwa `http://`, einen Pfad oder einen Port. Trage nur die IP-Adresse oder den Hostnamen ein und den Port in sein eigenes Feld. |
| *Der lokale Board Manager ist nicht erreichbar oder liefert keine gültigen Daten.* | Falsche Adresse oder falscher Port, der Board Manager läuft nicht, oder auf dem Port antwortet etwas anderes. Trage nur die IP-Adresse ein, ohne `http://` und ohne Port. |
| *Das Board verweigert den Zugriff (HTTP 401 oder 403).* | Der Board Manager selbst braucht keine Anmeldung. Etwas vor Port 3180 blockiert Home Assistant, zum Beispiel ein Reverse Proxy, eine Firewall oder eine Anmeldeseite. Lass Home Assistant direkt auf das Board zugreifen oder trage die Adresse des Boards selbst ein. |
| *Im Board Manager ist noch keine Board-ID eingerichtet.* | Das Board ist noch nicht bei Autodarts eingerichtet. Schließe die Einrichtung im Board Manager ab und versuche es erneut. |
| *Es wurden keine neuen Boards automatisch gefunden.* | Die Suche findet nur Boards, die von deinem Internetanschluss aus registriert und noch nicht eingerichtet sind. Gib stattdessen die Adresse ein. |
| *Die Board-Suche ist gerade nicht erreichbar.* | Der Suchdienst von Autodarts ist nicht erreichbar. Gib stattdessen die Adresse ein. |
| *Dieses Autodarts-Board ist bereits eingerichtet.* | Das Board ist schon vorhanden. Über **Neu konfigurieren** änderst du seine Adresse. |
| *Diese Adresse gehört zu einem anderen Board.* | **Neu konfigurieren** hat unter der neuen Adresse ein anderes Board gefunden. Trage die Adresse des Boards ein, zu dem dieser Eintrag gehört, oder füge das andere Board als neuen Eintrag hinzu. |
| *Das im Netzwerk gemeldete Board antwortet nicht.* | Ein entdecktes Board hat unter der gemeldeten Adresse nicht geantwortet, etwa weil der Board Manager inzwischen gestoppt ist. Starte den Board Manager und füge das Board erneut hinzu oder gib seine Adresse ein. |
| *Die Einrichtung dieses Boards läuft bereits.* | Ein anderer Einrichtungsdialog für dasselbe Board ist offen, etwa der des entdeckten Boards. Schließe die Einrichtung ab oder brich sie ab. |
| *Es gibt kein Board der Integration Autodarts mehr zum Übernehmen.* | Jedes Board, das unter dem früheren Namen von HomeDarts eingerichtet war, ist schon übernommen. HomeDarts übernimmt nur seine eigenen Boards, nicht die anderer Integrationen mit dem Namen Autodarts: Füge so ein Board als neues hinzu ([Umstieg von anderen Werkzeugen](coming-from.de.md)). |
| Das Board wird nicht automatisch gefunden | Die automatische Erkennung braucht Board Manager 2 und mDNS im Netzwerk. Home Assistant in Docker braucht dafür `network_mode: host`; über VLAN-Grenzen hinweg funktioniert mDNS nur mit einem Repeater. Nutze sonst die Suche oder die Adresse. |

## Reparaturen

Unter **Einstellungen → Reparaturen** kann Home Assistant diese Hinweise anzeigen:

| Hinweis | Bedeutung und Lösung |
| --- | --- |
| **Autodarts-Board-Adresse zeigt auf ein anderes Board** | Unter der eingerichteten Adresse antwortet ein Board mit anderer Board-ID, etwa nach vertauschten IP-Adressen. Die Entitäten bleiben nicht verfügbar, damit sie nie Daten eines fremden Boards zeigen. Öffne die Integration, wähle **Neu konfigurieren** und das richtige Board. Der Hinweis verschwindet dann von selbst. |
| **Autodarts-Board kalibrieren** | Mindestens 20 % der letzten 100 Darts, bei mindestens 50 Darts insgesamt, mussten korrigiert werden, vom Board, auf der Anzeigetafel oder mit `homedarts.correct_dart`, siehe *Korrekturquote der Erkennung*. Zieh alle Darts, öffne den Hinweis und bestätige: Die Integration kalibriert alle Kameras und zählt wieder bei null. Der Hinweis verschwindet auch, sobald die Quote unter 10 % fällt. |
| **Board auf den neuen Autodarts Board Manager umstellen** | Das Board nutzt noch den klassischen Board Manager 1, den Autodarts abschalten wird. Installiere Board Manager 2 auf dem Board-PC; die Integration stellt sich selbst um, und der Hinweis verschwindet. |
| **Autodarts-Board sieht ständig eine Hand** | Das Board meldet eine Hand, die sich nicht bewegt, und erkennt keine Darts, siehe [unten](#keine-darts-weil-das-board-eine-hand-sieht). Bestätige den Hinweis, um die Erkennung neu zu starten. |
| **Autodarts-Board unter neuer Adresse gefunden** | Das Board antwortet unter seiner eingestellten Adresse nicht mehr mit seiner Board-ID, aber unter einer anderen, unter der Board Manager 2 es angekündigt hat (mDNS), etwa nach einer DHCP-Änderung. Öffne den Hinweis und bestätige nur, wenn es dein Board ist: Die Integration prüft die Adresse noch einmal, wechselt zu ihr und lädt neu. Entitäten, Training und Einstellungen bleiben erhalten. Siehe [Adresswechsel](how-it-works.de.md#adresswechsel). |
| **Autodarts-Board verweigert den Zugriff** | Das Board antwortet mit HTTP 401 oder 403. Der Board Manager braucht keine Anmeldung, also blockiert ein Reverse Proxy, eine Firewall oder eine Anmeldung vor Port 3180 Home Assistant. Lass Home Assistant auf das Board zugreifen; der Hinweis verschwindet beim nächsten erfolgreichen Lesen. |
| **Autodarts-Board antwortet in einem unbekannten Format** | Eine nötige Abfrage (Zustand, Einstellungen oder `/api/system`) hat dreimal hintereinander in einem Format geantwortet, das diese Version nicht versteht, meist nach einem Board-Manager-Update. Aktualisiere die Integration. Bleibt der Hinweis, [melde ihn](#fehler-melden) mit den Diagnosedaten; das Protokoll nennt die betroffenen Abfragen. |
| **Einige Automationen, Skripte oder Dashboards nutzen noch den alten Namen** | HomeDarts hat deine Boards übernommen, aber die aufgeführten Automationen, Skripte und YAML-Dashboards rufen noch Aktionen wie `autodarts.start_game` auf oder nutzen Karten wie `custom:autodarts-card`. Ersetze in ihren Aktionen `autodarts.` durch `homedarts.` und in den Typen ihrer Karten `custom:autodarts` durch `custom:homedarts`, dann ignoriere den Hinweis. Siehe [Automationen laufen nach dem Wechsel nicht mehr](#automationen-laufen-nach-dem-wechsel-zu-homedarts-nicht-mehr). |
| **Home Assistant neu starten, um den Wechsel zu HomeDarts abzuschließen** | Die Übernahme hat die Dateien der Integration unter ihrem früheren Namen entfernt; geladen bleibt sie bis zum Neustart von Home Assistant. Öffne den Hinweis und bestätige den Neustart. |

## Betrieb

### Entitäten sind nicht verfügbar

- **Alle Board-Entitäten:** Der Board Manager hat dreimal hintereinander nicht geantwortet; ein oder zwei verpasste Lesevorgänge, also wenige Sekunden, behalten die letzten Werte. Sobald das Board wieder da ist, erholen sich die Entitäten innerhalb von Sekunden. Training, Übungsspiel, persönliche Bestleistungen und die Board-Ereignisse bleiben verfügbar, auch wenn das Board beim Start von Home Assistant ausgeschaltet ist.
- **Nur Einstellungen und Kameras, der Rest funktioniert:** Das Board hat seine Konfiguration noch nicht gemeldet. Das erledigt sich beim nächsten Lesen, spätestens nach 30 Sekunden.
- **Nach einem Board-Manager-Update:** Beim Wechsel der Generation lädt sich die Integration neu. Warte ein paar Sekunden.

### Meldungen am Eintrag des Boards

**Einstellungen → Geräte & Dienste → HomeDarts for Autodarts** zeigt, warum ein Board nicht geladen ist oder seine Entitäten nicht verfügbar sind:

| Meldung | Ursache und Lösung |
| --- | --- |
| *Der Board Manager antwortet nicht.* | Das Board ist offline oder nicht erreichbar. Prüfe, ob Board-PC und Board Manager laufen; die Entitäten erholen sich von selbst. |
| *Gib die lokale Adresse des Board Managers ein: Öffne das Menü dieses Eintrags und wähle Neu konfigurieren.* | Der Eintrag hat keine lokale Adresse, etwa ein alter Cloud-Eintrag. Öffne das Menü des Eintrags (⋮) → **Neu konfigurieren** und trage die Adresse ein. |
| *Der Board Manager antwortet in einem Format, das diese Version der Integration nicht versteht.* | Meist nach einem Board-Manager-Update. Aktualisiere die Integration; siehe **Autodarts-Board antwortet in einem unbekannten Format** unter [Reparaturen](#reparaturen). |
| *Der Board Manager verweigert den Zugriff.* | Siehe **Autodarts-Board verweigert den Zugriff** unter [Reparaturen](#reparaturen). |
| *Das gespeicherte Training dieses Boards stammt aus einer neueren Version der Integration.* | Die Integration wurde auf eine ältere Version zurückgesetzt, nachdem eine neuere Training, Übungsspiel und Statistik gespeichert hatte. Installiere diese Version wieder oder stelle ein Backup von Home Assistant von vor dem Update wieder her. Bis dahin lädt das Board nicht, und die gespeicherten Daten bleiben unverändert. |
| *Das gespeicherte Training dieses Boards kann gerade nicht gelesen werden.* | Home Assistant konnte seinen Ordner `.storage` nicht lesen, etwa weil der Speicher voll ist oder sich die Berechtigungen geändert haben. Prüfe den freien Speicher und die Berechtigungen von `.storage`; Home Assistant versucht es von selbst erneut und überschreibt bis dahin nichts. |
| *Das gespeicherte Training dieses Boards kann nicht wiederhergestellt werden.* | Die gespeicherten Daten passen nicht zu dem, was diese Version erwartet. [Melde einen Fehler](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose) mit dem Protokoll und den Diagnosedaten; die gespeicherten Daten bleiben unverändert. |

### Eine Aktion schlägt fehl

| Meldung | Ursache und Lösung |
| --- | --- |
| *Das Board hat die Aktion nicht angenommen.* | Das Board hat den Befehl abgelehnt oder nicht geantwortet. Prüfe die Verbindung und versuche es erneut. |
| *Dieses Board unterstützt die Aktion nicht.* | Der Board Manager kennt diesen Befehl nicht, zum Beispiel die Kamerastreams bei Board Manager 1. |
| *Der Board Manager verweigert den Zugriff.* | Siehe **Autodarts-Board verweigert den Zugriff** unter [Reparaturen](#reparaturen). |
| *Es ist kein Autodarts-Board mit lokaler Verbindung geladen.* | Jede `homedarts`-Aktion braucht ein lokal verbundenes, geladenes Board. Prüfe den Eintrag unter **Einstellungen → Geräte & Dienste**. |
| Home Assistant meldet, dass du dazu nicht berechtigt bist (*Unauthorized*) | `homedarts.delete_player`, `homedarts.rename_player`, `homedarts.export`, `homedarts.backup`, `homedarts.restore`, `homedarts.link_player` und `homedarts.unlink_player` löschen die Daten der Spieler, schreiben sie heraus oder ersetzen sie, deshalb dürfen nur Administratoren sie ausführen, etwa nicht der Benutzer des Bildschirms am Board. Automationen führen sie auch aus. |
| *Es sind mehrere Autodarts-Boards eingerichtet. Wähle das Board.* | Bei mehreren Boards wählst du das Board in der Aktion, in YAML im Feld `config_entry_id`. |
| Home Assistant meldet, dass der Konfigurationseintrag nicht gefunden wurde, zu einer anderen Integration gehört oder nicht geladen ist | Das in der Aktion gewählte Board wurde gelöscht, ist ein Eintrag einer anderen Integration oder ist nicht geladen. Wähle das Board neu; lädt ein Board nicht, steht der Grund an seinem Eintrag. |
| *… steht mehrfach in der Spielerliste.* | Jeder Spieler braucht einen eigenen Namen. Spieler ohne Namen dürfen mehrfach vorkommen. |
| *Ein Spielername darf keine geschweiften Klammern, kein Prozentzeichen, keine Raute (#) und keine Steuerzeichen enthalten.* | Home Assistant würde diese Zeichen als Beginn einer Vorlage lesen. Lass `{`, `}`, `%`, `#` und Steuerzeichen weg. |
| *Killer braucht mindestens zwei Spieler.* | Nenne in der Aktion zwei bis vier Spieler oder stelle *Übungsspiel Spielerzahl* auf 2 oder mehr. |
| *Es gibt kein Spielerprofil mit dem Namen …* | Prüfe die Schreibweise; Groß- und Kleinschreibung spielen keine Rolle. Der Sensor *Spielerprofile* listet alle Profile. |
| *Es gibt keine Person … in Home Assistant.* | `homedarts.link_player` braucht eine Personen-Entität, etwa `person.alex`. Lege die Person zuerst unter **Einstellungen → Personen** an. |
| *Teams brauchen vier Spieler: Spieler 1 und 3 gegen Spieler 2 und 4.* | Nenne vier Spieler oder stelle *Übungsspiel Spielerzahl* auf 4. |
| *Teams spielen X01 und die Cricket-Spiele.* | Schalte *Teams* für Party- und Trainingsspiele aus. |
| *Startpunkte sind 0 (die des Spiels) oder 2 bis 1001.* | Korrigiere `start_scores` in der Aktion oder die Einstellung *Übungsspiel Startpunkte Spieler N*. |
| *Die Startpunkte nennen … Werte, es spielen aber nur … Spieler.* | `start_scores` hat höchstens einen Wert pro Spieler, in Wurfreihenfolge; mit dem Bot zählt auch sein Platz. Lass die überzähligen Werte weg. |
| *Teams spielen von den Startpunkten der Spieler 1 und 2, ein Wert pro Team.* | Im Team-Match gilt der erste Wert für Team 1 und der zweite für Team 2. Gib höchstens zwei an. |
| *Startpunkte von 3 lassen sich mit Double-In und Double-Out nicht auschecken: …* | Das einzige Eröffnungs-Double, D1, lässt 1 übrig, und die kann kein Double beenden. Wähle andere Startpunkte oder schalte Double-In oder Double-Out aus. |
| *… ist kein Feld des Boards.* | `segment` von `homedarts.correct_dart` und `homedarts.throw_dart` nimmt S1 bis S20, D1 bis D20, T1 bis T20, 25 für das äußere Bull, BULL für das Bullseye oder MISS. |
| *Nenne das Feld mit segment oder die Stelle des Darts mit x und y.* | `homedarts.correct_dart` und `homedarts.throw_dart` brauchen das Feld, die Position oder beides. |
| *Gib die Position mit x und y an …* | Eine Position braucht `x` und `y`, beide von -3 bis 3: 0 ist die Mitte, 1 der äußere Rand des Doppelrings, und `y` zeigt zur 20. |
| *Die angegebene Position liegt in …, nicht in …* | Das Feld ergibt sich aus der Position. Lass `segment` weg oder gib das Feld an dieser Stelle an. |
| *Die aktuelle Aufnahme hat keinen Dart …* | `homedarts.correct_dart` korrigiert Dart 1, 2 oder 3 der aktuellen Aufnahme, sobald er im Board steckt. Eine Aufnahme, deren Darts gezogen sind, holst du mit `homedarts.undo_visit` zurück. |
| *Die Darts des Bots lassen sich nicht korrigieren.* | Die Darts des Bots kommen von Home Assistant, nicht vom Board. Korrigieren lassen sich nur die Darts eines Spielers. |
| *Die manuelle Eingabe ist aus.* | `homedarts.throw_dart` nimmt Darts nur an, solange der Schalter *Übungsspiel manuelle Eingabe* an ist. Schalte ihn zuerst ein. |
| *Der Bot ist am Board.* | Der Bot wirft gerade seine Aufnahme. Warte sie ab oder beende sie mit `homedarts.next_player`. |
| *Die Aufnahme hat schon drei Darts.* | Gib mit `homedarts.next_player` weiter oder zieh die Darts, bevor du den nächsten Dart eingibst. |
| *Die Aufnahme hat keine Darts zum Beenden.* | Ohne Darts gibt `homedarts.next_player` nur weiter, wo ein Spieler aussetzen darf: in X01, den Cricket- und den Partyspielen, nicht aber in Trainingsspielen, beim Ausbullen und während bei Killer die Zahlen gewählt werden. |
| *Es gibt keine Aufnahme zum Zurücknehmen.* | `homedarts.undo_visit` nimmt die letzte abgeschlossene Aufnahme zurück, solange kein Dart im Board steckt und sich weder das Spiel noch die Trainingssession seitdem geändert haben. Zieh zuerst die Darts; die Darts der aktuellen Aufnahme korrigierst du mit `homedarts.correct_dart`. |
| *Die Bot-Stärke ist 0 (kein Bot) oder ein 3-Dart-Average von 20 bis 120.* | Korrigiere `bot_level` in der Aktion oder die Einstellung *Übungsspiel Bot-Stärke*. |
| *Mit dem Bot spielen bis zu drei Spieler: …* | Der Bot bekommt in X01 und den Cricket-Spielen einen eigenen Platz. Spiel mit höchstens drei Spielern oder stell die Bot-Stärke auf 0. |
| *Der Exportordner … darf nicht versteckt sein, und Home Assistant muss dort Schreiben erlauben: …* | Lass den Ordner leer für `homedarts/exports` im Medienordner, oder wähle einen Ordner, der nicht mit einem Punkt beginnt, in `www`, in einem Medienordner oder in einem Ordner aus `allowlist_external_dirs`. |
| *Der Export konnte nicht geschrieben werden: …* | Der Ordner ist nicht beschreibbar oder der Speicher voll; die Meldung nennt den Grund. |
| *In der letzten Stunde wurden … Exporte geschrieben, mehr schreibt die Integration nicht.* | Die Integration schreibt nur eine begrenzte Zahl von Exporten pro Stunde. Versuche es später erneut. |
| *Dieses Turnierformat braucht … bis … Spieler, nicht …* | Nenne so viele Spieler, wie das Format nimmt, jeden mit eigenem Namen: drei bis acht bei jeder gegen jeden, sechs bis 32 mit Gruppen, sonst drei bis 32. |
| *… Spieler passen nicht in … Gruppen* | Wähle weniger Gruppen oder lass das Board sie wählen (*Turniergruppen* `0` für den Knopf *Turnier starten*), oder weniger Weiterkommende (*Turnier Weiter je Gruppe*), damit jede Gruppe drei bis acht Spieler hat und mehr, als weiterkommen. |
| *Es läuft kein Turnier.* | *Nächstes Turniermatch* und *Turnier beenden* brauchen ein laufendes Turnier. |
| *Es läuft bereits ein Turnier.* | Es läuft immer nur ein Turnier. Beende es, bevor du ein neues startest. |
| *Das Turnier ist vorbei.* | Das Finale ist gespielt; *Nächstes Turniermatch* hat kein Match mehr. Beende das Turnier oder starte ein neues. |
| *… spielt im Turnier mit.* | Einen Spieler des laufenden Turniers kannst du nicht löschen. Beende zuerst das Turnier. |
| *Das Turniermatch … gegen … läuft noch.* | *Nächstes Turniermatch* wartet auf die Pause zwischen zwei Matches. Spiel das Match zu Ende oder beende das Turnier. |

### HACS aktualisiert nicht auf 2.0

HACS meldet beim Update von 1.x *No manifest.json file found 'custom_components/autodarts/manifest.json'*. Seit 2.0 liegt die Integration in `custom_components/homedarts`, und ein laufendes HACS behält den Ordner, den es beim Start von Home Assistant gefunden hat. Starte Home Assistant neu, aktualisiere in HACS noch einmal und starte noch einmal neu; dann [steigst du um](new-name.de.md#umsteigen) wie gewohnt.

### Automationen laufen nach dem Wechsel zu HomeDarts nicht mehr

Seit 2.0 beginnen die Aktionen der Integration mit `homedarts.`, etwa `homedarts.start_game`, und ihre Karten mit `custom:homedarts`. Sobald HomeDarts [deine Boards übernommen hat](new-name.de.md), gibt es die Aktionen des alten Namens, etwa `autodarts.start_game`, nicht mehr:

- **Automationen und Skripte**, die sie aufrufen, schlagen fehl, weil Home Assistant die Aktion nicht findet. Ersetze `autodarts.` durch `homedarts.`; die Reparatur *Einige Automationen, Skripte oder Dashboards nutzen noch den alten Namen* listet sie auf.
- **Dashboards in YAML** zeigen *Custom element doesn't exist: autodarts-card*. Ersetze in den Typen der Karten und der Strategie `custom:autodarts` durch `custom:homedarts` und `board_style: autodarts` durch `board_style: flat`.
- **Auslöser und Bedingungen mit Entitäten** funktionieren weiter: Die Entitäts-IDs bleiben, etwa `event.autodarts_board_ereignisse`.

Die Details stehen unter [Was du selbst änderst](new-name.de.md#was-du-selbst-änderst).

### Keine Echtzeitaktualisierung

*Echtzeitverbindung* ist aus, und Änderungen erscheinen mit etwa 2 Sekunden Verzögerung:

- Ein Proxy oder eine Firewall zwischen Home Assistant und dem Board blockiert möglicherweise WebSocket-Verbindungen auf Port 3180. Antwortet das Board auf Lesevorgänge, bleiben seine Echtzeitereignisse aber etwa eine halbe Minute aus, steht einmal eine Warnung im Protokoll.
- Nach einem Neustart des Board Managers verbindet sich die Integration neu, sobald ein Lesevorgang das Board wieder erreicht, sonst spätestens nach 60 Sekunden.

### Darts werden im Training falsch gezählt

- Darts, die beim Start von Home Assistant im Board stecken, werden absichtlich nicht gezählt.
- Wird eine Entnahme nicht erkannt und folgen neue Darts, schließt die Integration die vorige Aufnahme und zählt die neuen Darts.
- Reißt die Verbindung während einer Aufnahme ab, geht die Aufnahme weiter, wenn das Board danach noch ihre Darts zeigt. Wurden die Darts inzwischen gezogen, wird die Aufnahme mit den Darts abgeschlossen, die vor der Unterbrechung bekannt waren; Darts, die danach noch während der Unterbrechung geworfen wurden, zählen nicht.
- Das Training zählt, was das Board erkennt. Korrigierst du ein falsch erkanntes Feld in Autodarts, übernimmt das Training die Korrektur nur, wenn das Board sie meldet.

Neu beginnen: **Neue Trainingssession** oder *Neue Session* auf der Trainingskarte. Soll nichts mehr gezählt werden, schalte **Trainingssession** und *Sessions automatisch starten* aus.

### Nach einer Entnahme zählen keine Darts

Der Status bleibt *Darts werden entnommen*, obwohl das Board leer ist, und neue Darts zählen nicht. Board Manager 2.0.2 beginnt manchmal direkt nach einer Entnahme eine neue und bleibt darin hängen, wie ein Spieler berichtet hat. Solange *Hängende Entnahme lösen* an ist, [setzt die Integration das Board](entities.de.md#eine-entnahme-die-das-board-nie-beendet) nach zehn Sekunden zurück, und es geht weiter; das Protokoll nennt jedes Zurücksetzen auf Stufe Info.

- Um das Board sofort zu lösen, drücke **Erkennung zurücksetzen**.
- Hängt das Board nach drei Versuchen noch, stoppe und starte die Erkennung oder starte den Board Manager neu.

### Keine Darts, weil das Board eine Hand sieht

*Hand erkannt* bleibt auf Board Manager 2.1 an, obwohl niemand am Board ist, und kein Dart zählt, auch nach einer Kalibrierung. Bei einem echten Board begann das, als sein Lichtring bei laufender Erkennung eingeschaltet wurde; das Licht ist die wahrscheinliche Ursache, aber nicht bewiesen. Siehe [Eine Hand, die das Board ständig sieht](entities.de.md#eine-hand-die-das-board-ständig-sieht).

- Stoppe und starte die Erkennung, mit dem Schalter *Erkennung* oder indem du den Hinweis *Autodarts-Board sieht ständig eine Hand* bestätigst. Solange *Hängende Entnahme lösen* an ist, tut die Integration das nach einer Minute selbst, wenn kein von ihr geführtes Spiel läuft und kein Dart im Board steckt. Ein Match auf play.autodarts.io hält sie nicht auf.
- Schaltet eine Routine das Licht des Boards, schalte es, bevor die Erkennung startet, oder [starte die Erkennung danach neu](automations.de.md#die-erkennung-nach-dem-licht-neu-starten).

### Eine Kamera wird als gestört gemeldet

*Kamerastörung* geht an, wenn eine Kamera bei laufender Erkennung 15 Sekunden lang keine Bilder liefert. Prüfe Kabel und USB-Anschluss der Kamera und ob sie im Board Manager erscheint. Oft hilft auch eine neue Kalibrierung.

### Karte fehlt oder ist veraltet

- **Custom element doesn't exist: homedarts-card:** Starte Home Assistant nach der Installation neu und lade die Seite neu.
- **Nichts oder *Custom element doesn't exist* bei Home Assistant Cast:** Starte Home Assistant nach der Installation oder einem Update der Integration einmal neu und streame dann noch einmal. *Einstellungen → Dashboards → ⋮ → Ressourcen* listet `homedarts-strategy.js` und `homedarts-card.js` unter `/homedarts/`, im Ordner der Version; mit Ressourcen in YAML trägst du die [beiden Zeilen](cards.de.md#home-assistant-cast) selbst ein.
- **Alte Kartenversion nach einem Update:** Lade die Seite neu. In der Companion-App hilft *Einstellungen → Companion-App → Fehlerbehebung → Frontend-Cache zurücksetzen*.
- **Der Aufnahmeverlauf ist leer:** Er kommt aus dem Recorder und braucht daher die Integration `recorder` (standardmäßig aktiv). Er füllt sich mit abgeschlossenen Aufnahmen.

### Momente von Online-Matches kommen nicht an

Gehe die [Online-Brücke](online-matches.de.md) Schritt für Schritt durch und beobachte den Sensor *Letztes Ereignis der Online-Brücke*:

- **Kein Sensor:** Die Brücke ist aus. Schalte sie in den Optionen des Boards (**Konfigurieren**) ein.
- **Die Adresse selbst:** Öffne sie mit angehängtem `?event=gameon` in einem Browser in deinem Heimnetz. Ändert sich der Sensor nicht, erreicht der Browser Home Assistant unter dieser Adresse nicht: Nimm die Adresse, mit der du Home Assistant öffnest. Eine Adresse von außerhalb deines Heimnetzes braucht *Aufrufe von außerhalb deines Heimnetzes annehmen*.
- **Nur von der Autodarts-Seite nicht:** Prüfe, ob die WLED-Funktion von Tools for Autodarts an ist, die Effekte aktiviert sind und die Autodarts-Seite offen ist. Die Entwicklertools des Browsers (F12, *Konsole*) zeigen Aufrufe, die der Browser blockiert hat, etwa als *Mixed Content*; siehe [gemischte Inhalte](online-matches.de.md#grenzen).
- **Nur manche Momente:** Einen Trigger, den die Brücke nicht kennt, nennt einmalig eine Warnung im Log von Home Assistant. Tools for Autodarts spielt pro Trigger einen Effekt, entferne also andere Effekte mit demselben Trigger.

## Von Autodarts 1.x auf 2.x

Ein Spieler hat einen Board-PC mit Ubuntu 24.04 und drei Kameras von Autodarts 1.x auf Autodarts Desktop 2.0.2 umgestellt und berichtet, was sich dabei geändert hat. Andere Systeme und Versionen können sich anders verhalten. Die Integration selbst braucht keine Änderung: Sie erkennt Board Manager 2 von selbst, lädt neu und ergänzt die Entitäten von Board Manager 2, und Training, Spiele und Statistiken bleiben erhalten ([Board-Manager-Generationen](how-it-works.de.md#board-manager-generationen)).

| Was du bemerkst | Ursache und Lösung |
| --- | --- |
| Die Erkennung startet nicht, und das Protokoll von Autodarts meldet, dass keine Kamera streamt | 2.x übernimmt die Anmeldung des Boards, aber nicht seine Liste der Kameras. Wähle die Kameras neu aus, in derselben Reihenfolge wie vorher: Die Kalibrierung gehört zum Platz der Kamera, nicht zur Kamera. Kameras desselben Modells können dieselbe Seriennummer haben; der USB-Anschluss, an dem sie stecken, unterscheidet sie. |
| Die Erkennung startet nicht, solange der Board-PC offline ist | Nach jedem Start wartet 2.x, bis es den Autodarts-Server einmal erreicht hat. Danach antwortet das Board im lokalen Netz, und die Integration arbeitet wie vorher. |
| 2.x kann Port 3180 beim ersten Start nicht öffnen | Der alte Board Manager oder ein Browser-Tab, der noch mit ihm verbunden ist, kann den Port kurz belegen. Schließe den Tab und starte die App neu, sobald der Port frei ist. |
| Nach einer Entnahme zählen keine Darts | Board Manager 2.0.2 bleibt manchmal bei leerem Board in einer Entnahme hängen. Ist [*Hängende Entnahme lösen*](entities.de.md#eine-entnahme-die-das-board-nie-beendet) an, löst die Integration sie nach zehn Sekunden, siehe [Nach einer Entnahme zählen keine Darts](#nach-einer-entnahme-zählen-keine-darts). |
| Die Erkennung stoppt nach einigen Minuten ohne Darts | Das ist der Standby des Boards. [*Kamera-Standby*](entities.de.md#board-einstellungen) stellt die Minuten ein, 5, 10, 15, 30 oder 60, und der Schalter [*Erkennung*](entities.de.md#steuerung) startet die Erkennung wieder, auch aus einer Automation. |

**Home Assistant mit HTTPS:** Die Karten dieser Integration zeigen, was Home Assistant weiß, und rufen seine Aktionen auf; mit dem Board verbinden sie sich nie selbst. Ein Browser, der Home Assistant über HTTPS öffnet, blockiert deshalb nichts von ihnen, mit 1.x wie mit 2.x. Nur die Integration spricht mit dem Board, über HTTP im lokalen Netz.

## Diagnose und Logs

### Diagnosedaten herunterladen

**Einstellungen → Geräte & Dienste → HomeDarts for Autodarts →** Menü des Boards (⋮) → **Diagnosedaten herunterladen**. Die Datei enthält:

- den Board-Zustand und die Zusammenfassung der Einstellungen;
- unter `local_readings` die Bewegung, ob die Kameras laufen, die Bildraten und die Last des Board-PCs;
- die Board-Manager-Generation, die Verbindungen und das Leseintervall;
- das Übungsspiel mit seinen Regeln und ob gerade ausgebullt wird;
- die Zahl der gespeicherten Sessions, Bestleistungen, Spielerprofile, Matches und Darts aufs Double;
- unter `connection` den Verlauf der Verbindung: verpasste Lesevorgänge in Folge, die Art des letzten Fehlers, das letzte erfolgreiche Lesen, wie lange das Board schon fehlt, die Dauer des letzten Lesens, Abfragen mit unbekanntem Format und für die Echtzeitverbindung Verbindungsaufbauten, fehlgeschlagene Versuche, den aktuellen Abstand bis zum nächsten Versuch, den Grund des letzten Abbruchs und die Zahl übersprungener Nachrichten, außerdem unter `stuck_takeout`, ob hängende Entnahmen gelöst werden, ob gerade eine abgewartet wird und wie viele Zurücksetzungen das Board angenommen oder abgelehnt hat, und unter `stuck_hand`, ob eine Hand als hängend gilt, ob gerade eine abgewartet wird und wie viele Neustarts das Board angenommen oder abgelehnt hat, mit dem letzten.

Board-ID, Board-Name, Adressen und Spielernamen sind geschwärzt; Fehlermeldungen sind nicht enthalten.

### Debug-Protokollierung

Wähle auf der Integrationsseite **Debug-Protokollierung aktivieren**, stelle das Problem nach und wähle **Debug-Protokollierung deaktivieren**. Home Assistant lädt dann das Protokoll herunter. Alternativ in `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.homedarts: debug
```

### Fehler melden

Öffne ein [Issue](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose) mit:

- Home-Assistant-Version und Board-Manager-Version;
- den Diagnosedaten;
- den passenden Protokollzeilen.

Sicherheitsprobleme meldest du bitte vertraulich, wie in [SECURITY.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SECURITY.md) beschrieben.

Englisch und Deutsch sind beide willkommen. Nach wenigen Minuten setzt der Issue-Assistent die Labels und schreibt eine Erstanalyse: eine Zusammenfassung, die wahrscheinliche Ursache oder die passende Stelle der Dokumentation, verwandte Issues und, wenn nötig, Rückfragen. Der Assistent nutzt derzeit Claude, eine KI von Anthropic; er liest den Text des Issues und das öffentliche Repository und kann sich irren. Der Maintainer liest jedes Issue ebenfalls und entscheidet.

- **Rückfragen** markieren das Issue als wartend auf dich. Antworte als Kommentar oder indem du das Issue bearbeitest. Ohne Antwort folgt nach 15 Tagen eine Erinnerung, nach 30 Tagen wird das Issue geschlossen; eine Antwort öffnet es wieder.
- **Ein wahrscheinliches Duplikat** eines offenen Issues bekommt einen Hinweis und wird 3 Tage später geschlossen, damit alles an einer Stelle bleibt. Geht es um etwas anderes, schreib einen Kommentar oder reagiere auf den Hinweis mit 👎, dann bleibt es offen.
- **Ein Fix** auf `main` markiert das Issue mit `fixed-in-next-release`. Es bleibt offen, bis ein Release den Fix ausliefert, und wird dann mit einem Link auf das Release geschlossen. Besteht das Problem nach dem Update weiter, schreib innerhalb von 30 Tagen einen Kommentar, dann wird das Issue wieder geöffnet.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/issue-lifecycle-dark.png">
  <img src="images/de/issue-lifecycle-light.png" alt="Lebenslauf eines Issues: Labels und KI-Erstanalyse; fehlen Informationen, wartet es mit needs-info auf den Melder, mit einer Erinnerung an Tag 15 und dem Schließen an Tag 30, und eine Antwort gibt es an den Maintainer oder öffnet es wieder; ein sicheres Duplikat bekommt einen Hinweis und wird an Tag 3 geschlossen, wenn niemand kommentiert oder mit Daumen runter reagiert. Ein gemergter Fix markiert es mit fixed-in-next-release; das Release schließt es mit einem Link, und ist es noch nicht behoben, geht es zurück an den Maintainer." width="640">
</picture>
