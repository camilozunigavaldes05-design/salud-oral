"""Versión de los archivos estáticos, para que el navegador no sirva copias viejas."""
from pathlib import Path

from django.conf import settings


def _calcular_version():
    """La fecha del archivo más nuevo de static/. Cambia sola al editar CSS o JS."""
    carpetas = getattr(settings, "STATICFILES_DIRS", [])
    marcas = [
        archivo.stat().st_mtime
        for carpeta in carpetas
        for archivo in Path(carpeta).rglob("*")
        if archivo.is_file()
    ]
    return str(int(max(marcas))) if marcas else "0"


# En desarrollo se recalcula en cada petición; en producción basta una vez.
_VERSION = None


def version_estaticos(request):
    global _VERSION
    if settings.DEBUG:
        return {"v_estaticos": _calcular_version()}
    if _VERSION is None:
        _VERSION = _calcular_version()
    return {"v_estaticos": _VERSION}
