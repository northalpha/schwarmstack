from django import template

register = template.Library()


@register.filter
def dauer(seconds) -> str:
    """Sekunden als „3 h 30 min“ (oder „45 s“)."""
    total = round(float(seconds or 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    parts = []
    if hours:
        parts.append(f"{hours} h")
    if minutes:
        parts.append(f"{minutes} min")
    if secs and not hours:
        parts.append(f"{secs} s")
    return " ".join(parts) or "0 s"


@register.filter
def mib(value) -> str:
    """Bytes als MiB oder GiB mit Komma (deutsch)."""
    value = float(value or 0)
    if value >= 1024**3:
        return f"{value / 1024**3:.2f} GiB".replace(".", ",")
    return f"{value / 1024**2:.0f} MiB"
