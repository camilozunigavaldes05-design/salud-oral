from django import forms

from cuentas.models import Usuario


class FiltroUsuariosForm(forms.Form):
    buscar = forms.CharField(label="Buscar", required=False, widget=forms.TextInput(attrs={"type": "search", "placeholder": "Nombre o correo"}))
    rol = forms.ChoiceField(label="Rol", required=False, choices=[("", "Todos")] + Usuario.Rol.choices)
    estado = forms.ChoiceField(label="Estado", required=False, choices=[("", "Todos")] + Usuario.Estado.choices)


class FiltroAuditoriaForm(forms.Form):
    usuario = forms.CharField(label="Usuario", required=False, widget=forms.TextInput(attrs={"type": "search", "placeholder": "Correo"}))
    accion = forms.ChoiceField(label="Acción", required=False)
    desde = forms.DateField(label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, acciones=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accion"].choices = [("", "Todas")] + [(accion, accion) for accion in acciones]
