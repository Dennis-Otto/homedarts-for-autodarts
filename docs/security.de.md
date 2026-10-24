---
description: "Wie HomeDarts deine Daten und dein Board schützt: was sie schützt, wem sie vertraut, welche Bedrohungen sie abwehrt und welche Risiken bleiben."
---

# Sicherheit

[← Dokumentation](README.de.md) · [English](security.md)

Diese Seite erklärt, wie die Integration deine Daten und dein Board schützt, wem sie vertraut und welche Risiken bleiben. Sicherheitslücken meldest du bitte vertraulich, wie in [SECURITY.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SECURITY.md) beschrieben.

## Was geschützt wird

| Schutzgut | Wo es liegt | Schutz |
| --- | --- | --- |
| API-Schlüssel des Boards, TLS-Schlüssel, Kamerapfade | Konfiguration des Board Managers | Werden direkt beim Lesen verworfen; nie gespeichert, protokolliert, angezeigt oder in Diagnosedaten übernommen |
| Board-ID, Board-Adresse | Integrationseintrag in Home Assistant | In Diagnosedaten geschwärzt; der Verbindungsverlauf in den Diagnosedaten enthält Zähler, Fehlerarten und Dauern, nie Adressen oder Fehlermeldungen |
| Trainingssessions, Übungsspiele und Turniere, Bestleistungen, Spielernamen und -profile mit direkten Vergleichen, Match-Verlauf, Doppelanalyse, Fortschritt samt Dart-Positionen, Erfolgen und verknüpften Personen, Wochenbericht und Trainingskalender | `.storage` von Home Assistant ([gespeicherte Daten](how-it-works.de.md#gespeicherte-daten)) | Nur lokal; wird mit der Integration gelöscht; Spielernamen sind in Diagnosedaten geschwärzt |
| Exporte mit Spielernamen | Standardmäßig `homedarts/exports` im Medienordner; auf Wunsch `www`, ein anderer Medienordner oder ein Ordner aus `allowlist_external_dirs` | Nur von Administratoren und Automationen geschrieben, höchstens 20 pro Stunde; nur in Ordner, in die Home Assistant schreiben lässt, nie in versteckte; unerratbare Dateinamen; Downloads nur für Administratoren |
| Steuerung des Boards | Board-Manager-API | Aktionen nur auf Wunsch eines Nutzers oder einer Automation, genau einmal gesendet |
| Adresse der Online-Brücke (optional) | Optionen des Integrationseintrags in Home Assistant | Ein zufälliges Geheimnis aus 64 Hexadezimalzeichen, nur in den Optionen angezeigt; von der Integration nie protokolliert und nie in Diagnosedaten; in den Optionen durch eine neue ersetzbar, die die alte sofort abschaltet, auch während die Brücke aus ist |

## Vertrauensgrenzen

```text
 Board-PC                      Home Assistant                    Internet
┌────────────────────┐        ┌──────────────────────────┐       ┌──────────────────────┐
│ Board Manager      │  LAN   │ HomeDarts                │ HTTPS │ Suchdienst von       │
│ Port 3180, ohne    ├───────►│ prüft jede Antwort       ├──────►│ Autodarts, nur bei   │
│ Anmeldung          │        │ Dashboard-Karten         │       │ der Board-Suche      │
└────────────────────┘        └──────────────────────────┘       └──────────────────────┘
```

1. **Board Manager → Integration.** Die lokale API hat keine Anmeldung. Die Integration behandelt jede Antwort als nicht vertrauenswürdig: Typen, Wertebereiche und Strukturen werden geprüft, bevor ein Wert eine Entität erreicht. Unerwartete Daten erscheinen als *unbekannt*, statt Fehler auszulösen. Versionsnummern müssen wie Versionsnummern aussehen, Texte mit mehr als 255 Zeichen erscheinen als unbekannt, und Echtzeitnachrichten werden auf dieselben bekannten Werte reduziert wie gelesene Antworten. Eine Antwort in unbekanntem Format wird einmal protokolliert; antwortet eine nötige Abfrage weiter so, erscheint ein Reparaturhinweis. HTTP 401 oder 403 wird als verweigerter Zugriff gemeldet; die Integration sendet dem Board nie Zugangsdaten.
2. **Integration → Dashboard.** Die Karten zeigen Board-Daten im Browser. Jeder Text vom Board oder aus der Entitätsverwaltung wird maskiert, Zahlen werden geprüft, bevor sie zu SVG-Geometrie werden.
3. **Integration → Internet.** Im lokalen Betrieb verlässt nichts das Heimnetz. *Boards im Netzwerk suchen* fragt einmalig und nur auf Wunsch den öffentlichen Suchdienst von Autodarts; von sich aus fragt die Integration ihn nie. Eine Verknüpfung mit der Autodarts-Cloud und eine Autodarts-Anmeldung gibt es nicht ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch). Auch die Übernahme der Boards, die unter dem früheren Namen der Integration, Autodarts, eingerichtet sind, geschieht in Home Assistant ([wie](how-it-works.de.md#vom-früheren-namen-übernommen)).
4. **Netzwerk → Integration (mDNS).** Jedes Gerät im Netzwerk kann ein Autodarts-Board melden. Die Integration spricht nur die Adressen an, von denen die Meldung kommt, nie Loopback-, Link-local- oder Multicast-Adressen und nie eine Adresse, die nur in den Eigenschaften der Meldung steht. Ein eingerichtetes Board zieht nie von selbst um: Antwortet es unter seiner eingerichteten Adresse nicht mehr mit seiner Board-ID, bietet ein Reparaturhinweis die neue Adresse an, und der Eintrag zieht erst um, wenn du bestätigst, nachdem das Board dort erneut erkannt wurde.
5. **Browser → Integration (Online-Brücke, optional).** Standardmäßig aus. Eingeschaltet nimmt Home Assistant die Aufrufe der Browser-Erweiterung Tools for Autodarts unter einer geheimen Webhook-Adresse an, standardmäßig nur aus dem Heimnetz. Die Integration nimmt nur die bekannten Trigger an, Felder begrenzter Länge und höchstens 20 Aufrufe pro Sekunde und 120 pro Minute. Ein Aufruf kann nur ein Board-Ereignis `online_*` auslösen: Er steuert nie das Board und ändert keine gespeicherten Daten. [Online-Matches](online-matches.de.md).

## Bedrohungen und Gegenmaßnahmen

| Bedrohung | Gegenmaßnahme | Nachweis |
| --- | --- | --- |
| Geheimnisse des Boards gelangen nach Home Assistant | Die Konfiguration wird direkt nach dem Lesen auf eine Liste erlaubter Felder reduziert; Antworten auf Schreibzugriffe werden verworfen | Tests prüfen, dass der API-Schlüssel nie in Entitäten, Diagnosedaten oder Logs erscheint, auch im Docker-End-to-End-Test |
| Fehlerhafte oder bösartige Board-Daten bringen Integration oder Karten zum Absturz | Prüfung jeder Nachricht; Property-based Tests mit Hypothesis (Trainings-Engine) und fast-check (Karten) mit Tausenden Zufallseingaben | `tests/test_training_properties.py`, `tests/frontend/properties.test.js` |
| Skripteinschleusung über Board- oder Gerätenamen in den Karten | Jeder eingefügte Text wird maskiert; kein `innerHTML` mit unmaskierten Daten | fast-check-Eigenschaft „maskierter Text enthält nie Markup“; DOM-Test, dass ein Spieler namens `<img onerror>` als Text erscheint |
| Ein falsches Board unter der eingerichteten Adresse zeigt oder steuert fremde Daten | Die Board-ID wird bei Board Manager 2 bei jedem Lesen geprüft, bei Board Manager 1 beim Start und mindestens alle 30 Sekunden; bei Abweichung sind die Entitäten nicht verfügbar, seine Echtzeitnachrichten werden ignoriert, und ein Reparaturhinweis erscheint | `tests/test_local_setup.py`, `tests/test_issues_and_metadata.py`, `tests/test_realtime.py` |
| Ein Gerät im Netzwerk meldet sich als Board | Nur die meldenden Adressen werden angesprochen; ein Board, das unter seiner eingerichteten Adresse noch antwortet, zieht nie um; sonst fragt erst ein Reparaturhinweis, und beim Bestätigen wird die Board-ID erneut geprüft | `tests/test_discovery.py` |
| Jemand erfährt die Adresse der Online-Brücke und sendet falsche Momente | Standardmäßig aus; ohne Freigabe nur Aufrufe aus dem Heimnetz; ein Geheimnis aus 64 zufälligen Hexadezimalzeichen; nur bekannte Trigger, begrenzte Längen, höchstens 20 Aufrufe pro Sekunde und 120 pro Minute; nur Ereignisse; eine neue Adresse in den Optionen, die die alte sofort ersetzt, auch beim Ausschalten der Brücke | `tests/test_online.py` |
| Viele Zuschauer überlasten den Board-PC mit Kamerastreams | Pro Kamera werden höchstens zwei Livestreams weitergegeben; weitere Zuschauer bekommen Standbilder | `tests/test_camera_stream.py` |
| Fehlerhafte Board-Daten oder ein Fehler in einer Spielregel trennen die Verbindung | Fehler in Training und Spielen bleiben begrenzt und werden einmal protokolliert; schnell wechselnde Werte lösen keine Spiellogik aus; Lesevorgänge überschneiden sich nie | `tests/test_connection.py` |
| Ein Export schreibt, wo er nicht soll, überschreibt eine Datei oder füllt die Festplatte | Nur Administratoren und Automationen exportieren; der Ordner wird vor dem Schreiben aufgelöst, sodass weder `..` noch ein symbolischer Link woandershin führt, und er muss einer sein, in den Home Assistant schreiben lässt (`www`, die Medienordner, `allowlist_external_dirs`); versteckte Ordner und Steuerzeichen werden abgelehnt; höchstens 20 Exporte pro Stunde; jeder Export ist eine neue Datei | `tests/test_reports_setup.py` |
| Ein Highlight-Foto schreibt, wo es nicht soll, oder überschreibt eine Datei | Nur Administratoren und Automationen speichern Highlight-Fotos; für den Ordner gelten die Regeln der Exporte; ein Dateiname behält von Spieler und Bezeichnung nur sichere Zeichen; jedes Foto ist eine neue Datei, und eine abgebrochene wird gelöscht | `tests/test_highlights.py` |
| Ein Voice-Pack schreibt oder löscht, wo es nicht soll, oder ersetzt ein aufgenommenes Pack | Nur Administratoren und Automationen erzeugen Voice-Packs; für den Ordner gelten die Regeln der Exporte; ein Pack-Name ist ein einfacher Ordnername, ohne `/` oder `..`; die Sounds werden in einen versteckten Ordner neben dem Pack aufgenommen, der nur ein Pack ersetzt, das die Integration selbst erzeugt hat (markiert mit `.homedarts-voice-pack`), unmittelbar davor erneut geprüft; immer nur ein Pack auf einmal | `tests/test_voices.py` |
| Die Übernahme vom früheren Namen ändert oder löscht, was ihr nicht gehört | Übernommen werden nur Einträge, die die Integration unter ihrem früheren Namen angelegt hat, nie die einer anderen Integration mit der Domain `autodarts`; die Übernahme löscht nur den Ordner `autodarts` in `custom_components`, dessen Manifest dieses Projekt nennt; Speicher, Einträge der Verwaltung und Medien ziehen innerhalb von Home Assistant um, ohne Anmeldung und ohne Verbindung ins Internet; eine Mediendatei, die schon da ist, bleibt | `tests/test_takeover.py` |
| Der Benutzer eines gemeinsamen Wandtablets löscht, benennt um, verknüpft oder exportiert die Daten der Spieler oder speichert, was eine Kamera sieht | `homedarts.delete_player`, `homedarts.rename_player`, `homedarts.link_player`, `homedarts.unlink_player`, `homedarts.export`, `homedarts.save_highlight` und `homedarts.generate_voice_pack` sind Aktionen für Administratoren, die Automationen weiterhin ausführen; nur Administratoren laden Exporte herunter | `tests/test_services.py`, `tests/test_reports_setup.py`, `tests/test_highlights.py` |
| Ein Spielername läuft in einer Tabellenkalkulation als Formel | CSV-Zellen, die wie eine Formel beginnen, bekommen einen Apostroph vorangestellt | `tests/test_reports_setup.py` |
| Eine Aktion läuft doppelt, etwa Neustart oder Zurücksetzen | Aktionen werden genau einmal gesendet und nie automatisch wiederholt | `tests/test_local_api.py` |
| Eine kompromittierte Abhängigkeit oder ein manipulierter Build | Abhängigkeiten per Hash, gepinnte Actions und Images, Dependabot, Dependency Review, CodeQL, Gitleaks, OpenSSF Scorecard | [Development](development.md#continuous-integration) |
| Eine kompromittierte Action, ein Paket oder ein Test eines Pull Requests schickt ein Token oder Daten aus einem Job der CI anderswohin | Harden-Runner sperrt jeden Host, den ein Job der projekteigenen Workflows nicht braucht; die Bots, die schreiben dürfen, erreichen nur GitHub und laufen ohne sudo und Docker; das Home Assistant der Tests ruft nichts im Internet auf | `tests/test_workflow_network.py`, `tests/test_e2e_offline.py`, [Entwicklung](development.de.md#netzwerk-der-jobs) |
| Ein manipuliertes Release | Release-Pakete tragen eine mit Sigstore signierte SLSA-Provenance | [Releases](releases.md#signed-release-packages) |

## Häufige Schwachstellen

Wie die Integration den Schwachstellen der [CWE Top 25](https://cwe.mitre.org/top25/) begegnet, die für sie zählen. CodeQL sucht bei jedem Pull Request im Python- und JavaScript-Code nach ihnen.

| Schwachstelle | Gegenmaßnahme |
| --- | --- |
| Cross-Site-Scripting (CWE-79) | Jeder Text vom Board, aus der Entitätsverwaltung oder von einem Spieler wird maskiert, bevor er zu HTML wird, und Zahlen werden geprüft, bevor sie zu SVG-Geometrie werden |
| Pfadmanipulation (CWE-22) | Exporte, Highlight-Fotos und erzeugte Voice-Packs lösen ihren Ordner vor dem Schreiben auf, sodass weder `..` noch ein symbolischer Link woandershin führt; die Kopien der Highlights liefern nur einfache Dateinamen von Fotos im Highlight-Ordner aus; Voice-Packs sind einfache Ordnernamen im Voice-Ordner |
| Unzureichende Eingabeprüfung (CWE-20) | Jede Antwort des Board Managers, jede Echtzeitnachricht und jeder Aufruf der Online-Brücke wird gegen bekannte Typen, Wertebereiche und Längen geprüft |
| Preisgabe vertraulicher Daten (CWE-200, CWE-532) | Der API-Schlüssel des Boards wird direkt beim Lesen verworfen und nie gespeichert, protokolliert oder angezeigt; die Diagnosedaten schwärzen Board-IDs, Adressen und Spielernamen |
| Fehlende Berechtigungsprüfung (CWE-862) | Aktionen, Downloads, Highlight-Kopien und die WebSocket-Befehle brauchen eine Anmeldung bei Home Assistant; Löschen, Neuverknüpfen und Exportieren der Daten von Spielern, das Speichern von Highlight-Fotos und das Erzeugen von Voice-Packs brauchen einen Administrator |
| Serverseitige Anfragefälschung (CWE-918) | Die Erkennung spricht nur die Adressen an, von denen eine Meldung kommt, nie Loopback-, Link-local- oder Multicast-Adressen |
| Unkontrollierter Ressourcenverbrauch (CWE-400) | Höchstens zwei Livestreams pro Kamera, 20 Exporte pro Stunde und für die Online-Brücke 20 Aufrufe pro Sekunde und 120 pro Minute |
| Formel-Injektion in Exporten (CWE-1236) | CSV-Zellen, die wie eine Formel beginnen, bekommen einen Apostroph vorangestellt |
| Befehls- und Code-Injektion (CWE-78, CWE-94) | Die Integration führt keine Befehle aus und wertet keinen Code aus, und zur Laufzeit hat sie keine Python-Abhängigkeiten |

## Grundsätze

- **Minimale Rechte:** GitHub-Workflows laufen mit Lese-Token, außer ein Job braucht mehr. Die Integration liest den Board Manager und schreibt nur, wenn du oder eine Automation es verlangt. Die Aktionen, die Daten der Spieler löschen, neu verknüpfen oder exportieren, sind Administratoren vorbehalten.
- **Sicher im Fehlerfall:** Unbekannte Daten werden zu *unbekannt*, ein unerreichbares Board macht Entitäten nicht verfügbar, und ein falsches Board zeigt nie seine Daten.
- **Lokal zuerst:** Die Integration spricht mit dem Board Manager in deinem Netzwerk und braucht kein Autodarts-Konto; die Board-Suche und die Online-Brücke sind optional.
- **Kleine Angriffsfläche:** Keine Python-Abhängigkeiten zur Laufzeit und keine eigenen offenen Ports. Was die Integration dem Webserver von Home Assistant hinzufügt:
  - die Dateien der Karten unter `/homedarts/`, etwa `/homedarts/<Version>/homedarts-card.js`, `homedarts-strategy.js` und die Texte jeder Sprache in `text/`, ohne Anmeldung ausgeliefert wie jede andere Frontend-Datei; sie enthalten Code und Texte, keine Daten;
  - die siebzehn Aktionen `homedarts.*`, die wie jede Aktion eine Anmeldung brauchen: `start_game`, `correct_dart`, `throw_dart`, `enter_visit`, `next_player`, `undo_visit`, `start_tournament`, `next_tournament_match`, `stop_tournament` und `voice_sound`, das nur liest, welche Sounds ein Voice-Pack hat, für alle Benutzer, `delete_player`, `rename_player`, `link_player`, `unlink_player`, `export`, `save_highlight` und `generate_voice_pack` für Administratoren, Automationen und von ihnen gestartete Skripte;
  - die Downloads der Exporte seit dem letzten Start unter `/api/homedarts/export/`, für Administratoren oder mit ihrem signierten Link, der nach einer Minute abläuft;
  - kleine Kopien der Highlight-Fotos unter `/api/homedarts/highlights/`, für angemeldete Benutzer wie die Fotos selbst; ausgeliefert werden nur einfache Dateinamen von Fotos im Highlight-Ordner;
  - den WebSocket-Befehl `homedarts/positions`, mit dem die Karten die Dart-Positionen lesen, für angemeldete Benutzer;
  - den WebSocket-Befehl `homedarts/voice_pack`, mit dem die Anzeigetafel die Sounds eines Voice-Packs auflistet (höchstens 10.000 Dateien werden angesehen), für angemeldete Benutzer;
  - nur solange die Online-Brücke an ist, eine geheime Webhook-Adresse.

## Verbleibende Risiken

- Die lokale API des Board Managers hat keine Anmeldung. Jeder, der Port 3180 in deinem Netzwerk erreicht, kann das Board steuern, mit oder ohne diese Integration. Betreibe den Board-PC in einem vertrauenswürdigen Netzwerk.
- Dateien im Ordner `www` liefert Home Assistant unter `/local/` ohne Anmeldung an jeden aus, der Home Assistant erreicht und den Dateinamen kennt. Exporte landen im Medienordner, der eine Anmeldung braucht, außer du wählst `www`; lösche Exporte in `www`, die du nicht mehr brauchst.
- Autodarts unterstützt die lokale API ab Board Manager 2 offiziell nicht mehr. Eine künftige Version kann sie ändern; die Integration erkennt die Generation und wird gegen beide getestet.
- Die Integration spricht unverschlüsseltes HTTP mit dem Board. Meldet Board Manager 2 einen HTTPS-Port, nutzt sie den gemeldeten HTTP-Port; TLS zum Board wird nicht unterstützt.
- Die Online-Brücke beruht darauf, dass ihre Adresse geheim bleibt. Wer sie kennt und Home Assistant erreicht, kann Online-Board-Ereignisse und die Automationen darauf auslösen, bis du eine neue Adresse erzeugst.
- Jeder im Netzwerk kann per mDNS ein Board melden. Home Assistant zeigt dann ein gefundenes Board an, das erst nach deiner Bestätigung hinzugefügt wird.
