# actividades/forms.py

from django import forms
from django.forms import modelformset_factory
from datetime import date
from .models import (
    # Modelos existentes
    ReporteDiarioMaquinaria, ReportePersonal, Actividad,
    PartidaActividad, AvanceDiario, ReporteClima,
    # Nuevos modelos para el desglose
    MetaPorZona, AvancePorZona
)

# --- Formularios sin cambios ---
class ReporteMaquinariaForm(forms.ModelForm):
    class Meta:
        model = ReporteDiarioMaquinaria
        fields = [
            'fecha', 'empresa', 'partida', 'tipo_maquinaria', 'zona_trabajo',
            'cantidad_total', 'cantidad_activa', 'cantidad_inactiva', 'observaciones',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'empresa': forms.Select(attrs={'class': 'form-control'}),
            'partida': forms.Select(attrs={'class': 'form-control'}),
            'tipo_maquinaria': forms.Select(attrs={'class': 'form-control'}),
            'zona_trabajo': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_total': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_activa': forms.NumberInput(attrs={'class': 'form-control'}),
            'cantidad_inactiva': forms.NumberInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'fecha' in self.fields:
            self.fields['fecha'].initial = date.today()

class ReportePersonalForm(forms.ModelForm):
    class Meta:
        model = ReportePersonal
        fields = '__all__'
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and 'fecha' in self.fields:
            self.fields['fecha'].initial = date.today()
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ConsultaClimaForm(forms.Form):
    fecha = forms.DateField(
        label="Selecciona una fecha",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True,
        initial=date.today
    )

# --- Formularios Modificados y Nuevos ---

# --- 1. Formularios para el modelo Actividad ---

class MetaPorZonaForm(forms.ModelForm):
    class Meta:
        model = MetaPorZona
        # Añadir los nuevos campos de fecha
        fields = ['zona', 'meta', 'fecha_inicio_programada', 'fecha_fin_programada']
        # Añadir widgets para que aparezca el selector de calendario
        widgets = {
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date'}),
        }

# FormSet para manejar múltiples metas por zona
MetaPorZonaFormSet = modelformset_factory(
    MetaPorZona,
    form=MetaPorZonaForm,
    extra=1, # Permitir añadir una nueva zona vacía
    can_delete=True # Permitir eliminar zonas existentes
)

class ActividadForm(forms.ModelForm):
    # ELIMINADO: Campo 'tipo_registro_meta' ya no es necesario
    # TIPO_REGISTRO_CHOICES = [...]
    # tipo_registro_meta = forms.ChoiceField(...)

    class Meta:
        model = Actividad
        # MODIFICADO: Se elimina 'tipo_registro_meta' y 'meta_general' de los fields.
        # Ahora siempre se registrarán las metas por zona a través del FormSet.
        fields = [
            'nombre', 'padre', 'proyecto', 'partida',
            'unidad_medida', 'fecha_inicio_programada', 'fecha_fin_programada'
        ]
        widgets = {
            'fecha_inicio_programada': forms.DateInput(attrs={'type': 'date'}),
            'fecha_fin_programada': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplica la clase 'form-control' a todos los widgets
        for field_name, field in self.fields.items():
            # Evita sobreescribir widgets que no son de input estándar (como RadioSelect si lo hubiera)
            if hasattr(field.widget, 'attrs'):
                existing_classes = field.widget.attrs.get('class', '')
                # Asegura no duplicar la clase si ya existe
                if 'form-control' not in existing_classes:
                    field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

        # Establece fechas iniciales solo si es una nueva instancia
        if not self.instance.pk:
            if 'fecha_inicio_programada' in self.fields:
                self.fields['fecha_inicio_programada'].initial = date.today()
            if 'fecha_fin_programada' in self.fields:
                 self.fields['fecha_fin_programada'].initial = date.today()

        # Ajusta el queryset del campo 'padre' para excluirse a sí mismo si se está editando
        if 'padre' in self.fields:
            queryset = Actividad.objects.all()
            if self.instance and self.instance.pk:
                # Excluir la instancia actual y sus descendientes para evitar bucles
                descendientes_pks = list(self.instance.sub_actividades.values_list('pk', flat=True)) # Simplificado
                # Podríamos añadir recursión aquí si la jerarquía es profunda, pero por ahora excluimos solo hijos directos
                pks_a_excluir = [self.instance.pk] + descendientes_pks
                queryset = queryset.exclude(pk__in=pks_a_excluir)

            self.fields['padre'].queryset = queryset.order_by('padre__nombre', 'nombre')
            # Opcional: añadir una opción vacía para claridad
            self.fields['padre'].empty_label = "--- Ninguna (Categoría Raíz) ---"

# --- 2. Formularios para el modelo AvanceDiario ---

class AvancePorZonaForm(forms.ModelForm):
    """Formulario para una sola entrada de avance por zona."""
    class Meta:
        model = AvancePorZona
        fields = ['zona', 'cantidad']
        widgets = { # Asegurar que los widgets tengan la clase correcta
            'zona': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
        }

# FormSet para manejar múltiples avances por zona en un día
AvancePorZonaFormSet = modelformset_factory(
    AvancePorZona,
    form=AvancePorZonaForm,
    extra=1, # Permitir añadir una nueva zona vacía
    can_delete=True # Permitir eliminar zonas existentes
)

class AvanceDiarioForm(forms.ModelForm):
    # ELIMINADO: Campo 'tipo_registro' ya no es necesario
    # TIPO_REGISTRO_CHOICES = [...]
    # tipo_registro = forms.ChoiceField(...)

    class Meta:
        model = AvanceDiario
        # MODIFICADO: Se elimina 'tipo_registro' y 'cantidad_general'.
        # Ahora siempre se registrará el avance por zonas usando el FormSet.
        fields = ['actividad', 'fecha_reporte', 'empresa']
        widgets = {
            'fecha_reporte': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        # Tomamos el queryset filtrado como argumento extra
        actividad_queryset = kwargs.pop('actividad_queryset', None)
        super().__init__(*args, **kwargs)

        # Establece fecha inicial solo si es nuevo
        if not self.instance.pk and 'fecha_reporte' in self.fields:
            self.fields['fecha_reporte'].initial = date.today()

        # Aplica clase 'form-control' a todos los campos
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                existing_classes = field.widget.attrs.get('class', '')
                if 'form-control' not in existing_classes:
                     field.widget.attrs['class'] = f'{existing_classes} form-control'.strip()

        # Si se proporcionó un queryset filtrado para 'actividad', lo usamos
        if actividad_queryset is not None:
            self.fields['actividad'].queryset = actividad_queryset
        elif 'actividad' in self.fields: # Asegurar que el campo exista
             # Por defecto, filtramos para mostrar solo actividades 'hoja' (sin hijos)
             # Esto debería ajustarse según la lógica de negocio (¿se puede reportar avance en categorías padre?)
             self.fields['actividad'].queryset = Actividad.objects.filter(sub_actividades__isnull=True).order_by('nombre')