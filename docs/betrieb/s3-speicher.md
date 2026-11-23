# S3-Speicher einrichten

Master gehen per Multipart-Upload direkt aus dem Browser in den Bucket (ADR 0005). Schwarmstack stellt nur signierte Links aus und liest danach Größe und Header. Damit das funktioniert, braucht der Bucket eine CORS-Freigabe für die eigene Domain und sollte unvollständige Uploads selbst abräumen.

## Umgebungsvariablen

| Variable | Produktion (Beispiel) | Bedeutung |
|---|---|---|
| `STORAGE_BACKEND` | `s3` | `local` nur für Entwicklung und Tests |
| `S3_ENDPOINT_URL` | `https://fsn1.your-objectstorage.com` | Endpunkt des Anbieters (Standort des Buckets) |
| `S3_BUCKET` | `schwarmstack-prod` | eigener Bucket je Umgebung |
| `S3_REGION` | `fsn1` | Region bzw. Standort |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | – | als GitHub-Environment-Secret (ADR 0001), nie im Repo |
| `S3_ADDRESSING_STYLE` | `virtual` | `path` nur für Garage lokal |
| `UPLOAD_LINK_SECONDS` | `900` | Gültigkeit eines signierten Links |

Staging bekommt einen eigenen Bucket und eigene Schlüssel.

## Bucket einrichten

Einmal je Bucket, mit denselben Umgebungsvariablen wie die App:

```bash
uv run python src/manage.py s3_bucket_setup --origin https://upload.dzvf.de
```

Für Staging entsprechend `--origin https://upload.northalpha.de`. Der Befehl setzt:

- **CORS:** Herkunft nur die eigene Domain; Methoden `GET`, `PUT`, `POST`, `DELETE`; alle Header erlaubt; **`ETag` freigegeben**. Ohne freigegebenen `ETag` kann Uppy die Teile nicht abschließen.
- **Lifecycle:** Unvollständige Multipart-Uploads werden nach 7 Tagen abgeräumt.

Prüfen, ob beides gesetzt ist (der Anbieter sollte beides kennen; falls die Lifecycle-Regel abgelehnt wird, meldet der Befehl einen Fehler):

```bash
aws s3api get-bucket-cors --bucket schwarmstack-prod --endpoint-url https://fsn1.your-objectstorage.com
```

```bash
aws s3api get-bucket-lifecycle-configuration --bucket schwarmstack-prod --endpoint-url https://fsn1.your-objectstorage.com
```

## Lokal und in CI: Garage

`scripts/garage.sh start` startet Garage als S3-kompatiblen Container mit festen Testschlüsseln, legt den Bucket `schwarmstack-test` an, setzt CORS und gibt die Umgebungsvariablen aus. Damit laufen die Vertragstests und der Browser-Durchlauf auch gegen echtes S3:

```bash
set -a; eval "$(scripts/garage.sh start)"; set +a
```

```bash
uv run pytest
```

Ohne gestartetes Garage werden diese Tests übersprungen; die Vertragstests laufen dann gegen die lokale Platte und `moto`.
