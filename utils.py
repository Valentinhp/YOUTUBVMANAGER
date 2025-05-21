import isodate

def iso8601_to_seconds(duration_str: str) -> int:
    """
    Convierte una cadena ISO 8601 ('PT5M30S') a segundos.
    Si falla, devuelve 0.
    """
    try:
        dur = isodate.parse_duration(duration_str)
        return int(dur.total_seconds())
    except Exception:
        return 0
