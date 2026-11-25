import logging

from .models import Auditoria

logger = logging.getLogger(__name__)

OK = "OK"
FALLIDO = "FALLIDO"
BLOQUEADO = "BLOQUEADO"
RECHAZADO = "RECHAZADO"


def registrar(usuario, accion, recurso, resultado=OK):
    if usuario is None or not getattr(usuario, "pk", None):
        return None
    try:
        return Auditoria.objects.create(
            usuario=usuario,
            accion=accion[:60],
            recurso=recurso[:120],
            resultado=resultado[:20],
        )
    except Exception:
        logger.exception("No se pudo registrar la auditoría de %s", accion)
        return None
