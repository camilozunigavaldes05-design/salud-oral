import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage


def _almacenamiento():
    return FileSystemStorage(location=settings.ALMACENAMIENTO_PRIVADO)


def guardar_imagen(paciente_id, contenido, extension):
    nombre = f"pacientes/{paciente_id}/{uuid.uuid4().hex}.{extension}"
    return _almacenamiento().save(nombre, ContentFile(contenido))


def leer_imagen(nombre):
    with _almacenamiento().open(nombre, "rb") as archivo:
        return archivo.read()


def eliminar_imagen(nombre):
    if nombre:
        _almacenamiento().delete(nombre)
