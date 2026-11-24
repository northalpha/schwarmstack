- ADR 0009 zum Upload-Ablauf (#41): Der Browser legt den Multipart-Upload an, der Server
  signiert jede S3-Anfrage einzeln und übernimmt die Upload-ID des Browsers. Tests halten fest,
  dass eine falsche Upload-ID nur den eigenen Master trifft. Warum: Die Umsetzung wich von der
  Spec ab, ohne dass die Entscheidung und ihre Folgen irgendwo festgehalten waren.
