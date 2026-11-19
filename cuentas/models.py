from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear_usuario(self, email, password, **extra):
        if not email:
            raise ValueError("El correo es obligatorio")
        usuario = self.model(email=self.normalize_email(email), **extra)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear_usuario(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("rol", Usuario.Rol.ADMINISTRADOR)
        return self._crear_usuario(email, password, **extra)


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        PACIENTE = "PACIENTE", "Paciente"
        PROFESIONAL = "PROFESIONAL", "Profesional"
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"

    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        PENDIENTE_VERIFICACION = "PENDIENTE_VERIFICACION", "Pendiente de verificación"
        SUSPENDIDA = "SUSPENDIDA", "Suspendida"
        BLOQUEADA = "BLOQUEADA", "Bloqueada"

    username = None
    email = models.EmailField("correo", max_length=120, unique=True)
    first_name = models.CharField("nombre", max_length=80)
    last_name = models.CharField("apellido", max_length=80)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.PACIENTE)
    estado = models.CharField(max_length=25, choices=Estado.choices, default=Estado.ACTIVA)
    intentos_fallidos = models.PositiveIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UsuarioManager()

    class Meta:
        db_table = "usuario"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class Profesional(models.Model):
    usuario = models.OneToOneField(
        Usuario,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profesional",
    )
    registro = models.CharField(max_length=20, unique=True)
    especialidad = models.CharField(max_length=80)
    centro = models.CharField(max_length=120)
    comuna = models.CharField(max_length=60)
    verificado = models.BooleanField(default=False)

    class Meta:
        db_table = "profesional"
        verbose_name_plural = "profesionales"

    def __str__(self):
        return f"{self.usuario} - {self.especialidad}"
