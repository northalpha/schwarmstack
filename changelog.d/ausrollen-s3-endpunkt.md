- Ausrollen prüft `S3_ENDPOINT_URL` vorab: Ohne `https://` bricht das Skript ab, bevor etwas
  auf den Host geht. Warum: boto3 lehnt einen Endpunkt ohne Schema ab, und das fiel bisher erst
  nach dem Neustart über `/healthz` auf.
