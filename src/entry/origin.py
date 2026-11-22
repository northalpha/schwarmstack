from urllib.parse import urlparse


def origin_of(url: str) -> str | None:
    """Origin (https://host[:port]) einer Adresse, kleingeschrieben und ohne Standardport 443.

    Nur https zählt. Pfad, Query und Fragment werden ignoriert (der Browser schickt bei
    „strict-origin-when-cross-origin“ ohnehin nur den Origin).
    """
    try:
        parsed = urlparse(url or "")
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    origin = f"https://{parsed.hostname.lower()}"
    if port and port != 443:
        origin += f":{port}"
    return origin


def origin_allowed(referer: str, allowed_origins: list[str]) -> bool:
    origin = origin_of(referer)
    if origin is None:
        return False
    return origin in {o for o in (origin_of(a) for a in allowed_origins) if o}
