- CORS des Buckets bei jedem Deploy: `auf-dem-host.sh` ruft `s3_bucket_setup` mit der Domain
  der Umgebung auf. Der Befehl wandelt Umlaut-Domains in Punycode um und prüft die Freigabe
  danach per CORS-Preflight wie ein Browser; greift sie nicht, bricht der Deploy vor der
  Migration ab. Warum: Mit fehlender oder als Unicode gesetzter Herkunft scheiterte jeder
  Upload im Browser mit „Network error during S3 request“, und das fiel erst beim Hochladen auf.
