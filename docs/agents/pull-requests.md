# Pull Requests

Jede Session, die Code oder Doku ändert, legt am Ende einen Pull Request an und wartet auf die CI. Das gilt als ausdrücklicher Auftrag. Gemerged wird nie von der Session, sondern erst nach dem Review durch die Betreiber.

## Ablauf

1. **Vorher prüfen:** `scripts/pruefen.sh` (Cloud: ggf. `dockerd &>/tmp/dockerd.log &`, sonst `--schnell` und im Bericht sagen, dass es so war).
2. **Pushen** auf den eigenen Branch, nie auf `main`.
3. **PR gegen `main` anlegen.** Der Text folgt dem Skill `pr`. Wenn die Session ein Issue ganz erledigt (auch bei `/implement`), steht immer `Closes #<Issue>` im PR-Text (bei einem Bug `Fixes #<Issue>`), in einer eigenen Zeile; fehlt es, schließt der Merge das Issue nicht. Bleibt ein Rest offen, steht er im PR-Text, und das Issue bleibt offen.
4. **PR abonnieren** (`subscribe_pr_activity`) und den Turn beenden. Nicht pollen, nicht schlafen: Ein Ereignis weckt die Session.
5. **Auf die CI warten** und jedes Ergebnis prüfen: `test` und `image` müssen grün sein, ebenso `installer`, wenn er läuft (nur bei Änderungen an `deploy/` und am `Dockerfile`). CodeQL meldet Funde als Code-Scanning-Alerts des PR, nicht als roten Job: auch bei grünem `analysieren` die Alerts lesen (`gh api repos/northalpha/schwarmstack/code-scanning/alerts -X GET -f ref=refs/pull/<nr>/merge -f state=open`). Übersprungene Jobs (`staging`, `production`, `von-hand`, ggf. `installer`) sind in Ordnung.
6. **Melden**, sobald die CI grün und der PR konfliktfrei ist: Link, was geändert wurde, was nur lokal und was in der CI lief. Danach nicht mergen und auf das Review warten.

## Wenn die CI rot ist

- Log lesen (`get_job_logs`), Ursache finden, beheben, pushen. Das Beheben ist Teil der Aufgabe.
- Kein Test wird übersprungen, deaktiviert oder abgeschwächt, um grün zu werden.
- Kein leerer Commit und kein Schließen und Öffnen des PR, um die CI neu anzustoßen. Ein Job darf einmal erneut laufen; ein „Flake“ ist keine Ursache.
- Ist der Fehler auf `main` ebenfalls rot oder betrifft er etwas, das der PR nicht berührt, im PR einmal sagen, warum, und die Betreiber fragen.

## Konflikte und fremde Änderungen

- Konflikt mit `main`: `main` in den Branch mergen. Kein Rebase, kein Force-Push, auch nicht auf dem eigenen Branch, wenn schon ein PR offen ist.
- Mehrere Sessions laufen parallel. Vor dem Anlegen des PR `git fetch origin main` und prüfen, ob `main` sich seit dem Start bewegt hat. Die CI läuft auf dem Merge-Stand von PR und `main`, nicht auf dem Branch allein.
- Tests dürfen keine Werte fest annehmen, die ein anderer PR ändern kann (z. B. die aktuelle `CONSENT_TEXT_VERSION`). Den Wert aus den Settings lesen.

## Review

Review-Kommentare: kleine Wünsche umsetzen und auf dem Thread antworten, größere Änderungen vorschlagen statt einfach pushen. Genehmigen und mergen tun nur die Betreiber.
